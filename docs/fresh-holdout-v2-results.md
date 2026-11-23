# Fresh holdout validation — 23 November 2026

The 40-document holdout was generated and consumed once for paired validation. The improved classifier does not pass all predeclared engineering targets. Both frozen versions used the same synthetic model-consensus references.

| Contextual measure | Baseline | Improved |
| --- | --- | --- |
| PII exact spans | 24/71 (33.8%) | 45/71 (63.4%) |
| PII overlap spans | 24/71 (33.8%) | 45/71 (63.4%) |
| PII-positive documents detected | 17/20 | 19/20 |
| PII-negative documents flagged | 9/20 | 5/20 |
| PII unresolved documents | 11 | 8 |
| MNPI-positive documents detected | 3/20 | 14/20 |
| MNPI-negative documents flagged | 0/20 | 0/20 |
| MNPI unresolved documents | 19 | 6 |

Abstentions count against positive detection and negative coverage. `not_detected` does not establish absence. Span agreement measures supplied positive references rather than population recall. Reference coverage was declared exhaustive for 39 documents and unknown for one, so pooled PII precision and F2 are unavailable.

Unmet engineering targets:

- `mnpi_positive_abstention_rate_max`: observed 0.3000, target 0.2000.
- `mnpi_positive_detection_min`: observed 0.7000, target 0.8000.
- `pii_exact_span_agreement_min`: observed 0.6338, target 0.8000.
- `pii_negative_abstention_rate_max`: observed 0.3500, target 0.2500.
- `pii_negative_flag_rate_max`: observed 0.2500, target 0.1000.
- `pii_overlap_span_agreement_min`: observed 0.6338, target 0.8500.

The holdout is now consumed. No classifier changes or repeated tuning/evaluation were performed in this run. These results do not support another claim of unseen validation on these sources.

The initial 80-candidate batch produced 39 accepted references. Before any classifier metrics were computed, the candidate resource bound was prospectively extended to complete the already authorized 40-document cohort. Only the unused USD0.30223925 from the same USD3 cap was allocated to completion; one new candidate completed the missing both-positive quadrant for USD0.04016150. Models, primary thresholds, label/voting rules and classifier snapshots were unchanged. Source-job document IDs were namespaced without changing any source text, annotation or accepted label. The combined 40-document set was then released exactly once. This resource amendment is recorded in the machine-readable result.

Accounted token-cost ceiling: **US$2.73792225** of the **US$3 cap**. Settled usage ceiling: US$2.47787700; uncertain reserve: US$0.26004525. These are conservative usage-based accounting amounts, not a verified provider invoice. The job allowance is closed; the unused amount is not authorization for another run.

The ledger audit reconciled 320 received completions, 3 uncertain requests, and zero request replays. Every ledger step stayed within the cap. Known judge-validation correction attempts: 2. Unknown request charges were not automatically retried.

Two API read timeouts and one execution-process interruption required recovery. Execution used 5 durable segments under the same aggregate cap. Unfinished candidates were skipped on recovery, and uncertain request reservations were carried forward without resending those requests.

| Judged quadrant | Accepted | Target |
| --- | --- | --- |
| both | 10 | 10 |
| mnpi_only | 10 | 10 |
| neither | 10 | 10 |
| pii_only | 10 | 10 |

| PII reference type | Observed occurrences | Target |
| --- | --- | --- |
| BANK_ACCOUNT | 3 | 3 |
| DATE_OF_BIRTH | 4 | 3 |
| EMAIL | 20 | 3 |
| GOVERNMENT_ID | 3 | 3 |
| PERSONAL_RECORD_ID | 10 | 3 |
| PERSON_NAME | 22 | 3 |
| PHONE | 3 | 3 |
| POSTAL_ADDRESS | 3 | 3 |
| QUASI_IDENTIFIER_COMBINATION | 3 | 3 |

| PII type: exact source-span agreement | Baseline | Improved |
| --- | --- | --- |
| BANK_ACCOUNT | 0/3 | 2/3 |
| DATE_OF_BIRTH | 2/4 | 2/4 |
| EMAIL | 18/20 | 18/20 |
| GOVERNMENT_ID | 3/3 | 3/3 |
| PERSONAL_RECORD_ID | 1/10 | 3/10 |
| PERSON_NAME | 0/22 | 14/22 |
| PHONE | 0/3 | 1/3 |
| POSTAL_ADDRESS | 0/3 | 2/3 |
| QUASI_IDENTIFIER_COMBINATION | 0/3 | 0/3 |

The improved classifier still leaves one PII-positive document unresolved; among 20 PII-negative references it flags five and abstains on seven. It abstains on six of 20 MNPI-positive references. Personal-record IDs (3/10 exact matches), person names (14/22) and quasi-identifiers (0/3) remain notable extraction gaps. These are supplied model-reference observations, not independently verified legal errors.

Unresolved candidates: 38; failed candidates: 3. Raw challenges, disagreement and provenance remain in the private run directory.

The generator was GPT-6.2 Sol with high reasoning; three separate GPT-6.1 Terra passes supplied model-consensus references. These repeated passes are not independent models or human annotations. The sample is small and quota-balanced; agreement is not population accuracy. Legal materiality, public status, model confidence and rule scores remain unverified or uncalibrated.

Verification used the frozen controller and classifiers. It checked source/annotation identity, exact recomputed consensus, exclusion integrity, configuration/model identities, request/usage linkage, budget accounting and recovery. Generator and judge inputs contained no classifier predictions. All pre-existing repository files and the original uncommitted patch were preserved. Runtime code and reference labels were not changed to improve the result.

Baseline runtime SHA-256: `b9ced7e9e858b6226c28aabbbef7a304c3b2a00f2ef18cb4169d375886d01739`. Improved runtime: `9e28c87ad7acb888b7506ad9e061abd8d7b6f3773b1089cb29040a6a7aaf3c62`. Configuration: `605f7be34ac5917d5fc7e7c978c6344bbb95f6e5f30877367ef9cce690cc49ea`.

Model pricing was rechecked on 23 November against the official [Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol) and [Terra](https://developers.openai.com/api/docs/models/gpt-6.1-terra) pages. The controller retains the previously approved conservative input-price ceilings and reserves the full output allowance before sending each request.

See the [machine-readable result](../reports/current/fresh_holdout_v2_results.json) for full aggregate metrics and accounting. Raw sources, annotations, requests and responses remain private.
