#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:4000}"
SOURCE="${SOURCE:-myanimelistanime}"
QUERY="${QUERY:-rezero}"
SPOILER_LEVEL="${SPOILER_LEVEL:-standard}"
MODE="${MODE:-validation}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[sayless] python3 is required for smoke_api.sh"
  exit 1
fi

if ! curl -fsS --max-time 3 "${API_BASE_URL}/" >/dev/null 2>&1; then
  echo "[sayless] Backend is not reachable at ${API_BASE_URL}."
  echo "[sayless] Start the API first, then rerun ./scripts/smoke_api.sh."
  exit 1
fi

if [ "$MODE" = "validation" ]; then
  TMP_STATUS_FILE="$(mktemp)"

  curl -sS \
    -o /tmp/sayless-smoke-api-error.json \
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
    echo "[sayless] Expected 422 from validation smoke request, got ${HTTP_STATUS}."
    cat /tmp/sayless-smoke-api-error.json
    exit 1
  fi

  if ! grep -q '"code":"invalid_target_type"' /tmp/sayless-smoke-api-error.json; then
    echo "[sayless] Validation smoke response did not include invalid_target_type."
    cat /tmp/sayless-smoke-api-error.json
    exit 1
  fi

  rm -f /tmp/sayless-smoke-api-error.json
  echo "[sayless] Deterministic API validation smoke checks passed."
  exit 0
fi

if [ "$MODE" != "live" ]; then
  echo "[sayless] Unsupported MODE '${MODE}'. Use MODE=validation or MODE=live."
  exit 1
fi

echo "[sayless] Searching '$QUERY' on source '$SOURCE'..."
SEARCH_RESPONSE="$(curl -fsS "${API_BASE_URL}/api/v1/search?source=${SOURCE}&query=${QUERY}")"

MEDIA_ID="$(
  printf '%s' "$SEARCH_RESPONSE" | python3 -c '
import json, sys
data = json.load(sys.stdin)["data"]["results"]
if not data:
    raise SystemExit(1)
print(data[0]["id"])
'
)"

echo "[sayless] Using media id: ${MEDIA_ID}"
TARGETS_RESPONSE="$(curl -fsS "${API_BASE_URL}/api/v1/media/${SOURCE}/${MEDIA_ID}/targets")"

TARGET_INFO="$(
  printf '%s' "$TARGETS_RESPONSE" | python3 -c '
import json, sys
data = json.load(sys.stdin)["data"]["targets"]
if not data:
    raise SystemExit(1)
first = data[0]
print(first["type"])
print(first["id"])
'
)"

TARGET_TYPE="$(printf '%s' "$TARGET_INFO" | sed -n '1p')"
TARGET_ID="$(printf '%s' "$TARGET_INFO" | sed -n '2p')"

echo "[sayless] Using target ${TARGET_TYPE}:${TARGET_ID}"
echo "[sayless] Requesting summary..."

curl -fsS \
  -X POST "${API_BASE_URL}/api/v1/summarize" \
  -H "Content-Type: application/json" \
  -d "{
    \"source\": \"${SOURCE}\",
    \"media_id\": \"${MEDIA_ID}\",
    \"target_type\": \"${TARGET_TYPE}\",
    \"target_id\": \"${TARGET_ID}\",
    \"spoiler_level\": \"${SPOILER_LEVEL}\"
  }"

echo
