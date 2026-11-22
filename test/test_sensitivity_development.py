import json
from unittest.mock import patch

import pytest

from scripts.evaluate_sensitivity import scorecard
from scripts.model_corpus import consensus, input_identity
from test.test_model_corpus import TEXT, annotation


def records():
    a = annotation()
    return [
        {
            "document_id": "dev",
            "text": TEXT,
            "text_sha256": input_identity(TEXT),
            "status": "completed",
            "accepted": True,
            "annotations": [{"output": a}] * 3,
            "consensus": consensus([a] * 3),
        }
    ]


def mocked_evaluation():
    counts = {"tp": 1, "fn": 0, "fp": 0, "tn": 1, "unknown": 2}
    return {
        "contextual_document_presence": {
            "counts": {c: counts for c in ("pii", "mnpi")},
            "by_quadrant": {
                q: {c: {"unknown": 1 if q in {"both", "neither"} else 0} for c in ("pii", "mnpi")}
                for q in ("both", "neither", "pii_only", "mnpi_only")
            },
        },
        "contextual_pii": {mode: {"gold": 2, "matched": 1} for mode in ("exact", "overlap")},
    }


def test_gate_counts_abstentions_against_positive_detection_and_negative_coverage():
    with patch("scripts.evaluate_sensitivity.corpus.evaluate_records", return_value=mocked_evaluation()):
        result = scorecard(records(), {"pii_positive_detection_min": 0.9, "pii_negative_abstention_rate_max": 0.25})
    assert not result["passed"]
    assert result["measurements"]["pii_positive_detection"] == 0.5
    assert result["measurements"]["pii_negative_abstention_rate"] == 0.5


@pytest.mark.parametrize("split", ["holdout", "released_holdout", "test"])
def test_gate_refuses_holdout_and_other_splits(split):
    with pytest.raises(ValueError, match="holdout refused"):
        scorecard([dict(records()[0], split=split)], {})


def test_gate_rejects_label_changes_and_bad_thresholds():
    data = records()
    data[0]["consensus"]["quadrant"] = "both"
    with pytest.raises(ValueError, match="consensus mismatch"):
        scorecard(data, {})
    with patch("scripts.evaluate_sensitivity.corpus.evaluate_records", return_value=mocked_evaluation()):
        for threshold in [float("nan"), True, -0.1, 1.1, "1"]:
            with pytest.raises(ValueError):
                scorecard(records(), {"pii_positive_detection_min": threshold})
        with pytest.raises(ValueError, match="unknown engineering"):
            scorecard(records(), {"invented_accuracy_min": 0.5})


def test_targets_are_checked_in_before_detector_tuning():
    from scripts.evaluate_sensitivity import ROOT

    targets = json.loads((ROOT / "config/sensitivity-development-gates.json").read_text())
    assert targets["pii_exact_span_agreement_min"] == 0.8
    assert targets["mnpi_positive_detection_min"] == 0.8
