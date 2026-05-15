import json
from ...common.play_infos import PlayInfos
import requests
import logging

logger = logging.getLogger(__name__)


PLAYBACK_BASE_URL = 'https://playback.rte-api.bellmedia.ca'
STREAM_META_BASE_URL = 'https://stream.video.9c9media.com'
LICENSE_URL = 'https://license.9c9media.ca/widevine'

PLAYBACK_HEADERS = {
  'accept': '*/*',
  'accept-encoding': 'gzip',
  'connection': 'Keep-Alive',
  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
  'origin': 'https://www.crave.ca',
  'referer': 'https://www.crave.ca/',
  'x-client-platform': 'platform_jasper_web',
}

STREAM_HEADERS = {
  'accept': '*/*',
  'accept-encoding': 'gzip',
  'connection': 'Keep-Alive',
  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
  'origin': 'https://www.crave.ca',
  'referer': 'https://www.crave.ca/',
}


class CAPI():
  @staticmethod
  def get_play_infos(destination: str, content_id: str, language: str, token: str = None, filter: str = None) -> PlayInfos:
    '''
    `destination` is ignored (kept for backwards compatibility). The new flow
    resolves the destination and package via the playback service.
    '''
    if not token:
      logger.error('Playback requires a profile-scoped access token')
      return None

    # 1. Get content metadata (destination_id, package_code) from playback service
    meta = CAPI._get_playback_metadata(content_id, language, token)
    if not meta:
      return None
    destination_id = meta.get('destinationId')
    package_code = meta.get('packageCode')
    if destination_id is None or not package_code:
      logger.error('Playback metadata missing destinationId/packageCode')
      return None

    # 2. Get content package id from CAPI
    package_id = CAPI._get_package_id(package_code, content_id, language)
    if not package_id:
      return None

    # 3. Resolve the actual manifest URL via stream meta endpoint
    stream = CAPI._get_stream_urls(content_id, package_id, destination_id, token)
    if not stream:
      return None

    manifest_url = stream.get('playback')
    subtitles_url = stream.get('trickplay')
    if not manifest_url:
      logger.error('No playback URL in stream meta response')
      return None

    # Pass token via pipe-headers so inputstream.adaptive includes Authorization
    pipe_headers = 'User-Agent=okhttp%2F4.9.0&Authorization=Bearer+{}'.format(token)
    manifest_url_piped = manifest_url + '|{}'.format(pipe_headers)
    subtitles_url_piped = (subtitles_url + '|{}'.format(pipe_headers)) if subtitles_url else None
    license_url = LICENSE_URL + '?jwt={}'.format(token)

    return PlayInfos(
        manifest_url=manifest_url_piped,
        subtitles_url=subtitles_url_piped,
        license_url=license_url,
        manifest_headers=STREAM_HEADERS,
        license_headers=STREAM_HEADERS
    )

  @staticmethod
  def _get_playback_metadata(content_id: str, language: str, token: str) -> dict:
    url = '{}/contents/{}'.format(PLAYBACK_BASE_URL, content_id)
    headers = dict(PLAYBACK_HEADERS)
    headers['authorization'] = 'Bearer ' + token
    headers['x-playback-language'] = (language or 'fr').upper()
    headers['accept-language'] = headers['x-playback-language']
    logger.debug('Fetching playback metadata for content_id={}'.format(content_id))
    response = requests.get(url=url, headers=headers)
    if response.status_code != 200:
      logger.error('Playback metadata failed ({}): {}'.format(response.status_code, response.text[:200]))
      return None
    try:
      return json.loads(response.text)
    except Exception as e:
      logger.error('Failed to parse playback metadata: {}'.format(e))
      return None

  @staticmethod
  def _get_package_id(package_code: str, content_id: str, language: str) -> str:
    url = 'https://capi.9c9media.com/destinations/{}/platforms/android/contents/{}'.format(
      package_code, content_id)
    url += '?$lang={}&$include=[ContentPackages]'.format(language or 'fr')
    response = requests.get(url=url, headers={
      'accept-encoding': 'identity',
      'user-agent': 'okhttp/4.9.0',
    })
    if response.status_code != 200:
      logger.error('CAPI content lookup failed ({})'.format(response.status_code))
      return None
    try:
      packages = json.loads(response.text).get('ContentPackages') or []
      if not packages:
        logger.error('No content packages found')
        return None
      return str(packages[0]['Id'])
    except Exception as e:
      logger.error('Failed to parse CAPI content: {}'.format(e))
      return None

  @staticmethod
  def _get_stream_urls(content_id: str, package_id: str, destination_id: int, token: str) -> dict:
    url = ('{}/meta/content/{}/contentpackage/{}/destination/{}/platform/1'
           '?format=mpd&filter=fe&uhd=false&hd=true&mcv=false&mca=false'
           '&mta=true&stt=true&hdr10=true').format(
      STREAM_META_BASE_URL, content_id, package_id, destination_id)
    headers = dict(STREAM_HEADERS)
    headers['authorization'] = 'Bearer ' + token
    response = requests.get(url=url, headers=headers)
    if response.status_code != 200:
      logger.error('Stream meta failed ({}): {}'.format(response.status_code, response.text[:200]))
      return None
    try:
      return json.loads(response.text)
    except Exception as e:
      logger.error('Failed to parse stream meta: {}'.format(e))
      return None
