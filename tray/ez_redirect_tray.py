#!/usr/bin/env python3
"""
EZ Redirect - macOS Menu Bar App

This creates a menu bar icon with controls for the EZ Redirect service.
Uses rumps for native macOS integration (preferred) with pystray fallback.
"""

import json
import os
import subprocess
import sys
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path

# Default paths
DEFAULT_INSTALL_DIR = Path("/usr/local/ez-redirect")
DEFAULT_CONFIG_PATH = DEFAULT_INSTALL_DIR / "backend" / "config.json"

# Check for rumps (native macOS) first, then fall back to pystray
try:
    import rumps
    USE_RUMPS = True
except ImportError:
    USE_RUMPS = False
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        print("Error: Neither rumps nor pystray is installed.")
        print("Install with: pip install rumps  (recommended for macOS)")
        print("Or: pip install pystray pillow")
        sys.exit(1)


def get_config_path():
    """Get config path from environment or use default"""
    env_path = os.environ.get("EZ_REDIRECT_CONFIG")
    if env_path:
        return Path(env_path)
    return DEFAULT_CONFIG_PATH


def load_config():
    """Load configuration from config.json"""
    config_path = get_config_path()
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load config from {config_path}: {e}")
        return {"port": 8000}


def get_port():
    """Get the configured port"""
    return int(load_config().get("port", 8000))


def get_current_url():
    """Fetch current redirect URL from API"""
    try:
        port = get_port()
        url = f"http://localhost:{port}/api/current"
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read().decode())
            return data.get("current_url", "Unknown")
    except Exception:
        return "Service not responding"


def is_service_running():
    """Check if the backend service is running"""
    try:
        port = get_port()
        url = f"http://localhost:{port}/api/current"
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def open_interface():
    """Open the web interface in the default browser"""
    port = get_port()
    webbrowser.open(f"http://localhost:{port}")


def copy_redirect_url():
    """Copy the redirect URL to clipboard"""
    port = get_port()
    redirect_url = f"http://localhost:{port}/redirect"
    
    # Use pbcopy on macOS
    process = subprocess.Popen(
        ["pbcopy"],
        stdin=subprocess.PIPE,
        env={**os.environ, "LANG": "en_US.UTF-8"}
    )
    process.communicate(redirect_url.encode("utf-8"))


def restart_service():
    """Restart the backend service"""
    try:
        uid = os.getuid()
        label = "com.ezredirect.service"
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"],
            check=False
        )
    except Exception as e:
        print(f"Error restarting service: {e}")


def view_logs():
    """Open the log files in Console.app"""
    log_path = DEFAULT_INSTALL_DIR / "logs" / "service.log"
    if log_path.exists():
        subprocess.run(["open", "-a", "Console", str(log_path)])
    else:
        # Try opening the logs directory
        logs_dir = DEFAULT_INSTALL_DIR / "logs"
        if logs_dir.exists():
            subprocess.run(["open", str(logs_dir)])


# ============================================================
# RUMPS Implementation (Native macOS - Preferred)
# ============================================================

if USE_RUMPS:
    class EZRedirectApp(rumps.App):
        def __init__(self):
            super().__init__(
                "EZ Redirect",
                icon=self.create_icon(),
                quit_button=None  # We'll add our own
            )
            self.menu = [
                rumps.MenuItem("Status: Checking...", callback=None),
                rumps.MenuItem("Current: Loading...", callback=None),
                None,  # Separator
                rumps.MenuItem("Open Interface", callback=self.on_open_interface),
                rumps.MenuItem("Copy Redirect URL", callback=self.on_copy_url),
                None,  # Separator
                rumps.MenuItem("Restart Service", callback=self.on_restart),
                rumps.MenuItem("View Logs", callback=self.on_view_logs),
                None,  # Separator
                rumps.MenuItem("Quit", callback=self.on_quit),
            ]
            
            # Start a timer to update status
            self.timer = rumps.Timer(self.update_status, 5)
            self.timer.start()
            
            # Initial update
            self.update_status(None)
        
        def create_icon(self):
            """Create the menu bar icon"""
            # Try to use a custom icon if it exists
            icon_path = DEFAULT_INSTALL_DIR / "tray" / "icon.png"
            if icon_path.exists():
                return str(icon_path)
            
            # Return None to use default (or create one dynamically)
            # For now, we'll use the app title as a fallback
            return None
        
        def update_status(self, _):
            """Update the status menu items"""
            try:
                running = is_service_running()
                port = get_port()
                
                if running:
                    self.menu["Status: Checking..."].title = f"● Status: Running (port {port})"
                    current = get_current_url()
                    # Truncate long URLs
                    if len(current) > 40:
                        current = current[:37] + "..."
                    self.menu["Current: Loading..."].title = f"→ {current}"
                else:
                    self.menu["Status: Checking..."].title = "○ Status: Not Running"
                    self.menu["Current: Loading..."].title = "→ Service offline"
            except Exception as e:
                print(f"Error updating status: {e}")
        
        def on_open_interface(self, _):
            open_interface()
        
        def on_copy_url(self, _):
            copy_redirect_url()
            rumps.notification(
                "EZ Redirect",
                "Copied!",
                "Redirect URL copied to clipboard",
                sound=False
            )
        
        def on_restart(self, _):
            restart_service()
            rumps.notification(
                "EZ Redirect",
                "Restarting",
                "Service is restarting...",
                sound=False
            )
            # Update status after a short delay
            rumps.Timer(self.update_status, 3).start()
        
        def on_view_logs(self, _):
            view_logs()
        
        def on_quit(self, _):
            rumps.quit_application()
    
    def run_tray():
        """Run the rumps-based tray app"""
        app = EZRedirectApp()
        app.run()


# ============================================================
# PYSTRAY Implementation (Fallback)
# ============================================================

else:
    def create_pystray_icon():
        """Create a simple icon for pystray"""
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Dark circle background
        draw.ellipse((4, 4, size - 4, size - 4), fill=(17, 24, 39, 255))
        
        # Arrow symbol
        arrow_color = (74, 222, 128, 255)  # Green
        # Draw a simple right-pointing arrow
        draw.polygon([
            (20, 18),
            (44, 32),
            (20, 46)
        ], fill=arrow_color)
        
        return image
    
    def run_tray():
        """Run the pystray-based tray app"""
        
        def on_open(icon, item):
            open_interface()
        
        def on_copy(icon, item):
            copy_redirect_url()
        
        def on_restart(icon, item):
            restart_service()
        
        def on_logs(icon, item):
            view_logs()
        
        def on_quit(icon, item):
            icon.stop()
        
        def get_status_text():
            if is_service_running():
                return f"● Running (port {get_port()})"
            return "○ Not Running"
        
        def get_current_text():
            if is_service_running():
                url = get_current_url()
                if len(url) > 35:
                    url = url[:32] + "..."
                return f"→ {url}"
            return "→ Service offline"
        
        icon_image = create_pystray_icon()
        icon = pystray.Icon(
            "ezredirect",
            icon_image,
            "EZ Redirect",
            menu=pystray.Menu(
                pystray.MenuItem(get_status_text, None, enabled=False),
                pystray.MenuItem(get_current_text, None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Open Interface", on_open),
                pystray.MenuItem("Copy Redirect URL", on_copy),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Restart Service", on_restart),
                pystray.MenuItem("View Logs", on_logs),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", on_quit),
            ),
        )
        icon.run()


# ============================================================
# Main Entry Point
# ============================================================

if __name__ == "__main__":
    print(f"Starting EZ Redirect tray app (using {'rumps' if USE_RUMPS else 'pystray'})...")
    run_tray()