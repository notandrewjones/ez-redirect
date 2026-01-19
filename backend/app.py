"""
EZ Redirect - FastAPI Backend

A simple redirect server with preset management, temporary redirects,
Supabase cue integration, and scheduled event management.
"""

from typing import Optional
from fastapi import FastAPI, Response, HTTPException, Body, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import sys

# Ensure the parent directory is in the path for imports
current_dir = Path(__file__).resolve().parent
base_dir = current_dir.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from backend.redirect_state import RedirectState


app = FastAPI(
    title="EZ Redirect",
    debug=False,
)

# Allow all origins (fine for a LAN tool; you can lock this down later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state = RedirectState()

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


# ----------------- UI ROUTES -----------------

@app.get("/")
def serve_index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/styles.css")
def serve_styles():
    return FileResponse(WEB_DIR / "styles.css")


# ----------------- REDIRECT ENDPOINT -----------------

@app.get("/redirect")
def redirect():
    """Endpoint NFC tags should use for the actual redirect."""
    target = state.get_current_url()
    return Response(status_code=302, headers={"Location": target})


# ----------------- STATE / CURRENT INFO -----------------

@app.get("/api/current")
def api_current():
    return state.info()


# ----------------- SET URLS -----------------

@app.post("/api/set")
def api_set(payload: dict = Body(...)):
    """Set the active redirect URL and clear any timer."""
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url'")
    state.set_current_url(url)
    return {"status": "ok", "current_url": url}


@app.post("/api/temp")
def api_temp(payload: dict = Body(...)):
    """Set a temporary redirect."""
    url = payload.get("url")
    seconds = payload.get("seconds")
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url'")
    if seconds is None:
        raise HTTPException(status_code=400, detail="Missing 'seconds'")
    try:
        seconds = int(seconds)
    except ValueError:
        raise HTTPException(status_code=400, detail="'seconds' must be an integer")

    state.set_temp_url(url, seconds)
    return {
        "status": "ok",
        "current_url": url,
        "expires_in": seconds,
    }


@app.post("/api/set-default")
def api_set_default(payload: dict = Body(...)):
    """Set the default redirect URL."""
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url'")
    state.set_default_url(url)
    return {"status": "ok", "default_url": url}


# ----------------- PRESETS API -----------------

@app.get("/api/presets")
def api_get_presets():
    return state.get_presets()


@app.post("/api/presets/add")
def api_add_preset(payload: dict = Body(...)):
    name = payload.get("name")
    url = payload.get("url")
    cue = payload.get("cue")  # Can be None, or a dict with headline, body_text, etc.
    
    if not name or not url:
        raise HTTPException(status_code=400, detail="Missing 'name' or 'url'")
    
    # Validate cue structure if provided
    if cue is not None and not isinstance(cue, dict):
        raise HTTPException(status_code=400, detail="'cue' must be an object or null")
    
    state.add_or_update_preset(name, url, cue)
    return {"status": "ok"}


@app.post("/api/presets/delete")
def api_delete_preset(payload: dict = Body(...)):
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Missing 'name'")
    state.delete_preset(name)
    return {"status": "ok"}


@app.post("/api/presets/rename")
def api_rename_preset(payload: dict = Body(...)):
    old = payload.get("old")
    new = payload.get("new")
    if not old or not new:
        raise HTTPException(status_code=400, detail="Missing 'old' or 'new'")
    renamed = state.rename_preset(old, new)
    return {"status": "ok", "renamed": renamed}


# ----------------- SECURITY (API KEY) -----------------

@app.get("/api/security/status")
def api_security_status():
    """Return API key + enabled flag so UI can manage it."""
    return state.security_info()


@app.post("/api/security/toggle")
def api_security_toggle(payload: dict = Body(...)):
    enabled = payload.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="Missing 'enabled'")
    state.set_api_key_enabled(bool(enabled))
    return state.security_info()


