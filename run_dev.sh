#!/bin/bash

# Noupe Dev Bootstrapper
# Starts FastAPI backend and opens the frontend Chat UI

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 Starting Noupe services..."

# ── Activate project venv if present ──
if [ -z "$VIRTUAL_ENV" ] && [ -f "$ROOT/.venv/bin/activate" ]; then
    echo "🐍 Activating .venv..."
    source "$ROOT/.venv/bin/activate"
fi

# ── Preflight checks ──
echo "🧪 Running preflight checks..."
if [ "${NOUPE_PREFLIGHT_STRICT:-0}" = "1" ]; then
    python3 "$ROOT/scripts/preflight.py" --strict
else
    python3 "$ROOT/scripts/preflight.py" || true
fi

# --- Preflight: checkpoint validation ---
MISSING=0

check_file() {
    if [ ! -f "$1" ]; then
        echo "⚠️  Missing: $1"
        MISSING=$((MISSING + 1))
    fi
}

check_dir_has_model() { # dir must contain a model weight file
    local dir="$1"
    local name="$2"
    if [ ! -d "$dir" ]; then
        echo "⚠️  Missing checkpoint dir for ${name}: ${dir}"
        MISSING=$((MISSING + 1))
        return
    fi
    for ext in safetensors bin pt ckpt; do
        if ls "$dir"/*."$ext" 1>/dev/null 2>&1; then
            return 0
        fi
    done
    echo "⚠️  No model weights in ${dir} for ${name} (need .safetensors/.bin/.pt/.ckpt)"
    MISSING=$((MISSING + 1))
}

check_file "$ROOT/layer3-clustering/checkpoints/anomaly_detector.joblib"
check_dir_has_model "$ROOT/layer4-classification/model-1/checkpoints/best" "model1"
check_dir_has_model "$ROOT/layer4-classification/model-2/checkpoints/best" "model2"

if [ "$MISSING" -gt 0 ]; then
    echo ""
    echo "────────────────────────────────────────────────────"
    echo "  ${MISSING} checkpoint(s) missing."
    echo "  Train models first or download pre-trained weights."
    echo "  Affected layers will be skipped at runtime."
    echo "────────────────────────────────────────────────────"
    echo ""
    read -r -p "Continue anyway? [Y/n] " ans
    case "$ans" in
        [nN]*) echo "Aborted."; exit 1 ;;
    esac
fi

# 1. Start FastAPI backend in the background
echo "📦 Booting FastAPI backend on http://localhost:8000..."
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 2. Give the backend a moment to initialize
sleep 2

# 3. Open the frontend
echo "🌐 Opening Chat UI..."
if command -v open >/dev/null 2>&1; then
    open "$ROOT/frontend/index.html"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$ROOT/frontend/index.html" >/dev/null 2>&1 &
else
    echo "ℹ️  Could not auto-open browser. Open this file manually:"
    echo "   $ROOT/frontend/index.html"
fi

echo "✅ Services are running. Press Ctrl+C to stop both."

# Trap SIGINT (Ctrl+C) to kill the backend process
trap "kill $BACKEND_PID; echo -e '\n🛑 Services stopped.'; exit" SIGINT

# Wait for backend to continue running
wait $BACKEND_PID
