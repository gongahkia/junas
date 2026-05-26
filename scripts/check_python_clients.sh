#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-${ROOT}/.venv-uv}"
export UV_PYTHON="${UV_PYTHON:-3.12}"

cd "${ROOT}"

if command -v uv >/dev/null 2>&1; then
    PYTHON=(uv run python)
else
    PYTHON=(python3)
fi

echo "Verifying Kaypoh sync and async Python clients..."
"${PYTHON[@]}" -m py_compile \
    src/kaypoh/client.py \
    api/client.py \
    backend/client.py \
    scripts/examples/sync_client_example.py \
    scripts/examples/async_client_example.py \
    scripts/examples/round_trip_example.py \
    scripts/examples/decision_flow_example.py
"${PYTHON[@]}" -m unittest test.test_python_client

echo "Running legal-corpus recall gate..."
PYTHONPATH="${ROOT}/src" "${PYTHON[@]}" "${ROOT}/scripts/recall_gate.py"
