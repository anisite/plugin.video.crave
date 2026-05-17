import utils
from pycrave import Crave
import logging
import os
from urllib import parse
import sys
import ast
import xbmcvfs
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmc
from pycrave.common.search_result import SearchResult
from pycrave.common.result_info import MovieResultInfo
from pycrave.common.media import Media, MediaEpisode
from pycrave.common.category import Category
from list_items import add_item, add_search_item, add_favorites_item, init_dbs
from pycrave.common.favorites_db import FavoritesDB
from pycrave.lib.cravings import cravings as cravings_api
from langs import get_text


PROTOCOL = 'mpd'
DRM = 'com.widevine.alpha'


# LOGGER
LOGGER = logging.getLogger(__name__)


# VARIABLES
ADDON = utils.get_addon()
ADDON_NAME = utils.get_addon_name()
CACHE_DIR = utils.get_cache_dir()

# SETTINGS
USERNAME = utils.get_setting('username')
PASSWORD = utils.get_setting('password')
META_LANG = utils.get_setting('metadata_lang')
PLAY_LANG = utils.get_setting('audio_lang')
utils.check_user_pass()

# PARSE ARGUMENTS
BASE_URL = utils.get_base_url()
ADDON_HANDLE = utils.get_handle()
URL = utils.get_url()
OBJ_TYPE = utils.get_obj_type()
CMDS = utils.get_cmds()
utils.check_url()

# DATABASES
_PROFILE_DIR = utils.get_profile_dir()
favorites_db = FavoritesDB(os.path.join(_PROFILE_DIR, 'favorites.json'))
init_dbs(favorites_db)

# INITIALIZE CLIENT
crave = Crave(
    cache_dir=CACHE_DIR,
    username=USERNAME,
    password=PASSWORD,
    metadata_lang=META_LANG
)

# CHECK LOGIN
if crave.account_infos == None:
    xbmcgui.Dialog().ok(ADDON_NAME, get_text('login_error'))
    exit(1)

# SETUP GUI
# Estuary skin view IDs:
#   500 grid (poster wall) | 50 thumb-right | 55 list | 51 caroussel | 502 fixed_right
GRID_VIEW = '500'
LIST_VIEW = '55'
EPISODES_VIEW = '502'


class CravePlayer(xbmc.Player):
    """Monitors playback to save/clear resume positions."""

    def __init__(self, play_id, content_package_id='', package_code='',
                 media_id='', content_type='episode'):
        super().__init__()
        self._play_id = play_id
        self._content_package_id = content_package_id
        self._package_code = package_code
        self._media_id = media_id
        self._content_type = content_type
        self._last_pos = 0
        self._last_dur = 0

    def tick(self):
        """Capture current playback position while the player is active."""
        try:
            self._last_pos = int(self.getTime())
            self._last_dur = int(self.getTotalTime())
        except Exception:
            pass

    def onPlayBackPaused(self):
        self.tick()
        self._post_bookmark(self._last_pos, self._last_dur)
        LOGGER.debug('Paused: bookmark saved {}s for {}'.format(self._last_pos, self._play_id))

    def onPlayBackStopped(self):
        self._save()

    def onPlayBackError(self):
        self._save()

    def onPlayBackEnded(self):
        self._post_bookmark(0)
        LOGGER.debug('Playback ended naturally for {}'.format(self._play_id))

    def _save(self):
        if self._last_pos > 0:
            self._post_bookmark(self._last_pos, self._last_dur)
            LOGGER.debug('Resume saved: {}s for {}'.format(self._last_pos, self._play_id))
        else:
            LOGGER.debug('No position to save for {}'.format(self._play_id))

    def _post_bookmark(self, offset, duration=0):
        if not self._content_package_id or not self._media_id:
            return
        try:
            cravings_api.post_bookmark(
                session=crave.session,
                token=crave.login_handler.access_token,
                content_id=self._play_id,
                content_package_id=self._content_package_id,
                package_code=self._package_code,
                media_id=self._media_id,
                content_type=self._content_type,
                offset=offset,
                duration=duration,
            )
        except Exception as e:
            LOGGER.error('Failed to post bookmark: {}'.format(e))


def _set_content_for(elements):
    has_movie = any(getattr(e, 'media_type', '') == 'movie' for e in elements)
    has_show = any(getattr(e, 'media_type', '') == 'tvshow' for e in elements)
    has_result = any(getattr(e, 'obj_type', '') == 'result' for e in elements)
    if has_movie and not has_show:
        xbmcplugin.setContent(ADDON_HANDLE, 'movies')
    elif has_show and not has_movie:
        xbmcplugin.setContent(ADDON_HANDLE, 'tvshows')
    elif has_result:
        xbmcplugin.setContent(ADDON_HANDLE, 'videos')
    else:
        xbmcplugin.setContent(ADDON_HANDLE, 'files')
    return GRID_VIEW if has_result else LIST_VIEW


