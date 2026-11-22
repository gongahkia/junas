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


def test_sparse_identifier_types_have_exact_person_linked_evidence():
    text = (
        "Client name: Noor Tay\nPersonal bank account number: 123-456-789\n"
        "Passport number: X1234567\nPersonal mobile: +65 8123 4567\n"
        "Client staff ID: PT-7821; direct extension 418\n"
        "Home address: 28 Example Road, Singapore\n"
        "Only resident uniquely identified: Age: 41; postal code: 123456; occupation: archivist"
    )
    evidence = review(text).sensitivity["pii"]["evidence"]
    labels = {s["label"] for s in evidence}
    assert {"BANK_ACCOUNT", "PHONE", "GOVERNMENT_ID", "POSTAL_ADDRESS", "QUASI_IDENTIFIER_COMBINATION"} <= labels
    for s in evidence:
        assert text[s["start_char"] : s["end_char"]] == s["matched_text"]


def test_corporate_and_generic_lookalikes_are_not_personal_fields():
    text = (
        "Company bank account number: 123-456-789\nPublic hotline telephone: +65 6123 4567\n"
        "Corporate passport number: X1234567\nOffice mailing address: 28 Example Road\n"
        "Age: 41; postal code: 123456; occupation: archivist"
    )
    assert not any(s["rule"].startswith("contextual_") for s in review(text).sensitivity["pii"]["evidence"])


def test_mnpi_does_not_join_different_issuers_or_unrelated_private_claims():
    for text in [
        "Cedar Vale Ltd. has a material acquisition. Birch Grove Ltd. has not been publicly disclosed.",
        "Cedar Vale Ltd. has a material acquisition. The unrelated service memo has not been publicly disclosed.",
        "Cedar Vale Ltd. has a material acquisition. The employee rota has not been publicly disclosed.",
    ]:
        assert review(text).sensitivity["mnpi"]["state"] != "present"


def test_prose_person_names_shortened_references_and_personal_record_aliases():
    text = (
        "Director Amira Vale Wen (portal ID DIR-ZZ-591; amira.vale@example.test) requested paper copies. "
        "Amira’s reply named Theo Marsh (staff ref. ZZ-832). Ms Vale requested a receipt. "
        "The client record names “Amira Vale”."
    )
    pii = review(text).sensitivity["pii"]["evidence"]
    assert {"Amira Vale Wen", "Theo Marsh", "Amira", "Vale", "Amira Vale"} <= {
        s["matched_text"] for s in pii if s["label"] == "PERSON_NAME"
    }
    assert {"DIR-ZZ-591", "ZZ-832"} <= {s["matched_text"] for s in pii if s["label"] == "PERSONAL_RECORD_ID"}
    assert all(text[s["start_char"] : s["end_char"]] == s["matched_text"] for s in pii)


def test_unlabelled_name_anchored_by_person_action_and_government_field():
    text = "Nalini Moss Wen (NRIC: T1234567A) requested an account update. She confirmed the spelling."
    assert any(
        s["matched_text"] == "Nalini Moss Wen" and s["label"] == "PERSON_NAME"
        for s in review(text).sensitivity["pii"]["evidence"]
    )


def test_client_case_reference_requires_individual_linkage():
    positive = "Individual client intake | Matter ZQ-108. Client capacity: prospective investor."
    negative = "Corporate board memorandum | Matter ZQ-108. General governance enquiries only."
    assert any(s["matched_text"] == "ZQ-108" for s in review(positive).sensitivity["pii"]["evidence"])
    assert not any(s["matched_text"] == "ZQ-108" for s in review(negative).sensitivity["pii"]["evidence"])


def test_capitalized_organization_titles_and_city_are_not_person_names():
    text = "Company name: Cedar Vale Systems Ltd.\nFrom: Singapore Corporate Secretariat\nGeneral Board Memorandum"
    assert not any(s["label"] == "PERSON_NAME" for s in review(text).sensitivity["pii"]["evidence"])


def test_prose_contacts_belong_to_person_despite_company_in_sentence():
    text = (
        "The company secretary recorded director Amira Vale’s preferred number as +65 8111 2233. "
        "Her correspondence address is 71 Invented Fern Lane, #03-09, Singapore 123456. "
        "Her personal bank account (Example Bank, account no. 123-456-789) receives refunds."
    )
    items = review(text).sensitivity["pii"]["evidence"]
    assert {"+65 8111 2233", "71 Invented Fern Lane, #03-09, Singapore 123456", "123-456-789"} <= {
        s["matched_text"] for s in items
    }


