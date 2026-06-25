"""Items 78 + 99: pseudonymised-but-linkable identifier detectors.

Universal PII rules in `engine.py`:
    employee_id              (medium standalone)
    customer_account_number  (medium standalone)
    medical_record_number    (high standalone — special-category)
    internal_session_id      (medium standalone)
    bank_customer_reference  (medium standalone)
    insurance_member_id      (medium standalone)

`_amplify_pseudonymised_when_linked` escalates medium standalone rules to high when a
named_person finding co-occurs anywhere in the same document. medical_record_number is
already high standalone — escalation is a no-op for it.

Citation: GDPR Recital 26 + PDPC Anonymisation Advisory Guidelines treat IDs the
controller can re-link to a subject as personal data.
"""

import unittest

from kaypoh.review.citations import pii_rationale
from kaypoh.review.engine import PreSendReviewEngine


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings(self, text: str, document_type: str = "generic", source: str = "SG", destination: str = "SG"):
        return self.engine.review(
            text=text,
            source_jurisdiction=source,
            destination_jurisdiction=destination,
            entity_id=None,
            include_suggestions=False,
            document_type=document_type,
            review_profile="strict",
        ).findings

    def _by_rule(self, text: str, rule: str, **kw):
        return [f for f in self._findings(text, **kw) if f.rule == rule]


class EmployeeIdRecallTests(_Base):
    def test_employee_id_anchor_colon_form(self):
        f = self._by_rule("Employee ID: EMP-12345 has been onboarded.", "employee_id")
        self.assertEqual(len(f), 1)
        self.assertTrue(f[0].matched_text)

    def test_employee_no_anchor(self):
        f = self._by_rule("Employee No. 4567890 reports to HR.", "employee_id")
        self.assertEqual(len(f), 1)

    def test_emp_prefix_form(self):
        f = self._by_rule("Reference EMP-AB12345 in the ledger.", "employee_id")
        self.assertEqual(len(f), 1)

    def test_staff_id_anchor(self):
        f = self._by_rule("Staff ID 778899 was assigned access.", "employee_id")
        self.assertEqual(len(f), 1)


class EmployeeIdPrecisionTests(_Base):
    def test_employee_id_followed_by_lowercase_prose_does_not_fire(self):
        # the case in test/fixtures/legal-corpus-adversarial/employment_letter_adv_07.txt:
        # "your employee ID will be linked to your NRIC". Without case-sensitive capture +
        # digit lookahead, "will" would false-positive as the ID.
        f = self._by_rule(
            "Your employee ID will be linked to your NRIC for verification.",
            "employee_id",
        )
        self.assertEqual(f, [],
                         f"prose 'employee ID will be...' must not match: {f!r}")

    def test_employee_id_without_digit_does_not_fire(self):
        # capture requires \d in lookahead — purely alpha ID after anchor is rejected.
        f = self._by_rule("Employee ID: ABCDEF was deactivated.", "employee_id")
        self.assertEqual(f, [])


class CustomerAccountRecallTests(_Base):
    def test_customer_account_anchor(self):
        f = self._by_rule("Customer Account: CUST-998877 unpaid.", "customer_account_number")
        self.assertEqual(len(f), 1)

    def test_acct_prefix(self):
        f = self._by_rule("Charged via ACCT-12345678 last cycle.", "customer_account_number")
        self.assertEqual(len(f), 1)

    def test_member_id_anchor(self):
        f = self._by_rule("Member ID 4001234 expires soon.", "customer_account_number")
        self.assertEqual(len(f), 1)

    def test_customer_reference_anchor(self):
        f = self._by_rule("Customer Reference ABC-998877.", "customer_account_number")
        self.assertEqual(len(f), 1)


