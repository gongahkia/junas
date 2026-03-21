#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

HOST="${NOUPE_HOST:-0.0.0.0}"
PORT="${NOUPE_PORT:-8000}"
LOG_LEVEL="${NOUPE_LOG_LEVEL:-info}"
RELOAD="${NOUPE_RELOAD:-0}"

export NOUPE_FAIL_ON_LAYER_LOAD_ERROR="${NOUPE_FAIL_ON_LAYER_LOAD_ERROR:-1}"

activate_venv

echo "🧪 Running backend-only preflight checks..."
if [ "${NOUPE_PREFLIGHT_STRICT:-1}" = "1" ]; then
    python3 "${ROOT}/scripts/preflight.py" --strict
else
    python3 "${ROOT}/scripts/preflight.py" || true
fi

echo "📦 Starting backend only on ${BACKEND_URL}..."
if [ "${RELOAD}" = "1" ]; then
    exec python3 -m uvicorn backend.main:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --log-level "${LOG_LEVEL}" \
        --reload
fi

exec python3 -m uvicorn backend.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --log-level "${LOG_LEVEL}"
