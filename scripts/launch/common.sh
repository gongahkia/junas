#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KAYPOH_HOST="${KAYPOH_HOST:-0.0.0.0}"
KAYPOH_PORT="${KAYPOH_PORT:-8000}"
KAYPOH_READY_TIMEOUT_SECONDS="${KAYPOH_READY_TIMEOUT_SECONDS:-180}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-${ROOT}/.venv-uv}"
export UV_PYTHON="${UV_PYTHON:-3.12}"

BACKEND_PID=""
BACKEND_URL="http://localhost:${KAYPOH_PORT}"

cleanup_services() {
    local exit_code=$?
    trap - EXIT INT TERM

    if [ -n "${BACKEND_PID}" ]; then
        kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    fi

    echo ""
    echo "Services stopped."
    exit "${exit_code}"
}

python_cmd() {
    if command -v uv >/dev/null 2>&1; then
        (cd "${ROOT}" && uv run python "$@")
    else
        python3 "$@"
    fi
}

uvicorn_cmd() {
    if command -v uv >/dev/null 2>&1; then
        (cd "${ROOT}" && uv run uvicorn "$@")
    else
        python3 -m uvicorn "$@"
    fi
}

run_preflight() {
    if [ "${KAYPOH_PREFLIGHT_STRICT:-1}" = "1" ]; then
        python_cmd "${ROOT}/scripts/preflight.py" --strict
    else
        python_cmd "${ROOT}/scripts/preflight.py" || true
    fi
}

wait_for_backend_ready() {
    local ready_url="http://127.0.0.1:${KAYPOH_PORT}/ready"

    echo "Waiting for backend readiness at ${ready_url}..."

    python_cmd - "${BACKEND_PID}" "${KAYPOH_PORT}" "${KAYPOH_READY_TIMEOUT_SECONDS}" <<'PY'
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
        time.sleep(1)
        continue

    if payload.get("ready") is True:
        print("Backend is ready.")
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

    time.sleep(1)

sys.stderr.write(f"timed out waiting for backend readiness at {url}\n")
sys.exit(1)
PY
}

emit_launch_telemetry_report() {
    local report_path="${KAYPOH_LAUNCH_TELEMETRY_FILE:-}"
    local launch_mode="${1:-backend}"

    if [ -z "${report_path}" ]; then
        return 0
    fi

    mkdir -p "$(dirname "${report_path}")"

    if ! python_cmd - "${BACKEND_URL}" "${report_path}" "${launch_mode}" <<'PY'
import datetime
import json
import sys
import urllib.request
from pathlib import Path

base_url = sys.argv[1].rstrip("/")
report_path = Path(sys.argv[2])
launch_mode = sys.argv[3]


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
    "launch_mode": launch_mode,
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
print(f"Launch telemetry written to {report_path}")
PY
    then
        echo "Failed to write launch telemetry report to ${report_path}"
        return 1
    fi
}
