#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[sayless] Missing required command: $1"
    exit 1
  fi
}

require_command npm

if ! command -v mix >/dev/null 2>&1; then
  echo "[sayless] mix is not installed, so the backend cannot be started locally."
  echo "[sayless] Run ./scripts/bootstrap.sh after installing Elixir/Mix."
  exit 1
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "[sayless] Missing backend/.env with GEMINI_API_KEY and TMDB_API_KEY."
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "[sayless] Frontend dependencies are missing. Run ./scripts/bootstrap.sh first."
  exit 1
fi

echo "[sayless] Starting Phoenix backend..."
(cd "$BACKEND_DIR" && mix phx.server) &
BACKEND_PID=$!

echo "[sayless] Starting Next.js frontend..."
(cd "$FRONTEND_DIR" && npm run dev) &
FRONTEND_PID=$!

cleanup() {
  echo "[sayless] Stopping dev servers..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup SIGINT SIGTERM EXIT

echo "[sayless] Backend PID: $BACKEND_PID"
echo "[sayless] Frontend PID: $FRONTEND_PID"
wait
