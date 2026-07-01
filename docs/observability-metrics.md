# Observability Metrics Boundary

Junas metrics use bounded labels only. Do not add labels from raw prompts, email bodies, document text, subjects, titles, filenames, recipient addresses, URLs, matched spans, replacement text, reviewer rationale, auth headers, API keys, JWTs, local pairing tokens, tenant secrets, or reversible mapping values.

## SIEM-Safe Metrics

These metrics can feed SIEM or central dashboards when downstream retention and access controls are configured. Export counters as counts/rates and gauges as status values.

| Metric | Safe labels | Use |
|---|---|---|
| `junas_http_requests_total` | endpoint, method, status code | Backend traffic, 4xx/5xx alerts, adapter auth failure rates. |
| `junas_classification_results_total` | endpoint, classification, cache status, degraded | Legacy classification volume and risk bucket counts. |
| `junas_review_surface_total` | endpoint, surface, workflow, decision | Reviewed documents by surface/workflow and policy outcome. |
| `junas_policy_decisions_total` | decision, surface, workflow | Allow/warn/block/rewrite/approval rates. |
| `junas_policy_required_actions_total` | action, decision, surface, workflow | Required action mix without reasons or source text. |
| `junas_adapter_timeouts_total` | surface, workflow, adapter | Adapter timeout rates. |
| `junas_degraded_modes_total` | endpoint, surface, workflow, mode, status | Degraded extraction/review coverage. |
| `junas_approval_requests_total` | status, reason code | Approval request rate and queue pressure. |
| `junas_approval_completed_total` | action | Completed approval decisions by bounded action. |
| `junas_reviewer_decisions_total` | action, decision taxonomy | False-positive, policy-exception, and accept-risk aggregates. |
| `junas_safe_rewrite_applied_total` | endpoint, surface, workflow, action | Safe rewrite or hold action usage counts. |
| `junas_layer_execution_total` | layer, outcome | Layer execution failures and skips by configured layer name. |
| `junas_layer_load_total` | layer, phase, outcome | Startup/lazy-load layer failures. |
| `junas_required_layer_configured` | layer | Required layer config state. |
| `junas_required_layer_available` | layer | Required layer availability state. |
| `junas_required_layer_warming` | layer | Required layer warmup state. |
| `junas_dependency_configured` | dependency | External helper configured state. |
| `junas_dependency_healthy` | dependency | External helper health state. |
| `junas_preflight_check_status` | check | Production preflight pass/fail status from `scripts/preflight.py --prometheus-output`. |

## Local-Only Or Rollup-Only Metrics

Histograms are safe from a content perspective but high-volume. Keep raw bucket series in Prometheus/Grafana unless the SIEM pipeline has cost, retention, and cardinality controls. Export p50/p95/p99 rollups only when SIEM needs them.

| Metric | Boundary | Reason |
|---|---|---|
| `junas_http_request_duration_seconds` | Prometheus raw buckets; SIEM rollup only | Per-route latency buckets are noisy but useful for SLO dashboards. |
| `junas_classification_duration_seconds` | Prometheus raw buckets; SIEM rollup only | Legacy endpoint timing buckets do not need event-log indexing. |
| `junas_policy_decision_duration_seconds` | Prometheus raw buckets; SIEM rollup only | Policy timing is useful as aggregate p95/p99, not as per-scrape SIEM events. |
| `junas_layer_execution_duration_seconds` | Prometheus raw buckets; SIEM rollup only | Layer execution timing should stay operational unless aggregated. |
| `junas_layer_load_duration_seconds` | Prometheus raw buckets; SIEM rollup only | Startup/lazy-load timing should stay operational unless aggregated. |

## Disabled Or Prohibited Metrics

Disable or reject any metric, dashboard extract, alert label, support bundle, or SIEM field that includes:

- raw prompt, email subject/body, document text, attachment bytes, title, filename, recipient address, channel name, workspace name, URL, or reviewer rationale
- `matched_text`, matched span coordinates, replacement text, pseudonym mapping value, ciphertext, local pairing token, API key, JWT, authorization header, cookie, or raw tenant secret
- free-text adapter labels, policy reasons, exception notes, OCR text, public-evidence query text, or LLM prompt/completion text
- unbounded ids such as raw tenant ids, actor ids, matter names, folder names, document names, or idempotency keys unless they are backend-local ids or keyed hashes

If a new metric needs one of those values, do not export it. Replace the label with a bounded enum, count, bucket, policy id/version, keyed hash, or omit the dimension.

## Operator Checks

- Review new metrics against this document before adding them to `src/junas/backend/observability.py`.
- Scrape `/metrics` only over authenticated infrastructure paths; never expose it publicly.
- Keep reverse-proxy body logging disabled for Junas routes.
- Feed SIEM alerts from `deploy/prometheus/junas-alerts.yml` and preflight status from `junas_preflight_check_status`.
- Use `scripts/generate_product_value_report.py` for raw-free value reporting instead of exporting ad hoc CSVs from request logs.
