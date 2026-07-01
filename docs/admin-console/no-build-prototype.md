# Admin Console No-Build Prototype

Status: no-build wireframe. This document is the required prototype artifact before
any admin console frontend framework dependency, server-rendered template, or admin UI
route is added.
This no-build wireframe comes before any admin console frontend framework dependency.

## Prototype Goals

- Validate admin console navigation before implementation.
- Keep the FastAPI backend as the trust boundary.
- Show review sessions, decisions, policy config, reviewer queue, false-positive
  triage, audit exports, and tenant health without raw body exposure by default.
- Prove which controls need endpoint requirements before code.
- Avoid selecting React, Vue, Svelte, HTMX, Jinja templates, or any other frontend
  surface until customer validation.

## Global Shell

```text
Junas Admin
Tenant: tenant-a        Role: admin        Policy: default / 2026-06-14

[Review Sessions] [Reviewer Queue] [Policy Config] [False Positives] [Audit Exports] [Tenant Health]

Status band:
Ready: yes | Auth: jwt | Journal key: configured | Retention manifest: configured | SIEM: enabled
```

Global rules:

- No raw prompt, email body, document text, matched spans, reversible mappings, auth
  headers, local pairing tokens, raw reviewer rationale, recipients, or filenames in
  table rows.
- Every list has tenant-scoped pagination, stable sorting, and privacy-safe filters.
- Every detail page shows policy id/version, review id, request id, hashes, counts,
  timestamps, and verification status before any sensitive evidence action.

## Review Sessions

```text
Filters:
Surface [all] Workflow [all] Decision [all] Required action [all] Policy version [all]
Created after [UTC] Created before [UTC] SLA [all]

Table:
Review ID | Created | Surface | Workflow | Decision | Required actions | Policy | Findings | Expires | Audit
rev-...   | 09:30Z  | outlook | email_send | block | hold_until_public | default/2026-06-14 | 2 high | 09:35Z | export

Actions:
open detail | request audit export | copy review id
```

Detail view:

- Decision trail: policy decision, send allowed, required actions, recommended
  actions, blocking finding ids, reviewer decisions, and replay status.
- Privacy strip: document hash, finding counts, severity counts, recipient count, and
  attachment count.
- Links: reviewer queue item, audit export job, false-positive triage item.

## Reviewer Queue

```text
Tabs:
Unassigned | Assigned to me | Overdue | Completed

Table:
Approval ID | Review ID | SLA | Assignee | Required roles | Decision | Policy | Findings | Status
appr-...    | rev-...   | due soon | unassigned | checker,admin | approval_required | default/2026-06-14 | 1 high | pending

Actions:
claim | assign | reassign | record decision
```

Decision panel:

- Action: approve, policy_exception, accept_risk, request_changes, hold, reject.
- Reason code required.
- Optional rationale marked sensitive and excluded from SIEM by default.
- Conflict flag when requester and reviewer are the same principal.

## Policy Config

```text
Active policy:
Policy ID | Version | Hash | Published by | Published at | Validation
default   | 2026-06-14 | sha256:... | legal-ops | 09:00Z | valid

Drafts:
Draft ID | Base version | Candidate version | Status | Updated | ETag
draft-1  | 2026-06-14  | 2026-07-01-a | validation_failed | 09:20Z | W/"..."

Actions:
new draft | import TOML | validate | publish | rollback | abandon
```

Validation panel:

- Field errors from `docs/policy/schema.md`.
- Changed field names and config hash.
- No raw preview text stored in draft, logs, telemetry, or SIEM.

## False-Positive Triage

```text
Filters:
Rule [all] Category [all] Jurisdiction [all] Detector issue [all] Status [all]

Table:
Finding ID | Rule | Category | Jurisdiction | Reject reason | Detector issue | Fixture task | Status
f-...      | sg_nric_fin | PII | SG | defined_term | defined_term_or_placeholder | task-... | create_fixture

Actions:
categorize | create synthetic fixture task | link detector issue | resolve
```

Fixture task panel:

- Uses rule id, jurisdiction, detector issue category, document hash, and sanitized
  reproduction notes.
- Customer-derived fixture path stays blocked until `customer_sample_approved` and
  `scripts/check_fixture_scrub.py` evidence exist.

## Audit Exports

```text
Request export:
Review ID [rev-...] Reason [customer_audit] Retention [audit_packs] Include defensibility [ ]

Jobs:
Job ID | Review ID | Status | Pack verification | Journal verification | Retention | Expires | Download
job-... | rev-...  | exported | valid | valid | audit_packs | 2033-07-01 | sensitive

Actions:
request | verify pack | verify journal | download | expire | delete
```

The UI wraps `scripts/export_audit_pack.py`, `scripts/verify_audit_pack.py`, and
`scripts/verify_journal.py` through server-controlled jobs. Browser clients do not
choose export paths.

## Tenant Health

```text
Auth        jwt enabled, roles from claim, dev headers rejected
Policy      default / 2026-06-14, last validation valid
Journal     key configured, last verify valid
Retention   manifest configured
Adapters    outlook fresh, browser fresh, desktop local fallback only
SIEM        enabled, last event accepted
Errors      backend 0, adapter auth 0, export verify 0
```

Health cards link to the underlying requirements docs, not raw logs.

## Framework Gate

Do not add a frontend framework dependency, `package.json` frontend workspace, bundled
asset pipeline, server-rendered templates, or admin routes until:

- this no-build prototype is reviewed with target users
- at least five target-user interviews or pilot workflow sessions are recorded
- endpoint requirements for the touched surface are approved
- auth, telemetry, no-raw-content, and tenant-isolation tests are planned
- ADR 0005 is revisited or superseded

## Related Documents

- `docs/adr/0005-admin-console-docs-only-until-validation.md`
- `docs/admin-console/requirements.md`
- `docs/admin-console/review-session-list-endpoint.md`
- `docs/admin-console/policy-config-ui.md`
- `docs/admin-console/reviewer-queue.md`
- `docs/admin-console/false-positive-triage.md`
- `docs/admin-console/audit-export-ui.md`
- `docs/admin-console/auth-requirements.md`
- `docs/admin-console/telemetry-requirements.md`
