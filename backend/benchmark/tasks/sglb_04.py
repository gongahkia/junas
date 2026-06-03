"""SGLB-04 Citation-Verify task.

Input contract:
- ``case.inputs["citation"]``: candidate citation string (e.g. "[2023] SGCA 5")

Output (model surface):
- A JSON list containing exactly one label: "valid" or "invalid".
  This format keeps SGLB-04 compatible with the multi-label F1 evaluator
  used across the harness.

Scoring:
- ``multi_label_f1`` over the single-element labels list, with
  ``expected_output["labels"] = ["valid"]`` or ``["invalid"]``.
- For diagnostic introspection, the deterministic SAL grammar checker
  ``api.services.sal_citation.validate_citation`` is the canonical
  oracle: this task wraps it as the "model" so we can measure
  scorer-vs-oracle agreement on synthetic data, and so the same task can
  later be re-run against an LLM by swapping the runner.
"""
from __future__ import annotations

import json

from api.services.sal_citation import validate_citation
from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_04_task(case: Case) -> str:
    citation = str(case.inputs.get("citation", "")).strip()
    result = validate_citation(citation)
    label = "valid" if result.valid else "invalid"
    return json.dumps([label])


register_task("sglb_04", sglb_04_task)
