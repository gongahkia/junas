# SGLB-10 Citation-Generation

Version: 0.1-smoke. Tracking issue: [#51](https://github.com/gongahkia/junas/issues/51).

## Capability

**C3 — Citation handling (generation).** Given an SG fact pattern,
predict the controlling SG authority (a case citation).

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `rule_qa` family.
- Dahl et al., **Large Legal Fictions** (J. Legal Analysis 2024,
  [arXiv:2401.01301](https://arxiv.org/abs/2401.01301)) — establishes
  the empirical baseline (58–88% hallucination on US random federal
  cases).

## Input contract

```python
case.inputs = {
  "fact_pattern": str,   # SG legal scenario
}
```

## Output contract

Model output is a JSON list of up to 3 SG citation strings, ordered
by the model's confidence:

```json
["[2009] 2 SLR(R) 332", "[2007] 4 SLR(R) 413", "[2014] 4 SLR 412"]
```

## Scoring

- **Top-1 hit rate:** gold citation appears in position 1.
- **Top-3 hit rate:** gold citation appears in positions 1–3.
- Evaluator names: `citation_generation_top1`, `citation_generation_top3`.
- **Citation grammar validity:** delegated to SGLB-04 scorer
  (`validate_citation`). Models that emit invalid grammar are
  penalised on grammar-validity even if the case is real.
- Leaderboard reports per-domain breakdown.

## Source provenance

- v0.1 smoke source: `backend/benchmark/datasets/sglb_11_real_pool.yaml`,
  the existing curated SG real-citation pool used for SGLB-11.
- Dataset construction: deterministic domain round-robin over named cases
  in that pool. The gold label is copied mechanically from the curated
  citation field. Fact patterns are synthetic lookup prompts keyed to the
  case name and domain.
- Provenance fields: `source_pool`, `source_pool_sha`, `domain`,
  `case_name`, `label_provenance`.
- Production target: CommonLII SG / eLitigation public corpus rows with
  headnotes or catchwords mapped mechanically to citation labels. That
  corpus is not present in this repo state.

## Limitations

- The shipped v0.1 smoke is `data_tier=synthetic` and benchmark-ineligible.
  It validates task/evaluator/harness wiring, not substantive legal
  retrieval.
- A production fact pattern may have a citation set rather than a single citation;
  the scorer accepts any member of the set in top-1.
- Models that pattern-match common cases (e.g. *Gay Choon Ing v Loh Sze
  Ti Terence Peter*) for every contract question would inflate scores;
  per-domain breakdown surfaces this.
- Overruled / disapproved authorities are flagged in metadata; we
  accept "current good law" only.

## v0.1 / v0.2 stratification

- v0.1: 40 synthetic smoke fact patterns.
- v0.2: CommonLII/eLitigation-derived fact patterns with post-2026-Q1
  held-out judgments.
- Per-domain leaderboard breakdown.

## Synthetic v0.1 prompt template

The builder uses the following deterministic template family:

```text
A <domain> dispute asks for the Singapore authority on <domain-specific
issue> involving the parties named in <case name>. Return the most
relevant Singapore case citation.
```

This keeps the case-to-citation mapping mechanical while the real
headnote-derived dataset is unavailable.
