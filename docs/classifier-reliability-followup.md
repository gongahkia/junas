# Classifier reliability follow-up — 23 November 2026

The contextual classifier is now versioned `junas.sensitivity.v3`. Local replays pass all nine unchanged development targets on each of the three datasets below. This work used no paid inference.

| Development measure | Before this follow-up | After |
| --- | --- | --- |
| Retired 40 docs: exact PII spans | 45/71 (63.4%) | 71/71 (100%) |
| Retired 40 docs: PII-positive documents detected | 19/20 | 20/20 |
| Retired 40 docs: MNPI-positive documents detected | 14/20 | 20/20 |
| Retired 40 docs: PII-negative documents flagged | 5/20 | 0/20 |
| Retired 40 docs: PII-negative abstentions | 7/20 | 0/20 |
| Earlier 72 docs: exact PII spans | 122/129 (94.6%) | 122/129 (94.6%) |
| Earlier 72 docs: MNPI-positive documents detected | 36/36 | 36/36 |
| Earlier 200 docs: exact PII spans | 472/531 (88.9%) | 473/531 (89.1%) |
| Earlier 200 docs: MNPI-positive documents detected | 87/100 | 90/100 |

The latest consumed holdout was explicitly retired into development before diagnosis and tuning. Its original references, consumption marker and failed fresh-validation result remain unchanged. The 100% replay result is tuned model-reference agreement, not another unseen validation. The older consumed holdout from the US$10 run remains excluded from this work. Each replay dataset contains all four PII/MNPI quadrants; the earlier 72 and 200 sets have 18 and 50 documents per quadrant.

PII changes ground person roles and parenthetical records, distinguish shared role mailboxes and corporate accounts, parse partial birth dates, and link multi-part personal emails and combined personal attributes within bounded paragraphs. MNPI changes link shortened issuer names to an unambiguous qualified company, distinguish counterparties from subjects, recognize actual recall decisions, and connect explicitly referenced materiality evidence across adjacent paragraphs. Ambiguous issuers, hypothetical events, conflicting public/private claims and unrelated contexts retain negative or abstaining behavior. Added regressions exercise these boundaries with varied names, source offsets and line endings.

The retirement tool refuses unconsumed or modified references and exports private development copies without changing their labels. Future holdout exclusions now include the new identity regressions. Broad findings, scores and risk classifications retain their previous behavior in the historical replay.

Verification results are recorded in [the machine-readable report](../reports/current/classifier_reliability_followup.json). Python 3.11 and 3.12 each pass 1,802 tests plus 254 subtests. Ruff lint/format passes on all ten changed Python files; scoped mypy passes on six sources, with an unused-configuration note for `junas.cli`. The authored gate passes 72 cases covering all quadrants and nine entity types; all nine locked corpus gates pass. A network-disabled replay of 1,722 documents and 27,034 findings finds no changed legacy result, invalid span or duplicate finding. The sdist/wheel build and an isolated offline installation passes four classifier cases and CLI execution, with the installed runtime hash matching the source. Initial full-suite attempts failed while writing to the quota-limited `/tmp`; both complete reruns passed using private temporary directories on the workspace disk. Full-project mypy and external corpus acquisition were not run.

Remaining limitations are measurable: the 200-document set still has 58 unmatched exact reference PII spans, one missed PII-positive document and ten positive MNPI abstentions; the 72-document set has seven unmatched exact spans. Exact unmatched predictions on declared exhaustive units remain 11 and four respectively. Some reference coverage is unknown, so pooled PII precision/F2 is unavailable. Quasi-identifiers remain weak on earlier sets, the 200-document set has no bank-account examples, model judges can share errors, and confidence/legal materiality/public status remain unverified. Passing these development targets does not establish independent accuracy.

For another fresh 40-document run, the proposed generator remains GPT-6.2 Sol with three separate GPT-6.1 Terra judge passes, using high reasoning and two-of-three consensus. These are repeated samples from one judge model. The last comparable run accounted for US$2.73792225 including retained uncertain-request reserves. A 25% planning buffer gives US$3.4224, rounded up to **US$3.45 estimated**, with a proposed **US$4 maximum cap** and automatic stopping, possibly before 40 accepted documents. This is a cost proposal only: no new run bundle, spending authorization or paid run has been created.

Pricing was checked on 23 November 2026: standard input/output rates per million tokens are [US$2/US$10 for GPT-6.2 Sol](https://developers.openai.com/api/docs/models/gpt-6.2-sol) and [US$1/US$5 for GPT-6.1 Terra](https://developers.openai.com/api/docs/models/gpt-6.1-terra). Existing accounting uses conservative input ceilings of US$4.50 and US$2.25, including 30-minute cache-write charges, with no cache discount assumed. The estimate is empirical, not a completion or invoice guarantee. Before generation, a new bundle must freeze v3, reserve new scenario families, exclude all earlier candidates and authored regressions, and bind the approved budget to those artifacts.

Cumulative previous accounted/reserved usage is US$15.43956250. Rounding that to US$16, adding the proposed US$4 cap, and applying a planning rate of S$1.50/US$ plus 20% contingency gives S$36. This is a budget scenario, not a current exchange-rate quote or verified provider invoice; account balance and applicable credits were not rechecked.

All 6,766 initial repository files were checked for unexpected changes; the earlier uncommitted patch and README remain unchanged. The three paid-run archives retain all 1,079, 971 and 851 recorded file hashes. Validation applies to the current workspace, including its pre-existing uncommitted text-only changes. Private raw references and replay evidence remain outside Git.

Implementation HEAD: `f5d5c7a3`. Runtime SHA-256: `7ec08c5a4570c1868f51b53b4741ee2312e1a3379b75b1e47e0d081b21d6df3f`.
