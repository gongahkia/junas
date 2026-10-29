# Classifier baseline after product removal

Measured 2026-10-30 using Python 3.12.14, the locked dependencies, and the `strict` profile. Optional local NER and semantic fallback were disabled; retrieval/LLM providers were not used. Exact package versions, detector environment overrides, corpus hashes and classifier source hash are recorded in [the internal report](../reports/current/core_accuracy.json).

The product cleanup changed **zero predictions across 1,718 documents** compared before and after removal, including findings, scores, risk classification and degraded modes. See [the parity report](../reports/current/core_removal_parity.json). Detector rules, retained corpus labels and regression locks were not changed.

Validation after cleanup: **1,260 tests and 270 subtests passed**, including real local Tesseract OCR checks. Ruff checks, scoped core type checks, a clean wheel installation, and documentation-link checks also passed.

## Internal regression measurements

All nine existing regression gates passed across **1,722 documents**. These gates permit the misses and false positives already present in their baselines; passing them is not an accuracy acceptance criterion.

| Corpus | Documents | Label recall | Label precision | F2 | Existing gate |
|---|---:|---:|---:|---:|---|
| legal-corpus | 147 | 99.59% | 60.62% | 0.8825 | pass |
| legal-corpus-adversarial | 134 | 98.53% | 58.21% | 0.8654 | pass |
| legal-corpus-sea | 5 | 100.00% | 39.22% | 0.7634 | pass |
| legal-corpus-hk-au-jp-kr | 4 | 100.00% | 62.71% | 0.8937 | pass |
| legal-corpus-cn | 1 | 100.00% | 40.00% | 0.7692 | pass |
| legal-corpus-in | 1 | 100.00% | 58.33% | 0.8750 | pass |
| legal-corpus-ae | 1 | 100.00% | 40.00% | 0.7692 | pass |
| legal-corpus-sa | 1 | 100.00% | 45.45% | 0.8065 | pass |
| legal-corpus-reviewed-candidates | 1,428 | 99.65% | 97.11% | 0.9913 | pass |

The reviewed candidate corpus recovered 20,328 of 20,399 expected rule/text labels, missed 71, and produced 605 unmatched predictions. The matcher does not distinguish multiple occurrences of the same `(rule, matched_text)` pair. Labels are not uniformly exhaustive, so unmatched predictions are not automatically false positives. The report's automated triage is not independent human adjudication.

Against the broader **ideal** labels in that corpus, recall is **42.56%** (17,168 / 40,338). These ideal labels are a coverage-gap inventory, not independently validated public ground truth. High strict-label agreement and low ideal-label coverage can coexist.

## External breadth measurements

These are fresh runs on the same classifier source, evaluated separately from the internal snapshot. The internal JSON records `external_mode: skip`; it does not incorporate or certify these separate measurements.

| Dataset / slice | Documents | Recall | Precision | F2 |
|---|---:|---:|---:|---:|
| [TAB](../reports/current/core_tab_eval.json), train + dev + test | 1,268 | 19.84% | 93.98% | 0.2356 |
| [ai4privacy](../reports/current/core_ai4privacy_eval.json), en-GB proxy slice | 933 | 10.84% | Not measured | Not measured |
| [ai4privacy](../reports/current/core_ai4privacy_eval.json), en-US proxy slice | 2,032 | 38.18% | Not measured | Not measured |

TAB uses external human annotations, PII-only predictions, EU routing, overlap matching and greedy one-to-one matching per annotator. Its 104,983 gold spans include annotator-specific observations. The aggregate includes training and development data and must not be described as held-out test accuracy. The matcher now indexes gold spans by document/annotator; equivalence tests preserve the previous matching counts.

ai4privacy is an external synthetic dataset. The US/GB slices are selected by label proxies because no locale field is available; they are not representative national samples. A gold span is counted as recalled when any prediction overlaps it, so one prediction can satisfy multiple gold spans. The runner does not calculate precision. Its source manifest and slice definitions are in the JSON report.

These measurements show that the classifier is **not yet broadly accurate**. Text-only corpus results also do not measure document extraction or OCR accuracy.

## Reproduce and improve

```sh
uv sync --frozen --extra dev
./scripts/fetch_tab_fixture.sh
uv run python scripts/fetch_ai4privacy_fixture.py
uv run python scripts/evaluate_accuracy.py --external require
uv run pytest -q
```

The aggregate command regenerates the internal and external reports in one run. The committed measurements were produced with `evaluate_accuracy.py --external skip` plus the two external runners using the output paths linked above. Real OCR tests additionally require `--extra ocr` and native Tesseract.

Before adding product features:

1. Establish a protected, independently annotated holdout with exhaustive positive and negative examples, including real document/OCR cases and MNPI element reasoning.
2. Set acceptance targets by entity type, jurisdiction and input format, including false-negative and false-positive limits. The current regression locks are preservation checks, not those targets.
3. Use development data to improve broad PII coverage and adjudicate the remaining MNPI misses. Evaluate NER/advisory experiments separately; do not reconcile holdout labels to detector output.

See [methodology](../BENCHMARKS.md) and [known limitations](known-limitations.md).
