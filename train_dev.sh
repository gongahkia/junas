#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TRAINING_ROOT="$ROOT/training"
TARGET="${1:-}"

if [ -f "$ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$ROOT/.venv/bin/python"
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

print_menu() {
    echo "Available training workflows:"
    echo ""
    echo "1) classification"
    echo "   Document-level 80/20 split for the supervised classifiers only."
    echo "   Trains Model 1 and Model 2, then prints train/validation F1 reports."
    echo ""
    echo "2) pipeline"
    echo "   Two-pass end-to-end pipeline training."
    echo "   Trains classification, clustering, and regression artifacts,"
    echo "   then validates complete pipeline configurations and writes a report."
    echo ""
}

prompt_target() {
    if [ ! -t 0 ]; then
        echo "Non-interactive terminal: pass 'classification' or 'pipeline' explicitly." >&2
        exit 1
    fi

    while true; do
        print_menu
        printf "Select a training workflow [1]: "
        read -r selection

        case "${selection:-1}" in
            1|classification)
                TARGET="classification"
                return
                ;;
            2|pipeline)
                TARGET="pipeline"
                return
                ;;
            *)
                echo "Unrecognized selection. Choose 1 or 2."
                echo ""
                ;;
        esac
    done
}

if [ -z "$TARGET" ]; then
    prompt_target
else
    shift
fi

case "$TARGET" in
    classification)
        SCRIPT_PATH="$TRAINING_ROOT/train_validate_classification.py"
        DESCRIPTION="Document-level 80/20 split for the supervised classifiers only. Trains Model 1 and Model 2, then prints train/validation F1 reports."
        ;;
    pipeline)
        SCRIPT_PATH="$TRAINING_ROOT/train_validate_pipeline.py"
        DESCRIPTION="Two-pass end-to-end pipeline training. Trains classification, clustering, and regression artifacts, then validates complete pipeline configurations and writes a report."
        ;;
    *)
        echo "Unknown training workflow: $TARGET" >&2
        echo "Use 'classification' or 'pipeline'." >&2
        exit 1
        ;;
esac

echo "Selected: $TARGET"
echo "$DESCRIPTION"
echo "Running: $SCRIPT_PATH"
if [ "$#" -gt 0 ]; then
    echo "Arguments: $*"
fi

cd "$ROOT"
exec "$PYTHON_BIN" "$SCRIPT_PATH" "$@"
