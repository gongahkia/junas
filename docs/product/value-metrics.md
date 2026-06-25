# Product Value Metrics

Metrics must be computed from privacy-safe events, hashes, counts, policy ids, surface names, and timestamps. Do not store raw prompts, email bodies, document text, matched spans, reversible mappings, or authorization headers to calculate these metrics.

| Metric | Definition | Numerator | Denominator |
|---|---|---|---|
| Activation rate | Share of eligible users or tenants that trigger at least one Junas review in the measurement window. | Unique active users or tenants with one or more review events. | Eligible assigned users or onboarded tenants. |
| Reviewed-send rate | Share of eligible send/share/submit attempts that receive a Junas review before completion. | Attempts with completed `/review` decision before send/share/submit. | Eligible attempts observed by the adapter or direct integration. |
| Accepted-finding rate | Share of findings that users or reviewers accept without rejecting as false positive or policy exception. | Findings accepted, left unchallenged after decision completion, or acted on through rewrite/redaction/approval. | Findings returned to users or reviewers. |
| False-positive override rate | Share of findings overridden as false positive by an authorized reviewer or approved taxonomy path. | Findings with reviewer decision taxonomy `false_positive`. | Findings that reached reviewer/user decision. |
| Safe-rewrite usage | Share of reviewed workflows that use a safe rewrite, redaction, pseudonymization, hold text, or approved replacement action. | Review sessions with a completed safe-rewrite or rewrite-equivalent action. | Review sessions where rewrite action was offered or required. |
| Blocked-send rate | Share of reviewed send/share/submit attempts blocked by policy and not completed without approval. | Attempts with final decision `block` or unresolved `approval_required` before completion. | Reviewed send/share/submit attempts. |
| Audit-pack export rate | Share of tenants, matters, or review cohorts that export audit evidence during the measurement window. | Audit-pack exports completed with verified journal evidence. | Eligible tenants, matters, review cohorts, or admin-requested export jobs. |

## Reporting Rules

- Segment by surface, workflow, tenant, policy id/version, decision, required action, and adapter maturity.
- Use counts and hashes only for sensitive artifacts.
- Report confidence gaps when the adapter cannot observe the denominator.
- Do not compare adapters unless their eligible-attempt denominator is measured the same way.
- Treat a high activation rate without reviewed-send rate, accepted-finding rate, or audit-pack usage as weak evidence of product value.
