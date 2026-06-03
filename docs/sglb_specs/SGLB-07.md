# SGLB-07 Jurisdiction-Routing

Version: 0.1-draft. Tracking issue: [#33](https://github.com/gongahkia/junas/issues/33), [#34](https://github.com/gongahkia/junas/issues/34).

## Capability

**C2 — Case-law retrieval / jurisdiction reasoning.** Given an SG legal
question, classify the source-jurisdiction of the controlling authority.

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `function_of_decision`
  family.
- Common-law commentary on the SG courts' use of persuasive UK / AU /
  HK authority is the substantive background; we test the model's
  ability to predict the published court statement, not to opine on it.

## Input contract

```python
case.inputs = {
  "question": str,   # 50–200-token legal question
}
```

## Output contract

Model output is a single-element JSON list with one of:

```json
["sg_binding"]
["uk_persuasive"]
["au_persuasive"]
["hk_persuasive"]
["not_applicable"]
```

## Scoring

- `multi_label_f1` over the single-element labels list (overall accuracy
  in practice).
- Leaderboard reports per-class P/R.

## Source provenance

- Adapter: `api.adapters.public.elitigation.ElitigationAdapter`
  (TOS-gated; fallback to `CommonliiSgAdapter`).
- Required `extra_schema` fields: `citation`, `body`, `decision_date`.
- Dataset construction: SG judgments where the court explicitly states
  the persuasive source ("applying the principle in *Donoghue v
  Stevenson* [1932] AC 562, this court holds…"). The judgment's own
  statement is the gold label. Mechanical extraction.

## Limitations

- Excludes cases without an explicit source-jurisdiction statement
  (where the court applies a principle without naming its provenance).
- Persuasive-vs-binding is sometimes contested in the literature; we
  test the published-court framing, not the academic one.
- Multi-source cases (UK + AU cited together) are excluded from v0.1.

## v0.1 / v0.2 stratification

- v0.1: ~200 cases.
- v0.2 held-out: ~50 cases from post-2026-Q1 judgments.
- Per-source-jurisdiction leaderboard breakdown.
