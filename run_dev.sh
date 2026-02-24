#!/bin/bash

# Noupe Dev Bootstrapper
# Starts FastAPI backend and opens the frontend Chat UI

echo "🚀 Starting Noupe services..."

# 1. Start FastAPI backend in the background
echo "📦 Booting FastAPI backend on http://localhost:8000..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 2. Give the backend a moment to initialize
sleep 2

# 3. Open the frontend
echo "🌐 Opening Chat UI..."
open frontend/index.html

echo "✅ Services are running. Press Ctrl+C to stop both."

# Trap SIGINT (Ctrl+C) to kill the backend process
trap "kill $BACKEND_PID; echo -e '\n🛑 Services stopped.'; exit" SIGINT

# Wait for backend to continue running
wait $BACKEND_PID
