# T3B.2A — small Singapore human-review pilot

**Prepared candidates, not independent ground truth.** This packet contains 20 unreviewed synthetic development documents and 10 metadata-only holdout reservations. There are zero genuine reviewer submissions, independent adjudications or accepted gold records. Protected holdout status is **NOT READY**.

The user-authorized T3B.2A scope replaces the earlier 80-document/four-jurisdiction proposal for this initial pilot. It also explicitly permits new synthetic text. The three existing T3B.1 files and all historical labels/locks remain untouched.

## Packet contents

```text
annotation-pilot/
  CUSTODIAN.md
  manifest.json
  holdout-reservations.json
  reservation-check.json
  packet-hashes.json
  reviews.jsonl                     # empty; no review events
  status.json                       # every development example unreviewed
  reviewer-kit/
    INSTRUCTIONS.md                 # guidelines without detector crosswalk/results
    document-metadata.json          # IDs, family/source, type, jurisdiction, hash
    documents/dev-001.txt ... dev-020.txt
    submission-templates/dev-001.json ... dev-020.json
```

Give each reviewer a separate private copy of **reviewer-kit only**. The source texts and templates contain no predictions, triggered-rule lists, existing corpus labels or source-specific gold suggestions. Permitted annotation labels and generic field guidance are in the instructions. Do not provide the full repository, detector taxonomy crosswalk, prior annotations or merged review log as part of blind annotation.

The source files are canonical UTF-8 text and also the original synthetic sources. Their source and canonical hashes coincide intentionally. This is not a native-document/OCR dataset. Do not change frozen text or normalize newlines to make coordinates fit.

## Source provenance and eligibility qualifications

All 20 development excerpts were authored directly by the Codex assistant during this task. They are **model-authored synthetic material**, not independently sourced public documents, real clients, real transactions or independently validated labels. No separate model/provider/API request, dataset download or source-document upload was used to author them. The precise model identifier and underlying training-source overlap are not attested.

The legal/transaction scenarios, people, identifiers and contact details were invented for the task. No personal records were intentionally copied from an existing corpus or private source. Do not assume identifier checksum validity or legal treatment from author intent; reviewers must record uncertainty. Source-family IDs group two related excerpts in each of ten development families. Titles/types and family IDs are administrative metadata, not annotations.

Source eligibility is based on the user's explicit authorization for newly authored, non-sensitive synthetic examples under source eligibility B. `generation_origin: model` records that origin. `prior_use: development` records their exposure to this development runtime. They must not later be relabelled as protected holdout.

The existing schema's `synthetic_owned` authorization tag denotes new first-party synthetic material here; it is **not a legal ownership certification**. Licence text records task-authorized local research/review only, with publication/redistribution and ownership assessment pending. No third-party public licence is fabricated. Human acceptance of the packet and any wider redistribution remain pending.

The intended coverage spans direct personal identifiers, personal contact/record data, birth dates, contextual combinations, repeated and overlapping occurrences, administrative/hard-negative language and ambiguous transaction context. These are authoring intentions, not per-document expected labels. There is no gold list or scored sample-selection result. Independent reviewers may disagree with author intent.

## Holdout reservations

`hold-001` through `hold-010` reserve ten SG metadata slots with separate source/template/scenario-family namespaces. They contain **no source text, source paths, hashes, labels, reviewer identities, approvals or timestamps**. Content is `not_collected`; eligibility is `pending`; prior use is `unknown`.

Disjoint IDs are only a planning constraint. Semantic/near-duplicate comparison is unavailable until a human custodian independently obtains eligible, unexposed sources. The current development examples cannot supply holdout variants. Source/template/scenario separation must be checked against all development, regression and tuning material after collection. Do not fabricate hashes to fit the fully populated T3B.1 manifest schema.

No human-controlled protected storage has been established. Do not generate holdout text here, mount future protected data in this runtime, run predictions, score a holdout or claim a freeze. The metadata reservation format is deliberately not a populated annotation manifest. The existing T3B.1 content loader still refuses protected-holdout entries before reading source/review files.

## Review assignment and recording

Reviewer identities, assignments and timestamps are deliberately null in the blank templates. These templates are not valid submitted events or completed draft work. No fictitious people have been appointed. The empty log is the only current event log.

