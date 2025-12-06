#!/bin/bash

set -e

REPO_URL="https://github.com/notandrewjones/ez-redirect.git"
INSTALL_DIR="/opt/ez-redirect"
SERVICE_FILE="/etc/systemd/system/ez-redirect.service"

echo "🚀 Installing ez-redirect..."

# Install dependencies
echo "📦 Installing Python + FastAPI + Uvicorn..."
sudo apt update
sudo apt install -y python3 python3-pip git

sudo pip3 install fastapi uvicorn[standard]

# Clone or update repo
if [ ! -d "$INSTALL_DIR" ]; then
    echo "📥 Cloning repository into $INSTALL_DIR..."
    sudo git clone "$REPO_URL" "$INSTALL_DIR"
else
    echo "🔄 Updating existing installation..."
    cd "$INSTALL_DIR"
    sudo git pull
fi

# Permissions
sudo chown -R $USER:$USER "$INSTALL_DIR"

# Install or update service
echo "⚙️ Installing systemd service ez-redirect..."
sudo cp "$INSTALL_DIR/ez-redirect.service" "$SERVICE_FILE"
sudo chmod 644 "$SERVICE_FILE"

# Reload systemd manager configuration
sudo systemctl daemon-reload

# Enable service to run on boot
sudo systemctl enable ez-redirect

# Start or restart the service
sudo systemctl restart ez-redirect

echo ""
echo "🎉 ez-redirect installation complete!"
echo ""
echo "Your redirect service is now running at:"
echo "👉 http://$(hostname -I | awk '{print $1}'):8000/"
echo ""
echo "Manage with:"
echo "  sudo systemctl start ez-redirect"
echo "  sudo systemctl stop ez-redirect"
echo "  sudo systemctl restart ez-redirect"
echo "  sudo systemctl status ez-redirect"
echo ""
echo "To update later:"
echo "  cd /opt/ez-redirect && sudo git pull && sudo systemctl restart ez-redirect"
