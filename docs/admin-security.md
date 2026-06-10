# Admin And Security Guide

## Identity

Kaypoh server supports tenant API-key registry mode and JWT mode.

API-key registry:

```sh
uv run python scripts/generate_tenant_credentials.py \
  --tenant-id tenant-a \
  --subject legal-ops \
  --roles reviewer,maker,auditor
```

JWT mode for Okta, Microsoft Entra ID, or another OIDC issuer:

```sh
export KAYPOH_TENANCY_ENABLED=1
export KAYPOH_TENANCY_AUTH_MODES=jwt
export KAYPOH_JWT_ISSUER=https://idp.example/
export KAYPOH_JWT_AUDIENCE=kaypoh-api
export KAYPOH_JWT_JWKS_URL=https://idp.example/.well-known/jwks.json
export KAYPOH_JWT_TENANT_CLAIM=tenant_id
export KAYPOH_JWT_SUBJECT_CLAIM=sub
export KAYPOH_JWT_ROLES_CLAIM=roles
```

SAML deployments should terminate SAML at the identity-aware proxy or IdP bridge and pass a signed JWT to Kaypoh. Kaypoh does not parse SAML assertions directly.

## Tenant Isolation

Tenant identity is derived from validated API keys or JWT claims. Caller-supplied tenant headers are ignored. Journals, mappings, subject index, sessions, matter terms, and lane configs are tenant-scoped under `${KAYPOH_JOURNAL_DIR}/tenants/{tenant_id}/`.

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
export KAYPOH_JOURNAL_KEYS_FILE=/etc/kaypoh/journal-keys.toml
uv run python - <<'PY'
from kaypoh.review.journal import rotate_journal_key
rotate_journal_key(from_version="v1", to_version="v2", reason="scheduled rotation")
PY
uv run python scripts/verify_journal.py
```

Mapping-store and subject-index keys are customer-held secrets. Rotate them by creating a new key in the secret manager, restarting Kaypoh, and rewriting only retained mappings that still need reidentification.

## External KMS

Kaypoh reads secrets from environment variables or mounted files. Use AWS KMS/Secrets Manager, Azure Key Vault, GCP KMS/Secret Manager, HashiCorp Vault, Kubernetes Secrets encrypted at rest, or macOS Keychain to inject:

- `KAYPOH_JOURNAL_KEYS_FILE`
- `KAYPOH_MAPPING_STORE_KEY`
- `KAYPOH_SUBJECT_INDEX_KEY`
- provider API keys

The runtime does not call cloud KMS APIs directly. Keep decrypt permission outside Kaypoh and inject only the final runtime secret into the process.

## Local Daemon Pairing

Browser and Office clients should use `/local/pairing/start`, desktop approval through `/local/pairing/approve`, then `/local/pairing/claim` to receive a signed expiring local client token. Protected endpoints accept the signed token in `X-Kaypoh-Local-Token`.

## Logs And SIEM

Backend request logs include request ID, route, status, and latency only. SIEM events hash or drop sensitive values. Do not enable reverse-proxy body logging for Kaypoh routes.

Enable SIEM:

```sh
export KAYPOH_SIEM_ENABLED=1
export KAYPOH_SIEM_SINK=syslog
export KAYPOH_SIEM_SYSLOG_ADDRESS=udp://127.0.0.1:5514
export KAYPOH_SIEM_FACILITY=local4
export KAYPOH_SIEM_APP_NAME=kaypoh
```
