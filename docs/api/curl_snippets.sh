#!/bin/bash
set -euo pipefail

# Generated from kaypoh.backend.main:app OpenAPI contract.
BASE_URL="${BASE_URL:-http://localhost:8000}"

# POST /anonymize - Anonymize a document irreversibly
curl -sS -X POST "${BASE_URL}/anonymize" \
  -H "Content-Type: application/json" \
  -d '{"destination_jurisdiction":"US","document_type":"email","include_mnpi_scalars":true,"include_suggestions":true,"source_jurisdiction":"SG","text":"Send Dr Jane Tan S1234567D the confidential draft. Acme Corp expects a $2.5 billion acquisition before announcement."}'

# POST /cite-public-source - Cite audit-grade public evidence
curl -sS -X POST "${BASE_URL}/cite-public-source" \
  -H "Content-Type: application/json" \
  -d '{"destination_jurisdiction":"US","document_type":"email","entity_id":"Acme Corp","requested_action":"cite_public_source","review_profile":"audit_grade","source_jurisdiction":"SG","surface":"outlook","text":"Acme Corp will acquire GlobalTech before announcement.","workflow":"email_send"}'

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

# POST /documents/scrub - Scrub document metadata
curl -sS -X POST "${BASE_URL}/documents/scrub" \
  -H "Content-Type: application/json" \
  -d '{"document_base64":"string"}'

# GET /health - Get runtime health
curl -sS -X GET "${BASE_URL}/health"

# POST /hold-until-public - Hold high-risk MNPI until public
curl -sS -X POST "${BASE_URL}/hold-until-public" \
  -H "Content-Type: application/json" \
  -d '{"allowed_actions":["hold_until_public"],"destination_jurisdiction":"US","document_type":"email","requested_action":"hold_until_public","source_jurisdiction":"SG","surface":"outlook","text":"Acme Corp announced its acquisition of GlobalTech in a public press release.","workflow":"email_send"}'

# POST /local/pairing/approve - Approve local daemon pairing
curl -sS -X POST "${BASE_URL}/local/pairing/approve" \
  -H "Content-Type: application/json" \
  -H "X-Kaypoh-Local-Token: ${KAYPOH_LOCAL_DAEMON_TOKEN}" \
  -d '{"pairing_id":"sample-id","pairing_code":"string"}'

# POST /local/pairing/claim - Claim approved local daemon pairing
curl -sS -X POST "${BASE_URL}/local/pairing/claim" \
  -H "Content-Type: application/json" \
  -d '{"pairing_id":"sample-id","pairing_code":"string"}'

# POST /local/pairing/start - Start local daemon pairing
curl -sS -X POST "${BASE_URL}/local/pairing/start" \
  -H "Content-Type: application/json" \
  -d '{}'

# GET /local/pairing/status - Get local daemon pairing status
curl -sS -X GET "${BASE_URL}/local/pairing/status"

# GET /metrics - Get Prometheus metrics
curl -sS -X GET "${BASE_URL}/metrics"

# POST /pseudonymize - Pseudonymize a document before sending
curl -sS -X POST "${BASE_URL}/pseudonymize" \
  -H "Content-Type: application/json" \
  -d '{"destination_jurisdiction":"US","document_type":"email","include_mnpi_scalars":true,"include_suggestions":true,"persist_mapping":true,"source_jurisdiction":"SG","text":"Send Dr Jane Tan S1234567D the confidential draft. Acme Corp expects a $2.5 billion acquisition before announcement."}'

# GET /ready - Get backend readiness
curl -sS -X GET "${BASE_URL}/ready"

# POST /redact - Redact a document with opaque markers
curl -sS -X POST "${BASE_URL}/redact" \
  -H "Content-Type: application/json" \
  -d '{"destination_jurisdiction":"SG","document_type":"email","include_suggestions":true,"source_jurisdiction":"SG","text":"Send Dr Jane Tan S1234567D the confidential draft."}'

# POST /redact-pii - Redact PII only
curl -sS -X POST "${BASE_URL}/redact-pii" \
  -H "Content-Type: application/json" \
  -d '{"allowed_actions":["redact_pii"],"destination_jurisdiction":"US","document_type":"email","requested_action":"redact_pii","source_jurisdiction":"SG","surface":"outlook","text":"Send Dr Jane Tan S1234567D to external counsel.\n\nAcme Corp will acquire GlobalTech before announcement.","workflow":"email_send"}'

# POST /reidentify - Reidentify previously anonymized text
curl -sS -X POST "${BASE_URL}/reidentify" \
  -H "Content-Type: application/json" \
  -d '{"anonymized_text":"Send [PERSON_1] [NRIC_FIN_1] the draft.","mapping":[{"original_text":"Dr Jane Tan","placeholder":"[PERSON_1]"},{"original_text":"S1234567D","placeholder":"[NRIC_FIN_1]"}]}'

# POST /request-approval - Request reviewer approval
curl -sS -X POST "${BASE_URL}/request-approval" \
  -H "Content-Type: application/json" \
  -d '{"finding_ids":["pii:sg_nric_fin:25:34:0"],"reason_code":"rewrite_required","review_id":"b7f1faad-1d2b-4c35-9f60-6b7f08d6fbfb"}'

# POST /review - Review a document before sending
curl -sS -X POST "${BASE_URL}/review" \
  -H "Content-Type: application/json" \
  -d '{"actor_role":"end_user","attachment_count":1,"destination_jurisdiction":"SG","document_type":"research_note","entity_id":"Acme Corp","external_destination":true,"include_suggestions":true,"recipient_count":1,"recipient_domains":["example.com"],"requested_action":"send","sensitivity_label":"confidential","source_jurisdiction":"SG","surface":"outlook","text":"Please send the draft deck to Tan S1234567D. Acme Corp has confidential Q1 guidance.","workflow":"email_send"}'

# GET /review/{review_id} - Inspect review session state
curl -sS -X GET "${BASE_URL}/review/{review_id}"

# POST /review/{review_id}/decision - Record a per-finding decision
curl -sS -X POST "${BASE_URL}/review/{review_id}/decision" \
  -H "Content-Type: application/json" \
  -d '{"action":"reject","finding_id":"pii:named_person:5:16:0","rationale":"Defined term in contract preamble, not a real party","replacement_text":""}'

# POST /safe-rewrite - Safely rewrite a document deterministically
curl -sS -X POST "${BASE_URL}/safe-rewrite" \
  -H "Content-Type: application/json" \
  -d '{"allowed_actions":["safe_rewrite","redact_pii","hold_until_public"],"allowed_finding_ids":["pii:sg_nric_fin:25:34:0"],"destination_jurisdiction":"US","document_type":"email","requested_action":"safe_rewrite","source_jurisdiction":"SG","surface":"outlook","text":"Send Dr Jane Tan S1234567D the confidential draft before announcement.","workflow":"email_send"}'
