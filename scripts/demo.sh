#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "${JUNAS_DEMO_PORT:-}" ]; then
    JUNAS_DEMO_PORT="$(python3 - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
fi

BASE_URL="http://127.0.0.1:${JUNAS_DEMO_PORT}"
LOG_FILE="$(mktemp -t junas-demo.XXXXXX.log)"
BACKEND_PID=""

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    if [ -n "${BACKEND_PID}" ]; then
        kill "${BACKEND_PID}" >/dev/null 2>&1 || true
        wait "${BACKEND_PID}" 2>/dev/null || true
    fi
    if [ "${exit_code}" -ne 0 ]; then
        echo "backend log: ${LOG_FILE}" >&2
        tail -120 "${LOG_FILE}" >&2 || true
    else
        rm -f "${LOG_FILE}"
    fi
    exit "${exit_code}"
}

python_cmd() {
    if command -v uv >/dev/null 2>&1; then
        (cd "${ROOT}" && uv run python "$@")
    else
        PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}" python3 "$@"
    fi
}

uvicorn_cmd() {
    if command -v uv >/dev/null 2>&1; then
        (cd "${ROOT}" && uv run uvicorn "$@")
    else
        PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}" python3 -m uvicorn "$@"
    fi
}

trap cleanup EXIT INT TERM

export JUNAS_HOST="127.0.0.1"
export JUNAS_PORT="${JUNAS_DEMO_PORT}"
export PIPELINE_LAYERS=""
export JUNAS_PUBLIC_EVIDENCE_ENABLED="0"
export JUNAS_PUBLIC_EVIDENCE_PROVIDER="none"
export JUNAS_LLM_ENABLED="0"
export JUNAS_LLM_PROVIDER="none"
export JUNAS_LLM_HELPERS_ENABLED="0"
export JUNAS_LLM_DEFINED_TERMS_ENABLED="0"
export JUNAS_LLM_COVERAGE_AUDIT_ENABLED="0"
export JUNAS_IMAGE_SCAN_PROVIDER="none"
export JUNAS_REVIEW_PERSIST="0"
export JUNAS_TENANCY_ENABLED="0"
unset JUNAS_API_KEY

echo "Starting Junas deterministic demo backend at ${BASE_URL}"
uvicorn_cmd junas.backend.main:app --host 127.0.0.1 --port "${JUNAS_DEMO_PORT}" --log-level warning >"${LOG_FILE}" 2>&1 &
BACKEND_PID=$!

python_cmd "${ROOT}/scripts/demo.py" --base-url "${BASE_URL}"
