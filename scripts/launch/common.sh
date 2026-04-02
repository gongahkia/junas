#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NOUPE_HOST="${NOUPE_HOST:-0.0.0.0}"
NOUPE_PORT="${NOUPE_PORT:-8000}"
NOUPE_READY_TIMEOUT_SECONDS="${NOUPE_READY_TIMEOUT_SECONDS:-180}"
NOUPE_FRONTEND_DEMO_PORT="${NOUPE_FRONTEND_DEMO_PORT:-${NOUPE_OLD_FRONTEND_PORT:-8081}}"

BACKEND_PID=""
DEMO_SERVER_PID=""
FRONTEND_SELECTION="${FRONTEND_SELECTION:-}"

BACKEND_URL="http://localhost:${NOUPE_PORT}"
DEMO_ROOT="${ROOT}/archive/frontend-demos"
DEMO_BASE_URL="http://localhost:${NOUPE_FRONTEND_DEMO_PORT}"
LEGACY_FRONTEND_URL="${DEMO_BASE_URL}/legacy/?api=${BACKEND_URL}"
CHAT_FRONTEND_URL="${DEMO_BASE_URL}/chat/?api=${BACKEND_URL}"
EMAIL_FRONTEND_URL="${DEMO_BASE_URL}/email/?api=${BACKEND_URL}"
SLACK_FRONTEND_URL="${DEMO_BASE_URL}/slack/?api=${BACKEND_URL}"

cleanup_services() {
    local exit_code=$?
    trap - EXIT INT TERM

    if [ -n "${DEMO_SERVER_PID}" ]; then
        kill "${DEMO_SERVER_PID}" >/dev/null 2>&1 || true
    fi

    if [ -n "${BACKEND_PID}" ]; then
        kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    fi

    echo ""
    echo "🛑 Services stopped."
    exit "${exit_code}"
}

open_url() {
    local url="$1"
    if [ "${NOUPE_NO_BROWSER:-0}" = "1" ]; then
        echo "ℹ️  Browser auto-open disabled. Open this manually if needed:"
        echo "   ${url}"
        return
    fi
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

activate_venv() {
    if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "${ROOT}/.venv/bin/activate" ]; then
        echo "🐍 Activating .venv..."
        # shellcheck source=/dev/null
        source "${ROOT}/.venv/bin/activate"
    fi
}

prompt_frontends() {
    local default_selection="$1"
    local default_numeric="5"

    if [ "${default_selection}" = "none" ]; then
        default_numeric="6"
    fi

    if [ -n "${NOUPE_FRONTENDS:-}" ]; then
        FRONTEND_SELECTION="${NOUPE_FRONTENDS}"
        return
    fi

    if [ ! -t 0 ]; then
        FRONTEND_SELECTION="${default_selection}"
        return
    fi

    echo ""
    echo "Which frontend(s) should open after the backend is ready?"
    echo "  1) Legacy analyzer only (${LEGACY_FRONTEND_URL})"
    echo "  2) Chat demo only (${CHAT_FRONTEND_URL})"
    echo "  3) Email demo only (${EMAIL_FRONTEND_URL})"
    echo "  4) Slack demo only (${SLACK_FRONTEND_URL})"
    echo "  5) All frontends"
    echo "  6) Backend only (do not open a frontend)"
    printf "Selection [%s]: " "${default_numeric}"
    read -r selection

    case "${selection:-${default_numeric}}" in
        1) FRONTEND_SELECTION="legacy" ;;
        2) FRONTEND_SELECTION="chat" ;;
        3) FRONTEND_SELECTION="email" ;;
        4) FRONTEND_SELECTION="slack" ;;
        5) FRONTEND_SELECTION="all" ;;
        6) FRONTEND_SELECTION="none" ;;
        legacy|chat|email|slack|all|none|both) FRONTEND_SELECTION="${selection}" ;;
        *)
            echo "⚠️  Unrecognized selection. Defaulting to ${default_selection}."
            FRONTEND_SELECTION="${default_selection}"
            ;;
    esac
}

selection_includes() {
    local surface="$1"

    case "${FRONTEND_SELECTION}" in
        all)
            return 0
            ;;
        both)
            case "${surface}" in
                legacy|chat) return 0 ;;
            esac
            return 1
            ;;
        "${surface}")
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

