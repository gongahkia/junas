# Pilot Success Rubric

This rubric defines what a pilot must measure before Junas can claim workflow value.
It is not a substitute for customer validation; it is the evidence shape required for
the pilot review.

Use with `docs/deployment-pilot-rollout.md`, `docs/product/value-metrics.md`, and
`scripts/generate_product_value_report.py`.

## Required Measures

| Measure | Required evidence | Pass condition |
|---|---|---|
| Avoided risky sends/shares/submits | Count of reviewed eligible attempts with final `block`, unresolved `approval_required`, `rewrite_required`, `hold_until_public`, or degraded `block_send` before completion. | Baseline, target, measured count, denominator, and denominator confidence are recorded. |
| Accepted rewrites | Count of safe rewrite, redaction, pseudonymization, hold text, or approved replacement actions accepted by users or reviewers. | Rewrite-equivalent action usage is measurable by surface, workflow, policy id/version, and required action. |
| Reviewer decisions | Count of approval, reject, policy exception, accept-risk, request-changes, and hold decisions by authorized reviewer role. | Reviewer actions are journaled with policy id/version, finding ids, role, and taxonomy without raw rationale in reports. |
| Low false-positive fatigue | False-positive override rate plus support-ticket trend for false-positive complaints. | The pilot has a predeclared target and does not expand while false-positive override rate or support volume is above that target. |

## Evidence Sources

| Evidence source | Required fields | Prohibited fields |
|---|---|---|
| Backend metrics | surface, workflow, decision, required action, policy id/version, counts, latency buckets | raw prompt, email body, document text, matched span |
| Review journal | review id, request id, decision, finding ids, reviewer role, action taxonomy, payload hashes | raw reviewer rationale in aggregate exports |
| Adapter telemetry | started, decision received, user action, timeout/failure, completion mode, bounded error type | recipient address, auth header, local token, endpoint URL with secrets |
| Audit pack | manifest hash, journal slice, decision metadata, verification result | unredacted customer text in shared pilot report |
| Support intake | issue class, review id, policy id/version, adapter version, status, owner | raw customer text pasted into tickets |

## Required Report Shape

Every pilot success report must include:

- reporting window and timezone
- cohort size and assigned surface
- selected adapter or direct service integration
- policy id/version
- data sources used
- denominator confidence: `complete`, `partial`, or `unknown`
- avoided risky sends/shares/submits count and rate
- accepted rewrite count and rate
- reviewer decision count and completion status
- false-positive override rate and support-ticket count
- audit-pack export/verification result
- decision: expand, hold, or stop

## Decision Rules

Expand only when all required measures have a measured result and the rollback path has
been tested. Hold when any denominator is `unknown`, reviewer decisions are not
journaled, audit export cannot be verified, or false-positive fatigue exceeds the
predeclared target. Stop when the selected workflow cannot observe eligible attempts,
cannot keep telemetry raw-free, or cannot route blocked users to an approved next action.

Do not use activation rate alone as a success claim. A pilot with many reviews but no
measured avoided sends, no accepted rewrites, no reviewer decisions, or high
false-positive fatigue has not shown workflow value.
