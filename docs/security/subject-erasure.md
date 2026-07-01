# Subject Erasure

Subject erasure in Junas is an indexed lookup and disposition workflow. It deletes
reversible mappings, removes the subject-index bucket, and appends tombstones to
immutable journaled review sessions. It does not rewrite external logs, SIEM indexes,
backups, or legal-hold archives.

## Prerequisites

Required when `JUNAS_REVIEW_PERSIST=1`:

- `JUNAS_JOURNAL_DIR`: service-account owned persistence root.
- `JUNAS_JOURNAL_KEY` or `JUNAS_JOURNAL_KEYS_FILE`: HMAC journal verification.
- `JUNAS_MAPPING_STORE_KEY`: encrypted persisted mapping files.
- `JUNAS_SUBJECT_INDEX_KEY`: HMAC lookup key for subject values.

If data was restored from backup or predates subject-index enforcement, rebuild the
index before lookup:

```sh
uv run python scripts/erase_subject.py --tenant tenant-a --backfill --json
```

## Workflow

1. Run dry-run lookup:

```sh
uv run python scripts/erase_subject.py \
  --tenant tenant-a \
  --value "jane@example.com" \
  --dry-run \
  --json
```

2. Execute erasure with a ticket, DSAR, court order, or legal citation:

```sh
uv run python scripts/erase_subject.py \
  --tenant tenant-a \
  --value "jane@example.com" \
  --citation "DSR-2026-05-28-001" \
  --json
```

3. Verify no active subject-index matches remain and the journal chain still verifies:

```sh
uv run python scripts/erase_subject.py --tenant tenant-a --value "jane@example.com" --dry-run --json
uv run python scripts/verify_journal.py --tenant tenant-a
```

The raw `--value` is used to compute an HMAC lookup and is not written to the subject
index, mapping-store deletion event, or review-session tombstone.

## Artifact Disposition

| Artifact | Disposition | Notes |
|---|---|---|
| Persisted mapping files | Deleted | Matching `${JUNAS_JOURNAL_DIR}/mappings/{document_hash}.json` files are removed by `scripts/erase_subject.py` through `purge_mapping`. |
| Subject index bucket | Deleted | The matching HMAC bucket is removed from `subject_index/index.json` after mapping and review dispositions are recorded. |
| Review journal entries | Tombstoned | Prior `review_started` and decision events remain append-only. `subject_erasure_recorded` events list affected `finding_ids`, rules, and document hash. |
| Review session state | Tombstoned by replay | Session state is rebuilt from journal replay and must treat erased findings as tombstoned rather than active. |
| Audit packs | Retained or expired by operator policy | Already exported sealed packs are not mutated in place. Expire, supersede, or annotate them according to the retention/legal-hold policy. |
| SIEM exports | Delegated | Junas cannot erase external SIEM indexes. Use SIEM retention, deletion, or legal-hold controls. |
| Application and proxy logs | Delegated | Logs should already exclude raw body text; retention/deletion belongs to the log platform. |
| Backups and cold archives | Delegated | The operator must apply backup expiry, restore-time re-erasure, or legal-hold procedures outside Junas. |
| Fixtures and reports | Retained only if scrubbed | Production subject data must not be promoted into fixtures or reports. Remove accidental data and run `scripts/check_fixture_scrub.py`. |
| Matter terms | Operator-managed | Matter-defined-term sidecars may contain casefolded terms; delete or retain them according to matter lifecycle policy. |

## Output Fields

`scripts/erase_subject.py --json` returns hashes and ids only:

- `pii_hash`
- `matched_mapping_documents`
- `matched_review_sessions`
- `deleted_mapping_documents`
- `missing_mapping_documents`
- `journaled_review_sessions`
- `removed_index_entries`

Do not paste raw subject values into tickets or release notes; use `pii_hash`,
`document_hash`, `review_id`, and the erasure citation.
