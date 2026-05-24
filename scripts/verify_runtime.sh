#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
CURL_BIN="${CURL_BIN:-curl}"
HOST="${KAYPOH_VERIFY_HOST:-127.0.0.1}"

TEMP_DIR=""
SERVER_PID=""
SERVER_LOG=""
REDIS_PID=""
REDIS_LOG=""
REDIS_DIR=""

HTTP_STATUS=""
HTTP_BODY=""

info() {
  printf '[verify] %s\n' "$*"
}

fail() {
  printf '[verify] ERROR: %s\n' "$*" >&2
  if [[ -n "${SERVER_LOG:-}" && -f "${SERVER_LOG:-}" ]]; then
    printf '\n[verify] Last backend log lines:\n' >&2
    tail -n 40 "$SERVER_LOG" >&2 || true
  fi
  if [[ -n "${REDIS_LOG:-}" && -f "${REDIS_LOG:-}" ]]; then
    printf '\n[verify] Last redis log lines:\n' >&2
    tail -n 20 "$REDIS_LOG" >&2 || true
  fi
  exit 1
}

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${REDIS_PID:-}" ]] && kill -0 "${REDIS_PID}" >/dev/null 2>&1; then
    kill "${REDIS_PID}" >/dev/null 2>&1 || true
    wait "${REDIS_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${TEMP_DIR:-}" && -d "${TEMP_DIR:-}" ]]; then
    rm -rf "${TEMP_DIR}"
  fi
}

trap cleanup EXIT

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || fail "required command not found: $cmd"
}

assert_file() {
  local path="$1"
  [[ -e "$path" ]] || fail "required path missing: $path"
}

find_free_port() {
  "$PYTHON_BIN" - <<'PY'
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

request() {
  local method="$1"
  local url="$2"
  local body="${3:-}"
  local response_file="$TEMP_DIR/response.json"

  if [[ "$method" == "GET" ]]; then
    HTTP_STATUS="$("$CURL_BIN" -sS -o "$response_file" -w '%{http_code}' "$url")" || fail "request failed: GET $url"
  else
    HTTP_STATUS="$("$CURL_BIN" -sS -o "$response_file" -w '%{http_code}' -X "$method" -H 'Content-Type: application/json' -d "$body" "$url")" \
      || fail "request failed: $method $url"
  fi

  HTTP_BODY="$(cat "$response_file")"
}

assert_status() {
  local expected="$1"
  [[ "$HTTP_STATUS" == "$expected" ]] || fail "expected HTTP $expected, got $HTTP_STATUS with body: $HTTP_BODY"
}

assert_json() {
  local body="$1"
  local expr="$2"
  local message="$3"
  JSON_INPUT="$body" "$PYTHON_BIN" - "$expr" "$message" <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["JSON_INPUT"])
expr = sys.argv[1]
message = sys.argv[2]
namespace = {"payload": payload}
if not eval(expr, namespace):
    print(f"{message}\nexpression: {expr}\npayload: {json.dumps(payload, indent=2)}", file=sys.stderr)
    raise SystemExit(1)
PY
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local message="$3"
  grep -q "$needle" <<<"$haystack" || fail "$message"
}

wait_for_ready() {
  local port="$1"
  local ready_url="http://${HOST}:${port}/ready"
  local response_file="$TEMP_DIR/ready.json"

  for _ in $(seq 1 180); do
    if [[ -n "${SERVER_PID:-}" ]] && ! kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
      fail "backend exited before reporting ready"
    fi

    local status
    status="$("$CURL_BIN" -sS -o "$response_file" -w '%{http_code}' "$ready_url" 2>/dev/null || true)"
    if [[ "$status" == "200" ]]; then
      local body
      body="$(cat "$response_file")"
      if JSON_INPUT="$body" "$PYTHON_BIN" - <<'PY'
import json
import os

payload = json.loads(os.environ["JSON_INPUT"])
raise SystemExit(0 if payload.get("ready") else 1)
PY
      then
        return 0
      fi
    fi
    sleep 1
  done

  fail "backend did not become ready on port $port"
}

stop_server() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  SERVER_PID=""
  SERVER_LOG=""
}