def test_role_mailboxes_and_corporate_identifier_lookalikes_are_excluded():
    text = (
        "Individual intake guidance: the mock company reference is T1234567A. "
        "It does not identify an applicant. Contact intake@example.test, payroll-ops@example.test, "
        "or brand-disclosures@example.test. Registered office: 71 Invented Fern Lane, Singapore 123456."
    )
    assert review(text).sensitivity["pii"]["state"] == "not_detected"


def test_quasi_identifier_requires_person_linkage_and_preserves_source():
    text = "Individual client intake. Client capacity: treasury analyst at Cedar Vale Ltd."
    items = review(text).sensitivity["pii"]["evidence"]
    assert any(
        s["label"] == "QUASI_IDENTIFIER_COMBINATION" and s["matched_text"] == "treasury analyst at Cedar Vale Ltd"
        for s in items
    )
    generic = "The policy explains what a treasury analyst at Cedar Vale Ltd. does."
    assert not any(s["label"] == "QUASI_IDENTIFIER_COMBINATION" for s in review(generic).sensitivity["pii"]["evidence"])


def test_company_mailer_and_template_case_ids_are_not_personal_identifiers():
    text = (
        "Individual client intake research. Template ref. QZ-571. "
        "A specimen shareholder circular lists Corporate Secretariat, 51 Imaginary Grove, Singapore 123456. "
        "Payroll Operations (payroll@example.test) handles generic queries. No individual particulars were recorded."
    )
    assert review(text).sensitivity["pii"]["state"] == "not_detected"


def test_repeated_names_use_exact_offsets_without_duplicate_aliases():
    text = "Client name: Élodie Moss\n" * 200
    from junas.review.contextual_people import person_names

    names = person_names(text)
    assert len(names) == 200
    assert len({(n["start_char"], n["end_char"]) for n in names}) == 200
    assert all(n["matched_text"] == "Élodie Moss" for n in names)


def test_structured_contacts_support_compound_names_and_masked_ids():
    text = (
        "Contact: Vale Mei Wen, Amira\nEmail: amira.vale-wen@example.test\n"
        "Staff ID (sender): HM-Z8-271\nNRIC on file: T••••123B\n"
        "Mailing address: 12 Invented Shore Rise, #09-02, Singapore\n"
        "The email was signed “V. Mei”. Her date of birth (18 June 1986) is on file."
    )
    items = review(text).sensitivity["pii"]["evidence"]
    values = {s["matched_text"] for s in items}
    assert {
        "Vale Mei Wen, Amira",
        "amira.vale-wen@example.test",
        "HM-Z8-271",
        "T••••123B",
        "12 Invented Shore Rise, #09-02, Singapore",
        "18 June 1986",
    } <= values


def test_repeated_personal_record_identifier_keeps_both_occurrences():
    text = "Client name: Anika Moss. Contact record ID: ZZ-123-AB. Please quote ZZ-123-AB in the reply."
    spans = [s for s in review(text).sensitivity["pii"]["evidence"] if s["matched_text"] == "ZZ-123-AB"]
    assert len(spans) == 2


def test_generic_editorial_roles_and_mailboxes_are_not_persons():
    text = (
        "From: Research Counsel <research-desk@example.test>\nTo: Library Review <review@example.test>\n"
        "Nerali Policy Forum prepared general guidance. Comments: policy-desk@example.test."
    )
    assert review(text).sensitivity["pii"]["state"] == "not_detected"


def test_contact_reference_is_person_linked_and_repeated_occurrences_are_retained():
    text = (
        "The register lists Amara Sol Mendez (contact ref. CP-Z892; amara.mendez@example.test). "
        "The follow-up repeats CP-Z892.\nClient contact ID: CV-003-47"
    )
    items = review(text).sensitivity["pii"]["evidence"]
    assert any(s["label"] == "PERSON_NAME" and s["matched_text"] == "Amara Sol Mendez" for s in items)
    assert sum(s["matched_text"] == "CP-Z892" for s in items) == 2
    assert any(s["label"] == "PERSONAL_RECORD_ID" and s["matched_text"] == "CV-003-47" for s in items)
    corporate = "Company contact reference: CO-08912. Corporate contact ID: CO-01811."
    assert review(corporate).sensitivity["pii"]["state"] == "not_detected"
