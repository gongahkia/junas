#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"

# the system python3 on some setups (e.g. brew @3.14) lacks httpx and causes confusing
# ImportError failures during the pre-push hook. require the project venv to keep the
# environment hermetic. opt out with KAYPOH_HOOK_ALLOW_SYSTEM_PYTHON=1 if you know better.
if [ ! -x "${PYTHON_BIN}" ]; then
    if [ "${KAYPOH_HOOK_ALLOW_SYSTEM_PYTHON:-0}" = "1" ] && command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
        echo "⚠️  Using system python3 because KAYPOH_HOOK_ALLOW_SYSTEM_PYTHON=1."
    else
        cat >&2 <<EOM
❌ Cannot find ${PYTHON_BIN}.

The pre-push hook requires the project virtualenv so dependencies (httpx, fastapi,
pydantic, presidio, spacy, ...) are guaranteed available. Set one up:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -e ".[local,dev]"     # or ".[server,dev]" for the full stack
    python -m spacy download en_core_web_sm

If you really need to bypass this and use the system python3, set:
    KAYPOH_HOOK_ALLOW_SYSTEM_PYTHON=1
EOM
        exit 1
    fi
fi

cd "${ROOT}"

echo "🧪 Verifying Kaypoh sync and async Python clients..."
"${PYTHON_BIN}" -m py_compile \
    src/kaypoh/client.py \
    api/client.py \
    backend/client.py \
    scripts/examples/sync_client_example.py \
    scripts/examples/async_client_example.py
"${PYTHON_BIN}" -m unittest test.test_python_client

echo "🧪 Running legal-corpus recall gate..."
PYTHONPATH="${ROOT}/src" "${PYTHON_BIN}" "${ROOT}/scripts/recall_gate.py"
