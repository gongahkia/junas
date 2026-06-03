# SGLB-10 Citation-Generation

Version: 0.1-draft. Tracking issue: [#51](https://github.com/gongahkia/junas/issues/51).

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
  "fact_pattern": str,   # 200–400-token SG fact pattern
  "domain": str,         # contract | tort | equity | statutory | procedure
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
- **Citation grammar validity:** delegated to SGLB-04 scorer
  (`validate_citation`). Models that emit invalid grammar are
  penalised on grammar-validity even if the case is real.
- Leaderboard reports per-domain breakdown.

## Source provenance

- Adapter: `ElitigationAdapter` (TOS-gated; #34).
- Required `extra_schema` fields: `citation`, `body`, `categories`.
- Dataset construction: judgments where the court explicitly identifies
  the controlling authority ("this question is governed by *X v Y*
  [YYYY] SGCA NN at [m]"). Mechanical regex extraction; 10% hand-audit.

## Limitations

- A fact pattern may have a citation set rather than a single citation;
  the scorer accepts any member of the set in top-1.
- Models that pattern-match common cases (e.g. *Gay Choon Ing v Loh Sze
  Ti Terence Peter*) for every contract question would inflate scores;
  per-domain breakdown surfaces this.
- Overruled / disapproved authorities are flagged in metadata; we
  accept "current good law" only.

## v0.1 / v0.2 stratification

- v0.1: ~250 fact patterns.
- v0.2 held-out: ~50 patterns from post-2026-Q1 judgments.
- Per-domain leaderboard breakdown.
