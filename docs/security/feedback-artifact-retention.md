# Feedback Artifact Retention

Status: operator policy requirements. This document covers feedback artifacts created
between reviewer decisions, fixture queues, candidate labels, promoted locks, and
dashboard reports.

## Scope

Feedback artifacts include:

- hashes such as `document_hash`, `pii_hash`, finding-id hashes, queue ids, and
  idempotency-key hashes
- candidate and reviewed `.labels.json` files
- fixture task `.sidecar.json` files and reviewed `.bucket.json` sidecars
- raw customer samples approved for reproduction work
- audit-pack references, false-positive and false-negative queues, eval reports, and
  detector dashboards

Default rule: keep synthetic and scrubbed evidence only; do not retain raw customer
samples in the repository.

## Retention Matrix

| Artifact | Default location | Baseline retention | Legal hold | Subject erasure behavior |
|---|---|---|---|---|
| Hashes | Review journal, queues, dashboards, reports | Same as the parent artifact, commonly journal retention for audit hashes and 30-90 days for queue/report hashes | Hold with the parent audit record; do not reverse or expand hashes into raw values | Keep HMAC/digest values when required for audit tombstones; remove subject-index buckets with `scripts/erase_subject.py`. |
| Labels | `test/fixtures/**/*.labels.json` | Source-controlled only after synthetic generation, scrub, and human review | Pause deletion or rewrite while litigation/regulatory hold applies; record hold id outside the labels file | Synthetic labels usually remain. If labels contain accidental real subject text, remove active files, regenerate locks, and coordinate repository-history purge if policy requires. |
| Sidecars | `*.sidecar.json`, `*.bucket.json`, queue output dirs | Working queues: 30-90 days. Promoted/reviewed sidecars: align with fixture/report retention. | Preserve sidecar plus queue summary under the hold id; no raw text may be added for convenience | Delete or tombstone sidecars linked to an erased raw sample unless the sidecar is scrubbed and legal hold requires retention. |
| Raw samples | Controlled customer evidence store outside Git | Not stored by default. If `customer_sample_approved`, retain only for the approved purpose/window. | Legal hold pauses deletion; access remains restricted to approved reviewers | Delete when erasure applies unless legal hold blocks deletion; record tombstone/citation and recreate synthetic fixtures without raw subject text. |
| False-positive/negative queues | Operator output path under `reports/` or ticket attachment | 30-90 days unless promoted into fixtures or retained for audit | Hold queue row ids and hashes, not raw reviewer text | Drop queue rows tied to erased subjects unless retained as hash-only audit evidence. |
| Eval reports and dashboards | `reports/` or release evidence | Release evidence retention or 90 days for local drafts | Hold committed reports that support a release or audit claim | Reports must omit raw spans; if a report accidentally includes raw subject text, remove it and regenerate from scrubbed inputs. |

## Raw Sample Admission

Raw customer samples may enter feedback work only when all are true:

- `customer_sample_approved` evidence exists
- a retention class and expiry are assigned before storage
- legal-hold status is checked before deletion or mutation
- access is limited to approved reviewers/operators
- scrub evidence is recorded before any fixture or label is committed
- subject-erasure disposition is known before promotion

Approved raw samples are controlled evidence, not training data and not default fixture
material. Prefer synthetic reproduction from hashes, counts, rule ids, policy context,
and sanitized reviewer notes.

## Legal Hold

Legal hold freezes deletion for the held artifact class but does not permit broader
copying. While held:

- do not move raw samples into Git
- do not use raw samples for training, fine-tuning, distillation, or benchmarks
- keep sidecars and labels scrubbed
- record hold id, owner, scope, and release condition in the operator evidence system
- run subject-erasure dry runs and record what is blocked by hold

## Subject Erasure

Subject erasure for feedback artifacts follows `docs/security/subject-erasure.md`:

1. Use the raw subject value only to compute HMAC lookup with `scripts/erase_subject.py`.
2. Delete reversible mappings and subject-index buckets.
3. Append `subject_erasure_recorded` tombstones to the journal.
4. Remove raw sample files and unsanitized sidecars unless legal hold blocks deletion.
5. Regenerate fixtures, labels, locks, reports, and dashboards if a promoted artifact
   changed.
6. Use hashes, `review_id`, queue id, and erasure citation in tickets; do not paste the
   raw subject value.

## Required Metadata

Every customer-derived feedback artifact must record:

- source flag: `synthetic`, `scrubbed_customer_sample`, or `hash_only_signal`
- `customer_sample_approved` when applicable
- retention class and expiry or external policy reference
- legal-hold status
- subject-erasure disposition
- reviewer approval reference
- scrub/check evidence before commit

## Related Documents

- `docs/feedback-loop.md`
- `docs/security/data-retention.md`
- `docs/security/subject-erasure.md`
- `docs/telemetry-feedback-loop.md`
- `scripts/check_fixture_scrub.py`
- `scripts/erase_subject.py`
