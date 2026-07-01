# Adapter Telemetry

Status: normative for adapters. Adapter telemetry is correlation evidence only; backend review responses and the review journal remain the source of truth.

Use with `docs/telemetry-feedback-loop.md`, `docs/integrations/privacy.md`, `docs/integrations/failure-semantics.md`, and `test/test_siem_export.py`.

## Schemas

| Surface | Schema version |
|---|---|
| Outlook | `junas.outlook.telemetry.v1` |
| Browser GenAI | `junas.browser.telemetry.v1` |
| DMS | `junas.dms.telemetry.v1` |
| Direct API | `junas.api.telemetry.v1` |
| Normalized SIEM export | `junas.siem.v1` |

Adapters may emit surface-specific telemetry locally. SIEM exporters must normalize those events into the SIEM-safe shape before central export.

## Event Names

| Surface | Event | Meaning |
|---|---|---|
| Outlook | `outlook_review_started` | Message context was collected and `/review` is about to run. |
| Outlook | `outlook_policy_decision_received` | Backend returned a parseable review/policy response. |
| Outlook | `outlook_user_proceeded_after_warning` | Outlook prompt-user path was selected for a warn decision. |
| Outlook | `outlook_user_blocked` | Runtime completed with a block/soft-block/hard-block result. |
| Outlook | `outlook_user_requested_approval` | Policy decision required reviewer approval. |
| Outlook | `outlook_backend_failure` | Context collection, timeout, fetch, non-2xx response, or JSON handling failed. |
| Browser GenAI | `browser_prompt_review_started` | Prompt paste/submit review is about to call the backend. |
| Browser GenAI | `browser_policy_decision_received` | Backend returned a parseable review/policy response. |
| Browser GenAI | `browser_user_canceled` | User declined a warning prompt. |
| Browser GenAI | `browser_user_rewrote` | Adapter applied a rewrite/redaction result. |
| Browser GenAI | `browser_user_proceeded_after_warning` | User accepted a warning prompt. |
| Browser GenAI | `browser_selector_failure` | Required prompt or submit selector was missing. |
| Browser GenAI | `browser_backend_timeout` | Backend call timed out or service worker reported timeout. |
| DMS | `dms_review_started` | DMS hook started review before upload/check-in/share. |
| DMS | `dms_policy_decision_received` | Backend returned a parseable review/policy response. |
| DMS | `dms_upload_held` | Upload/check-in was held pending approval or rewrite. |
| DMS | `dms_upload_blocked` | Upload/check-in was blocked or quarantined. |
| DMS | `dms_backend_failure` | Backend, auth, extraction, or malformed-response failure affected DMS review. |
| Direct API | `api_review_started` | Service caller started a review operation. |
| Direct API | `api_policy_decision_received` | Service caller received a review/policy response. |
| Direct API | `api_backend_failure` | Service caller observed backend/auth/malformed-response failure. |

## Allowed Fields

Adapter telemetry may include:

- `schema_version`
- `event_name`
- `surface`
- `workflow`
- `adapter_version`
- `request_id`
- `review_id`
- `policy_id`
- `policy_version`
- `decision`
- `send_allowed`
- `required_actions`
- `recommended_actions`
- `failure_class`
- `failure_mode`
- `backend_status`
- `error_type`
- `finding_count`
- `blocking_finding_count`
- `degraded_count`
- `degraded_modes`
- `recipient_count`
- `recipient_domain_count`
- `attachment_count`
- `timeout_ms`
- `elapsed_ms_bucket`
- `retry_count`
- `selector_kind`
- `operation`
- `auth_mode`
- `tenant_hash`
- `subject_hash`
- `idempotency_key_hash`
- `document_hash`
- `matter_id_hash`
- `document_id_hash`

Use hashes for tenant, subject, document, matter, idempotency, and finding identifiers when exported outside the backend trust boundary.

## Prohibited Fields

