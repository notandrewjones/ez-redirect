#!/bin/bash
set -e

# ============================================================
# EZ Redirect - macOS Installer
# ============================================================
# This installer can work from:
#   1. A local directory (if you have the files already)
#   2. A git clone (if REPO_URL is set and accessible)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/usr/local/ez-redirect"
VENV_DIR="$INSTALL_DIR/venv"
PLIST_DIR="$HOME/Library/LaunchAgents"
SERVICE_PLIST="$PLIST_DIR/com.ezredirect.service.plist"
TRAY_PLIST="$PLIST_DIR/com.ezredirect.tray.plist"

# Optional: Set this if you want to pull from git instead of local
REPO_URL="${EZ_REDIRECT_REPO:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# ============================================================
# Check for Homebrew and Python
# ============================================================
check_dependencies() {
    echo ""
    echo "Checking dependencies..."
    
    if ! command -v brew &> /dev/null; then
        print_error "Homebrew is required but not installed."
        echo "Install it from: https://brew.sh"
        echo "Run: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    print_status "Homebrew found"
    
    # Install python if needed
    if ! command -v python3 &> /dev/null; then
        print_warning "Python3 not found. Installing via Homebrew..."
        brew install python
    fi
    print_status "Python3 found: $(python3 --version)"
}

# ============================================================
# Stop existing services
# ============================================================
stop_existing_services() {
    echo ""
    echo "Stopping any existing services..."
    
    launchctl unload "$SERVICE_PLIST" 2>/dev/null || true
    launchctl unload "$TRAY_PLIST" 2>/dev/null || true
    
    # Also try to kill any running processes
    pkill -f "ez_redirect_tray" 2>/dev/null || true
    pkill -f "run_service.py" 2>/dev/null || true
    
    print_status "Existing services stopped"
}

# ============================================================
# Create install directory
# ============================================================
setup_install_dir() {
    echo ""
    echo "Setting up installation directory..."
    
    if [ ! -d "$INSTALL_DIR" ]; then
        sudo mkdir -p "$INSTALL_DIR"
    fi
    sudo chown -R "$(whoami)":admin "$INSTALL_DIR"
    print_status "Install directory ready: $INSTALL_DIR"
}

