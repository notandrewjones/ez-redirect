from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi import HTTPException

from .redirect_state import RedirectState

app = FastAPI(
    title="Local Redirect Controller",
    debug=True
)


# Allow browser calls from the same origin or others if you ever host UI separately
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can lock this down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state = RedirectState()

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

print("BASE_DIR:", BASE_DIR)
print("WEB_DIR:", WEB_DIR)


# ----------------- UI ROUTES -----------------

@app.get("/")
def serve_index():
    """Serve the main HTML UI."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/styles.css")
def serve_styles():
    """Serve the CSS file referenced from index.html."""
    return FileResponse(WEB_DIR / "styles.css")


# ----------------- REDIRECT ENDPOINT -----------------

@app.get("/redirect")
def redirect():
    """
    This is the URL your NFC tags should point to.
    It will 302 redirect to the current active URL.
    """
    target = state.get_current_url()
    return Response(status_code=302, headers={"Location": target})


# ----------------- API ENDPOINTS -----------------

@app.get("/api/current")
def api_current():
    """Get current redirect info (URL, default, temporary flag, etc.)"""
    return state.info()


@app.post("/api/set")
def api_set(url: str):
    """Set the active redirect URL (clears any temporary override)."""
    state.set_url(url)
    return {"status": "ok", "current_url": state.get_current_url()}


@app.post("/api/temp")
def api_temp(url: str, seconds: int):
    """
    Set a temporary redirect for <seconds>.
    After that time, it will revert to the default URL.
    """
    state.set_temp(url, seconds)
    return {"status": "ok", "current_url": state.get_current_url(), "expires_in": seconds}


@app.post("/api/set-default")
def api_set_default(url: str):
    """Optional: change the default URL."""
    state.set_default(url)
    return {"status": "ok", "default_url": url}


# --------- Presets ---------

@app.get("/api/presets")
def api_get_presets():
    """Return all presets as {name: url}."""
    return state.get_presets()


@app.post("/api/presets/add")
def api_add_preset(name: str, url: str):
    """
    Add or update a preset.
    If a preset with that name exists, it will be overwritten.
    """
    state.add_or_update_preset(name, url)
    return {"status": "ok"}


@app.post("/api/presets/delete")
def api_delete_preset(name: str):
    """Delete a preset by name."""
    state.delete_preset(name)
    return {"status": "ok"}
    
@app.post("/api/presets/rename")
def api_rename_preset(old: str, new: str):
    renamed = state.rename_preset(old, new)
    return {"status": "ok", "renamed": renamed}
    
# ----------------- Apply Preset with URL ----------------

@app.get("/preset/{preset_name}")
async def activate_preset_by_url(preset_name: str):
    # normalize for matching
    normalized = preset_name.replace("-", " ").lower()

    # find matching preset
    match = None
    for name, data in state.presets.items():
        if name.lower() == normalized:
            match = (name, data)
            break

    if not match:
        raise HTTPException(status_code=404, detail="Preset not found")

    preset_name, preset_data = match

    # apply preset
    state.set_current_url(preset_data["url"])
    state.clear_timer()  # cancel any timed override
    state.save()

    # return confirmation or redirect to UI
    return {
        "status": "ok",
        "active_preset": preset_name,
        "active_url": preset_data["url"],
    }


# ----------------- DEV ENTRYPOINT -----------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=5000, reload=True)
