# Roadmap

This roadmap follows the product docs in `docs/product/`. A phase is not promoted by implementation alone; it needs exit evidence.

User-requested integration intake is tracked in `docs/product/integration-backlog.md`.
Backlog rows must be categorized as `direct API`, `Outlook`, `browser`, `DMS`, `Slack`,
`Google Workspace`, or `unsupported`.

Scope anti-goals and deferred stretch ideas live in
`docs/product/scope-governance.md`; cite that page when rejecting scope creep.

## Current Issue Triage

Status: 2026-07-04, based on open GitHub issues. This is an equivalent public roadmap, not a delivery promise.

| Lane | Issues | Gate before promotion |
|---|---|---|
| Now | [#84](https://github.com/gongahkia/junas/issues/84) hosted deterministic demo, [#85](https://github.com/gongahkia/junas/issues/85) hosted playground verification, [#76](https://github.com/gongahkia/junas/issues/76) product usability pass. | Must improve current Junas launch evidence without widening product scope. |
| Next | [#34](https://github.com/gongahkia/junas/issues/34) distribution paths, [#12](https://github.com/gongahkia/junas/issues/12) optional rule-pack import. | Needs reproducible evidence, bounded claims, or an explicit decision note before implementation is promoted. |
| Later / research | [#5](https://github.com/gongahkia/junas/issues/5)-[#9](https://github.com/gongahkia/junas/issues/9), [#15](https://github.com/gongahkia/junas/issues/15)-[#25](https://github.com/gongahkia/junas/issues/25), and [#4](https://github.com/gongahkia/junas/issues/4). | Legacy Aki/macOS/video-redaction ideas require fresh product-scope validation against current Junas positioning before work starts. |

## Kill Criteria

Adapter promotion requires measurable workflow value, not just technical feasibility. A candidate adapter should stay experimental, be paused, or be archived when it cannot show a useful activation rate, reviewed-send or reviewed-submit rate, accepted-finding rate, safe-rewrite usage, blocked-risk outcome, or audit-pack export path for its target workflow.

Technical completion is insufficient when the adapter creates high false-positive override rates, stores or logs raw content outside policy, lacks admin deployment evidence, cannot survive ordinary surface changes, or duplicates a workflow that direct API integration already handles with less user friction.

## P0 Backend Policy Contract

Scope:

- Add workflow context to review requests.
- Return a stable policy decision contract on `/review`, `/pseudonymize`, `/anonymize`, and `/redact`.
- Provide deterministic required/recommended actions, policy reasons, action catalog, timings, audit journal events, and SIEM-safe exports.
- Document policy schema, decision contract, versioning, idempotency, and review expiry.

Exit criteria:

- Policy unit tests cover PII high, MNPI high, mixed findings, recipient/domain context, degraded coverage, reviewer override, and missing context.
- Contract tests prove old clients can still read `send_allowed` and ignore new fields.
- OpenAPI examples include policy decisions and adapter surfaces.
- Audit/SIEM tests prove no raw document text, matched spans, prompts, mappings, or auth headers are emitted.
- `docs/policy/` and API versioning docs are complete enough for adapter implementation.

## P1 Outlook Smart Alerts

Scope:

- Treat Outlook Smart Alerts as the first supported email adapter target.
- Template manifests for dev, staging, and production.
- Map backend decisions to allow, warning, block, approval, and rewrite behavior.
- Document admin deployment, SendMode behavior, CORS/well-known requirements, client compatibility, timeout budgets, privacy checks, telemetry, and QA.

Exit criteria:

- Manifest validation script checks Mailbox requirement set, `OnMessageSend`, SendMode, runtime URL, taskpane URL, and HTTPS production host.
- Manual or automated QA proves send checks call `/review` with subject, body, recipients, attachment metadata, and surface `outlook`.
- Fixture screenshots or text snapshots cover allow, warn, block, and approval-required Smart Alert messages.
- Privacy check proves the adapter does not store message body in browser local storage, extension storage, or console logs.
- Tenant deployment guide is usable by a Microsoft 365 admin.

## P1/P2 Browser Extension

Scope:

- P1: support managed prompt review for selected GenAI browser surfaces with explicit selector tests and user confirmation for warn decisions.
- P1: provide backend URL/auth/local-pairing options, connection health, privacy tests, telemetry, enterprise deployment docs, and local fixture smoke tests.
- P2: broaden surface coverage only after adapter policy, selector failure behavior, MV3 lifecycle QA, and manual Chrome/Edge matrices are stable.

Exit criteria:

- ChatGPT, Claude, Gemini, and generic textarea modules have DOM selector tests against local fixture pages.
- Prompt review calls `/review` with surface `browser_genai` and no prompt text is persisted in extension storage or logs.
- Failure behavior is documented and tested so selector drift does not silently block sends without a policy decision.
- Chrome/Edge deployment docs include force-install policy, update URL, permission rationale, and hosted/local daemon modes.
- Browser adapter smoke tests run without external SaaS credentials.

## P2 Desktop Watcher

Scope:

- Keep `junas-watch` as an experimental local fallback for offline review, demos, and power users.
- Document clipboard/folder threat model, explicit clipboard opt-in, local token use, output-directory scope, LaunchAgent packaging, and auth failure behavior.

Exit criteria:

- README and `pyproject.toml` docs mark the watcher experimental without removing the console script.
- Config sample disables clipboard polling by default.
- Tests prove output stays under the configured output directory.
- Tests prove auth failures do not print sensitive clipboard content.
- Packaging docs state LaunchAgent install is optional and admin-controlled.
