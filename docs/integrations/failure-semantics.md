# Adapter Failure Semantics

Status: normative for adapter behavior. This page defines how adapters handle backend failure, malformed responses, degraded review coverage, and platform gaps.

Use with `docs/integrations/adapter-protocol.md`, `docs/policy/decision-contract.md`, and `docs/api/idempotency.md`.

## Failure Classes

Adapters must classify failures before deciding whether workflow completion can continue.

| Class | Examples | Required evidence |
|---|---|---|
| Transport failure | DNS failure, TCP failure, TLS failure, CORS failure, timeout, HTTP 429, HTTP 503 | backend status, error type, timeout budget, retry count |
| Auth failure | HTTP 401, HTTP 403, expired local token, invalid JWT, missing API key | auth mode only; no token values |
| Malformed response | non-JSON body, missing `policy_decision`, invalid `policy_decision.decision`, missing `review_id` for approval flow | response shape summary only |
| Backend degraded review | non-empty `degraded_modes`, extraction failure, OCR unavailable, helper unavailable | degraded mode names/counts/statuses |
| Adapter context failure | missing recipient context, missing attachment count, selector failure, unsupported client event, unavailable add-in runtime | adapter surface, workflow, selector/context kind |
| Platform bypass | add-in disabled, extension not installed, mobile/native app, offline mode where event never runs | platform/client state when observable |

Raw prompt, email body, document text, matched text, recipient addresses, filenames, auth headers, tokens, and endpoint URLs must not appear in failure telemetry.

## Completion Modes

| Mode | Meaning | Allowed use |
|---|---|---|
| `allow-on-failure` | Workflow may continue even though no trustworthy policy decision was produced. | Low-risk, read-only, internal, or explicitly admin-approved workflows. Never use as the default for external email send, GenAI prompt submit, DMS external share, approval-required retry, or high-sensitivity labels. |
| `soft-block-on-failure` | Adapter interrupts completion, shows failure state, and may allow user/admin confirmation or retry per tenant policy. | Warn-only pilots, advisory browser flows, Outlook `SoftBlock` platform fallback, or workflows where business continuity beats enforcement. |
| `hard-block-on-failure` | Adapter stops completion until a valid review, valid approval, safe rewrite, or admin break-glass path exists. | Default for controlled send/upload/share gates, high-risk workflows, malformed policy decisions, auth failures, and degraded coverage with `degraded_policy="block_send"`. |
| `admin-configured-degradation` | Adapter applies a tenant/surface-specific rule for degraded review coverage after the backend returns a valid response. | Use only from trusted admin config, not user input. Must record the configured mode in sanitized telemetry/audit metadata. |

Failure mode is separate from policy decision. If a valid response says `policy_decision.decision="block"`, the adapter must block even when its transport failure mode would otherwise allow.

## Backend Degradation

`degraded_policy` controls backend behavior for valid review responses with degraded coverage:

| `degraded_policy` | Backend result | Adapter behavior |
|---|---|---|
| `allow` | Degraded modes may appear while `send_allowed` can remain true. | Show advisory degradation state when UI exists; emit telemetry; complete only if admin config permits `allow-on-failure`. |
| `warn` | Degraded modes are returned for warning display. | Treat as `soft-block-on-failure` for interactive workflows unless tenant policy says advisory-only. |
| `block_send` | Policy can return `block` plus `required_actions=["retry_review"]`. | Treat as `hard-block-on-failure`; user must retry after degradation clears or use approved break-glass. |

Adapters must not hide `degraded_modes` when they affect completion. A degraded but valid review is still different from transport failure: it has `request_id`, `review_id`, policy metadata, and auditable backend evidence.

## Surface Defaults

| Surface | Default failure mode | Notes |
|---|---|---|
| Outlook Smart Alerts send | `hard-block-on-failure` while the event handler runs | Backend timeout, malformed response, auth failure, and degraded `block_send` must block current send. Add-in unavailable before event execution follows Outlook `SoftBlock` platform behavior and is not fail-closed enforcement. |
| Browser GenAI submit | `hard-block-on-failure` once prompt submit is intercepted | Backend timeout or malformed response must not silently submit captured prompt text. Selector failure means no policy decision was evaluated; show visible no-capture state and telemetry when possible. |
| DMS upload/check-in | `hard-block-on-failure` for external or high-sensitivity workflows; otherwise admin-configured | Prefer hold/quarantine for unavailable backend, malformed response, auth failure, or degraded extraction. Store decision metadata only. |
| Direct API | caller/admin-configured | Service callers must define whether the business operation fails closed, queues, retries, or proceeds with advisory audit evidence. |
| Word taskpane | `soft-block-on-failure` | Word taskpane is document review, not true send-time enforcement; show failure and require enforcement elsewhere. |
| Desktop watcher | `allow-on-failure` for original file/clipboard state | Desktop watcher is an opt-in local fallback; failures must not corrupt source files or claim send/upload enforcement. |

## Admin Configuration

Production pilots should keep a surface matrix:

| Config key | Meaning |
|---|---|
| `surface` / `workflow` | Adapter path governed by the rule. |
| `failure_mode` | One of `allow-on-failure`, `soft-block-on-failure`, or `hard-block-on-failure`. |
| `degraded_policy` | Backend request value: `allow`, `warn`, or `block_send`. |
| `timeout_ms` | Adapter timeout budget. |
| `retry_budget` | Maximum automatic retries for unchanged content and context. |
| `break_glass_roles` | Roles allowed to override a failure state. |
| `allowed_failure_classes` | Failure classes eligible for soft-block or allow-on-failure. |
| `telemetry_required` | Whether sanitized failure telemetry must be emitted before completion. |

Admins must not configure user-controlled fields to weaken failure behavior. Adapter settings stored in browser, Office, or desktop storage are local hints; backend tenant policy and deployment configuration remain authoritative.

## Retry And Break-Glass

- Retry only with the same `Idempotency-Key` when content, recipients, attachments, destination, matter context, profile, and tenant policy are unchanged.
- Do not retry HTTP 400, 401, or 403 automatically.
- Do not convert malformed response into allow.
- Break-glass must record actor role, reason code, timestamp, surface, workflow, request/review id when available, and failure class.
- Break-glass records must not contain raw content, matched text, auth material, endpoint URL, or raw idempotency key.
- Approval retry still requires backend policy satisfaction; adapters are not approval authorities.

## Telemetry

Failure telemetry may include:

- `surface`
- `workflow`
- `failure_class`
- `failure_mode`
- `backend_status`
- `error_type`
- `timeout_ms`
- `retry_count`
- `degraded_count`
- `degraded_modes`
- `policy_id`
- `policy_version`
- `request_id`
- `review_id`
- `idempotency_key_hash`

Failure telemetry must not include:

- raw prompt, email body, document text, page text, selected text, matched text, rewritten text, or replacement text
- recipient addresses, attachment filenames, file paths, matter names, user-entered notes, auth headers, JWTs, API keys, local pairing tokens, endpoint URLs, mapping values, or raw idempotency keys

## Minimum QA

Before a surface is marked supported, test each mode:

- backend timeout
- backend unavailable
- HTTP 401/403 auth failure
- HTTP 429/503 retryable failure
- malformed JSON
- valid response without `policy_decision`
- valid response with `degraded_modes`
- expired `review_expires_at`
- changed content/context after review
- platform unavailable path, such as disabled add-in or extension not installed
