#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: verify_macos_dmg_release.sh <signed-notarized-dmg>

Environment:
  JUNAS_VERIFY_INSTALL_DIR       install directory; default /Applications
  JUNAS_VERIFY_OVERWRITE=1       replace an existing JunasMenuBar.app
  JUNAS_VERIFY_OPEN=1            open the installed app after Gatekeeper checks
  JUNAS_VERIFY_CLEANUP=1         remove the installed app after verification
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage
  exit 64
fi

DMG="$1"
INSTALL_DIR="${JUNAS_VERIFY_INSTALL_DIR:-/Applications}"
APP_DEST="$INSTALL_DIR/JunasMenuBar.app"
MOUNT_DIR="$(mktemp -d -t junas-dmg-mount.XXXXXX)"

if [[ ! -f "$DMG" ]]; then
  printf 'DMG not found: %s\n' "$DMG" >&2
  exit 66
fi

cleanup() {
  hdiutil detach "$MOUNT_DIR" >/dev/null 2>&1 || true
  rmdir "$MOUNT_DIR" >/dev/null 2>&1 || true
}
trap cleanup EXIT

shasum -a 256 "$DMG"
spctl -a -t open --context context:primary-signature -v "$DMG"
hdiutil attach "$DMG" -nobrowse -mountpoint "$MOUNT_DIR"

if [[ ! -d "$MOUNT_DIR/JunasMenuBar.app" ]]; then
  printf 'JunasMenuBar.app missing from mounted DMG\n' >&2
  exit 70
fi

if [[ -e "$APP_DEST" ]]; then
  if [[ "${JUNAS_VERIFY_OVERWRITE:-0}" != "1" ]]; then
    printf 'install target already exists; set JUNAS_VERIFY_OVERWRITE=1 to replace: %s\n' "$APP_DEST" >&2
    exit 73
  fi
  rm -rf "$APP_DEST"
fi

mkdir -p "$INSTALL_DIR"
cp -R "$MOUNT_DIR/JunasMenuBar.app" "$APP_DEST"
test -x "$APP_DEST/Contents/Resources/aki-sidecar/aki-sidecar"
spctl -a -t exec -vv "$APP_DEST"

if [[ "${JUNAS_VERIFY_OPEN:-0}" == "1" ]]; then
  open "$APP_DEST"
  printf 'manual_check_required: menu-bar app opened; verify start/pause/stop controls and Open TUI\n'
fi

if [[ "${JUNAS_VERIFY_CLEANUP:-0}" == "1" ]]; then
  rm -rf "$APP_DEST"
fi

printf 'macos_dmg_release_verified: true | dmg: %s | app: %s\n' "$DMG" "$APP_DEST"
