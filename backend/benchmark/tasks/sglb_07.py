"""SGLB-07 Jurisdiction-Routing task runner.

Input contract:
- ``case.inputs["question"]``: legal question text.

Output (model surface):
- Single-element JSON array drawn from
  ``["sg_binding", "uk_persuasive", "au_persuasive", "hk_persuasive", "not_applicable"]``.

Scoring:
- ``multi_label_f1`` over the single-element labels list.

Oracle runner returns the gold label as JSON.
"""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_07_task(case: Case) -> str:
    expected = case.expected_output or {}
    return json.dumps(list(expected.get("labels", [])))


register_task("sglb_07", sglb_07_task, benchmark_eligible=False)
