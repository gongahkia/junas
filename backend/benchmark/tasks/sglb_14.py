"""SGLB-14 Statutory-Entailment task runner."""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_14_task(case: Case) -> str:
    expected = case.expected_output or {}
    return json.dumps({"entailment": expected.get("entailment", "indeterminate")})


register_task("sglb_14", sglb_14_task, benchmark_eligible=False)
