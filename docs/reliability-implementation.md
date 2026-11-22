# Automated reliability implementation

The eight agreed changes are implemented in order. All verification and corpus comparison in this tranche are offline; no additional paid inference or human annotation has been performed. The previously inspected 200 documents remain development data. Their labels are provisional model consensus, not independent ground truth.

1. **Target definitions.** `ReviewResult.sensitivity` exposes person-linked PII and text-claimed contextual MNPI separately from the existing broad `findings`, risk scores and `SAFE`/risk classification. Shared organizational contacts are excluded from the personal-contact target. Unestablished person association returns `unknown`. `not_detected` means no contextual candidate was found; absence is never verified. Existing broad signals and scoring retain their original meaning.
2. **Fresh grouped holdout.** `config/corpus-partitions.json` reserves distinct development and holdout scenario/template groups. `config/model_corpus.holdout.json` proposes 40 fresh accepted documents, ten per quadrant. These are reservations, not collected data. Ordinary evaluation skips holdout records, and development diagnostics refuse them. Before any annotation calls, holdout source admission checks a config-bound exclusion registry using source hashes and the existing annotation-pilot shingle/Jaccard contamination heuristic. This is a contamination screen, not proof of semantic independence or access isolation.
3. **Error analysis.** `scripts/corpus_diagnostics.py` produces document IDs, missing entities, boundary errors, unmatched versus unjudged predictions, unmapped rules, negative-reference signals and contextual abstentions. Matching reuses the existing maximum-cardinality one-to-one occurrence implementation. Reports preserve model-reference and coverage qualifications.
4. **Contextual PII.** Explicit personal-name, employee/client/contact-record and birth-date fields have local exact-offset detectors. Names preserve repeated occurrences and Unicode; birth dates require valid calendar dates. Field labels are excluded from entity boundaries. Organizational fields and generic contacts have separate handling. Name-shaped email local parts remain a heuristic rather than verified identity linkage.
5. **Contextual MNPI.** A positive hypothesis requires local issuer, event, explicit materiality and nonpublic-claim evidence, with auditable component spans. Public claims, negation, hypothetical/immaterial matters, mixed claims, separate paragraphs and unrelated issuer/disclosure contexts are handled conservatively. Public status is text-claimed and never externally verified. Cross-paragraph linkage and many materiality implications remain unresolved.
6. **Coverage gaps.** Explicit personal bank accounts, phones/extensions, government IDs, home addresses and identifying combinations of quasi-identifiers have positive and corporate/generic-negative regression cases. Generator proposals target the largest observed entity deficit. Only accepted consensus-positive occurrences count toward targets. Reaching quadrant quotas with missing entity types reports `coverage_shortfall`; labels are never forced or substituted. Quotas count occurrences, not independent documents. Coverage is intentionally bounded, and a shortfall requires a revised future proposal rather than unbounded generation.
7. **Recovery.** The main runner journals each preflight, reservation and settlement; fsyncs request/response artifacts; and saves atomic candidate snapshots. `--resume-from` reconstructs aggregate costs, validates sources and completed annotations against saved model responses, keeps uncertain reserves, and skips incomplete candidates. It uses new candidate variants and request hashes, without replaying uncertain requests. Original authorization/cap, configuration and prompt identity cannot change. Segment locks and a one-use continuation claim reject simultaneous or duplicate continuations. A damaged spending journal fails closed. Old historical run formats need an audited migration; the completed USD25 run is not reopened.
8. **Regression/reporting gates.** `scripts/check_reliability.py` runs 72 authored synthetic cases: all four quadrants × nine entity types × two source layouts. Gates cover document errors/abstentions and exact positive-entity spans. CI also runs mocked budget, crash, offset, abstention and partition contracts on Python 3.11/3.12. These cases are development regressions and do not establish population accuracy. Offline corpus reporting includes per-quadrant confusion counts, per-entity exact/overlap agreement, unknowns, and explicit nulls for independently validated accuracy and calibrated confidence. A one-time `release-holdout` operation records a classifier/source snapshot and consumes the fresh model-reference holdout; it never creates independent truth.

## Offline commands

```sh
uv run --frozen python scripts/check_reliability.py --output /private/new-gates.json
uv run --frozen python scripts/corpus_report.py development --records /private/development.jsonl --output /private/new-comparison.json
uv run --frozen python scripts/corpus_diagnostics.py --records /private/development.jsonl --output /private/new-diagnostics.json
uv run --frozen python scripts/corpus_cost_review.py --output /private/new-cost-review.json
```

After a future development batch, refresh the exclusion registry with **all** previously used development sources before generating the fresh holdout. Preserve the prior 200 documents and authored regression sources as well as new development records. The prepared private registry currently contains 272 sources (200 previous development documents plus 72 authored cases). The exclusion utility writes new artifacts and a new bound configuration; it never changes the old proposal in place:

```sh
uv run --frozen python scripts/corpus_partitions.py --records /private/old-development.jsonl /private/new-development.jsonl /private/authored-regressions.jsonl --output /private/new-exclusions.json --config config/model_corpus.holdout.json --bind-config /private/new-holdout-config.json
```