class CustomerAccountPrecisionTests(_Base):
    def test_lowercase_prose_after_anchor_does_not_fire(self):
        f = self._by_rule(
            "Each customer account will be migrated to the new platform.",
            "customer_account_number",
        )
        self.assertEqual(f, [])

    def test_no_digit_id_does_not_fire(self):
        f = self._by_rule("Customer Account: ALPHA exists in the ledger.", "customer_account_number")
        self.assertEqual(f, [])


class MedicalRecordRecallTests(_Base):
    def test_mrn_colon_form(self):
        f = self._by_rule("MRN: 1234567 admitted Tuesday.", "medical_record_number")
        self.assertEqual(len(f), 1)

    def test_medical_record_no_form(self):
        f = self._by_rule("Medical Record No. 9988776 transferred.", "medical_record_number")
        self.assertEqual(len(f), 1)

    def test_patient_id_form(self):
        f = self._by_rule("Patient ID 778899 has scheduled.", "medical_record_number")
        self.assertEqual(len(f), 1)


class MedicalRecordPrecisionTests(_Base):
    def test_mrn_word_without_digits_does_not_fire(self):
        f = self._by_rule("Patient ID badges are blue this year.", "medical_record_number")
        self.assertEqual(f, [])


class InternalSessionRecallTests(_Base):
    def test_session_id_labelled_uuid(self):
        f = self._by_rule(
            "Session ID: 550e8400-e29b-41d4-a716-446655440000 was opened.",
            "internal_session_id",
        )
        self.assertEqual(len(f), 1)

    def test_suffixed_session_uuid(self):
        f = self._by_rule(
            "Audit token 550e8400-e29b-41d4-a716-446655440000_session was exported.",
            "internal_session_id",
        )
        self.assertEqual(len(f), 1)


class InternalSessionPrecisionTests(_Base):
    def test_bare_uuid_does_not_fire(self):
        f = self._by_rule(
            "Reference 550e8400-e29b-41d4-a716-446655440000 appears in the log.",
            "internal_session_id",
        )
        self.assertEqual(f, [])

    def test_session_id_prose_without_uuid_does_not_fire(self):
        f = self._by_rule("The session ID will be rotated after logout.", "internal_session_id")
        self.assertEqual(f, [])


class BankCustomerReferenceTests(_Base):
    def test_bank_cif_label_fires(self):
        f = self._by_rule("Bank CIF: CIF-778899 remains restricted.", "bank_customer_reference")
        self.assertEqual(len(f), 1)

    def test_customer_information_file_fires(self):
        f = self._by_rule(
            "Customer information file number BCR-2026-001 is in the annex.",
            "bank_customer_reference",
        )
        self.assertEqual(len(f), 1)

    def test_bank_reference_prose_does_not_fire(self):
        f = self._by_rule("The bank reference material was updated.", "bank_customer_reference")
        self.assertEqual(f, [])


class InsuranceMemberIdTests(_Base):
    def test_insurance_member_id_fires(self):
        f = self._by_rule("Insurance member ID: IM-778899 was added.", "insurance_member_id")
        self.assertEqual(len(f), 1)

    def test_policy_member_number_fires(self):
        f = self._by_rule("Policy member number PM-2026-001 is in the claims file.", "insurance_member_id")
        self.assertEqual(len(f), 1)

    def test_insurance_member_id_does_not_double_count_customer_rule(self):
        text = "Insurance member ID: IM-778899 was added."
        self.assertEqual(self._by_rule(text, "customer_account_number"), [])
        self.assertEqual(len(self._by_rule(text, "insurance_member_id")), 1)

    def test_member_benefits_prose_does_not_fire(self):
        f = self._by_rule("The member benefits guide explains coverage tiers.", "insurance_member_id")
        self.assertEqual(f, [])


