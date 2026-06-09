from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
from typing import get_type_hints

import pytest


def _tool_module(name: str):
    for prefix in ("mcp.tools", "backend.mcp.tools"):
        try:
            return importlib.import_module(f"{prefix}.{name}")
        except ModuleNotFoundError:
            continue
    raise ModuleNotFoundError(name)


benchmark_tool = _tool_module("run_benchmark")
compliance_tool = _tool_module("check_compliance")
statute_tool = _tool_module("lookup_statute")
cases_tool = _tool_module("retrieve_cases")
citation_tool = _tool_module("verify_citation")

run_benchmark = benchmark_tool.run_benchmark
check_compliance = compliance_tool.check_compliance
lookup_statute = statute_tool.lookup_statute
retrieve_cases = cases_tool.retrieve_cases
verify_citation = citation_tool.verify_citation


def test_verify_citation_returns_sal_validation_payload():
    result = verify_citation("[2023] SGCA 5")
    assert result["citation"] == "[2023] SGCA 5"
    assert result["valid"] is True
    assert result["kind"] == "neutral_case"


def test_check_compliance_filters_by_regime():
    result = check_compliance(
        "The organisation obtains consent before collecting personal data under the PDPA.",
        "pdpa",
    )
    assert result["regime"] == "pdpa"
    assert result["summary"]["total"] == 2
    assert {row["rule_id"] for row in result["results"]} == {"pdpa-consent", "pdpa-purpose"}


def test_check_compliance_rejects_unknown_regime():
    result = check_compliance("hello", "uk_gdpr")  # type: ignore[arg-type]
    assert "error" in result
    assert result["allowed_regimes"] == ["employment_act", "pdpa", "roc_2021"]


def test_lookup_statute_uses_local_sso_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sso = tmp_path / "statutes.jsonl"
    sso.write_text(
        json.dumps(
            {
                "number": "13",
                "chapter_number": "PDPA2012",
                "name": "Consent required",
                "text_plain": "An organisation must obtain consent.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(statute_tool, "_candidate_paths", lambda: [sso])

    result = lookup_statute("s 13 PDPA")
    assert result["found"] is True
    assert result["result"]["name"] == "Consent required"


def test_retrieve_cases_uses_case_retrieval_service(monkeypatch: pytest.MonkeyPatch):
    class FakeService:
        def search_cases(self, query: str, top_k: int, include_scores: bool):
            return {
                "query": query,
                "results": [{"case_id": "case-1", "relevance_score": 0.9}],
                "retrieval_info": {"top_k": top_k, "include_scores": include_scores},
            }

    monkeypatch.setattr(cases_tool, "_create_service", lambda: FakeService())

    result = retrieve_cases("restraint of trade", k=3)
    assert result["results"][0]["case_id"] == "case-1"
    assert result["retrieval_info"]["top_k"] == 3


def test_run_benchmark_rejects_unknown_model():
    result = asyncio.run(run_benchmark("sglb_04", "bad-model"))  # type: ignore[arg-type]
    assert "error" in result
    assert result["allowed_models"] == ["anthropic", "azure", "gemini", "ollama"]


def test_run_benchmark_runs_sglb_16_local_oracle():
    result = asyncio.run(run_benchmark("sglb_16", "ollama"))
    assert result["external_llm_calls"] is False
    assert result["total_cases"] == 30
    assert result["per_evaluator_mean"]["sglb_16_redflag_f1"] == 1.0


def test_tool_signatures_are_schema_friendly():
    benchmark_hints = get_type_hints(benchmark_tool.run_benchmark)
    statute_hints = get_type_hints(statute_tool.lookup_statute)
    cases_hints = get_type_hints(cases_tool.retrieve_cases)
    compliance_hints = get_type_hints(compliance_tool.check_compliance)
    assert benchmark_hints["task"] is str
    assert "model" in benchmark_hints
    assert statute_hints["query"] is str
    assert cases_hints["k"] is int
    assert compliance_hints["text"] is str
