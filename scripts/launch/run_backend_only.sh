#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

HOST="${NOUPE_HOST:-0.0.0.0}"
PORT="${NOUPE_PORT:-8000}"
LOG_LEVEL="${NOUPE_LOG_LEVEL:-info}"
RELOAD="${NOUPE_RELOAD:-0}"
FRONTEND_SELECTION="none"

export NOUPE_FAIL_ON_LAYER_LOAD_ERROR="${NOUPE_FAIL_ON_LAYER_LOAD_ERROR:-1}"

trap cleanup_services EXIT INT TERM

activate_venv

echo "🧪 Running backend-only preflight checks..."
if [ "${NOUPE_PREFLIGHT_STRICT:-1}" = "1" ]; then
    python3 "${ROOT}/scripts/preflight.py" --strict
else
    python3 "${ROOT}/scripts/preflight.py" || true
fi

echo "📦 Starting backend only on ${BACKEND_URL}..."
if [ "${RELOAD}" = "1" ]; then
    python3 -m uvicorn backend.main:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --log-level "${LOG_LEVEL}" \
        --reload &
else
    python3 -m uvicorn backend.main:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --log-level "${LOG_LEVEL}" &
fi

BACKEND_PID=$!
wait_for_backend_ready
emit_launch_telemetry_report "none" || true

echo "✅ Backend-only service is running."
echo "   Backend: ${BACKEND_URL}"
echo "Press Ctrl+C to stop."

wait "${BACKEND_PID}"
