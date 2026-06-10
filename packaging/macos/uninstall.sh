#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${KAYPOH_INSTALL_DIR:-$HOME/Applications/kaypoh-local}"
PLIST="$HOME/Library/LaunchAgents/com.kaypoh.local.plist"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
rm -rf "$INSTALL_DIR"
