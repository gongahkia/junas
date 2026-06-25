#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Cleaning local development caches..."

rm -rf "$ROOT/.pytest_cache" "$ROOT/.ruff_cache" "$ROOT/.mypy_cache" "$ROOT/.prometheus-multiproc"
find "$ROOT" -type d -name __pycache__ -prune -exec rm -rf {} +

echo "Local development caches removed."
