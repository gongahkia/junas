#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[sayless] Installing frontend dependencies..."
(cd "$ROOT_DIR/frontend" && npm install)

if command -v mix >/dev/null 2>&1; then
  echo "[sayless] Fetching backend dependencies..."
  (cd "$ROOT_DIR/backend" && mix deps.get)
else
  echo "[sayless] Skipping backend dependency setup because mix is not installed."
fi
