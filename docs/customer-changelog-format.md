# Customer-Facing Changelog Format

Use this format for customer-facing release notes and pilot updates. Keep it separate
from internal commit logs. Every entry must state customer impact, affected surfaces,
evidence, rollback notes, and whether action is required.

## Header

| Field | Required value |
|---|---|
| Release | version, date, commit, image tag, or package hash |
| Audience | pilot tenant, production tenant, local users, or public demo |
| Deployment mode | hosted, customer-managed, local-only, hybrid, or demo |
| Action required | none, admin action, adapter redeploy, policy review, credential rotation, or user communication |
| Rollback reference | link to `docs/deployment-rollback.md` or release-specific rollback note |

## Sections

### Detector Accuracy Changes

Use for recognizer, rule, corpus, OCR/image, quasi-identifier, MNPI, benchmark, or
precision/recall changes.

Required fields:

- rules or detectors changed
- jurisdictions or document types affected
- expected effect on false positives, false negatives, recall, precision, or latency
- eval report, test, fixture, or lock evidence
- whether customer policy thresholds need review

Do not describe detector changes as accuracy improvements without committed eval
evidence.

### Policy Behavior Changes

Use for policy decision, required action, reviewer role, approval, warning, block,
safe-rewrite, hold, or audit-decision behavior.

Required fields:

- policy id/version or config field changed
- affected decisions: `allow`, `warn`, `block`, `approval_required`, or `rewrite_required`
- affected required/recommended actions
- migration or compatibility notes
- audit/journal effect

Do not hide decision-shape changes inside generic "backend fixes" language.

### Adapter Behavior Changes

Use for Outlook, browser, Word, DMS, desktop watcher, local daemon pairing, packaging,
manifest, telemetry, or failure-mode behavior.

Required fields:

- adapter and version/package/manifest hash
- supported client/runtime versions affected
- changed workflow context sent to `/review`
- changed UI/completion behavior
- privacy/storage/telemetry impact
- install, rollback, or admin assignment action

Do not imply unsupported surfaces are covered because one adapter changed.

### Security Fixes

Use for auth, tenant isolation, rate limits, logging, SIEM, secret handling, dependency,
SBOM, CORS/CSRF, local daemon ACL, signing, or packaging security fixes.

Required fields:

- severity and affected deployment modes
- affected routes, adapters, packages, or config keys
- whether credentials, tokens, keys, or manifests need rotation
- tests/scans/SBOM evidence
- exposure statement using only verified facts

Do not include exploit details, secrets, tokens, raw customer content, or unverified
impact claims.

## Entry Template

```md
## <Release or Date>

Audience:
Deployment mode:
Action required:
Rollback:

### Detector Accuracy Changes
- Change:
- Impact:
- Evidence:
- Customer action:

### Policy Behavior Changes
- Change:
- Impact:
- Evidence:
- Customer action:

### Adapter Behavior Changes
- Change:
- Impact:
- Evidence:
- Customer action:

### Security Fixes
- Change:
- Impact:
- Evidence:
- Customer action:
```

## Review Gate

Before sending a changelog, run the claim through
`docs/product/claim-review-checklist.md`. If a section has no customer-facing change,
write `None` rather than omitting the section; this keeps detector accuracy, policy
behavior, adapter behavior, and security fixes visibly separated.
