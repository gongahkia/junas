# Fresh holdout v6 results — 23 November 2026

The approved run completed forty accepted synthetic documents below the USD4 cap. **V6 failed five of nine unchanged targets.** MNPI detection improved from frozen v5's 1/20 to v6's 2/20 on the same fresh cohort. That small improvement is far below the 80% target. The previously reported 20/20 development replay did not transfer. [Inference] This is strong evidence of scenario-specific fitting; it does not establish which individual model-reference labels are independently correct. [Aggregate evidence](../reports/current/fresh_holdout_v6_results.json).

| Measurement | Frozen v5 | Frozen v6 |
|---|---:|---:|
| MNPI-positive detections | 1/20 | 2/20 |
| MNPI-positive abstentions | 18/20 | 17/20 |
| MNPI-positive negative predictions | 1/20 | 1/20 |
| MNPI-negative flags / abstentions | 0/20 / 0/20 | 0/20 / 0/20 |
| PII-positive detections | 18/20 | 18/20 |
| PII-positive abstentions / negative predictions | 1/20 / 1/20 | 1/20 / 1/20 |
| PII-negative flags / abstentions | 7/20 / 2/20 | 7/20 / 2/20 |
| Exact PII reference spans | 44/68 (64.71%) | 44/68 (64.71%) |
| Overlapping PII reference spans | 45/68 (66.18%) | 45/68 (66.18%) |

Abstentions count against positive detection and remain separate from negative predictions. Failed targets were MNPI-positive detection (10%, minimum 80%), MNPI-positive abstention (85%, maximum 20%), exact PII agreement (64.71%, minimum 80%), overlap PII agreement (66.18%, minimum 85%) and PII-negative flag rate (35%, maximum 10%). Four targets pass. All PII metrics tie between versions. Twenty-two typed predictions are unmatched under exact matching; overall conditional precision and F2 remain unavailable because two accepted references have unknown completeness.

## Coverage and reference limits

The cohort has ten documents per quadrant and meets all nine subtype coverage requirements. Accepted family counts are executive succession 12, court injunction 11, mineral reserves 6 and voting-control arrangements 11. This is not an equally distributed family sample. Fifty-eight candidates were attempted: forty accepted, seventeen unresolved and one interrupted candidate excluded during recovery. Admission used judge labels and coverage alone, never classifier predictions.

GPT-6.2 Sol generated sources; three GPT-6.1 Terra samples supplied references. Thirty-three accepted document references were unanimous and seven were majority references; thirty-eight have exhaustive PII coverage declarations and two have unknown completeness. These are correlated, uncalibrated model judgments, not human annotations or independent legal ground truth. Rejected ambiguous candidates are outside the scored cohort. The new scenario IDs, layouts and 8,000-entry exclusion registry reduce direct reuse but do not prove semantic novelty or training-data independence.

## Spending and recovery

| Accounting | USD |
|---|---:|
| Approved aggregate cap | 4.00000000 |
| Settled conservative token-cost ceiling | 2.42215750 |
| Retained reserve for the interrupted request | 0.08703650 |
| **Accounted / reserved total** | **2.50919400** |
| Peak accounted/reserved balance | 2.58257900 |
| Unused allowance, now closed | 1.49080600 |

Generation stopped when quotas were met, not because the cap was exhausted. The first process exited with SIGTERM (143); the origin of that signal is unverified. No worker remained active. Durable recovery validated the original journal, retained the in-flight reserve, skipped the incomplete candidate and continued with new requests under the same USD4 authorization. It did not reset the budget or replay requests. The two-segment ledger contains 230 received completions: 58 generator and 172 judge responses.

Cumulative prior plus current accounted/reserved usage is USD22.43293000, approximately S$40.38 under the existing SGD1.50/USD and 20% contingency assumptions. These are planning assumptions and conservative token ceilings, not a verified invoice, exchange-rate quote or eligible-credit balance. The allowance is closed; no further paid calls are authorized by its unused balance.

## Verification and preservation

The cohort was marked consumed before metrics and each frozen classifier evaluated it once. Source, prompts, thresholds and selection policy stayed unchanged. No retuning, replacement cohort, repeated release or retirement into development followed inspection of these scores.

The final audit denied network connections, recomputed journal reservations/settlements, validated response/source/annotation/consensus linkage and checked the saved paired scores against the frozen targets without rerunning classification. The peak and final balances remained below USD4. All 5,562 previously recorded artifact hashes match. Classifier v6 remains `63ad99341c01445f684554e25e823e195c54f8b5c0a0a040ac7814137b1a18c5`; baseline v5 remains `62849d0115fa6416041e21c44461929333cd570bcf5171c78957177ad4ac82ce`.

Runtime code did not change, so the previous full classifier suites were not repeated. The actual run artifacts, frozen inputs and accounting were verified. Hosted CI, external benchmarks, optional NER and advisory-model usefulness were not exercised. Raw sources, responses, private authorization identifiers and journals remain in `/home/gongahkia/.local/share/junas/research/2026-11-23-fresh-holdout-v6/bundle`.

The [predeclared plan](fresh-holdout-v6-plan.md) remains the planning record. This failed result is preserved as the first unseen evaluation. The classifier is not broadly reliable on this evidence; another rule-tuning cycle on these same cases must not be represented as independent validation.
