"""SGLB-11 Citation-Hallucination task.

Input contract:
- ``case.inputs["passage"]``: passage with N citations, some real, some
  fabricated.

Output (model surface):
- JSON list of the citation strings the model believes are fabricated.

Scoring:
- Custom ``citation_hallucination_f1`` evaluator (registered in
  ``benchmark.evaluators``) reports overall P/R/F1 plus a per-
  perturbation-class breakdown when `case.metadata.citation_index`
  carries provenance.

Task runner shape:
- The default ``sglb_11`` registered task is the **oracle wrapper** —
  it consults the case metadata directly and returns the gold list.
  This gives a deterministic regression test (oracle vs oracle = F1=1.0).
- For real evaluation, swap the runner for an LLM-call wrapper at
  registration time (lands when #36 baselines start).
"""
from __future__ import annotations

import json
from typing import Any

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_11_oracle_task(case: Case) -> str:
    """Oracle baseline: read fakes from the case metadata.

    Used for regression testing and as a sanity check that the harness +
    scorer wiring is correct. Real LLM runs swap this out at
    registration time.
    """
    index = case.metadata.get("citation_index", [])
    fakes = [entry["citation"] for entry in index if entry.get("is_fake")]
    return json.dumps(fakes)


register_task("sglb_11", sglb_11_oracle_task)
