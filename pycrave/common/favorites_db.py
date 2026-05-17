import json
import os
import logging

logger = logging.getLogger(__name__)


class FavoritesDB:
    """Persist user favorites in a local JSON file."""

    def __init__(self, path):
        self._path = path
        self._data = self._load()

    def is_favorite(self, media_id):
        return str(media_id) in self._data

    def toggle(self, media_id, title='', image='', media_type=''):
        """Add if absent, remove if present. Returns True when added."""
        if self.is_favorite(media_id):
            self.remove(media_id)
            return False
        self.add(media_id, title, image, media_type)
        return True

    def add(self, media_id, title, image='', media_type=''):
        self._data[str(media_id)] = {
            'id': str(media_id),
            'title': title,
            'image': image,
            'media_type': media_type,
        }
        self._save()

    def remove(self, media_id):
        if str(media_id) in self._data:
            del self._data[str(media_id)]
            self._save()

    def get_all(self):
        return list(self._data.values())

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error('FavoritesDB save failed: {}'.format(e))
