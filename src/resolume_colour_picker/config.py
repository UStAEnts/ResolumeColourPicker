import json
from pathlib import Path

from platformdirs import user_cache_dir
from PySide6.QtCore import Signal, QObject

        

class Config(QObject):
    """
    Manages a simple JSON cache stored in an OS-appropriate user cache directory.
    """
    value_changed = Signal(str, object) # Key, Value

    def __init__(self, app_name: str, filename: str = "cache.json", defaults: dict = {}):
        super().__init__()
        self.app_name = app_name

        # Determine cache directory based on OS
        self.cache_dir = Path(user_cache_dir(app_name))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.cache_file = self.cache_dir.joinpath(filename) 
        self._data = {}
        self.load()

        self.defaults = defaults
        for (key, value) in defaults.items():
            if key not in self:
                self.set(key, value, broadcast=False) 

    def reset(self, broadcast = True):
        for (key, value) in self.defaults.items():
            self.set(key, value, broadcast=broadcast)

    def load(self):
        """Load cache data from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                print(f"Warning: cache file corrupted, starting fresh: {self.cache_file}")
                self._data = {}
        else:
            self._data = {}

    def save(self):
        """Save cache data to disk."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)
        except IOError as e:
            print(f"Failed to save cache: {e}")

    def get(self, key, default=None):
        """Retrieve a value from the cache."""
        return self._data.get(key, default)

    def set(self, key, value, autosave=False, broadcast=True):
        """Set a value in the cache. Optionally save immediately."""
        self._data[key] = value
        if autosave:
            self.save()
        if broadcast:
            self.value_changed.emit(key, value)

    def delete(self, key, autosave=False, broadcast=True):
        """Delete a value from the cache. Optionally save immediately."""
        if key in self._data:
            del self._data[key]
            if autosave:
                self.save()
        if broadcast:
            self.value_changed.emit(key, None)

    def broadcast_change(self, key):
        self.value_changed.emit(key, self._data[key])

    def __getitem__(self, key):
        return self._data[key]  # raises KeyError if missing, like dict

    def __setitem__(self, key, value):
        self._data[key] = value
        self.value_changed.emit(key, value)

    def __delitem__(self, key):
        del self._data[key]
        self.value_changed.emit(key, None)

    def __contains__(self, key):
        return key in self._data  # allows 'key in cache'

    # Optional: context manager for automatic save
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()
