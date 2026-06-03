"""SGLB-08 Clause-Tone synthetic task wrapper."""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


def _require_reviewed(case: Case) -> None:
    if case.metadata.get("data_tier") != "synthetic" or case.metadata.get("review_stage") != "reviewed":
        raise ValueError("SGLB-08 reads reviewed synthetic fixtures only")


async def sglb_08_task(case: Case) -> str:
    _require_reviewed(case)
    return json.dumps((case.expected_output or {}).get("labels", []))


register_task("sglb_08", sglb_08_task)