# COMMAND
if OBJ_TYPE == 'none':

    # COMMAND: MAIN MENU
    if CMDS == 'main':
        xbmcplugin.setContent(ADDON_HANDLE, 'files')
        add_search_item()
        add_favorites_item()
        elements = crave.get_root_categories()
        if elements is not None:
            for element in elements:
                list_item = add_item(element, len(elements))
                if list_item is None:
                    continue
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            xbmc.executebuiltin("Container.SetViewMode({})".format(LIST_VIEW))

    # COMMAND: SEARCH
    elif CMDS == 'search':
        search_terms = utils.search_modal()
        if search_terms is None or search_terms.strip() == '':
            exit(0)
        results = crave.search(search_terms)
        if results is not None:
            view_mode = _set_content_for(results)
            for result in results:
                list_item = add_item(result, len(results))
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            xbmc.executebuiltin("Container.SetViewMode({})".format(view_mode))

    # COMMAND: FAVORITES LIST
    elif CMDS == 'favorites':
        xbmcplugin.setContent(ADDON_HANDLE, 'videos')
        favs = favorites_db.get_all()
        for fav in favs:
            r = SearchResult(
                id=fav['id'],
                title=fav['title'],
                image=fav.get('image', ''),
                media_type=fav.get('media_type', ''),
            )
            add_item(r, len(favs))
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        xbmc.executebuiltin('Container.SetViewMode({})'.format(GRID_VIEW))

    # COMMAND: TOGGLE FAVORITE (RunPlugin — no directory)
    elif CMDS == 'toggle_favorite':
        args = parse.parse_qs(URL[1:])
        fav_id = args.get('fav_id', [''])[0]
        if fav_id:
            added = favorites_db.toggle(
                fav_id,
                args.get('fav_title', [''])[0],
                args.get('fav_image', [''])[0],
                args.get('fav_media_type', [''])[0],
            )
            msg = 'Ajouté aux favoris' if added else 'Retiré des favoris'
            xbmcgui.Dialog().notification(ADDON_NAME, msg, time=2000)
        xbmc.executebuiltin('Container.Refresh')

# CATEGORY PROVIDED
elif OBJ_TYPE == 'category':
    category = Category.from_url(URL)
    elements = crave.get_elements(category)
    if elements is not None:
        view_mode = _set_content_for(elements)
        for element in elements:
            list_item = add_item(element, len(elements))
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        xbmc.executebuiltin("Container.SetViewMode({})".format(view_mode))

# RESULT PROVIDED
elif OBJ_TYPE == 'result':
    result = SearchResult.from_url(URL)
    title = crave.get_result_infos(result)
    if title is not None and PLAY_LANG in title:
        title = title[PLAY_LANG]
        if title.type == 'serie':
            xbmcplugin.setContent(ADDON_HANDLE, 'episodes')
            view_mode = EPISODES_VIEW
        else:
            xbmcplugin.setContent(ADDON_HANDLE, 'movies')
            view_mode = GRID_VIEW
        list_item = add_item(title)
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        xbmc.executebuiltin("Container.SetViewMode({})".format(view_mode))

# MEDIA PROVIDED
elif OBJ_TYPE == 'media':
    media = Media.from_url(URL)
    play_infos = crave._get_play_infos_media(media)

    if play_infos is None:
        xbmcgui.Dialog().ok(ADDON_NAME, 'No playback info available.')
    else:
        is_live = media.additionnal_infos.get('is_live', False)

        try:
            import inputstreamhelper
            if play_infos.is_hls:
                is_helper = inputstreamhelper.Helper('hls')
            else:
                is_helper = inputstreamhelper.Helper(PROTOCOL, drm=DRM)
            if not is_helper.check_inputstream():
                exit(0)
            inputstream_addon = is_helper.inputstream_addon
        except ImportError:
            inputstream_addon = 'inputstream.adaptive'

        play_item = xbmcgui.ListItem(path=play_infos.manifest_url)
        play_item.setContentLookup(False)
        play_item.setProperty('inputstream', inputstream_addon)

        if play_infos.is_hls:
            play_item.setMimeType('application/x-mpegURL')
            play_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        else:
            play_item.setMimeType('application/dash+xml')
            play_item.setProperty('inputstream.adaptive.manifest_type', PROTOCOL)
            play_item.setProperty('inputstream.adaptive.license_type', DRM)
            play_item.setProperty(
                'inputstream.adaptive.license_key', play_infos.license_url + '||R{SSM}|')
            play_item.setProperty('inputstream.adaptive.license_flags', 'persistent_storage')

        if not is_live:
            server_pos = cravings_api.get_bookmark(
                session=crave.session,
                token=crave.login_handler.access_token,
                content_id=media.play_id,
                content_package_id=play_infos.content_package_id,
            )
            if server_pos > 60:
                play_item.setProperty('StartOffset', str(server_pos))

        content_type = 'movie' if media.type == 'movie' else 'episode'
        player = CravePlayer(
            play_id=media.play_id,
            content_package_id='' if is_live else play_infos.content_package_id,
            package_code='' if is_live else play_infos.package_code,
            media_id='' if is_live else media.additionnal_infos.get('media_id', ''),
            content_type=content_type,
        )
        xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, play_item)

        # Keep script alive so player callbacks (stop/end) can fire
        monitor = xbmc.Monitor()
        wait = 0
        while wait < 20 and not monitor.abortRequested() and not player.isPlaying():
            monitor.waitForAbort(0.5)
            wait += 1
        while not monitor.abortRequested() and player.isPlaying():
            monitor.waitForAbort(1)
            player.tick()
