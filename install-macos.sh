#!/bin/bash

set -e

echo "Installing ez-redirect (macOS)..."

# Install Homebrew Python + git
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required. Install from https://brew.sh"
    exit 1
fi

brew install python git

INSTALL_DIR="/usr/local/ez-redirect"
VENV_DIR="$INSTALL_DIR/venv"

# Clone or update repo
if [ ! -d "$INSTALL_DIR" ]; then
    sudo git clone https://github.com/notandrewjones/ez-redirect.git "$INSTALL_DIR"
else
    sudo git -C "$INSTALL_DIR" pull
fi

# Create venv (avoids PEP 668 issues)
echo "Creating Python virtual environment..."
sudo python3 -m venv "$VENV_DIR"

# Install dependencies inside venv
echo "Installing Python dependencies in venv..."
sudo "$VENV_DIR/bin/pip" install fastapi uvicorn[standard]

# Create launchd service
PLIST=~/Library/LaunchAgents/com.ezredirect.app.plist

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

echo "Loading launchd service..."
launchctl unload $PLIST 2>/dev/null || true
launchctl load $PLIST

echo "ez-redirect installed and running at:"
echo "http://localhost:8000"
