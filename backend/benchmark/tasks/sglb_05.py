"""SGLB-05 Employment-Issue task runner.

Input contract:
- ``case.inputs["scenario"]``: 100-300-token fact pattern.

Output (model surface):
- JSON array of issue labels drawn from the MOM-published taxonomy.

Scoring:
- ``multi_label_f1`` — reuses the existing strong-tier evaluator.

Oracle runner returns the gold labels as JSON so the harness has a
complete v0.1 shape before live MOM data lands.
"""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_05_task(case: Case) -> str:
    expected = case.expected_output or {}
    return json.dumps(list(expected.get("labels", [])))


register_task("sglb_05", sglb_05_task, benchmark_eligible=False)
