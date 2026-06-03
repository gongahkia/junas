# LLM-Call Task Runner

Converts the harness from "every shipped task scores 1.0 via oracle" into
producing real numbers, by wrapping an `api.services.llm_client.LLMClient`
into a `benchmark.registry.TASKS` runner.

## Quick start

```python
from benchmark.llm_runner import MockLLMClient, llm_task_for
from benchmark.registry import register_task

# Build a runner for SGLB-04 using the mock client (no API key needed).
client = MockLLMClient(default_response='["valid"]')
runner = llm_task_for(workflow="sglb_04", client=client, provider_label="mock:test")
register_task("sglb_04_llm_mock", runner)

# Run via the existing harness.
# python -m benchmark.cli run --workflow sglb_04_llm_mock \
#   --dataset benchmark/datasets/sglb_04_citation_verify.yaml \
#   --evaluator multi_label_f1 --strict
```

## Plug a real provider

```python
from api.services.llm_client import get_llm_client
from api.config import get_settings
from benchmark.llm_runner import llm_task_for
from benchmark.registry import register_task

settings = get_settings()  # reads OPENAI_API_KEY / ANTHROPIC_API_KEY / etc.
real_client = get_llm_client(settings)
runner = llm_task_for(
    workflow="sglb_04",
    client=real_client,
    provider_label=f"{settings.llm_provider}:{settings.openai_model}",
)
register_task("sglb_04_llm_openai", runner)
```

## Failure modes

| Condition | Result |
|---|---|
| Provider call raises | Logged + empty string returned; evaluator scores 0 against the case |
| Provider returns non-string | Coerced to `str(...)`; evaluator scores against the coerced text |
| Output not parseable as JSON | Evaluator records 0 for that case (no silent retries) |

This is the honest design: JSON-parse failures show up as a quality metric
("the model failed structured output N times") rather than getting hidden
behind retries that would inflate scores.

## Registered prompt builders

| Workflow | Output contract |
|---|---|
| `sglb_04` | `["valid"]` or `["invalid"]` — single-element JSON array |
| `sglb_08` | `["standard" \| "aggressive" \| "balanced" \| "protective"]` |
| `sglb_11` | JSON array of fabricated-citation strings (possibly empty) |
| `sglb_12` | JSON array of issue label strings from the SGLB-12 taxonomy |

Each builder is versioned (e.g. `SGLB_04_PROMPT_VERSION = "sglb-04-v1"`).
When a prompt template changes materially, bump the version so receipts
from before and after the change remain distinguishable.

## Reproducibility

Every receipt that uses this runner should record:

- `prompt_version` — from the builder constant
- `provider_label` — from `LLMRunnerConfig.provider_label`
- `prompt_sha` — from `prompt_sha(builder, sample_case)`
- `max_tokens` — from `LLMRunnerConfig.max_tokens`

Currently the receipt schema does not yet carry these — the runner stores
them on the config object, but wiring them through `RunSummary` is a
follow-up (see coverage matrix §4.4).
