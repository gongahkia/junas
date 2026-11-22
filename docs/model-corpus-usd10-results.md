# Automated 72-development / 40-holdout run

Completed the user-approved synthetic-only job under the combined **USD10** cap. The classifier, prompts and model settings remained frozen across both batches. No further paid calls were made after the requested quotas were filled.

| Batch | Accepted | Candidates | Per quadrant | Configured-rate usage ceiling |
|---|---:|---:|---:|---:|
| Development | 72 | 92 | 18 | USD2.82947000 |
| Holdout | 40 | 54 | 10 | USD1.75355450 |

Combined configured-rate usage accounting: **USD4.58302450**, with **USD0** in uncertain request reserves. The cap was not reached. This is conservative token accounting, not a verified invoice or confirmation of credit usage. USD5.41697550 of this job's allowance was unused; it is not an account credit balance or approval for further inference.

Both batches met all nine entity-coverage targets: at least three accepted positive occurrences per PII type in development and at least one per type in holdout. These targets count model-reference occurrences. Detector performance is reported separately below.

The generator was GPT-6.2 Sol with high reasoning. Annotation used three separate GPT-6.1 Terra passes with high reasoning. Agreement among repeated samples of one judge model does not establish independent errors or ground truth.

## Frozen classifier versus model-reference labels

The table uses the contextual `ReviewResult.sensitivity` predictions, separately from the existing broad risk findings/scores. References are synthetic, model-derived labels. Unknown classifier predictions are shown explicitly and are not counted as correct negatives.

| Batch / target | Positive detected | Positive missed | Positive abstained | Negative flagged | Negative no candidate | Negative abstained |
|---|---:|---:|---:|---:|---:|---:|
| Development / PII | 28 | 3 | 5 | 14 | 13 | 9 |
| Development / MNPI | 13 | 1 | 22 | 0 | 33 | 3 |
| Holdout / PII | 18 | 2 | 0 | 4 | 3 | 13 |
| Holdout / MNPI | 5 | 0 | 15 | 0 | 14 | 6 |

| Batch / PII occurrence comparison | Exact model-reference matches | Overlap model-reference matches |
|---|---:|---:|
| Development | 46/129 | 55/129 |
| Holdout | 33/97 | 36/97 |

Occurrence matching is maximum-cardinality one-to-one matching with exact/overlap results kept separate. Pooled precision/F2 are qualified by model-declared coverage; missing completeness retains unavailable metrics. Even unanimous completeness remains unverified model testimony. No independently validated accuracy or calibrated confidence is available.

### PII span agreement by entity type

| Type | Development exact / reference | Holdout exact / reference |
|---|---:|---:|
| BANK_ACCOUNT | 2/3 | 0/1 |
| DATE_OF_BIRTH | 5/6 | 3/3 |
| EMAIL | 26/27 | 21/23 |
| GOVERNMENT_ID | 3/4 | 1/1 |
| PERSONAL_RECORD_ID | 5/29 | 4/28 |
| PERSON_NAME | 5/43 | 4/37 |
| PHONE | 0/3 | 0/1 |
| POSTAL_ADDRESS | 0/7 | 0/2 |
| QUASI_IDENTIFIER_COMBINATION | 0/7 | 0/1 |

The largest heldout exact-span gaps were person names (4/37) and personal record IDs (4/28). Bank accounts, phones and quasi-identifiers each have only one heldout reference occurrence; those sparse results do not establish population performance.

## Integrity and limitations

- 20 development and 14 holdout candidates had unresolved reference labels and were retained outside the accepted sets. No incomplete/failed candidates or uncertain requests remained.
- Three holdout annotation responses required bounded validation retries; their initial responses and paid usage were retained. Development required no such retries. No annotations were manually repaired or relabelled.
- Holdout source admission screened against 2124 previously used source texts, including all newly generated development sources. No source conflict was admitted. Hash/shingle and scenario-group screens do not prove semantic independence or access isolation.
- Source/annotation linkage was validated against actual saved model responses; request and token-cost journals reconciled. No request fingerprint was replayed.
- The holdout was evaluated once against the frozen classifier and is now consumed. It is not an untouched test set for subsequent tuning.
- All 6750 protected original repository files and 1,079 prior paid-job artifacts were verified unchanged. No classifier or prompt tuning occurred during this job.
- Labels remain model-reference research evidence. The corpus is synthetic and Singapore-focused, with balanced artificial prevalence and selection for resolved labels. It does not establish real-world legal MNPI status, sensitivity, precision or confidence calibration.

Aggregate evidence: `reports/current/model_corpus_coverage_holdout_usd10_results.json`.

Private accepted sources, raw responses, authorizations, journals, frozen source, audits and the one-time holdout evaluation remain at `/home/gongahkia/.local/share/junas/research/2026-11-22-coverage-holdout-usd10`. No API key is included.