start_server() {
  local name="$1"
  local port="$2"
  shift 2

  stop_server
  SERVER_LOG="$TEMP_DIR/${name}.backend.log"

  info "starting ${name} backend on ${HOST}:${port}"
  (
    cd "$ROOT"
    export KMP_DUPLICATE_LIB_OK=TRUE
    export KAYPOH_FAIL_ON_LAYER_LOAD_ERROR=1
    export KAYPOH_LAZY_LOAD_HEAVY=0
    export KAYPOH_PREWARM_REQUIRED_LAYERS=0
    export KAYPOH_PRETTY_LOGS=0
    while (($#)); do
      export "$1"
      shift
    done
    exec "$PYTHON_BIN" -m uvicorn backend.main:app --host "$HOST" --port "$port" --log-level warning
  ) >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!

  wait_for_ready "$port"
}

start_redis() {
  local redis_server_bin
  redis_server_bin="${REDIS_SERVER_BIN:-$(command -v redis-server || true)}"
  [[ -n "$redis_server_bin" ]] || fail "redis-server is required for mosaic verification"

  REDIS_DIR="$TEMP_DIR/redis"
  mkdir -p "$REDIS_DIR"
  REDIS_LOG="$TEMP_DIR/redis.log"

  local port="$1"
  info "starting temporary redis on ${HOST}:${port}"
  "$redis_server_bin" \
    --save "" \
    --appendonly no \
    --bind "$HOST" \
    --port "$port" \
    --dir "$REDIS_DIR" >"$REDIS_LOG" 2>&1 &
  REDIS_PID=$!

  for _ in $(seq 1 50); do
    if REDIS_HOST="$HOST" REDIS_PORT="$port" "$PYTHON_BIN" - <<'PY'
import os
import redis

client = redis.Redis(host=os.environ["REDIS_HOST"], port=int(os.environ["REDIS_PORT"]))
client.ping()
PY
    then
      return 0
    fi
    sleep 0.2
  done

  fail "temporary redis did not become ready on port $port"
}

smoke_runtime_endpoints() {
  local port="$1"
  local expected_pipeline="$2"

  request GET "http://${HOST}:${port}/health"
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["status"] == "ok"' "/health should report ok"

  request GET "http://${HOST}:${port}/ready"
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["ready"] is True' "/ready should report ready"
  assert_json "$HTTP_BODY" "payload['pipeline'] == ${expected_pipeline}" "/ready should expose the configured pipeline"

  request GET "http://${HOST}:${port}/diagnostics"
  assert_status 200
  assert_json "$HTTP_BODY" "payload['pipeline'] == ${expected_pipeline}" "/diagnostics should expose the configured pipeline"

  request GET "http://${HOST}:${port}/metrics"
  assert_status 200
  assert_contains "$HTTP_BODY" 'kaypoh_http_requests_total' "/metrics should expose Kaypoh Prometheus counters"
}

smoke_lexicon_embedding_clustering() {
  local port="$1"
  smoke_runtime_endpoints "$port" '["lexicon", "embedding", "clustering"]'

  info "smoke testing lexicon short-circuit"
  request POST "http://${HOST}:${port}/classify" \
    '{"text":"Acme Corp is acquiring GlobalTech for $2.5 billion next quarter."}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["classification"] == "HIGH_RISK"' "lexicon threshold text should classify as HIGH_RISK"
  assert_json "$HTTP_BODY" 'payload["lexicon"] is not None and payload["lexicon"]["flagged"] is True' "lexicon output should be present and flagged"

  info "smoke testing embeddings and clustering"
  request POST "http://${HOST}:${port}/classify" \
    '{"text":"The company published its annual sustainability report and thanked employees for the launch event.","debug":true}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["embedding"] is not None and len(payload["embedding"]) > 0' "embedding debug payload should be populated"
  assert_json "$HTTP_BODY" 'payload["clustering"] is not None and "anomaly_score" in payload["clustering"]' "clustering output should be populated"
}

smoke_models_and_regression() {
  local port="$1"
  smoke_runtime_endpoints "$port" '["model1", "model2", "regression"]'

  info "smoke testing model1 safe path"
  request POST "http://${HOST}:${port}/classify" \
    '{"text":"The company published its annual sustainability report and thanked employees for the launch event."}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["classification"] == "SAFE"' "safe public text should classify as SAFE"
  assert_json "$HTTP_BODY" 'payload["model1"] is not None and payload["model2"] is None' "model2 should be skipped for safe model1 output"

  info "smoke testing model2 low-risk path"
  request POST "http://${HOST}:${port}/classify" \
    '{"text":"Finance is reviewing confidential pricing scenarios before the public launch."}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["classification"] == "LOW_RISK"' "confidential pricing review text should classify as LOW_RISK"
  assert_json "$HTTP_BODY" 'payload["model2"] is not None and payload["model2"]["label"] == "low_risk"' "model2 should emit low_risk"
  assert_json "$HTTP_BODY" 'payload["regression"] is not None and payload["regression"]["risk_score"] > 0.4' "regression should keep the confidential pricing text in the LOW_RISK band"

  info "smoke testing model2 high-risk path and regression"
  request POST "http://${HOST}:${port}/classify" \
    '{"text":"The board will secretly approve the acquisition of BetaCorp for $500 million next Tuesday before the market opens."}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["classification"] == "HIGH_RISK"' "board-approved secret acquisition text should classify as HIGH_RISK"
  assert_json "$HTTP_BODY" 'payload["model2"] is not None and payload["model2"]["label"] == "high_risk"' "model2 should emit high_risk"
  assert_json "$HTTP_BODY" 'payload["regression"] is not None and payload["regression"]["risk_score"] > 0.7 and "reasoning" in payload["regression"]' "regression output should be populated and stay in the HIGH_RISK band"
}

smoke_mosaic() {
  local port="$1"
  smoke_runtime_endpoints "$port" '["model1", "model2", "mosaic"]'

  info "smoke testing mosaic aggregation"
  request POST "http://${HOST}:${port}/classify" \
    '{"text":"Finance is reviewing tentative pricing scenarios before the public launch.","entity_id":"Acme Corp"}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["classification"] == "LOW_RISK"' "first mosaic fragment should remain LOW_RISK"
  assert_json "$HTTP_BODY" 'payload["mosaic"] is not None and payload["mosaic"]["unique_fragment_count"] == 1 and payload["mosaic"]["escalated"] is False' "first mosaic fragment should record one unique event without escalation"

  request POST "http://${HOST}:${port}/classify" \
    '{"text":"A supplier contract may be renewed under similar terms next quarter.","entity_id":"Acme Corp"}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["classification"] == "HIGH_RISK"' "second unique mosaic fragment should escalate to HIGH_RISK"
  assert_json "$HTTP_BODY" 'payload["mosaic"] is not None and payload["mosaic"]["unique_fragment_count"] == 2 and payload["mosaic"]["recent_event_count"] == 2' "mosaic should report two unique and recent events"
  assert_json "$HTTP_BODY" 'payload["mosaic"]["escalated"] is True and len(payload["mosaic"]["matched_event_ids"]) == 2' "mosaic should expose escalation evidence"
}

main() {
  assert_file "$PYTHON_BIN"
  require_cmd "$CURL_BIN"

  TEMP_DIR="$(mktemp -d)"

  info "bootstrapping artifacts"
  (
    cd "$ROOT"
    "$PYTHON_BIN" scripts/bootstrap_artifacts.py --sync-from-legacy >/dev/null
    "$PYTHON_BIN" scripts/preflight.py --strict >/dev/null
  )

  info "running lint, type-checks, and automated tests"
  (
    cd "$ROOT"
    "$PYTHON_BIN" -m ruff check \
      src/kaypoh/backend/main.py \
      src/kaypoh/backend/schemas.py \
      src/kaypoh/configs/runtime.py \
      src/kaypoh/configs/artifacts.py \
      test/test_runtime_settings_validation.py \
      test/test_preflight_validation.py \
      test/test_redis_integration.py \
      test/test_runtime_artifact_integration.py \
      test/integration_helpers.py
    "$PYTHON_BIN" -m mypy \
      src/kaypoh/backend/main.py \
      src/kaypoh/backend/cache.py \
      src/kaypoh/backend/observability.py \
      src/kaypoh/backend/schemas.py \
      src/kaypoh/configs/runtime.py \
      src/kaypoh/configs/artifacts.py
    "$PYTHON_BIN" -m unittest discover -s test -p 'test*.py'
  )

  local port_a
  local port_b
  local port_c
  local redis_port
  port_a="$(find_free_port)"
  port_b="$(find_free_port)"
  port_c="$(find_free_port)"
  redis_port="$(find_free_port)"

  start_server "lexicon-embedding-clustering" "$port_a" "PIPELINE_LAYERS=lexicon,embedding,clustering"
  smoke_lexicon_embedding_clustering "$port_a"

  start_server "models-regression" "$port_b" "PIPELINE_LAYERS=model1,model2,regression"
  smoke_models_and_regression "$port_b"

  start_redis "$redis_port"
  start_server \
    "mosaic" \
    "$port_c" \
    "PIPELINE_LAYERS=model1,model2,mosaic" \
    "MOSAIC_THRESHOLD=2" \
    "MOSAIC_TTL_HOURS=1" \
    "REDIS_HOST=$HOST" \
    "REDIS_PORT=$redis_port"
  smoke_mosaic "$port_c"

  info "all verification steps passed"
}

main "$@"
