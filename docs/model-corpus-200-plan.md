# Prepared 200-document majority/quadrant run

**Superseded cost proposal:** the user subsequently chose a S$50 allowance. The active plan now uses Sol generation, three Terra samples and a USD 25 limit; see [the budget revision](model-corpus-200-budget.md). This page and its original reports preserve the earlier distinct-model proposal.

Prepared on 22 November 2026. **No paid inference has been launched for this proposal.** The earlier USD 5 authorization applied to the historical four-document job, not this configuration. User review of the cost and a new spending cap must precede a live run.

## Corpus and voting contract

The [historical configuration](../config/model_corpus.200.distinct.json) targets **200 accepted synthetic development documents**:

| Observed PII | Observed MNPI | Accepted target |
|---|---|---:|
| Absent | Absent | 50 |
| Present | Absent | 50 |
| Absent | Present | 50 |
| Present | Present | 50 |

Observed states come from separate judge votes, not the generator's requested quadrant. Every document uses a separate generator and exactly three distinct judge model IDs. Two-of-three support produces provisional majority labels; three-of-three support is identified separately. The vote threshold stays two when a judge abstains. A positive document label needs source-grounded evidence; a negative needs an explicit exhaustive-completeness declaration and no positive evidence. Missing materiality/publicity information stays unknown. Confidence remains each model's uncalibrated self-report.

The runner targets the largest remaining deficit, accepts only resolved observed quadrants with space, and stops immediately when all targets are filled. It permits at most **300 generated candidates**, including failed, uncertain or excess-quota examples. Each judge has at most **two accounted-content attempts**; the generator has one. Unknown transport/usage stops without retry and retains the full reservation. Raw attempts, dissent, failures, unaccepted candidates and quota shortfalls remain in the run artifacts. Reaching the candidate or spending limit can leave fewer than 200 accepted examples; the report/CLI then indicate incomplete coverage. There is no automatic paid resume or extra generation beyond these limits.

Document-level TP/FP/TN/FN counts are reported separately for PII and MNPI, overall and by quadrant, relative to model-voted references. The prediction is any strict category finding; MNPI signals are not legal truth. PII exact/overlap span metrics retain the existing nine-label crosswalk and separately report unmapped findings. Span precision/F2 require unanimous declared completeness and span agreement, even where document labels have majority support. An accepted document can therefore have provisional document labels and unresolved span completeness.

This intentionally balanced corpus does not estimate production prevalence. All models use OpenAI, so different IDs do not establish independent errors or provider diversity. No calibration, training or classifier tuning is part of this run. It is developmental data; a separately reserved, scenario-grouped test set must be frozen before future tuning and holdout claims.

## Models, prices and limits

