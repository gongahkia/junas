#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${KAYPOH_CODESIGN_IDENTITY:=}"
: "${KAYPOH_NOTARYTOOL_PROFILE:=}"
: "${KAYPOH_PACKAGE_OUTPUT:=dist/kaypoh-local-macos.zip}"
SPEC="$ROOT/packaging/kaypoh-local.spec"

uv run pyinstaller "$SPEC"

if [[ -n "$KAYPOH_CODESIGN_IDENTITY" ]]; then
  /usr/bin/codesign --force --timestamp --options runtime --sign "$KAYPOH_CODESIGN_IDENTITY" dist/kaypoh-local/kaypoh-local
  /usr/bin/codesign --verify --strict --deep dist/kaypoh-local/kaypoh-local
fi

/usr/bin/ditto -c -k --keepParent dist/kaypoh-local "$KAYPOH_PACKAGE_OUTPUT"

if [[ -n "$KAYPOH_NOTARYTOOL_PROFILE" ]]; then
  /usr/bin/xcrun notarytool submit "$KAYPOH_PACKAGE_OUTPUT" --keychain-profile "$KAYPOH_NOTARYTOOL_PROFILE" --wait
  /usr/bin/xcrun stapler staple "$KAYPOH_PACKAGE_OUTPUT" || true
fi
