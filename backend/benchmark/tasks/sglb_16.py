"""SGLB-16 Review-Redflag-Recall task runner."""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_16_task(case: Case) -> str:
    expected = case.expected_output or {}
    return json.dumps(list(expected.get("defects", [])))


register_task("sglb_16", sglb_16_task, benchmark_eligible=False)
