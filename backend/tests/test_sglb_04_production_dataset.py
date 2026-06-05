from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

from api.services.sal_citation import validate_citation
from benchmark.dataset_builders.sglb_04 import (
    DEFAULT_N_PER_PERTURBATION,
    DEFAULT_VALID_NEGATIVE_N,
    PERTURBATION_KINDS,
    VALID_NEGATIVE_STRATUM,
    _assign_split,
    build_dataset,
)
from benchmark.evaluators import EvaluatorContext, MultiLabelF1


DATASETS_DIR = Path(__file__).parent.parent / "benchmark" / "datasets"
FULL_PATH = DATASETS_DIR / "sglb_04_citation_verify_full.yaml"
LEGACY_SMOKE_PATH = DATASETS_DIR / "sglb_04_citation_verify.yaml"
SMOKE_PATH = DATASETS_DIR / "sglb_04_citation_verify_smoke.yaml"


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _label_for(citation: str) -> str:
    return "valid" if validate_citation(citation).valid else "invalid"


def test_builder_default_stratification_counts() -> None:
    dataset = build_dataset()
    cases = list(dataset["cases"])
    counts = Counter(case["metadata"]["stratum"] for case in cases)
    assert len(cases) == DEFAULT_N_PER_PERTURBATION * len(PERTURBATION_KINDS) + DEFAULT_VALID_NEGATIVE_N
    for perturbation in PERTURBATION_KINDS:
        assert counts[perturbation] == DEFAULT_N_PER_PERTURBATION
    assert counts[VALID_NEGATIVE_STRATUM] == DEFAULT_VALID_NEGATIVE_N


def test_production_yaml_meets_sglb_04_contract() -> None:
    data = _load(FULL_PATH)
    cases = list(data["cases"])
    counts = Counter(case["metadata"]["stratum"] for case in cases)
    assert len(cases) >= 1000
    for perturbation in PERTURBATION_KINDS:
        assert counts[perturbation] >= 100
    assert counts[VALID_NEGATIVE_STRATUM] >= 200

    seen_names: set[str] = set()
    seen_citations: set[str] = set()
    for case in cases:
        citation = str(case["inputs"]["citation"])
        result = validate_citation(citation)
        expected_label = str(case["expected_output"]["labels"][0])
        assert _label_for(citation) == expected_label, case["name"]
        assert case["metadata"]["split"] == _assign_split(str(case["name"]))
        assert case["metadata"]["breakdown"]["expected_errors"] == [error.code for error in result.errors]
        assert case["metadata"]["breakdown"]["stratum"] == case["metadata"]["stratum"]
        assert str(case["name"]) not in seen_names
        assert citation.lower().rstrip(".") not in seen_citations
        seen_names.add(str(case["name"]))
        seen_citations.add(citation.lower().rstrip("."))


def test_smoke_dataset_copy_preserves_legacy_30_case_set() -> None:
    legacy = _load(LEGACY_SMOKE_PATH)
    smoke = _load(SMOKE_PATH)
    assert smoke == legacy
    assert len(smoke["cases"]) == 30


def test_multi_label_f1_reports_sglb_04_breakdown_detail() -> None:
    case = next(
        case
        for case in _load(FULL_PATH)["cases"]
        if case["metadata"]["stratum"] == "court_swap"
    )
    result = asyncio.run(
        MultiLabelF1().evaluate(
            EvaluatorContext(
                case_name=case["name"],
                inputs=case["inputs"],
                expected_output=case["expected_output"],
                metadata=case["metadata"],
                output=json.dumps(case["expected_output"]["labels"]),
            )
        )
    )
    assert result.score == pytest.approx(1.0)
    assert result.detail["breakdown"]["stratum"] == "court_swap"
    assert result.detail["breakdown"]["expected_errors"] == ["unknown_court"]
