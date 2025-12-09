from fastapi import FastAPI, Response, HTTPException, Body, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from .redirect_state import RedirectState


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
    if not name or not url:
        raise HTTPException(status_code=400, detail="Missing 'name' or 'url'")
    state.add_or_update_preset(name, url)
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


# ----------------- Apply Preset via URL (with API key) -----------------

@app.get("/preset/{preset_name}")
async def activate_preset_by_url(
    preset_name: str,
    key: str | None = Query(default=None),
):
    """
    Apply a preset by name.

    If API key security is enabled, callers must include ?key=YOUR_API_KEY
    For example: http://host:8000/preset/giving?key=SECRET123
    """
    api_key_enabled = state.is_api_key_enabled()
    if api_key_enabled:
        expected = state.get_api_key()
        if not key or key != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    normalized = preset_name.replace("-", " ").lower()

    match = None
    for name, data in state.get_presets().items():
        if name.lower() == normalized:
            match = (name, data)
            break

    if not match:
        raise HTTPException(status_code=404, detail="Preset not found")

    preset_name, preset_data = match

    if not isinstance(preset_data, dict) or "url" not in preset_data:
        raise HTTPException(
            status_code=500,
            detail=f"Preset '{preset_name}' must be stored as an object: {{ 'url': '...' }}",
        )

    state.set_current_url(preset_data["url"])
    state.clear_timer()

    return {
        "status": "ok",
        "active_preset": preset_name,
        "active_url": preset_data["url"],
    }


# ----------------- DEV ENTRYPOINT -----------------

if __name__ == "__main__":
    import uvicorn

    # For dev, we still default to whatever is in config
    port = state.get_port()
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=True)