A qualified single-reviewer development pilot is supported if two independent annotators and a separate adjudicator are unavailable. Record actual work and its limitations; never call it independently adjudicated ground truth. For double annotation, give reviewers separate kit copies and prohibit viewing each other's answers before submission.

1. Approve the source/taxonomy scope and appoint a real custodian. The custodian supplies actual pseudonymous reviewer IDs and records identity/role verification outside the packet.
2. Each reviewer fills their own templates, exact spans, PII/MNPI completeness, uncertainty and actual provenance. Use actual record IDs and actual timezone-bearing timestamps. Do not auto-fill independent-review attestations. Source model authorship and annotation independence are distinct disclosures.
3. Reviewers submit entries privately. The custodian records them using `prepare_evaluation_dataset.py append`, creating a **new** complete log and retaining previous versions. An unchanged blank template must be refused.
4. Multiple active submissions require a separate recorded adjudication, preserving disagreements. Corrections are new snapshots with `supersedes`, actual timestamps and a rationale. Do not replace earlier annotations silently.
5. An `accepted` record requires explicit actual human approval of the reviewed submission/adjudication. The tool cannot authenticate reviewers or authorize ground-truth promotion. Keep completeness/provenance qualifications attached.

Never place real submissions in this repository merely because blank examples are stored here. The custodian should retain real reviewer entries and immutable log anchors outside Git, with deliberate access controls.

## Offline commands

Run from the repository root using the existing frozen environment. Write results to new external paths; do not overwrite the supplied empty log or initial status. Examples use a hypothetical already-created private development directory; no protected contents are involved.

```sh
uv run --frozen python scripts/prepare_evaluation_dataset.py validate docs/annotation-pilot/manifest.json --reviews docs/annotation-pilot/reviews.jsonl --output /private/dev/initial-validation.json
uv run --frozen python scripts/prepare_evaluation_dataset.py append docs/annotation-pilot/manifest.json --entry /private/dev/actual-entry.json --output /private/dev/reviews-v1.jsonl
uv run --frozen python scripts/prepare_evaluation_dataset.py append docs/annotation-pilot/manifest.json --reviews /private/dev/reviews-v1.jsonl --entry /private/dev/actual-next-entry.json --output /private/dev/reviews-v2.jsonl
uv run --frozen python scripts/prepare_annotation_packet.py status docs/annotation-pilot/manifest.json --reviews /private/dev/reviews-v2.jsonl --output /private/dev/status-v2.json
```

Status reporting distinguishes `unreviewed`, `annotated_by_one_reviewer`, `independently_double_annotated`, `disagreement_pending`, `adjudicated` and `accepted`. Non-blind or otherwise unqualified double submissions are `double_annotated_unqualified`. Independent double annotation means recorded blind/non-author declarations only: independence remains `declared_not_verified`, not authenticated fact. Status calculation does not write review events, resolve disagreements or complete stages automatically.

Use `--simulation` only for explicitly synthetic workflow exercises. Such events are simulations, not human annotation counts. No simulated submissions are included in the supplied pilot log. Unit tests exercise mechanics separately with toy text and simulation-only metadata.

To rebuild a separate blank packet from an already verified development manifest:

```sh
uv run --frozen python scripts/prepare_annotation_packet.py build docs/annotation-pilot/manifest.json --reservations docs/annotation-pilot/holdout-reservations.json --guidelines docs/annotation-pilot/reviewer-kit/INSTRUCTIONS.md --output /private/dev/new-blank-packet
```

The destination must not already exist. The builder copies exact canonical text, administrative metadata and blank entries, with no inferred annotations. `packet-hashes.json` covers the generated packet payload; this custodian handoff is separate from that inventory. Copying a kit grants no protected access and is not an independent-review approval.

## Human decisions still required

Approve the synthetic-only source qualification, narrow nine-label taxonomy and 20-example SG scope. Appoint actual reviewers and decide whether to start with a qualified single-reviewer development exercise or arrange two annotators and a separate adjudicator. Confirm where real submissions are retained and who may approve them.

Separately appoint a holdout custodian and protected storage, obtain eligible new holdout sources without exposing them here, check prior-use/semantic leakage and approve any future freeze explicitly. No holdout collection, scoring, model benchmarking, T4 or T5 is authorized by preparation of this packet.
