import unittest
from unittest import mock

from kaypoh.review.detectors.semantic import clear_semantic_pii_state_for_tests
from kaypoh.review.engine import PreSendReviewEngine


class NoCostDetectionBatchTests(unittest.TestCase):
    def _review(self, text: str, jurisdiction: str = "SG"):
        return PreSendReviewEngine().review(
            text=text,
            destination_jurisdiction=jurisdiction,
            source_jurisdiction=jurisdiction,
            entity_id=None,
            include_suggestions=True,
        )

    def _rules(self, text: str, jurisdiction: str = "SG") -> set[str]:
        return {finding.rule for finding in self._review(text, jurisdiction).findings}

    def test_validated_spanish_dni_fires_and_bad_check_digit_does_not(self):
        self.assertIn("eu_national_id", self._rules("Spanish DNI: 12345678Z", "EU"))
        self.assertNotIn("eu_national_id", self._rules("Spanish DNI: 12345678A", "EU"))

    def test_validated_dutch_bsn_and_polish_pesel_fire(self):
        self.assertIn("eu_national_id", self._rules("Dutch BSN: 123456782", "EU"))
        self.assertIn("eu_national_id", self._rules("Polish PESEL: 44051401359", "EU"))

    def test_invalid_member_state_id_shape_is_rejected(self):
        self.assertNotIn("eu_national_id", self._rules("Dutch BSN: 123456789", "EU"))
        self.assertNotIn("eu_national_id", self._rules("Polish PESEL: 44051401358", "EU"))

    def test_conservative_uk_us_hk_address_slices_fire(self):
        self.assertIn("uk_postal_address", self._rules("Send to 221B Baker Street NW1 6XE.", "UK"))
        self.assertIn("us_postal_address", self._rules("Ship to 123 Market Street, CA 94105.", "US"))
        self.assertIn(
            "hk_postal_address",
            self._rules("Flat 7, 12th Floor, Pacific House, Hong Kong.", "HK"),
        )

    def test_multiline_uk_and_us_address_slices_fire(self):
        self.assertIn("uk_postal_address", self._rules("Send to:\n221B Baker Street\nLondon NW1 6XE", "UK"))
        self.assertIn("us_postal_address", self._rules("Ship to:\n123 Market Street\nSan Francisco CA 94105", "US"))
        self.assertIn(
            "au_postal_address",
            self._rules("Registered address:\n1 Airport Drive\nAdelaide Airport SA 5950", "AU"),
        )
        self.assertIn(
            "eu_postal_address",
            self._rules("Domicile:\n12 Rue de la Paix\nParis FR-75002", "EU"),
        )
        self.assertIn(
            "eu_postal_address",
            self._rules("Office:\n12 Kärntner Straße\nVienna AT-1010", "EU"),
        )

    def test_generic_addresses_without_jurisdiction_format_do_not_fire(self):
        text = "Please meet at the office near River Road tomorrow."
        self.assertNotIn("uk_postal_address", self._rules(text, "UK"))
        self.assertNotIn("us_postal_address", self._rules(text, "US"))

    def test_label_anchored_generic_address_fallback_fires(self):
        rules = self._rules("Address: Unit 9, 77 Shenton Way, Singapore 068810.", "SG")

        self.assertIn("postal_address", rules)

    def test_notice_and_invoice_address_labels_fire(self):
        self.assertIn(
            "postal_address",
            self._rules("Notice address: Unit 9, 77 Shenton Way, Singapore 068810.", "SG"),
        )
        self.assertIn(
            "postal_address",
            self._rules("Invoice address: 12 Jalan Ampang, Kuala Lumpur 50450 Malaysia.", "MY"),
        )

    def test_specific_address_rule_takes_precedence_over_generic_fallback(self):
        result = self._review("Registered address: 1 Airport Drive, Adelaide Airport SA 5950.", "AU")
        rules = [finding.rule for finding in result.findings]

        self.assertIn("au_postal_address", rules)
        self.assertNotIn("postal_address", rules)

    def test_generic_address_fallback_rejects_prose(self):
        self.assertNotIn("postal_address", self._rules("Address: the issue 2026 will be discussed.", "SG"))

    def test_broad_unlabelled_address_fallback_fires_when_person_linked(self):
        text = "Employee record: Dr Nur Aisyah\n12 Jalan Ampang\nKuala Lumpur 50450 Malaysia"
        result = self._review(text, "MY")
        findings = [finding for finding in result.findings if finding.rule == "postal_address"]

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["fallback"], "broad_unlabelled_postal_address")

    def test_broad_unlabelled_address_fallback_rejects_org_only_registered_office(self):
        text = "Registered office: 12 Jalan Ampang\nKuala Lumpur 50450 Malaysia"

        self.assertNotIn("postal_address", self._rules(text, "MY"))

    def test_jurisdiction_address_slice_rejects_org_only_registered_office(self):
        text = "Company details: Northway FinTech plc, Registered Office: 4 Ash Lane, Lonton, ZY1 4ZZ."

        self.assertNotIn("uk_postal_address", self._rules(text, "UK"))

    def test_broad_unlabelled_address_fallback_rejects_email_prose(self):
        text = "Send Dr Jane Tan S1234567D at jane@example.com. Acme expects $2.5 billion."

        self.assertNotIn("postal_address", self._rules(text, "SG"))

    def test_broad_unlabelled_address_fallback_rejects_url_prose_window(self):
        text = (
            "URL logs show https://portal.example.com/case/1 and the team reviewed the Singapore disclosure plan.\n"
            "No employee home address is being processed in this incident memo.\n"
            "The market impact estimate is SGD 5000000 before announcement."
        )

        self.assertNotIn("postal_address", self._rules(text, "SG"))

    def test_personal_attribute_inference_fires_with_structure_metadata(self):
        result = self._review("People\nDr Jane Tan works at Acme Pte Ltd.\n", "SG")
        findings = [finding for finding in result.findings if finding.rule == "personal_attribute_inference"]

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["attribute_type"], "employer")
        self.assertEqual(findings[0].metadata["structural_unit_kind"], "paragraph")

    def test_personal_attribute_relationship_and_location_fire(self):
        rules = self._rules("Dr Jane Tan's spouse Mary Lim lives nearby. Mr Alan Goh lives in Bukit Timah.")

        self.assertIn("personal_attribute_inference", rules)

    def test_directed_relation_extraction_adds_relation_metadata(self):
        result = self._review("Dr Jane Tan reports to Ms Mary Lim.", "SG")
        findings = [finding for finding in result.findings if finding.rule == "personal_attribute_inference"]

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["attribute_type"], "relationship")
        self.assertEqual(findings[0].metadata["relation_type"], "reports_to")
        self.assertEqual(findings[0].metadata["inferred_value"], "Ms Mary Lim")

    def test_richer_personal_attribute_types_fire(self):
        result = self._review(
            "Dr Jane Tan studies at National University of Singapore.\n"
            "Mr Alan Goh holds a solicitor practising certificate.\n"
            "Ms Sara Lim works in Finance Team.\n",
            "SG",
        )
        attribute_types = {
            finding.metadata["attribute_type"]
            for finding in result.findings
            if finding.rule == "personal_attribute_inference"
        }
        self.assertIn("education", attribute_types)
        self.assertIn("professional_license", attribute_types)
        self.assertIn("department", attribute_types)

    def test_occupation_personal_attribute_type_fires(self):
        result = self._review("Dr Jane Tan works as Senior Actuary.\n", "SG")
        attribute_types = {
            finding.metadata["attribute_type"]
            for finding in result.findings
            if finding.rule == "personal_attribute_inference"
        }

        self.assertIn("occupation", attribute_types)

    def test_special_category_personal_attribute_escalates(self):
        result = self._review("Dr Jane Tan was diagnosed with Type 1 diabetes.", "SG")
        findings = [finding for finding in result.findings if finding.rule == "personal_attribute_inference"]

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "high")
        self.assertTrue(findings[0].metadata["special_category_attribute"])
        self.assertEqual(findings[0].metadata["special_category_type"], "health")

    def test_semantic_pii_fallback_is_env_gated(self):
        text = "Full name: Jane Tan\nEmployee ID: EMP-2026-1042"
        self.assertNotIn("named_person", self._rules(text, "SG"))
        with mock.patch.dict("os.environ", {"KAYPOH_SEMANTIC_PII_FALLBACK": "1"}):
            result = self._review(text, "SG")
        names = [finding for finding in result.findings if finding.rule == "named_person"]
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0].matched_text, "Jane Tan")
        self.assertEqual(names[0].metadata["fallback"], "semantic_label_anchor")

    def test_semantic_pii_fallback_can_extract_dob_and_age(self):
        text = "Patient DOB is 14 February 1988.\nPatient age recorded as 42."
        self.assertNotIn("date_of_birth", self._rules(text, "SG"))
        self.assertNotIn("age_reference", self._rules(text, "SG"))
        with mock.patch.dict("os.environ", {"KAYPOH_SEMANTIC_PII_FALLBACK": "1"}):
            result = self._review(text, "SG")
        findings = {(finding.rule, finding.matched_text) for finding in result.findings}
        self.assertIn(("date_of_birth", "14 February 1988"), findings)
        self.assertIn(("age_reference", "42"), findings)

    def test_semantic_pii_fallback_can_extract_sentence_dob_and_age(self):
        text = "Patient Jane Tan was born on 14 February 1988.\nSubject Jane Tan is 42 years old."
        with mock.patch.dict("os.environ", {"KAYPOH_SEMANTIC_PII_FALLBACK": "1"}):
            result = self._review(text, "SG")
        findings = {(finding.rule, finding.matched_text, finding.metadata.get("fallback")) for finding in result.findings}

        self.assertIn(("date_of_birth", "14 February 1988", "semantic_sentence_anchor"), findings)
        self.assertIn(("age_reference", "42", "semantic_sentence_anchor"), findings)

    def test_semantic_pii_fallback_can_extract_multilingual_labels(self):
        text = "姓名: Jane Tan\n生年月日: 14 February 1988\n年齢: 42"
        with mock.patch.dict("os.environ", {"KAYPOH_SEMANTIC_PII_FALLBACK": "1"}):
            result = self._review(text, "JP")
        findings = {(finding.rule, finding.matched_text) for finding in result.findings}

        self.assertIn(("named_person", "Jane Tan"), findings)
        self.assertIn(("date_of_birth", "14 February 1988"), findings)
        self.assertIn(("age_reference", "42"), findings)

    def test_local_ner_fallback_can_extract_unlabelled_person_when_available(self):
        text = "Meeting note: Jane Tan approved the access review."
        start = text.index("Jane Tan")
        with mock.patch.dict("os.environ", {"KAYPOH_LOCAL_NER_FALLBACK": "1"}, clear=False):
            with mock.patch(
                "kaypoh.review.detectors.semantic._local_ner_entities",
                return_value=([(start, start + len("Jane Tan"), "PERSON")], None),
            ):
                result = self._review(text, "SG")
        names = [finding for finding in result.findings if finding.rule == "named_person"]

        self.assertEqual(len(names), 1)
        self.assertEqual(names[0].matched_text, "Jane Tan")
        self.assertEqual(names[0].metadata["fallback"], "local_ner")

    def test_local_ner_fallback_reports_degraded_mode_when_model_missing(self):
        clear_semantic_pii_state_for_tests()
        with mock.patch.dict(
            "os.environ",
            {"KAYPOH_LOCAL_NER_FALLBACK": "1", "KAYPOH_LOCAL_NER_MODEL": "__kaypoh_missing_model__"},
            clear=False,
        ):
            result = self._review("Meeting note without labelled names.", "SG")
        clear_semantic_pii_state_for_tests()

        self.assertTrue(any(item["mode"] == "local_ner_unavailable" for item in result.degraded_modes))


if __name__ == "__main__":
    unittest.main()
