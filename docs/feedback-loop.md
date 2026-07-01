# Feedback Loop: Journal To Candidate Corpus

Status: canonical path. This document defines how reviewer decisions become detector
quality work and, only after review gates, promoted recall-lock evidence.

## Current Boundary

There is no automatic journal-to-fixture exporter. That is intentional: review journals
can contain sensitive workflow evidence, and customer text must not flow into test
fixtures by default.

Canonical path:

1. Reviewer records a decision in the journal.
2. Triage converts authorized reviewer feedback into a detector issue category.
3. A synthetic fixture or explicitly approved scrubbed customer sample is created in
   the candidate corpus.
4. Candidate labels are human reviewed.
5. Candidate fixtures are evaluated.
6. Approved candidates are promoted into the reviewed candidate corpus.
7. Recall locks and accuracy docs are updated from promoted, reviewed fixtures only.

## Source Events

Use journal events as signals, not as raw fixture sources:

- `review_started`: review id, hashes, policy context, findings, and counts.
- `decision_recorded`: reviewer action, reviewer identity source, finding id, action,
  and rationale.
- `approval_requested`: approval status, required reviewer roles, and reason code.
- `audit_exported`: audit-pack export evidence.

Only authorized `decision_recorded` feedback may affect labels. Per
`docs/policy/journal-replay.md`, a `reject` removes a finding from downstream use only
when reviewer identity is authoritative. Legacy or unauthenticated rejects stay audit
signals until reviewed.

## Existing Scripts

| Step | Script | Role |
|---|---|---|
| Inspect journal integrity | `scripts/verify_journal.py` | Confirms journal chain before using reviewer decisions as signals. |
| Export session evidence | `scripts/export_audit_pack.py` | Produces a controlled audit ZIP for a review session. |
| Verify audit pack | `scripts/verify_audit_pack.py` | Checks pack layout, pack HMAC, journal slice, and counts. |
| Export false-positive queue | `scripts/export_false_positive_queue.py` | Emits authorized reviewer rejects with hashed document ids and fixture sidecar templates. |
| Export false-negative queue | `scripts/export_false_negative_queue.py` | Emits reviewer-added and unresolved approval-required items as false-negative candidate work. |
| Generate fixture | `scripts/generate_legal_fixture.py` | Creates a single synthetic legal/privacy fixture. |
| Generate candidate batch | `scripts/generate_candidate_corpus.py` | Creates batched synthetic candidate fixtures. |
| Scrub fixture | `scripts/check_fixture_scrub.py` | Blocks secrets or raw customer data before fixture commit. |
| Review candidate | `scripts/review_candidate_fixture.py` | Records `_human_review_status` and reviewer metadata. |
| Check review gate | `scripts/check_candidate_review_status.py` | Fails when candidate labels lack human approval. |
| Reconcile strict labels | `scripts/reconcile_candidate_strict_labels.py` | Reports runtime/label deltas without promoting runtime findings into labels. |
| Promote exact spans | `scripts/promote_candidate_exact_spans.py` | Moves ideal labels into strict labels only when runtime emits exact spans. |
| Evaluate candidates | `scripts/evaluate_candidate_corpus.py` | Produces candidate recall, precision, and `candidate_recall.lock.json`. |
| Report stage status | `scripts/candidate_corpus_report.py` | Summarizes candidate stage, review state, and eval posture. |
| Stage gate | `scripts/check_candidate_stage_gate.py` | Gates jurisdiction stage advancement and promotion readiness. |
| Promote candidates | `scripts/promote_candidate_fixtures.py` | Copies human-approved, non-runtime-derived candidate fixtures into reviewed corpus. |
| Check promoted lock freshness | `scripts/check_promoted_lock_freshness.py` | Fails CI when reviewed fixture inputs change without the promoted lock and accuracy doc. |
| Attribute misses | `scripts/run_layer_attribution_eval.py` | Writes candidate, miss-bucket, and concentration reports. |

## Canonical Workflow

### 1. Verify Source Evidence

```sh
uv run python scripts/verify_journal.py
uv run python scripts/export_audit_pack.py "$REVIEW_ID" --output ./out/audit.zip
uv run python scripts/verify_audit_pack.py ./out/audit.zip
```

Use the audit pack to inspect decision context. Do not copy raw prompt, email body,
document text, matched text, recipient address, filename, mapping value, auth header,
or local pairing token into a fixture task.

### 2. Categorize Feedback

First assign one decision taxonomy label from `docs/policy/decision-taxonomy.md`:
`false_positive`, `false_negative`, `acceptable_risk`, `public_source_confirmed`,
`stale_information`, or `policy_exception`. Taxonomy is the audit-safe reviewer
feedback meaning. Detector issue categories below are only for false-positive fixture
work.

Map the reviewer signal into one detector issue category from
`docs/admin-console/false-positive-triage.md`, such as:

- `context_false_positive`
- `defined_term_or_placeholder`
- `public_information`
- `entity_type_confusion`
- `jurisdiction_mismatch`
- `span_boundary_error`
- `severity_or_policy_mismatch`
- `duplicate_or_dedup_error`
- `reviewer_error_or_dispute`
- `needs_detector_issue`

