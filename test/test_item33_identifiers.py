"""Item 33 mini-slice: DOB/age, online/device IDs, ITIN, and US DLN.

The detectors are intentionally anchored and validator-backed. These tests lock recall
for canonical forms and precision for malformed or under-specified identifiers.
"""

import unittest

from kaypoh.review.citations import pii_rationale
from kaypoh.review.engine import PreSendReviewEngine

US_DRIVER_LICENSE_SAMPLES = {
    "AL": "1234567",
    "AK": "1234567",
    "AZ": "A12345678",
    "AR": "123456789",
    "CA": "A1234567",
    "CO": "123456789",
    "CT": "123456789",
    "DE": "1234567",
    "FL": "A123456789012",
    "GA": "123456789",
    "HI": "A12345678",
    "ID": "AB123456C",
    "IL": "A12345678901",
    "IN": "A123456789",
    "IA": "123AB1234",
    "KS": "A12345678",
    "KY": "A12345678",
    "LA": "123456789",
    "ME": "1234567",
    "MD": "A123456789012",
    "MA": "A12345678",
    "MI": "A123456789012",
    "MN": "A123456789012",
    "MS": "123456789",
    "MO": "A123456",
    "MT": "123456789",
    "NE": "A1234567",
    "NV": "X12345678",
    "NH": "12ABC12345",
    "NJ": "A12345678901234",
    "NM": "123456789",
    "NY": "123456789",
    "NC": "123456789012",
    "ND": "ABC123456",
    "OH": "AB123456",
    "OK": "A123456789",
    "OR": "1234567",
    "PA": "12345678",
    "RI": "V123456",
    "SC": "12345678901",
    "SD": "123456789",
    "TN": "123456789",
    "TX": "12345678",
    "UT": "1234567890",
    "VT": "12345678",
    "VA": "A123456789",
    "WA": "WDLABCD12345",
    "WV": "A123456",
    "WI": "A1234567890123",
    "WY": "123456789",
}


