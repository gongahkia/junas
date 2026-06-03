# SG-LegalBench Task Specifications

One markdown file per task, structured identically so the §3 of the
planned arXiv preprint (#37) can be mechanically derived from this
directory.

Per-spec sections:

1. **Capability** — one of C1–C9 from `docs/coverage-matrix.md` §2.
2. **Literature anchor** — explicit citation to prior work that establishes
   the methodology we adopt.
3. **Input contract** — exact shape of `case.inputs`.
4. **Output contract** — model output format the scorer expects.
5. **Scoring** — which evaluator + `expected_output` shape + the metric
   reported in the leaderboard.
6. **Source provenance** — which adapter, which `extra_schema` fields the
   dataset builder consumes.
7. **Limitations** — explicit, named, falsifiable.
8. **v0.1 / v0.2 stratification** — held-out post-cutoff subset rules.

When the spec changes materially, bump its version line in the front
matter and add a `CHANGELOG` block at the bottom.
