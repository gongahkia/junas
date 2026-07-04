#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${JUNAS_CODESIGN_IDENTITY:=}"
: "${JUNAS_NOTARYTOOL_PROFILE:=}"
: "${JUNAS_PACKAGE_OUTPUT:=dist/junas-local-macos.zip}"
: "${JUNAS_RELEASE_SIGNING_REQUIRED:=0}"
SPEC="$ROOT/packaging/junas-local.spec"
DESKTOP_SRC="${JUNAS_DESKTOP_SRC:-$ROOT/integrations/desktop}"

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

if [[ ! -f "$DESKTOP_SRC/watch.py" ]]; then
  echo "missing desktop adapter source: $DESKTOP_SRC/watch.py" >&2
  exit 64
fi

if [[ ! -f "$SPEC" ]]; then
  echo "missing PyInstaller spec: $SPEC" >&2
  exit 64
fi

uv run pyinstaller "$SPEC"

if [[ -n "$JUNAS_CODESIGN_IDENTITY" ]]; then
  /usr/bin/codesign --force --timestamp --options runtime --sign "$JUNAS_CODESIGN_IDENTITY" dist/junas-local/junas-local
  /usr/bin/codesign --verify --strict --deep dist/junas-local/junas-local
fi

/usr/bin/ditto -c -k --keepParent dist/junas-local "$JUNAS_PACKAGE_OUTPUT"

if [[ -n "$JUNAS_NOTARYTOOL_PROFILE" ]]; then
  /usr/bin/xcrun notarytool submit "$JUNAS_PACKAGE_OUTPUT" --keychain-profile "$JUNAS_NOTARYTOOL_PROFILE" --wait
  /usr/bin/xcrun stapler staple "$JUNAS_PACKAGE_OUTPUT" || true
fi
