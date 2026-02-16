#!/usr/bin/env bash
# Run both backend and frontend dev servers for cAI-png V2
# - Starts backend on :5000 and frontend on :3000
# - Streams logs from both to ./logs and tails them

set -euo pipefail

# Move to repo root
cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"

# Auto-source root .env (without leaking into shell history) if present
if [ -f .env ]; then
  echo "[env] Sourcing root .env"
  set -a
  . ./.env
  set +a
fi

# Masked echo of critical variables for troubleshooting
MASKED_GEMINI="${GEMINI_API_KEY:0:8}********"
if [ -n "${GEMINI_API_KEY:-}" ]; then
  echo "[env] GEMINI_API_KEY detected (prefix): $MASKED_GEMINI"
else
  echo "[env] GEMINI_API_KEY not loaded from root .env or environment"
fi

LOG_DIR="$ROOT_DIR/logs"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_LOG="$LOG_DIR/backend.dev.log"
FRONTEND_LOG="$LOG_DIR/frontend.dev.log"

mkdir -p "$LOG_DIR"

# Helpers
cleanup() {
  echo "\nShutting down..."
  # kill tail first so it releases file handles
  if [[ -n "${TAIL_PID:-}" ]]; then kill "$TAIL_PID" 2>/dev/null || true; fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then kill -9 "$FRONTEND_PID" 2>/dev/null || true; fi
  if [[ -n "${BACKEND_PID:-}" ]]; then kill -9 "$BACKEND_PID" 2>/dev/null || true; fi
  # Also kill any orphaned node processes on our ports
  lsof -ti :5000 :3000 2>/dev/null | xargs -r kill -9 2>/dev/null || true
}
trap cleanup EXIT INT TERM

check_cmd() { command -v "$1" >/dev/null 2>&1; }

# Pre-emptively kill any processes on our ports before starting
echo "[preflight] Checking for port conflicts..."
STRAY_PIDS=$(lsof -ti :5000,:3000 2>/dev/null || true)
if [[ -n "$STRAY_PIDS" ]]; then
  echo "[preflight] Killing stray processes on ports 5000/3000: $STRAY_PIDS"
  echo "$STRAY_PIDS" | xargs -r kill -9 2>/dev/null || true
  sleep 1
fi

if ! check_cmd node; then
  echo "Error: node is not installed. Install Node.js >= 18 and retry." >&2
  exit 1
fi
if ! check_cmd npm; then
  echo "Error: npm is not installed." >&2
  exit 1
fi

# Warn if Gemini key not set (macros will return placeholder values)
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "[warn] GEMINI_API_KEY not set (from environment or .env). Macros endpoint will return placeholder values."
fi

# Start backend
(
  cd "$BACKEND_DIR"
  # Inject GEMINI_API_KEY into backend/.env if backend .env missing or key absent
  if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    if [[ ! -f .env ]]; then
      echo "[backend-env] Creating backend/.env with GEMINI_API_KEY"
      printf "GEMINI_API_KEY=%s\n" "$GEMINI_API_KEY" > .env
    else
      if ! grep -q '^GEMINI_API_KEY=' .env; then
        echo "[backend-env] Appending GEMINI_API_KEY to backend/.env"
        printf "\nGEMINI_API_KEY=%s\n" "$GEMINI_API_KEY" >> .env
      fi
    fi
  fi
  # Ensure essential defaults exist
  ensure_var() { local k="$1" v="$2"; if ! grep -q "^$k=" .env 2>/dev/null; then echo "[backend-env] Setting default $k=$v"; printf "\n%s=%s\n" "$k" "$v" >> .env; fi }
  if [[ ! -f .env ]]; then touch .env; fi
  ensure_var NODE_ENV "development"
  ensure_var PORT "5000"
  ensure_var MONGODB_URI "mongodb://localhost:27017/caipng"
  ensure_var CORS_ORIGIN "http://localhost:3000"
  if [[ ! -d node_modules ]]; then
    echo "[backend] Installing dependencies..."
    npm install
  fi
  export CORS_ORIGIN="${CORS_ORIGIN:-http://localhost:3000}"
  echo "[backend] Starting dev server on :5000... (logs: $BACKEND_LOG)"
  npm run dev >"$BACKEND_LOG" 2>&1 &
  echo $! > "$ROOT_DIR/.backend.pid"
)
BACKEND_PID="$(cat "$ROOT_DIR/.backend.pid")"
rm -f "$ROOT_DIR/.backend.pid"

# Start frontend
(
  cd "$FRONTEND_DIR"
  if [[ ! -d node_modules ]]; then
    echo "[frontend] Installing dependencies..."
    npm install
  fi
  echo "[frontend] Starting dev server on :3000... (logs: $FRONTEND_LOG)"
  npm run dev >"$FRONTEND_LOG" 2>&1 &
  echo $! > "$ROOT_DIR/.frontend.pid"
)
FRONTEND_PID="$(cat "$ROOT_DIR/.frontend.pid")"
rm -f "$ROOT_DIR/.frontend.pid"

# Tail both logs
echo "\nBoth servers started. Opening combined logs (Ctrl+C to stop):"
 tail -n +1 -f "$BACKEND_LOG" "$FRONTEND_LOG" & echo $! > "$ROOT_DIR/.tail.pid"
TAIL_PID="$(cat "$ROOT_DIR/.tail.pid")"
rm -f "$ROOT_DIR/.tail.pid"

# Print quick links
cat <<EOF

Frontend:  http://localhost:3000
Backend:   http://localhost:5000

Tips:
- Set GEMINI_API_KEY in your environment before running for real macro estimates.
- If MongoDB isn’t running locally, ensure MONGODB_URI in backend .env points to a reachable instance.
EOF

# Wait on child processes (tail keeps the script in foreground)
wait "$TAIL_PID"
