#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${KAYPOH_EXTENSION_SRC:-$ROOT/integrations/browser_extension}"
OUT_DIR="${KAYPOH_EXTENSION_OUT_DIR:-$ROOT/dist/browser-extension}"
ZIP_PATH="$OUT_DIR/kaypoh-local-review.zip"

if [[ ! -f "$SRC/manifest.json" ]]; then
  echo "missing browser extension source: $SRC/manifest.json" >&2
  exit 64
fi

mkdir -p "$OUT_DIR"
rm -f "$ZIP_PATH"
(cd "$SRC" && /usr/bin/zip -X -r "$ZIP_PATH" .)

if [[ -n "${KAYPOH_CHROME_EXTENSION_KEY:-}" ]]; then
  CHROME_BIN="${KAYPOH_CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
  "$CHROME_BIN" --pack-extension="$SRC" --pack-extension-key="$KAYPOH_CHROME_EXTENSION_KEY"
  mv "$ROOT/integrations/browser_extension.crx" "$OUT_DIR/kaypoh-local-review.crx"
fi

echo "$ZIP_PATH"
