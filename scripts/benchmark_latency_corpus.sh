#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CORPUS_DIR="${LATENCY_CORPUS_DIR:-$ROOT/test/fixtures/latency-corpus}"

export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-${ROOT}/.venv-uv}"
export UV_PYTHON="${UV_PYTHON:-3.12}"

if [ ! -d "$CORPUS_DIR" ]; then
    echo "Latency corpus folder not found: $CORPUS_DIR" >&2
    exit 1
fi

echo "Benchmark corpus: $CORPUS_DIR"
echo "Runner: $ROOT/scripts/benchmark_latency.py"

cd "$ROOT"
if command -v uv >/dev/null 2>&1; then
    exec uv run python "$ROOT/scripts/benchmark_latency.py" "$CORPUS_DIR" "$@"
fi
exec python3 "$ROOT/scripts/benchmark_latency.py" "$CORPUS_DIR" "$@"
