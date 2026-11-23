# Accuracy evaluation

The primary command is:

```sh
uv run python scripts/evaluate_accuracy.py
```

It evaluates the nine locked legal/adversarial/jurisdiction corpora, records source and corpus hashes, reports missed expectations and unexpected findings, and runs existing regression locks without rewriting them. The JSON output is `reports/current/core_accuracy.json`.

## Interpret the measurements

- Internal `candidate_recall` is agreement with expected `(rule, matched_text)` labels. It does not distinguish repeated occurrences with the same text.
- Internal `candidate_precision` treats unexpected findings as unmatched predictions. Labels are not uniformly exhaustive, so this is label agreement, not independently adjudicated precision.
- F2 gives recall more weight than precision. Report both components, rather than relying on one combined score.
- Ideal-label results are coverage-gap measurements, kept distinct from strict regression labels.
- A passing lock means existing behavior was preserved. It does not mean the classifier meets a production accuracy target.
- Detector-derived or reconciled labels must not be described as independent ground truth. Corpus promotion requires human review and provenance checks.

## Independent breadth checks

```sh
./scripts/fetch_tab_fixture.sh
uv run python scripts/fetch_ai4privacy_fixture.py
uv run python scripts/evaluate_accuracy.py --external require
```

TAB is an external manually annotated corpus. ai4privacy is an external synthetic dataset with US/GB label-proxy slices; these are not representative national samples. The runners support exact and overlap matching. TAB uses greedy one-to-one matching per annotator. ai4privacy counts a gold span as recalled if any prediction overlaps it, so one prediction can cover multiple gold spans. Compare these metric definitions before comparing systems.

For model selection, use development data; reserve TAB's test split for a final held-out check:

```sh
uv run python scripts/run_tab_eval.py --splits dev --output reports/current/tab_dev.json
uv run python scripts/run_tab_eval.py --splits test --output reports/current/tab_test.json
```

The aggregate convenience runner uses all three TAB splits to reproduce the historical breadth baseline. It must not be called a held-out test after tuning on those documents.

No external fixture is downloaded by an evaluation run. Missing datasets are recorded as missing; `--external require` exits unsuccessfully if either is absent. Raw corpus text is not sent to a remote provider by strict evaluation.

## Focused investigation

```sh
uv run python scripts/recall_gate.py --corpus test/fixtures/legal-corpus-adversarial
uv run python scripts/evaluate_candidate_corpus.py --profile strict --output /tmp/junas-candidate-detail.json
uv run python scripts/run_layer_attribution_eval.py --help
uv run python scripts/generate_accuracy_doc.py --check
```

Use the detailed candidate report and miss-bucketing tools to select the next detector change. Add independently reviewed positive and negative examples, then rerun recall and precision gates. Do not regenerate labels from detector output to improve a reported score.

## Separate measurement tracks

Junas now accepts UTF-8 text only. Native PDF/Office/email/image extraction and OCR support and their tests were removed. Historical extraction measurements do not describe the current package. Text admission, contextual sensitivity, legacy findings and optional advisory outputs retain separate validation contracts.

Use `scripts/measure_external_surfaces.py --help` to measure legacy findings and contextual PII independently on TAB development and ai4privacy slices. It preserves the existing matching definitions, labels each prediction surface and records the runtime hash. Broad masking labels have no approved contextual subtype crosswalk; unavailable occurrence metrics remain unavailable when analysis degrades.

See [the baseline](docs/baseline.md) and [limitations](docs/known-limitations.md).

## T3A versioned measurement contract

Legacy summaries and regression locks retain their historical definitions. In particular, gate precision charges explicit `must_not_detect` challenges only, and historical independence fields are provenance-marker exclusion calculations rather than proof of blind annotation.

New `annotation_audit_v1` and `occurrence_v1` outputs distinguish provenance, occurrence identity, one-to-one exact/overlap matching, physical splits and declared annotation completeness. Precision is unavailable when exhaustive target annotation is not established; a caller declaration does not certify ground truth. See [the metric definitions and holdout requirements](docs/evaluation-metrics.md). Use explicit new output paths to preserve historical reports. Current internal rule/text labels are not upgraded into occurrence ground truth.
