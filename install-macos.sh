#!/bin/bash
set -e

echo "Installing ez-redirect (macOS)..."

# --- Requirements ---
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required. Install from https://brew.sh"
    exit 1
fi

brew install python git

INSTALL_DIR="/usr/local/ez-redirect"
VENV_DIR="$INSTALL_DIR/venv"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/com.ezredirect.app.plist"

REPO_URL="https://github.com/notandrewjones/ez-redirect.git"

# --- Clone or update repo into INSTALL_DIR ---
if [ ! -d "$INSTALL_DIR" ]; then
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$(whoami)":admin "$INSTALL_DIR"
fi

if [ ! -d "$INSTALL_DIR/.git" ]; then
    echo "Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
else
    echo "Updating existing repo..."
    cd "$INSTALL_DIR"
    git pull --ff-only
fi

cd "$INSTALL_DIR"

# --- Python virtual environment ---
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pystray pillow

# --- Ensure backend/web/tray directories exist ---
mkdir -p "$INSTALL_DIR/backend"
mkdir -p "$INSTALL_DIR/web"
mkdir -p "$INSTALL_DIR/tray"

# --- Create default config.json if missing ---
CONFIG_PATH="$INSTALL_DIR/backend/config.json"
if [ ! -f "$CONFIG_PATH" ]; then
    cat > "$CONFIG_PATH" <<EOF
{
    "default_url": "https://example.com",
    "current_url": "https://example.com",
    "expires_at": null,
    "port": 8000,
    "api_key_enabled": false,
    "api_key": null
}
EOF
fi

# --- LaunchAgent plist for user session ---
mkdir -p "$PLIST_DIR"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ezredirect.app</string>

    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>$INSTALL_DIR/backend/run_service.py</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/ez-redirect.log</string>

    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/ez-redirect-error.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

# --- ez-update helper script ---
UPDATE_SCRIPT="/usr/local/bin/ez-update"

sudo bash -c "cat > '$UPDATE_SCRIPT'" <<'EOF'
#!/bin/bash
set -e

INSTALL_DIR="/usr/local/ez-redirect"
VENV_DIR="$INSTALL_DIR/venv"
PLIST_PATH="$HOME/Library/LaunchAgents/com.ezredirect.app.plist"

cd "$INSTALL_DIR"
git pull --ff-only

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pystray pillow

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "ez-redirect updated and restarted."
EOF

sudo chmod +x "$UPDATE_SCRIPT"

echo ""
echo "🎉 ez-redirect installation complete!"
echo "Service is running on your configured port (default: 8000)."
echo "Open: http://localhost:8000"
echo ""
echo "To update anytime, run: ez-update"
echo ""
