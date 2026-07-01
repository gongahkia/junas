# Admin Console Auth Requirements

Status: requirements only. Do not add admin console auth middleware, endpoints, or UI
code until ADR 0005 is revisited or a dedicated implementation task approves them.

## Purpose

Admin console access must use existing Junas tenant identity and roles. It must not
introduce a second identity model, caller-supplied tenant selectors, local daemon
tokens, or production use of local-dev-only reviewer headers.

## Accepted Identity Sources

Production admin console auth may use only:

- API-key registry credentials from `JUNAS_TENANT_CREDENTIALS_JSON`
- JWT credentials from configured issuer, audience, JWKS, tenant, subject, and roles
  claims
- a trusted identity-aware proxy only when it passes a signed JWT that Junas validates

Required production settings:

- `JUNAS_TENANCY_ENABLED=1`
- `JUNAS_TENANCY_AUTH_MODES=api_key`, `jwt`, or `api_key,jwt`
- tenant id derived from the validated API key or JWT tenant claim
- actor id derived from the configured credential subject or JWT subject claim
- roles derived from the credential registry or JWT roles claim

The admin console must not trust request body fields, query parameters, cookies,
`X-Tenant-ID`, `X-Actor-Role`, `X-Reviewer-ID`, local pairing tokens, or adapter-supplied
workflow context as authoritative identity.

## Local-Dev Header Rule

`X-Reviewer-ID` is local-dev-only compatibility for reviewer attribution when
`JUNAS_DEV_AUTH=1`. Admin console production routes must reject local-dev-only reviewer
headers, even if the header is present with otherwise valid admin credentials.
Production admin console routes must reject local-dev-only reviewer headers.

Requirements:

- `JUNAS_DEV_AUTH=1` must not be allowed in production admin console deployments.
- `X-Reviewer-ID` must never grant admin console access.
- `X-Reviewer-ID` must never override authenticated API-key or JWT subject.
- Any admin console route receiving `X-Reviewer-ID` in production must emit a
  privacy-safe auth-denied event.

## Role Matrix

| Surface | Allowed roles | Denied roles |
|---|---|---|
| Review-session list | `admin`, `auditor`, `checker` | `reviewer`, `maker`, unauthenticated |
| Review-session detail | `admin`, `auditor`, `checker` | `reviewer`, `maker`, unauthenticated |
| Policy config read | `admin`, `auditor`, `checker` | `reviewer`, `maker`, unauthenticated |
| Policy config draft/validate | `admin` | `auditor`, `checker`, `reviewer`, `maker`, unauthenticated |
| Policy config publish/rollback | `admin` | `auditor`, `checker`, `reviewer`, `maker`, unauthenticated |
| Reviewer queue read | `admin`, `checker` | `auditor`, `reviewer`, `maker`, unauthenticated |
| Reviewer queue assignment | `admin`, `checker` | `auditor`, `reviewer`, `maker`, unauthenticated |
| Reviewer decision recording | `admin`, `checker`, `maker` via existing decision access | `auditor`, `reviewer`, unauthenticated |
| Audit export request/download | `admin`, `auditor` | `checker`, `reviewer`, `maker`, unauthenticated |
| False-positive triage | `admin`, `checker` | `auditor`, `reviewer`, `maker`, unauthenticated |
| Tenant health | `admin`, `auditor`, `checker` | `reviewer`, `maker`, unauthenticated |

Any tenant-specific expansion must be documented before implementation and tested with
the same deny-by-default behavior.

## Tenant Isolation

- Tenant scope must come from authenticated credentials.
- Admin console routes must not accept `tenant_id`, `tenant`, or equivalent
  caller-supplied tenant selectors.
- Object reads by `review_id`, `approval_id`, export job id, policy draft id, cursor,
  fixture task id, or detector issue id must be scoped to the credential-derived
  tenant before response serialization.
- Every admin object read must use the credential-derived tenant.
- Cross-tenant ids must return a generic not-found or forbidden response that does not
  reveal whether the object exists.
- Cursors and export job ids must be bound to tenant, actor role, filters, and sort
  order.

## Browser Session Requirements

If a future UI is browser-based:

- Prefer bearer JWT or identity-aware proxy tokens validated by the backend.
- Do not use ambient cookies unless CSRF protections, SameSite policy, origin checks,
  and custom-header requirements are documented and tested.
- Do not store API keys, JWTs, local pairing tokens, or export download URLs in
  persistent browser storage.
- Clear sensitive admin state on logout, token expiry, tenant switch, and browser tab
  close where supported.

## Auth-Denied Audit Events

Required event names:

- `admin_auth_missing`
- `admin_auth_invalid`
- `admin_role_denied`
- `admin_cross_tenant_denied`
- `admin_dev_header_rejected`
- `admin_local_token_rejected`

Events may include tenant id when authenticated, actor id when authenticated, auth mode,
role set, route id, request id, status code, denial reason code, and timestamp. Events
must not include raw reviewed content, matched text, raw rationale, auth header values,
API keys, JWTs, local pairing tokens, export ZIP bytes, recipients, filenames, or
mapping values.

## Required Tests Before Implementation

- Missing auth returns 401 for every admin console route.
- Invalid API key and invalid JWT return 401.
- `reviewer` and `maker` roles cannot read admin console lists.
- `auditor` can request/download audit exports but cannot publish policy config.
- `checker` can read review sessions but cannot download audit packs unless tenant
  policy explicitly grants it.
- Caller-supplied tenant ids are ignored or rejected.
- Cross-tenant object ids, cursors, export jobs, and policy draft ids are denied.
- `X-Reviewer-ID` is rejected in production and cannot override API-key/JWT subject.
- Local daemon `X-Junas-Local-Token` cannot authenticate admin console routes.

## Related Documents

- `docs/adr/0005-admin-console-docs-only-until-validation.md`
- `docs/admin-console/requirements.md`
- `docs/admin-security.md`
- `docs/security/api-inventory.md`
- `docs/security/release-checklist.md`
- `docs/deployment-hardening.md#tenant-auth-and-rbac`
