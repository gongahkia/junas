#!/bin/bash
set -e

# Noupe Eval Runner
# Runs test/run_eval.py against all configs in configs/

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Activate project venv if present ──
if [ -z "$VIRTUAL_ENV" ] && [ -f "$ROOT/.venv/bin/activate" ]; then
    echo "🐍 Activating .venv..."
    source "$ROOT/.venv/bin/activate"
fi

EVAL_SCRIPT="$ROOT/test/run_eval.py"
EVAL_DATA="$ROOT/test/eval.json"
CONFIGS_DIR="$ROOT/configs"
BASE_PORT=8100

echo "════════════════════════════════════════════════"
echo "  Noupe Evaluation Suite"
echo "════════════════════════════════════════════════"
echo ""

configs=("$CONFIGS_DIR"/eval_*.toml)

if [ ${#configs[@]} -eq 0 ]; then
    echo "❌ No eval configs found in $CONFIGS_DIR"
    exit 1
fi

echo "📋 Found ${#configs[@]} config(s):"
for cfg in "${configs[@]}"; do
    echo "   • $(basename "$cfg")"
done
echo ""

PASS=0
FAIL=0
IDX=0

for cfg in "${configs[@]}"; do
    PORT=$((BASE_PORT + IDX))
    NAME=$(basename "$cfg" .toml)
    echo "────────────────────────────────────────────────"
    echo "  ▶ Running: $NAME (port $PORT)"
    echo "────────────────────────────────────────────────"

    if python3 "$EVAL_SCRIPT" --config "$cfg" --data "$EVAL_DATA" --port "$PORT"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "  ⚠️  $NAME exited with errors"
    fi

    echo ""
    IDX=$((IDX + 1))
done

echo "════════════════════════════════════════════════"
echo "  ✅ Eval complete: $PASS passed, $FAIL failed"
echo "  Configs evaluated: ${#configs[@]}"
echo "════════════════════════════════════════════════"

[ "$FAIL" -eq 0 ] || exit 1
