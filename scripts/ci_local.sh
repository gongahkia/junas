#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"
CI_LOCAL_BACKEND_PORT="${CI_LOCAL_BACKEND_PORT:-4010}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:${CI_LOCAL_BACKEND_PORT}}"
DOCKER_BACKEND_IMAGE="${DOCKER_BACKEND_IMAGE:-elixir:1.17}"

log() {
  echo "[sayless][ci-local] $*"
}

wait_for_backend() {
  for attempt in $(seq 1 180); do
    if curl -fsS "${API_BASE_URL}/" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  return 1
}

run_frontend_checks() {
  log "Running frontend checks..."
  (
    cd "$FRONTEND_DIR"
    npm ci
    npm run test
    npm run lint
    npm run build
  )
}

run_backend_checks_native() {
  log "Running backend checks with local mix..."
  (
    cd "$BACKEND_DIR"
    mix deps.get
    mix compile
    MIX_ENV=test mix test
  )

  local log_file server_pid
  log_file="$(mktemp)"

  (
    cd "$BACKEND_DIR"
    GEMINI_API_KEY="${GEMINI_API_KEY:-ci-dummy-gemini-key}" \
      TMDB_API_KEY="${TMDB_API_KEY:-ci-dummy-tmdb-key}" \
      PORT="$CI_LOCAL_BACKEND_PORT" \
      mix phx.server >"$log_file" 2>&1
  ) &
  server_pid=$!

  cleanup() {
    kill "$server_pid" 2>/dev/null || true
    rm -f "$log_file"
  }

  trap cleanup EXIT

  if ! wait_for_backend; then
    log "Backend failed to start."
    cat "$log_file"
    exit 1
  fi

  (
    cd "$ROOT_DIR"
    API_BASE_URL="$API_BASE_URL" ./scripts/smoke_backend_http.sh
  )

  cleanup
  trap - EXIT
}

run_backend_checks_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    log "docker is required when mix is not available."
    exit 1
  fi

  log "Running backend checks in Docker because mix is unavailable..."
  docker run --rm \
    -v "$ROOT_DIR:/workspace" \
    -w /workspace/backend \
    "$DOCKER_BACKEND_IMAGE" \
    bash -lc "mix local.hex --force && mix local.rebar --force && mix deps.get && mix compile && MIX_ENV=test mix test"

  local container_name
  container_name="sayless-ci-local-backend-$$"

  docker run -d --name "$container_name" \
    -p "${CI_LOCAL_BACKEND_PORT}:${CI_LOCAL_BACKEND_PORT}" \
    -e "PORT=${CI_LOCAL_BACKEND_PORT}" \
    -e "PHX_BIND_ALL=true" \
    -e "GEMINI_API_KEY=${GEMINI_API_KEY:-ci-dummy-gemini-key}" \
    -e "TMDB_API_KEY=${TMDB_API_KEY:-ci-dummy-tmdb-key}" \
    -v "$ROOT_DIR:/workspace" \
    -w /workspace/backend \
    "$DOCKER_BACKEND_IMAGE" \
    bash -lc "mix local.hex --force && mix local.rebar --force && mix deps.get && mix phx.server" >/dev/null

  cleanup() {
    docker rm -f "$container_name" >/dev/null 2>&1 || true
  }

  trap cleanup EXIT

  if ! wait_for_backend; then
    log "Backend failed to start in Docker."
    docker logs "$container_name" || true
    exit 1
  fi

  (
    cd "$ROOT_DIR"
    API_BASE_URL="$API_BASE_URL" ./scripts/smoke_backend_http.sh
  )

  cleanup
  trap - EXIT
}

main() {
  run_frontend_checks

  if command -v mix >/dev/null 2>&1; then
    run_backend_checks_native
  else
    run_backend_checks_docker
  fi

  log "All CI-equivalent checks passed."
}

main "$@"
