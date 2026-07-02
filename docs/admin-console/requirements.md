# Admin Console Requirements

Status: requirements only. Do not add a frontend framework, server-rendered UI, or new
admin endpoint until the related ADR and endpoint requirements are approved.

The admin console is a tenant-scoped operations surface for compliance admins, legal
reviewers, auditors, and security operators. The FastAPI backend remains the trust
boundary for tenant identity, role checks, policy decisions, audit journal writes,
retention, and raw-content handling. The console must not become a second policy engine
or a raw document browser.

## Scope Summary

| Area | Purpose | Required capabilities | Out of scope |
|---|---|---|---|
| Review sessions | Show review-session metadata and workflow state. | List by tenant, surface, workflow, adapter, decision, required action, policy id/version, `review_id`, request time, `review_expires_at`, and hashed document id. Use pagination and no raw body exposure by default. | Full-text search over prompts, emails, or documents. |
| Decisions | Explain the decision trail for a session. | Show `policy_decision.decision`, `send_allowed`, required/recommended actions, blocking findings metadata, reviewer actions, rationale ids, timestamps, and replay status. | Editing prior decisions or softening backend policy results in the UI. |
| Policy config | Let admins manage versioned tenant policy. | Draft, validate, publish, rollback, compare versions, show active `policy_id` and `policy_version`, and journal every change. | Hand-editing production config without validation or bypassing backend startup checks. |
| Audit exports | Produce audit evidence without raw text leakage. | Start audit-pack export jobs, show export status, link to `scripts/export_audit_pack.py` and `scripts/verify_audit_pack.py`, and expose journal verification results. | Downloading raw prompts, email bodies, document text, reversible mappings, or auth headers. |
| False-positive triage | Route reviewer rejects into detector-quality work. | Aggregate rejected findings by rule, severity, surface, policy version, detector category, hashed document id, reviewer taxonomy, and candidate fixture sidecar status. | Training on customer text by default or exporting raw customer samples. |
| Tenant health | Show whether a tenant can operate safely. | Display backend readiness, active policy version, auth mode, journal-key status, retention manifest status, adapter telemetry freshness, error rates, and configured integrations. | Replacing SIEM, IdP, MDM, DLP, or uptime monitoring tools. |

## Roles

- Compliance admin: view tenant health, publish validated policy config, inspect
  aggregate decisions, and request audit exports.
- Legal reviewer: view assigned approval or triage queues, record decisions, and add
  rationale without broad audit-only access.
- Auditor: read audit exports, journal verification, policy/version history, and
  sanitized review-session evidence.
- Security engineer: view auth, adapter telemetry, failed access attempts, and
  integration health without raw reviewed content.

## Privacy And Security Requirements

- No raw body exposure by default for review sessions, decisions, audit exports, or
  false-positive triage.
- Never store raw prompts, email bodies, document text, matched spans, reversible
  mappings, auth headers, local pairing tokens, or reviewer rationale containing raw
  customer text in frontend storage, logs, telemetry, or exported admin tables.
- All reads and actions must be tenant-scoped from authenticated credentials, not
  caller-supplied tenant ids.
- Role checks must distinguish compliance admin, legal reviewer, auditor, and security
  engineer behavior before any endpoint ships.
- Adapter telemetry shown in the console must use the allowed event fields from the
  adapter docs and must not include raw content.

## Dependencies

- Review-session list requirements:
  `docs/admin-console/review-session-list-endpoint.md`.
- Policy config UI requirements: `docs/admin-console/policy-config-ui.md`.
- Reviewer queue requirements: `docs/admin-console/reviewer-queue.md`.
- False-positive triage requirements: `docs/admin-console/false-positive-triage.md`.
- Audit export UI requirements: `docs/admin-console/audit-export-ui.md`.
- Admin console auth requirements: `docs/admin-console/auth-requirements.md`.
- Admin console telemetry requirements: `docs/admin-console/telemetry-requirements.md`.
- No-build prototype: `docs/admin-console/no-build-prototype.md`.
- Policy config docs: `docs/policy/schema.md` and `docs/policy/examples.md`.
- Decision behavior: `docs/policy/decision-contract.md` and
  `docs/policy/journal-replay.md`.
- Audit tooling: `scripts/export_audit_pack.py`, `scripts/verify_audit_pack.py`, and
  `scripts/verify_journal.py`.
- Retention and erasure: `docs/security/data-retention.md` and
  `docs/security/subject-erasure.md`.
- Product workflows: `docs/product/workflows.md`.

## Non-Goals Before Validation

- No customer-facing dashboard claims until pilot users validate the workflows.
- No frontend framework dependency before a no-build prototype or wireframe exists.
- No admin route that trusts local-dev-only headers in production.
- No cross-tenant review id lookup, policy read, approval action, export, or erasure
  path.
