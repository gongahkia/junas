# Adapter Protocol

Status: normative for adapters. The FastAPI backend is the trust boundary; adapters collect workflow context, call backend endpoints, render policy outcomes, and emit privacy-safe telemetry.

Use this page with `docs/policy/decision-contract.md`, `docs/api/idempotency.md`, and `docs/api/versioning.md`.

## Request Contract

Adapters must call `POST /review` before completing send, submit, upload, or share workflows. Provide exactly one content source:

- `text`: inline email body, prompt text, extracted DMS text, or API text.
- `document_base64`: base64 text, DOCX, or PDF payload with `document_filename` and `document_mime_type` when known.

Core request fields:

| Field | Required | Adapter rule |
|---|---|---|
| `text` or `document_base64` | yes | Send content only in the HTTPS request body. Do not put raw content in URLs, headers, idempotency keys, telemetry, logs, or storage. |
| `source_jurisdiction` | default `SG` | Set from tenant/workspace context when known. |
| `destination_jurisdiction` | default `SG` | Set from recipient, repository, tenant, or workflow destination when known. |
| `document_type` | default `generic` | Use `email`, `prompt`, `memo`, `research_note`, `deck`, `dms_document`, or tenant-specific values. |
| `review_profile` | default `strict` | Use `strict` for deterministic adapter checks unless tenant policy explicitly enables `audit_grade`. |
| `degraded_policy` | default `warn` | Outlook send hooks should use `block_send`; browser and direct API pilots may use tenant-configured behavior. |
| `entity_id` | optional | Issuer/company context for MNPI or public-evidence review. |
| `include_suggestions` | optional | Set false when UI cannot render suggestions. |

Workflow context fields:

| Field | Allowed values or shape | Adapter rule |
|---|---|---|
| `surface` | `api`, `outlook`, `browser_genai`, `dms`, `desktop`, `word`, `slack`, `google_workspace`, `other` | Always set the most specific implemented surface. |
| `workflow` | `api_review`, `email_send`, `prompt_submit`, `document_upload`, `document_review`, `desktop_watch`, `reviewer_override`, `auditor_export`, `collaboration_message`, `other` | Set the user workflow, not the transport mechanism. |
| `actor_role` | `end_user`, `legal_reviewer`, `compliance_admin`, `security_engineer`, `platform_integrator`, `auditor`, `service_account`, `other` | Use role from trusted adapter/admin context. |
| `recipient_domains` | list of domains | Send domains only, not full addresses. Empty lists are allowed. |
| `recipient_count` | integer | Send count when recipients are visible to the adapter. |
| `attachment_count` | integer | Send count; do not send attachment names unless the document payload itself is being reviewed. |
| `sensitivity_label` | string | Preserve upstream label names when available. |
| `external_destination` | boolean | Prefer explicit true/false when the adapter knows boundary status. |
| `requested_action` | `review`, `send`, `submit`, `upload`, `safe_rewrite`, `redact_pii`, `pseudonymize`, `anonymize`, `request_approval`, `hold_until_public`, `cite_public_source`, `proceed_with_warning`, `other` | Set to the action the user is trying to complete. |
| `session_id` | adapter-scoped opaque id | Use a non-sensitive compose, tab, matter, or upload session id. |

Surface defaults:

| Surface | Required context |
|---|---|
| Outlook | `surface="outlook"`, `workflow="email_send"`, `document_type="email"`, `degraded_policy="block_send"`, recipient domains/count, attachment count. |
| Browser GenAI | `surface="browser_genai"`, `workflow="prompt_submit"`, `document_type="prompt"`, submit attempt id in local idempotency state. |
| DMS | `surface="dms"`, `workflow="document_upload"`, `document_type="dms_document"`, matter/document ids in adapter audit metadata, attachment count when relevant. |
| Direct API | `surface="api"`, `workflow="api_review"`, service account or caller role. |

## Response Contract

Adapters must treat `policy_decision` as source of truth. `send_allowed` is a compatibility shortcut derived from `policy_decision.send_allowed`.

Required response fields to retain in adapter state:

| Field | Adapter use |
|---|---|
| `request_id` and `X-Request-ID` | Correlate support, backend logs, SIEM records, and adapter retry state. |
| `review_expires_at` | Require a fresh review when expired before workflow completion. |
| `policy_decision.decision` | Map to allow, warn, block, approval-required, or rewrite-required behavior. |
| `policy_decision.send_allowed` | Decide whether the original workflow may complete now. |
| `policy_decision.required_actions` | Offer these before completion; required beats recommended. |
| `policy_decision.recommended_actions` | Offer non-blocking actions for warn or advisory flows. |
| `policy_decision.blocking_findings` | Reference finding ids only; do not copy matched text into telemetry. |
| `policy_decision.policy_id` / `policy_decision.policy_version` | Pin audit, support, and stale-decision checks. |
| `policy_decision.policy_reasons` | Display to users where appropriate; do not log if tenant policy treats reasons as sensitive. |
| `policy_decision.review_id` | Use for approval, retry, audit, and review-state lookup. |
| `action_catalog` | Offer only actions listed here. |
| `degraded_modes` | Render degraded coverage and apply the configured failure policy. |
| `timings_ms` | Safe for latency telemetry. |

