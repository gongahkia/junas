#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${JUNAS_CODESIGN_IDENTITY:=}"
: "${JUNAS_NOTARYTOOL_PROFILE:=}"
: "${JUNAS_PACKAGE_OUTPUT:=dist/junas-local-macos.zip}"
SPEC="$ROOT/packaging/junas-local.spec"
DESKTOP_SRC="${JUNAS_DESKTOP_SRC:-$ROOT/integrations/desktop}"

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