The configuration hash changes, so any earlier spending declaration does not apply to that new configuration. Other development sources used before holdout collection must also enter the registry. This workflow cannot establish that nobody has inspected the holdout outside the tools.

For an authorized interrupted **new-format** job, use the same configuration and authorization with a new private output directory:

```sh
uv run --frozen python scripts/model_corpus.py run --config /private/config.json --authorization /private/authorization.json --env-file .env --resume-from /private/previous-segment --output /private/new-segment
```

A heldout run also needs its `--exclusion-registry /private/exclusions.json`. Resumption remains explicit; once started, accounting validation and continuation are automated. Unknown requests are skipped, never automatically retried. Finished jobs cannot resume. No new spending approval is implied by recovery support.

After classifier choices are frozen, the one-time offline holdout release is:

```sh
uv run --frozen python scripts/corpus_report.py release-holdout --run-dir /private/heldout-final-segment --development-records /private/all-development.jsonl --output /private/holdout-result.json
```

## Next paid proposals — not launched

Both proposals retain the GPT-6.2 Sol generator and three separate GPT-6.1 Terra judge passes, with high reasoning. Repeated passes of Terra do not establish independent errors.

| Proposal | Accepted target | Candidate bound | Empirical cost estimate | Proposed USD cap |
|---|---:|---:|---:|---:|
| Targeted development coverage | 72 (18/quadrant) | 108 | $2.59 | $6 |
| Fresh grouped holdout | 40 (10/quadrant) | 80 | $1.44 | $4 |
| Combined additional work | 112 | 188 | **$4.03** | **$10** |

Estimates scale the previous USD7.19666825 accounted/reserved cost over 200 accepted documents, including excluded candidates and uncertain reserves. A two-times empirical scenario is USD8.06. New prompts, context lengths, validation retries and quota rejection can change cost; neither scenario is a maximum. Unrestricted configured token bounds are substantially higher, so hard caps may leave quadrant or entity shortfalls. See `reports/current/reliability_cost_review.json` for full token ceilings and config hashes. No authorization file was created for either proposal.

[OpenAI's Sol model page](https://developers.openai.com/api/docs/models/gpt-6.2-sol) lists USD2 input / USD10 output per million tokens, and [Terra's model page](https://developers.openai.com/api/docs/models/gpt-6.1-terra) lists USD1 / USD5, checked on 22 November 2026. The configurations retain conservative input ceilings of USD4.5 and USD2.25 to cover ordinary input plus the listed 30-minute cache-write prices; long cache retention is not requested. No live model inventory or inference was requested in this tranche. Pricing and FX assumptions must be fresh before a future launch.

Prior accounted/reserved spending is USD8.11861575 including the earlier smoke run; the proposal rounds that to USD8.20. With a combined additional USD10 cap, a 1.5 SGD/USD ceiling and 20% fee buffer, the combined planning scenario is **S$32.76**, within the user's S$50 allowance. Each proposal also reserves USD18.20 conservatively in its existing SGD gate to earmark prior and other planned work. This planning arithmetic does not authenticate invoices, credits, actual FX/fees or unrelated account spending.

## Verification and measured development agreement

Full suites passed on Python 3.11 and 3.12: **1,703 tests and 254 subtests on each version**. The final offline-report provenance addition passed all five reporting/gate tests separately. Ruff formatting/lint, scoped mypy (ten changed source modules), all nine historical locked-corpus gates, sdist/wheel builds and an isolated wheel import smoke check passed. Exact replay of 1,722 historical documents / 27,034 findings preserved every legacy result field, with zero changed scores/classifications, invalid spans or duplicate findings. The added contextual evidence was also checked against source offsets.

All 72 authored quadrant/entity cases passed, including exact spans and absence of extra entity predictions. These authored cases are regression checks; they are not a fresh independent evaluation corpus.

The existing 200-document **development** comparison reports:

| Contextual target | Positive reference: detected | Missed | Abstained | Negative reference: flagged | No candidate | Abstained |
|---|---:|---:|---:|---:|---:|---:|
| PII | 99 | 1 | 0 | 22 | 34 | 44 |
| MNPI | 28 | 0 | 72 | 0 | 66 | 34 |

Contextual PII matches **329/531 exact** and **340/531 overlap** model-reference spans. The former broad strict crosswalk matched 205/531 exact. This comparison uses an added contextual prediction surface and changed mapping/scope; it does not establish independent accuracy. Pooled precision/F2 remain unavailable because six documents lack unanimous model-declared exhaustive PII coverage. The 106 MNPI abstentions are a substantial remaining limitation; they must not be counted as correct negatives or silently omitted from recall interpretation.

The 40 pre-existing modified-file diffs and 1,079 archived paid-job artifacts were verified unchanged. The README was not edited during this tranche. No key bytes were found in checked new code/artifacts, no new paid authorization was created, and no additional paid calls ran. External dataset measurements were intentionally skipped; hosted CI was not triggered. The broader research mypy check was not rerun, and its previously reported eleven errors outside the scoped modules remain unresolved. Detailed aggregate evidence is in `reports/current/reliability_implementation.json`.
