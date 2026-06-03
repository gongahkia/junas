# Synthetic SGLB Generation

This package generates synthetic candidates only for SGLB-08, SGLB-12, and
SGLB-15. Other SGLB tasks depend on real regulator or court outputs and must
not use this pipeline.

## Pipeline

1. Plan a deterministic taxonomy matrix:

```sh
python -m benchmark.synthetic plan --task sglb_08 --n 20 --dry-run
```

2. Generate candidates with a rotating provider set. The mock provider is used
in tests and does not call any external API:

```sh
python -m benchmark.synthetic generate --task sglb_08 --n 2 --providers mock --no-review-gate
```

The label comes directly from the taxonomy cell embedded in the generation
prompt. There is no LLM autolabel step.

3. Record human review:

```sh
python -m benchmark.synthetic review --fixture <slug> --decision approve --reviewer <name>
```

Valid decisions are `approve`, `reject`, and `needs_edit`. Candidates remain in
`*_candidates/` until explicitly approved.

4. Promote approved candidates:

```sh
python -m benchmark.synthetic promote --task sglb_08
```

Promotion moves approved YAML files into the task's `*_reviewed/` directory,
writes `promotion_audit.jsonl`, and refreshes `dataset.yaml` for the benchmark
harness. The harness should evaluate reviewed datasets only.

## Cost Controls

Use `--dry-run` to print the matrix and estimated cost without creating LLM
clients. Use `--max-cost-usd` to abort before generation when the estimated
cost exceeds the cap:

```sh
python -m benchmark.synthetic generate --task sglb_12 --n 100 \
  --providers anthropic,openai,google --max-cost-usd 5
```

All randomness goes through one `random.Random(seed)` in the planner, so the
same `(task, n, providers, seed, generator_version, prompt_version)` yields the
same matrix and candidate metadata.
