"""End-to-end harness tests + evaluator unit coverage."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from benchmark.evaluators import (
    EVALUATORS,
    CitationFormatValid,
    CitesSgStatute,
    CompliancePresent,
    ConstraintSatisfaction,
    ContainsKeyword,
    EvaluatorContext,
    EvaluatorStrength,
    ExactMatch,
    HasCitationMarker,
    MinLength,
    MultiLabelF1,
    UsesSalStyle,
)
from benchmark.registry import register_task
from benchmark.runner import run, write_summary
from benchmark.schema import Case


@pytest.fixture
def smoke_dataset_path() -> Path:
    return Path(__file__).parent.parent / "benchmark" / "datasets" / "example_echo.yaml"


# === Evaluator unit tests ===


def _ctx(output: str, expected: dict | None = None) -> EvaluatorContext:
    return EvaluatorContext(
        case_name="t",
        inputs={},
        expected_output=expected,
        metadata={},
        output=output,
    )


def test_exact_match_strict():
    e = ExactMatch()
    assert asyncio.run(e.evaluate(_ctx("[2023] SGCA 5", {"span": "[2023] SGCA 5"}))).score == 1.0
    assert asyncio.run(e.evaluate(_ctx("[2023] SGCA 6", {"span": "[2023] SGCA 5"}))).score == 0.0


def test_multi_label_f1_overlap():
    e = MultiLabelF1()
    # predicted={pdpa, ea}, expected={pdpa, roc} → tp=1, p=1/2, r=1/2, f1=0.5
    r = asyncio.run(e.evaluate(_ctx('["pdpa", "ea"]', {"labels": ["pdpa", "roc"]})))
    assert r.score == pytest.approx(0.5, abs=1e-3)


def test_multi_label_f1_perfect_match():
    e = MultiLabelF1()
    r = asyncio.run(e.evaluate(_ctx('["pdpa", "ea"]', {"labels": ["pdpa", "ea"]})))
    assert r.score == pytest.approx(1.0)


def test_citation_format_valid_recognises_neutral_case():
    e = CitationFormatValid()
    r = asyncio.run(
        e.evaluate(_ctx("As held in [2023] SGCA 5 the principle stands."))
    )
    assert r.score == 1.0
    assert r.detail["total"] >= 1


def test_citation_format_valid_flags_malformed():
    e = CitationFormatValid()
    r = asyncio.run(e.evaluate(_ctx("[1800] SGZZ 5")))
    assert r.score == 0.0


def test_cites_sg_statute_detects_cap_form():
    e = CitesSgStatute()
    r = asyncio.run(
        e.evaluate(_ctx("Per the Penal Code (Cap. 224, 2008 Rev Ed) the act is criminal."))
    )
    assert r.score == 1.0


def test_cites_sg_statute_detects_section_form():
    e = CitesSgStatute()
    r = asyncio.run(e.evaluate(_ctx("See s 9 of the Penal Code Act for the rule.")))
    assert r.score == 1.0


def test_cites_sg_statute_zero_when_absent():
    assert asyncio.run(CitesSgStatute().evaluate(_ctx("No statute is mentioned"))).score == 0.0


def test_uses_sal_style_rewards_short_form_after_duplicate():
    e = UsesSalStyle()
    # Two raw repeats — should be Ibid'd; raw passage emits no Ibid.
    text = "[2023] SGCA 5 [2023] SGCA 5"
    r = asyncio.run(e.evaluate(_ctx(text)))
    # No Ibid present despite consecutive duplicate ⇒ penalised
    assert r.score == 0.0


def test_uses_sal_style_no_op_when_single_citation():
    text = "[2023] SGCA 5 is dispositive."
    r = asyncio.run(UsesSalStyle().evaluate(_ctx(text)))
    assert r.score == 1.0


def test_compliance_present_partial_match():
    e = CompliancePresent()
    r = asyncio.run(
        e.evaluate(
            _ctx(
                "The PDPA imposes obligations.",
                {"required_regimes": ["pdpa", "employment_act"]},
            )
        )
    )
    assert r.score == 0.5


def test_constraint_satisfaction_runs_constraints():
    e = ConstraintSatisfaction()
    expected = {
        "constraints": [
            {"id": "c1", "kind": "named_party_present", "params": {"party_names": ["Acme"]}},
            {"id": "c2", "kind": "iso_date_present"},
        ]
    }
    output = "This Agreement is between Acme Pte Ltd and Globex Corp, dated 2026-06-03."
    r = asyncio.run(e.evaluate(_ctx(output, expected)))
    assert r.score == 1.0


def test_constraint_satisfaction_unknown_kind_fails_one():
    e = ConstraintSatisfaction()
    expected = {"constraints": [{"id": "x", "kind": "does_not_exist", "params": {}}]}
    r = asyncio.run(e.evaluate(_ctx("anything", expected)))
    assert r.score == 0.0


def test_weak_evaluators_carry_weak_tier():
    for name in ("contains", "has_citation_marker", "min_length"):
        assert EVALUATORS[name].strength == EvaluatorStrength.WEAK


def test_strong_evaluators_carry_strong_tier():
    for name in (
        "exact_match",
        "multi_label_f1",
        "citation_format_valid",
        "cites_sg_statute",
        "uses_sal_style",
        "compliance_present",
        "constraint_sat",
    ):
        assert EVALUATORS[name].strength == EvaluatorStrength.STRONG


# === Runner end-to-end ===


def test_runner_loads_dataset_and_scores(smoke_dataset_path: Path):
    summary = asyncio.run(
        run(
            workflow="echo",
            dataset_path=smoke_dataset_path,
            evaluators=["citation_format_valid"],
            max_concurrency=2,
        )
    )
    assert summary.total_cases == 3
    means = summary.per_evaluator_mean()
    assert "citation_format_valid" in means


def test_runner_strict_mode_rejects_weak_evaluator(smoke_dataset_path: Path):
    with pytest.raises(ValueError, match="strict mode rejects weak evaluators"):
        asyncio.run(
            run(
                workflow="echo",
                dataset_path=smoke_dataset_path,
                evaluators=["contains"],
                strict=True,
            )
        )


def test_runner_writes_json_receipt(tmp_path: Path, smoke_dataset_path: Path):
    summary = asyncio.run(
        run(
            workflow="echo",
            dataset_path=smoke_dataset_path,
            evaluators=["cites_sg_statute"],
            max_concurrency=2,
        )
    )
    out = tmp_path / "receipt.json"
    write_summary(summary, out)
    data = out.read_text(encoding="utf-8")
    assert "per_evaluator_mean" in data
    assert "started_at" in data
    assert "finished_at" in data


def test_unknown_workflow_returns_per_evaluator_error(smoke_dataset_path: Path):
    summary = asyncio.run(
        run(
            workflow="does_not_exist",
            dataset_path=smoke_dataset_path,
            evaluators=["cites_sg_statute"],
        )
    )
    assert all(r.error for r in summary.results)


def test_register_task_then_run(tmp_path: Path):
    async def upper(case: Case) -> str:
        return str(case.inputs.get("query", "")).upper()

    register_task("upper", upper)

    ds_path = tmp_path / "ds.yaml"
    ds_path.write_text(
        "cases:\n"
        "  - name: c1\n"
        "    inputs:\n"
        "      query: hello\n"
        "    expected_output:\n"
        "      span: HELLO\n",
        encoding="utf-8",
    )
    summary = asyncio.run(
        run(workflow="upper", dataset_path=ds_path, evaluators=["exact_match"])
    )
    assert summary.per_evaluator_mean()["exact_match"] == 1.0
