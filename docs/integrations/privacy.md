# Adapter Privacy

Status: normative for adapters. Adapters may expose raw content to the configured Junas backend for review, but they must not persist raw content or leak it through telemetry, logs, storage, ids, or support artifacts.

Use with `docs/integrations/adapter-protocol.md`, `docs/integrations/auth.md`, `docs/integrations/failure-semantics.md`, and `docs/security/data-retention.md`.

## Collection Boundary

Adapters may collect only what is needed for the current workflow attempt.

| Data | May collect | Persistence rule |
|---|---|---|
| Raw text | Email body/subject, selected text, prompt text, document text, extracted DMS text | Memory only until review/rewrite response is handled. |
| Document payload | `document_base64` for text, DOCX, or PDF review | Send to backend only; do not persist in adapter storage. |
| Matched text | Finding spans returned by backend for UI rendering | Render in UI if needed; do not store in adapter telemetry, logs, local storage, extension storage, Office storage, or SIEM fields. |
| Workflow context | `surface`, `workflow`, `actor_role`, recipient domains/count, attachment count, destination, sensitivity label | Store only sanitized summaries needed for retry, audit, or support. |
| Document metadata | MIME type, page count, char count, extraction method, document id, matter id | Store ids/counts where the workflow owner already owns those identifiers; avoid filenames unless required by the system of record. |
| Auth material | API key, JWT, local token | Use only in request headers. Store only in approved adapter settings storage. Never emit to telemetry or logs. |
| Policy result | `request_id`, `review_id`, policy id/version, decision, action names, expiry, counts | Safe to store as adapter retry/support state. |

Adapters must not scrape unrelated page content, collect continuous keystrokes, read browser history/cookies, inspect arbitrary tabs, or collect files that the user/workflow did not submit for review.

## Data Movement

| Deployment | Raw content path | Privacy statement |
|---|---|---|
| Hosted backend | Adapter sends raw content over HTTPS to the configured Junas backend. | Raw content leaves the user device or SaaS hook and enters the tenant backend trust boundary. |
| Local daemon | Adapter sends raw content over loopback or local socket to `junas-local`. | Raw content leaves the browser/Office/desktop runtime but stays on the endpoint unless optional server features are enabled. |
| Direct API | Caller service sends raw content to Junas backend. | Raw content leaves the caller service boundary and enters Junas backend handling. |
| DMS hook | DMS service sends extracted text or document payload to Junas backend. | Raw content stays server-side between DMS and Junas; DMS audit fields store metadata only. |
| Audit-grade optional helpers | Backend may use public-evidence or LLM helper paths only when configured. | Strict profile is deterministic-only; opt-in helper use must produce privacy ledger evidence. |

Adapters must show or document which backend endpoint they call: local daemon, hosted tenant server, or direct API. They must not silently switch raw content from local daemon to hosted server.

## Allowed Storage

Adapters may persist:

- backend origin or local endpoint
- auth mode
- local pairing token or bearer token when the selected mode requires it
- timeout budget
- allowed/blocked host policy
- opt-in toggles such as paste interception or prompt-submit review
- idempotency key hash, not raw key
- `request_id`, `review_id`, decision, action names, policy id/version, `review_expires_at`, timestamps, counts, and degraded-mode names

Adapters must not persist:

- raw prompt, email body, subject, document text, selected text, page text, extracted text, or `document_base64`
- matched text, rewritten text, replacement text, reviewer rationale containing source content, or safe-rewrite source spans
- recipient addresses, attachment filenames, local file paths, matter names, raw idempotency keys, auth headers, API keys, JWTs, local tokens in logs, reversible mapping values, or endpoint URLs with embedded secrets

## Surface Rules

| Surface | May collect | Must not store |
|---|---|---|
| Outlook | Subject, body, recipient domains/count, attachment count, policy response | Message body, subject, full recipient addresses, attachment names, auth tokens, matched text, Smart Alert message bodies in logs/storage. |
| Browser GenAI | Selected/pasted/submitted prompt text for the active target, host policy, selector kind, policy response | Prompt text, rewritten text, page text, matched spans, DOM snapshots, browser history, cookies, arbitrary tab data. |
| DMS | Document payload or extracted text, document id, matter id, version id, actor id, policy response | Raw document text in DMS-visible audit fields, matched text, auth headers, reversible mapping values, sensitive reviewer rationale. |
| Direct API | Caller-provided text/document payload and workflow context | Request/response body logging, matched text in logs, auth headers, mapping values. |
| Word | Active document text and document metadata for review | Raw document text, reversible mappings, auth headers, matched text in Office storage/logs. |
| Desktop watcher | Explicitly selected file/folder/clipboard content | Source overwrite, clipboard persistence, raw file text in notifications/logs, broad recursive scans without opt-in. |

## Telemetry Boundary

Allowed telemetry fields:

- `surface`
- `workflow`
- `request_id`
- `review_id`
- `policy_id`
- `policy_version`
- `decision`
- `send_allowed`
- action names
- finding count
- blocking finding count
- degraded count
- recipient count
- recipient-domain count
- attachment count
- timeout bucket
- backend status
- error type
- idempotency key hash

Prohibited telemetry fields:

- raw prompt, email body, subject, document text, selected text, page text, extracted text, `document_base64`
- matched text, rewritten text, replacement text, reviewer rationale containing source content
- recipient addresses, attachment filenames, file paths, matter names, auth headers, API keys, JWTs, local tokens, endpoint URLs, raw idempotency keys, mapping values

## Training And Feedback

Customer text is not training data by default. Adapters must not send raw prompt, email, document, matched span, reviewer rationale, or audit-pack content to training, fine-tuning, distillation, prompt optimization, or benchmark workflows unless a separate customer-approved artifact path exists.

Feedback loops should use hashes, counts, rule ids, policy context, sanitized reviewer decisions, synthetic fixtures, and scrubbed approved samples. See `docs/feedback-loop.md` and `docs/security/feedback-artifact-retention.md`.

## Privacy QA

Before a surface is marked supported, test:

- no raw content in browser local storage, extension storage, Office runtime storage, session storage, IndexedDB, or localStorage
- no raw content in console logs, network error logs, telemetry events, SIEM events, audit exports, or support bundles
- no auth headers, API keys, JWTs, local pairing tokens, endpoint URLs, raw idempotency keys, or mapping values in logs/telemetry
- no recipient addresses or attachment filenames outside the review request body unless the workflow system of record already owns them
- local daemon mode does not call hosted backend without explicit configuration
- hosted server mode uses HTTPS and exact allowed backend origins
- failed review, timeout, malformed response, and selector failure do not persist raw content
