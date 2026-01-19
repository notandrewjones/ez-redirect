import json
import time
import secrets
import threading
import requests
from datetime import datetime, timedelta
from threading import RLock
from pathlib import Path
from collections import OrderedDict
from typing import Dict, Any, Optional, List


class RedirectState:
    """
    Central state manager for ez-redirect.

    - Stores current/default redirect URLs and temporary timer in config.json
    - Stores presets in presets.json with optional cue data
    - Stores port and API key security config in config.json
    - Manages Supabase integration for cue posting
    - Handles scheduled event creation
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
            "supabase_url": "",
            "supabase_api_key": "",
            "scheduled_events": [
                {"day": "sunday", "time": "11:00", "enabled": True}
            ],
            "manual_events": []  # List of manually scheduled events
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
        self.presets: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

        for name, value in raw_presets.items():
            if isinstance(value, str):
                # old format -> wrap with no cue
                self.presets[name] = {"url": value, "cue": None}
            elif isinstance(value, dict) and "url" in value:
                self.presets[name] = {
                    "url": value["url"],
                    "cue": value.get("cue", None)
                }
            else:
                # Skip malformed entries
                continue

        # Persist cleaned presets if necessary
        if raw_presets != self.presets:
            self._save_json(self.presets_path, self.presets)

        # Track created events to avoid duplicates (date strings)
        self._created_events_today: set = set()
        
        # Start the scheduler thread
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()

    # ----------------- internal helpers -----------------

    def _generate_api_key(self) -> str:
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

    def get_presets(self) -> "OrderedDict[str, Dict[str, Any]]":
        return self.presets

    def add_or_update_preset(self, name: str, url: str, cue: Optional[Dict[str, str]] = None) -> None:
        with self.lock:
            self.presets[name] = {"url": url, "cue": cue}
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
            new_presets: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
            for key, value in self.presets.items():
                if key == old_name:
                    new_presets[new_name] = value
                else:
                    new_presets[key] = value
            self.presets = new_presets
            self._save_json(self.presets_path, self.presets)
            return True

    def get_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a single preset by name (case-insensitive, dash-tolerant)."""
        normalized = name.replace("-", " ").lower()
        for preset_name, data in self.presets.items():
            if preset_name.lower() == normalized:
                return {"name": preset_name, **data}
        return None

    # ----------------- Supabase integration -----------------

    def get_supabase_config(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "url": self.data.get("supabase_url", ""),
                "api_key": self.data.get("supabase_api_key", ""),
                "configured": bool(self.data.get("supabase_url") and self.data.get("supabase_api_key"))
            }

    def set_supabase_config(self, url: str, api_key: str) -> None:
        with self.lock:
            self.data["supabase_url"] = url
            self.data["supabase_api_key"] = api_key
            self._save_json(self.config_path, self.data)

    def _get_today_event_id(self) -> str:
        """Get today's date as event_id in YYYY-MM-DD format."""
        return datetime.now().strftime("%Y-%m-%d")

    def post_cue_to_supabase(self, preset_name: str, cue_data: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """
        Post a cue to Supabase for the current event.
        
        If cue_data is None, posts a cue with empty fields (hides the banner).
        """
        config = self.get_supabase_config()
        
        if not config["configured"]:
            return {"success": False, "error": "Supabase not configured"}

        event_id = self._get_today_event_id()
        
        # Build the cue payload
        if cue_data is None:
            # Hide cue - post with empty/null fields
            payload = {
                "event_id": event_id,
                "cue_type": preset_name,
                "headline": "",
                "body_text": "",
                "button_text": "",
                "button_url": ""
            }
        else:
            payload = {
                "event_id": event_id,
                "cue_type": preset_name,
                "headline": cue_data.get("headline", ""),
                "body_text": cue_data.get("body_text", ""),
                "button_text": cue_data.get("button_text", ""),
                "button_url": cue_data.get("button_url", "")
            }

        headers = {
            "apikey": config["api_key"],
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        try:
            response = requests.post(
                f"{config['url']}/rest/v1/cues",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in (200, 201, 204):
                return {"success": True, "event_id": event_id}
            else:
                return {
                    "success": False, 
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def create_event_in_supabase(self, event_id: str, start_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Create a new event in Supabase using the stored procedure.
        """
        config = self.get_supabase_config()
        
        if not config["configured"]:
            return {"success": False, "error": "Supabase not configured"}

        headers = {
            "apikey": config["api_key"],
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        payload = {"p_event_id": event_id}

        try:
            response = requests.post(
                f"{config['url']}/rest/v1/rpc/create_event",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in (200, 201, 204):
                # If start_time provided, update the event's service_start_time
                if start_time:
                    self._update_event_start_time(event_id, start_time)
                return {"success": True, "event_id": event_id}
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def _update_event_start_time(self, event_id: str, start_time: datetime) -> None:
        """Update an event's service_start_time."""
        config = self.get_supabase_config()
        if not config["configured"]:
            return

        headers = {
            "apikey": config["api_key"],
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        # Format as ISO string
        start_time_str = start_time.isoformat()

        try:
            requests.patch(
                f"{config['url']}/rest/v1/events?event_id=eq.{event_id}",
                json={"service_start_time": start_time_str},
                headers=headers,
                timeout=10
            )
        except requests.exceptions.RequestException:
            pass  # Silent fail for start time update

    # ----------------- Scheduled Events -----------------

    def get_scheduled_events(self) -> List[Dict[str, Any]]:
        with self.lock:
            return self.data.get("scheduled_events", [])

    def set_scheduled_events(self, events: List[Dict[str, Any]]) -> None:
        with self.lock:
            self.data["scheduled_events"] = events
            self._save_json(self.config_path, self.data)

    def add_scheduled_event(self, day: str, time_str: str, enabled: bool = True) -> None:
        with self.lock:
            events = self.data.get("scheduled_events", [])
            events.append({"day": day.lower(), "time": time_str, "enabled": enabled})
            self.data["scheduled_events"] = events
            self._save_json(self.config_path, self.data)

    def remove_scheduled_event(self, index: int) -> bool:
        with self.lock:
            events = self.data.get("scheduled_events", [])
            if 0 <= index < len(events):
                events.pop(index)
                self.data["scheduled_events"] = events
                self._save_json(self.config_path, self.data)
                return True
            return False

    def update_scheduled_event(self, index: int, day: str, time_str: str, enabled: bool) -> bool:
        with self.lock:
            events = self.data.get("scheduled_events", [])
            if 0 <= index < len(events):
                events[index] = {"day": day.lower(), "time": time_str, "enabled": enabled}
                self.data["scheduled_events"] = events
                self._save_json(self.config_path, self.data)
                return True
            return False

    # ----------------- Manual Events -----------------

    def get_manual_events(self) -> List[Dict[str, Any]]:
        with self.lock:
            return self.data.get("manual_events", [])

    def add_manual_event(self, date: str, time_str: str) -> None:
        """Add a manual event for a specific date/time."""
        with self.lock:
            events = self.data.get("manual_events", [])
            events.append({"date": date, "time": time_str, "created": False})
            self.data["manual_events"] = events
            self._save_json(self.config_path, self.data)

    def remove_manual_event(self, index: int) -> bool:
        with self.lock:
            events = self.data.get("manual_events", [])
            if 0 <= index < len(events):
                events.pop(index)
                self.data["manual_events"] = events
                self._save_json(self.config_path, self.data)
                return True
            return False

    # ----------------- Scheduler -----------------

    def _scheduler_loop(self) -> None:
        """Background thread that checks for scheduled events."""
        while self._scheduler_running:
            try:
                self._check_scheduled_events()
                self._check_manual_events()
            except Exception as e:
                print(f"Scheduler error: {e}")
            
            # Check every 30 seconds
            time.sleep(30)

    def _check_scheduled_events(self) -> None:
        """Check if any recurring scheduled events should fire."""
        now = datetime.now()
        current_day = now.strftime("%A").lower()
        current_time = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")

        events = self.get_scheduled_events()
        
        for event in events:
            if not event.get("enabled", True):
                continue
                
            event_day = event.get("day", "").lower()
            event_time = event.get("time", "")
            
            # Check if this is the right day and time (within 1 minute window)
            if event_day == current_day:
                event_key = f"{today_str}_{event_time}"
                
                # Parse times to compare
                try:
                    event_hour, event_min = map(int, event_time.split(":"))
                    
                    # Check if we're within 1 minute of the scheduled time
                    if now.hour == event_hour and now.minute == event_min:
                        if event_key not in self._created_events_today:
                            # Create the event
                            start_time = now.replace(hour=event_hour, minute=event_min, second=0, microsecond=0)
                            result = self.create_event_in_supabase(today_str, start_time)
                            
                            if result.get("success"):
                                self._created_events_today.add(event_key)
                                print(f"Created scheduled event: {today_str} at {event_time}")
                except ValueError:
                    continue

        # Clear old entries at midnight
        if now.hour == 0 and now.minute == 0:
            self._created_events_today.clear()

    def _check_manual_events(self) -> None:
        """Check if any manual events should fire."""
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        with self.lock:
            events = self.data.get("manual_events", [])
            changed = False
            
            for event in events:
                if event.get("created"):
                    continue
                    
                event_date = event.get("date", "")
                event_time = event.get("time", "")
                
                if event_date == current_date:
                    try:
                        event_hour, event_min = map(int, event_time.split(":"))
                        
                        if now.hour == event_hour and now.minute == event_min:
                            start_time = now.replace(hour=event_hour, minute=event_min, second=0, microsecond=0)
                            result = self.create_event_in_supabase(event_date, start_time)
                            
                            if result.get("success"):
                                event["created"] = True
                                changed = True
                                print(f"Created manual event: {event_date} at {event_time}")
                    except ValueError:
                        continue
            
            if changed:
                self._save_json(self.config_path, self.data)

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