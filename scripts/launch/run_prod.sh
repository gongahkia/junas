#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

HOST="${JUNAS_HOST:-0.0.0.0}"
PORT="${JUNAS_PORT:-8000}"
WORKERS="${JUNAS_UVICORN_WORKERS:-2}"
LOG_LEVEL="${JUNAS_LOG_LEVEL:-info}"

export JUNAS_FAIL_ON_LAYER_LOAD_ERROR=1
export JUNAS_LAZY_LOAD_HEAVY="${JUNAS_LAZY_LOAD_HEAVY:-0}"
export JUNAS_RESPONSE_CACHE_SIZE="${JUNAS_RESPONSE_CACHE_SIZE:-0}"
PROM_DIR="${PROMETHEUS_MULTIPROC_DIR:-$ROOT/.prometheus-multiproc}"
export PROMETHEUS_MULTIPROC_DIR="$PROM_DIR"

trap cleanup_services EXIT INT TERM

echo "Starting Junas production backend..."

echo "Running strict preflight checks..."
python_cmd "${ROOT}/scripts/preflight.py" --strict --deployment production

rm -rf "${PROM_DIR}"
mkdir -p "${PROM_DIR}"

echo "Booting production backend on ${BACKEND_URL}..."
uvicorn_cmd junas.backend.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WORKERS}" \
    --log-level "${LOG_LEVEL}" &
BACKEND_PID=$!

wait_for_backend_ready
emit_launch_telemetry_report "prod" || true

echo "Production backend is running."
echo "   Backend: ${BACKEND_URL}"
echo "Press Ctrl+C to stop everything."

wait "${BACKEND_PID}"
