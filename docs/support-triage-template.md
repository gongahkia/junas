# Support Triage Template

Use this template for pilot and production support issues. Do not collect raw prompts,
email bodies, document text, matched spans, recipient addresses, auth headers, JWTs,
local daemon tokens, API keys, reversible mappings, or reviewer free text in tickets.

## Shared Intake Fields

| Field | Required value |
|---|---|
| Issue class | detector miss, false positive, adapter failure, auth failure, policy dispute, or audit export issue. |
| Tenant/cohort | Tenant id or tenant hash, pilot group, matter id hash, or deployment id. |
| Surface/workflow | `api`, `outlook`, `browser_genai`, `dms`, `word`, `desktop`, or `other`; workflow enum when available. |
| Request/review ids | `request_id`, `review_id`, idempotency key hash, or audit pack id. |
| Policy | policy id, policy version, decision, required actions, and degraded mode. |
| Version | backend commit/image tag, adapter version, manifest/package hash, browser/Office/client version. |
| Reproduction | synthetic reproduction path or hash-only reference. |
| Severity | pilot blocker, production blocker, privacy/security, degraded, or informational. |
| Owner/SLA | named owner, next action, due date, and escalation path. |

## Detector Miss

Required:

- review id and rule/detector bucket if known
- expected finding category and jurisdiction
- whether the miss is PII, MNPI, quasi-identifier, document metadata, image/OCR, or other
- synthetic reproduction text or `hash_only_signal`
- candidate fixture issue link if promoted for evaluation

Do not attach raw customer samples unless `customer_sample_approved` evidence and
scrub/check steps exist under `docs/security/feedback-artifact-retention.md`.

## False Positive

Required:

- review id, finding ids, rule ids, severity, and policy id/version
- reviewer decision taxonomy label, such as `false_positive`
- whether the user was blocked, warned, rewritten, or routed to approval
- support count for repeated reports by surface/workflow

Do not paste reviewer rationale into SIEM, dashboards, or public tickets.

## Adapter Failure

Required:

- adapter: Outlook, browser, DMS, Word, desktop, or direct API
- runtime/client version, manifest/package hash, extension id, or add-in assignment scope
- backend status, timeout bucket, auth mode, request id, and bounded error type
- failure path: backend unavailable, auth failed, malformed response, selector failure,
  degraded extraction, platform bypass, or telemetry missing

Do not include raw prompt, email body, document text, subject, filename, recipient
address, or endpoint URL with secrets.

## Auth Failure

Required:

- auth mode: API key registry, JWT/JWKS, mTLS, local pairing token, or single-tenant exception
- tenant id/hash, role, route, status code, request id, and denial reason
- whether `JUNAS_DEV_AUTH=0` and production preflight passed
- key/credential rotation status if a secret may be stale

Do not paste API keys, JWTs, local daemon tokens, mTLS private keys, or raw headers.

## Policy Dispute

Required:

- policy id/version, decision, required actions, policy reasons, and workflow context
- reviewer role and requested outcome: approve, reject, policy exception, accept risk,
  request changes, or hold
- whether content/context changed after the original review
- linked policy config issue or change request

Do not treat the adapter as the policy authority; disputes must resolve through backend
policy config, reviewer decision, or documented non-goal.

## Audit Export Issue

Required:

- review id, audit pack id/path hash, export command, verification command, and failure
  output without raw payloads
- journal key status, key version, tenant, and retention manifest status
- whether `scripts/export_audit_pack.py`, `scripts/verify_audit_pack.py`, or
  `scripts/verify_journal.py` failed
- subject-erasure or legal-hold status if evidence is missing or tombstoned

Do not attach unredacted audit packs to support tickets. Share sanitized manifests,
hashes, verification status, and command output only.

## Closure Fields

| Field | Required value |
|---|---|
| Root cause | detector, policy, adapter, auth, deployment, docs, vendor platform, or customer config. |
| Fix path | code fix, policy update, adapter recertification, docs update, support response, or rejected/non-goal. |
| Evidence | test, doc, report, issue, PR, or sanitized customer approval record. |
| Customer response | approved response text that contains no prohibited raw data. |
| Follow-up | eval fixture, support FAQ, changelog entry, pilot metric update, or backlog item. |
