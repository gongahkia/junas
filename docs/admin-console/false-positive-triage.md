# False-Positive Triage Requirements

Status: requirements only. Do not add false-positive triage endpoints or UI code
until ADR 0005 is revisited or a dedicated implementation task approves them.

## Purpose

False-positive triage converts authorized reviewer `reject` decisions into detector
quality work without training on customer text by default. The UI should help admins
group rejected findings, choose detector issue categories, and create sanitized
candidate fixture tasks only when policy permits sample handling.

## Source Signals

Accepted input signals:

- `decision_recorded` events where `action="reject"` and reviewer identity is
  authorized according to `docs/policy/journal-replay.md`
- review-session metadata: tenant id, surface, workflow, policy id/version,
  document hash, finding id, rule, category, severity, jurisdiction, detector family,
  and source verification status
- reviewer reason codes and sanitized reviewer rationale
- aggregate counts from audit-pack and feedback exports

Rejected findings must not be treated as false positives when reviewer identity is
missing, unauthorized, legacy-only, or replay rules keep the finding active.

## Detector Issue Categories

Each triage item must carry exactly one primary `detector_issue_category`:

| Category | Meaning |
|---|---|
| `context_false_positive` | Detector hit is syntactically valid but context makes it safe or irrelevant. |
| `defined_term_or_placeholder` | Hit is a contract term, fictional placeholder, template field, or example value. |
| `public_information` | Reviewer says the signal is already public or stale, so MNPI treatment is wrong. |
| `entity_type_confusion` | Detector picked the wrong category, such as company id as person id. |
| `jurisdiction_mismatch` | Rule fired for the wrong jurisdiction or cross-border context. |
| `span_boundary_error` | Hit is valid in kind but the span is too broad, too narrow, or overlaps badly. |
| `severity_or_policy_mismatch` | Detector hit is real but severity or policy action is too strong. |
| `duplicate_or_dedup_error` | Duplicate findings or deduplication caused noisy output. |
| `reviewer_error_or_dispute` | The reject is disputed or needs second reviewer adjudication. |
| `needs_detector_issue` | Enough evidence exists to file a detector bug or precision task. |

Secondary tags may include rule id, detector family, jurisdiction, source surface,
policy version, and fixture-readiness status.

## Triage Workflow

1. Reviewer records a `reject` decision with `reason_code` and optional sanitized
   rationale.
2. Backend replay confirms the reject is authorized and finding-scoped.
3. Triage groups the reject by detector issue category, rule, jurisdiction, severity,
   surface, workflow, policy id/version, and document hash.
4. Admin marks the item as `needs_more_review`, `known_limitation`, `create_fixture`,
   `file_detector_issue`, `discard_reviewer_error`, or `resolved`.
5. Fixture generation is allowed only after a human confirms sample-handling policy,
   source approval, and scrub status.

## Fixture Generation Linkage

Triage must link to existing fixture tooling without copying raw customer content by
default:

- `scripts/generate_legal_fixture.py` for synthetic reproduction fixtures
- `scripts/generate_candidate_corpus.py` for batched candidate generation
- `scripts/check_fixture_scrub.py` before any customer-derived sample can enter test
  fixtures
- `scripts/review_candidate_fixture.py` and `scripts/check_candidate_review_status.py`
  for human approval gates
- `scripts/evaluate_candidate_corpus.py` and `scripts/candidate_corpus_report.py` for
  measuring candidate impact before promotion

Allowed fixture task fields: detector issue category, rule id, category, jurisdiction,
surface, workflow, severity, policy id/version, finding id, document hash, reviewer
reason code, and sanitized reproduction notes. Raw customer text, matched spans,
recipient addresses, filenames, auth headers, reversible mappings, and local pairing
tokens must not be copied into fixture tasks by default.

Customer-derived fixtures require an explicit `customer_sample_approved` flag,
scrubbed text, reviewer approval metadata, source tenant, retention class, and
`scripts/check_fixture_scrub.py` evidence before entering any repo fixture directory.

## Required UI States

- Aggregate false-positive dashboard by rule, category, jurisdiction, surface,
  workflow, severity, policy version, and detector issue category.
- Triage queue with status: `new`, `needs_more_review`, `create_fixture`,
  `file_detector_issue`, `known_limitation`, `discard_reviewer_error`, or `resolved`.
- Detail view showing finding metadata, reviewer reason code, sanitized rationale,
  replay authorization status, fixture task status, and linked detector issue.
- Fixture task panel that can create synthetic fixture prompts without raw customer
  text.
- Export view that emits privacy-safe CSV/JSON with counts, ids, hashes, categories,
  and statuses only.

## Audit Events

Required event names:

- `false_positive_triage_opened`
- `false_positive_triage_categorized`
- `false_positive_fixture_task_created`
- `false_positive_detector_issue_linked`
- `false_positive_triage_resolved`

Events must include tenant id, actor id, actor role, request id, review id, finding id,
rule, category, severity, detector issue category, triage status, policy id/version,
document hash, fixture task id when present, detector issue id when present, and
timestamps. Events must not include raw reviewed content, matched text, raw rationale,
recipients, filenames, auth headers, mapping values, or local pairing tokens.

## Non-Goals

- No automatic detector retraining from reviewer rejects.
- No customer text copied into fixtures without explicit sample approval and scrub
  evidence.
- No false-positive rate claim from unauthorized rejects.
- No UI ability to change historical reviewer decisions.
- No detector promotion until candidate fixtures pass the existing human-review and
  evaluation gates.

## Related Documents

- `docs/adr/0005-admin-console-docs-only-until-validation.md`
- `docs/admin-console/requirements.md`
- `docs/admin-console/reviewer-queue.md`
- `docs/policy/journal-replay.md`
- `docs/accuracy.md`
- `test/test_candidate_fixture_tooling.py`
