#!/bin/bash
# EZ Redirect updater (macOS).
#
# /usr/local/bin/ez-update is a tiny wrapper that runs this file from the
# install directory, so changes to the update logic ship with git like any
# other code -- no reinstall needed.
#
# The install directory is a deployment copy: it always ends up matching
# GitHub exactly. Live data (config.json, presets.json) is preserved, and any
# hand edits to code are saved as a patch before being replaced, never lost.
#
# Everything is inside main() so bash reads the whole script before running
# it; git replaces this file mid-update.

INSTALL_DIR="${EZ_INSTALL_DIR:-/usr/local/ez-redirect}"
BRANCH="${EZ_BRANCH:-main}"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.service.plist"
TRAY_PLIST="$HOME/Library/LaunchAgents/com.ezredirect.tray.plist"
WRAPPER="${EZ_WRAPPER:-/usr/local/bin/ez-update}"
LIVE_FILES=(backend/config.json backend/presets.json)
BACKUP_DIR="$HOME/.ez-redirect-backups/$(date +%Y%m%d-%H%M%S)"

main() {
    set -uo pipefail

    if [ ! -d "$INSTALL_DIR/.git" ]; then
        echo "❌ $INSTALL_DIR is not a git checkout; can't update."
        exit 1
    fi
    cd "$INSTALL_DIR" || exit 1

    echo "Stopping services..."
    launchctl unload "$SERVICE_PLIST" 2>/dev/null || true
    launchctl unload "$TRAY_PLIST" 2>/dev/null || true

    # Whatever happens from here on, restart the service before exiting.
    trap 'start_services' EXIT

    echo "Fetching latest version..."
    if ! git fetch --quiet origin "$BRANCH"; then
        echo "❌ Couldn't reach GitHub. Restarting the current version unchanged."
        exit 1
    fi

    # Back up live settings and any local code edits.
    mkdir -p "$BACKUP_DIR"
    local f
    for f in "${LIVE_FILES[@]}"; do
        [ -f "$f" ] && cp "$f" "$BACKUP_DIR/"
    done
    if ! git diff --quiet HEAD -- . ':!backend/config.json' ':!backend/presets.json' ':!*.pyc'; then
        git diff HEAD -- . ':!backend/config.json' ':!backend/presets.json' ':!*.pyc' \
            > "$BACKUP_DIR/local-code-changes.patch"
        echo "⚠️  Found local edits to code files on this machine. They're being"
        echo "   replaced with the GitHub version; a copy was saved to:"
        echo "   $BACKUP_DIR/local-code-changes.patch"
    fi

    # Make the checkout match GitHub exactly.
    local before after
    before="$(git rev-parse --short HEAD)"
    if ! git reset --hard --quiet "origin/$BRANCH"; then
        echo "❌ Update failed. Restoring settings and restarting the current version."
        restore_live_files
        exit 1
    fi
    after="$(git rev-parse --short HEAD)"
    restore_live_files

    if [ "$before" = "$after" ]; then
        echo "Already up to date ($after)."
    else
        echo "Updated $before → $after:"
        git log --oneline "$before..$after" | sed 's/^/   /'
    fi

    echo "Updating Python dependencies..."
    if [ -f "$VENV_DIR/bin/pip" ]; then
        "$VENV_DIR/bin/pip" install --upgrade pip --quiet || true
        "$VENV_DIR/bin/pip" install -r backend/requirements.txt --quiet \
            || echo "⚠️  Dependency install had errors (see above)."
    else
        echo "⚠️  No virtualenv at $VENV_DIR; skipping."
    fi

    install_wrapper

    # Keep only the 10 most recent backups.
    ls -1dt "$HOME/.ez-redirect-backups"/*/ 2>/dev/null | tail -n +11 | xargs rm -rf 2>/dev/null || true

    echo ""
    echo "✅ ez-redirect updated to $after. Settings backup: $BACKUP_DIR"
}

restore_live_files() {
    local f
    for f in "${LIVE_FILES[@]}"; do
        [ -f "$BACKUP_DIR/$(basename "$f")" ] && cp "$BACKUP_DIR/$(basename "$f")" "$f"
    done
}

start_services() {
    echo "Starting services..."
    launchctl load "$SERVICE_PLIST" 2>/dev/null || true
    sleep 2
    launchctl load "$TRAY_PLIST" 2>/dev/null || true
}

# Older installs have a full copy of the update logic in /usr/local/bin.
# Replace it with the wrapper so future updates always use this file.
install_wrapper() {
    local want
    want="$(cat <<EOF
#!/bin/bash
# Runs the updater that ships with ez-redirect (see scripts/ez-update.sh).
exec /bin/bash "$INSTALL_DIR/scripts/ez-update.sh" "\$@"
EOF
)"
    if [ "$(cat "$WRAPPER" 2>/dev/null)" = "$want" ]; then
        return
    fi
    echo "Installing new ez-update command (one-time; may ask for your password)..."
    if printf '%s\n' "$want" > "$WRAPPER" 2>/dev/null \
        || printf '%s\n' "$want" | sudo tee "$WRAPPER" > /dev/null; then
        chmod +x "$WRAPPER" 2>/dev/null || sudo chmod +x "$WRAPPER"
    else
        echo "⚠️  Couldn't update $WRAPPER; the update itself still succeeded."
    fi
}

main "$@"
exit $?
