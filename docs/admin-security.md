# Admin And Security Guide

## Identity

Junas server supports tenant API-key registry mode and JWT mode.

API-key registry:

```sh
uv run python scripts/generate_tenant_credentials.py \
  --tenant-id tenant-a \
  --subject legal-ops \
  --roles reviewer,maker,auditor
```

JWT mode for Okta, Microsoft Entra ID, or another OIDC issuer:

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

SAML deployments should terminate SAML at the identity-aware proxy or IdP bridge and pass a signed JWT to Junas. Junas does not parse SAML assertions directly.

## Tenant Isolation

Tenant identity is derived from validated API keys or JWT claims. Caller-supplied tenant headers are ignored. Journals, mappings, subject index, sessions, matter terms, and lane configs are tenant-scoped under `${JUNAS_JOURNAL_DIR}/tenants/{tenant_id}/`.

Roles:

- `reviewer`, `maker`, `checker`, `admin`: review and rewrite endpoints.
- `maker`, `checker`, `admin`: decision recording.
- `auditor`, `checker`, `admin`: review-session reads.

## Key Rotation

Production preflight requires a journal keystore:

```toml
active = "v2"

[keys.v1]
secret = "old-secret"

[keys.v2]
secret = "new-secret"
```

Rotate:

```sh
export JUNAS_JOURNAL_KEYS_FILE=/etc/junas/journal-keys.toml
uv run python - <<'PY'
from junas.review.journal import rotate_journal_key
rotate_journal_key(from_version="v1", to_version="v2", reason="scheduled rotation")
PY
uv run python scripts/verify_journal.py
```

Mapping-store and subject-index keys are customer-held secrets. Rotate them by creating a new key in the secret manager, restarting Junas, and rewriting only retained mappings that still need reidentification.

Journal integrity is conditional on `JUNAS_JOURNAL_KEY` or
`JUNAS_JOURNAL_KEYS_FILE`. The HMAC chain is tamper-evident evidence verified by
`scripts/verify_journal.py`; it does not provide OS-level append-only storage.

Mapping-store encryption is conditional on `JUNAS_MAPPING_STORE_KEY`. Without that
key, persisted mapping files are not application-encrypted and must rely on
service-account permissions plus host/volume encryption.

## External KMS

Junas reads secrets from environment variables or mounted files. Use AWS KMS/Secrets Manager, Azure Key Vault, GCP KMS/Secret Manager, HashiCorp Vault, Kubernetes Secrets encrypted at rest, or macOS Keychain to inject:

- `JUNAS_JOURNAL_KEYS_FILE`
- `JUNAS_MAPPING_STORE_KEY`
- `JUNAS_SUBJECT_INDEX_KEY`
- provider API keys

The runtime does not call cloud KMS APIs directly. Keep decrypt permission outside Junas and inject only the final runtime secret into the process.

## Local Daemon Pairing

Browser and Office clients should use `/local/pairing/start`, desktop approval through `/local/pairing/approve`, then `/local/pairing/claim` to receive a signed expiring local client token. Protected endpoints accept the signed token in `X-Junas-Local-Token`.

## Local Daemon CSRF Boundary

Browser-origin requests to a local Junas daemon must pass both checks:

- `Origin` must match the configured local daemon allowlist.
- Protected requests must include `X-Junas-Local-Token` with the signed local client token.

This follows the [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) guidance to require a custom request header that forces CORS preflight, paired with strict origin validation. Do not rely on cookies, ambient browser credentials, or loopback-only binding as the CSRF boundary. Simple HTML form posts cannot set `X-Junas-Local-Token` and must fail before reaching review, rewrite, reidentify, approval, or metadata-scrub handlers.

## Logs And SIEM

Backend request logs include request ID, route, status, and latency only. SIEM events hash or drop sensitive values. Do not enable reverse-proxy body logging for Junas routes.

Enable SIEM:

```sh
export JUNAS_SIEM_ENABLED=1
export JUNAS_SIEM_SINK=syslog
export JUNAS_SIEM_SYSLOG_ADDRESS=udp://127.0.0.1:5514
export JUNAS_SIEM_FACILITY=local4
export JUNAS_SIEM_APP_NAME=junas
```
