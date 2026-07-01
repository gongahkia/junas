# Product Personas

## End User

Job-to-be-done: before sending email, pasting into GenAI, or uploading a document, I need quick guidance on whether the content is safe to share and what action will make it safe without leaving my workflow.

- Needs: low-friction review, clear allow/warn/block state, safe rewrite options, minimal legal jargon, no duplicate data entry.
- Risks: ignores standalone tools, over-shares to avoid delays, cannot distinguish PII from MNPI or public from non-public context.
- Success signal: reviewed-send rate rises without a high false-positive override rate.

## Legal Reviewer

Job-to-be-done: when a user requests approval or challenges a finding, I need enough evidence and context to decide, record rationale, and preserve an audit trail without exposing more raw text than necessary.

- Needs: finding-level rationale, policy reasons, source/destination context, reviewer actions, tamper-evident journal entries when journal keys are configured, override taxonomy.
- Risks: receives noisy queues, loses rationale outside the system, approves without policy context, cannot replay decisions.
- Success signal: approval decisions are timely, reasoned, and replayable from the journal.

## Compliance Admin

Job-to-be-done: I need to configure tenant policy, monitor adoption and exceptions, export audit evidence, and prove controls are operating without turning Junas into the only DLP control.

- Needs: policy profiles, value metrics, false-positive trends, audit exports, retention settings, SIEM mapping, deployment boundaries.
- Risks: adapter support is overstated, policy drift is invisible, metrics require raw content, rollout tries too many surfaces at once.
- Success signal: policy decisions, overrides, blocked sends, and audit exports are measurable by surface and policy version.

## Security Engineer

Job-to-be-done: I need Junas integrations to preserve tenant boundaries, avoid sensitive logs, enforce auth, and emit privacy-safe telemetry that fits existing security architecture.

- Needs: stable API contract, auth model, tenant isolation, body-size caps, CORS/CSRF controls, no-body-log tests, SIEM-safe fields.
- Risks: adapters store prompts locally, caller-supplied tenant ids are trusted, public URL fetches create SSRF exposure, logs leak content.
- Success signal: integration tests prove tenant isolation, privacy-safe events, and fail-closed behavior for protected paths.

## Platform Integrator

Job-to-be-done: I need to connect Junas to DMS, API gateways, browser/email surfaces, or workflow tools using predictable schemas and failure semantics.

- Needs: OpenAPI examples, idempotency guidance, response decision contract, timeout/retry behavior, compatibility matrix, adapter certification checklist.
- Risks: schema changes break clients, duplicate reviews confuse users, unsupported surfaces are treated as production-ready.
- Success signal: integrations can use direct HTTP first, then add one workflow adapter with documented maturity and QA evidence.
