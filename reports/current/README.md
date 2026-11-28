# Classifier reports

“Current” is the historical output directory, not a claim that every file measures HEAD. Preserve dated reports, source hashes and failed original holdout results.

- `browser_live_development_v1.json`: completed real WebLLM run over 144 authored short cases, with all rows, 42 validation failures, 102 incomplete proposals, hardware/timing observations and artifact hashes. Fails seven of nine targets; not independent accuracy.
- `browser_short_development_v1.json`: separate deterministic replay and initial headless verification; its model-not-run status is historical.

- `evaluation_closeout_v5.json`: latest local evidence, separate external prediction surfaces and clean-checkout verification.
- `fresh_holdout_v5_plan.json`: offline proposal only; no paid inference or new validation result.
- `classifier_reliability_v4.json`: previous local development replay.
- `fresh_holdout_v3_results.json`: immutable original consumed holdout outcome, before later tuning.
- `core_accuracy.json`, `core_tab_eval.json`, `core_ai4privacy_eval.json`, `core_removal_parity.json`: historical legacy-detector measurements; see [baseline interpretation](../../docs/baseline.md).
- `T4A_REPORT.md`, `t4a_evidence.json`: 22 November mocked AI integrity assessment, including components removed by later text-only work. Saved temporary paths are historical evidence, not current execution prerequisites.
- `text_only_automated_20261122.json`, `model_corpus_200*_plan.json`, `model_corpus_200*review.json`: earlier scope/cost proposals, not current spending authorization.

Model consensus is qualified reference agreement, not independent accuracy or calibrated confidence. See [the latest closeout](../../docs/evaluation-closeout-v5.md).
