# API Inventory

Generated from the live FastAPI app route table and current auth dependencies. This inventory covers app routes plus FastAPI-generated OpenAPI/docs routes.

## Auth Groups

| Group | Requirement |
|---|---|
| Public | No route dependency. Restrict at reverse proxy when exposed outside local/dev networks. |
| Runtime local ACL | When `JUNAS_LOCAL_DAEMON_ACL_ENABLED=1`, local middleware checks `Origin` for all requests and requires `X-Junas-Local-Token` for protected review/rewrite paths. |
| Review access | `X-API-Key` or `Authorization: Bearer ...`; roles `reviewer`, `maker`, `checker`, or `admin` when tenancy is enabled. |
| Decision access | `X-API-Key` or `Authorization: Bearer ...`; roles `maker`, `checker`, or `admin` when tenancy is enabled. |
| Audit access | `X-API-Key` or `Authorization: Bearer ...`; roles `auditor`, `checker`, or `admin` when tenancy is enabled. |

Legacy single-tenant mode: if `JUNAS_TENANCY_ENABLED=0` and `JUNAS_API_KEY` is unset, dependency-protected routes do not enforce auth or roles. Production deployments should enable tenancy or set `JUNAS_API_KEY` behind a trusted proxy.

## Global Limits

| Control | Current value |
|---|---|
| Request body cap | `api.max_request_bytes` / `JUNAS_MAX_REQUEST_BYTES`, default `10485760` bytes, enforced before schema validation for `POST`, `PUT`, and `PATCH`. |
| Public demo body cap | `JUNAS_PUBLIC_DEMO_BODY_MAX_BYTES`, default `8192` bytes. |
| Public demo text cap | `JUNAS_PUBLIC_DEMO_TEXT_MAX_CHARS`, default `4000` chars. |
| Public demo rate limit | `JUNAS_PUBLIC_DEMO_RATE_LIMIT`, default 30 requests per `JUNAS_PUBLIC_DEMO_RATE_LIMIT_WINDOW_SECONDS`, default 60 seconds, keyed by forwarded/client IP. |
| Backend route rate limits | `rate_limit.*` / `JUNAS_RATE_LIMIT_*`, disabled by default. When enabled, process-local limits cover `/review`, `/classify/batch`, `/reidentify`, local pairing, and approval/decision routes. See [`rate-limits.md`](./rate-limits.md). |

## Route Table

| Method | Route | Auth | Roles | Tenant scope | Rate limit | Payload cap |
|---|---|---|---|---|---|---|
| GET | `/openapi.json` | Public | n/a | none | none | n/a |
| GET | `/docs` | Public | n/a | none | none | n/a |
| GET | `/docs/oauth2-redirect` | Public | n/a | none | none | n/a |
| GET | `/redoc` | Public | n/a | none | none | n/a |
| GET | `/local/pairing/status` | Public plus runtime local ACL when enabled | n/a | local in-memory daemon state | none | n/a |
| POST | `/local/pairing/start` | Runtime local ACL origin check when enabled | n/a | local in-memory pending pairing | `local_pairing` when enabled | global body cap |
| POST | `/local/pairing/approve` | Runtime local ACL origin check plus daemon secret in `X-Junas-Local-Token` | n/a | local in-memory pending pairing | `local_pairing` when enabled | global body cap |
| POST | `/local/pairing/claim` | Runtime local ACL origin check when enabled plus pairing id/code | n/a | local in-memory pending pairing | `local_pairing` when enabled | global body cap |
| GET | `/demo` | Public, gated by `JUNAS_PUBLIC_DEMO_ENABLED=1` | n/a | none | none | n/a |
| POST | `/demo/review` | Public, gated by `JUNAS_PUBLIC_DEMO_ENABLED=1` | n/a | no persistence | public demo rate limit | public demo body/text caps plus global body cap |
| GET | `/health` | Public | n/a | none | none | n/a |
| GET | `/ready` | Public | n/a | none | none | n/a |
| GET | `/diagnostics` | Public | n/a | none | none | n/a |
| GET | `/metrics` | Public | n/a | none | none | n/a |
| POST | `/classify` | Review access | `reviewer`, `maker`, `checker`, `admin` | credential-derived tenant context for policy/audit side effects | none | global body cap |
| POST | `/classify/batch` | Review access | `reviewer`, `maker`, `checker`, `admin` | credential-derived tenant context for policy/audit side effects | `batch_classify` when enabled | global body cap |
| POST | `/review` | Review access | `reviewer`, `maker`, `checker`, `admin` | persisted sessions are scoped to credential-derived tenant id | `review` when enabled | global body cap |
| POST | `/cite-public-source` | Review access | `reviewer`, `maker`, `checker`, `admin` | credential-derived tenant context; external provider use follows tenant/deployer opt-in | none | global body cap |
| POST | `/request-approval` | Review access | `reviewer`, `maker`, `checker`, `admin` | approval request recorded under credential-derived tenant id when persistence is enabled | `decision` when enabled | global body cap |
| POST | `/redact-pii` | Review access | `reviewer`, `maker`, `checker`, `admin` | credential-derived tenant context; no reidentification mapping is persisted by this action | none | global body cap |
| POST | `/hold-until-public` | Review access | `reviewer`, `maker`, `checker`, `admin` | credential-derived tenant context; no reidentification mapping is persisted by this action | none | global body cap |
| POST | `/safe-rewrite` | Review access | `reviewer`, `maker`, `checker`, `admin` | credential-derived tenant context; no reidentification mapping is persisted by this action | none | global body cap |
| POST | `/pseudonymize` | Review access | `reviewer`, `maker`, `checker`, `admin` | persisted mappings are scoped to credential-derived tenant id when enabled and requested | none | global body cap |
| POST | `/anonymize` | Review access | `reviewer`, `maker`, `checker`, `admin` | credential-derived tenant context; no reidentification mapping is persisted | none | global body cap |
| POST | `/redact` | Review access | `reviewer`, `maker`, `checker`, `admin` | credential-derived tenant context; no reidentification mapping is persisted | none | global body cap |
| POST | `/documents/scrub` | Review access | `reviewer`, `maker`, `checker`, `admin` | credential-derived tenant context for auth/audit; scrubbed bytes returned to caller | none | global body cap |
| POST | `/reidentify` | Review access | `reviewer`, `maker`, `checker`, `admin` | persisted mapping lookup is scoped to credential-derived tenant id | `reidentify` when enabled | global body cap |
| POST | `/review/{review_id}/decision` | Decision access | `maker`, `checker`, `admin` | review id lookup and decision append are scoped to credential-derived tenant id | `decision` when enabled | global body cap |
| GET | `/review/{review_id}` | Audit access | `auditor`, `checker`, `admin` | review id lookup is scoped to credential-derived tenant id | none | n/a |

## Operator Notes

- Treat `/openapi.json`, `/docs`, `/redoc`, `/diagnostics`, and `/metrics` as internal routes in production unless a proxy policy explicitly allows them.
- Local daemon ACL is not a substitute for tenant auth on hosted deployments.
- Public demo routes must remain disabled unless intentionally exposing the deterministic demo.
- Built-in route rate limits are process-local; enforce equivalent distributed limits at the proxy/gateway layer for multi-worker deployments.
- Any new route must be added here with auth group, role set, tenant scope, rate limit, and payload cap before release.
