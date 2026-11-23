# Fresh holdout v3 results — 23 November 2026

The automated run generated and validated 40 accepted documents below the approved US$4 cap. **Classifier v3 failed six of the nine unchanged reliability targets.** Relative to the frozen v2 baseline, it matched one additional PII reference span and left document-level detection and abstention rates unchanged. [Inference] The earlier development gains largely failed to transfer to these new scenarios.

| Measure | Previous v2 | Current v3 |
| --- | --- | --- |
| Exact PII reference spans | 54/80 (67.5%) | 55/80 (68.8%) |
| Overlapping PII reference spans | 54/80 (67.5%) | 55/80 (68.8%) |
| PII-positive documents detected | 20/20 | 20/20 |
| PII-negative documents flagged | 4/20 | 4/20 |
| PII-negative abstentions | 8/20 | 8/20 |
| MNPI-positive documents detected | 7/20 | 7/20 |
| MNPI-positive abstentions | 13/20 | 13/20 |
| MNPI-negative documents flagged / abstaining | 0/20 / 0/20 | 0/20 / 0/20 |

Positive detection counts abstentions against detection. The 13 MNPI abstentions are explicit unknowns, not negative predictions. PII document detection alone hides substantial span gaps: v3 still misses 25 reference spans and has six unmatched predictions on model-declared exhaustive annotations. Conditional PII precision is 90.2% and F2 is 72.2%; these depend on unverified model completeness and do not establish independent accuracy.

| PII type | Reference occurrences | v2 exact matches | v3 exact matches |
| --- | --- | --- | --- |
| Person name | 25 | 14 | 15 |
| Personal record ID | 16 | 11 | 11 |
| Personal email | 21 | 21 | 21 |
| Government ID | 3 | 3 | 3 |
| Postal address | 3 | 3 | 3 |
| Bank account | 3 | 1 | 1 |
| Date of birth | 3 | 1 | 1 |
| Phone | 3 | 0 | 0 |
| Quasi-identifier combination | 3 | 0 | 0 |

The failed targets were exact PII agreement (68.75%, minimum 80%), overlap agreement (68.75%, minimum 85%), PII-negative flag rate (20%, maximum 10%), PII-negative abstention rate (40%, maximum 25%), MNPI-positive detection (35%, minimum 80%) and MNPI-positive abstention (65%, maximum 20%). The three passing targets were PII-positive document detection and both MNPI-negative rates. No labels, thresholds or classifier code were changed during generation or after inspecting the scores.

The cohort contains ten documents in each PII/MNPI quadrant, and at least three consensus occurrences of every PII type. It uses newly reserved refinancing, operating-licence suspension, tender-withdrawal and public-investment-education families. The 4,610-entry exclusion registry covers earlier generated candidates, rejected sources and authored regressions. Fingerprint/shingle checks do not prove semantic novelty or independence from model training data.

Sixty-four candidates were attempted: 40 accepted references, 21 unresolved candidates and three failed candidates. The unresolved/failed sources remain private challenges. Selection used judge labels and coverage only. GPT-6.2 Sol generated text; three separate GPT-6.1 Terra passes supplied two-of-three consensus. Thirty-eight accepted document references were unanimous and two were majority references. All 40 PII references were unanimously declared exhaustive with agreed spans. These are model-reference agreements; the judges share a model and can share errors. No human annotations were used, confidence remains uncalibrated, and legal materiality/public status remain unverified.

| Budget accounting | USD |
| --- | ---: |
| Approved cap | 4.00000000 |
| Settled token-cost ceiling | 2.08486750 |
| Retained reserves for two uncertain completion requests | 0.16961350 |
| **Total accounted / reserved** | **2.25448100** |
| Unused allowance, now closed | 1.74551900 |

The ledger contains 248 received completions: 63 generator and 185 judge responses. Execution used four durable segments following interruptions and one token-preflight failure without a completion. Recovery retained every uncertain reserve, skipped incomplete candidates and refused a stale branch before any new API call. No paid request was replayed, and the cap was never reset or increased. A temporary Python environment disappeared; recovery used persistent Python 3.12.16 with the same recorded environment and matching numpy/httpx versions. Recorded token-cost ceilings are not a verified provider invoice or credit balance.

Cumulative previous plus current accounted/reserved usage is US$17.69404350. At the stated planning assumptions of S$1.50/US$ and 20% contingency, that is about S$31.85; this is not a current exchange-rate quote or bank charge. The allowance is closed and its unused balance does not authorize further paid calls.

Preparation passed 129 relevant tests on each of Python 3.11 and 3.12, Ruff lint/format on three changed Python files and scoped mypy on two sources. The full classifier suite was not repeated because runtime code is unchanged from the previously verified v3. Frozen-bundle integrity, response/source/consensus linkage and aggregate-budget recovery checks passed. Local classification and the final audit denied network connections. All 6,771 initial repository files were checked for unexpected changes; the existing uncommitted patch and README remain unchanged. Earlier archives retain all 1,079, 971, 851 and 45 recorded file hashes.

The holdout was consumed once before metrics. It is no longer unseen validation and was not converted into development data in this task. There was no tuning, repeated release or additional paid experiment after the result. Raw sources, responses, ledger and frozen classifiers remain private. Aggregate evidence is in [the results report](../reports/current/fresh_holdout_v3_results.json), with the predeclared design in [the plan report](../reports/current/fresh_holdout_v3_plan.json).

Frozen v2 SHA-256: `9e28c87ad7acb888b7506ad9e061abd8d7b6f3773b1089cb29040a6a7aaf3c62`. Frozen v3 SHA-256: `7ec08c5a4570c1868f51b53b4741ee2312e1a3379b75b1e47e0d081b21d6df3f`.
