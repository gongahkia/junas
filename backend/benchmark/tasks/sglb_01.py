"""SGLB-01 PDPA-Outcome task runner.

Input contract:
- ``case.inputs["fact_summary"]``: redacted PDPC fact summary (str)

Output (model surface):
- A JSON object: ``{"obligations": [<obligation labels>], "penalty_band": "<band>"}``
  - ``obligations`` drawn from the closed PDPC taxonomy in
    ``data.ingestion.pdpc.OBLIGATION_TAXONOMY``.
  - ``penalty_band`` is one of ``none|low|mid|high``.

Scoring:
- ``sglb_01_obligations_f1`` — multi-label F1 over obligation labels.
- ``penalty_band_mae`` — ordinal MAE on the penalty band index.

This module's runner is the oracle baseline: it returns ``expected_output``
as JSON so the harness end-to-end pipeline can be exercised without an
LLM. The real eval swaps the runner via ``benchmark.llm_runner.llm_task_for``
using the ``sglb_01`` prompt builder.
"""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_01_task(case: Case) -> str:
    expected = case.expected_output or {}
    payload = {
        "obligations": list(expected.get("obligations", [])),
        "penalty_band": expected.get("penalty_band", "none"),
    }
    return json.dumps(payload)


register_task("sglb_01", sglb_01_task)
