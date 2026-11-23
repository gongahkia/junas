# Fresh holdout v5 results — 23 November 2026

The approved automated run generated and validated **40 accepted synthetic documents below the USD4 cap**. **Classifier v5 failed three of nine unchanged reliability targets.** Frozen v4 and v5 tied on every reported paired metric. The earlier local abstention repair showed no measurable benefit on this new cohort; the main remaining gap is MNPI generalization. [Complete aggregate evidence](../reports/current/fresh_holdout_v5_results.json).

| Measure | Frozen v4 | Frozen v5 |
|---|---:|---:|
| Exact PII reference spans | 71/85 (83.53%) | 71/85 (83.53%) |
| Overlapping PII reference spans | 72/85 (84.71%) | 72/85 (84.71%) |
| PII-positive documents detected | 20/20 | 20/20 |
| PII-negative documents flagged | 1/20 | 1/20 |
| PII-negative abstentions | 5/20 | 5/20 |
| MNPI-positive documents detected | 3/20 | 3/20 |
| MNPI-positive abstentions | 17/20 | 17/20 |
| MNPI-negative documents flagged / abstaining | 0/20 / 1/20 | 0/20 / 1/20 |

Abstentions count against positive detection and remain explicit unknowns, not negative predictions. Failed targets were PII overlap agreement (84.71%, minimum 85%), MNPI-positive detection (15%, minimum 80%) and MNPI-positive abstention (85%, maximum 20%). The other six pass; PII-negative abstention sits exactly at its 25% maximum. No thresholds, reference labels or classifier code were changed in response to these scores.

| PII subtype | Reference spans | v5 exact matches | v5 overlap matches |
|---|---:|---:|---:|
| Bank account | 4 | 1 | 1 |
| Date of birth | 4 | 4 | 4 |
| Email | 23 | 23 | 23 |
| Government ID | 3 | 3 | 3 |
| Personal record ID | 14 | 11 | 11 |
| Person name | 28 | 24 | 25 |
| Phone | 3 | 2 | 2 |
| Postal address | 3 | 3 | 3 |
| Quasi-identifier combination | 3 | 0 | 0 |

V5 has fourteen missed exact reference spans and two unmatched typed predictions; seven additional legacy-rule predictions are explicitly unmapped to the contextual target taxonomy. Two accepted documents have unknown reference completeness, so overall conditional PII precision and F2 are unavailable. Supplied-positive span agreement does not establish population recall or legal accuracy.

## Cohort and reference quality

The cohort has ten documents in each PII/MNPI quadrant and at least three model-consensus occurrences of every required PII subtype. Newly reserved families cover dividend deferral, clinical-trial unblinding, asset impairment and public sustainability corrections. The 7,833-entry exclusion registry includes prior candidates/rejections, regressions, internal fixtures and the external texts measured during the previous task. Exact/skeleton and shingle checks are contamination heuristics, not proof of semantic novelty or model-training independence.

Sixty-four candidates were attempted: forty accepted, twenty-three unresolved and one failed. The failed candidate was excluded after two judge responses failed exact evidence/offset validation. Selection used judge labels and coverage alone; classifier predictions did not choose the cohort. The accepted references comprise thirty-eight unanimous and two majority document references. Thirty-eight have exhaustive PII coverage declarations and two have unknown completeness. The read-only reference audit flags twenty-three unresolved document-vote cases and makes no label changes.

GPT-6.2 Sol generated the sources; three separate GPT-6.1 Terra samples supplied majority references, all with the approved high reasoning settings. Same-model judge samples can share errors. No human annotations were used. Independent accuracy and calibrated confidence remain unavailable, and the rejected ambiguous cases are outside the scored cohort.

## Cost and stopping

| Accounting | USD |
|---|---:|
| Approved cap | 4.00000000 |
| Settled conservative token-cost ceiling | 2.22969250 |
| Retained uncertain reserves | 0 |
| Peak accounted/reserved balance | 2.30579250 |
| Unused allowance, now closed | 1.77030750 |

Generation stopped when all quotas were met; it did not hit the budget. The one-segment ledger has 255 received completions (64 generator, 191 judge), zero uncertain completion charges and zero replayed requests. The final audit recomputed every reservation and settlement, verified usage/model/request/source/consensus linkage and checked that the balance never exceeded USD4. These conservative ceilings are not a verified provider invoice or eligible-credit balance.

Cumulative prior plus current accounted/reserved usage is **USD19.92373600**, about **S$35.86** under the existing SGD1.50/USD and 20% contingency planning assumptions. This is not a current FX quote or bank charge. The allowance is closed; unused funds do not authorize another paid run.

## Verification and preservation

The cohort was marked consumed before scoring, then evaluated once against each frozen classifier. The controller exited 1 because reliability targets failed, after successful generation and paired evaluation. No classifier tuning, second release, replacement holdout or extra paid experiment followed the scores.

Frozen-bundle/environment integrity, ledger recovery, response/source/reference linkage and saved-metric/threshold checks passed. The final audit denied network connections and read existing scores without rerunning classification. Baseline evaluation denied network connections; the improved strict classifier retained its frozen default configuration. All 4,236 prior archived artifact hashes match. Original v3 results, prior proposals, labels, root README and thresholds remain unchanged.

Runtime code did not change, so the previous full verification (1,850 tests plus 254 subtests on each Python version) was not repeated. Current work verifies the actual live-run artifacts and document/JSON integrity. Hosted CI, optional NER and live advisory usefulness were not exercised.

Raw sources, model responses, authorization identifiers and journals remain private in `/home/gongahkia/.local/share/junas/research/2026-11-23-evaluation-closeout/holdout-v5`. The [predeclared proposal](fresh-holdout-v5-plan.md) remains the planning record. This cohort is consumed and no longer unseen; the original failed result must remain intact during any future development analysis.

Frozen v4 runtime: `2d311c9eb04d9f7bfa21802e6603ca4164de915d9a1e7c355000a23203745c3c`. Frozen v5 runtime: `62849d0115fa6416041e21c44461929333cd570bcf5171c78957177ad4ac82ce`.
