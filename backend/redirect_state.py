import json
import time
from threading import Lock
from pathlib import Path
from collections import OrderedDict



class RedirectState:
    def __init__(self):
        self.lock = Lock()

        # Paths to JSON files
        base_dir = Path(__file__).resolve().parent.parent
        self.config_path = base_dir / "backend" / "config.json"
        self.presets_path = base_dir / "backend" / "presets.json"

        # Load config (with defaults)
        defaults = {
            "default_url": "https://example.com",
            "current_url": "https://example.com",
            "expires_at": None
        }

        self.data = self._load_json(self.config_path, defaults)
        for key, value in defaults.items():
            self.data.setdefault(key, value)

        # Load presets as an OrderedDict to preserve order
        raw_presets = self._load_json(self.presets_path, {})
        self.presets = OrderedDict(raw_presets)
    

    def _load_json(self, path: Path, default):
        try:
            with path.open("r") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_json(self, path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(data, f, indent=4)

    # ----------------- core redirect logic -----------------

    def get_current_url(self) -> str:
        with self.lock:
            # If temporary redirect expired, revert to default
            expires_at = self.data.get("expires_at")
            if expires_at and time.time() > expires_at:
                self.data["current_url"] = self.data["default_url"]
                self.data["expires_at"] = None
                self._save_json(self.config_path, self.data)

            return self.data["current_url"]

    def set_url(self, url: str):
        with self.lock:
            self.data["current_url"] = url
            self.data["expires_at"] = None
            self._save_json(self.config_path, self.data)

    def set_default(self, url: str):
        with self.lock:
            self.data["default_url"] = url
            # Optionally also set current to default when changed:
            # self.data["current_url"] = url
            self._save_json(self.config_path, self.data)

    def set_temp(self, url: str, seconds: int):
        with self.lock:
            self.data["current_url"] = url
            self.data["expires_at"] = time.time() + int(seconds)
            self._save_json(self.config_path, self.data)

    # ----------------- presets handling -----------------

    def get_presets(self) -> dict:
        # read-only; no need to lock
        return self.presets

    def add_or_update_preset(self, name: str, url: str):
        with self.lock:
            self.presets[name] = url
            self._save_json(self.presets_path, self.presets)

    def delete_preset(self, name: str):
        with self.lock:
            if name in self.presets:
                del self.presets[name]
                self._save_json(self.presets_path, self.presets)
                
    def rename_preset(self, old_name: str, new_name: str):
        with self.lock:
            if old_name not in self.presets:
                return False

            # Get current value
            url = self.presets[old_name]

            # Build a new ordered structure
            new_presets = OrderedDict()

            for key, value in self.presets.items():
                if key == old_name:
                    new_presets[new_name] = value
                else:
                    new_presets[key] = value

            self.presets = new_presets
            self._save_json(self.presets_path, self.presets)
            return True
            
    def add_or_update_preset(self, name: str, url: str):
        with self.lock:
            if name in self.presets:
                # Overwrite existing entry but preserve position
                self.presets[name] = url
            else:
                # Append new preset at end
                self.presets[name] = url

            self._save_json(self.presets_path, self.presets)
            
    def clear_timer(self):
        self.timer = None

    def save(self):
        self._save_json(self.config_path, {
            "current_url": self.current_url,
            "default_url": self.default_url
        })
        self._save_json(self.presets_path, self.presets)
    

    # ----------------- API info -----------------

    def info(self) -> dict:
        with self.lock:
            return {
                "current_url": self.data.get("current_url"),
                "default_url": self.data.get("default_url"),
                "expires_at": self.data.get("expires_at"),
                "is_temporary": self.data.get("expires_at") is not None
            }
