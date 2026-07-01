# ADR 0005: Admin Console Docs-Only Until Validation

Status: Accepted

Date: 2026-07-01

## Context

Junas needs an admin console for review sessions, decisions, policy config, audit
exports, false-positive triage, and tenant health. The requirements are documented,
but the operational workflows have not been validated with pilot users. Choosing a UI
surface now would commit the project to framework, deployment, and security tradeoffs
before the highest-risk requirements are known.

The FastAPI backend remains the trust boundary for tenant identity, role checks,
policy decisions, audit journal writes, retention, and raw-content handling. Admin UI
work must not create a second policy engine, a raw document browser, or a route that
weakens tenant isolation.

## Decision

Keep the admin console docs-only until customer validation. Do not add a separate
frontend, server-rendered FastAPI templates, new admin endpoints, or a frontend
framework dependency for the admin console yet.

The next admin-console artifact should be a no-build prototype or wireframe document
that validates navigation, role boundaries, and required evidence without shipping an
interactive surface. Endpoint requirements may be documented before implementation,
but endpoint code remains gated on explicit role, tenant isolation, pagination, audit,
and no raw body exposure by default requirements.

## Alternatives Considered

- Separate frontend: strongest long-term UX flexibility, but adds build, auth,
  deployment, dependency, and browser-storage security work before validated demand.
- Server-rendered FastAPI templates: lower tooling cost, but still creates production
  UI routes and raw-content handling risks before the endpoint contract is approved.
- Docs-only with a no-build prototype: lowest implementation risk while product,
  security, and endpoint requirements are still being validated.

## Consequences

- Admin-console work remains requirements-first until customer validation provides
  evidence for the workflow and UI surface.
- `docs/admin-console/requirements.md` is the normative scope document for now.
- No frontend framework dependency should be added for this surface before the
  no-build prototype or wireframe is reviewed.
- No admin endpoint should ship before tests prove tenant scoping, role checks, and
  no raw body exposure by default.
- The project has no interactive admin console until this ADR is revisited.

## Revisit Triggers

Revisit this decision after all of the following exist:

- evidence from at least five target-user interviews or pilot workflow sessions across
  legal, compliance, and security roles
- a reviewed no-build prototype or wireframe covering review sessions, decisions,
  policy config, audit exports, false-positive triage, and tenant health
- endpoint requirements for pagination, tenant isolation, role checks, audit events,
  and no raw body exposure by default
- an auth design that refuses local-dev-only headers in production
- a deployment decision for whether the chosen UI is separate frontend,
  server-rendered FastAPI templates, or another documented surface

## Related Documents

- `docs/admin-console/requirements.md`
- `docs/product/personas.md`
- `docs/product/workflows.md`
- `docs/policy/decision-contract.md`
- `docs/security/api-inventory.md`