class Item33IdentifierTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _review(self, text: str, *, profile: str = "strict"):
        return self.engine.review(
            text=text,
            source_jurisdiction="US",
            destination_jurisdiction="US",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile=profile,
        )

    def _rules(self, text: str, *, profile: str = "strict") -> set[str]:
        return {finding.rule for finding in self._review(text, profile=profile).findings}

    def test_date_of_birth_canonical_forms_fire(self):
        for text in [
            "DOB: 1988-02-14",
            "Date of birth: February 14, 1988",
            "Born on 14/02/1988",
            "Birthday: 14 February 1988",
        ]:
            with self.subTest(text=text):
                self.assertIn("date_of_birth", self._rules(text))

    def test_date_of_birth_rejects_invalid_dates(self):
        self.assertNotIn("date_of_birth", self._rules("DOB: 2026-99-99"))

    def test_adult_age_field_fires_but_minor_age_stays_with_minor_detector(self):
        self.assertIn("age_reference", self._rules("Age: 42"))
        self.assertIn("age_reference", self._rules("The client is 42 years old."))
        self.assertIn("age_reference", self._rules("Applicant turns 67 next month."))
        minor_rules = self._rules("Age: 12")
        self.assertNotIn("age_reference", minor_rules)
        self.assertIn("minor_data_reference", minor_rules)

    def test_ip_address_validators(self):
        self.assertIn("ip_address", self._rules("Client IP: 203.0.113.7"))
        self.assertIn("ip_address", self._rules("IPv6 address: 2001:db8::1"))
        self.assertNotIn("ip_address", self._rules("Client IP: 999.1.1.1"))

    def test_device_identifier_validators(self):
        self.assertIn("mac_address", self._rules("MAC address: aa:bb:cc:dd:ee:ff"))
        self.assertNotIn("mac_address", self._rules("MAC clause to be negotiated."))
        self.assertIn("imei", self._rules("IMEI: 490154203237518"))
        self.assertNotIn("imei", self._rules("IMEI: 490154203237519"))
        self.assertIn("cookie_id", self._rules("Cookie ID: abcdef1234567890"))
        self.assertIn("advertising_id", self._rules("GAID: 123e4567-e89b-12d3-a456-426614174000"))
        self.assertIn("device_serial_number", self._rules("Device serial number: AB12CD34EF56"))
        self.assertNotIn("cookie_id", self._rules("Cookie preference: chocolatechip"))
        self.assertNotIn("device_serial_number", self._rules("Serial number 42 in the schedule."))

    def test_eu_national_id_requires_eu_pack_and_label(self):
        eu_result = self.engine.review(
            text="IE PPSN: 1234567T is attached.",
            source_jurisdiction="EU",
            destination_jurisdiction="EU",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        self.assertIn("eu_national_id", {finding.rule for finding in eu_result.findings})
        self.assertNotIn("eu_national_id", self._rules("IE PPSN: 1234567T"))

    def test_uk_company_number_requires_uk_pack_and_shape(self):
        result = self.engine.review(
            text="Company number: 01234567. Companies House no. SC123456. CRN: OC123456.",
            source_jurisdiction="UK",
            destination_jurisdiction="UK",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        findings = [finding for finding in result.findings if finding.rule == "uk_company_number"]
        self.assertEqual([finding.matched_text for finding in findings], ["01234567", "SC123456", "OC123456"])
        self.assertNotIn("uk_company_number", self._rules("Company number: 01234567."))
        bad = self.engine.review(
            text="Company number: ABC12345.",
            source_jurisdiction="UK",
            destination_jurisdiction="UK",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        self.assertNotIn("uk_company_number", {finding.rule for finding in bad.findings})

    def test_eu_company_id_requires_eu_pack_and_shape(self):
        result = self.engine.review(
            text="EU VAT ID: DE123456789. Partita IVA: IT12345678901. BTW nummer: NL123456789B01.",
            source_jurisdiction="EU",
            destination_jurisdiction="EU",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        values = [finding.matched_text for finding in result.findings if finding.rule == "eu_company_id"]
        self.assertEqual(values, ["DE123456789", "IT12345678901", "NL123456789B01"])
        self.assertNotIn("eu_company_id", self._rules("EU VAT ID: DE123456789."))
        bad = self.engine.review(
            text="EU VAT ID: ZZ123. Invoice number: DE123456789.",
            source_jurisdiction="EU",
            destination_jurisdiction="EU",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        self.assertNotIn("eu_company_id", {finding.rule for finding in bad.findings})
        zero = self.engine.review(
            text="Legacy record shows BE VAT: BE0000000000 marked as UAT test data.",
            source_jurisdiction="EU",
            destination_jurisdiction="EU",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        self.assertNotIn("eu_company_id", {finding.rule for finding in zero.findings})

    def test_broader_eu_checksum_identifiers_fire(self):
        samples = [
            "DE tax ID: 51370420006",
            "Italian codice fiscale: MRTMTT91D08F205J",
            "Belgian national number: 85.07.30-033.28",
            "Portuguese NIF: 501964843",
            "Swedish personnummer: 640823-3234",
            "Finnish HETU: 131052-308T",
            "Irish PPSN: 1234567T",
            "Austrian SVNR: 1237 010180",
            "Czech birth number: 900101/1239",
            "Slovak birth number: 546231/1239",
            "Romanian CNP: 1960101220017",
        ]
        for text in samples:
            with self.subTest(text=text):
                result = self.engine.review(
                    text=text,
                    source_jurisdiction="EU",
                    destination_jurisdiction="EU",
                    entity_id=None,
                    include_suggestions=False,
                    document_type="generic",
                    review_profile="strict",
                )
                self.assertIn("eu_national_id", {finding.rule for finding in result.findings})

    def test_broader_eu_checksum_identifiers_reject_bad_values(self):
        samples = [
            "DE tax ID: 51370420007",
            "Italian codice fiscale: MRTMTT91D08F205A",
            "Belgian national number: 85.07.30-033.29",
            "Portuguese NIF: 501964844",
            "Swedish personnummer: 640823-3235",
            "Finnish HETU: 131052-308A",
            "Irish PPSN: 1234567A",
            "Austrian SVNR: 1238 010180",
            "Czech birth number: 900101/1238",
            "Slovak birth number: 546231/1238",
            "Romanian CNP: 1960101220018",
        ]
        for text in samples:
            with self.subTest(text=text):
                result = self.engine.review(
                    text=text,
                    source_jurisdiction="EU",
                    destination_jurisdiction="EU",
                    entity_id=None,
                    include_suggestions=False,
                    document_type="generic",
                    review_profile="strict",
                )
                self.assertNotIn("eu_national_id", {finding.rule for finding in result.findings})

    def test_localized_dob_labels_fire(self):
        for text in ["出生日期: 1988-02-14", "생년월일: 1988-02-14"]:
            with self.subTest(text=text):
                self.assertIn("date_of_birth", self._rules(text))

    def test_us_itin_fires_and_validator_rejects_bad_middle_range(self):
        self.assertIn("us_itin", self._rules("ITIN: 912-70-1234"))
        self.assertNotIn("us_itin", self._rules("ITIN: 912-49-1234"))

    def test_us_driver_license_all_fifty_state_shapes_fire(self):
        for state, number in US_DRIVER_LICENSE_SAMPLES.items():
            with self.subTest(state=state):
                self.assertIn("us_driver_license", self._rules(f"{state} Driver License: {number}"))

    def test_us_driver_license_rejects_wrong_state_shape(self):
        self.assertNotIn("us_driver_license", self._rules("CA Driver License: 12345678"))

    def test_audit_grade_warns_on_driver_license_missing_state(self):
        result = self._review("Driver License: A1234567", profile="audit_grade")
        self.assertNotIn("us_driver_license", {finding.rule for finding in result.findings})
        self.assertTrue(any(w.get("rule_guess") == "us_driver_license" for w in result.coverage_warnings))

    def test_audit_grade_warns_on_masked_driver_license(self):
        result = self._review("CA Driver License: A1234***", profile="audit_grade")
        self.assertNotIn("us_driver_license", {finding.rule for finding in result.findings})
        self.assertTrue(any("masked or partial" in w.get("why", "") for w in result.coverage_warnings))

    def test_strict_profile_does_not_warn_on_driver_license_missing_state(self):
        result = self._review("Driver License: A1234567", profile="strict")
        self.assertEqual(result.coverage_warnings, [])

    def test_audit_grade_warns_on_unsupported_driver_license_issuer(self):
        result = self._review("PR Driver License: X1234567", profile="audit_grade")
        self.assertTrue(any("unsupported" in w.get("why", "") for w in result.coverage_warnings))

    def test_item33_rationales_exist(self):
        for rule in [
            "date_of_birth",
            "age_reference",
            "ip_address",
            "mac_address",
            "imei",
            "cookie_id",
            "advertising_id",
            "device_serial_number",
            "eu_national_id",
            "uk_company_number",
            "eu_company_id",
            "us_itin",
            "us_driver_license",
        ]:
            with self.subTest(rule=rule):
                self.assertGreater(len(pii_rationale(rule=rule, jurisdiction="US", matched_text="x")), 30)


if __name__ == "__main__":
    unittest.main()
