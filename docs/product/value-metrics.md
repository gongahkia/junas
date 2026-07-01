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

## Privacy-Safe Aggregation Model

Product value reporting must use event counters, ids, keyed hashes, and bounded labels. Raw content is allowed only in the request body sent to the configured backend trust boundary for review. It must not be copied into metrics stores, dashboard extracts, SIEM indexes, telemetry payloads, CSV exports, alert labels, support tickets, or aggregation keys.

Allowed aggregation inputs:

- `surface`, `workflow`, adapter maturity, tenant hash, cohort hash, policy id/version, decision, required action, degraded mode, timeout bucket, approval status, reviewer role, and rewrite action.
- `review_id`, `request_id`, `matter_id`, `document_id`, `actor_id`, and tenant ids only as keyed hashes or backend-local ids with documented retention.
- Counts such as finding count, blocking finding count, required action count, recipient count bucket, attachment count bucket, degraded mode count, and replacement count.
- Timestamps rounded to the reporting window, such as hour, day, week, or pilot phase.

Prohibited aggregation inputs:

- Raw prompt, email body, document text, subject, title, filename, attachment name, recipient address, channel name, workspace name, URL, matched span, replacement text, reviewer rationale, auth header, API key, JWT, local daemon token, or reversible mapping value.
- Top-N phrase, recipient, filename, subject, or excerpt reports.
- Free-text labels supplied by users or adapters unless they are mapped to an allowlisted taxonomy before aggregation.

Use these backend metrics as raw-free sources where available:

| Product question | Raw-free source | Safe dimensions | Unsafe substitute |
|---|---|---|---|
| Which workflows are active? | `junas_review_surface_total` | `surface`, `workflow`, `decision` | prompt text, email subject, document filename |
| Which policies create friction? | `junas_policy_decisions_total`, `junas_policy_required_actions_total` | decision, required action, policy id/version from SIEM/journal metadata | full policy reasons with source excerpts |
| Where does review degrade? | `junas_degraded_modes_total` | degraded mode, status, surface, workflow | failed document names or OCR text |
| Are adapters timing out? | `junas_adapter_timeouts_total` | adapter, surface, workflow, timeout bucket | endpoint URL with auth material |
| Are approvals used? | `junas_approval_requests_total`, `junas_approval_completed_total` | status, reason code, reviewer role, policy version | reviewer rationale or raw reviewed text |
| Are users applying safer outputs? | `junas_safe_rewrite_applied_total` | endpoint, surface, workflow, replacement action | rewritten text or replacement value |

Aggregation formulas:

- Activation rate: count distinct tenant or actor hashes with at least one `junas_review_surface_total` event, divided by assigned tenant or actor hashes.
- Reviewed-send rate: count adapter-observed attempts with a completed review decision before completion, divided by adapter-observed eligible attempts. If the adapter cannot observe attempts that bypass review, mark denominator confidence as `partial`.
- Accepted-finding rate: count finding ids with no false-positive reject and with a final allowed, rewritten, redacted, approved, or held outcome, divided by returned finding ids.
- Safe-rewrite usage: count review sessions with `junas_safe_rewrite_applied_total` or rewrite-equivalent action events, divided by sessions where `safe_rewrite`, `redact_pii`, or `hold_until_public` was required or recommended.
- Blocked-send rate: count reviewed send/share/submit attempts with final `block`, unresolved `approval_required`, or degraded `block_send`, divided by reviewed send/share/submit attempts.

Every aggregate report must include:

- reporting window and timezone
- data sources used
- denominator confidence: `complete`, `partial`, or `unknown`
- whether values are tenant-local, backend-local, SIEM-exported, or dashboard-derived
- retention policy for the aggregate and the underlying event stream

`scripts/generate_product_value_report.py` reads Prometheus text metrics and writes `reports/product-value-report.json`
with reviewed documents by surface, block rate, warn rate, rewrite rate, approval rate, and override rate. It ignores
unknown metrics and emits only bounded labels and counts.
