#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL_DIR="${KAYPOH_INSTALL_DIR:-$HOME/Applications/kaypoh-local}"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/Kaypoh"
PLIST="$LAUNCH_DIR/com.kaypoh.local.plist"

mkdir -p "$INSTALL_DIR" "$LAUNCH_DIR" "$LOG_DIR"
rsync -a --delete "$ROOT/dist/kaypoh-local/" "$INSTALL_DIR/"
sed -e "s#__INSTALL_DIR__#$INSTALL_DIR#g" -e "s#__LOG_DIR__#$LOG_DIR#g" \
  "$ROOT/packaging/macos/com.kaypoh.local.plist.template" > "$PLIST"
chmod 0644 "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/com.kaypoh.local"
