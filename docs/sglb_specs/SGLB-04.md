# SGLB-04 Citation-Verify

Version: 0.1-shipped (smoke). Tracking issue: [#29](https://github.com/gongahkia/junas/issues/29), [#32](https://github.com/gongahkia/junas/issues/32).

## Capability

**C3 — Citation handling.** Given a candidate SG legal citation,
determine whether it conforms to the SAL Style Guide grammar.

## Literature anchor

- The SAL Style Guide grammar itself (Quick Reference 2007 +
  SLR Style Guide 2021) is the authority.
- Guha et al., **LegalBench** (NeurIPS 2023), `citation_extraction`
  family — but our evaluator is deterministic, not LLM-judge.

## Input contract

```python
case.inputs = {
  "citation": str,   # candidate citation, e.g. "[2023] SGCA 5"
}
```

## Output contract

Model output is a single-element JSON list containing `"valid"` or
`"invalid"`:

```json
["valid"]
```

## Scoring

- `multi_label_f1` over the single-element labels list with
  `expected_output["labels"]` set to `["valid"]` or `["invalid"]`.
- Strict mode (`--strict`) required for publication runs.

## Source provenance

- No external adapter needed. Dataset constructed mechanically from the
  SAL grammar implementation in `api.services.sal_citation`.
- Perturbation taxonomy aligns with SGLB-11:
  - `year_off`, `volume_off`, `page_off`, `case_name_swap`, `court_swap`,
    `wholesale_fabrication`, `composite`.

## Limitations

- Grammar conformance ≠ existence. A perfectly-formed `[2026] SGCA 999`
  passes SGLB-04 but may not be a real case. SGLB-11 covers existence.
- The grammar reflects the 2007 + 2021 guides; pre-2007 citation forms
  may legitimately fail and are excluded from the dataset.
- The current dataset (`benchmark/datasets/sglb_04_citation_verify.yaml`)
  is a 30-case smoke set; a 1000+ case production dataset lands in #32.

## v0.1 / v0.2 stratification

- v0.1 smoke: 30 cases, stratified across kinds + perturbation classes.
- v0.2 production: ~1000 cases with per-perturbation-class breakdown
  in the leaderboard.

## CHANGELOG

- 0.1-shipped (smoke, 2026-06-03): registered as `sglb_04` workflow,
  scorer wraps `validate_citation`, integration tests landed.
