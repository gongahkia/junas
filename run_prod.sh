#!/bin/bash
set -euo pipefail

# Noupe Production Profile
# Multi-worker uvicorn launch without autoreload.

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "$ROOT/.venv/bin/activate" ]; then
    source "$ROOT/.venv/bin/activate"
fi

HOST="${NOUPE_HOST:-0.0.0.0}"
PORT="${NOUPE_PORT:-8000}"
WORKERS="${NOUPE_UVICORN_WORKERS:-2}"
LOG_LEVEL="${NOUPE_LOG_LEVEL:-info}"

if [ "${NOUPE_PREFLIGHT_STRICT:-1}" = "1" ]; then
    python3 "$ROOT/scripts/preflight.py" --strict
else
    python3 "$ROOT/scripts/preflight.py"
fi

exec python3 -m uvicorn backend.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "$LOG_LEVEL"
