# SGLB-15 Draft-Constraint-Sat

Version: 0.1-synthesis-ready. Tracking issue: [#56](https://github.com/gongahkia/junas/issues/56).

## Capability

**C6 — Drafting under constraints.** Given an SG drafting brief and a
list of verifiable hard constraints, score whether the model's drafted
document satisfies each constraint.

## Literature anchor

- Zhou et al., **IFEval** (2023, [arXiv:2311.07911](https://arxiv.org/abs/2311.07911))
  — verifiable instruction-following methodology. 25 constraint
  templates, all checked by short Python functions.

## Input contract

```python
case.inputs = {
  "drafting_brief": str,
  "constraints": list[dict],   # each: {id, kind, params}
}
```

`kind` ∈ {`named_party_present`, `governing_law_singapore`,
`citation_format_valid`, `required_section_present`, `min_word_count`,
`iso_date_present`, `sgd_amount_present`, `no_forbidden_phrase`}.

## Output contract

Model output is the drafted document as Markdown.

## Scoring

- `constraint_sat` evaluator: runs each constraint function against the
  drafted output; reports per-constraint pass/fail.
- **All-pass rate:** fraction of cases where *every* constraint passes
  (strict).
- **Constraint-pass rate:** mean fraction of constraints passed per
  case (lenient).
- Per-constraint-kind breakdown in the leaderboard.
- **No LLM-judge in the scoring pipeline.** Every constraint is a
  Python function (`benchmark.constraints.CONSTRAINTS`). Audit point.

## Source provenance

- Template inputs from `backend/api/services/template_service.py` (the
  SG-applicable templates: NDA, employment, MOU, tenancy, board
  resolution, share transfer).
- Brief generation is programmatic: randomised party names, dates,
  durations, currency amounts.
- Constraint generation is programmatic: each brief samples 3–6
  constraints from the taxonomy.
- Synthetic-tier scaffolding stores constraint-set applicability at
  `backend/benchmark/synthetic/sglb_15_constraints.yaml`. This gates which
  constraint payloads can be paired with each SG template type.

## Limitations

- Constraints capture verifiable structural properties, not drafting
  quality. Documented explicitly.
- Models that game by stuffing required keywords without coherent
  drafting will score well on constraints; we say so.
- Refusal rate (models that refuse to draft) is reported separately,
  not collapsed into the headline metric.

## v0.1 / v0.2 stratification

- v0.1: ~200 briefs × ~5 constraints each.
- v0.2 held-out: ~50 briefs built from new template variations.
- Per-template-type and per-constraint-kind breakdown.

## Synthesis pipeline

SGLB-15 may use `benchmark.synthetic` because every hard constraint is fixed by
the generation instruction and scored by Python functions. Candidates must be
human-reviewed before promotion and are reported under the `synthetic` tier.

The synthetic planner reads `backend/benchmark/synthetic/sglb_15_constraints.yaml`
to pair template IDs with applicable constraint sets. Validation rejects
candidate fixtures whose input constraints diverge from expected constraints,
whose constraint set is stale or unknown, or whose template/set pairing is not
declared in that taxonomy.
