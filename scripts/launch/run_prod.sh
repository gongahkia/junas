#!/bin/bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/common.sh"

HOST="${NOUPE_HOST:-0.0.0.0}"
PORT="${NOUPE_PORT:-8000}"
WORKERS="${NOUPE_UVICORN_WORKERS:-2}"
LOG_LEVEL="${NOUPE_LOG_LEVEL:-info}"

export NOUPE_FAIL_ON_LAYER_LOAD_ERROR=1
export NOUPE_LAZY_LOAD_HEAVY="${NOUPE_LAZY_LOAD_HEAVY:-0}"
PROM_DIR="${PROMETHEUS_MULTIPROC_DIR:-$ROOT/.prometheus-multiproc}"
export PROMETHEUS_MULTIPROC_DIR="$PROM_DIR"

trap cleanup_services EXIT INT TERM

echo "🚀 Starting Noupe production services..."

prompt_frontends "none"

echo ""
echo "Frontend selection: ${FRONTEND_SELECTION}"

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

if selection_requires_demo_server; then
    start_demo_server
    open_selected_frontends
else
    echo "ℹ️  Production backend is ready. No frontend opened."
fi

echo "✅ Production services are running."
echo "   Backend: ${BACKEND_URL}"
print_selected_frontends
echo "Press Ctrl+C to stop everything."

wait "${BACKEND_PID}"
