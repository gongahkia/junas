#!/bin/bash
set -euo pipefail

# Noupe Production Profile
# Multi-worker uvicorn launch with strict preflight and optional frontend launch.

ROOT="$(cd "$(dirname "$0")" && pwd)"

HOST="${NOUPE_HOST:-0.0.0.0}"
PORT="${NOUPE_PORT:-8000}"
WORKERS="${NOUPE_UVICORN_WORKERS:-2}"
LOG_LEVEL="${NOUPE_LOG_LEVEL:-info}"
OLD_FRONTEND_PORT="${NOUPE_OLD_FRONTEND_PORT:-8081}"
READY_TIMEOUT_SECONDS="${NOUPE_READY_TIMEOUT_SECONDS:-180}"

BACKEND_PID=""
LEGACY_FRONTEND_PID=""
FRONTEND_SELECTION=""
BACKEND_URL="http://localhost:${PORT}"
CHAT_FRONTEND_URL="${BACKEND_URL}/chat/"
LEGACY_FRONTEND_URL="http://localhost:${OLD_FRONTEND_PORT}/"

export NOUPE_FAIL_ON_LAYER_LOAD_ERROR=1
export NOUPE_LAZY_LOAD_HEAVY="${NOUPE_LAZY_LOAD_HEAVY:-0}"
PROM_DIR="${PROMETHEUS_MULTIPROC_DIR:-$ROOT/.prometheus-multiproc}"
export PROMETHEUS_MULTIPROC_DIR="$PROM_DIR"

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM

    if [ -n "${LEGACY_FRONTEND_PID}" ]; then
        kill "${LEGACY_FRONTEND_PID}" >/dev/null 2>&1 || true
    fi

    if [ -n "${BACKEND_PID}" ]; then
        kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    fi

    echo ""
    echo "🛑 Production services stopped."
    exit "$exit_code"
}

trap cleanup EXIT INT TERM

open_url() {
    local url="$1"
    if command -v open >/dev/null 2>&1; then
        open "$url"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    else
        echo "ℹ️  Could not auto-open browser. Open this manually:"
        echo "   ${url}"
    fi
}

wait_for_url() {
    local url="$1"
    local pid="$2"
    local timeout="$3"

    python3 - "$url" "$pid" "$timeout" <<'PY'
import os
import sys
import time
import urllib.request

url = sys.argv[1]
pid = int(sys.argv[2])
timeout = int(sys.argv[3])
deadline = time.time() + timeout

while time.time() < deadline:
    try:
        os.kill(pid, 0)
    except OSError:
        sys.stderr.write(f"process {pid} exited before {url} became reachable\n")
        sys.exit(2)

    try:
        with urllib.request.urlopen(url, timeout=2):
            sys.exit(0)
    except Exception:
        time.sleep(1)

sys.stderr.write(f"timed out waiting for {url}\n")
sys.exit(1)
PY
}

