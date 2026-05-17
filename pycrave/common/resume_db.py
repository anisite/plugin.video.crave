import json
import os
import logging

logger = logging.getLogger(__name__)


class ResumeDB:
    """Persist playback resume positions in a local JSON file."""

    def __init__(self, path):
        self._path = path
        self._data = self._load()

    def get(self, play_id):
        """Return saved position in seconds, or 0 if none."""
        return self._data.get(str(play_id), 0)

    def set(self, play_id, position):
        """Save position. Ignored if <= 60 s (not worth resuming)."""
        if position > 60:
            self._data[str(play_id)] = int(position)
            self._save()
            logger.debug('ResumeDB: saved {}s for {}'.format(int(position), play_id))

    def clear(self, play_id):
        """Remove saved position (e.g. after natural end)."""
        if str(play_id) in self._data:
            del self._data[str(play_id)]
            self._save()

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
                json.dump(self._data, f)
        except Exception as e:
            logger.error('ResumeDB save failed: {}'.format(e))
