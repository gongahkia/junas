# SGLB-06 Rules-of-Court-2021

Version: 0.1-draft. Tracking issue: [#33](https://github.com/gongahkia/junas/issues/33).

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

Model output is a JSON list of `"O.<n>, r.<m>"` references:

```json
["O. 9, r. 1"]
```

## Scoring

- `multi_label_f1` where each label is a normalised `"O. N, r. M"` string.
- Leaderboard also reports top-3 accuracy: the gold rule appears in the
  model's first 3 emitted labels.

## Source provenance

- Adapter: `api.adapters.public.sso.SsoAdapter`.
- Required `extra_schema` fields: `unique_id`, `legis_title` (must be
  "Rules of Court 2021"), `fragments_content` (decoded), `data_json`.
- Scenario construction: from the Rule's own scope text (each Rule of
  ROC 2021 carries a "Scope of this Order" preamble), draft a scenario
  that should match. Mechanical: scope-text → scenario template fill.

## Limitations

- ROC 2021 has 32 Orders; rare Orders may be under-represented. Stratify
  the dataset to require at least 3 cases per Order.
- Some scenarios trigger multiple Rules; the F1 metric handles that
  naturally.
- Excluded: Rules whose scope text refers to other Orders (cross-rule
  reasoning is its own task in a future version).

## v0.1 / v0.2 stratification

- v0.1: ~180 scenarios, ≥3 per Order.
- v0.2 held-out: ~30 scenarios from Rules amended post-2026-Q1.
- Per-Order leaderboard breakdown.
