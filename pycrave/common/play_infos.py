from typing import Any, Dict
import xml.etree.ElementTree as ET
import logging

# Logger
logger = logging.getLogger(__name__)


class PlayInfos():
    def __init__(self, manifest_url, subtitles_url: str, license_token=None, license_url=None, manifest_headers=None, license_headers=None, package_code=None, content_package_id=None, is_hls=False):
        logger.debug('Initializing play infos...')
        self.manifest_url: str = manifest_url
        self.subtitles_url: str = subtitles_url
        self.license_url: str = license_url
        self.manifest_headers: Dict[str, str] = manifest_headers
        self.license_headers: Dict[str, str] = license_headers
        self.package_code: str = package_code or ''
        self.content_package_id: str = content_package_id or ''
        self.is_hls: bool = is_hls
        self.manifest_response = None

        if self.license_url is None:
            logger.debug('No license URL provided, trying to find it...')
            self._extract_license_url()

    def __str__(self) -> Dict[str, Any]:
        return str(self.__dict__)

    def _extract_license_url(self) -> str:
        pass

    def get_base_url(self) -> str:
        logger.debug('Extracting base URL...')
        try:
            logger.debug('Searching in manifest...')
            root = ET.fromstring(self.manifest_response.text)
            ns = {'mpd': 'urn:mpeg:dash:schema:mpd:2011'}
            el = root.find('mpd:BaseURL', ns) or root.find('BaseURL')
            if el is not None and el.text:
                logger.debug('Base URL: {}'.format(el.text))
                return el.text
        except:
            pass
        logger.error('Unable to find base URL')
        return None
