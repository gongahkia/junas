#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

HOST="${KAYPOH_HOST:-0.0.0.0}"
PORT="${KAYPOH_PORT:-8000}"
LOG_LEVEL="${KAYPOH_LOG_LEVEL:-info}"
RELOAD="${KAYPOH_RELOAD:-0}"

export KAYPOH_FAIL_ON_LAYER_LOAD_ERROR="${KAYPOH_FAIL_ON_LAYER_LOAD_ERROR:-1}"

trap cleanup_services EXIT INT TERM

echo "Running backend-only preflight checks..."
run_preflight

echo "Starting backend only on ${BACKEND_URL}..."
if [ "${RELOAD}" = "1" ]; then
    uvicorn_cmd kaypoh.backend.main:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --log-level "${LOG_LEVEL}" \
        --reload &
else
    uvicorn_cmd kaypoh.backend.main:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --log-level "${LOG_LEVEL}" &
fi

BACKEND_PID=$!
wait_for_backend_ready
emit_launch_telemetry_report "none" || true

echo "Backend-only service is running."
echo "   Backend: ${BACKEND_URL}"
echo "Press Ctrl+C to stop."

wait "${BACKEND_PID}"
