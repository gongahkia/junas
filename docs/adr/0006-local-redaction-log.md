# ADR 0006: Local Redaction Log

Status: Accepted

## Context

Junas already has a review journal for policy decisions, approval events, audit export, and subject-erasure tombstones. Local-only deployments can write machine-local journal and mapping files when persistence keys are configured. A separate always-on redaction-event log would help users verify what was detected and when, but it would also create another sensitive metadata store on the endpoint.

## Decision

Do not add a separate local redaction-event log for v1. Use the existing review journal as the only local evidence log, and keep it disabled unless local persistence is configured with explicit keys.

Local-only evidence behavior:

- Default state: no separate redaction log UI or background event stream.
- Storage path: `${JUNAS_JOURNAL_DIR:-./junas-journal}` or the tenant-scoped equivalent.
- Required keys: `JUNAS_JOURNAL_KEY` or `JUNAS_JOURNAL_KEYS_FILE` for tamper-evident journal entries; mapping/reidentify paths also need mapping and subject-index keys.
- Stored data: hashes, counts, finding ids, policy decisions, action names, timestamps, and tombstones; no raw prompt, email, document, matched text, mapping value, auth token, or endpoint secret should be added for convenience.
- Retention: operator-owned through `docs/security/data-retention.md` and the retention manifest.
- UI exposure: none in v1. Operators can use `scripts/verify_journal.py`, audit-pack export, and documented local-only deployment paths.

## Rationale

The user value is auditability: proving that review occurred, which findings/actions were produced, and whether later reviewer or erasure events changed replay state. The existing journal already supports that model without adding a second store with its own deletion, encryption, and support burden.

The privacy risk is metadata accumulation. A local redaction timeline can reveal workflow timing, repeated document hashes, sensitive categories, and policy decisions even without raw content. Keeping one keyed, documented journal reduces the local attack surface and makes retention/erasure behavior easier to explain.

## Consequences

- Local users do not get a consumer-facing redaction history panel in v1.
- Local deployments that need evidence must configure journal keys and host encryption.
- Future UI work must read replayed, sanitized journal state instead of introducing an independent log.
- If a later issue adds a redaction history UI, it must define retention, deletion, export, and subject-erasure behavior before implementation.