Prices were rechecked against the official [Astra](https://developers.openai.com/api/docs/models/gpt-6.2-astra), [Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol), [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4) and [GPT-5.2](https://developers.openai.com/api/docs/models/gpt-5.2) documentation on 22 November 2026. All roles use high reasoning and the standard service tier. There are no tools, search fees or Batch discounts in this proposal. Reasoning tokens count toward output limits.

| Role / model | Input limit | Output limit | Published input / output USD per million | Accounting input ceiling USD per million |
|---|---:|---:|---:|---:|
| Generator: `gpt-6.2-astra` | 12,000 | 8,192 | 8 / 40 | 18 |
| Judge: `gpt-6.2-sol` | 12,000 | 8,192 | 2 / 10 | 4.5 |
| Judge: `gpt-5.4-2026-03-05` | 12,000 | 16,384 | 2.5 / 15 | 2.5 |
| Judge: `gpt-5.2-2025-12-11` | 12,000 | 16,384 | 1.75 / 14 | 1.75 |

Astra/Sol accounting inputs conservatively include ordinary input plus the listed 30-minute cache-write rates. No extended-retention caching is requested or discount assumed. The earlier authenticated read-only model inventory listed all four IDs, including the pinned GPT-5.2 snapshot. That inventory does not certify live access, endpoint/schema compatibility or annotation quality for this revised experiment; those remain unverified without inference. Model identity/billing tier/usage bounds are checked on each response.

## Cost review

The [offline machine plan](../reports/current/model_corpus_200_plan.json) records the exact configuration hash and arithmetic:

| Scenario | Maximum completions | Configured token-cost ceiling, USD |
|---|---:|---:|
| 200 candidates, no judge retries | 800 | **241.1472** |
| 300 candidates, no judge retries | 1,200 | **361.7208** |
| 300 candidates, every judge uses both attempts | 2,100 | **560.3376** |

Each completion also has one input-token preflight. The last row includes all permitted refill candidates and judge corrections; it is the conservative bound to consider for a cap covering the entire prepared configuration. A rounded **USD 561 cap** would cover that configured arithmetic. A lower approved cap is supported, but can stop before the quotas are filled. No cap or authorization declaration has been created for this run.

For a smaller-cost *scenario*, replaying the historical smoke's observed token consumption across 200 candidates and adding a GPT-5.2 judge at the successful GPT-5.4 annotations' observed token counts gives **USD 64.1362**; 300 candidates at that usage gives **USD 96.2043**. This includes the historical failed-attempt token overhead, but assumes the new judge consumes the proxy's tokens. It is not a forecast, confidence interval or spending bound: document decisions, prompts, lengths, quota acceptance rates and GPT-5.2 consumption have not been measured live. The detailed formula and source hashes are in [the cost review](../reports/current/model_corpus_200_cost_review.json).

All figures are configured-rate token accounting, not a verified invoice. Credit balance, expiry and applicability remain unverified; this proposal does not assume free credits. API keys and private account IDs are absent from the plan/configuration/reports.

## Offline preparation and future execution

To produce a fresh offline plan without reading `.env` or making provider requests:

```sh
uv run --frozen python scripts/model_corpus.py plan --config config/model_corpus.200.json --output /tmp/junas-200-new-plan.json
```

After the user reviews the cost and authorizes a specific cap, prepare a new private authorization declaration bound to that exact configuration hash using the [authorization contract](automated-corpus.md#paid-run-boundary-and-accounting). The eventual command is:

```sh
uv run --frozen python scripts/model_corpus.py run --config config/model_corpus.200.json --authorization /path/to/private/approved-200-authorization.json --env-file .env --output /path/to/private/new-200-run
```

The paths above are placeholders, not existing authorization or a paid launch. Source text must still be newly generated; historical fixtures, the earlier four documents and protected holdout data are not inputs. V2 intentionally rejects old v1 configurations and declarations; historical v1 results retain their original interpretation and snapshots.

## Verification

The new focused suite passes **67 tests**, including a complete mocked 200-document/three-judge run that fills all four quotas and stops at 200, before the 300-candidate ceiling. Additional tests cover majority/unanimous/minority support, document-level dissent, abstentions, the materiality/publicity state table, exhaustive negative declarations, exact evidence, unknown exclusion, both categories' TP/FP/TN/FN counts, generator/judge separation, bounded refill, mismatched requested/observed quadrants, budget/uncertain transport and exact plan costs. Scoped runner mypy and changed Python Ruff checks pass.

Full suites passed on both Python 3.11 and 3.12: **1,653 tests plus 254 subtests on each version, without skips**. Commands: `uv run --frozen pytest -q`, `uv run --frozen pytest -q test/test_model_corpus.py`, Ruff format/check on the two changed Python files, and `uv run --frozen mypy --explicit-package-bases --follow-imports=silent scripts/model_corpus.py`. No new live-model quality or compatibility test, confidence calibration, external corpus evaluation or holdout evaluation was performed. The existing broader research mypy check remains outside the clean scoped result and previously reported 11 errors in unchanged evaluation scripts.
