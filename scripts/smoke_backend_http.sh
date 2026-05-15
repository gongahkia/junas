#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:4000}"

if ! curl -fsS --max-time 3 "${API_BASE_URL}/" >/dev/null 2>&1; then
  echo "[sayless] Backend is not reachable at ${API_BASE_URL}."
  echo "[sayless] Start Phoenix first, then rerun ./scripts/smoke_backend_http.sh."
  exit 1
fi

ROOT_RESPONSE="$(curl -fsS "${API_BASE_URL}/")"

if ! printf '%s' "$ROOT_RESPONSE" | grep -q '"name":"SayLess API"'; then
  echo "[sayless] Backend root response did not include the expected API metadata."
  exit 1
fi

TMP_STATUS_FILE="$(mktemp)"
curl -sS \
  -o /tmp/sayless-smoke-error.json \
  -w "%{http_code}" \
  -X POST "${API_BASE_URL}/api/v1/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "themoviedbmovie",
    "media_id": "550",
    "target_type": "episode",
    "target_id": "1:1",
    "spoiler_level": "standard"
  }' > "$TMP_STATUS_FILE"

HTTP_STATUS="$(cat "$TMP_STATUS_FILE")"
rm -f "$TMP_STATUS_FILE"

if [ "$HTTP_STATUS" != "422" ]; then
  echo "[sayless] Expected 422 from invalid summarize request, got ${HTTP_STATUS}."
  cat /tmp/sayless-smoke-error.json
  exit 1
fi

if ! grep -q '"code":"invalid_target_type"' /tmp/sayless-smoke-error.json; then
  echo "[sayless] Validation smoke response did not contain invalid_target_type."
  cat /tmp/sayless-smoke-error.json
  exit 1
fi

rm -f /tmp/sayless-smoke-error.json
echo "[sayless] Backend HTTP smoke checks passed."
