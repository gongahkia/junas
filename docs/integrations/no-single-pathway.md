# No Single Pathway

Status: normative for production pilot architecture. A production pilot should deploy the direct API/backend contract plus at least one workflow adapter that covers a real user completion path.

Use with `docs/product/workflows.md`, `docs/integrations/direct-api.md`, `docs/integrations/maturity-matrix.md`, and `docs/integrations/adapter-certification-checklist.md`.

## Recommendation

Use both:

- Direct API: baseline integration with the FastAPI backend, policy config, auth, audit journal, SIEM export, and generated OpenAPI/client examples.
- At least one workflow adapter: Outlook Smart Alerts, Browser GenAI extension, DMS hook, or another certified adapter that intercepts a real send, submit, upload, share, or review workflow.

This is not a requirement for every demo or backend-only customer integration. It is the recommended production pilot shape when Junas is being evaluated for daily user workflow value.

## Why Direct API Alone Is Not Enough For Workflow Pilots

Direct API is the contract source and can be production-grade for service integrations, but it does not prove that users are reviewed at the moment they paste, send, upload, or share content. A direct API-only pilot can validate backend policy and audit evidence, but it should not claim in-workflow capture unless the customer workflow actually calls it before completion.

Direct API-only is acceptable when:

- the customer has no UI workflow and owns a service-side pre-send/pre-upload call
- the integration is an API gateway, proxy, DMS hook, or workflow engine
- the pilot goal is backend policy validation, not end-user activation

Direct API-only must not claim:

- Outlook send-time enforcement
- GenAI prompt pre-submit review
- DMS check-in hold behavior
- desktop endpoint enforcement
- tenant-wide DLP replacement

## Why Adapter Alone Is Not Enough

Adapters are activation surfaces. They collect context, call `/review`, display or apply `policy_decision`, and emit privacy-safe telemetry. They are not alternate policy engines.

Adapter-only pilots fail the architecture bar when:

- the backend policy contract is not validated independently
- auth, tenant isolation, audit journal, SIEM, and OpenAPI examples are not exercised
- the adapter has no certified failure behavior
- the adapter cannot call follow-on actions such as `/safe-rewrite`, `/request-approval`, or `/documents/scrub`
- support evidence depends on one client UI that may change

## Recommended Pilot Combinations

| Pilot goal | Baseline path | Workflow adapter | Claim allowed after certification |
|---|---|---|---|
| Email pre-send review | Direct API + policy/audit | Outlook Smart Alerts | Outlook send review for certified client/version groups. |
| GenAI prompt review | Direct API + policy/audit | Browser GenAI extension | Prompt review for certified managed Chrome/Edge targets and hosts. |
| DMS upload/check-in | Direct API + policy/audit | DMS hook/scanner | Service-side document upload/check-in review for certified repository hooks. |
| Author-side document review | Direct API + policy/audit | Word taskpane | User-triggered document review only; not save/share enforcement. |
| Offline local fallback | Direct API/local daemon | Desktop watcher | Opt-in local review only; not endpoint enforcement. |
| Future collaboration surfaces | Direct API first | Slack/Google Workspace only after implementation | Research-only until source, auth, privacy, telemetry, and smoke tests exist. |

## Production Pilot Exit Criteria

Before calling a pilot production-ready:

- direct API `/review` examples validate against OpenAPI and Pydantic schemas
- backend auth and tenant identity are configured
- policy id/version is pinned and visible in responses
- at least one workflow adapter passes `adapter-certification-checklist.md`
- telemetry joins adapter events to policy decisions without raw content
- failure semantics are tested for backend timeout, auth failure, degraded review, malformed response, and platform bypass
- privacy tests prove no raw content is persisted in adapter storage, logs, telemetry, SIEM, or screenshots
- audit evidence can be exported and verified

## Wording Rules

Allowed:

- "Direct API plus Outlook Smart Alerts pilot"
- "Direct API plus managed Browser GenAI extension pilot"
- "DMS hook backed by the same `/review` policy contract"
- "Word taskpane review, not save/share enforcement"
- "Desktop watcher opt-in local fallback"

Not allowed:

- "Junas covers all Slack/Google Workspace traffic"
- "Any adapter can be used without the backend policy contract"
- "Desktop watcher is endpoint DLP"
- "Word taskpane blocks sharing"
- "Browser extension guarantees coverage when target DOM changes"
- "Direct API-only pilot proves user workflow activation"

## Exceptions

Exceptions must be recorded in the pilot plan:

- Backend-only service integration: allowed when the customer workflow is server-side and no UI adapter is needed.
- Research-only evaluation: allowed when measuring policy quality with fixture traffic.
- Air-gapped local review: allowed with local daemon/direct API, but do not claim SaaS workflow capture.
- Adapter discovery: allowed for prototype evidence, but do not claim production support until certification passes.
