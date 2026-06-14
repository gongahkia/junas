"""SGLB-09 Summary-Faithfulness task runner."""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_09_task(case: Case) -> str:
    expected = case.expected_output or {}
    facts = expected.get("atomic_facts")
    return json.dumps({"atomic_facts": facts if isinstance(facts, list) else []})


register_task("sglb_09", sglb_09_task, benchmark_eligible=False)