selection_requires_demo_server() {
    case "${FRONTEND_SELECTION}" in
        legacy|chat|email|slack|all|both) return 0 ;;
        *) return 1 ;;
    esac
}

start_demo_server() {
    if [ -n "${DEMO_SERVER_PID}" ]; then
        return
    fi

    if [ ! -d "${DEMO_ROOT}" ]; then
        echo "❌ Demo root missing: ${DEMO_ROOT}"
        exit 1
    fi

    echo "🌐 Starting archived frontend demo server on ${DEMO_BASE_URL}/ ..."
    python3 -m http.server "${NOUPE_FRONTEND_DEMO_PORT}" -d "${DEMO_ROOT}" >/dev/null 2>&1 &
    DEMO_SERVER_PID=$!
    wait_for_url "http://127.0.0.1:${NOUPE_FRONTEND_DEMO_PORT}/legacy/" "${DEMO_SERVER_PID}" 30
}

open_selected_frontends() {
    if selection_includes "legacy"; then
        echo "🌐 Opening legacy analyzer..."
        open_url "${LEGACY_FRONTEND_URL}"
    fi
    if selection_includes "chat"; then
        echo "🌐 Opening chat demo..."
        open_url "${CHAT_FRONTEND_URL}"
    fi
    if selection_includes "email"; then
        echo "🌐 Opening email demo..."
        open_url "${EMAIL_FRONTEND_URL}"
    fi
    if selection_includes "slack"; then
        echo "🌐 Opening slack demo..."
        open_url "${SLACK_FRONTEND_URL}"
    fi
}

print_selected_frontends() {
    if selection_includes "legacy"; then
        echo "   Legacy analyzer: ${LEGACY_FRONTEND_URL}"
    fi
    if selection_includes "chat"; then
        echo "   Chat demo: ${CHAT_FRONTEND_URL}"
    fi
    if selection_includes "email"; then
        echo "   Email demo: ${EMAIL_FRONTEND_URL}"
    fi
    if selection_includes "slack"; then
        echo "   Slack demo: ${SLACK_FRONTEND_URL}"
    fi
}

emit_launch_telemetry_report() {
    local report_path="${NOUPE_LAUNCH_TELEMETRY_FILE:-}"
    local frontend_selection="${1:-${FRONTEND_SELECTION:-none}}"

    if [ -z "${report_path}" ]; then
        return 0
    fi

    mkdir -p "$(dirname "${report_path}")"

    if ! python3 - "${BACKEND_URL}" "${report_path}" "${frontend_selection}" <<'PY'
import datetime
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

base_url = sys.argv[1].rstrip("/")
report_path = Path(sys.argv[2])
frontend_selection = sys.argv[3]

def fetch_json(path: str) -> dict:
    url = f"{base_url}{path}"
    with urllib.request.urlopen(url, timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, dict):
            return payload
        return {"raw": payload}

ready = fetch_json("/ready")
diagnostics = fetch_json("/diagnostics")

report = {
    "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "backend_url": base_url,
    "frontend_selection": frontend_selection,
    "ready": {
        "status": ready.get("status"),
        "ready": ready.get("ready"),
        "pipeline": ready.get("pipeline", []),
        "missing_required_layers": ready.get("missing_required_layers", []),
        "warming_required_layers": ready.get("warming_required_layers", []),
        "reasons": ready.get("reasons", []),
    },
    "diagnostics": {
        "pipeline": diagnostics.get("pipeline", []),
        "loaded_layers": diagnostics.get("loaded_layers", []),
        "lazy_layers": diagnostics.get("lazy_layers", []),
        "warming_required_layers": diagnostics.get("warming_required_layers", []),
        "startup_timings_ms": diagnostics.get("startup_timings_ms", {}),
        "load_errors": diagnostics.get("load_errors", []),
        "dependency_status": diagnostics.get("dependency_status", {}),
        "runtime_layer_errors": diagnostics.get("runtime_layer_errors", {}),
    },
}

report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(f"🧾 Launch telemetry written to {report_path}")
PY
    then
        echo "⚠️  Failed to write launch telemetry report to ${report_path}"
        return 1
    fi
}