# ============================================================
# Copy or clone files
# ============================================================
install_files() {
    echo ""
    echo "Installing application files..."
    
    if [ -n "$REPO_URL" ]; then
        # Clone from git
        if [ -d "$INSTALL_DIR/.git" ]; then
            print_status "Updating from git..."
            cd "$INSTALL_DIR"
            git pull --ff-only
        else
            print_status "Cloning from git..."
            rm -rf "$INSTALL_DIR"/*
            git clone "$REPO_URL" "$INSTALL_DIR"
        fi
    else
        # Copy from local directory
        print_status "Copying files from local directory..."
        
        # Check if we're running from within the project directory
        if [ -f "$SCRIPT_DIR/backend/app.py" ]; then
            SOURCE_DIR="$SCRIPT_DIR"
        elif [ -f "$SCRIPT_DIR/../backend/app.py" ]; then
            SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
        else
            print_error "Cannot find project files. Run this script from the ez-redirect directory."
            exit 1
        fi
        
        # Copy files (excluding .git, __pycache__, etc.)
        rsync -av --exclude='.git' \
                  --exclude='__pycache__' \
                  --exclude='*.pyc' \
                  --exclude='.DS_Store' \
                  --exclude='venv' \
                  --exclude='*.log' \
                  "$SOURCE_DIR/" "$INSTALL_DIR/"
    fi
    
    print_status "Files installed"
}

# ============================================================
# Setup Python virtual environment
# ============================================================
setup_venv() {
    echo ""
    echo "Setting up Python virtual environment..."
    
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        print_status "Virtual environment created"
    else
        print_status "Virtual environment exists"
    fi
    
    # Activate and install dependencies
    source "$VENV_DIR/bin/activate"
    
    pip install --upgrade pip --quiet
    pip install fastapi "uvicorn[standard]" pystray pillow rumps --quiet
    
    print_status "Python dependencies installed"
}

# ============================================================
# Create default config files if missing
# ============================================================
setup_config() {
    echo ""
    echo "Setting up configuration..."
    
    mkdir -p "$INSTALL_DIR/backend"
    
    CONFIG_PATH="$INSTALL_DIR/backend/config.json"
    if [ ! -f "$CONFIG_PATH" ]; then
        cat > "$CONFIG_PATH" <<'CONFIGEOF'
{
    "default_url": "https://example.com",
    "current_url": "https://example.com",
    "expires_at": null,
    "port": 8000,
    "api_key_enabled": false,
    "api_key": null
}
CONFIGEOF
        print_status "Created default config.json"
    else
        print_status "config.json exists"
    fi
    
    PRESETS_PATH="$INSTALL_DIR/backend/presets.json"
    if [ ! -f "$PRESETS_PATH" ]; then
        echo '{}' > "$PRESETS_PATH"
        print_status "Created default presets.json"
    else
        print_status "presets.json exists"
    fi
}

# ============================================================
# Create LaunchAgent for the backend service
# ============================================================
create_service_plist() {
    echo ""
    echo "Creating backend service LaunchAgent..."
    
    mkdir -p "$PLIST_DIR"
    
    cat > "$SERVICE_PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ezredirect.service</string>

    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>$INSTALL_DIR/backend/run_service.py</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$INSTALL_DIR</string>
    </dict>

    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/service.log</string>

    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/service-error.log</string>

    <key>ThrottleInterval</key>
    <integer>5</integer>
</dict>
</plist>
PLISTEOF

    print_status "Service LaunchAgent created"
}

# ============================================================
# Create LaunchAgent for the tray app
# ============================================================
create_tray_plist() {
    echo ""
    echo "Creating tray app LaunchAgent..."
    
    cat > "$TRAY_PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ezredirect.tray</string>

    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>$INSTALL_DIR/tray/ez_redirect_tray.py</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <false/>

    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$INSTALL_DIR</string>
        <key>EZ_REDIRECT_CONFIG</key>
        <string>$INSTALL_DIR/backend/config.json</string>
    </dict>

    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/tray.log</string>

    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/tray-error.log</string>

    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
</dict>
</plist>
PLISTEOF

    print_status "Tray app LaunchAgent created"
}

# ============================================================
# Create logs directory
# ============================================================
setup_logs() {
    mkdir -p "$INSTALL_DIR/logs"
    print_status "Logs directory created"
}

# ============================================================
# Start services
# ============================================================
start_services() {
    echo ""
    echo "Starting services..."
    
    launchctl load "$SERVICE_PLIST"
    print_status "Backend service started"
    
    # Small delay to let the service start
    sleep 2
    
    launchctl load "$TRAY_PLIST"
    print_status "Tray app started"
}

# ============================================================
# Create helper scripts
# ============================================================
create_helper_scripts() {
    echo ""
    echo "Creating helper scripts..."
    
    # ez-update script
    sudo tee /usr/local/bin/ez-update > /dev/null <<'UPDATEEOF'
#!/bin/bash
set -e

INSTALL_DIR="/usr/local/ez-redirect"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.service.plist"
TRAY_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.tray.plist"

echo "Stopping services..."
launchctl unload "$SERVICE_PLIST" 2>/dev/null || true
launchctl unload "$TRAY_PLIST" 2>/dev/null || true

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating from git..."
    cd "$INSTALL_DIR"
    git pull --ff-only
fi

echo "Updating Python dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install fastapi "uvicorn[standard]" pystray pillow rumps --quiet

echo "Starting services..."
launchctl load "$SERVICE_PLIST"
sleep 2
launchctl load "$TRAY_PLIST"

echo ""
echo "✅ ez-redirect updated and restarted!"
UPDATEEOF
    sudo chmod +x /usr/local/bin/ez-update
    
    # ez-restart script
    sudo tee /usr/local/bin/ez-restart > /dev/null <<'RESTARTEOF'
#!/bin/bash
SERVICE_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.service.plist"
TRAY_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.tray.plist"

echo "Restarting ez-redirect..."

launchctl unload "$SERVICE_PLIST" 2>/dev/null || true
launchctl unload "$TRAY_PLIST" 2>/dev/null || true

sleep 1

launchctl load "$SERVICE_PLIST"
sleep 2
launchctl load "$TRAY_PLIST"

echo "✅ ez-redirect restarted!"
RESTARTEOF
    sudo chmod +x /usr/local/bin/ez-restart
    
    # ez-stop script
    sudo tee /usr/local/bin/ez-stop > /dev/null <<'STOPEOF'
#!/bin/bash
SERVICE_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.service.plist"
TRAY_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.tray.plist"

echo "Stopping ez-redirect..."

launchctl unload "$SERVICE_PLIST" 2>/dev/null || true
launchctl unload "$TRAY_PLIST" 2>/dev/null || true

echo "✅ ez-redirect stopped!"
STOPEOF
    sudo chmod +x /usr/local/bin/ez-stop
    
    # ez-status script
    sudo tee /usr/local/bin/ez-status > /dev/null <<'STATUSEOF'
#!/bin/bash
echo "EZ Redirect Status"
echo "=================="

# Check service
if launchctl list | grep -q "com.ezredirect.service"; then
    echo "✅ Backend service: Running"
else
    echo "❌ Backend service: Not running"
fi

# Check tray
if launchctl list | grep -q "com.ezredirect.tray"; then
    echo "✅ Tray app: Running"
else
    echo "❌ Tray app: Not running"
fi

# Check if port is responding
PORT=$(python3 -c "import json; print(json.load(open('/usr/local/ez-redirect/backend/config.json')).get('port', 8000))" 2>/dev/null || echo "8000")
if curl -s "http://localhost:$PORT/api/current" > /dev/null 2>&1; then
    echo "✅ API responding on port $PORT"
else
    echo "❌ API not responding on port $PORT"
fi

echo ""
echo "Logs:"
echo "  Service: /usr/local/ez-redirect/logs/service.log"
echo "  Tray:    /usr/local/ez-redirect/logs/tray.log"
STATUSEOF
    sudo chmod +x /usr/local/bin/ez-status
    
    # ez-uninstall script
    sudo tee /usr/local/bin/ez-uninstall > /dev/null <<'UNINSTALLEOF'
#!/bin/bash
echo "Uninstalling ez-redirect..."

SERVICE_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.service.plist"
TRAY_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.tray.plist"

# Stop services
launchctl unload "$SERVICE_PLIST" 2>/dev/null || true
launchctl unload "$TRAY_PLIST" 2>/dev/null || true

# Remove plists
rm -f "$SERVICE_PLIST"
rm -f "$TRAY_PLIST"

# Remove install directory
sudo rm -rf /usr/local/ez-redirect

# Remove helper scripts
sudo rm -f /usr/local/bin/ez-update
sudo rm -f /usr/local/bin/ez-restart
sudo rm -f /usr/local/bin/ez-stop
sudo rm -f /usr/local/bin/ez-status
sudo rm -f /usr/local/bin/ez-uninstall

echo "✅ ez-redirect has been uninstalled!"
UNINSTALLEOF
    sudo chmod +x /usr/local/bin/ez-uninstall
    
    print_status "Helper scripts created"
}

# ============================================================
# Main installation
# ============================================================
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║           EZ Redirect - macOS Installer                ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    
    check_dependencies
    stop_existing_services
    setup_install_dir
    install_files
    setup_venv
    setup_config
    setup_logs
    create_service_plist
    create_tray_plist
    create_helper_scripts
    start_services
    
    # Get the configured port
    PORT=$(python3 -c "import json; print(json.load(open('$INSTALL_DIR/backend/config.json')).get('port', 8000))" 2>/dev/null || echo "8000")
    
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║           Installation Complete! 🎉                    ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    echo "  📍 Install location: $INSTALL_DIR"
    echo "  🌐 Web interface:    http://localhost:$PORT"
    echo "  🔄 Redirect URL:     http://localhost:$PORT/redirect"
    echo ""
    echo "  Helper commands:"
    echo "    ez-status    - Check service status"
    echo "    ez-restart   - Restart all services"
    echo "    ez-stop      - Stop all services"  
    echo "    ez-update    - Update and restart"
    echo "    ez-uninstall - Remove ez-redirect"
    echo ""
    echo "  The tray icon should appear in your menu bar."
    echo ""
}

main "$@"