Adapter telemetry, logs, dashboards, and SIEM exports must not include:

- raw prompt, email body, subject, document text, selected text, page text, extracted text, or `document_base64`
- matched text, rewritten text, replacement text, safe-rewrite source spans, or reviewer rationale containing source content
- recipient addresses, attachment filenames, local file paths, matter names, user-entered free text, comments, or support notes
- auth headers, API keys, JWTs, local pairing tokens, daemon secrets, cookies, endpoint URLs, raw idempotency keys, reversible mapping values, or raw audit-pack bytes

If a field can contain customer text, hash or drop it before adapter telemetry leaves memory.

## SIEM Mapping

Normalize adapter telemetry into `junas.siem.v1`:

| Adapter field | SIEM location |
|---|---|
| `event_name` | `action` |
| adapter telemetry class | `event_type="adapter_telemetry"` |
| lifecycle and completion events | `category="audit"` |
| auth denial or suspicious platform bypass | `category="security"` |
| external helper/privacy-ledger events | `category="privacy"` |
| completion state | `outcome` such as `started`, `succeeded`, `blocked`, `warned`, `failed`, `denied`, `canceled`, `held` |
| `request_id` | top-level `request_id` |
| `review_id` | top-level `review_id` |
| all other allowed fields | `details` after sanitization |
| prohibited raw fields | drop or hash according to `src/junas/backend/siem.py` sensitive-key rules |

Recommended outcome mapping:

| Event suffix or event | SIEM outcome |
|---|---|
| `*_review_started` | `started` |
| `*_policy_decision_received` | `succeeded` |
| `*_user_proceeded_after_warning` | `warned` |
| `*_user_canceled` | `canceled` |
| `*_user_rewrote` | `succeeded` |
| `*_user_requested_approval`, `dms_upload_held` | `held` |
| `*_user_blocked`, `dms_upload_blocked` | `blocked` |
| `*_backend_failure`, `browser_backend_timeout`, `browser_selector_failure`, `api_backend_failure`, `dms_backend_failure` | `failed` |

## Required Event Fields

| Event family | Required fields |
|---|---|
| `*_review_started` | `schema_version`, `event_name`, `surface`, `workflow`, `timeout_ms` when applicable, context counts available to the adapter. |
| `*_policy_decision_received` | `request_id`, `review_id`, `policy_id`, `policy_version`, `decision`, `send_allowed`, action names, finding/degraded counts. |
| `*_user_*` | `request_id` or `review_id`, `decision`, completion mode, action names when applicable. |
| `*_backend_failure` / timeout / selector failure | `failure_class`, `failure_mode`, `backend_status`, `error_type`, `timeout_ms` when applicable. |
| DMS upload events | hashed document/matter/version ids, policy decision metadata, hold/block reason code, idempotency key hash. |
| Direct API events | request/review ids, caller surface/workflow, policy decision metadata, status code or failure class. |

## Aggregations

Safe aggregations:

- reviewed documents by `surface` and `workflow`
- allow/warn/block/approval/rewrite rates by policy id/version
- warning override rate by surface and policy version
- backend failure rate by surface, error type, and timeout bucket
- degraded review count by mode and surface
- approval requested/completed counts by reviewer role and policy version
- safe rewrite applied count by surface and required action

Unsafe aggregations:

- top recipient addresses
- common attachment filenames
- prompt phrases, email subjects, document excerpts, matched spans, replacement text
- reviewer comments containing source content
- endpoint URLs or auth failure values

## QA

Before central collection, tests must prove:

- no raw content in `globalThis.junasTelemetrySink(event)` payloads
- no raw content in DOM `junas:telemetry` events
- no raw content in SIEM events after `sanitize_details`
- auth failures redact API keys, JWTs, local tokens, and auth headers
- policy events carry ids, counts, decisions, and action names without full response bodies
- browser and Outlook telemetry fixtures cover backend timeout, malformed response, warn, block, approval, and rewrite paths
