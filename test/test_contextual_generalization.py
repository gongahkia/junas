"""Authored variations and controls; not independent validation data."""

import pytest

from test.test_sensitivity import review


@pytest.mark.parametrize("role", ["reviewer was", "attendee", "editor,", "recipient of"])
@pytest.mark.parametrize("name", ["Elara Fen", "Amira Sol Tan", "Élodie Vale"])
def test_role_names_link_record_identifiers_without_consuming_labels(role, name):
    text = f"The {role} {name} (reviewer ref. QX-743; elara.fen@example.test) responded."
    spans = review(text).sensitivity["pii"]["evidence"]
    assert any(s["label"] == "PERSON_NAME" and s["matched_text"] == name for s in spans)
    assert any(s["label"] == "PERSONAL_RECORD_ID" and s["matched_text"] == "QX-743" for s in spans)
    assert all(text[s["start_char"] : s["end_char"]] == s["matched_text"] for s in spans)


@pytest.mark.parametrize("mailbox", ["refunds", "bridge-ops", "education", "licensing", "publications", "settlements"])
def test_business_mailboxes_and_specimen_bank_fields_are_not_personal(mailbox):
    text = (
        "The customer FAQ issued by the Northern Licensing Office has Bank account: "
        f"000-000000-0 on a specimen form. Queries: {mailbox}@example.test."
    )
    assert review(text).sensitivity["pii"]["state"] == "not_detected"


@pytest.mark.parametrize("separator", ["\n\n", "\r\n\r\n", "\n \n"])
def test_person_does_not_ground_a_separate_generic_profile(separator):
    text = (
        "Client name: Elara Fen." + separator + "Template birth month and year (April 1992), home postal sector (53), "
        "and her role as the sole overnight approver."
    )
    assert not any(s["label"] == "QUASI_IDENTIFIER_COMBINATION" for s in review(text).sensitivity["pii"]["evidence"])


def test_uppercase_explicit_person_name_is_preserved():
    assert any(s["matched_text"] == "ALICE" for s in review("Name: ALICE").sensitivity["pii"]["evidence"])


def test_profile_dates_and_contacts_grounded_in_a_person_record():
    text = (
        "Reviewer was Elara Fen (reviewer ref. EF-842). Her birth month and year (April 1992), "
        "home postal sector (53), and her role as the sole overnight approver identify the record. "
        "Personal mobile: +65 5550 0192."
    )
    spans = review(text).sensitivity["pii"]["evidence"]
    assert {"PERSON_NAME", "PERSONAL_RECORD_ID", "DATE_OF_BIRTH", "QUASI_IDENTIFIER_COMBINATION", "PHONE"} <= {
        s["label"] for s in spans
    }
