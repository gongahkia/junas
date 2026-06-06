# Cold-Start Guide: SGLB-04 LLM Baseline

This guide is the no-questions path for a new agent dropped into `junas`.
It registers an LLM-backed SGLB-04 task, runs the existing smoke dataset
with a mock client first, then swaps in OpenAI `gpt-4o-mini`.
Goal: produce a JSON receipt with provenance fields.

## Target

Produce:

```text
runs/baselines/openai/sglb_04/<timestamp>-gpt-4o-mini.json
```

Use:

- task under test: `sglb_04`
- dataset: `backend/benchmark/datasets/sglb_04_citation_verify_smoke.yaml`
- evaluator: `multi_label_f1`
- strict mode: `true`
- provider label: `openai:gpt-4o-mini`
- max tokens: `64`

The receipt must include `provenance.prompt_version`,
`provenance.prompt_sha`, `provenance.provider_label`, and
`provenance.max_tokens`.

## 1. Orient From Repo Root

```sh
cd /Users/gongahkia/Desktop/coding/projects/junas
pwd
git status --short --branch
sed -n '1,240p' AGENT-RUNBOOK.md
sed -n '1,220p' backend/benchmark/LLM_RUNNER.md
sed -n '1,220p' CONTRIBUTING.md
```

Rules those files establish:

- Use `.venv/bin/python`, not system Python.
- Use `benchmark.llm_runner.register_llm_task(...)`.
- Use strong evaluators with `--strict`.
- LLM task registration is process-local.
- Register and run in the same Python process.

## 2. Prepare Branch And Venv

```sh
git switch docs/cold-start-guide || git switch -c docs/cold-start-guide
ls -l .venv/bin/python || uv venv .venv --python /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13
.venv/bin/python --version
uv pip install --python .venv/bin/python -e backend
uv pip install --python .venv/bin/python pytest pytest-asyncio ruff openpyxl beautifulsoup4 lxml httpx pyyaml pydantic pydantic-settings openai anthropic
```

## 3. Confirm SGLB-04

```sh
sed -n '1,260p' backend/benchmark/datasets/sglb_04_citation_verify_smoke.yaml
sed -n '1,180p' backend/benchmark/tasks/sglb_04.py
rg -n "SGLB_04_PROMPT_VERSION|def sglb_04_prompt_builder|register_llm_task" backend/benchmark/llm_runner.py
cd backend
../.venv/bin/python -m pytest tests/test_llm_runner.py tests/test_receipt_provenance.py tests/test_sglb_04_production_dataset.py -q
../.venv/bin/python -m benchmark.cli list --kind tasks
cd ..
```

SGLB-04 is Citation-Verify. Inputs contain `case.inputs["citation"]`.
Outputs must be a single JSON array: `["valid"]` or `["invalid"]`.
The smoke dataset has 30 constructed citation-grammar cases.
It does not test whether a citation identifies a real case.
If a doc mentions `backend/tests/test_sglb_04_task.py`, use
`backend/tests/test_sglb_04_production_dataset.py`; that is the live file.

## 4. Run A Mock LLM Receipt

This uses the repo's `MockLLMClient`. The score is not the point; the
point is that the LLM registration path writes provenance to the receipt.

```sh
cd backend
../.venv/bin/python - <<'PY'
import asyncio, json
from datetime import datetime, timezone
from pathlib import Path
from benchmark.llm_runner import MockLLMClient, register_llm_task
from benchmark.runner import load_dataset, run, write_summary

DATASET = Path("benchmark/datasets/sglb_04_citation_verify_smoke.yaml")
workflow = "sglb_04_llm_mock_cold_start"
dataset = load_dataset(DATASET)
register_llm_task(
    name=workflow,
    workflow="sglb_04",
    client=MockLLMClient(default_response='["valid"]'),
    provider_label="mock:always-valid",
    max_tokens=64,
    sample_case=dataset.cases[0],
)
summary = asyncio.run(run(
    workflow=workflow,
    dataset_path=DATASET,
    evaluators=["multi_label_f1"],
    max_concurrency=4,
    strict=True,
))
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out = Path("../runs/baselines/mock/sglb_04") / f"{stamp}-always-valid.json"
out.parent.mkdir(parents=True, exist_ok=True)
write_summary(summary, out)
assert summary.total_cases == 30
assert summary.strict is True
assert summary.provenance["prompt_version"] == "sglb-04-v1"
assert summary.provenance["provider_label"] == "mock:always-valid"
assert summary.provenance["prompt_sha"]
assert summary.provenance["max_tokens"] == 64
print(json.dumps({"receipt": str(out), "mean": summary.per_evaluator_mean(), "provenance": summary.provenance}, indent=2, sort_keys=True))
PY
cd ..
```

## 5. Configure OpenAI

Use shell env or repo-root `.env`. Do not commit secrets.

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

The real run below forces `llm_provider=openai` and
`openai_model=gpt-4o-mini`; it reads the key from env or `.env`.
If the key is absent, stop with the credential error.
Do not ask the user and do not fabricate a baseline.

## 6. Run gpt-4o-mini

```sh
cd backend
../.venv/bin/python - <<'PY'
import asyncio, json
from datetime import datetime, timezone
from pathlib import Path
from api.config import Settings
from api.services.llm_client import get_llm_client
from benchmark.llm_runner import register_llm_task
from benchmark.runner import load_dataset, run, write_summary

REPO_ROOT = Path.cwd().parent
DATASET = Path("benchmark/datasets/sglb_04_citation_verify_smoke.yaml")
MODEL = "gpt-4o-mini"
workflow = "sglb_04_llm_openai_gpt_4o_mini_cold_start"
settings = Settings(_env_file=REPO_ROOT / ".env", llm_provider="openai", openai_model=MODEL)
client = get_llm_client(settings)
dataset = load_dataset(DATASET)
register_llm_task(
    name=workflow,
    workflow="sglb_04",
    client=client,
    provider_label=f"openai:{MODEL}",
    max_tokens=64,
    sample_case=dataset.cases[0],
)
summary = asyncio.run(run(
    workflow=workflow,
    dataset_path=DATASET,
    evaluators=["multi_label_f1"],
    max_concurrency=1,
    strict=True,
))
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out = Path("../runs/baselines/openai/sglb_04") / f"{stamp}-gpt-4o-mini.json"
out.parent.mkdir(parents=True, exist_ok=True)
write_summary(summary, out)
prov = summary.provenance
assert summary.total_cases == 30
assert summary.strict is True
assert prov["prompt_version"] == "sglb-04-v1"
assert prov["provider_label"] == "openai:gpt-4o-mini"
assert prov["prompt_sha"]
assert prov["max_tokens"] == 64
print(json.dumps({"receipt": str(out), "mean": summary.per_evaluator_mean(), "provenance": prov}, indent=2, sort_keys=True))
PY
cd ..
```

Do not edit the receipt to improve the score.
Malformed JSON is a scored model failure by design.

## 7. Do Not

- Do not use oracle workflow `sglb_04` as the LLM baseline.
- Do not split registration and running across separate Python processes.
- Do not run the full production SGLB-04 dataset for this cold start.
- Do not replace `multi_label_f1` with a weak evaluator.
- Do not commit `.env`, receipts, or unrelated worktree changes.
Done means the OpenAI receipt exists and the inline assertions passed.
