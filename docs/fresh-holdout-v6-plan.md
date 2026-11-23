# Fresh holdout v6 — original frozen plan

Subsequent execution was approved and completed; see the [original failed validation result](fresh-holdout-v6-results.md). The proposal below remains the pre-run planning record.

Prepared offline on 23 November 2026. Classifier v6 is frozen; **no documents have been generated and no paid API calls have been made**. Earlier allowances are closed. The [complete cost/protocol record](../reports/current/fresh_holdout_v6_plan.json) binds the private frozen manifest, configuration and classifiers.

## What the next run will test

The target is forty accepted synthetic documents, ten in each PII/MNPI quadrant, with at least three model-consensus occurrences of each of the nine PII subtypes. Four newly reserved families cover executive succession, court injunctions affecting plant access, mineral reserve reassessments and shareholder voting-control arrangements. Their prompts request handover logs, multi-party correspondence, technical liaison notes and question-and-answer briefs, with natural paraphrases instead of stock boilerplate. No examples from these proposed families have been generated or used to tune the classifier in this task.

The generator remains `gpt-6.2-sol` and the judges are three separate `gpt-6.1-terra` samples, all with high reasoning. Base prompt version `synthetic-quadrants-majority-v5`, annotation definitions and the nine engineering targets remain unchanged. Judge-only document labels and subtype coverage select the cohort; classifier outputs never select candidates. Unknown labels and invalid evidence remain rejected, and their counts are reported.

V6 (`63ad99341c01445f684554e25e823e195c54f8b5c0a0a040ac7814137b1a18c5`) and frozen v5 (`62849d0115fa6416041e21c44461929333cd570bcf5171c78957177ad4ac82ce`) will evaluate the same admitted cohort once. Passing requires all nine unchanged targets; improvement over v5 alone is not success. The complete cohort is marked consumed before metrics. There will be no classifier, prompt, threshold or admission changes after generation begins, no outcome-driven replacement cohort and no retry of a failed evaluation. Original failures and incomplete coverage remain the reported result.

The private bundle is `/home/gongahkia/.local/share/junas/research/2026-11-23-fresh-holdout-v6/bundle`. Its 306-file manifest freezes source, dependencies, models, prompts, targets, proposal and exclusions. The 8,000-entry exclusion registry inherits used external texts and adds all prior generated candidates/rejections and current authored regressions. Reserved family IDs are disjoint from prior groups. Fingerprints, numeric/email skeletons and shingle checks cannot prove semantic novelty or independence from model training data.

This is a small synthetic generalization probe. It is not independently validated accuracy, confidence calibration or evidence that overfitting has been ruled out. The generator and judge may share blind spots; three samples of one judge are correlated. Accepted documents need not be equally distributed across families, so actual composition and rejected cases must be reported. Judge-only admission may favor clearer cases. Twenty positives per target provide limited evidence, even when every engineering gate passes.

## Cost before any paid calls

The buffered estimate is **USD3.45**: the highest accounted cost among the completed earlier forty-document stages, USD2.73792225, plus 25%, rounded up. The proposed **aggregate hard provider cap is USD4**, covering generation, judging, validation-repair attempts and every durable continuation segment. It is a new allowance; previous unused funds are not reused.

Published standard rates were rechecked on 23 November: [Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol) USD2 input / USD10 output and [Terra](https://developers.openai.com/api/docs/models/gpt-6.1-terra) USD1 input / USD5 output per million tokens. Conservative controller input ceilings remain USD4.50 / USD2.25, including standard input plus 30-minute cache writes; no cache discount is assumed. Credits and invoice totals remain unverified.

Each request reserves its full token-cost ceiling before dispatch. Uncertain completion charges retain their reserves and requests are not automatically replayed. The controller stops at the cap, quotas or 120-candidate limit. It may fail to reach forty accepted documents under USD4; incomplete coverage is reported without forcing labels or releasing a partial cohort. The proposal also records the much larger token-maxima cost without the cap, so the estimate is not confused with a worst-case completion guarantee.

Prior accounted/reserved usage is USD19.92373600, rounded up to a USD20 planning reserve. With a new USD4 cap, SGD1.50/USD and 20% fee contingency, the cumulative scenario is **S$43.20**. That remains below the requested S$50 planning ceiling, conditional on those assumptions; it is not a current FX quote or bank invoice. The additional capped scenario alone is S$7.20.

## Verification and next action

124 relevant preparation, partition, recovery, budget and reliability tests pass on each Python version (3.11 and 3.12). Ruff lint/format passes for three changed Python files; full-project mypy passes all 108 source/evaluation files with its existing unused-config note. The frozen-bundle and runtime checks pass with network connections denied. Classifier source, root README and engineering thresholds are unchanged. The previous full v6 verification remains 1,925 tests and 254 subtests on each runtime; it was not repeated for this preparation-only change. Hosted CI was not triggered.

**Explicit approval of the new USD4 cap is required before generation/judging.** No authorization file, API-key load or live research request is part of preparation. After approval, the existing controller performs generation, three-pass judging and paired validation automatically, preserving the first result regardless of success.
