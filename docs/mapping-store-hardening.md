# Mapping Store Hardening

Junas can persist `/pseudonymize` mapping tables when `JUNAS_REVIEW_PERSIST=1` so
`/reidentify` can restore text later from a `document_hash`. Those mappings contain the
original PII/MNPI scalars and should be treated as sensitive secrets.

## Encryption

Set `JUNAS_MAPPING_STORE_KEY` to enable authenticated encryption for newly written
mapping files:

```sh
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

```sh
export JUNAS_MAPPING_STORE_KEY='paste-generated-key-here'
export JUNAS_SUBJECT_INDEX_KEY='paste-subject-index-hmac-key-here'
export JUNAS_REVIEW_PERSIST=1
```

Encrypted mapping files are stored as Fernet envelopes under
`${JUNAS_JOURNAL_DIR:-./junas-journal}/mappings/`. Existing plaintext mapping files
remain readable for compatibility, but are not rewritten automatically.

Without `JUNAS_MAPPING_STORE_KEY`, persisted mapping files are not
application-encrypted; they are protected only by service-account permissions and
host/volume encryption. Key loss is destructive: encrypted mapping files cannot be
recovered without the key. Rotate
by setting a new key and rewriting only mappings that still need to be retained.

`JUNAS_SUBJECT_INDEX_KEY` is separate from `JUNAS_MAPPING_STORE_KEY`. It HMACs
canonical subject values into `${JUNAS_JOURNAL_DIR:-./junas-journal}/subject_index/index.json`
so erasure requests can find affected mapping files without storing raw PII in the
index. When `JUNAS_REVIEW_PERSIST=1`, Junas fails closed if this key is missing.

## Retention

Delete one mapping by hash:

```sh
PYTHONPATH=src python3 scripts/purge_mappings.py --document-hash <sha256>
```

Preview or apply age-based retention:

```sh
PYTHONPATH=src python3 scripts/purge_mappings.py --older-than-days 30 --dry-run
PYTHONPATH=src python3 scripts/purge_mappings.py --older-than-days 30
```

For subject-initiated erasure, rebuild the reverse index if needed and erase by
subject value with a legal/ticket citation:

```sh
PYTHONPATH=src python3 scripts/erase_subject.py --backfill
PYTHONPATH=src python3 scripts/erase_subject.py --value 'jane@example.com' --citation DSR-2026-05-28
```

The subject erasure path deletes reversible mapping files, appends
`subject_erasure_recorded` journal tombstones for review-session findings, and removes
the matching HMAC index bucket. CLI JSON output includes hashes and document/review
references, not the raw subject value.

Detailed artifact disposition is documented in `docs/security/subject-erasure.md`.

## Journal Integrity Boundary

Review journals use HMAC chaining when `JUNAS_JOURNAL_KEY` or
`JUNAS_JOURNAL_KEYS_FILE` is supplied. That provides tamper-evidence for verification
with `scripts/verify_journal.py`; it does not provide OS-level append-only storage or
prevent deletion by a host administrator.

## Deployment Controls

- Restrict `${JUNAS_JOURNAL_DIR}` to the service account that runs Junas.
- Use FileVault, BitLocker, LUKS, or cloud-volume encryption for disk-level protection.
- Keep `JUNAS_MAPPING_STORE_KEY` in a secrets manager, not in checked-in config.
- Keep `JUNAS_SUBJECT_INDEX_KEY` in a secrets manager; changing it requires
  `scripts/erase_subject.py --backfill` before subject lookups will match older data.
- Do not share mapping files between tenants; use separate journal directories for each tenant.
- Treat HMAC journal verification as tamper-evidence, not OS-level append-only storage.
