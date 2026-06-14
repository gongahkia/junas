# Request IDs and Adapter Idempotency

Kaypoh v0.1 returns a server-generated `request_id` in review-like responses and the `X-Request-ID` response header. For `/review`, that value is also the review-session id used by `/review/{review_id}` and `/review/{review_id}/decision`.

The backend does not currently deduplicate repeated `POST /review` calls. Adapters must provide local idempotency for retry, double-click, Smart Alerts re-entry, browser submit interception, and network retry flows.

## Fields

| Field | Owner | Scope | Adapter use |
|---|---|---|---|
| `X-Request-ID` response header | Backend | One HTTP request | Correlate adapter logs, backend logs, SIEM events, and support tickets. |
| `request_id` response field | Backend | One review operation | Store as the review id for retry, approval, audit, and decision recording. |
| `policy_decision.review_id` | Backend | Same review operation | Prefer this nested value when routing policy actions. |
| `Idempotency-Key` request header | Adapter | Adapter-defined retry group | Generate and retain locally for retry grouping. v0.1 has no server-side dedupe behavior for this header. |

## Adapter Key Construction

Adapters should build one idempotency key per user-intended completion attempt:

```text
tenant_or_adapter_instance + surface + workflow + draft_or_dom_identity + normalized_destination + content_hmac + attachment_fingerprint + adapter_attempt_epoch
```

Rules:

- Use a keyed HMAC for `content_hmac` when the key may be persisted, logged, or sent to telemetry.
- Include recipient domains, recipient count, and attachment count when the surface exposes them.
- Include the message compose id, draft id, tab id, DOM form id, or equivalent local identity when available.
- Rotate `adapter_attempt_epoch` when the user edits body text, subject/prompt text, recipients, attachment set, destination surface, or tenant policy context.
- Do not include raw prompt, email body, matched text, recipients, or filenames in the idempotency key.

## Retry Behavior

Adapters should keep a short-lived local cache keyed by the idempotency key:

- `in_flight`: suppress duplicate UI prompts and attach later callbacks to the first request.
- `succeeded`: reuse the stored `request_id`, `policy_decision`, `action_catalog`, and `review_expires_at` if still valid.
- `failed_timeout`: retry with the same idempotency key when the user intent and content are unchanged.
- `failed_validation` or `failed_auth`: do not retry automatically; show the adapter degradation state.

Recommended TTL is one compose or submit attempt, capped at 5 minutes for Outlook Smart Alerts and 2 minutes for browser GenAI submit interception. A tenant can use shorter TTLs for high-risk workflows.

## Outlook Smart Alerts

- Create the key when `OnMessageSend` fires.
- Reuse the key when Outlook re-enters the handler for the same draft without content, recipient, or attachment changes.
- Store only the key, backend `request_id`, decision summary, expiry, and timestamps in adapter memory.
- When Outlook retries after a backend timeout, use the same key and replace the cached state only if a later successful response arrives.

## Browser GenAI Adapter

- Create the key on submit interception, not on every keystroke.
- Treat a changed textarea/editor value as a new key.
- Suppress duplicate modal prompts for double-clicks or Enter-key repeats while the first review is in flight.
- Clear the key after successful submit, cancel, page navigation, or editor mutation.

## Server-Side Compatibility

Future server-side idempotency may use `Idempotency-Key` plus tenant identity and endpoint path to return the first completed response for the same adapter retry group. Until that exists, repeated `POST /review` calls create separate review sessions, so adapter-local dedupe is required.
