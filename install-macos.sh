#!/bin/bash

set -e

echo "Installing ez-redirect (macOS)..."

# Install Homebrew if missing
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required. Install from https://brew.sh"
    exit 1
fi

brew install python git

INSTALL_DIR="/usr/local/ez-redirect"

# Clone or update repo
if [ ! -d "$INSTALL_DIR" ]; then
    sudo git clone https://github.com/YOUR_GITHUB_USERNAME/ez-redirect.git "$INSTALL_DIR"
else
    sudo git -C "$INSTALL_DIR" pull
fi

sudo pip3 install fastapi uvicorn[standard]

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
        <string>python3</string>
        <string>$INSTALL_DIR/backend/app.py</string>
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

launchctl load $PLIST

echo "ez-redirect installed and started."
echo "Access at http://localhost:8000"