False negatives should be recorded as detector miss work, not as false-positive
overrides.

### 3. Create Candidate Fixture

Preferred path: create a synthetic reproduction from the detector issue category,
jurisdiction, rule id, policy context, and sanitized notes:

```sh
uv run python scripts/generate_legal_fixture.py \
  --jurisdiction SG \
  --concept direct_identifiers \
  --document-type memo \
  --variant negative
```

For batches:

```sh
uv run python scripts/generate_candidate_corpus.py --jurisdictions SG --concepts direct_identifiers
```

Customer-derived samples require all of:

- explicit `customer_sample_approved` evidence
- scrubbed fixture text
- reviewer approval metadata
- retention classification
- `uv run python scripts/check_fixture_scrub.py <fixture-path>` evidence

### 4. Human Review Candidate Labels

```sh
uv run python scripts/review_candidate_fixture.py \
  test/fixtures/legal-corpus-candidates/sg/direct_identifiers/example.txt \
  --decision approve \
  --reviewer owner \
  --notes "approved synthetic reproduction for context_false_positive"

uv run python scripts/check_candidate_review_status.py \
  --corpus test/fixtures/legal-corpus-candidates
```

Rejected or `needs_edit` labels must not be promoted.

### 5. Reconcile And Evaluate

```sh
uv run python scripts/reconcile_candidate_strict_labels.py \
  --corpus test/fixtures/legal-corpus-candidates \
  --require-human-reviewed \
  --reason "reviewer feedback reproduction"

uv run python scripts/promote_candidate_exact_spans.py \
  --corpus test/fixtures/legal-corpus-candidates \
  --actor owner

uv run python scripts/evaluate_candidate_corpus.py \
  --corpus test/fixtures/legal-corpus-candidates \
  --update-lock \
  --require-human-reviewed \
  --reason "reviewer feedback candidate baseline"
```

The reconcile step is report-only. Do not copy runtime findings into `must_detect`.
Create or edit labels from independent human review, fixture instructions, or approved
synthetic reproduction work.

The candidate lock is `test/fixtures/legal-corpus-candidates/candidate_recall.lock.json`.
It is a candidate-corpus baseline, not promoted production accuracy evidence.
Candidate evaluation reports both strict candidate recall and independent-label recall;
the independent metric excludes labels whose provenance indicates runtime promotion.

### 6. Promote Reviewed Candidates

```sh
uv run python scripts/promote_candidate_fixtures.py \
  --candidate-dir test/fixtures/legal-corpus-candidates \
  --target test/fixtures/legal-corpus-reviewed-candidates
```

Promotion writes `candidate_promotion_manifest.jsonl` and copies only human-approved
fixtures plus labels.

### 7. Refresh Promoted Evidence

Run promoted-corpus evaluation and accuracy doc generation only after promotion:

```sh
uv run python scripts/recall_gate.py \
  --corpus test/fixtures/legal-corpus-reviewed-candidates \
  --update \
  --require-human-reviewed \
  --reason "promoted reviewed candidate fixtures from reviewer feedback"

uv run python scripts/generate_accuracy_doc.py
```

Promoted evidence lives at:

- `test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json`
- `docs/accuracy.md`

Do not claim improved detection until the promoted corpus has fixture text plus
`.labels.json` sidecars, all labels are human-approved, the recall gate refreshed the
promoted lock with `--require-human-reviewed`, a precision report or precision lock is
committed, and `docs/accuracy.md` is regenerated from those locks. Candidate-only
reports, demo screenshots, unpromoted sidecars, and roadmap notes are not
improved-detection evidence.

CI runs `scripts/check_promoted_lock_freshness.py` on pull-request and push diffs. A
change to any reviewed-candidate `.txt` or `.labels.json` fixture input must include
both `test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json`
and `docs/accuracy.md` in the same diff.

## Required Metadata

Every feedback-derived candidate label must preserve:

- detector issue category
- source reviewer decision id or audit evidence reference
- source rule id, category, severity, and jurisdiction
- synthetic or customer-derived source flag
- `customer_sample_approved` when customer-derived
- `_human_review_status`
- `_human_review`
- `_human_review_history`
- promotion manifest entry when promoted

## Non-Goals

- No automatic training from reviewer decisions.
- No raw journal text copied into fixtures.
- No recall lock update from unreviewed candidate labels.
- No recall lock update from labels whose source or reason indicates strict-runtime promotion.
- No reviewed-corpus promotion from labels whose source or reason indicates strict-runtime promotion.
- No promoted accuracy claim from candidate-only `candidate_recall.lock.json`.
- No customer-derived fixture without sample approval and scrub evidence.

## Related Documents

- `docs/admin-console/false-positive-triage.md`
- `docs/policy/decision-taxonomy.md`
- `docs/policy/journal-replay.md`
- `docs/accuracy.md`
- `docs/product/value-metrics.md`
- `test/test_candidate_fixture_tooling.py`
- `test/test_candidate_review_workflow.py`
