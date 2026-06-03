# SGLB-05 Employment-Issue

Version: 0.1-draft. Tracking issue: [#33](https://github.com/gongahkia/junas/issues/33), [#59](https://github.com/gongahkia/junas/issues/59).

## Capability

**C5 — Issue spotting.** Multi-label identification of which Employment
Act / MOM-regulated issues a scenario triggers.

## Literature anchor

- Guha et al., **LegalBench** (NeurIPS 2023), `learned_hands_*` family
  — multi-label legal issue classification.
- Chalkidis et al., **LexGLUE** (ACL 2022), ECtHR Task A multi-label
  scoring protocol.

## Input contract

```python
case.inputs = {
  "scenario": str,   # 100–300-token fact pattern about an employer/employee dispute
}
```

## Output contract

Model output is a JSON list of issue labels:

```json
["notice_period_breach", "cpf_non_contribution"]
```

## Scoring

- `multi_label_f1` with `expected_output["labels"]` drawn from the
  MOM-issue taxonomy.
- Leaderboard reports macro-F1, micro-F1, per-class P/R.

## Source provenance

- Adapter: `api.adapters.public.mom.MomAdapter` (issue #59).
- Required `extra_schema` fields: `subsource` (press_release / faq /
  advisory), `act_references`, `stated_breaches`, `subject_organisation`.
- Dataset builder uses MOM's own published categorisation as the issue
  taxonomy and the regulator-stated `stated_breaches` as the gold
  labels — mechanical extraction; no author judgment.

## Limitations

- The label set is constrained to MOM-published categories. Issues
  outside that taxonomy (e.g. industry-specific obligations) are not
  in scope.
- Press-release scenarios are often summarised; the publicly available
  narrative may not capture every issue that arose.
- Confidence calibration is not measured; only label presence.

## v0.1 / v0.2 stratification

- v0.1: ~120 scenarios from pre-2026-Q1 MOM press releases + FAQs.
- v0.2 held-out: ~30 scenarios from post-2026-Q1.
- Leaderboard reports per-issue precision/recall to surface rare-class
  performance.
