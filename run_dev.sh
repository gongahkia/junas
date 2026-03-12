#!/bin/bash

# Noupe Dev Bootstrapper
# Starts the FastAPI backend, optionally serves the legacy analyzer frontend,
# and opens the selected frontend(s) only after backend readiness.

ROOT="$(cd "$(dirname "$0")" && pwd)"
export NOUPE_FAIL_ON_LAYER_LOAD_ERROR="${NOUPE_FAIL_ON_LAYER_LOAD_ERROR:-1}"
NOUPE_HOST="${NOUPE_HOST:-0.0.0.0}"
NOUPE_PORT="${NOUPE_PORT:-8000}"
NOUPE_OLD_FRONTEND_PORT="${NOUPE_OLD_FRONTEND_PORT:-8081}"
NOUPE_READY_TIMEOUT_SECONDS="${NOUPE_READY_TIMEOUT_SECONDS:-180}"
PIPELINE_LAYERS_NORMALIZED="$(printf '%s' "${PIPELINE_LAYERS:-}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"

BACKEND_PID=""
LEGACY_FRONTEND_PID=""
PIDS=()
FRONTEND_SELECTION=""
BACKEND_URL="http://localhost:${NOUPE_PORT}"
LEGACY_FRONTEND_URL="http://localhost:${NOUPE_OLD_FRONTEND_PORT}/"
CHAT_FRONTEND_URL="${BACKEND_URL}/chat/"

echo "🚀 Starting Noupe development services..."

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM

    if [ -n "${LEGACY_FRONTEND_PID}" ]; then
        kill "${LEGACY_FRONTEND_PID}" >/dev/null 2>&1 || true
    fi

    if [ -n "${BACKEND_PID}" ]; then
        kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    fi

    if [ $exit_code -ne 0 ]; then
        echo ""
        echo "🛑 Services stopped."
    else
        echo ""
        echo "🛑 Services stopped."
    fi

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
    local ready_url="http://127.0.0.1:${NOUPE_PORT}/ready"

    echo "⏳ Waiting for backend readiness at ${ready_url}..."

    python3 - "${BACKEND_PID}" "${NOUPE_PORT}" "${NOUPE_READY_TIMEOUT_SECONDS}" <<'PY'
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
        FRONTEND_SELECTION="both"
        return
    fi

    echo ""
    echo "Which frontend(s) should open after the backend is ready?"
    echo "  1) Legacy analyzer only (${LEGACY_FRONTEND_URL})"
    echo "  2) Chat demo only (${CHAT_FRONTEND_URL})"
    echo "  3) Both frontends"
    echo "  4) Backend only (do not open a frontend)"
    printf "Selection [3]: "
    read -r selection

    case "${selection:-3}" in
        1) FRONTEND_SELECTION="legacy" ;;
        2) FRONTEND_SELECTION="chat" ;;
        3) FRONTEND_SELECTION="both" ;;
        4) FRONTEND_SELECTION="none" ;;
        legacy|chat|both|none) FRONTEND_SELECTION="${selection}" ;;
        *)
            echo "⚠️  Unrecognized selection. Defaulting to both frontends."
            FRONTEND_SELECTION="both"
            ;;
    esac
}

start_legacy_frontend_server() {
    echo "🌐 Starting legacy analyzer frontend on ${LEGACY_FRONTEND_URL}..."
    python3 -m http.server "${NOUPE_OLD_FRONTEND_PORT}" -d "${ROOT}/frontend" >/dev/null 2>&1 &
    LEGACY_FRONTEND_PID=$!
    wait_for_url "http://127.0.0.1:${NOUPE_OLD_FRONTEND_PORT}/" "${LEGACY_FRONTEND_PID}" 30
}

prompt_frontends

echo ""
echo "Frontend selection: ${FRONTEND_SELECTION}"

# ── Activate project venv if present ──
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "${ROOT}/.venv/bin/activate" ]; then
    echo "🐍 Activating .venv..."
    # shellcheck source=/dev/null
    source "${ROOT}/.venv/bin/activate"
