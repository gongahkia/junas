"""SG-LegalBench eval harness.

Lightweight, single-process harness for running benchmark tasks defined in
YAML datasets against a registered scorer. Mirrors the upstream
pydantic-evals schema (cases / inputs / expected_output / metadata) without
pulling the library, so we keep tight control over evaluator semantics —
the coverage matrix mandates stronger evaluators than the upstream
defaults.

Public surface:

- ``Case``, ``Dataset`` — Pydantic models for YAML deserialisation.
- ``Evaluator`` — protocol for a scorer with strength tier.
- ``EvaluatorRegistry``, ``TaskRegistry`` — name-based registration.
- ``run`` — async orchestrator.
- ``cli`` — argparse entry point (``python -m benchmark.cli``).

See ``docs/coverage-matrix.md`` §4.2 for the evaluator-strength policy.
"""

from benchmark.evaluators import (
    Evaluator,
    EvaluatorContext,
    EvaluatorStrength,
    EVALUATORS,
)
from benchmark.registry import TASKS, register_task
from benchmark.runner import RunSummary, run
from benchmark.schema import Case, Dataset, EvalCaseResult

__all__ = [
    "Case",
    "Dataset",
    "EvalCaseResult",
    "Evaluator",
    "EvaluatorContext",
    "EvaluatorStrength",
    "EVALUATORS",
    "RunSummary",
    "TASKS",
    "register_task",
    "run",
]
