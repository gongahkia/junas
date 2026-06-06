# Vendor self-eval guide

This guide takes a Singapore legal-tech ML engineer from a clean checkout to a
benchmark receipt they can paste into an internal slide deck. It is written for:

- SG legal-tech vendors evaluating a production or candidate LLM.
- LLM-team engineers who need reproducible, BYOK runs without touching benchmark
  internals.
- Academic researchers who want local receipts before comparing against the
  public SG-LegalBench leaderboard.

SG-LegalBench is an evaluation harness, not legal advice. Labels are
mechanically extracted from public sources; methodology rules live in the
[coverage matrix](coverage-matrix.md).

## Install

Use Python 3.11 or newer. From the repository root:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e backend openai anthropic
```

If you use `uv`, the equivalent is:

```sh
uv venv .venv --python python3.11
uv pip install --python .venv/bin/python -e backend openai anthropic
```

Run the CLI from `backend/`:

```sh
cd backend
../.venv/bin/python -m benchmark.cli list --kind tasks
../.venv/bin/python -m benchmark.cli list --kind evaluators
```

## Configure your provider

Create a local `.env` at the repo root. Do not commit it.

```sh
cp backend/.env.example .env
```

Set one provider block:

| Provider | `.env` values |
|---|---|
| Anthropic | `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...`, `ANTHROPIC_MODEL=claude-sonnet-4-6` |
| OpenAI | `LLM_PROVIDER=openai`, `OPENAI_API_KEY=...`, `OPENAI_MODEL=gpt-4o-mini` |
| Google Gemini | `LLM_PROVIDER=gemini`, `GEMINI_API_KEY=...`, `GEMINI_MODEL=gemini-2.0-flash` |
| Ollama | `LLM_PROVIDER=ollama`, `OLLAMA_URL=http://localhost:11434`, `OLLAMA_MODEL=<already-pulled-model>` |

For Ollama, start the server and pull the model first:

```sh
ollama serve
ollama pull qwen3:4b
```

## Select tasks

The CLI may list more workflows than are eligible for v0.1 publication. For
vendor self-eval and leaderboard submission, use:

| Task | Dataset | Evaluators |
|---|---|---|
| SGLB-01 PDPA-Outcome | `benchmark/datasets/sglb_01_pdpa.yaml` | `sglb_01_obligations_f1`, `penalty_band_mae` |
| SGLB-02 Statute-QA | `benchmark/datasets/sglb_02_statute_qa.yaml` | `sglb_02_citation_match`, `rouge_l_answer` |
| SGLB-04 Citation-Verify | `benchmark/datasets/sglb_04_citation_verify.yaml` | `multi_label_f1` |
| SGLB-08 Clause-Tone | `benchmark/datasets/sglb_08_clause_tone_reviewed/dataset.yaml` | `multi_label_f1` |

SGLB-05, SGLB-06, and SGLB-07 are code-shipped but data-pending for v0.1
vendor publication. Do not submit them to the public leaderboard until the
release notes say they are eligible.

## Run strict mode

First, run a no-network smoke test. This uses the oracle workflow, so
`provenance` is intentionally `{}`.

```sh
cd backend
../.venv/bin/python -m benchmark.cli run \
  --workflow sglb_04 \
  --dataset benchmark/datasets/sglb_04_citation_verify.yaml \
  --evaluator multi_label_f1 \
  --strict \
  --output ../runs/vendor/smoke-sglb-04.json
```

For your model, register an LLM-backed workflow and run the same strict harness.
This does not modify repo files.

