# Deployment Hardening

This guide covers the controls expected around a production Kaypoh deployment. It
does not replace a formal SOC 2 / ISO 27001 control set; it gives operators concrete
defaults for filesystem protection, transport hardening, secrets handling, and SIEM
export.

## Filesystem Boundaries

Run Kaypoh as a dedicated service account and keep runtime state out of user-writable
directories.

```sh
sudo install -d -o kaypoh -g kaypoh -m 0700 /var/lib/kaypoh
sudo install -d -o kaypoh -g kaypoh -m 0700 /var/lib/kaypoh/journal
sudo install -d -o kaypoh -g kaypoh -m 0750 /etc/kaypoh
```

Recommended ownership:

| Path | Owner | Mode | Contents |
|---|---|---:|---|
| `/etc/kaypoh/config.toml` | `root:kaypoh` | `0640` | Runtime config without raw secrets |
| `/var/lib/kaypoh/journal` | `kaypoh:kaypoh` | `0700` | HMAC journal, mapping store, audit packs |
| `/var/log/kaypoh` | `kaypoh:adm` | `0750` | Process logs when not shipping directly |

When `KAYPOH_TENANCY_ENABLED=1`, Kaypoh partitions journals, mappings, and defined-term
session sidecars under `${KAYPOH_JOURNAL_DIR}/tenants/{tenant_id}/`. Tenant IDs are
derived from configured API-key credentials or validated JWT claims, never from
caller-supplied tenant headers. Keep the base journal directory private to the Kaypoh
service account.

## At-Rest Encryption

Use host or volume encryption even when `KAYPOH_MAPPING_STORE_KEY` is enabled. The
mapping key protects mapping files; it does not encrypt the HMAC journal, process logs,
or audit-pack exports.

- macOS: FileVault for desktop deployments.
- Linux VM / bare metal: LUKS-backed volume for `/var/lib/kaypoh`.
- Windows: BitLocker on the service volume.
- Cloud: encrypted block volumes with customer-managed KMS keys where available.

Set `KAYPOH_MAPPING_STORE_KEY` from a secret manager for persisted mapping
confidentiality. See `docs/mapping-store-hardening.md` for key generation and purge
commands.

## Reverse Proxy

Terminate public TLS at a reverse proxy and keep the app bound to loopback or a private
pod/service network.

Minimal Nginx shape:

```nginx
server {
    listen 443 ssl http2;
    server_name kaypoh.internal.example;

    ssl_certificate     /etc/nginx/certs/kaypoh.crt;
    ssl_certificate_key /etc/nginx/certs/kaypoh.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Request-ID $request_id;
    }
}
```

For mTLS, require a client CA at the proxy layer:

```nginx
ssl_client_certificate /etc/nginx/certs/client-ca.crt;
ssl_verify_client on;
proxy_set_header X-Client-Cert-Subject $ssl_client_s_dn;
```

Minimal Envoy listener shape:

```yaml
filter_chains:
  - transport_socket:
      name: envoy.transport_sockets.tls
      typed_config:
        "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.DownstreamTlsContext
        common_tls_context:
          tls_certificates:
            - certificate_chain: { filename: /etc/envoy/certs/kaypoh.crt }
              private_key: { filename: /etc/envoy/certs/kaypoh.key }
          validation_context:
            trusted_ca: { filename: /etc/envoy/certs/client-ca.crt }
    filters:
      - name: envoy.filters.network.http_connection_manager
```

Keep `KAYPOH_API_KEY` enabled behind the proxy unless an upstream identity layer already
performs authenticated, authorized routing.

## Secrets

Keep these values out of checked-in config and shell history:

| Secret | Purpose |
|---|---|
| `KAYPOH_API_KEY` | API access gate for local/server endpoints |
| `KAYPOH_JOURNAL_KEY` or `KAYPOH_JOURNAL_KEYS_FILE` | HMAC journal sealing |
| `KAYPOH_MAPPING_STORE_KEY` | Fernet encryption for persisted mappings |
| `KAYPOH_SUBJECT_INDEX_KEY` | HMAC key for subject-erasure reverse-index lookups |
| `KAYPOH_EXA_API_KEY`, `KAYPOH_TINYFISH_API_KEY`, `KAYPOH_LLM_API_KEY` | External providers |

Recommended sources:

- AWS Secrets Manager or SSM Parameter Store with instance/pod IAM.
- HashiCorp Vault with short-lived leases.
- Kubernetes Secrets encrypted at rest with KMS and mounted as files or environment
  variables.
- macOS Keychain for desktop SKU operators.

## Kubernetes Baseline

Use read-only images and writable volumes only where Kaypoh must persist state.

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
volumes:
  - name: journal
    persistentVolumeClaim:
      claimName: kaypoh-journal
containers:
  - name: kaypoh
    image: ghcr.io/example/kaypoh:latest
    ports:
      - containerPort: 8000
    volumeMounts:
      - name: journal
        mountPath: /var/lib/kaypoh/journal
    env:
      - name: KAYPOH_JOURNAL_DIR
        value: /var/lib/kaypoh/journal
