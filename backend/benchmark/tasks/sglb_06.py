"""SGLB-06 Rules-of-Court-2021 task runner.

Input contract:
- ``case.inputs["scenario"]``: procedural scenario string

Output (model surface):
- JSON array of ``"O. <N>, r. <M>"`` labels.

Scoring:
- ``order_rule_label_f1`` — multi-label F1 over normalised labels.
- ``order_rule_top3`` — top-3 accuracy over the model's first 3 labels.

Oracle runner returns the gold labels as JSON so the harness can be
exercised end-to-end without an LLM.
"""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_06_task(case: Case) -> str:
    expected = case.expected_output or {}
    labels = list(expected.get("labels", []))
    return json.dumps(labels)


register_task("sglb_06", sglb_06_task)
