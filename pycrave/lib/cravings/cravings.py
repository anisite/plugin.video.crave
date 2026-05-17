import json
import requests
import logging

logger = logging.getLogger(__name__)

PLAYBACK_BASE = 'https://playback.rte-api.bellmedia.ca'
CRAVINGS_BASE = 'https://cravings.rte-api.bellmedia.ca'

_HEADERS = {
    'accept': '*/*',
    'accept-encoding': 'gzip, deflate, br',
    'content-type': 'application/json',
    'origin': 'https://www.crave.ca',
    'referer': 'https://www.crave.ca/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'x-client-platform': 'platform_jasper_web',
}


def get_bookmark(session: requests.Session, token: str, content_id: str, content_package_id: str) -> int:
    """Return server resume position in seconds, or 0 if none."""
    url = '{}/contents/{}/bookmark/{}'.format(PLAYBACK_BASE, content_id, content_package_id)
    headers = dict(_HEADERS)
    headers['authorization'] = 'Bearer ' + token
    try:
        r = session.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            offset = json.loads(r.text).get('startOffset', 0) or 0
            logger.debug('Server bookmark for {}: {}s'.format(content_id, offset))
            return int(offset)
        if r.status_code == 404:
            return 0
        logger.warning('get_bookmark returned {} for {}'.format(r.status_code, content_id))
    except Exception as e:
        logger.error('get_bookmark failed: {}'.format(e))
    return 0


def post_bookmark(session: requests.Session, token: str,
                  content_id: str, content_package_id: str, package_code: str,
                  media_id: str, content_type: str,
                  offset: int, duration: int) -> bool:
    """Save playback position to Crave server."""
    up_next = max(0, duration - 32) if duration else 0
    payload = {
        'contentId': str(content_id),
        'contentPackageId': str(content_package_id),
        'contentType': content_type,
        'duration': str(duration),
        'mediaId': str(media_id),
        'offset': offset,
        'packageCode': package_code,
        'upNextOffsetInSeconds': str(up_next),
    }
    headers = dict(_HEADERS)
    headers['authorization'] = 'Bearer ' + token
    try:
        r = session.post('{}/cravings/bookmark'.format(CRAVINGS_BASE),
                         headers=headers, json=payload, timeout=5)
        if r.status_code in (200, 201, 204):
            logger.debug('Bookmark saved: {}s for contentId={}'.format(offset, content_id))
            return True
        logger.warning('post_bookmark returned {} for {}'.format(r.status_code, content_id))
    except Exception as e:
        logger.error('post_bookmark failed: {}'.format(e))
    return False
