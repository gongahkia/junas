#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

HOST="${KAYPOH_HOST:-0.0.0.0}"
PORT="${KAYPOH_PORT:-8000}"
WORKERS="${KAYPOH_UVICORN_WORKERS:-2}"
LOG_LEVEL="${KAYPOH_LOG_LEVEL:-info}"

export KAYPOH_FAIL_ON_LAYER_LOAD_ERROR=1
export KAYPOH_LAZY_LOAD_HEAVY="${KAYPOH_LAZY_LOAD_HEAVY:-0}"
export KAYPOH_RESPONSE_CACHE_SIZE="${KAYPOH_RESPONSE_CACHE_SIZE:-0}"
PROM_DIR="${PROMETHEUS_MULTIPROC_DIR:-$ROOT/.prometheus-multiproc}"
export PROMETHEUS_MULTIPROC_DIR="$PROM_DIR"

trap cleanup_services EXIT INT TERM

echo "🚀 Starting Kaypoh production backend..."

activate_venv

echo "🧪 Running strict preflight checks..."
python3 "${ROOT}/scripts/preflight.py" --strict

rm -rf "${PROM_DIR}"
mkdir -p "${PROM_DIR}"

echo "📦 Booting production backend on ${BACKEND_URL}..."
python3 -m uvicorn backend.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WORKERS}" \
    --log-level "${LOG_LEVEL}" &
BACKEND_PID=$!

wait_for_backend_ready
emit_launch_telemetry_report "prod" || true

echo "✅ Production backend is running."
echo "   Backend: ${BACKEND_URL}"
echo "Press Ctrl+C to stop everything."

wait "${BACKEND_PID}"
