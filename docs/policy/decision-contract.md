# Policy Decision Contract

Adapters must treat `policy_decision` as the source of truth and keep `send_allowed` only as a compatibility shortcut.

## Common Rules

- Always preserve `review_id` for retry, approval, audit, and user-support flows.
- Use `docs/integrations/sequence-diagrams.md#reviewer-approval-and-adapter-retry` for the approval retry flow.
- Replay reviewer decisions according to `docs/policy/journal-replay.md`; adapters must not reinterpret legacy `accept`, `reject`, or `rewrite` actions.
- Use `docs/api/idempotency.md` for adapter-local retry grouping before issuing duplicate review requests.
- Display `policy_reasons` without adding raw prompt, email, document, or matched-span text to logs.
- Offer only actions present in `action_catalog`, then prioritize `required_actions` over `recommended_actions`.
- Treat `blocking_findings` as identifiers only; fetch or render finding details from the review response according to adapter privacy rules.
- If `policy_decision` is missing, legacy clients may read `send_allowed`; new adapters should fail per their configured degradation policy.

## Decisions

| Decision | Adapter behavior | Completion behavior |
|---|---|---|
| `allow` | Continue the workflow without interrupting the user. Optional passive telemetry may record decision, surface, workflow, policy id/version, and timing. | Send/share/submit may complete immediately. |
| `warn` | Show a non-blocking warning with relevant `policy_reasons`, recommended actions, and proceed/cancel controls where the surface supports them. | Completion may proceed immediately when the user confirms or when tenant policy allows silent warning. |
| `block` | Stop completion and show required actions. Do not provide a bypass unless a later review with public evidence or reviewer approval changes the decision. | Send/share/submit must not complete. |
| `approval_required` | Stop completion and route to reviewer workflow. Show reviewer-role requirement and preserve `review_id` for the approval retry path. | Completion must wait for recorded approval and a follow-up review/decision. |
| `rewrite_required` | Stop completion and offer safe rewrite, redaction, pseudonymization, or request-approval actions as allowed by `required_actions` and `action_catalog`. | Completion must wait for transformed content or reviewer approval. |

## Required Actions

| Action | Expected adapter behavior |
|---|---|
| `retry_review` | Ask the user or system to retry after degraded coverage is resolved. Do not submit original content. |
| `redact_pii` | Offer `/redact-pii` for irreversible PII replacement while leaving MNPI visible and flagged. |
| `safe_rewrite` | Offer deterministic safe rewrite when the API supports it. |
| `request_approval` | Call `/request-approval` with `review_id` to record a pending approval and display returned reviewer-role requirements. |
| `hold_until_public` | Offer `/hold-until-public` so high-severity MNPI receives hold text, a user reason, and audit rationale. |
| `cite_public_source` | Offer `/cite-public-source` where audit-grade review can return source URL, retrieval timestamp, and privacy-ledger entry. |
| `proceed_with_warning` | Allow proceed only for `warn` decisions or tenant-approved warning flows. |

## Failure Behavior

- Backend timeout: follow adapter degradation policy, then emit telemetry without raw content.
- Malformed response: treat as no valid policy decision and fail per adapter degradation policy.
- Missing `review_id`: do not create approval or retry flows; fail the adapter check unless the workflow is read-only.
- Policy id/version mismatch: continue only when the pinned schema/version policy allows it; otherwise block or require admin intervention.
- User edits content after review: require a new review. If content and workflow context are unchanged, require re-review after `review_expires_at`.
