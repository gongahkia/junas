# Evaluation closeout v5

23 November 2026. Items 6 and 8 are completed locally; item 7 is frozen and prepared, awaiting the separately required spending approval. This task made **zero paid API calls**. [Machine-readable evidence](../reports/current/evaluation_closeout_v5.json) and the [next holdout proposal](fresh-holdout-v5-plan.md) preserve the distinction between implementation verification, development agreement and unseen validation.

## Remaining local disagreements

The remaining MNPI abstention came from treating an entire confirmed withdrawal statement as hypothetical because a separate “even if … were counted” concession appeared later in it. The narrow change retains explicit confirmed/decided event assertions while keeping genuine initial `If`/`Even if` counterfactual controls. Three new regression cases and the focused 61-test run passed. The classifier schema is now `junas.sensitivity.v5`.

On the latest retired 40-document development set, both PII and MNPI detect all 20 model-reference positives; all 20 negatives for each remain clean without abstentions. PII exact span agreement is **79/80**, overlap **80/80**, with two unmatched exact predictions. These are exposed development examples, not new validation. The untouched original v3 holdout report still records its original failures.

| Development source | Exact PII spans | Overlap PII spans | PII positives | MNPI positives |
|---|---:|---:|---:|---:|
| Latest retired 40 | 79/80 | 80/80 | 20/20 | 20/20 |
| Earlier retired 40 | 71/71 | 71/71 | 20/20 | 20/20 |
| Original development 72 | 122/129 | 124/129 | 36/36 | 36/36 |
| Original development 200 | 474/531 | 478/531 | 99/100 | 90/100, 10 abstentions |

All four pass the unchanged nine engineering targets; this does not mean all remaining misses are resolved. The original 40-document USD10 protected cohort was not evaluated or used for tuning.

## Reference QA, without forced labels

The new read-only audit checks a consumed marker and source identity, validates three actual annotations, recomputes unchanged consensus and flags review candidates. In the latest consumed candidate pool it finds 40 accepted references (10 per quadrant), 21 unresolved MNPI candidates and three failed candidates. The unresolved annotations contain 99 MNPI span votes: 80 unknown-public-status votes and 70 materiality-not-established votes. These span counts overlap and are not document counts. Illustrative policy text without a confirmed event or established disclosure status can legitimately remain unresolved; the audit does not convert uncertainty into a negative label.

Two accepted texts have PII annotation questions: a quasi-identifier boundary omits a closing delimiter, and a birth-date subentity is not separately labelled inside a combination. These flags do not establish that the reference or prediction is legally correct. Original spans, references and metric denominators are preserved. See the [complete audit](../reports/current/model_reference_audit_v5.json).

Three passes of one judge model can share errors. Agreement and self-reported confidence are not independently validated accuracy; calibrated confidence remains unavailable. No human-review requirement was introduced.

## Separate external masking measurements

The offline runner measures legacy findings and contextual PII independently against the [manually annotated TAB corpus](https://github.com/NorskRegnesentral/text-anonymization-benchmark) and [synthetic ai4privacy dataset](https://huggingface.co/datasets/ai4privacy/pii-masking-200k). Only TAB development was evaluated in this task. Its test split was not evaluated here; historical aggregate use means it is not a newly protected test.

| Prediction surface | TAB dev overlap recall / precision | ai4privacy US proxy coverage | ai4privacy GB proxy coverage |
|---|---:|---:|---:|
| Legacy findings | 19.02% / 94.76% | 38.18% | 10.84% |
| Contextual PII | 15.73% / 87.85% | 14.51% | 5.23% |

TAB has 127 documents and 20,273 annotator-specific gold spans. These are its historical greedy per-annotator overlap metrics. ai4privacy has 2,032 US-proxy rows / 7,051 gold spans and 933 GB-proxy rows / 2,907 gold spans; it counts many-to-one gold coverage, without precision. Seventeen row IDs overlap slices, so they are not pooled. Broad masking labels include categories outside contextual person-linked PII, and no approved subtype crosswalk exists. The scores show low broad coverage, not a direct same-target comparison with synthetic truth-table agreement.

Corrected occurrence metrics are **unavailable** because some analyses report degraded modes. A recorded TAB example reports missing entity-size materiality lookup, even though the measurement requests PII. The evaluator's conservative validation remains intact; these statuses were not suppressed to obtain scores. These benchmarks do not establish MNPI accuracy or confidence calibration. [Raw aggregate reports and input/source hashes](../reports/current/external_v5/manifest.json) contain no source text.

## Repository and clean-checkout verification

The outstanding approved text-only pipeline/removal work and review-intake chronology guard are now committed. Historical governance/cost reports are preserved and indexed; active assumptions no longer advertise OCR. Full-project type checking exposed 43 errors, chiefly local-variable type reuse, missing annotations and obsolete Python-before-3.11 imports. The repairs pass all 108 source/evaluation files, and CI now requires that check. The root README's previously approved text-only update was committed without further content changes.

A clean local clone of source commit `95e47a45` was installed with `uv sync --frozen --extra dev` on both CI Python versions. It remained clean after verification:

- Python 3.12.16 and 3.11.18: **1,850 tests and 254 subtests passed on each**, no failures or skips.
- `mypy --explicit-package-bases src scripts`: all 108 files pass; it emits an unused-config note for `junas.cli`, not an error.
- Changed Python Ruff format/lint: all 35 files pass; `git diff --check` passes.
- `evaluate_accuracy.py --external skip`: all nine unchanged locked gates pass across 1,722 documents.
- Fixture scrub: 6,392 files pass. MNPI label provenance and promoted-lock freshness pass.
- Source distribution and wheel build; isolated wheel installation with locked dependencies, four PII/MNPI smoke cases, grounded offsets and CLI pass with network connections denied.
- External measurements and four development replays (352 documents) ran with network connections denied.
- All 3,744 archived artifact hashes across six prior evidence manifests match. Original holdout results, labels and engineering thresholds remain unchanged.

Hosted CI was not triggered; its relevant commands ran locally. Optional NER and live advisory/provider usefulness were not exercised. Later commits add evidence/docs only; the frozen runtime hash is `62849d0115fa6416041e21c44461929333cd570bcf5171c78957177ad4ac82ce`.

The next step is the prepared **USD3.45 estimate / USD4 hard-cap** fresh paired holdout. Its generation and validation have not run. Broad PII coverage, independent MNPI validation and confidence calibration remain open limitations.