class NamedPersonAmplifierTests(_Base):
    """Item 99 amplifier: medium → high when a named_person co-occurs in the same document."""

    def test_employee_id_alone_stays_medium(self):
        f = self._by_rule("Employee ID: EMP-12345 onboarded today.", "employee_id")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "medium",
                         f"alone, employee_id should be medium; got {f[0].severity}")

    def test_employee_id_with_named_person_escalates_to_high(self):
        text = "Dr Jane Tan was assigned Employee ID: EMP-12345 yesterday."
        f = self._by_rule(text, "employee_id")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high",
                         f"named_person co-occurrence should escalate; got {f[0].severity}")
        self.assertIn("re-link", f[0].reason.lower())

    def test_customer_account_alone_stays_medium(self):
        f = self._by_rule("Customer Account: CUST-998877 is overdue.", "customer_account_number")
        self.assertEqual(f[0].severity, "medium")

    def test_customer_account_with_named_person_escalates(self):
        text = "Mr Lee Wei Ming holds Customer Account: CUST-998877."
        f = self._by_rule(text, "customer_account_number")
        self.assertEqual(f[0].severity, "high")

    def test_medical_record_is_already_high_alone(self):
        # MRN ships at high standalone; the amplifier is a no-op for it.
        f = self._by_rule("MRN: 1234567 admitted Tuesday.", "medical_record_number")
        self.assertEqual(f[0].severity, "high")

    def test_internal_session_with_named_person_escalates(self):
        text = "Ms Lina Koh used Session ID: 550e8400-e29b-41d4-a716-446655440000."
        f = self._by_rule(text, "internal_session_id")
        self.assertEqual(f[0].severity, "high")

    def test_bank_customer_reference_with_named_person_escalates(self):
        text = "Mr Lee Wei Ming has Bank CIF: CIF-778899."
        f = self._by_rule(text, "bank_customer_reference")
        self.assertEqual(f[0].severity, "high")

    def test_insurance_member_id_with_named_person_escalates(self):
        text = "Dr Sarah Lim holds Insurance member ID: IM-778899."
        f = self._by_rule(text, "insurance_member_id")
        self.assertEqual(f[0].severity, "high")

    def test_far_apart_named_person_still_amplifies(self):
        # The amplifier is document-scoped, not ±200 chars — the named_person and ID can be
        # paragraphs apart and the linkage risk still holds.
        text = (
            "Dr Sarah Lim joined the firm last quarter. "
            + ". ".join(["Quarterly review continued"] * 30)
            + ". Employee ID: EMP-99999 was assigned during onboarding."
        )
        f = self._by_rule(text, "employee_id")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")


class PseudonymisedCitationTests(unittest.TestCase):
    def test_employee_id_citation_carries_gdpr_recital_26(self):
        text = pii_rationale(rule="employee_id", jurisdiction="EU", matched_text="EMP-12345")
        self.assertIn("Recital 26", text)
        self.assertIn("PDPC", text)

    def test_customer_account_citation_carries_pdpc(self):
        text = pii_rationale(rule="customer_account_number", jurisdiction="SG", matched_text="CUST-12345")
        self.assertIn("PDPC", text)

    def test_medical_record_citation_carries_hipaa_and_art_9(self):
        text = pii_rationale(rule="medical_record_number", jurisdiction="US", matched_text="1234567")
        self.assertIn("HIPAA", text)
        self.assertIn("Art 9", text)

    def test_internal_session_citation_carries_recital_26(self):
        text = pii_rationale(rule="internal_session_id", jurisdiction="EU", matched_text="session")
        self.assertIn("Recital 26", text)
        self.assertIn("PDPC", text)

    def test_bank_customer_reference_citation_carries_recital_26(self):
        text = pii_rationale(rule="bank_customer_reference", jurisdiction="SG", matched_text="CIF-778899")
        self.assertIn("Recital 26", text)
        self.assertIn("financial", text.lower())

    def test_insurance_member_id_citation_carries_pdpc(self):
        text = pii_rationale(rule="insurance_member_id", jurisdiction="SG", matched_text="IM-778899")
        self.assertIn("PDPC", text)
        self.assertIn("policyholder", text)


if __name__ == "__main__":
    unittest.main()
