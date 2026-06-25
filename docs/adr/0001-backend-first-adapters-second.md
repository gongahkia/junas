# ADR 0001: Backend First, Adapters Second

Status: Accepted

Date: 2026-06-14

## Context

Junas has multiple activation surfaces: direct API/client usage, Outlook Smart Alerts, browser GenAI capture, Word taskpane review, desktop watcher fallback, DMS hooks, and future collaboration surfaces. These surfaces differ in deployment control, vendor limitations, runtime permissions, and QA maturity. Treating any adapter as the product core would make policy behavior depend on the weakest or newest surface.

## Decision

Junas keeps adapters, but the FastAPI backend API and policy decisions are the deployment core. The backend owns request validation, tenant/auth boundaries, deterministic review, policy evaluation, rewrite action eligibility, audit events, privacy-safe observability, and compatibility contracts. Adapters collect workflow context, call the backend contract, display decisions, and implement surface-specific completion behavior.

Direct HTTP/OpenAPI integration remains a baseline path for customers that do not want UI adapters. Adapter maturity is promoted only when the adapter proves workflow value, privacy behavior, deployment support, and QA coverage against the backend contract.

## Consequences

- Backend schemas and policy docs must be stable before adapters claim support.
- Adapter code can move, mature, or be archived without changing the core trust boundary.
- README and roadmap language must avoid implying that desktop, browser, Office, or DMS adapters are required for integration.
- Security tests should focus first on tenant isolation, auth, body caps, no-body logs, policy determinism, and SIEM-safe audit output.
- Adapter docs must state deployment prerequisites and known platform limitations.

## Related Documents

- `docs/product/positioning.md`
- `docs/product/workflows.md`
- `docs/product/research-basis.md`
- `docs/roadmap.md`