wait_for_backend_ready() {
    local ready_url="http://127.0.0.1:${PORT}/ready"

    echo "⏳ Waiting for backend readiness at ${ready_url}..."

    python3 - "${BACKEND_PID}" "${PORT}" "${READY_TIMEOUT_SECONDS}" <<'PY'
import json
import os
import sys
import time
import urllib.request

pid = int(sys.argv[1])
port = int(sys.argv[2])
timeout = int(sys.argv[3])
url = f"http://127.0.0.1:{port}/ready"
deadline = time.time() + timeout
last_message = None

def alive(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
        return True
    except OSError:
        return False

while time.time() < deadline:
    if not alive(pid):
        sys.stderr.write("backend process exited before becoming ready\n")
        sys.exit(2)

    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.load(response)
    except Exception:
        time.sleep(2)
        continue

    if payload.get("ready") is True:
        print("✅ Backend is ready.")
        sys.exit(0)

    parts = [f"status={payload.get('status', 'unknown')}"]
    warming = payload.get("warming_required_layers") or []
    missing = payload.get("missing_required_layers") or []
    reasons = payload.get("reasons") or []

    if warming:
        parts.append(f"warming={', '.join(warming)}")
    if missing:
        parts.append(f"missing={', '.join(missing)}")
    if reasons:
        parts.append(f"reasons={'; '.join(reasons)}")

    message = " | ".join(parts)
    if message != last_message:
        print(f"   {message}")
        last_message = message

    time.sleep(2)

sys.stderr.write(f"timed out waiting for backend readiness at {url}\n")
sys.exit(1)
PY
}

prompt_frontends() {
    if [ -n "${NOUPE_FRONTENDS:-}" ]; then
        FRONTEND_SELECTION="${NOUPE_FRONTENDS}"
        return
    fi

    if [ ! -t 0 ]; then
        FRONTEND_SELECTION="none"
        return
    fi

    echo ""
    echo "Which surface(s) should open after the production backend is ready?"
    echo "  1) Legacy analyzer only (${LEGACY_FRONTEND_URL})"
    echo "  2) Chat demo only (${CHAT_FRONTEND_URL})"
    echo "  3) Both frontends"
    echo "  4) Backend only (do not open a frontend)"
    printf "Selection [4]: "
    read -r selection

    case "${selection:-4}" in
        1) FRONTEND_SELECTION="legacy" ;;
        2) FRONTEND_SELECTION="chat" ;;
        3) FRONTEND_SELECTION="both" ;;
        4) FRONTEND_SELECTION="none" ;;
        legacy|chat|both|none) FRONTEND_SELECTION="${selection}" ;;
        *)
            echo "⚠️  Unrecognized selection. Defaulting to backend only."
            FRONTEND_SELECTION="none"
            ;;
    esac
}

start_legacy_frontend_server() {
    echo "🌐 Starting legacy analyzer frontend on ${LEGACY_FRONTEND_URL}..."
    python3 -m http.server "${OLD_FRONTEND_PORT}" -d "${ROOT}/frontend" >/dev/null 2>&1 &
    LEGACY_FRONTEND_PID=$!
    wait_for_url "http://127.0.0.1:${OLD_FRONTEND_PORT}/" "${LEGACY_FRONTEND_PID}" 30
}

echo "🚀 Starting Noupe production services..."

prompt_frontends

echo ""
echo "Frontend selection: ${FRONTEND_SELECTION}"

if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "$ROOT/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$ROOT/.venv/bin/activate"
fi

echo "🧪 Running strict preflight checks..."
python3 "$ROOT/scripts/preflight.py" --strict

rm -rf "$PROM_DIR"
mkdir -p "$PROM_DIR"

echo "📦 Booting production backend on ${BACKEND_URL}..."
python3 -m uvicorn backend.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "$LOG_LEVEL" &
BACKEND_PID=$!

wait_for_backend_ready

case "${FRONTEND_SELECTION}" in
    legacy)
        start_legacy_frontend_server
        echo "🌐 Opening legacy analyzer..."
        open_url "${LEGACY_FRONTEND_URL}"
        ;;
    chat)
        echo "🌐 Opening chat demo..."
        open_url "${CHAT_FRONTEND_URL}"
        ;;
    both)
        start_legacy_frontend_server
        echo "🌐 Opening legacy analyzer and chat demo..."
        open_url "${LEGACY_FRONTEND_URL}"
        open_url "${CHAT_FRONTEND_URL}"
        ;;
    none)
        echo "ℹ️  Production backend is ready. No frontend opened."
        ;;
    *)
        echo "⚠️  Unknown frontend selection '${FRONTEND_SELECTION}'. No frontend opened."
        ;;
esac

echo "✅ Production services are running."
echo "   Backend: ${BACKEND_URL}"
if [ -n "${LEGACY_FRONTEND_PID}" ]; then
    echo "   Legacy analyzer: ${LEGACY_FRONTEND_URL}"
fi
if [ "${FRONTEND_SELECTION}" = "chat" ] || [ "${FRONTEND_SELECTION}" = "both" ]; then
    echo "   Chat demo: ${CHAT_FRONTEND_URL}"
fi
echo "Press Ctrl+C to stop everything."

wait "${BACKEND_PID}"