@app.post("/api/security/set-key")
def api_security_set_key(payload: dict = Body(...)):
    api_key = payload.get("api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing 'api_key'")
    state.set_api_key(api_key)
    return state.security_info()


@app.post("/api/security/regenerate")
def api_security_regenerate():
    _ = state.regenerate_api_key()
    return state.security_info()


# ----------------- PORT MANAGEMENT -----------------

@app.get("/api/port")
def api_get_port():
    return {"port": state.get_port()}


@app.post("/api/port")
def api_set_port(payload: dict = Body(...)):
    port = payload.get("port")
    if port is None:
        raise HTTPException(status_code=400, detail="Missing 'port'")
    try:
        port = int(port)
    except ValueError:
        raise HTTPException(status_code=400, detail="'port' must be an integer")

    if not (1024 <= port <= 65535):
        raise HTTPException(status_code=400, detail="Port must be between 1024 and 65535")

    state.set_port(port)
    return {"status": "ok", "port": port, "requires_restart": True}


# ----------------- SUPABASE CONFIGURATION -----------------

@app.get("/api/supabase/config")
def api_get_supabase_config():
    """Get Supabase configuration (masks the API key for display)."""
    config = state.get_supabase_config()
    return {
        "url": config["url"],
        "api_key": config["api_key"][:10] + "..." if config["api_key"] else "",
        "api_key_full": config["api_key"],  # Full key for the form
        "configured": config["configured"]
    }


@app.post("/api/supabase/config")
def api_set_supabase_config(payload: dict = Body(...)):
    """Set Supabase URL and API key."""
    url = payload.get("url", "")
    api_key = payload.get("api_key", "")
    
    state.set_supabase_config(url, api_key)
    return {"status": "ok", "configured": bool(url and api_key)}


@app.post("/api/supabase/test")
def api_test_supabase():
    """Test the Supabase connection by fetching events."""
    config = state.get_supabase_config()
    
    if not config["configured"]:
        return {"success": False, "error": "Supabase not configured"}
    
    import requests
    
    headers = {
        "apikey": config["api_key"],
        "Authorization": f"Bearer {config['api_key']}",
    }
    
    try:
        response = requests.get(
            f"{config['url']}/rest/v1/events?limit=1",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return {"success": True, "message": "Connection successful"}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ----------------- SCHEDULED EVENTS -----------------

@app.get("/api/events/scheduled")
def api_get_scheduled_events():
    """Get recurring scheduled events (e.g., every Sunday at 11:00)."""
    return state.get_scheduled_events()


@app.post("/api/events/scheduled/add")
def api_add_scheduled_event(payload: dict = Body(...)):
    """Add a recurring scheduled event."""
    day = payload.get("day")
    time_str = payload.get("time")
    enabled = payload.get("enabled", True)
    
    if not day or not time_str:
        raise HTTPException(status_code=400, detail="Missing 'day' or 'time'")
    
    valid_days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    if day.lower() not in valid_days:
        raise HTTPException(status_code=400, detail="Invalid day")
    
    state.add_scheduled_event(day, time_str, enabled)
    return {"status": "ok"}


@app.post("/api/events/scheduled/update")
def api_update_scheduled_event(payload: dict = Body(...)):
    """Update a recurring scheduled event."""
    index = payload.get("index")
    day = payload.get("day")
    time_str = payload.get("time")
    enabled = payload.get("enabled", True)
    
    if index is None or not day or not time_str:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    success = state.update_scheduled_event(int(index), day, time_str, enabled)
    return {"status": "ok" if success else "error"}


@app.post("/api/events/scheduled/delete")
def api_delete_scheduled_event(payload: dict = Body(...)):
    """Delete a recurring scheduled event."""
    index = payload.get("index")
    
    if index is None:
        raise HTTPException(status_code=400, detail="Missing 'index'")
    
    success = state.remove_scheduled_event(int(index))
    return {"status": "ok" if success else "error"}


# ----------------- MANUAL EVENTS -----------------

@app.get("/api/events/manual")
def api_get_manual_events():
    """Get manually scheduled one-time events."""
    return state.get_manual_events()


@app.post("/api/events/manual/add")
def api_add_manual_event(payload: dict = Body(...)):
    """Add a manual one-time event."""
    date = payload.get("date")  # YYYY-MM-DD
    time_str = payload.get("time")  # HH:MM
    
    if not date or not time_str:
        raise HTTPException(status_code=400, detail="Missing 'date' or 'time'")
    
    state.add_manual_event(date, time_str)
    return {"status": "ok"}


@app.post("/api/events/manual/delete")
def api_delete_manual_event(payload: dict = Body(...)):
    """Delete a manual event."""
    index = payload.get("index")
    
    if index is None:
        raise HTTPException(status_code=400, detail="Missing 'index'")
    
    success = state.remove_manual_event(int(index))
    return {"status": "ok" if success else "error"}


@app.post("/api/events/create-now")
def api_create_event_now():
    """Manually create an event for today right now."""
    from datetime import datetime
    
    today = datetime.now().strftime("%Y-%m-%d")
    result = state.create_event_in_supabase(today, datetime.now())
    
    if result.get("success"):
        return {"status": "ok", "event_id": today}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))


