# Adapter Auth

Status: normative for adapters. Authentication identifies tenant, subject, and roles before review, rewrite, approval, reidentify, audit, or erasure operations.

Use this page with `docs/admin-security.md`, `docs/security/local-daemon.md`, and `docs/integrations/adapter-protocol.md`.

## Supported Modes

| Mode | Header | Use |
|---|---|---|
| API key registry | `X-API-Key: <key>` | Direct API, DMS hooks, server-side integrations, and hosted adapters where an API key maps to one tenant credential. |
| JWT | `Authorization: Bearer <jwt>` | Enterprise adapters behind Okta, Microsoft Entra ID, or another OIDC issuer. |
| Local daemon pairing | `X-Junas-Local-Token: <signed-token>` | Same-device browser, Office, Word, desktop, and local fallback clients calling the packaged daemon. |

Do not send API keys, JWTs, local tokens, or tenant ids in query strings. Do not store auth material in telemetry, SIEM event fields, screenshots, support bundles, or fixture text.

## API Key Registry

Enable tenancy and API-key auth with tenant credentials:

```sh
export JUNAS_TENANCY_ENABLED=1
export JUNAS_TENANCY_AUTH_MODES=api_key
export JUNAS_TENANT_CREDENTIALS_JSON='{"tenant-a-key":{"tenant_id":"tenant-a","subject":"legal-ops","roles":["reviewer","maker","auditor"]}}'
```

Adapters send:

```http
X-API-Key: tenant-a-key
```

Backend behavior:

- Compares keys with the tenant credential registry.
- Resolves `tenant_id`, `subject`, and `roles` from the matched credential.
- Rejects missing or unknown keys with 401.
- Applies route roles after tenant resolution.

Use distinct keys per tenant, deployment stage, and adapter class. Rotate by adding a replacement credential, deploying adapters with the new key, then removing the old key after active retry windows expire.

## JWT

Enable JWT mode for OIDC-style deployments:

```sh
export JUNAS_TENANCY_ENABLED=1
export JUNAS_TENANCY_AUTH_MODES=jwt
export JUNAS_JWT_ISSUER=https://idp.example/
export JUNAS_JWT_AUDIENCE=junas-api
export JUNAS_JWT_JWKS_URL=https://idp.example/.well-known/jwks.json
export JUNAS_JWT_TENANT_CLAIM=tenant_id
export JUNAS_JWT_SUBJECT_CLAIM=sub
export JUNAS_JWT_ROLES_CLAIM=roles
```

Adapters send:

```http
Authorization: Bearer <jwt>
```

Backend behavior:

- Validates signature, issuer, audience, expiry, and not-before claims.
- Reads tenant, subject, and roles from configured claims.
- Rejects missing tenant claim with 401.
- Rejects tokens with no recognized roles with 403.

Roles must map to Junas route roles:

| Role | Allowed route family |
|---|---|
| `reviewer`, `maker`, `checker`, `admin` | Review and rewrite endpoints. |
| `maker`, `checker`, `admin` | Decision and approval-changing endpoints. |
| `auditor`, `checker`, `admin` | Review-session reads and audit-oriented endpoints. |

SAML deployments should terminate SAML at an IdP bridge or identity-aware proxy and pass a signed JWT to Junas. Junas does not parse SAML assertions directly.

## Local Daemon Pairing

Local daemon auth is for same-device clients, not hosted multi-tenant trust. Pairing flow:

1. Adapter calls `POST /local/pairing/start` with client display name.
2. Desktop/tray approval calls `POST /local/pairing/approve` with pairing id, code, and daemon secret.
3. Adapter calls `POST /local/pairing/claim` and receives a signed local client token.
4. Adapter sends protected requests with `X-Junas-Local-Token`.

Current local TTLs:

- Pairing request TTL: 300 seconds.
- Signed local client token TTL: 90 days.

When local ACL is enabled, browser-origin requests must pass both checks:

- `Origin` matches `JUNAS_LOCAL_DAEMON_ALLOWED_ORIGINS`.
- Protected request includes `X-Junas-Local-Token`.

Local token storage rules:

- Browser/Office adapters may store local token in extension or Office runtime storage only when local daemon mode is selected.
- Do not sync local tokens to cloud storage when the platform offers non-sync storage.
- Do not write local tokens to logs, telemetry, DOM, URLs, or screenshots.
- Treat local token as a same-user secret; local malware or same-user processes may still read process memory, browser storage, files, or keychain prompts.

## Tenant Context

Tenant context is derived only from validated credentials:

| Source | Tenant | Subject | Roles |
|---|---|---|---|
| API key registry | credential `tenant_id` | credential `subject` | credential `roles` |
| JWT | configured tenant claim | configured subject claim | configured roles claim |
| Local daemon token | local daemon runtime context | paired local client | local protected-client capability |

Caller-supplied tenant ids are ignored because they are not proof of authority. Headers or body fields such as `X-Tenant-ID`, `tenant_id`, matter tenant, workspace tenant, or adapter tenant hints are workflow context only; they must not select storage, journals, mappings, subject indexes, matter stores, or policy ownership.

Ignoring caller-supplied tenant ids prevents:

- Tenant A reading Tenant B review sessions with guessed ids.
- Reidentify calls crossing tenant mapping stores.
- Approval or decision writes against another tenant's journal.
- Subject erasure, matter, or session operations targeting another tenant by header spoofing.
- Adapter bugs that accidentally mix customer workspace ids with backend tenant ids.

## Route Auth Expectations

| Adapter action | Endpoint family | Required auth |
|---|---|---|
| Review before completion | `/review`, rewrite/redact/pseudonymize variants | API key/JWT review role or valid local token. |
| Request approval | `/request-approval` | API key/JWT review-capable role or valid local token where local approval is enabled. |
| Record reviewer decision | `/review/{review_id}/decision` | API key/JWT maker/checker/admin role. |
| Read review state | `/review/{review_id}` | API key/JWT auditor/checker/admin role. |
| Reidentify | `/reidentify` | Tenant-scoped credential with access to that tenant's mapping store. |
| Local pairing approve | `/local/pairing/approve` | Daemon secret via `X-Junas-Local-Token`. |

Adapters must fail closed for auth failures on controlled workflows. Do not retry 401 or 403 automatically; route the user to pairing, sign-in, or admin remediation.

## Telemetry Boundary

Auth telemetry may include:

- `auth_mode`
- `tenant_hash`
- `role_count`
- `subject_hash`
- `surface`
- `workflow`
- `failure_class`
- `status_code`

Auth telemetry must not include:

- API keys, JWTs, local tokens, daemon secrets, tenant ids in clear text, subject ids in clear text, auth headers, cookies, endpoint URLs with credentials, pairing codes, or QR-code payloads.
