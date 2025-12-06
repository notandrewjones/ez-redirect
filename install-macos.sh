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
PLIST=~/Library/LaunchAgents/com.ezredirect.app.plist

# --- Clone or Update Repo ---

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Cloning repository..."
    sudo git clone https://github.com/notandrewjones/ez-redirect.git "$INSTALL_DIR"
else
    echo "Updating repository..."
    sudo git -C "$INSTALL_DIR" pull
fi

# --- Fix Ownership Automatically ---
echo "Fixing permissions..."
sudo chown -R $USER:staff "$INSTALL_DIR"

# Mark directory as safe for Git
git config --global --add safe.directory "$INSTALL_DIR"

# --- Create Virtual Environment ---

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install fastapi uvicorn[standard]

# --- Create launchd Service ---

echo "Creating launchd plist..."

cat <<EOF > $PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ezredirect.app</string>

    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/uvicorn</string>
        <string>backend.app:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8000</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

echo "Reloading launchd service..."
launchctl unload $PLIST 2>/dev/null || true
launchctl load $PLIST

# --- Install ez-update Command ---
echo "Installing ez-update command..."

UPDATE_SCRIPT="/usr/local/bin/ez-update"

sudo tee $UPDATE_SCRIPT > /dev/null <<EOF
#!/bin/bash
echo "Updating ez-redirect..."
cd $INSTALL_DIR
git pull
launchctl unload $PLIST
launchctl load $PLIST
echo "Update complete."
EOF

sudo chmod +x $UPDATE_SCRIPT

echo ""
echo "🎉 ez-redirect installation complete!"
echo "Service is running at: http://localhost:8000"
echo ""
echo "To update anytime, run:"
echo "    ez-update"
echo ""