# ----------------- Apply Preset via URL (with API key) -----------------

@app.get("/preset/{preset_name}")
async def activate_preset_by_url(
    preset_name: str,
    key: Optional[str] = Query(default=None),
):
    """
    Apply a preset by name.

    If API key security is enabled, callers must include ?key=YOUR_API_KEY
    For example: http://host:8000/preset/giving?key=SECRET123
    
    This also posts the cue to Supabase if configured.
    """
    api_key_enabled = state.is_api_key_enabled()
    if api_key_enabled:
        expected = state.get_api_key()
        if not key or key != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    preset = state.get_preset(preset_name)
    
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    if "url" not in preset:
        raise HTTPException(
            status_code=500,
            detail=f"Preset '{preset_name}' must have a 'url' field",
        )

    # Set the redirect URL
    state.set_current_url(preset["url"])
    state.clear_timer()

    # Post cue to Supabase
    cue_result = state.post_cue_to_supabase(preset["name"], preset.get("cue"))

    return {
        "status": "ok",
        "active_preset": preset["name"],
        "active_url": preset["url"],
        "cue_posted": cue_result.get("success", False),
        "cue_error": cue_result.get("error") if not cue_result.get("success") else None,
        "event_id": cue_result.get("event_id"),
    }


# ----------------- Apply Preset from UI (also posts cue) -----------------

@app.post("/api/preset/activate")
def api_activate_preset(payload: dict = Body(...)):
    """
    Activate a preset from the UI.
    
    This sets the redirect URL AND posts the cue to Supabase.
    """
    name = payload.get("name")
    
    if not name:
        raise HTTPException(status_code=400, detail="Missing 'name'")
    
    preset = state.get_preset(name)
    
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    # Set the redirect URL
    state.set_current_url(preset["url"])
    state.clear_timer()
    
    # Post cue to Supabase
    cue_result = state.post_cue_to_supabase(preset["name"], preset.get("cue"))
    
    return {
        "status": "ok",
        "active_preset": preset["name"],
        "active_url": preset["url"],
        "cue_posted": cue_result.get("success", False),
        "cue_error": cue_result.get("error") if not cue_result.get("success") else None,
        "event_id": cue_result.get("event_id"),
    }


# ----------------- HEALTH CHECK -----------------

@app.get("/api/health")
def api_health():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "ez-redirect"}


# ----------------- DEV ENTRYPOINT -----------------

if __name__ == "__main__":
    import uvicorn

    # For dev, we still default to whatever is in config
    port = state.get_port()
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=True)