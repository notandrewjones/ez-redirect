import json
import time
from threading import Lock
from pathlib import Path
from collections import OrderedDict


class RedirectState:
    def __init__(self):
        self.lock = Lock()

        # Base paths
        base_dir = Path(__file__).resolve().parent.parent
        self.config_path = base_dir / "backend" / "config.json"
        self.presets_path = base_dir / "backend" / "presets.json"

        # Load config with defaults
        defaults = {
            "default_url": "https://example.com",
            "current_url": "https://example.com",
            "expires_at": None
        }

        self.data = self._load_json(self.config_path, defaults)

        # Ensure all keys exist
        for key, value in defaults.items():
            self.data.setdefault(key, value)

        # Load presets as ordered dict
        raw_presets = self._load_json(self.presets_path, {})
        self.presets = OrderedDict()

        # ENFORCE CORRECT STRUCTURE:
        # Convert:  "Giving": "https://..." → "Giving": {"url": "..."}
        for name, value in raw_presets.items():
            if isinstance(value, str):
                self.presets[name] = {"url": value}
            else:
                self.presets[name] = value

        # Save corrected preset format if needed
        self._save_json(self.presets_path, self.presets)

    # ----------------- JSON helpers -----------------

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

    # ----------------- redirect logic -----------------

    def get_current_url(self) -> str:
        with self.lock:
            expires = self.data.get("expires_at")

            # Expired temporary redirect?
            if expires and time.time() > expires:
                self.data["current_url"] = self.data["default_url"]
                self.data["expires_at"] = None
                self._save_json(self.config_path, self.data)

            return self.data["current_url"]

    def set_current_url(self, url: str):
        with self.lock:
            self.data["current_url"] = url
            self.data["expires_at"] = None
            self._save_json(self.config_path, self.data)

    def set_default_url(self, url: str):
        with self.lock:
            self.data["default_url"] = url
            self._save_json(self.config_path, self.data)

    def set_temp_url(self, url: str, seconds: int):
        with self.lock:
            self.data["current_url"] = url
            self.data["expires_at"] = time.time() + int(seconds)
            self._save_json(self.config_path, self.data)

    def clear_timer(self):
        with self.lock:
            self.data["expires_at"] = None
            self._save_json(self.config_path, self.data)

    # ----------------- presets management -----------------

    def get_presets(self) -> dict:
        return self.presets  # Already ordered dict of {name: {"url": ...}}

    def add_or_update_preset(self, name: str, url: str):
        with self.lock:
            # ALWAYS enforce dict structure
            if name in self.presets:
                self.presets[name] = {"url": url}
            else:
                self.presets[name] = {"url": url}

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

            url_data = self.presets[old_name]

            new_presets = OrderedDict()
            for key, val in self.presets.items():
                if key == old_name:
                    new_presets[new_name] = val
                else:
                    new_presets[key] = val

            self.presets = new_presets
            self._save_json(self.presets_path, self.presets)
            return True

    # ----------------- API info -----------------

    def info(self) -> dict:
        with self.lock:
            return {
                "current_url": self.data.get("current_url"),
                "default_url": self.data.get("default_url"),
                "expires_at": self.data.get("expires_at"),
                "is_temporary": self.data.get("expires_at") is not None
            }
