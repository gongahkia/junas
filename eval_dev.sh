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
TMP_DIR=$(mktemp -d)

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

    OUTPUT=$(python3 "$EVAL_SCRIPT" --config "$cfg" --data "$EVAL_DATA" --port "$PORT" 2>&1) && STATUS=0 || STATUS=$?

    echo "$OUTPUT"

    # save per-config output and config for report parsing
    echo "$OUTPUT" > "$TMP_DIR/${NAME}.txt"
    cp "$cfg" "$TMP_DIR/${NAME}.toml"

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

generate_report() {
    local fmt="$1"
    local outpath="$2"

    python3 - "$fmt" "$outpath" "$TIMESTAMP" "$PASS" "$FAIL" "$TMP_DIR" <<'PYEOF'
import sys, os, re, glob

fmt = sys.argv[1]       # "md" or "txt"
outpath = sys.argv[2]
timestamp = sys.argv[3]
passed = int(sys.argv[4])
failed = int(sys.argv[5])
tmp_dir = sys.argv[6]

files = sorted(glob.glob(os.path.join(tmp_dir, "eval_*.txt")))
total = len(files)

configs = []
for fpath in files:
    name = os.path.basename(fpath).replace(".txt", "")
    raw = open(fpath).read()

    config_path = fpath.replace(".txt", ".toml")
    config_raw = open(config_path).read() if os.path.exists(config_path) else ""

    predictions = []
    for m in re.finditer(r'\[(✓|✗)\]\s+id=(\S+)\s+expected=(\S+)\s+predicted=(\S+)', raw):
        predictions.append({
            "result": m.group(1),
            "id": m.group(2),
            "expected": m.group(3),
            "predicted": m.group(4),
        })

    accuracy = 0.0
    samples = 0
    am = re.search(r'accuracy:\s+([\d.]+)', raw)
    if am:
        accuracy = float(am.group(1))
    sm = re.search(r'samples\s*:\s+(\d+)', raw)
    if sm:
        samples = int(sm.group(1))

    metrics = []
    for m in re.finditer(r'^\s+(SAFE|LOW_RISK|HIGH_RISK|macro)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s+(\d+))?\s*$', raw, re.MULTILINE):
        metrics.append({
            "label": m.group(1),
            "precision": m.group(2),
            "recall": m.group(3),
            "f1": m.group(4),
            "support": m.group(5) or "",
        })

    macro = next((m for m in metrics if m["label"] == "macro"), None)

    configs.append({
        "name": name,
        "config_raw": config_raw,
        "predictions": predictions,
        "accuracy": accuracy,
        "samples": samples,
        "metrics": [m for m in metrics if m["label"] != "macro"],
        "macro": macro,
    })

lines = []

if fmt == "md":
    lines.append("# Noupe Evaluation Report")
    lines.append("")
    lines.append(f"- **Generated**: `{timestamp}`")
    lines.append(f"- **Configs evaluated**: {total}")
    lines.append(f"- **Passed**: {passed}")
    lines.append(f"- **Failed**: {failed}")
    lines.append("")

    # summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Config | Samples | Accuracy | Macro Precision | Macro Recall | Macro F1 |")
    lines.append("|--------|---------|----------|-----------------|--------------|----------|")
    for c in configs:
        mp = c["macro"]["precision"] if c["macro"] else "—"
        mr = c["macro"]["recall"] if c["macro"] else "—"
        mf = c["macro"]["f1"] if c["macro"] else "—"
        lines.append(f"| {c['name']} | {c['samples']} | {c['accuracy']:.4f} | {mp} | {mr} | {mf} |")
    lines.append("")

    # per-config details
    for c in configs:
        lines.append("---")
        lines.append("")
        lines.append(f"## {c['name']}")
        lines.append("")

        # config block
        if c["config_raw"]:
            lines.append("### Configuration")
            lines.append("")
            lines.append("```toml")
            lines.append(c["config_raw"].rstrip())
            lines.append("```")
            lines.append("")

        # predictions table
        lines.append("### Predictions")
        lines.append("")
        lines.append("| ID | Expected | Predicted | Result |")
        lines.append("|----|----------|-----------|--------|")
        for p in c["predictions"]:
            lines.append(f"| {p['id']} | {p['expected']} | {p['predicted']} | {p['result']} |")
        lines.append("")

        # metrics table
        lines.append("### Metrics")
        lines.append("")
        lines.append("| Label | Precision | Recall | F1 | Support |")
        lines.append("|-------|-----------|--------|----|---------|")
        for m in c["metrics"]:
            lines.append(f"| {m['label']} | {m['precision']} | {m['recall']} | {m['f1']} | {m['support']} |")
        if c["macro"]:
            m = c["macro"]
            lines.append(f"| **macro** | **{m['precision']}** | **{m['recall']}** | **{m['f1']}** | |")
        lines.append("")

else:  # txt
    lines.append("Noupe Evaluation Report")
    lines.append(f"Generated: {timestamp}")
    lines.append(f"Configs: {total}  |  Passed: {passed}  |  Failed: {failed}")
    lines.append("")
    for c in configs:
        lines.append(f"{'=' * 56}")
        lines.append(f"  {c['name']}")
        lines.append(f"  samples: {c['samples']}  accuracy: {c['accuracy']:.4f}")
        lines.append("")
        for p in c["predictions"]:
            lines.append(f"  [{p['result']}] id={p['id']:<4} expected={p['expected']:<10} predicted={p['predicted']}")
        lines.append("")
        lines.append(f"  {'label':<12} {'precision':>10} {'recall':>10} {'f1':>10} {'support':>8}")
        lines.append(f"  {'-' * 54}")
        for m in c["metrics"]:
            lines.append(f"  {m['label']:<12} {m['precision']:>10} {m['recall']:>10} {m['f1']:>10} {m['support']:>8}")
        if c["macro"]:
            m = c["macro"]
            lines.append(f"  {'-' * 54}")
            lines.append(f"  {'macro':<12} {m['precision']:>10} {m['recall']:>10} {m['f1']:>10}")
        lines.append("")
    lines.append(f"{'=' * 56}")

with open(outpath, "w") as f:
    f.write("\n".join(lines) + "\n")
PYEOF
}

case "$choice" in
    [mM])
        mkdir -p "$REPORT_DIR"
        REPORT_PATH="$REPORT_DIR/eval_${TIMESTAMP}.md"
        generate_report "md" "$REPORT_PATH"
        echo "📄 Report saved to $REPORT_PATH"
        ;;
    [tT])
        mkdir -p "$REPORT_DIR"
        REPORT_PATH="$REPORT_DIR/eval_${TIMESTAMP}.txt"
        generate_report "txt" "$REPORT_PATH"
        echo "📄 Report saved to $REPORT_PATH"
        ;;
    *)
        echo "⏭️  No report saved."
        ;;
esac

rm -rf "$TMP_DIR"
[ "$FAIL" -eq 0 ] || exit 1
