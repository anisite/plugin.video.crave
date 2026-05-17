from copy import deepcopy
import base64
import json

from pycrave.common.category import Category
from ...common.media import MediaEpisode, MediaMovie
from ...common.result_info import ResultInfo, SerieResultInfo, MovieResultInfo
from ...common.search_result import SearchResult
from ...common.utils import format_episode_number

import requests
import logging
from .consts import (
  HEADERS, RTE_GRAPHQL_URL,
  GET_APP_PAYLOAD, GET_SCREEN_PAYLOAD, GET_CONTAINER_PAYLOAD,
  GET_SEARCH_PAYLOAD, GET_SHOWPAGE_PAYLOAD, GET_SEASON_PAYLOAD,
  GET_CONTINUE_WATCHING_PAYLOAD, GET_MY_LIST_PAYLOAD
)
from typing import Any, Dict, List, Union
from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)


class GraphQL():

  def __init__(self, session: requests.Session, tag: str,
               access_token: str = None, metadata_language: str = 'fr'):
    self.session = session
    self.tag = tag
    self.access_token = access_token
    self.subscriptions: List[str] = []
    self.scopes: List[str] = []
    self.packages: List[str] = []
    if metadata_language.lower() in ('en', 'english'):
      self.metadata_language = 'ENGLISH'
    else:
      self.metadata_language = 'FRENCH'

  @property
  def _user_language(self) -> str:
    return 'EN' if self.metadata_language == 'ENGLISH' else 'FR'

  # ===================================================================
  #   REQUESTS
  # ===================================================================

  def _build_bearer(self) -> str:
    payload = {'platform': 'platform_web', 'accessToken': self.access_token}
    raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    return base64.b64encode(raw).decode('ascii')

  def _make_rte_request(self, payload: dict, lang: str = None) -> requests.Response:
    data = deepcopy(payload)
    user_lang = lang or self._user_language
    if 'variables' in data and 'sessionContext' in data['variables']:
      data['variables']['sessionContext'] = {'userMaturity': 'ADULT', 'userLanguage': user_lang}
    headers = deepcopy(HEADERS)
    headers['Authorization'] = 'Bearer {}'.format(self._build_bearer())
    headers['x-client-platform'] = 'platform_web'
    headers['Accept-Language'] = 'fr-CA,fr;q=0.9,en;q=0.5' if user_lang == 'FR' else 'en-CA,en;q=0.9,fr;q=0.5'
    return self.session.post(url=RTE_GRAPHQL_URL, headers=headers, json=data)

  # ===================================================================
  #   CATEGORIES
  # ===================================================================

  def get_root_categories(self) -> List[Category]:
    return self.get_elements_screen(id=None, root=True)

  def get_elements(self, category: Category) -> List[Union[Category, SearchResult]]:
    if category is None:
      return None
    if category.type == 'screen':
      return self.get_elements_screen(category.id)
    elif category.type == 'continue_watching':
      return self._get_continue_watching()
    elif category.type == 'my_list':
      return self._get_my_list()
    elif category.type in ('rotator', 'grid', 'container'):
      return self.get_elements_container(category.id)
    return None

  def get_elements_screen(self, id: str, root: bool = False) -> List[Union[Category, SearchResult]]:
    if root:
      return self._get_root_categories_rte()
    return self._get_screen_rte(id)

  def _get_root_categories_rte(self) -> List[Category]:
    payload = deepcopy(GET_APP_PAYLOAD)
    response = self._make_rte_request(payload)
    if response.status_code != 200:
      logger.error('GetApp failed ({})'.format(response.status_code))
      return []
    screens = []
    try:
      nav_links = json.loads(response.text)['data']['app']['navigation']['navigationLinks']
      for link in nav_links:
        try:
          l = link.get('link') or {}
          action = l.get('action') or {}
          if action.get('__typename') != 'Screen':
            continue
          screen_id = action.get('id')
          title = l.get('displayTitle', '')
          path = (action.get('path') or '').lower()
          if screen_id and title:
            screens.append({'id': screen_id, 'title': title, 'path': path})
        except Exception:
          continue
    except Exception:
      logger.error('Failed to parse GetApp navigation')

    # Identify the home screen and inline its containers, with the remaining
    # screens listed alongside as folders.
    home = next((s for s in screens if s['path'] == 'home' or 'home' in s['id']), None)
    non_home_ids = {s['id'] for s in screens if home is None or s['id'] != home['id']}
    elements: List[Union[Category, SearchResult]] = []
    if home is not None:
      # Inline home containers but drop any sub-nav links that are already
      # top-level screens (avoids duplicates like "Junior" appearing twice).
      for el in self._get_screen_rte(home['id']):
        if getattr(el, 'id', None) in non_home_ids:
          continue
        elements.append(el)
    for s in screens:
      if home is not None and s['id'] == home['id']:
        continue
      elements.append(Category(type='screen', title=s['title'], id=s['id'], style='SCREEN'))
    return elements

  def _get_screen_rte(self, id: str) -> List[Union[Category, SearchResult]]:
    if not id:
      return []
    payload = deepcopy(GET_SCREEN_PAYLOAD)
    payload['variables']['id'] = id
    response = self._make_rte_request(payload)
    if response.status_code != 200:
      logger.error('GetScreen failed ({}) for id={}'.format(response.status_code, id))
      return []
    elements = []
    try:
      screen = json.loads(response.text)['data']['screen'] or {}

      # Secondary navigation links
      nav = screen.get('navigation') or {}
      for link in nav.get('navigationLinks') or []:
        try:
          action = link.get('action') or {}
          if action.get('__typename') == 'Screen':
            elements.append(Category(
              type='screen',
              title=link.get('displayTitle', ''),
              id=action['id'],
              style='SCREEN'
            ))
        except Exception:
          continue

      # Screen containers
      containers = [
        c for c in (screen.get('screenContentsPage') or {}).get('screenContents') or []
        if c.get('__typename') == 'Container'
      ]

      if not elements and len(containers) == 1:
        return self.get_elements_container(containers[0]['id'])

      seen_titles = set()
      for c in containers:
        title = (c.get('displayTitle') or '').strip()
        style = (c.get('style') or '').upper()
        # Skip promo teasers (style=TEASER) and CMS internal titles
        # (e.g. "Advanced Container | EN/FR | ... | Promo Teasers")
        if not title or style == 'TEASER' or '|' in title:
          continue
        # Skip duplicate titles (API sometimes returns same-named containers)
        title_key = title.lower()
        if title_key in seen_titles:
          continue
        seen_titles.add(title_key)
        if style == 'CONTINUEWATCHING':
          elements.append(Category(type='continue_watching', title=title, id=c['id'], style=style))
        elif style == 'MYLIST':
          elements.append(Category(type='my_list', title=title, id=c['id'], style=style))
        else:
          elements.append(Category(type='container', title=title, id=c['id'], style=style))
    except Exception:
      logger.error('Failed to parse GetScreen response for id={}'.format(id))
    return elements

  def get_elements_container(self, id: str) -> List[SearchResult]:
    if not id:
      return []
    payload = deepcopy(GET_CONTAINER_PAYLOAD)
    payload['variables']['id'] = id
    response = self._make_rte_request(payload)
    if response.status_code != 200:
      logger.error('GetPosterRotator failed ({}) for id={}'.format(response.status_code, id))
      return []
    elements = []
    try:
      items = json.loads(response.text)['data']['container']['containerItemsPage']['items']
      for item in items or []:
        result = self._parse_media_metadata(item)
        if result:
          elements.append(result)
    except Exception:
      logger.error('Failed to parse container response for id={}'.format(id))
    return elements

  # kept for compatibility
  def get_elements_rotator(self, id: str):
    return self.get_elements_container(id)

  def get_elements_grid(self, id: str):
    return self.get_elements_container(id)

  def _get_continue_watching(self) -> List[SearchResult]:
    payload = deepcopy(GET_CONTINUE_WATCHING_PAYLOAD)
    response = self._make_rte_request(payload)
    if response.status_code != 200:
      logger.error('GetContinueWatching failed ({})'.format(response.status_code))
      return []
    elements = []
    try:
      items = json.loads(response.text)['data']['continueWatchingItemsPage']['items'] or []
      for item in items:
        media = item.get('media') or {}
        if not media.get('id'):
          continue
        r = self._parse_media_metadata(media)
        if r:
          elements.append(r)
    except Exception as e:
      logger.error('Failed to parse continue watching: {}'.format(e))
    return elements

  def _get_my_list(self) -> List[SearchResult]:
    payload = deepcopy(GET_MY_LIST_PAYLOAD)
    response = self._make_rte_request(payload)
    if response.status_code != 200:
      logger.error('GetMyList failed ({})'.format(response.status_code))
      return []
    elements = []
    try:
      items = json.loads(response.text)['data']['myListItemsPage']['items'] or []
      for item in items:
        if not item.get('id'):
          continue
        r = self._parse_media_metadata(item)
        if r:
          elements.append(r)
    except Exception as e:
      logger.error('Failed to parse my list: {}'.format(e))
    return elements

  # ===================================================================
  #   SEARCH
  # ===================================================================

  def search(self, input: str) -> List[SearchResult]:
    if not input or len(input.strip()) < 3:
      return []
    payload = deepcopy(GET_SEARCH_PAYLOAD)
    payload['variables']['searchQuery'] = input.strip()
    response = self._make_rte_request(payload)
    if response.status_code != 200:
      logger.error('GetSearch failed ({})'.format(response.status_code))
      return []
    suggestions = []
    try:
      results = json.loads(response.text)['data']['search']['mediaResults']
      for item in results or []:
        r = self._parse_media_metadata(item)
        if r:
          suggestions.append((fuzz.partial_ratio(r.title, input), r))
    except Exception:
      logger.error('Failed to parse search response')
    return [x for _, x in sorted(suggestions, reverse=True)][:50]

  # ===================================================================
  #   RESULT INFOS
  # ===================================================================

  def get_result_infos(self, result: SearchResult) -> Dict[str, Union[MovieResultInfo, SerieResultInfo]]:
    return self.get_result_infos_id(result.id)

  def get_result_infos_id(self, content_id: str) -> Dict[str, Union[MovieResultInfo, SerieResultInfo]]:
    if not content_id:
      return None
    logger.debug('Getting showpage for id={}'.format(content_id))
    payload = deepcopy(GET_SHOWPAGE_PAYLOAD)
    payload['variables']['ids'] = [content_id]
    infos = {}
    for lang in ('FR', 'EN'):
      response = self._make_rte_request(payload, lang=lang)
      if response.status_code != 200:
        logger.warning('GetShowpage {} failed ({})'.format(lang, response.status_code))
        continue
      try:
        medias = json.loads(response.text)['data']['medias']
        if not medias:
          continue
        media = medias[0]
        media_type = (media.get('mediaType') or '').upper()
        version = lang.lower()
        if media_type == 'MOVIE':
          info = self._parse_movie(media, version)
        elif media_type == 'SERIES':
          info = self._parse_series(media, version, lang)
        else:
          logger.warning('Unknown mediaType: {}'.format(media_type))
          continue
        if info and info.medias:
          info.version = version
          infos[version] = info
      except Exception as e:
        logger.error('Failed to parse showpage {} for id={}: {}'.format(lang, content_id, e))
    return infos if infos else None

  # ===================================================================
  #   PARSERS
  # ===================================================================

  def _parse_media_metadata(self, item: dict) -> SearchResult:
    try:
      typename = item.get('__typename') or 'MediaMetadata'
      # ContentMetadata (e.g. EPISODIC containers): redirect to parent media so
      # the user lands on the show page instead of trying to play one episode.
      if typename == 'ContentMetadata':
        media = item.get('media') or {}
        if not media.get('id'):
          return None
        result = SearchResult()
        episode_title = item.get('title') or ''
        season_num = item.get('seasonNumber')
        episode_num = item.get('episodeNumber')
        label = media.get('title') or ''
        if season_num and episode_num:
          label = '{} - S{:0>2}E{:0>2}'.format(label, season_num, episode_num)
          if episode_title:
            label = '{}: {}'.format(label, episode_title)
        result.title = label
        result.search_title = media.get('title') or label
        result.id = media['id']
        result.platform_tag = self.tag
        result.has_access = not item.get('locked', False)
        result.description = item.get('shortDescription') or ''
        result.media_type = 'tvshow'
        imgs = item.get('metadataImages') or {}
        try:
          result.image = (imgs.get('poster') or {}).get('url') or ''
        except Exception:
          pass
        try:
          result.fanart = (imgs.get('thumbnail') or {}).get('url') or ''
        except Exception:
          pass
        return result

      # MediaMetadata (default)
      result = SearchResult()
      result.title = item['title']
      result.search_title = item['title']
      result.id = item['id']
      result.platform_tag = self.tag
      result.has_access = not item.get('locked', False)
      result.description = item.get('shortDescription') or item.get('description') or ''
      mt = (item.get('mediaType') or '').upper()
      if mt == 'MOVIE':
        result.media_type = 'movie'
      elif mt == 'SERIES':
        result.media_type = 'tvshow'
      imgs = item.get('metadataImages') or {}
      try:
        result.image = (imgs.get('poster') or {}).get('url') or ''
      except Exception:
        pass
      try:
        result.fanart = (imgs.get('thumbnail') or {}).get('url') or ''
      except Exception:
        pass
      try:
        result.logo = (item.get('originatingNetworkLogo') or {}).get('url') or ''
      except Exception:
        pass
      return result
    except Exception:
      return None

  # kept for compatibility with list_items.py
  def parse_search_result(self, item: dict) -> SearchResult:
    return self._parse_media_metadata(item)

  def _parse_movie(self, media: dict, version: str) -> MovieResultInfo:
    first = media.get('firstContent')
    if not first:
      logger.debug('No firstContent for movie id={}'.format(media.get('id')))
      return None

    for indicator in first.get('languageIndicators') or []:
      for lang in indicator.get('languages') or []:
        if lang.get('langCode', '').lower() != version:
          continue
        m = MediaMovie()
        m.title = media.get('title', '')
        m.summary = media.get('description', '')
        m.description = media.get('description', '')
        m.play_id = str(first['id'])
        m.has_access = not lang.get('locked', True) and not first.get('locked', False)
        m.playback_languages = [lang['langCode'].lower()]
        m.additionnal_infos['destination'] = indicator['indicator']
        try:
          m.duration = int(first.get('duration', {}).get('timeInSecs', 0))
        except Exception:
          pass
        try:
          m.image = media['metadataImages']['poster']['url']
        except Exception:
          pass
        infos = MovieResultInfo()
        infos.title = media.get('title', '')
        infos.summary = media.get('description', '')
        infos.description = media.get('description', '')
        try:
          infos.year = int(media.get('productionYear', 0) or 0)
        except Exception:
          pass
        imgs = media.get('metadataImages') or {}
        try:
          infos.image = (imgs.get('poster') or {}).get('url') or ''
        except Exception:
          pass
        try:
          infos.fanart = (imgs.get('thumbnail') or {}).get('url') or ''
        except Exception:
          pass
        try:
          infos.logo = (media.get('originatingNetworkLogo') or {}).get('url') or ''
        except Exception:
          pass
        infos.medias['default'] = m
        return infos
    return None

  def _parse_series(self, media: dict, version: str, lang_code: str) -> SerieResultInfo:
    infos = SerieResultInfo()
    infos.title = media.get('title', '')
    infos.summary = media.get('description', '')
    infos.description = media.get('description', '')
    imgs = media.get('metadataImages') or {}
    try:
      infos.image = (imgs.get('poster') or {}).get('url') or ''
    except Exception:
      pass
    try:
      infos.fanart = (imgs.get('thumbnail') or {}).get('url') or ''
    except Exception:
      pass
    try:
      infos.logo = (media.get('originatingNetworkLogo') or {}).get('url') or ''
    except Exception:
      pass

    for season in media.get('seasons') or []:
      try:
        season_num = int(season['seasonNumber'])
      except Exception:
        continue

      payload = deepcopy(GET_SEASON_PAYLOAD)
      payload['variables']['id'] = season['id']
      response = self._make_rte_request(payload, lang=lang_code)
      if response.status_code != 200:
        logger.warning('GetContentBySeasonId failed ({}) season={}'.format(
          response.status_code, season_num))
        continue

      try:
        episodes = json.loads(response.text)['data']['contentsBySeasonId'] or []
      except Exception:
        continue

      for episode in episodes:
        try:
          ep_num = int(episode['episodeNumber'])
        except Exception:
          continue
        ep_tag = format_episode_number(season_num, ep_num)

        for indicator in episode.get('languageIndicators') or []:
          for lang in indicator.get('languages') or []:
            if lang.get('langCode', '').lower() != version:
              continue
            ep = MediaEpisode()
            ep.season = season_num
            ep.episode = ep_num
            ep.episode_tag = ep_tag
            ep.title = episode.get('title', '')
            ep.summary = episode.get('shortDescription', '')
            ep.description = episode.get('shortDescription', '')
            ep.play_id = str(episode['id'])
            ep.has_access = not lang.get('locked', True) and not episode.get('locked', False)
            ep.playback_languages = [lang['langCode'].lower()]
            ep.additionnal_infos['destination'] = indicator['indicator']
            try:
              ep.duration = int(episode.get('duration', {}).get('timeInSecs', 0))
            except Exception:
              pass
            try:
              ep.image = episode['metadataImages']['thumbnail']['url']
            except Exception:
              pass
            infos.medias[ep_tag] = ep
    return infos
