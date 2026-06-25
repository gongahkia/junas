#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${JUNAS_INSTALL_DIR:-$HOME/Applications/junas-local}"
PLIST="$HOME/Library/LaunchAgents/com.junas.local.plist"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
rm -rf "$INSTALL_DIR"
