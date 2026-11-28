# Review v2: contextual decisions without legacy risk scoring

`ReviewResult` and CLI JSON now carry `schema_version: junas.review.v2`. The previous aggregate scoring mechanism could emit a `LOW_RISK` document label while contextual MNPI was `present`. It has been removed rather than translated into another uncalibrated score.

Removed fields and symbols:

- `overall_risk`, `document_score`, `pii_score`, `mnpi_score`;
- per-finding `score` and the exported `Classification` enum;
- severity-to-risk numeric weights, duplicate-count risk boosts and document risk thresholds;
- numeric advice-band constants, `scripts/calibrate_escalation_threshold.py` and its unused `config/runtime_calibrated.toml` output.

Use `result.sensitivity["pii"]["state"]` and `result.sensitivity["mnpi"]["state"]` in Python, or the corresponding paths in JSON. Each category is `present`, `not_detected` or `unknown`. Evidence includes source spans; MNPI components distinguish issuer, event, materiality and claimed disclosure status. These remain deterministic candidates, not calibrated probabilities or independently verified legal conclusions. `not_detected` is not a verified absence claim. Qualitative finding severity remains available as evidence metadata, without a separate document decision.

CLI exit statuses remain about execution: 0 completed, 1 degraded, 2 invalid input or failure. They do not express whether sensitive text was found. Text admission, jurisdiction resolution and detector evidence are preserved.

Configured advice remains optional and separate. Its router uses qualitative non-high MNPI evidence, not numeric scores. See [advisory governance](llm-governance.md) for the eligibility change and retained standalone model-proposal vocabulary. No providers are constructed by the default strict profile. No external request is authorized by this migration.

The old distilled-student evaluator compared model risk labels with the removed deterministic labels, rather than independent reference annotations. Its old command now exits 2 with a migration message before loading weights or making calls. The experimental teacher collector records `deterministic_sensitivity` and passes the MNPI state as context. Historical teacher rows, model artifacts, paid-run bundles, reference annotations, reports and locked expectations are not rewritten. No local or browser model has been promoted by this change.

The root README predates this contract and still mentions risk scores. Its editing restriction remains in force; this migration and the architecture document describe the active API.
