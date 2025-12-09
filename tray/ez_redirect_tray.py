import json
import os
import platform
import subprocess
import webbrowser
from pathlib import Path

from PIL import Image, ImageDraw
import pystray

# Default path for installed config
DEFAULT_CONFIG_PATH = Path("/usr/local/ez-redirect/backend/config.json")


def load_config():
    path = Path(os.environ.get("EZ_REDIRECT_CONFIG", DEFAULT_CONFIG_PATH))
    try:
        with path.open("r") as f:
            return json.load(f)
    except Exception:
        return {"port": 8000}


def get_port():
    cfg = load_config()
    return int(cfg.get("port", 8000))


def open_interface(icon, menu_item):
    port = get_port()
    webbrowser.open(f"http://localhost:{port}")


def restart_service(icon, menu_item):
    system = platform.system().lower()
    if system == "darwin":
        # macOS launchctl user agent
        uid = os.getuid()
        label = "com.ezredirect.app"
        subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"])
    elif system == "windows":
        # Placeholder: wire this up to a Windows Service if you create one
        # subprocess.run(["sc", "stop", "ezredirect"])
        # subprocess.run(["sc", "start", "ezredirect"])
        pass


def quit_app(icon, menu_item):
    icon.stop()


def create_icon_image():
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Background circle
    draw.ellipse((4, 4, size - 4, size - 4), fill=(17, 24, 39, 255))

    # Super simple visual marker; you can replace with a real PNG later
    return image


def run_tray():
    icon_image = create_icon_image()
    icon = pystray.Icon(
        "ezredirect",
        icon_image,
        "EZ Redirect",
        menu=pystray.Menu(
            pystray.MenuItem(lambda: f"Port: {get_port()}", None, enabled=False),
            pystray.MenuItem("Open Interface", open_interface),
            pystray.MenuItem("Restart Service", restart_service),
            pystray.MenuItem("Quit", quit_app),
        ),
    )
    icon.run()


if __name__ == "__main__":
    run_tray()
