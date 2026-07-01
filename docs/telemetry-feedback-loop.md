# Telemetry Feedback Loop

Status: requirements. This document defines how adapter telemetry, policy outcomes,
and reviewer decisions connect without storing raw prompts, email bodies, document
text, or matched spans in telemetry.

## Boundary

The backend review response and review journal remain the source of truth. Adapter
telemetry is correlation evidence only. It may explain what surface invoked review,
which policy outcome was shown, and whether the user or workflow completed, but it
must not become a second content store.

Use stable ids and hashes to join records:

| Join key | Source | Use |
|---|---|---|
| `request_id` | Adapter or backend | Correlates one adapter call with backend timing and failure telemetry. |
| `review_id` | Backend review response | Connects adapter outcome, approval request, reviewer decision, and audit pack. |
| `policy_id` / `policy_version` | `policy_decision` | Groups outcomes by active policy without copying policy TOML. |
| `surface` / `workflow` | Adapter | Groups Outlook send, browser prompt, DMS check-in, desktop, and direct API usage. |
| `finding_id` or finding-id hash | Review response / journal | Links decisions to findings without copying `matched_text`. |
| `document_hash` | Backend request or journal | Detects repeat reviews without storing the document. |
| `idempotency_key_hash` | Adapter | Groups retries without storing raw idempotency values. |

## Event Chain

| Step | Event | Required fields | Prohibited fields |
|---|---|---|---|
| Adapter starts review | `adapter_review_started` | `request_id`, `surface`, `workflow`, `tenant_id`, `adapter_version`, `document_hash` when available | prompt text, email body, document text, recipient address, filename |
| Backend records review | `review_started` | `review_id`, `request_id`, finding counts, risk scores, policy id/version, source/destination jurisdiction | raw content, `matched_text`, attachment bytes |
| Adapter receives outcome | `adapter_policy_outcome_received` | `review_id`, `request_id`, `decision`, `required_actions`, `recommended_actions`, timings, degraded state | full response body, finding text, suggestions containing original text |
| Approval is requested | `approval_requested` | `review_id`, approval id, required reviewer roles, reason code, SLA fields | raw rationale, raw prompt/email/document |
| Reviewer decides | `decision_recorded` | `review_id`, finding id/hash, decision action, decision taxonomy, reviewer id, reviewer role | raw reviewer rationale, copied matched span, customer text |
| Adapter completes or stops | `adapter_completion_recorded` | `review_id`, final adapter outcome, user proceeded flag, approval id when used, elapsed seconds | sent email body, submitted prompt, uploaded document |

## Policy Outcome Mapping

Adapters must copy only policy metadata into telemetry:

- `allow`: record passive completion counts and latency.
- `warn`: record warning shown, user proceeded or canceled, and warning reason codes.
- `block`: record blocked workflow and required action ids.
- `approval_required`: record approval request id and pending/completed status.
- `rewrite_required`: record safe-rewrite offered/applied status without storing original or rewritten text.
- degraded responses: record degraded reason code and configured degradation policy.

`policy_reasons` may be logged only as stable reason codes or policy ids. If the
human-readable reason includes user text, hash or drop it before telemetry export.

## Reviewer Decision Mapping

Reviewer decisions connect back through `review_id` and finding ids. The journal stores
authorized `decision_recorded` actions and the feedback taxonomy in
`docs/policy/decision-taxonomy.md`. Downstream dashboards may aggregate:

- false-positive decisions by rule, surface, workflow, policy id/version, and tenant
- false-negative candidate queues by rule and approval-required reason code
- warning override rate by surface and policy version
- approval completion latency by reviewer role and decision action
- safe-rewrite acceptance by surface and required action

Aggregations must use counts, ids, hashes, role names, rule names, and timestamps only.

## Example Safe Event

```json
{
  "schema_version": "junas.adapter_telemetry.v1",
  "event_name": "adapter_policy_outcome_received",
  "tenant_id": "tenant_demo",
  "request_id": "req_01HV",
  "review_id": "rev_01HV",
  "surface": "outlook",
  "workflow": "email_send",
  "policy_id": "default",
  "policy_version": "2026-06-14",
  "decision": "approval_required",
  "required_actions": ["request_approval", "hold_until_public"],
  "finding_count": 3,
  "blocking_finding_count": 2,
  "document_hash": "sha256:4f4f...",
  "elapsed_ms": 742,
  "degraded": false
}
```

## Must Not Store

Telemetry, dashboards, SIEM exports, and adapter logs must not store:

- raw prompts
- email subject or body text
- document text
- matched spans or `matched_text`
- recipient addresses
- filenames or attachment names
- attachment bytes
- auth header values, API keys, JWTs, local pairing tokens, or cookies
- reversible mapping values
- raw reviewer rationale when it contains customer text

## Related Documents

- `docs/feedback-loop.md`
- `docs/policy/decision-contract.md`
- `docs/policy/journal-replay.md`
- `docs/policy/decision-taxonomy.md`
- `docs/admin-console/telemetry-requirements.md`
- `docs/product/value-metrics.md`
- `test/test_siem_export.py`
