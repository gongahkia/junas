# SGLB-14 Statutory-Entailment

Version: 0.1-draft. Tracking issue: [#55](https://github.com/gongahkia/junas/issues/55), [#60](https://github.com/gongahkia/junas/issues/60).

## Capability

**C1 — Statute QA (entailment).** Given a scenario and a named SG
statute clause, classify the entailment relation.

## Literature anchor

- Holzenberger et al., **SARA** (2020,
  [arXiv:2005.05257](https://arxiv.org/abs/2005.05257)) —
  entailment-prompt format for statutory reasoning.
- Bowman et al., **SNLI** (EMNLP 2015) — 3-class entailment baseline.
- Guha et al., **LegalBench** (NeurIPS 2023), `hearsay` and
  `contract_nli` task families.

## Input contract

```python
case.inputs = {
  "scenario_text": str,         # 50–200-token fact pattern
  "statute_clause_id": str,     # e.g. "PDPA s.24"
  "statute_clause_text": str,   # full clause text
}
```

## Output contract

Model output is a single-element JSON list with one of:

```json
["entails"]
["contradicts"]
["neutral"]
```

## Scoring

- `multi_label_f1` (single-element; equivalent to 3-class accuracy).
- Confusion matrix in the leaderboard.

## Source provenance

- Adapter: `PdpcGuidanceAdapter` (PDPC Advisory Guidelines, #60),
  `MomAdapter` (MOM Employment Act FAQs).
- Required `extra_schema` fields:
  `extracted_worked_examples`/`stated_breaches`.
- **The credibility move:** entailment labels are extracted *mechanically*
  from regulator-published worked examples ("In this scenario, the
  organisation would be in breach of section X"). The regulator states
  the entailment; we just reformat.
- `neutral` examples are constructed by pairing a scenario with a
  clause from a *different* Act — guaranteed neutral by construction.

## Limitations

- Regulator worked examples carry implicit normative judgments. We
  document this and let users discount the task if they reject the
  regulator's framing.
- "Neutral" cross-act pairs may be too easy (textual surface
  dissimilarity); we include challenging neutrals (same-act
  different-section pairings).
- We run a statute-placeholder ablation (replace section numbers with
  generic tokens) to surface whether models pattern-match on numbers.

## v0.1 / v0.2 stratification

- v0.1: ~200 items, balanced across 3 classes.
- v0.2 held-out: ~50 items from post-2026-Q1 PDPC Advisory Guideline
  revisions.
- Statute-placeholder ablation delta reported in the leaderboard.
