# Redactor-To-Review Migration Guide

This guide moves older "redactor", "anonymizer", or `/classify`-first integrations to the current review and policy-decision model.

## What Changed

The old framing treated Junas as a transformation tool: call `/pseudonymize`, `/anonymize`, or `/redact`, then send the transformed text.

The current framing treats Junas as a pre-send review boundary: call `/review`, read `policy_decision`, show required/recommended actions from `action_catalog`, then call a follow-on action only when policy and user workflow require it.

Existing transformation endpoints remain available. They are no longer the recommended first call for new send/share/submit integrations.

## Migration Map

| Old framing | Current framing |
|---|---|
| "Run the redactor before sharing." | "Run `/review` before completion, then apply policy-approved action." |
| `/classify` decides risk. | `/review` returns findings, `policy_decision`, `action_catalog`, `review_id`, and `review_expires_at`. |
| `send_allowed` is the primary decision. | `policy_decision.send_allowed` is the primary decision; top-level `send_allowed` is compatibility. |
| `/pseudonymize` is the default. | `/pseudonymize` is for reversible placeholder workflows that need `/reidentify`. |
| `/anonymize` means no risk remains. | `/anonymize` is irreversible placeholder output over detected spans; residual context risk remains. |
| `/redact` is the only remediation. | `/redact-pii`, `/safe-rewrite`, `/hold-until-public`, `/cite-public-source`, and `/request-approval` are policy-routed actions. |
| UI copy says "anonymize/redact this." | UI copy says "review, decide, then rewrite/redact/approve/hold when required." |

## Step-By-Step Migration

1. Inventory clients that call `/classify`, `/pseudonymize`, `/anonymize`, or `/redact` before any `/review`.
2. Add a `/review` call with `surface`, `workflow`, destination context, `document_type`, and tenant auth before workflow completion.
3. Route UI and adapter behavior from `policy_decision.decision`, `required_actions`, `recommended_actions`, and `action_catalog`.
4. Preserve `request_id`, `review_id`, `policy_id`, `policy_version`, `review_expires_at`, and timing fields for audit/support.
5. Call `/safe-rewrite`, `/redact-pii`, `/hold-until-public`, `/cite-public-source`, `/request-approval`, `/pseudonymize`, `/anonymize`, or `/redact` only when that action is allowed by the response and needed by the workflow.
6. Require a fresh `/review` when text, recipients, attachments, destination, matter context, policy version, or `review_expires_at` changes.
7. Update user-facing copy, examples, runbooks, and dashboards from "redaction/anonymization outcome" to "review decision, action, and audit evidence."

## Endpoint Compatibility

- `/classify` and `/classify/batch` remain compatibility shims. New clients should use `/review`.
- `/pseudonymize`, `/anonymize`, `/redact`, `/redact-pii`, `/safe-rewrite`, `/hold-until-public`, `/cite-public-source`, `/request-approval`, `/reidentify`, and `/documents/scrub` remain root endpoints in v0.1.
- `/v1` aliases are not exposed yet. Pin the root endpoint OpenAPI snapshot used during adapter certification.

## Copy Changes

Use this wording:

- "Review before send/share/submit."
- "Policy decision: allow, warn, block, approval required, or rewrite required."
- "Safe rewrite, redaction, approval, hold, citation, or pseudonymization are follow-on actions."
- "Audit evidence uses hashes, counts, policy ids, decisions, and action metadata rather than raw body logs."

Avoid this wording:

- "The redactor makes sharing safe."
- "Anonymization removes all risk."
- "The adapter enforces every send or paste."
- "A transformation endpoint is the policy decision."

## References

- [`docs/faq/developer.md`](../faq/developer.md)
- [`docs/schema.md`](../schema.md)
- [`docs/policy/decision-contract.md`](../policy/decision-contract.md)
- [`docs/api/versioning.md`](../api/versioning.md)
- [`docs/api/idempotency.md`](../api/idempotency.md)
