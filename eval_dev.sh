#!/bin/bash
set -e

# Noupe Eval Runner
# Runs test/run_eval.py against all configs in configs/
# Optionally writes results to markdown or txt report.

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Activate project venv if present ──
if [ -z "$VIRTUAL_ENV" ] && [ -f "$ROOT/.venv/bin/activate" ]; then
    echo "🐍 Activating .venv..."
    source "$ROOT/.venv/bin/activate"
fi

EVAL_SCRIPT="$ROOT/test/run_eval.py"
EVAL_DATA="$ROOT/test/eval.json"
CONFIGS_DIR="$ROOT/configs"
REPORT_DIR="$ROOT/reports"
BASE_PORT=8100
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

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
CAPTURED=""

for cfg in "${configs[@]}"; do
    PORT=$((BASE_PORT + IDX))
    NAME=$(basename "$cfg" .toml)
    echo "────────────────────────────────────────────────"
    echo "  ▶ Running: $NAME (port $PORT)"
    echo "────────────────────────────────────────────────"

    OUTPUT=$(python3 "$EVAL_SCRIPT" --config "$cfg" --data "$EVAL_DATA" --port "$PORT" 2>&1) && STATUS=0 || STATUS=$?

    echo "$OUTPUT"

    CAPTURED+="CONFIG: $NAME"$'\n'
    CAPTURED+="$OUTPUT"$'\n\n'

    if [ "$STATUS" -eq 0 ]; then
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
echo ""

# ── Report prompt ──
echo "Save evaluation report?"
echo "  [m] Markdown (.md)"
echo "  [t] Plain text (.txt)"
echo "  [n] None"
read -r -p "Choice [m/t/n]: " choice

write_txt_report() {
    local path="$1"
    {
        echo "Noupe Evaluation Report"
        echo "Generated: $TIMESTAMP"
        echo "Configs: ${#configs[@]}  |  Passed: $PASS  |  Failed: $FAIL"
        echo ""
        echo "$CAPTURED"
    } > "$path"
}

write_md_report() {
    local path="$1"
    {
        echo "# Noupe Evaluation Report"
        echo ""
        echo "- **Generated**: \`$TIMESTAMP\`"
        echo "- **Configs evaluated**: ${#configs[@]}"
        echo "- **Passed**: $PASS"
        echo "- **Failed**: $FAIL"
        echo ""

        # parse each config block
        local current_name=""
        while IFS= read -r line; do
            if [[ "$line" =~ ^CONFIG:\ (.+)$ ]]; then
                current_name="${BASH_REMATCH[1]}"
                echo "---"
                echo ""
                echo "## $current_name"
                echo ""
                echo '```'
            elif [[ -z "$line" && -n "$current_name" ]]; then
                echo '```'
                echo ""
                current_name=""
            else
                echo "$line"
            fi
        done <<< "$CAPTURED"
        # close any unclosed block
        if [[ -n "$current_name" ]]; then
            echo '```'
        fi
    } > "$path"
}

case "$choice" in
    [mM])
        mkdir -p "$REPORT_DIR"
        REPORT_PATH="$REPORT_DIR/eval_${TIMESTAMP}.md"
        write_md_report "$REPORT_PATH"
        echo "📄 Report saved to $REPORT_PATH"
        ;;
    [tT])
        mkdir -p "$REPORT_DIR"
        REPORT_PATH="$REPORT_DIR/eval_${TIMESTAMP}.txt"
        write_txt_report "$REPORT_PATH"
        echo "📄 Report saved to $REPORT_PATH"
        ;;
    *)
        echo "⏭️  No report saved."
        ;;
esac

[ "$FAIL" -eq 0 ] || exit 1
