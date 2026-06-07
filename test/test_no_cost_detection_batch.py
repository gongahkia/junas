import unittest

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

    def test_generic_addresses_without_jurisdiction_format_do_not_fire(self):
        text = "Please meet at the office near River Road tomorrow."
        self.assertNotIn("uk_postal_address", self._rules(text, "UK"))
        self.assertNotIn("us_postal_address", self._rules(text, "US"))

    def test_personal_attribute_inference_fires_with_structure_metadata(self):
        result = self._review("People\nDr Jane Tan works at Acme Pte Ltd.\n", "SG")
        findings = [finding for finding in result.findings if finding.rule == "personal_attribute_inference"]

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metadata["attribute_type"], "employer")
        self.assertEqual(findings[0].metadata["structural_unit_kind"], "paragraph")

    def test_personal_attribute_relationship_and_location_fire(self):
        rules = self._rules("Dr Jane Tan's spouse Mary Lim lives nearby. Mr Alan Goh lives in Bukit Timah.")

        self.assertIn("personal_attribute_inference", rules)


if __name__ == "__main__":
    unittest.main()
