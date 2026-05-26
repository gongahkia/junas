#!/bin/bash
set -euo pipefail

# Generated from backend.main:app OpenAPI contract.
BASE_URL="${BASE_URL:-http://localhost:8000}"

# POST /classify - Classify one document
curl -sS -X POST "${BASE_URL}/classify" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${KAYPOH_API_KEY:-dev-secret}" \
  -d '{"debug":false,"entity_id":"Acme Corp","include_offending_spans":true,"text":"Acme Corp is acquiring GlobalTech for $2.5 billion next quarter."}'

# POST /classify/batch - Classify multiple documents
curl -sS -X POST "${BASE_URL}/classify/batch" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${KAYPOH_API_KEY:-dev-secret}" \
  -d '{"items":[{"include_offending_spans":true,"text":"Acme Corp is acquiring GlobalTech for $2.5 billion next quarter."},{"debug":false,"text":"Public press release for next week's earnings call."}]}'

# GET /diagnostics - Get runtime diagnostics
curl -sS -X GET "${BASE_URL}/diagnostics"

# GET /health - Get runtime health
curl -sS -X GET "${BASE_URL}/health"

# GET /metrics - Get Prometheus metrics
curl -sS -X GET "${BASE_URL}/metrics"

# GET /ready - Get backend readiness
curl -sS -X GET "${BASE_URL}/ready"
