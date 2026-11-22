# USD25 corpus run results

The authorized job completed on 22 November 2026 with **200 accepted, model-labelled synthetic documents**, exactly 50 per PII/MNPI quadrant. It stopped when the quotas filled. No extra batch, classifier tuning or training was started.

| Model-voted PII | Model-voted MNPI | Accepted |
|---|---|---:|
| Absent | Absent | 50 |
| Present | Absent | 50 |
| Absent | Present | 50 |
| Present | Present | 50 |

The run attempted 214 candidates: 200 accepted, 12 unresolved and two incomplete. All 14 unaccepted candidates remain in the challenge export. Sol generated the texts; three separate high-reasoning Terra passes annotated each completed candidate. Document labels were unanimous in 190 accepted examples and majority-supported in 10. This measures repeated-sample agreement from one judge model, not independent corroboration. Per-pass confidence and reasons remain available without an invented ensemble probability.

## Cost and interruptions

| Accounting item | USD |
|---|---:|
| Settled responses priced at the configured conservative rates | 7.02338950 |
| Full reservations retained for two unconfirmed requests | 0.17327875 |
| **Aggregate accounted/reserved ceiling** | **7.19666825** |
| Approved aggregate cap | 25.00 |
| Unused accounting headroom | 17.80333175 |

These are token-cost accounting figures, not a verified invoice or proof of credit usage. Credit applicability and actual bank FX/taxes/fees remain unverified. The previous four-document smoke job is separate and remains covered by the SGD planning reserve in [the budget proposal](model-corpus-200-budget.md).

The first process ended with SIGTERM (exit 143); its cause is unverified. A later request ended without verifiable response/usage information. Their candidates, `synthetic-0067` and `synthetic-0116`, were excluded. Requests 267 and 462 were never retried, and both full reservations remain counted. Operator-reviewed checkpoint continuations generated new candidates under the **same aggregate USD25 cap**, carrying all earlier costs forward. No budget was reset and no original artifacts were overwritten. Sanitized exception-type/status diagnostics were added for subsequent failures; the old generic error cannot establish that the earlier request timed out.

There were 854 received responses—214 generator and 640 judge responses—plus the two unconfirmed completion requests. Three known evidence/offset failures passed their single permitted correction attempt; the invalid responses remain in the audit trail. The recovered 107-document checkpoint is preserved separately from the final 200-document corpus.

## Classifier comparison

The unchanged strict engine was compared with the model-voted references. A document prediction means **any strict finding in that category**; these are broader signals than verified personal-data presence or legal MNPI determinations.

| Target | Positive references with a signal | Positive references without a signal | Negative references with a signal | Negative references without a signal |
|---|---:|---:|---:|---:|
| PII | 99 | 1 | 67 | 33 |
| MNPI | 95 | 5 | 34 | 66 |

Every one of the 67 PII-negative signal disagreements involved the email-address rule; one also involved the postal-address rule. The judge rubric excludes generic/shared company contacts. This identifies a scope/context issue to investigate before treating those counts as adjudicated detector errors. MNPI-negative signal rules include material events, financial amounts, large numbers and embargo language; their contextual/legal interpretation is not independently established.

For the narrow PII occurrence crosswalk, exact matching recovered **205 of 531 model-consensus spans (38.6%)**; overlap matching recovered **231 of 531 (43.5%)**. These are supplied-positive model-label agreement measurements, not population recall. Pooled precision/F2 remain unavailable: six accepted documents lack unanimous PII span/completeness agreement. The other 194 completeness declarations are still model assertions, not independent evidence of exhaustiveness. Another 43 PII findings are explicitly reported as unmapped rather than silently folded into those span measurements.

Span disagreements remain in 112 accepted documents. Positive PII counts are: person names 220, emails 155, personal record IDs 120, birth dates 17, postal addresses 13, government IDs 3, phones 2 and quasi-identifier combinations 1. There are **no consensus bank-account positives**. Filling the four document quadrants does not establish extensive coverage of every PII subtype, jurisdiction or real-world case.

## Verification and artifacts

The offline audit passed: all accepted spans and document-label contracts validate; every judge input links to newly generated text; request fingerprints are unique; usage/response IDs match the journals; consensus and quotas recompute; and strict evaluation reproduces with provider transport blocked. Reservations reconcile at every journal step without exceeding USD25. The 637 retained judge-annotation outputs (including unaccepted/partial records) also match their actual raw model payloads; all 214 text records link to their specific generator variants. The original 6,432 fixture/report/pilot files, old execution prefixes and runtime source were verified unchanged, and no API key or `.env` file appears in the run artifacts. No independent annotation, confidence calibration, external corpus or protected holdout evaluation was performed.

- [Machine result summary](../reports/current/model_corpus_200_usd25_results.json)
- [Accepted 200-document corpus](/home/gongahkia/.local/share/junas/research/2026-11-22-usd25-run/accepted-final.jsonl)
- [Retained 14 challenge records](/home/gongahkia/.local/share/junas/research/2026-11-22-usd25-run/challenges-final.jsonl)
- [Offline audit](/home/gongahkia/.local/share/junas/research/2026-11-22-usd25-run/audit-final.json)

Complete responses, prompts, configuration, source snapshots, cost journals and checkpoint lineage remain private under `/home/gongahkia/.local/share/junas/research/2026-11-22-usd25-run/`. No API key or `.env` file is included. The corpus is synthetic development evidence already inspected during development; it must not be promoted to independent ground truth or described as an untouched held-out benchmark.