fi

# ── Preflight checks ──
echo "🧪 Running preflight checks..."
if [ "${NOUPE_PREFLIGHT_STRICT:-1}" = "1" ]; then
    python3 "${ROOT}/scripts/preflight.py" --strict
else
    python3 "${ROOT}/scripts/preflight.py" || true
fi

# --- Preflight: checkpoint validation ---
MISSING=0

check_file() {
    if [ ! -f "$1" ]; then
        echo "⚠️  Missing: $1"
        MISSING=$((MISSING + 1))
    fi
}

check_dir_has_model() {
    local dir="$1"
    local name="$2"
    if [ ! -d "$dir" ]; then
        echo "⚠️  Missing checkpoint dir for ${name}: ${dir}"
        MISSING=$((MISSING + 1))
        return
    fi
    for ext in safetensors bin pt ckpt; do
        if ls "$dir"/*."$ext" 1>/dev/null 2>&1; then
            return 0
        fi
    done
    echo "⚠️  No model weights in ${dir} for ${name} (need .safetensors/.bin/.pt/.ckpt)"
    MISSING=$((MISSING + 1))
}

pipeline_has_layer() {
    local layer="$1"
    if [ -z "${PIPELINE_LAYERS_NORMALIZED}" ]; then
        return 0
    fi

    case ",${PIPELINE_LAYERS_NORMALIZED}," in
        *,"${layer}",*) return 0 ;;
        *) return 1 ;;
    esac
}

if pipeline_has_layer "clustering"; then
    check_file "${ROOT}/layer3-clustering/checkpoints/anomaly_detector.joblib"
fi

if pipeline_has_layer "model1"; then
    check_dir_has_model "${ROOT}/layer4-classification/model-1/checkpoints/best" "model1"
fi

if pipeline_has_layer "model2"; then
    check_dir_has_model "${ROOT}/layer4-classification/model-2/checkpoints/best" "model2"
fi

if pipeline_has_layer "regression"; then
    if [ ! -f "${ROOT}/layer6-regression/checkpoints/risk_regressor.json" ] || [ ! -f "${ROOT}/layer6-regression/checkpoints/metadata.json" ]; then
        echo "ℹ️  Optional regression checkpoint missing. Startup will continue without the regression layer."
    fi
fi

if [ "$MISSING" -gt 0 ]; then
    echo ""
    echo "────────────────────────────────────────────────────"
    echo "  ${MISSING} checkpoint(s) missing."
    echo "  Train models first or download pre-trained weights."
    echo "  Startup is blocked to avoid degraded runtime."
    echo "────────────────────────────────────────────────────"
    echo ""
    if [ "${NOUPE_ALLOW_PARTIAL_START:-0}" != "1" ]; then
        echo "Set NOUPE_ALLOW_PARTIAL_START=1 only if you intentionally want degraded startup."
        exit 1
    fi
    export NOUPE_FAIL_ON_LAYER_LOAD_ERROR="${NOUPE_FAIL_ON_LAYER_LOAD_ERROR:-0}"
fi

echo "📦 Booting FastAPI backend on ${BACKEND_URL}..."
python3 -m uvicorn backend.main:app --host "${NOUPE_HOST}" --port "${NOUPE_PORT}" &
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
        echo "ℹ️  Backend is ready. No frontend opened."
        ;;
    *)
        echo "⚠️  Unknown frontend selection '${FRONTEND_SELECTION}'. No frontend opened."
        ;;
esac

echo "✅ Services are running."
echo "   Backend: ${BACKEND_URL}"
if [ -n "${LEGACY_FRONTEND_PID}" ]; then
    echo "   Legacy analyzer: ${LEGACY_FRONTEND_URL}"
fi
if [ "${FRONTEND_SELECTION}" = "chat" ] || [ "${FRONTEND_SELECTION}" = "both" ]; then
    echo "   Chat demo: ${CHAT_FRONTEND_URL}"
fi
echo "Press Ctrl+C to stop everything."

wait "${BACKEND_PID}"
