#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

HOST="${KAYPOH_HOST:-0.0.0.0}"
PORT="${KAYPOH_PORT:-8000}"
LOG_LEVEL="${KAYPOH_LOG_LEVEL:-info}"

export KAYPOH_FAIL_ON_LAYER_LOAD_ERROR="${KAYPOH_FAIL_ON_LAYER_LOAD_ERROR:-1}"
export KAYPOH_RELOAD="${KAYPOH_RELOAD:-1}"

trap cleanup_services EXIT INT TERM

echo "Starting Kaypoh development backend..."
echo "Active pipeline: ${PIPELINE_LAYERS:-deterministic engine only}"

echo "Running preflight checks..."
run_preflight

echo "Booting FastAPI backend on ${BACKEND_URL}..."
uvicorn_cmd backend.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --log-level "${LOG_LEVEL}" \
    --reload &
BACKEND_PID=$!

wait_for_backend_ready
emit_launch_telemetry_report "dev" || true

echo "Development backend is running."
echo "   Backend: ${BACKEND_URL}"
echo "Press Ctrl+C to stop."

wait "${BACKEND_PID}"
