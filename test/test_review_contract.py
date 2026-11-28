"""The public review contract exposes contextual evidence without legacy risk scores."""

import json
import subprocess
import sys
from dataclasses import asdict, replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import junas
from junas import ReviewPipeline, classify_text
from junas.advisory.llm_adjudicator.inference import LocalLLMAdjudicator
from junas.review.engine import mnpi_advice_eligible

TEXT = (
    "Employee: Alice Tan. Email: alice.tan@example.com. "
    "SGX-listed Orchid Holdings Ltd has signed a material acquisition. "
    "The acquisition has not been publicly announced."
)
REMOVED = {"overall_risk", "document_score", "pii_score", "mnpi_score"}


def test_classification_and_json_have_one_contextual_decision_contract():
    result = classify_text(TEXT)
    output = ReviewPipeline().review_text(TEXT).to_dict()
    assert output["schema_version"] == "junas.review.v2"
    assert not REMOVED & output.keys()
    assert not REMOVED & asdict(result).keys()
    assert not hasattr(junas, "Classification")
    assert output["sensitivity"] == result.sensitivity
    assert result.sensitivity["pii"]["state"] == result.sensitivity["mnpi"]["state"] == "present"
    assert result.sensitivity["mnpi"]["public_status_verified"] is False
    for finding in output["findings"]:
        assert "score" not in finding
        assert TEXT[finding["start_char"] : finding["end_char"]] == finding["matched_text"]


def test_no_detection_is_not_a_safe_or_verified_absence_claim():
    result = classify_text("Lunch starts at noon.")
    assert result.sensitivity["absence_verified"] is False
    assert result.sensitivity["pii"]["state"] == result.sensitivity["mnpi"]["state"] == "not_detected"


def test_cli_emits_the_new_contract():
    run = subprocess.run(
        [sys.executable, "-m", "junas.cli", "classify", "--text", TEXT], capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    output = json.loads(run.stdout)
    assert output["schema_version"] == "junas.review.v2"
    assert not REMOVED & output.keys()


def test_advice_router_uses_severity_not_number_of_emissions():
    result = classify_text("Acme acquisition for $2.5 billion is pending.")
    finding = next(f for f in result.findings if f.category == "MNPI")
    repeated = [replace(finding, id=str(i)) for i in range(30)]
    assert mnpi_advice_eligible(repeated)
    assert not mnpi_advice_eligible(repeated + [replace(finding, severity="high")])
    assert not mnpi_advice_eligible([])
    assert not mnpi_advice_eligible([replace(finding, category="PII")])


@pytest.mark.parametrize("state", ["present", "unknown", "not_detected"])
def test_configured_adjudicator_accepts_contextual_state_without_legacy_label(state):
    settings = SimpleNamespace(
        enabled=True,
        provider="vllm",
        model="fake-model",
        base_url="http://127.0.0.1:8001/v1",
        llm_input_mode="structured_tokens",
        allow_remote_base_url=False,
        allow_remote_raw_text=False,
    )
    provider = LocalLLMAdjudicator(settings)
    payload = dict(
        risk_label="LOW_RISK",
        public_status="ambiguous",
        confidence=0.5,
        materiality_reason="unverified model proposal",
        matched_public_sources=[],
        unverified_claims=[],
        review_recommendation="unverified",
    )
    with patch.object(provider, "_call_openai_compatible", return_value=payload) as call:
        result = provider.adjudicate(text=TEXT, current_classification=state, findings=[])
    assert call.call_count == 1
    assert result["status"] == "adjudicated" and result["classification_applied"] is False


def test_old_student_risk_agreement_command_fails_before_loading_a_model():
    from training.distillation.eval_against_corpus import main

    assert main() == 2


def test_advice_cost_estimate_uses_the_runtime_routing_stage(tmp_path):
    from pathlib import Path

    from junas.review.engine import PreSendReviewEngine
    from scripts.run_layer_attribution_eval import audit_grade_cost_estimate

    source = Path("test/fixtures/legal-corpus-reviewed-candidates/ae_quasi_identifiers_privacy_notice_negative_001.txt")
    text = source.read_text()
    labels = json.loads(source.with_suffix(".labels.json").read_text())
    (tmp_path / "example.txt").write_text(text)
    (tmp_path / "example.labels.json").write_text(json.dumps(labels))
    engine = PreSendReviewEngine()
    eligibility = []

    def capture_route(**kwargs):
        eligibility.append(mnpi_advice_eligible(kwargs["findings"]))
        return False

    with patch.object(engine, "_llm_tier_engaged", side_effect=capture_route):
        engine.review(
            text=text,
            source_jurisdiction=labels["source_jurisdiction"],
            destination_jurisdiction=labels["destination_jurisdiction"],
            entity_id=None,
            include_suggestions=False,
        )
    assert eligibility == [True]
    assert audit_grade_cost_estimate(corpus=tmp_path)["audit_grade_eligible_docs"] == 1


def test_teacher_collection_records_contextual_states_without_legacy_labels(tmp_path, monkeypatch):
    from training.distillation.teacher_collector import CorpusDoc, _resolve_adjudicator, collect

    monkeypatch.setenv("JUNAS_CACHE_DIR", str(tmp_path / "cache"))
    output = tmp_path / "teacher.jsonl"
    doc = CorpusDoc("example", TEXT, "generic", "SG", "SG", "synthetic")
    assert collect(
        docs=[doc], output=output, adjudicator=_resolve_adjudicator("mock"), input_mode="structured_tokens", force=False
    ) == (1, 0)
    row = json.loads(output.read_text())
    assert "deterministic_classification" not in row
    assert row["deterministic_sensitivity"]["mnpi"]["state"] == "present"
    assert json.loads(row["user_content"])["current_classification"] == "present"
