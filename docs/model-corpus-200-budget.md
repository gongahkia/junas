# Revised 200-document plan: S$50 allowance

Prepared on 22 November 2026. **The user subsequently authorized the USD25 job, which completed with 200 accepted documents and USD7.19666825 accounted/reserved.** See [the completed run results](model-corpus-usd25-results.md). The user selected GPT-6.2 Sol as the generator after a fresh, authenticated read-only model inventory listed GPT-6.1 Terra but did not list GPT-6.2 Terra. The official GPT-6.2 Terra model page also returned 404. The original preparation review below predates authorization/execution; its machine reports remain unchanged as historical evidence.

## Active configuration

[The current configuration](../config/model_corpus.200.json) uses:

| Role | Model | Effort | Maximum output tokens |
|---|---|---|---:|
| Generator | `gpt-6.2-sol` | high | 8,192 |
| Judge pass 1 | `gpt-6.1-terra` | high | 16,384 |
| Judge pass 2 | `gpt-6.1-terra` | high | 16,384 |
| Judge pass 3 | `gpt-6.1-terra` | high | 16,384 |

All roles allow at most 12,000 input tokens. The target remains 200 accepted documents: 50 each for neither, PII only, MNPI only and both. There are at most 300 candidate generations and two accounted-content attempts per judge pass. The job stops when quotas fill, the candidate limit is reached or the next request would exceed the approved USD cap. A capped run may yield fewer than 200 accepted documents; shortfalls remain explicit. No labels are forced to fill a quadrant, and there is no automatic paid resume.

This is **repeated-sample majority voting from one judge model**, configured explicitly as `judge_mode=same_model_repeats`. It is not three-model corroboration. Each pass receives only the generated text/index, its pass number and its own validation error on correction. Pass numbers 1–3 remain in requests and annotations; answers and reasoning from other passes are not shared. Model sampling can still produce identical answers or shared errors. Two-of-three support remains provisional; unanimity and dissent stay visible, and confidence remains uncalibrated self-report. Existing distinct-model mode remains available and still rejects accidental duplicate IDs.

## Enforced USD limit and SGD buffer

The API uses USD. The configuration now embeds a **USD 25 maximum for this new job**. A later authorization can choose a lower cap, but one above USD 25 is rejected before provider transport. Each completion is reserved against its exact counted input plus maximum output before transport. Unknown completion/usage retains its full reservation and stops without retry.

The SGD planning allowance uses conservative assumptions:

| Component | Amount |
|---|---:|
| New-run API cap | USD 25 |
| Reserve for historical smoke job | USD 1 |
| Planning conversion ceiling | S$1.50 per USD |
| Additional tax/card-charge multiplier | 1.20 |
| Combined buffered scenario: `(25 + 1) × 1.50 × 1.20` | **S$46.80** |
| User's allowance | **S$50** |

The earlier smoke job's configured-rate usage ceiling was USD 0.9219475; the USD 1 reserve rounds it up. [UOB's 20 November FX report](https://www.uobgroup.com/assets/web-resources/research/pdf/FXI_261120.pdf) quotes USD/SGD 1.2920, at which USD 25 is S$32.30 before tax/card charges. The 1.50 conversion and 20% extra-charge factors are chosen buffers, not verified future bank rates, tax treatment or fees. The software enforces the USD cap and validates the configured SGD scenario; an exact SGD bank charge cannot be guaranteed by a USD-denominated API budget. No free-credit balance or applicability is assumed.

## Prices and token accounting

Official prices were checked on 22 November against [GPT-6.2 Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol) and [GPT-6.1 Terra](https://developers.openai.com/api/docs/models/gpt-6.1-terra). Published standard short-context input/output rates are USD 2/10 per million for Sol and USD 1/5 for Terra. The accounting input ceilings conservatively include ordinary input plus listed 30-minute cache-write rates: USD 4.5 and USD 2.25 per million respectively. No extended-retention caching, paid tools, fast tier or Batch discount is requested. Output limits include reasoning tokens.

[The offline plan](../reports/current/model_corpus_200_sgd50_plan.json) distinguishes unrestricted token allowances from the enforceable spending cap:

| Accounting scenario | USD |
|---|---:|
| 200 candidates at every configured token limit, without judge retries | 92.5360 |
| 300 candidates at every token limit, without judge retries | 138.8040 |
| 300 candidates including every permitted judge retry | 236.8320 |
| **Effective ceiling for this configured job** | **25.00** |

The larger figures are arithmetic over token limits, not permission to spend them. The job refuses a reservation that would exceed its smaller USD authorization/configuration cap. This means completing all 200 is not established in advance. At preparation, the revised prompts and Terra annotation behavior had not been exercised live. The completed job now provides live compatibility/grounding evidence, while semantic correctness and confidence calibration remain unverified. Historical token-use scenarios, if considered, are illustrations rather than forecasts; [the revised machine cost review](../reports/current/model_corpus_200_sgd50_review.json) preserves their assumptions.

Both selected IDs appeared in the fresh model inventory, but that does not establish live inference/schema compatibility or quality. The model IDs are aliases; unexpected resolved identity/billing tier/usage still stops the run. Pricing and FX assumptions must be rechecked if more than seven days old.

## Execution boundary and evidence

The earlier expensive configuration is preserved at [the distinct-model configuration](../config/model_corpus.200.distinct.json). Its original plan/review and private source snapshot remain historical evidence and do not apply to the new configuration hash. The four-document distinct-model example remains a separate experiment.

Fresh offline planning requires no key or provider calls:

```sh
uv run --frozen python scripts/model_corpus.py plan --config config/model_corpus.200.json --output /tmp/junas-sgd50-new-plan.json
```

A future paid run still requires a private authorization declaration matching the new configuration hash, organization/project and an approved USD cap no greater than 25. The user requested cost review before launch and then explicitly authorized the one USD25 job. That authorization is recorded privately; the completed job does not authorize an additional batch. Source data remain newly generated synthetic text; historical fixtures, prior generated documents and holdout data are not sent for annotation. These remain model-derived development labels, with the existing explicit negative/unknown, exact-offset and all-quadrant checks.

Focused and full-suite verification results, source hashes, the read-only inventory result and private reproducibility location are recorded in the revised machine cost review. Existing evaluation-script type errors remain outside the scoped runner mypy result; no classifier tuning, calibration or holdout evaluation is part of this revision.

Verification completed: **84 focused tests** and **1,670 tests plus 254 subtests on each of Python 3.11 and 3.12**, without skips. Changed-file Ruff format/lint and scoped runner mypy passed. Full command: `uv run --frozen pytest -q`; focused command: `uv run --frozen pytest -q test/test_model_corpus.py`.

The completed job required operator-reviewed checkpoint continuations after an unexpected SIGTERM and a later unverifiable response/usage outcome. Each continuation carried all settled costs and full unconfirmed reservations into the same aggregate cap and generated new candidates only; no unconfirmed request or source was retried. See the completed result for the immutable segment lineage and offline audit.
