"""SGLB-02 Statute-QA task runner.

Input contract:
- ``case.inputs["question"]``: natural-language question
- ``case.inputs["act_short_name"]``: short alias e.g. "PDPA"
- ``case.inputs["act_full_name"]``: full act title

Output (model surface):
- JSON object: ``{"citation": "<SAL-style section ref>", "answer": "<≤200 words>"}``

Scoring:
- ``sglb_02_citation_match`` — exact match after normalisation (primary).
- ``rouge_l_answer`` — ROUGE-L F1 against the gold answer span.

Oracle runner returns the gold expected_output as JSON so the harness
end-to-end pipeline can be exercised without an LLM.
"""
from __future__ import annotations

import json

from benchmark.registry import register_task
from benchmark.schema import Case


async def sglb_02_task(case: Case) -> str:
    expected = case.expected_output or {}
    payload = {
        "citation": str(expected.get("citation", "")),
        "answer": str(expected.get("answer_span", "")),
    }
    return json.dumps(payload)


register_task("sglb_02", sglb_02_task)
