# Data Retention Matrix

Retention is operator-owned. Junas provides artifact boundaries, purge helpers for
reversible mappings, subject-erasure tombstones for immutable journals, and a production
preflight check for declared retention controls.

## Matrix

| Artifact | Manifest control | Stored data | Storage boundary | Baseline policy | Erasure/deletion behavior |
|---|---|---|---|---|---|
| Review journal | `journal` | HMAC-chained review, policy, approval, export, and erasure events; current review findings are sanitized by default. | `${JUNAS_JOURNAL_DIR}/journal.jsonl` or tenant-scoped equivalent. | Long-lived audit evidence, commonly `2555` days or legal-hold policy. | Do not edit prior entries in place. Append `subject_erasure_recorded` tombstones and verify with `scripts/verify_journal.py`. |
| Mapping store | `mapping_store` | Encrypted reversible `/pseudonymize` mappings when persistence is enabled. | `${JUNAS_JOURNAL_DIR}/mappings/*.json` or tenant-scoped equivalent. | Short-lived reidentification support, commonly `90` days or shorter. | Delete with `scripts/purge_mappings.py` or `scripts/erase_subject.py`; encrypted data is unrecoverable after key loss. |
| Subject index | `subject_index` | HMAC(subject value) buckets pointing to mapping and review references; no raw subject values. | `${JUNAS_JOURNAL_DIR}/subject_index/index.json` or tenant-scoped equivalent. | Retain only while mapped/journaled references need lookup. | `scripts/erase_subject.py` removes matching HMAC buckets; rebuild with `--backfill` after restores. |
| Review sessions | `review_sessions` | Replayed review-session state derived from the journal. | Journal replay; no separate durable database in this repo. | Same as `journal` unless a future session store adds its own retention. | Subject erasure is represented by journal tombstones; do not expose erased findings as active state. |
| Matter terms | `matter_terms` | Lowercased matter-defined terms for cross-session review context. | `${JUNAS_JOURNAL_DIR}/matters/{matter_id}/defined_terms.json`. | Matter lifecycle policy, often matter close plus legal hold. | Operator-managed sidecar deletion; no API erasure endpoint exists in this repo. |
| Adapter telemetry | `adapter_telemetry` | Privacy-safe adapter events, decisions, counts, timings, and error types. | Adapter sink, browser/Office runtime sink, or customer telemetry platform. | Short operational window, commonly `30` to `90` days unless audit policy requires longer. | Delete in the telemetry platform; adapter telemetry must not include raw prompt, email, or document text. |
| SIEM exports | `siem` | Hash/count summarized privacy, journal, and security events. | Customer SIEM index or syslog sink. | Customer SIEM retention policy. | Managed by SIEM retention/legal-hold controls; Junas cannot erase external SIEM indexes. |
| Audit packs | `audit_packs` | ZIP exports containing manifest, journal slice, findings, and decisions for a review session. | Explicit output path, defaulting beside the journal. | Audit/legal evidence policy, commonly aligned with `journal`. | Expire or tombstone by operator policy; do not mutate a sealed pack in place. |
| Fixtures | `fixtures` | Synthetic or reviewed corpus fixtures and labels. | `test/fixtures/`. | Source-controlled test assets; no production raw data allowed. | Remove accidental sensitive fixtures and run `scripts/check_fixture_scrub.py` before commit. |
| Reports | `reports` | Local eval, latency, security, SBOM, and generated evidence outputs. | `reports/` and release-ticket attachments. | Per-run or release evidence retention; scrub before sharing. | Delete stale local reports; committed/generated reports must pass fixture scrub. |
| Application logs | `logs` | Request ids, routes, status, latency, and sanitized summaries. | Process log sink, reverse proxy, or customer logging platform. | Customer log-platform policy. | Managed by log-platform retention; reverse-proxy body logging must stay disabled. |
| Backups | `backups` | Backups of journal dir, config, keys, reports, and deployment state. | Customer backup/archive platform. | Customer backup and legal-hold policy. | Erasure from backups is delegated to customer backup controls and legal-hold process. |

## Retention Manifest Controls

Production preflight reads `JUNAS_RETENTION_MANIFEST` or `retention_manifest.json` and
requires one control per matrix row:

```json
{
  "schema_version": "junas.retention_manifest.v1",
  "controls": {
    "journal": { "retention_days": 2555 },
    "mapping_store": { "delete_after_days": 90 },
    "subject_index": { "delete_after_days": 90 },
    "review_sessions": { "retention_days": 2555 },
    "matter_terms": { "policy": "matter-lifecycle-retention" },
    "adapter_telemetry": { "retention_days": 90 },
    "siem": { "external_policy_ref": "splunk-index-retention" },
    "audit_packs": { "retention_days": 2555 },
    "fixtures": { "policy": "synthetic-fixtures-only" },
    "reports": { "retention_days": 90 },
    "logs": { "policy": "log-platform-policy-123" },
    "backups": { "retain_for_days": 365 }
  }
}
```

Validate before production:

```sh
uv run python scripts/check_retention_manifest.py --manifest /etc/junas/retention_manifest.json --strict
JUNAS_RETENTION_MANIFEST=/etc/junas/retention_manifest.json uv run python scripts/preflight.py --deployment production --strict
```

Accepted evidence keys are `retention_days`, `delete_after_days`, `retain_for_days`,
`policy`, and `external_policy_ref`.
