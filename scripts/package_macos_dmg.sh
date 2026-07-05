#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${JUNAS_CODESIGN_IDENTITY:=}"
: "${JUNAS_NOTARYTOOL_PROFILE:=}"
: "${JUNAS_RELEASE_SIGNING_REQUIRED:=0}"
: "${JUNAS_DMG_OUTPUT:=dist/JunasMenuBar.dmg}"

CHECK_CONFIG_ONLY=0
if [[ "${1:-}" == "--check-config" ]]; then
  CHECK_CONFIG_ONLY=1
fi

fail_release_config() {
  echo "$1" >&2
  exit 78
}

case "$JUNAS_RELEASE_SIGNING_REQUIRED" in
  0|1) ;;
  *) fail_release_config "JUNAS_RELEASE_SIGNING_REQUIRED must be 0 or 1" ;;
esac

if [[ "$JUNAS_RELEASE_SIGNING_REQUIRED" == "1" ]]; then
  if [[ -z "$JUNAS_CODESIGN_IDENTITY" ]]; then
    fail_release_config "JUNAS_CODESIGN_IDENTITY is required when JUNAS_RELEASE_SIGNING_REQUIRED=1"
  fi
  if [[ -z "$JUNAS_NOTARYTOOL_PROFILE" ]]; then
    fail_release_config "JUNAS_NOTARYTOOL_PROFILE is required when JUNAS_RELEASE_SIGNING_REQUIRED=1"
  fi
fi

if [[ -n "$JUNAS_NOTARYTOOL_PROFILE" && -z "$JUNAS_CODESIGN_IDENTITY" ]]; then
  fail_release_config "JUNAS_CODESIGN_IDENTITY is required when JUNAS_NOTARYTOOL_PROFILE is set"
fi

if [[ -n "$JUNAS_CODESIGN_IDENTITY" ]]; then
  if ! /usr/bin/security find-identity -v -p codesigning | /usr/bin/grep -F "$JUNAS_CODESIGN_IDENTITY" >/dev/null; then
    fail_release_config "configured codesign identity was not found in the keychain"
  fi
fi

if [[ "$CHECK_CONFIG_ONLY" == "1" ]]; then
  exit 0
fi

APP_BUNDLE="$ROOT/dist/JunasMenuBar.app"
SIDECAR_BUILD="$ROOT/dist/junas-sidecar"
SIDECAR_DEST="$APP_BUNDLE/Contents/Resources/junas-sidecar"
DMG_OUTPUT="$ROOT/$JUNAS_DMG_OUTPUT"
DMG_PARENT="$(dirname "$DMG_OUTPUT")"

./script/build_and_run.sh --bundle-only
uv run pyinstaller packaging/junas-sidecar.spec

rm -rf "$SIDECAR_DEST"
mkdir -p "$(dirname "$SIDECAR_DEST")"
cp -R "$SIDECAR_BUILD" "$SIDECAR_DEST"

if [[ -n "$JUNAS_CODESIGN_IDENTITY" ]]; then
  /usr/bin/codesign --force --timestamp --options runtime --sign "$JUNAS_CODESIGN_IDENTITY" "$SIDECAR_DEST/junas-sidecar"
  /usr/bin/codesign --force --timestamp --options runtime --deep --sign "$JUNAS_CODESIGN_IDENTITY" "$APP_BUNDLE"
  /usr/bin/codesign --verify --strict --deep "$APP_BUNDLE"
fi

mkdir -p "$DMG_PARENT"
STAGING_DIR="$(mktemp -d -t junas-dmg.XXXXXX)"
trap 'rm -rf "$STAGING_DIR"' EXIT
cp -R "$APP_BUNDLE" "$STAGING_DIR/JunasMenuBar.app"
ln -s /Applications "$STAGING_DIR/Applications"
/usr/bin/hdiutil create -volname "Junas" -srcfolder "$STAGING_DIR" -ov -format UDZO "$DMG_OUTPUT"

if [[ -n "$JUNAS_CODESIGN_IDENTITY" ]]; then
  /usr/bin/codesign --force --timestamp --sign "$JUNAS_CODESIGN_IDENTITY" "$DMG_OUTPUT"
  /usr/bin/codesign --verify "$DMG_OUTPUT"
fi

if [[ -n "$JUNAS_NOTARYTOOL_PROFILE" ]]; then
  /usr/bin/xcrun notarytool submit "$DMG_OUTPUT" --keychain-profile "$JUNAS_NOTARYTOOL_PROFILE" --wait
  /usr/bin/xcrun stapler staple "$DMG_OUTPUT"
  /usr/sbin/spctl -a -t open --context context:primary-signature -v "$DMG_OUTPUT"
fi

shasum -a 256 "$DMG_OUTPUT"
