# ADR 0002: Outlook Smart Alerts First

Status: Accepted

Date: 2026-06-14

## Context

Junas needs one primary workflow adapter for the first production pilot while keeping direct HTTP/OpenAPI integration as the baseline. The candidate adapters are Outlook Smart Alerts and the browser GenAI extension. Both target high-value pre-send moments, but they differ in deployment control, capture reliability, user intent, and QA shape.

## Decision

Outlook Smart Alerts is the first primary supported adapter target. The browser GenAI extension remains a supported-target roadmap surface, but it should not be the first production pilot adapter until selector tests, MV3 lifecycle behavior, permission review, and managed deployment docs are complete.

## Evidence

- Outlook Smart Alerts gives Junas a vendor-defined send-time hook through `OnMessageSend`, aligning directly with pre-send review.
- Microsoft 365 centralized deployment gives admins a documented rollout path, group assignment model, and custom manifest upload flow.
- Event-based activation docs distinguish prompt-user, soft-block, and hard-block send modes, which maps cleanly to Junas allow/warn/block/approval decisions.
- Email send has explicit recipient, subject, body, attachment, and external-domain context needed by the policy contract.
- Browser GenAI prompt review is important, but target DOMs change, unmanaged profiles are outside enterprise control, and mobile/native GenAI clients are out of browser-extension reach.

## Tradeoffs

- Outlook-first narrows the first pilot to Microsoft 365 email workflows and delays first-class browser prompt coverage.
- Smart Alerts behavior depends on Outlook client support, requirement sets, manifest correctness, timeout budgets, and admin deployment.
- Browser-first would reach GenAI prompts earlier, but would require stronger selector-drift handling and privacy proof before product claims are defensible.
- Direct API integration remains available for customers whose first workflow is DMS, gateway review, or a non-Outlook mail system.

## Consequences

- P1 Outlook work gets priority after the P0 backend policy contract.
- Browser extension work remains active, but support claims need fixture-page smoke tests and managed Chrome/Edge deployment docs.
- README and roadmap should present Outlook as the first primary adapter while avoiding universal email capture claims.
- Adapter certification should start with Outlook and then be reused for browser, DMS, Word, and future collaboration surfaces.

## Related Documents

- `docs/product/research-basis.md`
- `docs/roadmap.md`
- `docs/adr/0001-backend-first-adapters-second.md`
