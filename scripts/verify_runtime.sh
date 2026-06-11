#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CURL_BIN="${CURL_BIN:-curl}"
HOST="${KAYPOH_VERIFY_HOST:-127.0.0.1}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-${ROOT}/.venv-uv}"
export UV_PYTHON="${UV_PYTHON:-3.12}"

if command -v uv >/dev/null 2>&1; then
  PYTHON_CMD=(uv run python)
  UVICORN_CMD=(uv run uvicorn)
  RUFF_CMD=(uv run ruff)
else
  PYTHON_CMD=(python3)
  UVICORN_CMD=(python3 -m uvicorn)
  RUFF_CMD=(python3 -m ruff)
fi

TEMP_DIR=""
SERVER_PID=""
SERVER_LOG=""
HTTP_STATUS=""
HTTP_BODY=""

info() {
  printf '[verify] %s\n' "$*"
}

fail() {
  printf '[verify] ERROR: %s\n' "$*" >&2
  if [[ -n "${SERVER_LOG:-}" && -f "${SERVER_LOG:-}" ]]; then
    printf '\n[verify] Last backend log lines:\n' >&2
    tail -n 60 "$SERVER_LOG" >&2 || true
  fi
  exit 1
}

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
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

find_free_port() {
  "${PYTHON_CMD[@]}" - <<'PY'
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
  JSON_INPUT="$body" "${PYTHON_CMD[@]}" - "$expr" "$message" <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["JSON_INPUT"])
expr = sys.argv[1]
message = sys.argv[2]
if not eval(expr, {"payload": payload}):
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

  for _ in $(seq 1 90); do
    if [[ -n "${SERVER_PID:-}" ]] && ! kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
      fail "backend exited before reporting ready"
    fi

    local status
    status="$("$CURL_BIN" -sS -o "$response_file" -w '%{http_code}' "$ready_url" 2>/dev/null || true)"
    if [[ "$status" == "200" ]]; then
      local body
      body="$(cat "$response_file")"
      if JSON_INPUT="$body" "${PYTHON_CMD[@]}" - <<'PY'
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

start_server() {
  local port="$1"

  SERVER_LOG="$TEMP_DIR/backend.log"
  info "starting backend on ${HOST}:${port}"
  (
    cd "$ROOT"
    export KMP_DUPLICATE_LIB_OK=TRUE
    export KAYPOH_FAIL_ON_LAYER_LOAD_ERROR=1
    export KAYPOH_PRETTY_LOGS=0
    export PIPELINE_LAYERS=
    exec "${UVICORN_CMD[@]}" kaypoh.backend.main:app --host "$HOST" --port "$port" --log-level warning
  ) >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!

  wait_for_ready "$port"
}

