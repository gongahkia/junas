# MNPI reliability v6 — local diagnosis and repair

23 November 2026. The latest consumed 40-document cohort was exported to private development data with its source/consumption hashes and references unchanged. The [original failed fresh-holdout result](fresh-holdout-v5-results.md) remains intact. **This is exposed development replay after tuning, not new unseen validation. No paid API calls were made.** [Machine-readable evidence](../reports/current/mnpi_reliability_v6.json).

## Diagnosis and changes

The original v5 classifier abstained on 17 of 20 MNPI-positive references. Source-linked diagnostics emitted ten missing-event codes, five missing-materiality codes and six unlinked-disclosure codes across those cases; these counts overlap. The main problems were incomplete event vocabulary, a reliance on literal significance words and short disclosure references that failed to inherit their event context.

V6 adds recognition and bounded evidence links for dividend deferrals, clinical-trial readouts, impairment estimates and coupon changes. It recognises asserted financial consequences such as a forecast profit turning into a loss, dividend yield relative to a traded price, pivotal trial context and quantified coupon changes. A comparable-currency annual-interest/profit check uses a 10% engineering heuristic. These signals suggest potential significance; they are not universal legal thresholds, calibrated confidence or verified materiality. Public status remains a text claim with `public_status_verified: false`.

The issuer linker now handles unique short possessive references and listing prefixes, preserves Unicode name prefixes and distinguishes financial-period tags from company-name continuations. Explicit financial ownership can identify the issuer affected by a contract rather than the counterparty sending a notice; multiple conflicting financial owners abstain. Notice co-references retain their contract-impact topic when an impairment estimate is mentioned alongside them.

New controls cover public announcements, contradictory disclosure claims, normative policies, negated events, hypothetical financial magnitudes, tiny or cross-currency cost comparisons, ambiguous issuers and unrelated topics. Disclosure references alone no longer manufacture an event, and a financial consequence is not automatically treated as the event itself. Early controls caught four unsafe promotions, and per-document comparisons caught two older detections lost during implementation; these were corrected before final verification.

## Development results

| Source | MNPI-positive detections, v5 → v6 | V6 positive abstentions | V6 negative flags / abstentions |
|---|---:|---:|---:|
| Latest retired 40 | 3/20 → 20/20 | 0 | 0/20 / 0/20 |
| Earlier retired 40 | 20/20 → 20/20 | 0 | 0/20 / 0/20 |
| First retired 40 | 20/20 → 20/20 | 0 | 0/20 / 0/20 |
| Original development 72 | 36/36 → 36/36 | 0 | 0/36 / 0/36 |
| Original development 200 | 90/100 → 94/100 | 6 | 0/100 / 0/100 |

Across these 392 development documents, 21 positive references moved from abstention to detection. No previously detected positive was lost. None of the 196 reference-negative documents was flagged; the one previous negative abstention also cleared. These are descriptive model-reference agreements across exposed sources, not independent accuracy or an estimate for real-world prevalence.

Within the latest cohort, dividend deferrals improved from 0/7 to 7/7, trial readouts 0/2 to 2/2, impairments 0/3 to 3/3 and sustainability/financing cases 3/8 to 8/8. Evidence components retain exact source offsets. All four MNPI engineering targets pass locally.

All PII span, document and unmapped-rule measurements match v5 on all five replay cohorts. The latest cohort now passes **8/9 overall targets**: PII overlap remains **72/85 (84.71%)**, below its unchanged 85% minimum. Its exact PII match count remains 71/85. This task does not resolve that separate PII gap or alter the reference spans.

## Verification and limits

- Python 3.12.16 and 3.11.18: **1,925 tests and 254 subtests passed on each**, no failures or skips in the final suites.
- Full-project mypy: 108 source/evaluation files pass, with the existing unused `junas.cli` configuration note.
- Ruff lint/format: all eight changed Python files pass; `git diff --check` passes.
- All nine unchanged locked corpus gates pass across 1,722 documents. Label provenance and promoted-lock freshness checks pass.
- Source distribution and wheel builds pass; a locked, isolated wheel installation passes seven sensitivity/CLI checks with network connections denied and its runtime hash matches the replayed source.
- Five development replays and per-document frozen-v5 comparisons denied network connections. They check preserved PII results and individual MNPI state changes rather than relying on aggregate improvements alone.
- All 4,881 recorded artifact hashes across eight earlier archives match. Original holdout sources, references, failed results, thresholds and root README are unchanged. The earlier USD10 protected holdout was not used for development evaluation.

An initial test command imported the previous clean clone; it was replaced with dedicated locked environments whose imports point at the working checkout. Initial failing controls and intermediate regression results were used to correct the implementation, not reported as final success. Full suites were repeated after those corrections. Hosted CI and external PII benchmarks were not rerun; the reliability CI job now includes the added financial-event and scope controls. Optional NER and live advisory usefulness were not exercised.

Six older positive references still abstain: diagnostics identify remaining issuer links, event wording, disclosure references and materiality phrasing. Those cases were not forced positive. Passing authored variations and replaying exposed sources cannot establish generalization; **a new frozen, unseen holdout is still needed**, with a cost proposal and approval before any paid calls. Model-reference confidence remains uncalibrated.

Private diagnostics, the original v5 source snapshot, development export, per-document comparisons and verification logs are in `/home/gongahkia/.local/share/junas/research/2026-11-23-mnpi-reliability-v6`. Classifier runtime version: `junas.sensitivity.v6`; SHA-256: `63ad99341c01445f684554e25e823e195c54f8b5c0a0a040ac7814137b1a18c5`.