```

Add network policies so only the ingress/proxy namespace can reach the Kaypoh service.
If public evidence or remote LLM providers are disabled, block outbound internet egress.

## Tenant Auth And RBAC

Legacy single-tenant deployments can keep using `KAYPOH_API_KEY`. Multi-tenant server
deployments should enable tenancy and choose API-key registry mode, JWT mode, or both:

```sh
export KAYPOH_TENANCY_ENABLED=1
export KAYPOH_TENANCY_AUTH_MODES=api_key,jwt
export KAYPOH_TENANT_CREDENTIALS_JSON='{"tenant-a-key":{"tenant_id":"tenant-a","subject":"svc-a","roles":["reviewer","maker","auditor"]}}'
export KAYPOH_JWT_JWKS_URL=https://idp.example/.well-known/jwks.json
export KAYPOH_JWT_ISSUER=https://idp.example/
export KAYPOH_JWT_AUDIENCE=kaypoh-api
```

Supported roles are `reviewer`, `maker`, `checker`, `admin`, and `auditor`. Review,
pseudonymize, anonymize, redact, reidentify, and scrub routes accept `reviewer|maker|checker|admin`; decision
recording requires `maker|checker|admin`; review-session reads require
`auditor|checker|admin`.

Decision attribution is bound to the authenticated principal: JWT deployments record the
token subject, API-key deployments record the configured credential subject, and
`X-Reviewer-ID` is accepted only for local development with `KAYPOH_DEV_AUTH=1`.

## Subject Erasure Runbook

Subject erasure uses the HMAC reverse index under
`${KAYPOH_JOURNAL_DIR}/subject_index/` or the tenant-scoped equivalent. The index stores
only HMACs and persisted reference metadata; it does not store raw PII. Operators must
set the same `KAYPOH_SUBJECT_INDEX_KEY` used when the data was indexed.

Before handling a request, rebuild the index if the deployment predates subject-index
enforcement or if mappings/journals were restored from backup:

```sh
export KAYPOH_JOURNAL_DIR=/var/lib/kaypoh/journal
export KAYPOH_JOURNAL_KEY=...
export KAYPOH_SUBJECT_INDEX_KEY=...

uv run python scripts/erase_subject.py --tenant tenant-a --backfill --json
```

Use dry-run first and attach the ticket, DSAR, or legal citation to the real erase:

```sh
uv run python scripts/erase_subject.py \
  --tenant tenant-a \
  --value "jane@example.com" \
  --dry-run \
  --json

uv run python scripts/erase_subject.py \
  --tenant tenant-a \
  --value "jane@example.com" \
  --citation "DSR-2026-05-28-001" \
  --json
```

Verify the result by repeating the dry-run and checking journal integrity:

```sh
uv run python scripts/erase_subject.py --tenant tenant-a --value "jane@example.com" --dry-run --json
uv run python scripts/verify_journal.py --tenant tenant-a
```

This is not universal deletion. Reversible mapping files are deleted, and immutable review
journal references receive `subject_erasure_recorded` tombstones. Append-only journals,
application logs, SIEM exports, backups, cold archives, and records created before the
subject index existed remain governed by the customer's retention and legal-hold policy.
The operator must separately expire or tombstone those systems according to policy.

## Retention Manifest

Production strict preflight checks for an operator-maintained retention manifest. The
manifest records whether journal, mapping-store, application-log, SIEM, and backup
retention controls are configured; it does not perform deletion by itself.

Point Kaypoh at the manifest with `KAYPOH_RETENTION_MANIFEST`, or keep
`retention_manifest.json` at the repository/deployment root:

```json
{
  "controls": {
    "journal": { "retention_days": 2555 },
    "mapping_store": { "delete_after_days": 90 },
    "logs": { "policy": "log-platform-policy-123" },
    "siem": { "external_policy_ref": "splunk-index-retention" },
    "backups": { "retain_for_days": 365 }
  }
}
```

Validate it before production deploys:

```sh
uv run python scripts/check_retention_manifest.py --manifest /etc/kaypoh/retention_manifest.json --strict
KAYPOH_RETENTION_MANIFEST=/etc/kaypoh/retention_manifest.json uv run python scripts/preflight.py --deployment production --strict
```

## Document Ingest And Metadata

PDF review fails closed by default when the extracted text layer is missing, too sparse,
or image-only. Do not enable best-effort OCR in the server path; convert scanned files to
DOCX or submit a PDF with a reliable text layer.

`/review`, `/pseudonymize`, `/anonymize`, and `/redact` report DOCX/PDF/image container metadata under
`document.metadata_findings`. `/documents/scrub` removes supported DOCX properties,
comments, track-change author/date attributes, PDF info metadata, and JPEG/PNG EXIF where
the installed dependencies support that file type.

## SIEM Export

Kaypoh can emit JSON-over-syslog events for security and audit correlation. It is off by
default.

```toml
[siem]
enabled = true
sink = "syslog"
syslog_address = "udp://127.0.0.1:5514"
facility = "local4"
app_name = "kaypoh"
```

Equivalent environment variables:

```sh
export KAYPOH_SIEM_ENABLED=1
export KAYPOH_SIEM_SINK=syslog
export KAYPOH_SIEM_SYSLOG_ADDRESS=udp://127.0.0.1:5514
export KAYPOH_SIEM_FACILITY=local4
export KAYPOH_SIEM_APP_NAME=kaypoh
```

Emitted events use `schema_version="kaypoh.siem.v1"` and include:

| Event type | Source |
|---|---|
| `privacy_ledger` | External retrieval and LLM adjudication privacy decisions |
| `journal_event` | HMAC-sealed journal appends, summarized by payload hash |
| `security_event` | API-key denials, HTTP errors, mapping-store persistence/decrypt failures |

SIEM payloads do not include raw document text, matched finding text, mapping originals,
public-evidence query strings, reviewer rationales, or API secrets. Sensitive fields are
hashed or summarized with counts.
