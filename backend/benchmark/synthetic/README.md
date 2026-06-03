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

3. Inspect and validate candidates before review:

```sh
python -m benchmark.synthetic status --task sglb_08
python -m benchmark.synthetic show --task sglb_08 --fixture <slug>
python -m benchmark.synthetic validate --task sglb_08
```

`status` reports pending/approved/rejected/needs_edit counts, `show` prints the
body, label, and audit metadata for one fixture, and `validate` checks schema,
required audit metadata, reviewed-only state, and aggregate dataset consistency.
It also runs task-specific quality gates:

- prompt leakage / markdown-fence / refusal text is a hard error;
- SGLB-12 machine-readable issue-label leakage is a hard error;
- SGLB-15 input-vs-expected constraint mismatch is a hard error;
- length drift and SGLB-08 tone words appearing verbatim are warnings for human
  review, not automatic rejection.

4. Record human review:

```sh
python -m benchmark.synthetic review --fixture <slug> --decision approve --reviewer <name>
```

Valid decisions are `approve`, `reject`, and `needs_edit`. Candidates remain in
`*_candidates/` until explicitly approved.

5. Promote approved candidates:

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

Generation loads `.env` by default and only fills missing environment variables.
Use `--env-file path/to/.env` to select a file or `--no-env-file` to require the
current shell environment. Real providers fail a preflight check before any LLM
client is constructed when required keys are missing:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

All randomness goes through one `random.Random(seed)` in the planner, so the
same `(task, n, providers, seed, generator_version, prompt_version)` yields the
same matrix and candidate metadata.
