# Mapping Store Hardening

Kaypoh can persist `/anonymize` mapping tables when `KAYPOH_REVIEW_PERSIST=1` so
`/reidentify` can restore text later from a `document_hash`. Those mappings contain the
original PII/MNPI scalars and should be treated as sensitive secrets.

## Encryption

Set `KAYPOH_MAPPING_STORE_KEY` to enable authenticated encryption for newly written
mapping files:

```sh
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

```sh
export KAYPOH_MAPPING_STORE_KEY='paste-generated-key-here'
export KAYPOH_REVIEW_PERSIST=1
```

Encrypted mapping files are stored as Fernet envelopes under
`${KAYPOH_JOURNAL_DIR:-./kaypoh-journal}/mappings/`. Existing plaintext mapping files
remain readable for compatibility, but are not rewritten automatically.

Key loss is destructive: encrypted mappings cannot be recovered without the key. Rotate
by setting a new key and rewriting only mappings that still need to be retained.

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

## Deployment Controls

- Restrict `${KAYPOH_JOURNAL_DIR}` to the service account that runs Kaypoh.
- Use FileVault, BitLocker, LUKS, or cloud-volume encryption for disk-level protection.
- Keep `KAYPOH_MAPPING_STORE_KEY` in a secrets manager, not in checked-in config.
- Do not share mapping files between tenants; use separate journal directories for each tenant.
