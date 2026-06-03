# SG-LegalBench Harness

Lightweight async harness for running benchmark tasks against registered
scorers. YAML dataset schema is intentionally compatible with the
upstream pydantic-evals layout so external tasks can drop in.

## Quick start

```sh
# List registered tasks and evaluators
python -m benchmark.cli list

# Run the smoke task with two evaluators
python -m benchmark.cli run \
  --workflow echo \
  --dataset benchmark/datasets/example_echo.yaml \
  --evaluator citation_format_valid \
  --evaluator cites_sg_statute

# Strict mode (publication): reject weak evaluators
python -m benchmark.cli run \
  --workflow echo \
  --dataset benchmark/datasets/example_echo.yaml \
  --evaluator citation_format_valid \
  --strict
```

## Architecture

```
backend/benchmark/
├── schema.py        Case / Dataset / EvalCaseResult Pydantic models
├── evaluators.py    Evaluator base + strong/weak registry
├── constraints.py   IFEval-style constraint runners
├── registry.py      Task runner registry
├── runner.py        Async orchestrator + RunSummary
├── cli.py           argparse entry point
└── datasets/        YAML datasets (smoke + per-task)
```

## Evaluators

Each evaluator carries a strength tier from
`docs/coverage-matrix.md` §4.2:

| Name | Strength | What it measures |
|---|---|---|
| `exact_match` | strong | strict equality against `expected_output["span"]` |
| `multi_label_f1` | strong | multi-label F1 between output labels and `expected_output["labels"]` |
| `citation_format_valid` | strong | fraction of extracted citations passing SAL grammar |
| `cites_sg_statute` | strong | at least one SG statute citation present |
| `uses_sal_style` | strong | sequence-level Ibid/Id/supra correctness |
| `compliance_present` | strong | required compliance regimes (PDPA/EA/ROC2021) referenced |
| `constraint_sat` | strong | IFEval-style verifiable constraint satisfaction |
| `contains` | weak | back-compat keyword presence; rejected in `--strict` |
| `has_citation_marker` | weak | back-compat; rejected in `--strict` |
| `min_length` | weak | back-compat; rejected in `--strict` |

## Task registration

```python
from benchmark.registry import register_task

async def my_task(case):
    return await my_workflow(case.inputs["query"])

register_task("my_workflow", my_task)
```

## Adding constraints

Constraints used by `constraint_sat` live in `constraints.py`. Each is a
small Python function returning `True`/`False`. Add new kinds by editing
`CONSTRAINTS`.

## Reproducibility receipts

`--output receipt.json` emits a JSON receipt per coverage matrix §4.4
containing: workflow, dataset path, evaluators, per-case scores, per-
evaluator means, start/finish timestamps, strict flag, any weak
evaluators used.
