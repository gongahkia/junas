import json
from unittest.mock import patch

import pytest

from scripts.check_reliability import ENTITY_CASES, cases, check
from scripts.corpus_report import release_holdout
from scripts.model_corpus import QUADRANTS


def test_all_quadrants_and_all_nine_entities_have_positive_and_negative_regressions():
    rows = cases()
    assert len(rows) == 72
    assert {(r["quadrant"], r["entity_type"]) for r in rows} == {
        (q, label) for q in QUADRANTS for label in ENTITY_CASES
    }
    report = check()
    assert report["passed"], report["failures"]
    assert report["independently_validated_accuracy"] is None
    assert report["calibrated_confidence"] is None
    assert all(stats["entity_exact_hit"] == 4 for stats in report["by_entity"].values())


def test_gate_fails_when_contextual_detector_stops_finding_entities():
    from junas.review import sensitivity as module

    with patch.object(module, "contextual_pii", return_value=([], [])):
        report = check()
    assert not report["passed"]
    assert any(f["kind"] == "pii_fn" for f in report["failures"])


def test_holdout_release_is_once_and_records_frozen_classifier(tmp_path):
    run = tmp_path / "held"
    run.mkdir()
    from scripts.model_corpus import consensus, identity, input_identity
    from test.test_model_corpus import annotation, config

    cfg = config()
    (run / "manifest.json").write_text(
        json.dumps({"sampling": {"split": "holdout"}, "config": cfg, "config_sha256": identity(cfg)})
    )
    text = "Mr Alex called Mr Alex.\r\n"
    annotated = annotation()
    records = [
        {
            "split": "holdout",
            "template_group": "holdout-research-v1",
            "text": text,
            "text_sha256": input_identity(text),
            "document_id": "held-1",
            "annotations": [{"output": annotated} for _ in range(3)],
            "consensus": consensus([annotated] * 3),
            "accepted": True,
            "status": "completed",
        }
    ]
    (run / "combined-records.jsonl").write_text(json.dumps(records[0]) + "\n")
    dev = [{"text": "Different development source", "template_group": "dev-intake-v1"}]
    with patch("scripts.corpus_report.evaluate_records", return_value={"reference": "mocked"}) as evaluate:
        release_holdout(run, dev, tmp_path / "report.json")
    assert evaluate.call_args.args[0][0]["split"] == "released_holdout"
    marker = json.loads((run / "holdout-consumed.json").read_text())
    assert marker["classifier"]["classifier_sha256"]
    with pytest.raises(FileExistsError):
        release_holdout(run, dev, tmp_path / "again.json")


def test_cost_review_is_offline_and_includes_previous_spending():
    from scripts.corpus_cost_review import review

    with patch("httpx.Client", side_effect=AssertionError("network forbidden")):
        report = review()
    assert report["paid_calls_made"] == 0 and not report["live_calls_authorized"]
    assert report["proposed_combined_additional_cap_usd"] == "10"
    assert report["aggregate_prior_plus_proposed_sgd_scenario"] == "32.760"
    assert report["within_allowance_scenario"]


def test_offline_development_report_records_source_and_dataset_identity(tmp_path):
    from scripts.corpus_report import main

    records, output = tmp_path / "empty.jsonl", tmp_path / "report.json"
    records.write_text("")
    args = ["corpus_report.py", "development", "--records", str(records), "--output", str(output)]
    with patch("sys.argv", args), patch("httpx.Client", side_effect=AssertionError("network forbidden")):
        assert main() == 0
    report = json.loads(output.read_text())
    assert report["inputs_sha256"]
    assert report["reproducibility"]["classifier_sha256"]
    assert report["independently_validated_accuracy"] is None