smoke_runtime() {
  local port="$1"

  request GET "http://${HOST}:${port}/health"
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["status"] == "ok"' "/health should report ok"

  request GET "http://${HOST}:${port}/ready"
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["ready"] is True' "/ready should report ready"
  assert_json "$HTTP_BODY" 'payload["pipeline"] == []' "/ready should expose the deterministic-only pipeline"

  request GET "http://${HOST}:${port}/diagnostics"
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["pipeline"] == []' "/diagnostics should expose the deterministic-only pipeline"
  assert_json "$HTTP_BODY" '"redis" not in payload["dependency_status"]' "/diagnostics should not advertise Redis"

  request GET "http://${HOST}:${port}/metrics"
  assert_status 200
  assert_contains "$HTTP_BODY" 'kaypoh_http_requests_total' "/metrics should expose Kaypoh Prometheus counters"

  request POST "http://${HOST}:${port}/review" \
    '{"text":"Send Dr Jane Tan S1234567D the confidential SPA before announcement.","source_jurisdiction":"SG","destination_jurisdiction":"SG","document_type":"email"}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["classification"] == "HIGH_RISK"' "/review should classify sensitive text"
  assert_json "$HTTP_BODY" 'len(payload["findings"]) > 0' "/review should return findings"

  request POST "http://${HOST}:${port}/pseudonymize" \
    '{"text":"Send Dr Jane Tan S1234567D the confidential SPA before announcement.","source_jurisdiction":"SG","destination_jurisdiction":"SG","document_type":"email"}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["privacy_operation"] == "pseudonymize"' "/pseudonymize should identify the reversible operation"
  assert_json "$HTTP_BODY" '"[NRIC_FIN_1]" in payload["pseudonymized_text"] or "[PERSON_1]" in payload["pseudonymized_text"]' "/pseudonymize should replace sensitive spans"
  assert_json "$HTTP_BODY" 'len(payload["mapping"]) > 0' "/pseudonymize should return a mapping"

  request POST "http://${HOST}:${port}/anonymize" \
    '{"text":"Send Dr Jane Tan S1234567D the confidential SPA before announcement.","source_jurisdiction":"SG","destination_jurisdiction":"SG","document_type":"email"}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["privacy_operation"] == "anonymize" and payload["anonymization_mode"] == "placeholder_only"' "/anonymize should expose irreversible v2 mode"
  assert_json "$HTTP_BODY" '"[NRIC_FIN_1]" in payload["anonymized_text"] or "[PERSON_1]" in payload["anonymized_text"]' "/anonymize should replace sensitive spans"
  assert_json "$HTTP_BODY" '"mapping" not in payload and payload["mapping_persisted"] is False' "/anonymize should not return or persist a mapping"

  request POST "http://${HOST}:${port}/redact" \
    '{"text":"Send Dr Jane Tan S1234567D the confidential SPA before announcement.","source_jurisdiction":"SG","destination_jurisdiction":"SG","document_type":"email"}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["privacy_operation"] == "redact" and payload["redaction_style"] == "opaque_text_marker"' "/redact should expose opaque marker mode"
  assert_json "$HTTP_BODY" '"[REDACTED_1]" in payload["redacted_text"]' "/redact should replace sensitive spans with opaque markers"
  assert_json "$HTTP_BODY" 'all("matched_text" not in finding for finding in payload["findings"])' "/redact findings should not return original matched text"

  request POST "http://${HOST}:${port}/classify" \
    '{"text":"Acme Corp will acquire GlobalTech before announcement for $2.5 billion.","entity_id":"Acme Corp"}'
  assert_status 200
  assert_json "$HTTP_BODY" 'payload["classification"] == "HIGH_RISK"' "/classify should wrap engine.review"
  assert_json "$HTTP_BODY" 'payload["lexicon"] is None and payload["model1"] is None and payload["mosaic"] is None' "/classify should not emit archived layer payloads"
}

main() {
  require_cmd "$CURL_BIN"
  TEMP_DIR="$(mktemp -d)"

  info "running preflight"
  (cd "$ROOT" && "${PYTHON_CMD[@]}" scripts/preflight.py --strict)

  info "running focused tests"
  (
    cd "$ROOT"
    "${RUFF_CMD[@]}" check \
      src/kaypoh/backend/main.py \
      src/kaypoh/backend/schemas.py \
      src/kaypoh/configs/runtime.py \
      src/kaypoh/external/public_evidence/inference.py \
      scripts/preflight.py \
      test/test_runtime_settings_validation.py \
      test/test_backend_only_layout.py \
      test/test_tinyfish_and_remote_llm.py \
      test/test_public_evidence_llm.py
    "${PYTHON_CMD[@]}" -m unittest \
      test.test_runtime_settings_validation \
      test.test_backend_only_layout \
      test.test_tinyfish_and_remote_llm \
      test.test_public_evidence_llm \
      test.test_openapi_docs
  )

  local port
  port="$(find_free_port)"
  start_server "$port"
  smoke_runtime "$port"

  info "all verification steps passed"
}

main "$@"
