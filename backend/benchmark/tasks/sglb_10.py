"""SGLB-10 Citation-Generation task runner."""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_10_task(case: Case) -> str:
    expected = case.expected_output or {}
    citations = expected.get("citations")
    if isinstance(citations, list):
        return json.dumps(citations)
    citation = expected.get("citation")
    return json.dumps([citation] if citation else [])


register_task("sglb_10", sglb_10_task, benchmark_eligible=False)
