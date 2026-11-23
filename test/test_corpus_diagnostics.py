from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.corpus_diagnostics import diagnose


def test_buckets_distinguish_missing_boundary_and_unknown_coverage():
    text = "Alex calls Bea; extra"
    record = {
        "document_id": "d",
        "accepted": True,
        "status": "completed",
        "text": text,
        "consensus": {
            "pii": [
                {"start_char": 0, "end_char": 4, "label": "PERSON_NAME"},
                {"start_char": 11, "end_char": 14, "label": "PERSON_NAME"},
            ],
            "coverage": "unknown",
            "quadrant": "pii_only",
            "document_labels": {"pii": {"state": "present"}, "mnpi": {"state": "absent"}},
        },
    }
    output = SimpleNamespace(
        findings=[],
        sensitivity={
            "pii": {
                "state": "present",
                "evidence": [
                    {"start_char": 0, "end_char": 5, "label": "PERSON_NAME", "rule": "name"},
                    {"start_char": 16, "end_char": 21, "label": "PERSON_NAME", "rule": "name"},
                ],
            },
            "mnpi": {"state": "not_detected"},
        },
    )
    with patch("scripts.corpus_diagnostics.PreSendReviewEngine.review", return_value=output):
        report = diagnose([record])
    assert report["counts"] == {"boundary_error": 1, "missed_entity": 1, "unjudged_prediction": 1}
    output.sensitivity["mnpi"]["state"] = "unknown"
    with patch("scripts.corpus_diagnostics.PreSendReviewEngine.review", return_value=output):
        report = diagnose([record])
    assert report["details"][0]["buckets"][-1] == {
        "kind": "mnpi_abstention",
        "expected": "absent",
        "observed": "unknown",
    }


def test_diagnostics_refuse_holdout():
    with pytest.raises(ValueError, match="holdout"):
        diagnose([{"split": "holdout"}])
