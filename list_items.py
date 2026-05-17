import xbmcgui
import xbmcplugin
import xbmcaddon
import sys
import os
import utils
import logging
from urllib.parse import urlencode
from pycrave.common.media import Media

LOGGER = logging.getLogger(__name__)

BASE_URL = utils.get_base_url()
ADDON_HANDLE = utils.get_handle()
RESOURCE_DIR = utils.get_ressource_dir()

DEFAULT_FANART = os.path.join(RESOURCE_DIR, 'fanart.jpg')
DEFAULT_FOLDER = os.path.join(RESOURCE_DIR, 'folder.png')
DEFAULT_SEARCH = os.path.join(RESOURCE_DIR, 'search.png')

# Map container/screen style -> custom icon (falls back to folder.png)
STYLE_ICONS = {
    'CONTINUEWATCHING': 'continue_watching.png',
    'MYLIST': 'my_list.png',
    'TOP10': 'top10.png',
    'LIVE': 'live.png',
    'EPISODIC': 'episodic.png',
    'SCREEN': 'screen.png',
    'FAVORITES': 'favorites.png',
}

# Module-level DB references set by init_dbs() from addon.py
_favorites_db = None


def init_dbs(favorites_db):
    global _favorites_db
    _favorites_db = favorites_db


def _icon_for_style(style):
    name = STYLE_ICONS.get((style or '').upper())
    if not name:
        return DEFAULT_FOLDER
    path = os.path.join(RESOURCE_DIR, name)
    return path if os.path.exists(path) else DEFAULT_FOLDER


def add_search_item():
    list_item = xbmcgui.ListItem('Search')
    list_item.setArt({
        'thumb': DEFAULT_SEARCH,
        'icon': DEFAULT_SEARCH,
        'fanart': DEFAULT_FANART,
    })
    xbmcplugin.addDirectoryItem(
        handle=ADDON_HANDLE,
        url=BASE_URL + '?' + urlencode({'cmds': 'search'}),
        listitem=list_item,
        isFolder=True)


def add_favorites_item():
    icon = _icon_for_style('FAVORITES')
    list_item = xbmcgui.ListItem('Mes favoris')
    list_item.setArt({'thumb': icon, 'icon': icon, 'fanart': DEFAULT_FANART})
    xbmcplugin.addDirectoryItem(
        handle=ADDON_HANDLE,
        url=BASE_URL + '?' + urlencode({'cmds': 'favorites'}),
        listitem=list_item,
        isFolder=True)


def add_item(element, total=None):
    if element.obj_type == 'category':
        return add_item_category(element, total)
    elif element.obj_type == 'result':
        return add_item_result(element, total)
    elif element.obj_type == 'title':
        return add_item_title(element)


def add_item_category(element, total):
    list_item = xbmcgui.ListItem(element.title)
    image = getattr(element, 'image', '') or _icon_for_style(getattr(element, 'style', ''))
    list_item.setArt({
        'thumb': image,
        'icon': image,
        'poster': image,
        'fanart': DEFAULT_FANART,
    })
    kwargs = {
        'handle': ADDON_HANDLE,
        'url': element.to_url(BASE_URL),
        'listitem': list_item,
        'isFolder': True,
    }
    if total is not None:
        kwargs['totalItems'] = total
    xbmcplugin.addDirectoryItem(**kwargs)


