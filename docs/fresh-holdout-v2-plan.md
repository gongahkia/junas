# Fresh unseen holdout plan — 22 November 2026

The automated workflow is prepared; no new documents have been generated and no paid API calls have been made. It is waiting for approval of a new **US$3 cap**. No authorization file was created and the closed USD10 allowance will not be reused.

The target is 40 new synthetic documents, 10 in each PII/MNPI quadrant: neither, PII only, MNPI only, and both. Each of the nine PII types has a target of at least three model-consensus occurrences. These subtype targets exceed the previous holdout's one-occurrence targets. A budget, candidate or coverage shortfall is reported as incomplete; labels and thresholds will not be changed to complete the batch.

The generator remains GPT-6.2 Sol with high reasoning. Three separate GPT-6.1 Terra passes judge each document, with a fixed two-of-three majority. These are repeated samples of one judge model, so correlated errors remain possible. No classifier predictions are used to select documents or inform the generator/judges.

Four new scenario families are reserved:

- Escrow release reconciliation notes.
- Employee share-plan exercise settlement instructions.
- Listed-issuer product recall briefings.
- Public exchange consultation digests.

The exclusion registry has 4,405 entries. It inherits 2,124 prior exclusions, refreshes repository fixtures and authored regression sources, and fingerprints prior synthetic candidates and generator responses, including rejected sources and the consumed holdout. Old holdout labels were not used for preparation or retesting. Exact, normalized, numeric/email skeleton and shingle checks can reject reuse; they do not prove semantic novelty or independence from model training data.

Both classifiers, evaluator code, the dependency lock, recorded runtime/environment settings, thresholds, configuration and exclusions are bound in a private bundle. Generation and judging run using its frozen controller. The release requires complete coverage and rechecks the exclusions, source identities and three-judge consensus. It marks the holdout consumed before calculating metrics, then evaluates the improved and baseline classifiers on exactly the same records. It reports counts, span agreement, abstentions, fixed-target checks and before/after differences. A second release is refused.

| Cost item | Proposal |
| --- | --- |
| Previous 40-document stage, conservative accounted cost | US$1.75 |
| Planning estimate with 25% buffer, rounded upward | **US$2.20** |
| New hard token-cost budget | **US$3.00** |
| Additional SGD planning scenario | **S$5.40** |
| Prior reserve plus new cap, SGD scenario | **S$28.80**, within the stated S$50 allowance |

The SGD scenarios use a planning ceiling of S$1.50 per US dollar and 20% contingency; they are not current exchange-rate or bank-invoice quotes. Prior accounted/reserved spending is rounded up to US$13. Credit eligibility and actual invoice amounts remain unverified.

Current published Standard rates were checked: Sol is US$2 input/US$10 output per million tokens; Terra is US$1/US$5. The budget retains conservative input ceilings of US$4.50/US$2.25 to include Standard input plus 30-minute cache-write cost, assumes no cache savings, and reserves the full output ceiling before each completion. See the [Sol pricing page](https://developers.openai.com/api/docs/models/gpt-6.2-sol) and [Terra pricing page](https://developers.openai.com/api/docs/models/gpt-6.1-terra).

The configured maximum for all 80 candidates and bounded judge correction attempts at full token ceilings is US$63.16, which exceeds the proposed cap. **The US$3 cap may stop before the requested coverage is complete.** An uncertain request retains its full reserve and is not automatically retried. Budget stopping does not select a smaller successful-looking result for evaluation.

Verification: 125 relevant tests pass on each of Python 3.11 and 3.12, including mocked network boundaries, recovery, contamination checks, frozen-input/environment drift, budget stopping and one-shot paired release. Ruff format/lint and scoped mypy pass. The full classifier suite was not rerun because no runtime classifier files changed; the improved runtime hash matches the previously tested version. Repeated test snapshots initially exhausted temporary storage; sharing immutable fixture data resolved the test failures. The actual bundle passed integrity checks and refused execution without authorization before loading the key or creating a run.

The private bundle is `/home/gongahkia/.local/share/junas/research/2026-11-22-fresh-holdout-v2`. Its baseline runtime hash is `b9ced7e9e858b6226c28aabbbef7a304c3b2a00f2ef18cb4169d375886d01739`; the improved hash is `9e28c87ad7acb888b7506ad9e061abd8d7b6f3773b1089cb29040a6a7aaf3c62`. Raw sources, future API responses and the local key stay outside public reports. Original uncommitted changes and all 1,079/971 archived paid-run file hashes remain unchanged.

This is a small unseen synthetic model-reference check. It does not establish independent legal ground truth, calibrated confidence or population accuracy. All results, including regressions and abstentions, will be reported after the one-shot evaluation. Once inspected, this holdout is consumed and cannot support another unseen validation claim.

The machine-readable [cost and preparation report](../reports/current/fresh_holdout_v2_plan.json) records the exact configuration and frozen manifest identities.
