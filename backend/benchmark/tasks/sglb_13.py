"""SGLB-13 Counterfactual-Outcome task runner.

Input contract:
- ``case.inputs["fact_pattern"]``: redacted PDPC fact pattern (str)
- ``case.inputs["perturbation"]``: same fact pattern with one
  obligation-cue clause excised (str)

Output (model surface):
- A JSON object: ``{"outcome_changes": bool}``

Scoring: ``accuracy`` (strong-tier, registered in
``benchmark.evaluators``).
"""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_13_task(case: Case) -> str:
    expected = case.expected_output or {}
    return json.dumps({"outcome_changes": bool(expected.get("outcome_changes", False))})


register_task("sglb_13", sglb_13_task, benchmark_eligible=False)
