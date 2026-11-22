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


def test_person_fields_preserve_unicode_repeated_occurrences_and_minimal_boundaries():
    text = "Name: Élodie Tan\r\nName: Élodie Tan\r\nStaff ID: ZX-P0821; Date of birth (verified): 8 November 1988"
    pii = review(text).sensitivity["pii"]["evidence"]
    names = [s for s in pii if s["label"] == "PERSON_NAME"]
    assert [s["matched_text"] for s in names] == ["Élodie Tan", "Élodie Tan"]
    assert len({s["start_char"] for s in names}) == 2
    assert any(s["matched_text"] == "ZX-P0821" and s["label"] == "PERSONAL_RECORD_ID" for s in pii)
    assert any(s["matched_text"] == "8 November 1988" and s["label"] == "DATE_OF_BIRTH" for s in pii)
    assert all(text[s["start_char"] : s["end_char"]] == s["matched_text"] for s in pii)


def test_person_context_does_not_turn_business_fields_or_invalid_dates_into_pii():
    text = "From: Acme Services Ltd.\nContract reference: ZX-0821\nRelease date: 8 November 1988\nDOB: 31 February 1988"
    pii = review(text).sensitivity["pii"]["evidence"]
    assert not any(s["rule"].startswith("contextual_") for s in pii)


def test_unknown_email_association_is_visible_abstention():
    result = review("Address: abc123@example.test")
    assert result.sensitivity["pii"]["state"] == "unknown"


def test_mnpi_requires_issuer_materiality_and_nonpublic_in_same_context():
    text = (
        "Acme Ltd. signed a binding acquisition of all outstanding shares. "
        "It is price-sensitive and has not been publicly disclosed."
    )
    output = review(text).sensitivity["mnpi"]
    assert output["state"] == "present"
    assert not output["public_status_verified"]
    assert {c["kind"] for c in output["evidence"][0]["components"]} == {
        "issuer",
        "event",
        "materiality",
        "claimed_nonpublic",
    }
    for item in output["evidence"]:
        assert text[item["start_char"] : item["end_char"]] == item["matched_text"]
        for part in item["components"]:
            assert text[part["start_char"] : part["end_char"]] == part["matched_text"]


def test_mnpi_does_not_promote_public_hypothetical_negated_or_unlinked_claims():
    for text in [
        "Acme Ltd. publicly announced a material acquisition of all shares.",
        "Hypothetical training example: Acme Ltd. signed a material acquisition not yet publicly disclosed.",
        "Acme Ltd. has no material acquisition; no price-sensitive information has been publicly disclosed.",
        "Acme Ltd. considers an immaterial acquisition not yet publicly disclosed.",
        "Acme Ltd. has a material acquisition.\n\nThe unrelated service rota has not been publicly disclosed.",
        "Acme Ltd. has a material acquisition not yet publicly disclosed, but it was already publicly announced.",
        "The acquisition has not been publicly disclosed.",
    ]:
        assert review(text).sensitivity["mnpi"]["state"] != "present", text