```sh
cd backend
SGLB_TASK=sglb_04 SGLB_CONTAMINATION=0 ../.venv/bin/python - <<'PY'
import asyncio
import json
import os
from pathlib import Path

from api.config import Settings
from api.services.llm_client import get_llm_client, get_llm_model_name
from benchmark.llm_runner import register_llm_task
from benchmark.runner import load_dataset, run, write_summary

TASKS = {
    "sglb_01": ("benchmark/datasets/sglb_01_pdpa.yaml", ["sglb_01_obligations_f1", "penalty_band_mae"], 256),
    "sglb_02": ("benchmark/datasets/sglb_02_statute_qa.yaml", ["sglb_02_citation_match", "rouge_l_answer"], 384),
    "sglb_04": ("benchmark/datasets/sglb_04_citation_verify.yaml", ["multi_label_f1"], 64),
    "sglb_08": ("benchmark/datasets/sglb_08_clause_tone_reviewed/dataset.yaml", ["multi_label_f1"], 64),
}

workflow = os.environ.get("SGLB_TASK", "sglb_04")
dataset_path, evaluators, max_tokens = TASKS[workflow]
settings = Settings(_env_file=Path("../.env"))
client = get_llm_client(settings)
model = get_llm_model_name(settings)
dataset = load_dataset(dataset_path)
registered = f"{workflow}_llm_vendor_{settings.llm_provider}"

register_llm_task(
    name=registered,
    workflow=workflow,
    client=client,
    provider_label=f"{settings.llm_provider}:{model}",
    max_tokens=max_tokens,
    sample_case=dataset.cases[0],
)

summary = asyncio.run(
    run(
        workflow=registered,
        dataset_path=dataset_path,
        evaluators=evaluators,
        max_concurrency=int(os.environ.get("SGLB_MAX_CONCURRENCY", "2")),
        strict=True,
        contamination_probe=os.environ.get("SGLB_CONTAMINATION", "0") == "1",
    )
)

out = Path("../runs/vendor") / f"{registered}.json"
out.parent.mkdir(parents=True, exist_ok=True)
write_summary(summary, out)
print(json.dumps({
    "receipt": str(out),
    "score": summary.per_evaluator_mean(),
    "ci": summary.per_evaluator_bootstrap(),
    "contamination_summary": summary.contamination_summary,
    "provenance": summary.provenance,
}, indent=2, sort_keys=True))
PY
```

For publication-style runs on SGLB-01, SGLB-02, or SGLB-08, set
`SGLB_CONTAMINATION=1`. The probe adds one extra model call per labelled case.
SGLB-04 skips the probe because citation grammar is deterministic.

## Read the receipt

Use the [sample receipt](vendor-self-eval-guide/sample-receipt.json) as a
walkthrough. The current schema is documented in
[backend/benchmark/receipt_schema.md](../backend/benchmark/receipt_schema.md).

Fields to paste into a slide deck:

- `workflow`, `dataset`, `total_cases`: what you ran and how large it was.
- `strict: true`, `weak_evaluators_used: []`: publication mode rejected weak
  evaluators such as keyword or length checks.
- `per_evaluator_mean`: headline score per metric.
- `per_evaluator_bootstrap.<metric>`: 95% bootstrap CI. Quote it as
  `mean [ci_low, ci_high]`.
- `provenance.provider_label`: provider and model label.
- `provenance.prompt_version`, `provenance.prompt_sha`, `provenance.max_tokens`:
  reproducibility metadata for the exact prompt surface.
- `contamination_summary.mean_memorisation_rate`: share of probed cases where
  the model could recall labels without the task input.
- `contamination_summary.contamination_adjusted_score`: score over cases that
  were not flagged by the memorisation probe.
- `results[].metadata.memorisation_flag`: case-level contamination flags.

Citation and statute exact-match normalisation is specified in
[docs/normalisation-spec.md](normalisation-spec.md). Contamination probe
methodology is specified in
[docs/methodology/contamination.md](methodology/contamination.md).

## Submit

Submission is optional. To add your model to the public leaderboard, open a PR
or issue with:

- the receipt JSON under `runs/baselines/<vendor-or-provider>/<task>/`;
- provider/model display name and whether the model is hosted or local;
- task IDs and dataset versions;
- confirmation that every submitted receipt has `strict: true`;
- confirmation that LLM receipts include `prompt_sha`;
- contamination-probe receipts for SGLB-01, SGLB-02, and SGLB-08 when run.

The published row is built from receipt JSON. See
[sample-leaderboard-row.md](vendor-self-eval-guide/sample-leaderboard-row.md)
for the shape.

## Disagree with a label

Do not patch a label ad hoc in your private run and submit that score as
comparable. File the concern through the
[dispute and errata process](dispute-process.md). Use the label-dispute form
for one released case and the methodology-concern form for systemic scorer,
normaliser, split, or extraction-rule issues.