def add_item_result(element, total):
    list_item = xbmcgui.ListItem(element.title)
    poster = element.image or ''
    fanart = getattr(element, 'fanart', '') or poster or DEFAULT_FANART
    logo = getattr(element, 'logo', '') or ''
    art = {}
    if poster:
        art['poster'] = poster
        art['thumb'] = poster
        art['icon'] = poster
    if fanart:
        art['fanart'] = fanart
        art['landscape'] = fanart
    if logo:
        art['clearlogo'] = logo
    list_item.setArt(art)
    info = {'title': element.title}
    description = getattr(element, 'description', '') or ''
    if description:
        info['plot'] = description
        info['plotoutline'] = description
    media_type = getattr(element, 'media_type', '') or ''
    if media_type in ('movie', 'tvshow'):
        info['mediatype'] = media_type
    list_item.setInfo('video', info)
    # Favorites context menu
    if _favorites_db is not None:
        fav_label = 'Retirer des favoris' if _favorites_db.is_favorite(element.id) else 'Ajouter aux favoris'
        fav_url = BASE_URL + '?' + urlencode({
            'cmds': 'toggle_favorite',
            'fav_id': element.id,
            'fav_title': element.title,
            'fav_image': element.image or '',
            'fav_media_type': element.media_type or '',
        })
        list_item.addContextMenuItems([(fav_label, 'RunPlugin({})'.format(fav_url))])
    kwargs = {
        'handle': ADDON_HANDLE,
        'url': element.to_url(BASE_URL),
        'listitem': list_item,
        'isFolder': True,
    }
    if total is not None:
        kwargs['totalItems'] = total
    xbmcplugin.addDirectoryItem(**kwargs)


def add_item_title(element):
    if element.type == 'serie':
        return add_item_title_serie(element)
    elif element.type == 'movie':
        add_item_title_movie(element)


def _set_resume_indicator(list_item, progress_pct, total_secs):
    """Show a resume progress indicator without triggering Kodi's resume dialog.
    Setting TotalTime to '' is the trick that skips the popup while keeping the bar."""
    if not progress_pct or progress_pct >= 95 or not total_secs:
        return
    resume_secs = int(total_secs * progress_pct / 100)
    if resume_secs <= 0:
        return
    list_item.setProperty('ResumeTime', str(resume_secs))
    list_item.setProperty('TotalTime', '')


def _build_art(primary, fanart, logo):
    primary = primary or ''
    fanart = fanart or primary or DEFAULT_FANART
    art = {}
    if primary:
        art['poster'] = primary
        art['thumb'] = primary
        art['icon'] = primary
    if fanart:
        art['fanart'] = fanart
        art['landscape'] = fanart
    if logo:
        art['clearlogo'] = logo
    return art


def add_item_title_serie(element):
    series_fanart = getattr(element, 'fanart', '') or ''
    series_logo = getattr(element, 'logo', '') or ''
    series_image = element.image or ''
    for episode_tag in sorted(element.medias, reverse=True):
        media = element.medias[episode_tag]
        media.additionnal_infos['media_id'] = element.id
        list_item = xbmcgui.ListItem(episode_tag)
        # Per-episode thumbnail when available, fall back to the series art
        ep_image = media.image or series_image
        list_item.setArt(_build_art(ep_image, series_fanart, series_logo))
        info = {
            'mediatype': 'episode',
            'title': media.title,
            'plot': media.description,
            'plotoutline': media.description,
            'episode': media.episode,
            'season': media.season,
            'duration': media.duration,
            'tvshowtitle': element.title,
        }
        list_item.setInfo('video', info)
        list_item.setProperty('IsPlayable', 'true')
        _set_resume_indicator(list_item, getattr(media, 'progress_percentage', 0.0), media.duration or 0)
        xbmcplugin.addDirectoryItem(
            handle=ADDON_HANDLE, url=media.to_url(BASE_URL), listitem=list_item, isFolder=False)


def add_item_title_movie(element):
    media = element.medias['default']
    media.additionnal_infos['media_id'] = element.id
    list_item = xbmcgui.ListItem(element.title)
    primary = media.image or element.image or ''
    fanart = getattr(element, 'fanart', '') or primary
    logo = getattr(element, 'logo', '') or ''
    list_item.setArt(_build_art(primary, fanart, logo))
    info = {
        'mediatype': 'movie',
        'title': element.title,
        'plot': media.description,
        'plotoutline': media.description,
        'year': element.year,
        'duration': media.duration,
    }
    list_item.setInfo('video', info)
    list_item.setProperty('IsPlayable', 'true')
    _set_resume_indicator(list_item, getattr(media, 'progress_percentage', 0.0), media.duration or 0)
    xbmcplugin.addDirectoryItem(
        handle=ADDON_HANDLE, url=media.to_url(BASE_URL), listitem=list_item, isFolder=False)
