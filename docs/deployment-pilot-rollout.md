# Pilot Rollout Checklist

Use this checklist before a production pilot where real users, real tenant auth, or real
workflow traffic are involved. A pilot must validate the backend contract and one
workflow adapter or direct service path with measurable outcomes.

Use with `docs/deployment-hardening.md`, `docs/integrations/no-single-pathway.md`,
`docs/integrations/adapter-certification-checklist.md`,
`docs/product/value-metrics.md`, and `docs/deployment-rollback.md`.

## Scope Record

Record these fields before enabling users:

| Field | Required value |
|---|---|
| Pilot owner | Named customer/operator owner and Junas owner. |
| Tenant/auth mode | `JUNAS_TENANCY_ENABLED=1` with API-key registry, JWT/JWKS, mTLS, or documented single-tenant exception. |
| Policy profile | `JUNAS_POLICY_CONFIG`, policy id, policy version, reviewer roles, degraded behavior, and approval path. |
| Adapter | Exactly one supported workflow adapter or one direct service integration for the first pilot cohort. |
| Cohort | Tenant, group, matter, repository, browser policy group, or user list. |
| Data boundary | Hosted, customer-managed, local-only, or hybrid deployment mode. |
| Success window | Start/end date, timezone, reporting cadence, and exit review date. |

## Required Gates

| Gate | Evidence before rollout | Failure action |
|---|---|---|
| Tenant auth | `JUNAS_TENANCY_ENABLED=1`, configured auth mode, tenant credential/JWT validation, role mapping, and auth-denial smoke test. | Do not enable real users. |
| Policy profile | Validated `JUNAS_POLICY_CONFIG`, pinned policy id/version, reviewer override roles, degraded policy, and deterministic decision fixtures. | Keep traffic in test tenant. |
| One adapter | Adapter certification evidence for the selected Outlook, browser, DMS, Word, desktop, or direct API path. | Pilot backend-only or postpone adapter rollout. |
| Audit exports | `scripts/export_audit_pack.py`, `scripts/verify_audit_pack.py`, and `scripts/verify_journal.py` work against pilot evidence without raw body leakage. | Hold pilot exit claim. |
| Telemetry | Adapter events and backend metrics join by request/review ids using privacy-safe hashes, counts, policy ids, decisions, and bounded labels. | Disable product-value reporting for the pilot. |
| Support path | Support intake owner, escalation SLA, detector-miss path, false-positive path, auth failure path, adapter failure path, and policy dispute path are written. | Keep cohort internal only. |
| Rollback | `docs/deployment-rollback.md` path is tested for backend, selected adapter, credentials, and static assets. | Do not expand the cohort. |
| Success metrics | Baseline and target values are defined for activation, reviewed-send, accepted-finding, false-positive override, safe-rewrite, blocked-send, and audit-pack export metrics. | Treat results as qualitative only. |

## Preflight Commands

Run the production preflight and any selected adapter checks before assignment:

```sh
uv run python scripts/preflight.py --deployment production --strict
PYTHONPATH=src python3 -m pytest test/test_policy_decision_contract.py test/test_docs_links.py -q
```

Adapter-specific examples:

```sh
PYTHONPATH=src python3 -m pytest test/test_outlook_manifest_validate.py -q
PYTHONPATH=src python3 -m pytest test/test_browser_extension.py -q
PYTHONPATH=src python3 -m pytest test/test_adapter_smoke.py -q
```

Use the subset that matches the selected adapter. Do not present untested adapters as
pilot-covered surfaces.

## Support Intake

Every pilot must have one intake path and one owner for each issue class:

| Issue class | Required triage data | Prohibited data |
|---|---|---|
| Detector miss | review id, rule ids, detector bucket, synthetic reproduction plan | raw customer text in ticket |
| False positive | review id, finding ids, reviewer taxonomy label, policy id/version | free-text rationale copied to SIEM |
| Adapter failure | adapter, version, client version, timeout/error type, request id | raw prompt/email/document |
| Auth failure | tenant id/hash, auth mode, role, denial status, request id | API key, JWT, local token |
| Policy dispute | policy id/version, decision, required actions, reviewer role | raw legal memo or email body |
| Audit export issue | audit pack id/hash, journal verification status, export command | unredacted audit pack attachment |

## Success Metrics

Report these metrics from `docs/product/value-metrics.md`:

| Metric | Pilot use |
|---|---|
| Activation rate | Shows assigned users or tenants are actually triggering review. |
| Reviewed-send rate | Shows the selected adapter or direct integration captures eligible completion attempts. |
| Accepted-finding rate | Shows findings are acted on rather than routinely ignored. |
| False-positive override rate | Tracks review fatigue and detector precision issues. |
| Safe-rewrite usage | Shows users can complete work through safer output actions. |
| Blocked-send rate | Shows policy is stopping unresolved high-risk sends/shares/submits. |
| Audit-pack export rate | Shows audit evidence can be produced and verified. |

Every metric report must include reporting window, denominator confidence, data source,
retention policy, and whether values are backend-local, tenant-local, SIEM-exported, or
dashboard-derived.

## Exit Criteria

The pilot can expand only when:

- tenant auth and role checks pass for the assigned cohort
- policy id/version is pinned and visible in review responses
- selected adapter certification passes with failure-mode evidence
- audit export and journal verification work on pilot evidence
- telemetry has no raw content, auth material, recipient addresses, or matched spans
- support issues have owners and resolution paths
- rollback was tested or rehearsed for the selected backend and adapter artifacts
- success metrics have baseline, target, measured result, and denominator confidence
