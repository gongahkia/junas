# Synthetic Generation For SGLB-08/12/15

## Summary

- Adds the `benchmark.synthetic` pipeline for SGLB-08 Clause-Tone, SGLB-12
  Multi-Issue-Spotting, and SGLB-15 Draft-Constraint-Sat only.
- Keeps labels fixed by generation parameters: tone labels, issue
  compositions, and constraint sets are copied directly into `expected_output`;
  no second LLM autolabel step is used.
- Adds provider rotation, dry-run planning, cost caps, candidate review state,
  promotion audit logs, reviewed-only task wrappers, and `data_tier="synthetic"`
  receipts.
- Adds explicit taxonomy artifacts:
  `sglb_08_tones.yaml`, `sglb_12_taxonomy.yaml`,
  `sglb_12_compositions.yaml`, and `sglb_15_constraints.yaml`.

## Documentation Updates

- `docs/sglb_specs/SGLB-08.md` is bumped to `0.1-synthesis-ready`.
- `docs/sglb_specs/SGLB-12.md` is bumped to `0.1-synthesis-ready`.
- `docs/sglb_specs/SGLB-15.md` is bumped to `0.1-synthesis-ready`.

## Verification

- `pytest backend/tests/test_synthetic_generation.py -q`
- `pytest tests/test_benchmark_harness.py tests/test_benchmarks_router.py -q`
- `ruff check benchmark/synthetic benchmark/tasks/sglb_08.py benchmark/tasks/sglb_12.py benchmark/tasks/sglb_15.py tests/test_synthetic_generation.py`
- CLI dry-run and mock generate/review/promote smoke checks only; no real LLM
  calls.
