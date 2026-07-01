# Claim Review Checklist

Use this checklist before publishing README copy, website copy, procurement answers,
security questionnaires, demo scripts, release notes, screenshots, or adapter support
claims. Every marketing or security claim needs evidence before publication.

## Required Claim Record

| Field | Required value |
|---|---|
| Claim text | Exact sentence or bullet being reviewed. |
| Claim category | accuracy, security, privacy, deployment, adapter support, integration, legal boundary, or product value. |
| Evidence type | docs, tests, eval reports, external vendor docs, or committed artifact. |
| Evidence link | Repo path, report path, test name, or vendor URL. |
| Owner | Person approving the wording. |
| Review date | Date the evidence was checked. |
| Allowed wording | Final wording that matches the evidence. |
| Forbidden extrapolation | Wording that must not be used. |

## Evidence Rules

| Claim type | Acceptable evidence | Not enough |
|---|---|---|
| Accuracy | `docs/accuracy.md`, committed eval reports, promoted corpus locks, test fixtures with labels and provenance. | screenshots, demos, unpromoted sidecars, synthetic anecdotes, roadmap intent. |
| Security/privacy | security docs, threat model, tests proving no raw content in logs/storage/SIEM, dependency/SBOM reports. | general statements that the design is safe. |
| Adapter support | adapter source, manifest/package validation, smoke tests, certification checklist, compatibility matrix, vendor platform docs. | a local prototype, screenshot, or one developer browser profile. |
| Deployment | hardening docs, customer-managed/local-only docs, preflight output, Kubernetes/Docker examples, rollback docs. | a dev server or localhost command. |
| Product value | pilot success rubric, product value report, telemetry aggregation docs, validated pilot report. | activation count alone or unvalidated user enthusiasm. |
| External platform behavior | current external vendor docs with checked date and exact scope. | assumptions about Microsoft, Google, Slack, browser, or DMS behavior. |

## Review Steps

1. Classify the claim.
2. Link at least one acceptable evidence source.
3. Check that the evidence says the same thing as the claim.
4. Add a limitation if the evidence is fixture-only, pilot-only, adapter-specific, or not independently benchmarked.
5. Remove or rewrite any absolute coverage wording unless the evidence has the same scope.
6. Record the approved wording and forbidden extrapolation.
7. Re-check claims after dependency, adapter, vendor-platform, detector, policy, or deployment changes.

## Required Rejections

Reject or rewrite claims that say Junas:

- replaces DLP, legal advice, endpoint control, CASB, IdP policy, eDiscovery, or native SaaS admin controls
- covers every browser, email client, document repository, SaaS app, or mobile workflow
- has independent TAB or ai4privacy benchmark scores before committed eval reports exist
- sends no data to remote providers when public evidence or remote LLM layers are enabled
- blocks all risky sends when an adapter uses soft-block, prompt-user, local-only, or user-triggered behavior
- has low user friction without pilot success metrics

## Output

Every reviewed claim should resolve to one of:

- `approved`: evidence matches the wording.
- `revise`: evidence exists but wording is too broad.
- `reject`: no evidence or the claim conflicts with documented limitations.
- `external-refresh-required`: claim depends on vendor docs that must be rechecked before publication.
