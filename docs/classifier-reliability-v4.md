# Classifier v4 local reliability work

Items 1–5 are implemented and verified locally. The original consumed holdout was exported into a separate private development copy before diagnosis; its original text, annotations, consumption marker and failed validation results remain unchanged. No paid API calls were made.

The contextual output is now `junas.sensitivity.v4`. Changes broaden attributed person roles, link personal record/account fields across bank-name syntax, parse birth-month profiles, and distinguish role mailboxes, specimen bank fields and corporate identifiers. Names retain exact source offsets, including accented names and anchored abbreviated references. MNPI changes recognize financing, licence and withdrawal events and link explicitly referenced decisions within bounded context. Public claims, hypothetical events, ambiguity and different issuers retain separate controls.

The diagnostic tool now records document disagreements and abstentions in its per-document buckets, rather than only its aggregate counts. This exposed MNPI cases that were missing from the previous detail listing. New authored tests cover role/name combinations, line endings, linked profiles, corporate controls, event paraphrases, public/hypothetical variants and issuer separation. Future holdout exclusions include the two new regression files.

| Latest retired 40-document cohort | Original v3 validation | Tuned v4 development replay |
| --- | --- | --- |
| Exact PII reference spans | 55/80 | 79/80 |
| Overlapping PII reference spans | 55/80 | 80/80 |
| PII-positive documents detected | 20/20 | 20/20 |
| PII-negative documents flagged | 4/20 | 0/20 |
| PII-negative abstentions | 8/20 | 0/20 |
| MNPI-positive documents detected | 7/20 | 19/20 |
| MNPI-positive abstentions | 13/20 | 1/20 |
| MNPI-negative flags / abstentions | 0/20 / 0/20 | 0/20 / 0/20 |

This replay passes all nine unchanged engineering targets. It is tuned model-reference agreement and cannot be presented as another unseen validation. No reference labels or thresholds were changed. One exact PII boundary disagreement, two unmatched exact-span predictions and one positive MNPI abstention remain. Unknown predictions count against detection. Model-declared completeness is unverified, so unmatched predictions may include reference omissions as well as detector errors.

All four development cohorts pass the same targets:

| Cohort | Exact PII spans | PII-positive detection | MNPI-positive detection |
| --- | --- | --- | --- |
| Latest retired 40 | 79/80 | 20/20 | 19/20 |
| Previously retired 40 | 71/71 | 20/20 | 20/20 |
| Earlier 72 | 122/129 | 36/36 | 36/36 |
| Earlier 200 | 474/531 | 99/100 | 90/100 |

These 352 documents are development evidence. The older consumed holdout from the USD10 run was not evaluated or used for tuning. The older 200-document set still contains one missed PII-positive document and ten positive MNPI abstentions, and earlier span gaps remain. An intermediate licence-topic change regressed an older recall case; removing the generic trading-halt word from licence-topic matching restored the earlier result. Passing cohort gates alone was not used to excuse that regression.

Verification passed: 1,845 tests plus 254 subtests on each of Python 3.11 and 3.12; 39 newly authored regression cases; the 72-case all-quadrant gate; all nine locked historical corpus gates; Ruff lint/format on ten changed Python files; and scoped mypy on six sources. The sdist and wheel build, and an isolated offline wheel installation passes four classifier cases and CLI execution with networking disabled. The installed runtime hash matches the final source. The first Python 3.12 full run was superseded by a complete rerun after the final topic correction. Full-project mypy and external benchmark acquisition were not run.

All 6,775 initially recorded repository files were checked for unexpected changes. The pre-existing uncommitted patch and README are unchanged. Earlier archives retain all 1,079, 971, 851, 45 and 750 recorded file hashes. Runtime verification applies to the workspace, including its earlier uncommitted text-only changes.

Finite role/event patterns and bounded linkage still limit generalization. No independent accuracy, calibrated confidence, legal materiality, actual absence or external public-status verification is established. Fresh unseen validation remains necessary after freezing this version, with a separately reviewed cost proposal before any more paid calls. No fresh run was prepared or authorized in this task.

Runtime SHA-256: `2d311c9eb04d9f7bfa21802e6603ca4164de915d9a1e7c355000a23203745c3c`. Aggregate metrics and verification metadata are in [the machine-readable report](../reports/current/classifier_reliability_v4.json). Raw development copies and iteration artifacts remain outside Git.
