"""Dataset + result schemas for the benchmark harness.

YAML format is intentionally compatible with the pydantic-evals layout:

```yaml
extraction_rules:
  pdpc: abc1234
cases:
  - name: case_id_1
    extraction_rule_sha: abc1234
    inputs:
      query: "..."
    expected_output:
      contains: ["..."]
      span: "..."
    metadata:
      jurisdiction: SG
      category: pdpa
      split: train | dev | test
```

The harness does not impose a fixed set of input fields — each task
defines what shape its ``inputs`` dict carries. ``expected_output``
likewise depends on the evaluator chosen.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Case(BaseModel):
    name: str
    extraction_rule_sha: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_output: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class Dataset(BaseModel):
    extraction_rules: dict[str, str] = Field(default_factory=dict)
    cases: list[Case]

    model_config = ConfigDict(extra="forbid")


class EvalCaseResult(BaseModel):
    """Result for a single (case, evaluator) pair."""

    case_name: str
    evaluator: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
