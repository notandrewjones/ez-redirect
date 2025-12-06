from fastapi import FastAPI, Response, HTTPException, Body
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from .redirect_state import RedirectState


app = FastAPI(
    title="Local Redirect Controller",
    debug=False
)

# Allow all origins (safe for local LAN app)
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
    """Endpoint NFC tags should use."""
    target = state.get_current_url()
    return Response(status_code=302, headers={"Location": target})


# ----------------- STATE / CURRENT INFO -----------------

@app.get("/api/current")
def api_current():
    return state.info()


# ----------------- SET URLS -----------------

@app.post("/api/set")
def api_set(url: str):
    """Set the active redirect URL and clear any timer."""
    state.set_current_url(url)
    return {"status": "ok", "current_url": url}


@app.post("/api/temp")
def api_temp(url: str, seconds: int):
    """Set a temporary redirect."""
    state.set_temp_url(url, seconds)
    return {
        "status": "ok",
        "current_url": url,
        "expires_in": seconds
    }


@app.post("/api/set-default")
def api_set_default(url: str):
    """Set the default redirect URL."""
    state.set_default_url(url)
    return {"status": "ok", "default_url": url}


# ----------------- PRESETS API -----------------

@app.get("/api/presets")
def api_get_presets():
    return state.get_presets()


@app.post("/api/presets/add")
def api_add_preset(
    name: str = Body(...),
    url: str = Body(...)
):
    """Always store preset as {'url': ...}."""
    state.add_or_update_preset(name, url)
    return {"status": "ok"}


@app.post("/api/presets/delete")
def api_delete_preset(name: str = Body(...)):
    state.delete_preset(name)
    return {"status": "ok"}


@app.post("/api/presets/rename")
def api_rename_preset(old: str = Body(...), new: str = Body(...)):
    renamed = state.rename_preset(old, new)
    return {"status": "ok", "renamed": renamed}


# ----------------- Apply Preset via URL -----------------

@app.get("/preset/{preset_name}")
async def activate_preset_by_url(preset_name: str):
    normalized = preset_name.replace("-", " ").lower()

    match = None
    for name, data in state.presets.items():
        if name.lower() == normalized:
            match = (name, data)
            break

    if not match:
        raise HTTPException(status_code=404, detail="Preset not found")

    preset_name, preset_data = match

    if not isinstance(preset_data, dict) or "url" not in preset_data:
        raise HTTPException(
            status_code=500,
            detail=f"Preset '{preset_name}' must be stored as an object: {{ 'url': '...' }}"
        )

    # Apply preset
    state.set_current_url(preset_data["url"])
    state.clear_timer()  # ensure no temporary override stays active

    return {
        "status": "ok",
        "active_preset": preset_name,
        "active_url": preset_data["url"],
    }


# ----------------- DEV ENTRYPOINT -----------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