If `policy_decision` is absent, new adapters must treat the response as malformed and apply failure semantics. Legacy clients may read top-level `send_allowed`.

## Auth Headers

Supported adapter auth modes:

| Header | Use |
|---|---|
| `Authorization: Bearer <jwt-or-api-token>` | Hosted backend, API gateway, enterprise browser, DMS, and direct API deployments. |
| `X-API-Key: <key>` | API-key deployments where configured by backend auth. |
| `X-Junas-Local-Token: <token>` | Local daemon pairing for Outlook/browser/desktop pilots. |
| `Idempotency-Key: <opaque-key>` | Adapter retry grouping; v0.1 does not server-dedupe this header. |

Tenant identity comes from validated credentials. Adapters must not rely on caller-supplied tenant ids. Never log auth headers, local pairing tokens, JWTs, API keys, or endpoint URLs with embedded secrets.

## Retry Semantics

Retry only when user intent and reviewed content are unchanged:

| Condition | Adapter behavior |
|---|---|
| Transport timeout or network error | Retry with the same `Idempotency-Key` while the same compose/prompt/upload attempt is active. |
| HTTP 429 or 503 | Back off and retry if the workflow can wait; otherwise apply tenant failure semantics. |
| HTTP 400 or Pydantic validation error | Do not retry automatically; fix adapter payload. |
| HTTP 401 or 403 | Do not retry automatically; show auth failure and emit sanitized telemetry. |
| Malformed JSON or missing `policy_decision` | Treat as malformed response and apply failure semantics. |
| User edits text, recipients, attachments, destination, matter context, or policy profile | Start a new review with a new idempotency key. |
| `review_expires_at` passed | Start a new review before completion. |

Adapters must not replay approval or rewrite results across changed content or changed workflow context.

## Timeouts

Timeout budgets are adapter-owned and must be shorter than the surrounding user workflow can tolerate:

| Adapter | Recommended budget | Rule |
|---|---|---|
| Outlook Smart Alerts | 2500-4000 ms, capped by admin setting | Blocks a send click; prefer fast failure plus visible Smart Alert. |
| Browser GenAI submit | 3000-5000 ms | Blocks a prompt submit; show visible review-unavailable state. |
| DMS upload/check-in | 10-30 s | Server-side workflow can wait longer but must surface hold/quarantine state. |
| Direct API | Caller-defined | Use ordinary service timeout policy plus retry budget. |

Timeout telemetry may include budget, elapsed bucket, backend status, and error type. It must not include content.

## Idempotency Keys

Adapters should send one `Idempotency-Key` per user-intended completion attempt. Construct keys from non-sensitive values:

```text
tenant_or_adapter_instance + surface + workflow + local_attempt_id + normalized_destination + content_hmac + attachment_fingerprint + adapter_attempt_epoch
```

Rules:

- Use keyed HMAC for `content_hmac`.
- Store only the key, `request_id`, `review_id`, decision summary, action names, expiry, and timestamps.
- Rotate the key after any content, recipient, attachment, destination, matter, profile, or tenant-policy change.
- Do not include raw prompt, email body, matched text, recipient addresses, filenames, auth tokens, or mapping values.

See `docs/api/idempotency.md` for per-adapter cache states.

## Telemetry Events

Adapters may emit telemetry only after sanitization. Allowed fields:

- `schema_version`
- `event_name`
- `surface`
- `workflow`
- `request_id`
- `review_id`
- `policy_id`
- `policy_version`
- `decision`
- `send_allowed`
- `required_actions`
- `recommended_actions`
- `finding_count`
- `blocking_finding_count`
- `degraded_count`
- `recipient_count`
- `recipient_domain_count`
- `attachment_count`
- `timeout_ms`
- `elapsed_ms_bucket`
- `backend_status`
- `error_type`
- `idempotency_key_hash`

Prohibited fields:

- raw prompt, email body, document text, page text, or selected text
- matched text, rewritten text, replacement text, or reviewer rationale containing source content
- recipient addresses, attachment filenames, file paths, matter names, user free text, auth headers, tokens, endpoint URLs, mapping values, or raw idempotency keys

Baseline event names:

| Surface | Events |
|---|---|
| Outlook | `outlook_review_started`, `outlook_policy_decision_received`, `outlook_user_proceeded_after_warning`, `outlook_user_blocked`, `outlook_user_requested_approval`, `outlook_backend_failure` |
| Browser GenAI | `browser_prompt_review_started`, `browser_policy_decision_received`, `browser_user_canceled`, `browser_user_rewrote`, `browser_user_proceeded_after_warning`, `browser_selector_failure`, `browser_backend_timeout` |
| DMS | `dms_review_started`, `dms_policy_decision_received`, `dms_upload_held`, `dms_upload_blocked`, `dms_backend_failure` |
| Direct API | `api_review_started`, `api_policy_decision_received`, `api_backend_failure` |

## Follow-On Actions

Adapters may call follow-on endpoints only when the action is present in `action_catalog` and allowed by the current policy decision:

- `/safe-rewrite`
- `/redact-pii`
- `/hold-until-public`
- `/cite-public-source`
- `/request-approval`
- `/pseudonymize`
- `/anonymize`
- `/redact`
- `/documents/scrub`

Follow-on requests must preserve `surface`, `workflow`, `review_id` or request correlation, and the same privacy boundaries as `/review`.
