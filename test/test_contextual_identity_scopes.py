import pytest

from test.test_sensitivity import review


@pytest.mark.parametrize(
    "text,name",
    [
        ("The advice names Liora Fen Cai (date of birth: 12 May 1985; verification ref. VZ-812).", "Liora Fen Cai"),
        ("Respondent Elin Voss Lin (respondent reference RX-761; elin.voss@example.test) replied.", "Elin Voss Lin"),
        ("Maren Sol, the buyer’s treasury contact (maren.sol@example.test), replied.", "Maren Sol"),
        ("The seller’s representative, Anya Vale (party ref. PX-761), replied.", "Anya Vale"),
        ("Submissions clerk Eila Fen is checking the acknowledgements.", "Eila Fen"),
        ("Recall coordinator Ana Voss (fictional NRIC S1234567D) confirmed the count.", "Ana Voss"),
        ("Seller representative Eira Vale Sol (party ID EV-751; eira.vale.sol@example.test) replied.", "Eira Vale Sol"),
    ],
)
def test_person_roles_and_parenthetical_identity_fields_anchor_exact_names(text, name):
    items = review(text).sensitivity["pii"]["evidence"]
    assert any(s["label"] == "PERSON_NAME" and s["matched_text"] == name for s in items)
    assert all(text[s["start_char"] : s["end_char"]] == s["matched_text"] for s in items)


def test_new_person_fields_ground_contacts_and_references_without_assuming_numeric_addresses_are_ids():
    text = (
        "Seller representative Eira Vale Sol (party ID EV-751; eira.vale.sol@example.test). "
        "Her US callback is +1 202-555-0186. Her personal Cedar Bank account, no. 914-258-6321. "
        "Respondent reference RC-879 is on her record."
    )
    values = {(s["label"], s["matched_text"]) for s in review(text).sensitivity["pii"]["evidence"]}
    assert {
        ("PERSONAL_RECORD_ID", "EV-751"),
        ("EMAIL", "eira.vale.sol@example.test"),
        ("PHONE", "+1 202-555-0186"),
        ("BANK_ACCOUNT", "914-258-6321"),
        ("PERSONAL_RECORD_ID", "RC-879"),
    } <= values
    negative = (
        "The fictional Alder Bridge Exchange asked for feedback. "
        "Illustrative corporate correspondence: 27 Invented Quay, #04-05, Singapore 123456. "
        "Corporate record RX-345 is a template reference."
    )
    assert review(negative).sensitivity["pii"]["state"] == "not_detected"
    assert any(s["matched_text"] == "18" for s in review("Staff ID: 18").sensitivity["pii"]["evidence"])


@pytest.mark.parametrize("local", ["recalls", "recalls-alder", "shareplans", "consultations", "escrow"])
def test_function_mailboxes_are_excluded_even_when_they_resemble_personal_email_names(local):
    result = review(f"Responses go to {local}@example.test.").sensitivity["pii"]
    assert result["state"] == "not_detected"
    assert result["excluded"] and not result["evidence"]


def test_product_identifier_scope_is_explicit_and_does_not_bleed_into_worker_identity():
    product = (
        "The carton proof shows “ID No. S1234567D” beside the batch barcode. "
        "Operations confirmed that this is the artwork reference for the label."
    )
    assert review(product).sensitivity["pii"]["state"] == "not_detected"
    personal = "Name: Elin Vale\nNRIC: S1234567D\nShe checked a separate product reference on the carton proof."
    assert any(s["label"] == "GOVERNMENT_ID" for s in review(personal).sensitivity["pii"]["evidence"])
    corporate = "Client name: Elin Vale\nCorporate Cedar Bank account, no. 914-258-6321"
    assert not any(s["label"] == "BANK_ACCOUNT" for s in review(corporate).sensitivity["pii"]["evidence"])


@pytest.mark.parametrize("month", ["April 1991", "Apr 1991", "December 1984"])
def test_birth_month_and_linked_work_locality_attributes_preserve_minimal_spans(month):
    detail = f"born in {month}, resident in postal district 12 and assigned to the evening payroll desk"
    text = f"Client name: Elin Vale. Her personnel record says {detail}."
    items = review(text).sensitivity["pii"]["evidence"]
    assert any(s["label"] == "DATE_OF_BIRTH" and s["matched_text"] == month for s in items)
    assert any(s["label"] == "QUASI_IDENTIFIER_COMBINATION" and s["matched_text"] == detail for s in items)
    assert all(text[s["start_char"] : s["end_char"]] == s["matched_text"] for s in items)


def test_redacted_person_can_still_be_singled_out_by_age_locality_and_unique_job():
    detail = (
        "42-year-old resident of Alder Court who joined in April 2019 "
        "and is the issuer’s only overnight payroll supervisor"
    )
    items = review(f"The redacted employee record describes a {detail}.").sensitivity["pii"]["evidence"]
    assert any(s["label"] == "QUASI_IDENTIFIER_COMBINATION" and s["matched_text"] == detail for s in items)


@pytest.mark.parametrize("separator", ["\n\n", "\r\n\r\n", "\n \n"])
def test_generic_prose_attribute_template_cannot_borrow_a_person_from_another_paragraph(separator):
    detail = "born in April 1991, resident in postal district 12 and assigned to the evening payroll desk"
    text = f"Client name: Elin Vale.{separator}Template example: {detail}."
    assert not any(s["label"] == "QUASI_IDENTIFIER_COMBINATION" for s in review(text).sensitivity["pii"]["evidence"])


def test_multi_part_email_can_link_to_a_distant_name_within_the_same_paragraph_only():
    opening = "Eira Vale-Sol (staff ref. ES-712) confirmed receipt. "
    text = opening + "The attendance confirmation remains filed for reconciliation. " * 5
    text += "The confirmation was sent to eira.vale-sol@example.test."
    items = review(text).sensitivity["pii"]["evidence"]
    assert any(s["label"] == "EMAIL" and s["matched_text"] == "eira.vale-sol@example.test" for s in items)
    isolated = opening + "\n\nUnknown address: eira.vale-sol@example.test"
    assert not any(s["label"] == "EMAIL" for s in review(isolated).sensitivity["pii"]["evidence"])
