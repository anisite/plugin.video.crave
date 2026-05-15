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
from list_items import add_item, add_search_item
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
        try:
            import inputstreamhelper
            is_helper = inputstreamhelper.Helper(PROTOCOL, drm=DRM)
            if not is_helper.check_inputstream():
                exit(0)
            inputstream_addon = is_helper.inputstream_addon
        except ImportError:
            inputstream_addon = 'inputstream.adaptive'

        play_item = xbmcgui.ListItem(path=play_infos.manifest_url)
        play_item.setMimeType('application/dash+xml')
        play_item.setContentLookup(False)
        play_item.setProperty('inputstream', inputstream_addon)
        play_item.setProperty('inputstream.adaptive.manifest_type', PROTOCOL)
        play_item.setProperty('inputstream.adaptive.license_type', DRM)
        play_item.setProperty(
            'inputstream.adaptive.license_key', play_infos.license_url + '||R{SSM}|')
        xbmcplugin.setResolvedUrl(ADDON_HANDLE, True, play_item)
