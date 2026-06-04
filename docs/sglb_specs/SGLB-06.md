# SGLB-06 Rules-of-Court-2021

Version: 0.1-code-shipped (data pending live `make ingest-sso SSO_CODE=ROC2021`). Tracking issue: [#33](https://github.com/gongahkia/junas/issues/33).

## Capability

**C5 — Issue spotting (procedural).** Given a procedural scenario,
identify the applicable Order and Rule under the Rules of Court 2021.

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `rule_application` family.
- The Rules of Court 2021 (S 914/2021) themselves are the authority for
  the trigger taxonomy.

## Input contract

```python
case.inputs = {
  "scenario": str,   # 50–200-token procedural scenario
}
```

## Output contract

Model output is a JSON list of `O. <N>, r. <M>` references, ordered by
the model's confidence (most-applicable first):

```json
["O. 9, r. 1"]
```

## Scoring

- `order_rule_label_f1` — multi-label F1 over normalised
  `O. <N>, r. <M>` labels. Primary metric.
- `order_rule_top3` — fraction of gold labels appearing in the model's
  first 3 emitted labels.

Both evaluators normalise common surface variants (`Order 9, Rule 1`,
`O 9 r 1`, `O.9, r.1`) to the canonical form before comparison.

## Source provenance

- Adapter: `api.adapters.public.sso.SsoAdapter`.
- Ingestion: `data.ingestion.sso` with `SSO_CODE=ROC2021`. ROC 2021
  appears in `ACT_CODES` as `("ROC2021", "sl", "/SL-Supp/S914-2021/Published?DocDate=20211201&WholeDoc=1")`.
- Dataset builder: `benchmark.dataset_builders.sglb_06`.
  - Filters: drop `[Repealed]`, drop `len(scenario) < 100`, drop Rules
    without a parsed `Order N` in the `part` heading.
  - Scenario = the Rule's own scope/heading text (first paragraph after
    the leading rule number), truncated at a sentence boundary ≤600 chars.
  - Gold label = `O. <order>, r. <rule>` derived from the SSO `part`
    header (e.g. `"Order 9 PRE-ACTION PROTOCOLS"`) and the section
    number.

## Limitations

- **Data pending live ingest.** v0.1 ships builder + scorers + runner +
  prompt; the case data lands once `make ingest-sso SSO_CODE=ROC2021`
  populates the SSO JSONL with ROC 2021 sections (~150 Rules).
- **Single-label per Rule by default.** Multi-Rule scenarios are
  possible via the F1 metric but not yet generated; the v0.1 builder
  emits one gold label per case (each Rule is its own case).
- **Some Rules cross-reference other Orders.** Mechanical extraction
  yields the home-Order label only; cross-rule reasoning is out of scope.
- **ROC 2021 has 32 Orders;** rare Orders may be under-represented.
  Stratification (≥3 cases per Order) is enforced only after live
  ingest materialises the corpus.

## v0.1 / v0.2 stratification

- v0.1 (data pending): ~150 scenarios, one per Rule, ≥3 per Order on
  rebuild.
- v0.2 held-out: ~30 scenarios from Rules amended post-2026-Q1.
- Per-Order leaderboard breakdown.

## CHANGELOG

- 0.1-code-shipped (2026-06-04): builder, oracle runner, LLM prompt
  builder, `order_rule_label_f1` + `order_rule_top3` scorers, spec.
  Data lands on next `make ingest-sso SSO_CODE=ROC2021 && make build-sglb-06`.
