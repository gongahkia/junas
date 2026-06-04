# SGLB-02 Statute-QA

Version: 0.1-shipped (PDPA seed). Tracking issue: [#28](https://github.com/gongahkia/junas/issues/28), [#32](https://github.com/gongahkia/junas/issues/32).

## Capability

**C1 — Statute QA.** Given a question grounded in a specific SG statute
section, return the answer and the correct citation.

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `rule_qa` and
  `definition_extraction` task families.
- Holzenberger et al., **SARA: A Dataset for Statutory Reasoning in Tax
  Law** (2020, [arXiv:2005.05257](https://arxiv.org/abs/2005.05257)).

## Input contract

```python
case.inputs = {
  "question": str,           # natural-language question
  "act_short_name": str,     # e.g. "PDPA"
  "act_full_name": str,      # e.g. "Personal Data Protection Act 2012"
}
```

## Output contract

Model output is a JSON object:

```json
{
  "citation": "s 13 of the Personal Data Protection Act 2012",
  "answer": "free-form answer, ≤ 200 words"
}
```

## Scoring

- **Citation:** `sglb_02_citation_match` — exact match after canonical
  normalisation (`s <N>` form; case-insensitive; collapses whitespace
  and trailing punctuation). Primary metric.
- **Answer:** `rouge_l_answer` — sentence-level ROUGE-L F1 over
  whitespace-tokenised English (LCS-based) against the gold span. Coarse
  proxy; report alongside citation accuracy.

Leaderboard reports both metrics separately; no composite score.

## Source provenance

- Adapter: `api.adapters.public.sso.SsoAdapter`.
- Ingestion: `data.ingestion.sso` (port of `kevanwee/sgstatutescraper`,
  rate-limited 3s, retry + version-pinning); seed acts `PDPA2012`,
  `EmA1968`, `PC1871`, `ROC2021`.
- Dataset builder: `benchmark.dataset_builders.sglb_02`.
  - Filters: drop `[Repealed]`, drop `len(text) < 120`, drop boilerplate
    headings (`Interpretation`, `Definitions`, `Short title`,
    `Citation`, `Commencement`, `Application`).
  - Question template (mechanical, disclosed):
    `Under the {short_name}, what does the section on "{heading}" provide?`
  - Citation gold: `s <N> of the <full act title>`.
  - Answer gold: first paragraph of `text_plain` after stripping the
    leading section number; truncated at a sentence boundary ≤600 chars.

## Limitations

- **PDPA-only seed for v0.1.** The v0.1 dataset (~78 cases) is built
  from the PDPA 2012 fixture. EmA / PC / ROC2021 expansion requires live
  `make ingest-sso` against AGC; deferred until network budget allocated.
- **Mechanical question generation.** All questions follow one template.
  This is a deliberate methodology choice (reproducibility > realism); a
  10% spot-check by hand on the gold cases is the planned validation.
- **Answer is necessarily abstractive on the gold side too.** ROUGE-L is
  a coarse proxy for "answers the question correctly". Pair with the
  citation scorer (which is deterministic).
- **Statute revisions are versioned.** Each case pins to a specific
  `version_id` (e.g. `PDPA2012@2020`) so the gold answer is reproducible.
- **No cross-statute reasoning.** Items requiring synthesis across two
  statutes are out of scope; SGLB-12 covers multi-issue spotting.

## v0.1 / v0.2 stratification

Splits assigned deterministically by case-index modulo 10 (80/10/10) for
the PDPA-only seed:

- `train` ~64 cases, `dev` ~7, `test` ~7.

When live `make ingest-sso` materialises EmA/PC/ROC2021 sections, the
builder rebuilds and the splits expand toward the original target
(~500 cases). v0.2 held-out: ~80 sections from post-2026-Q1 statute
amendments. Leaderboard reports per-statute breakdowns to surface domain
skew.

## CHANGELOG

- 0.1-shipped (2026-06-04): SSO ingestion landed (#28); dataset builder
  + oracle runner + LLM prompt builder + citation/ROUGE-L scorers
  registered; PDPA-only seed materialised (78 cases, oracle 1.0/1.0).
