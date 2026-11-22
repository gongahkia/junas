"""Contextual predictions never replace broad signal scores."""

from types import SimpleNamespace

from junas.review.engine import PreSendReviewEngine
from junas.review.sensitivity import sensitivity


def review(text):
    return PreSendReviewEngine().review(
        text=text, source_jurisdiction="SG", destination_jurisdiction="SG", entity_id=None, include_suggestions=False
    )


def test_shared_email_remains_signal_but_not_personal_target():
    text = "support@example.test"
    output = sensitivity(
        text,
        [SimpleNamespace(category="PII", rule="email_address", start_char=0, end_char=len(text), matched_text=text)],
    )
    assert output["pii"]["state"] == "not_detected"
    assert output["pii"]["excluded"]
    assert not output["absence_verified"]


def test_personal_email_and_mnpi_signal_are_distinct_targets():
    result = review("Email alex.chen@example.test. Confidential financial amount SGD 50 million.")
    assert result.sensitivity["pii"]["state"] == "present"
    assert result.sensitivity["mnpi"]["state"] == "unknown"
    for item in result.sensitivity["pii"]["evidence"]:
        assert (
            item["matched_text"]
            == "Email alex.chen@example.test. Confidential financial amount SGD 50 million."[
                item["start_char"] : item["end_char"]
            ]
        )
