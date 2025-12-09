import json
import time
import secrets
from threading import Lock
from pathlib import Path
from collections import OrderedDict
from typing import Dict, Any
from threading import RLock



class RedirectState:
    """
    Central state manager for ez-redirect.

    - Stores current/default redirect URLs and temporary timer in config.json
    - Stores presets in presets.json as: { "Name": { "url": "https://..." } }
    - Stores port and API key security config in config.json as well.
    """

    def __init__(self) -> None:
        self.lock = RLock()

        base_dir = Path(__file__).resolve().parent.parent
        backend_dir = base_dir / "backend"

        self.config_path = backend_dir / "config.json"
        self.presets_path = backend_dir / "presets.json"

        # Default config values
        defaults: Dict[str, Any] = {
            "default_url": "https://example.com",
            "current_url": "https://example.com",
            "expires_at": None,
            "port": 8000,
            "api_key_enabled": False,
            "api_key": None,
        }

        # Load config
        self.data: Dict[str, Any] = self._load_json(self.config_path, defaults)

        # Ensure all keys exist
        changed = False
        for key, default_value in defaults.items():
            if key not in self.data:
                self.data[key] = default_value
                changed = True

        # Ensure api_key exists
        if not self.data.get("api_key"):
            self.data["api_key"] = self._generate_api_key()
            changed = True

        if changed:
            self._save_json(self.config_path, self.data)

        # Load presets as OrderedDict and normalise structure
        raw_presets = self._load_json(self.presets_path, {})
        self.presets: "OrderedDict[str, Dict[str, str]]" = OrderedDict()

        for name, value in raw_presets.items():
            if isinstance(value, str):
                # old format -> wrap
                self.presets[name] = {"url": value}
            elif isinstance(value, dict) and "url" in value:
                self.presets[name] = {"url": value["url"]}
            else:
                # Skip malformed entries
                continue

        # Persist cleaned presets if necessary
        if raw_presets != self.presets:
            self._save_json(self.presets_path, self.presets)

    # ----------------- internal helpers -----------------

    def _generate_api_key(self) -> str:
        # URL-safe random token
        return secrets.token_urlsafe(24)

    def _load_json(self, path: Path, default):
        try:
            with path.open("r") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(data, f, indent=4)

    # ----------------- redirect logic -----------------

    def get_current_url(self) -> str:
        with self.lock:
            expires = self.data.get("expires_at")
            if expires and time.time() > float(expires):
                # Temporary URL expired – revert to default
                self.data["current_url"] = self.data.get("default_url", "https://example.com")
                self.data["expires_at"] = None
                self._save_json(self.config_path, self.data)
            return self.data["current_url"]

    def set_current_url(self, url: str) -> None:
        with self.lock:
            self.data["current_url"] = url
            self.data["expires_at"] = None
            self._save_json(self.config_path, self.data)

    def set_default_url(self, url: str) -> None:
        with self.lock:
            self.data["default_url"] = url
            self._save_json(self.config_path, self.data)

    def set_temp_url(self, url: str, seconds: int) -> None:
        with self.lock:
            self.data["current_url"] = url
            self.data["expires_at"] = time.time() + int(seconds)
            self._save_json(self.config_path, self.data)

    def clear_timer(self) -> None:
        with self.lock:
            self.data["expires_at"] = None
            self._save_json(self.config_path, self.data)

    # ----------------- port management -----------------

    def get_port(self) -> int:
        with self.lock:
            return int(self.data.get("port", 8000))

    def set_port(self, port: int) -> None:
        with self.lock:
            self.data["port"] = int(port)
            self._save_json(self.config_path, self.data)

    # ----------------- security / API key -----------------

    def is_api_key_enabled(self) -> bool:
        with self.lock:
            return bool(self.data.get("api_key_enabled", False))

    def get_api_key(self) -> str:
        with self.lock:
            key = self.data.get("api_key")
            if not key:
                key = self._generate_api_key()
                self.data["api_key"] = key
                self._save_json(self.config_path, self.data)
            return key

    def set_api_key(self, api_key: str) -> None:
        with self.lock:
            self.data["api_key"] = api_key
            self._save_json(self.config_path, self.data)

    def set_api_key_enabled(self, enabled: bool) -> None:
        with self.lock:
            self.data["api_key_enabled"] = bool(enabled)
            self._save_json(self.config_path, self.data)

    def regenerate_api_key(self) -> str:
        with self.lock:
            self.data["api_key"] = self._generate_api_key()
            self._save_json(self.config_path, self.data)
            return self.data["api_key"]

    # ----------------- presets management -----------------

    def get_presets(self) -> "OrderedDict[str, Dict[str, str]]":
        return self.presets

    def add_or_update_preset(self, name: str, url: str) -> None:
        with self.lock:
            self.presets[name] = {"url": url}
            self._save_json(self.presets_path, self.presets)

    def delete_preset(self, name: str) -> None:
        with self.lock:
            if name in self.presets:
                del self.presets[name]
                self._save_json(self.presets_path, self.presets)

    def rename_preset(self, old_name: str, new_name: str) -> bool:
        with self.lock:
            if old_name not in self.presets:
                return False
            new_presets: "OrderedDict[str, Dict[str, str]]" = OrderedDict()
            for key, value in self.presets.items():
                if key == old_name:
                    new_presets[new_name] = value
                else:
                    new_presets[key] = value
            self.presets = new_presets
            self._save_json(self.presets_path, self.presets)
            return True

    # ----------------- info for API -----------------

    def info(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "current_url": self.data.get("current_url"),
                "default_url": self.data.get("default_url"),
                "expires_at": self.data.get("expires_at"),
                "is_temporary": self.data.get("expires_at") is not None,
                "port": self.get_port(),
                "api_key_enabled": self.is_api_key_enabled(),
            }

    def security_info(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "api_key_enabled": bool(self.data.get("api_key_enabled", False)),
                "api_key": self.data.get("api_key"),
            }
