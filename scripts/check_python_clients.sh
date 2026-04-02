#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"

if [ ! -x "${PYTHON_BIN}" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    else
        echo "❌ Could not find a Python interpreter for client checks."
        exit 1
    fi
fi

cd "${ROOT}"

echo "🧪 Verifying Noupe sync and async Python clients..."
"${PYTHON_BIN}" -m py_compile \
    src/noupe/client.py \
    api/client.py \
    backend/client.py \
    scripts/examples/sync_client_example.py \
    scripts/examples/async_client_example.py
"${PYTHON_BIN}" -m unittest test.test_python_client
