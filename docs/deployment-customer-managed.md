# Customer-Managed Deployment Secret Custody

Customer-managed deployment means the customer runs the Junas backend and owns the
secret source of record. The backend can load secrets from environment variables or
mounted files, but production values must come from customer-controlled custody such as
customer KMS, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, HashiCorp
Vault, Kubernetes Secrets encrypted at rest with KMS, or macOS Keychain for a local
desktop SKU. Mapping, journal HMAC, and subject-index values are customer-held
secrets, not Junas sample defaults.

This page complements [deployment hardening](deployment-hardening.md), the
customer-managed Docker example, and the Kubernetes reference manifests. Do not use
sample values from `deploy/docker/` or `deploy/kubernetes/` in production.

## Required Secret Ownership

| Control | Required secret | Custody rule | Runtime use |
|---|---|---|---|
| Mapping store encryption | `JUNAS_MAPPING_STORE_KEY` | customer-held Fernet key from a secret manager or KMS-backed secret. | Encrypts persisted `/pseudonymize` mapping files when `JUNAS_REVIEW_PERSIST=1`. |
| Journal HMAC | `JUNAS_JOURNAL_KEYS_FILE` for production rotation; `JUNAS_JOURNAL_KEY` only for legacy or single-key local use. | customer-held HMAC secret; mount the key file read-only. | Seals review, policy, approval, export, and erasure journal events for tamper-evidence. |
| Subject index lookup | `JUNAS_SUBJECT_INDEX_KEY` | customer-held HMAC secret retained with restore material. | HMACs subject values so subject erasure can find affected mappings and review references. |
| Tenant auth | `JUNAS_TENANT_CREDENTIALS_JSON`, JWT issuer/JWKS settings, or upstream mTLS identity. | Customer IdP, credential registry, or proxy identity layer. | Binds review and approval actions to tenant-scoped principals. |
| Retention evidence | `JUNAS_RETENTION_MANIFEST` | Customer-owned policy/runbook reference. | Production preflight checks that journals, mappings, subject index, SIEM, backups, logs, and audit packs have declared controls. |

`JUNAS_POLICY_CONFIG` is not normally a secret, but the customer must own its change
control because policy id/version values appear in audit evidence.

## Production Gates

Production persistence requires these controls before the backend serves traffic:

```sh
export JUNAS_REVIEW_PERSIST=1
export JUNAS_ALLOW_PLAINTEXT_MAPPINGS=0
export JUNAS_JOURNAL_KEYS_FILE=/etc/junas/journal-keys.toml
export JUNAS_MAPPING_STORE_KEY='from-customer-secret-manager'
export JUNAS_SUBJECT_INDEX_KEY='from-customer-secret-manager'
export JUNAS_RETENTION_MANIFEST=/etc/junas/retention_manifest.json

uv run python scripts/preflight.py --deployment production --strict
```

`scripts/preflight.py --deployment production --strict` checks the mapping key,
subject-index key, journal key-file rotation config, plaintext-mapping disablement,
tenant/auth posture, policy config, and retention manifest.

## Failure Boundaries

- Without `JUNAS_MAPPING_STORE_KEY`, persisted mapping files are not application-encrypted;
  production strict preflight fails when persistence is enabled.
- Without `JUNAS_JOURNAL_KEYS_FILE`, production strict preflight fails because journal
  key rotation is not configured. Journal HMAC provides tamper-evidence; it does not
  make the OS/filesystem layer append-only.
- Without `JUNAS_SUBJECT_INDEX_KEY`, subject erasure cannot look up prior subject
  values by HMAC. Production strict preflight fails when persistence is enabled.
- Without `JUNAS_RETENTION_MANIFEST`, production strict preflight fails because artifact
  retention and deletion controls are undeclared.
- Losing the mapping key makes encrypted mappings unrecoverable. Losing the subject
  index key breaks lookup against existing HMAC buckets until the index is rebuilt from
  retained source data. Losing journal HMAC keys breaks verification for entries sealed
  with those keys.

## Deployment Notes

For Docker, use `docker-compose.production.example.yml` as a shape only. Populate
`JUNAS_MAPPING_STORE_KEY`, `JUNAS_SUBJECT_INDEX_KEY`, `JUNAS_TENANT_CREDENTIALS_JSON`,
and the mounted journal key file from the customer's secret platform before startup.

For Kubernetes, keep `deploy/kubernetes/secret.example.yaml` as a placeholder file only.
Production clusters should source the same values from a customer secret controller or
KMS-backed Kubernetes Secret, mount `journal-keys.toml` read-only, and restrict reads to
the Junas service account.

For backup/restore, back up the journal directory, policy config, retention manifest,
and the secret versions needed to verify journals, decrypt retained mappings, and replay
subject erasure. Test restore plus `scripts/verify_journal.py` and
`scripts/erase_subject.py --backfill --dry-run` before pilot traffic.

## Operator Checklist

- Generate mapping, journal, and subject-index secrets inside the customer secret
  platform; do not paste production values into checked-in files or shell history.
- Mount key files read-only and keep writable state under the service-owned
  `JUNAS_JOURNAL_DIR`.
- Keep sample secrets, example manifests, and local `.env` files out of production
  release tickets.
- Run `uv run python scripts/check_retention_manifest.py --manifest /etc/junas/retention_manifest.json --strict`.
- Run `uv run python scripts/preflight.py --deployment production --strict` in CI or as
  an entrypoint before starting Uvicorn.
- Rotate journal HMAC by adding a new version to `JUNAS_JOURNAL_KEYS_FILE` and changing
  `active`; retain older versions while old journal entries must verify.
- Rotate mapping and subject-index keys only with a migration/backfill plan; old
  encrypted mappings and HMAC buckets depend on their original keys.
- Verify reverse proxy, process logs, SIEM exports, and support bundles do not include
  raw body text, matched spans, mapping originals, subject values, or auth headers.
