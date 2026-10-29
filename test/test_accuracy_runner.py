import json

import pytest

from scripts.evaluate_accuracy import evaluate_corpus, main


def test_missing_corpus_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="no labelled documents"):
        evaluate_corpus(tmp_path)


def test_missing_labels_are_not_silently_excluded(tmp_path):
    (tmp_path / "example.txt").write_text("Contact alice@example.com")
    with pytest.raises(ValueError, match="missing labels"):
        evaluate_corpus(tmp_path)


def test_measurement_keeps_real_misses_and_does_not_create_a_lock(tmp_path):
    (tmp_path / "example.txt").write_text("Contact alice@example.com")
    labels = {
        "doc_id": "example",
        "must_detect": [
            {"rule": "email_address", "matched_text": "alice@example.com"},
            {"rule": "sg_nric_fin", "matched_text": "S1234567D"},
        ],
    }
    (tmp_path / "example.labels.json").write_text(json.dumps(labels))
    report = evaluate_corpus(tmp_path)
    assert report["summary"]["matched"] == 1
    assert report["summary"]["missed"] == 1
    assert not report["regression_gate"]["passed"]
    assert not list(tmp_path.glob("*.lock.json"))


def test_failed_evaluation_writes_failure_report(tmp_path):
    output = tmp_path / "report.json"
    assert main(["--corpus", str(tmp_path), "--output", str(output), "--external", "skip"]) == 1
    report = json.loads(output.read_text())
    assert not report["regression_gates_passed"]
    assert "no labelled documents" in report["error"]


def test_required_external_data_cannot_silently_pass(tmp_path, monkeypatch):
    import scripts.evaluate_accuracy as runner

    monkeypatch.setattr(runner, "external_status", lambda: {"tab": {"available": False}})
    monkeypatch.setattr(
        runner,
        "evaluate_corpus",
        lambda _: {
            "regression_gate": {"passed": True},
            "summary": {"doc_count": 1, "candidate_recall": 1, "candidate_precision": 1, "candidate_f2": 1},
        },
    )
    output = tmp_path / "report.json"
    assert main(["--corpus", str(tmp_path), "--output", str(output), "--external", "require"]) == 1
    report = json.loads(output.read_text())
    assert report["regression_gates_passed"]
    assert not report["run_passed"]
    assert report["external"]["tab"]["status"] == "missing_fixture"
