# EZ Redirect

A simple, portable redirect server with a web interface and macOS menu bar app. Perfect for NFC tags, dynamic link routing, and LAN-based redirects.

## Features

- 🔄 **Instant Redirects**: Change where `/redirect` points with one click
- ⏱️ **Temporary Redirects**: Set a redirect that auto-reverts after a timer
- 📋 **Presets**: Save and quickly switch between common URLs
- 🔒 **API Security**: Optional API key protection for remote triggers
- 🖥️ **Menu Bar App**: macOS tray icon for quick access
- 🚀 **Auto-Start**: Runs on login automatically

## Quick Install (macOS)

```bash
# Clone or download the repository
git clone https://github.com/notandrewjones/ez-redirect.git
cd ez-redirect

# Run the installer
chmod +x install-macos.sh
./install-macos.sh
```

Or if you already have the files locally:

```bash
cd /path/to/ez-redirect
chmod +x install-macos.sh
./install-macos.sh
```

## What Gets Installed

- **Application**: `/usr/local/ez-redirect/`
- **Python venv**: `/usr/local/ez-redirect/venv/`
- **Config files**: `/usr/local/ez-redirect/backend/config.json`
- **Log files**: `/usr/local/ez-redirect/logs/`
- **LaunchAgents**: `~/Library/LaunchAgents/com.ezredirect.*.plist`

## Usage

### Web Interface

Open `http://localhost:8000` (or your configured port) to access the web UI.

### Redirect URL

Point your NFC tags or shortcuts to:
```
http://your-mac-ip:8000/redirect
```

### Activate Presets via URL

```
http://your-mac-ip:8000/preset/giving
http://your-mac-ip:8000/preset/my-preset?key=YOUR_API_KEY
```

### Menu Bar App

The menu bar icon provides:
- Current status and redirect URL
- Quick link to open the web interface
- Copy redirect URL to clipboard
- Restart service
- View logs

## Helper Commands

After installation, these commands are available system-wide:

| Command | Description |
|---------|-------------|
| `ez-status` | Check if services are running |
| `ez-restart` | Restart all services |
| `ez-stop` | Stop all services |
| `ez-update` | Update from git and restart |
| `ez-uninstall` | Remove ez-redirect completely |

## Configuration

Edit `/usr/local/ez-redirect/backend/config.json`:

```json
{
    "default_url": "https://example.com",
    "current_url": "https://example.com",
    "expires_at": null,
    "port": 8000,
    "api_key_enabled": false,
    "api_key": "your-secret-key"
}
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/redirect` | The actual redirect (use this for NFC) |
| GET | `/api/current` | Get current redirect info |
| POST | `/api/set` | Set current redirect URL |
| POST | `/api/temp` | Set temporary redirect |
| POST | `/api/set-default` | Set default URL |
| GET | `/api/presets` | List all presets |
| POST | `/api/presets/add` | Add/update a preset |
| POST | `/api/presets/delete` | Delete a preset |
| GET | `/preset/{name}` | Activate a preset by name |
| GET | `/api/port` | Get current port |
| POST | `/api/port` | Change port (requires restart) |
| GET | `/api/security/status` | Get API key status |
| POST | `/api/security/toggle` | Enable/disable API key |

## Troubleshooting

### Service not starting

Check the logs:
```bash
cat /usr/local/ez-redirect/logs/service-error.log
```

Or use the status command:
```bash
ez-status
```

### Tray app not appearing

1. Check if it's running: `launchctl list | grep ezredirect`
2. Check tray logs: `cat /usr/local/ez-redirect/logs/tray-error.log`
3. Restart it: `ez-restart`

### Port already in use

Change the port in config.json and restart:
```bash
# Edit the config
nano /usr/local/ez-redirect/backend/config.json
# Change "port": 8000 to another port

# Restart
ez-restart
```

### Reinstalling

```bash
ez-uninstall
# Then run the installer again
./install-macos.sh
```

## Development

To run locally without installing:

```bash
cd ez-redirect

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run the server
python backend/run_service.py

# In another terminal, run the tray app (optional)
python tray/ez_redirect_tray.py
```

## License

MIT