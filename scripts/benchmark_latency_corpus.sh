#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CORPUS_DIR="${LATENCY_CORPUS_DIR:-$ROOT/test/fixtures/latency-corpus}"

if [ -f "$ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

if [ ! -d "$CORPUS_DIR" ]; then
    echo "Latency corpus folder not found: $CORPUS_DIR" >&2
    exit 1
fi

echo "Benchmark corpus: $CORPUS_DIR"
echo "Runner: $ROOT/scripts/benchmark_latency.py"

cd "$ROOT"
exec "$PYTHON_BIN" "$ROOT/scripts/benchmark_latency.py" "$CORPUS_DIR" "$@"
