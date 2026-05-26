"""US / UK direct-ID recognizers + JP postal-code + AU postal-address recognizers.

Closes the US SSN / EIN, UK NIN, JP postal-code, AU postal-address gaps tracked in
ARCHITECTURE-PIVOT-24-MAY.md items 33 and 86-followup. Mirrors the HK/AU/JP/KR pack
discipline: recognizers must fire on canonical samples, validators must reject bad
inputs, statute suffixes must be present in rationales.
"""

import unittest

from kaypoh.review import jurisdictions
from kaypoh.review.citations import pii_rationale
from kaypoh.review.engine import PreSendReviewEngine


class UsUkPackLoadTests(unittest.TestCase):
    def test_us_and_uk_packs_carry_recognizers(self):
        jurisdictions.reload_registry()
        self.assertTrue(jurisdictions.RULE_PACKS["US"].recognizers, "US: no recognizers")
        self.assertTrue(jurisdictions.RULE_PACKS["UK"].recognizers, "UK: no recognizers")

    def test_jp_and_au_recognizer_inventory_grew(self):
        jurisdictions.reload_registry()
        jp_rules = {r.rule_name for r in jurisdictions.RULE_PACKS["JP"].recognizers}
        au_rules = {r.rule_name for r in jurisdictions.RULE_PACKS["AU"].recognizers}
        self.assertIn("jp_postal_code", jp_rules)
        self.assertIn("au_postal_address", au_rules)


class UsSsnRecognizerTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _rules(self, text: str) -> set[str]:
        result = self.engine.review(
            text=text,
            source_jurisdiction="US",
            destination_jurisdiction="US",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
        )
        return {finding.rule for finding in result.findings}

    def test_ssn_canonical_fires(self):
        # 123-45-6789: valid format, valid area (123), valid group (45), valid serial (6789).
        self.assertIn("us_ssn", self._rules("SSN: 123-45-6789"))

    def test_ssn_rejects_invalid_area_666(self):
        self.assertNotIn("us_ssn", self._rules("Number 666-12-3456 on file."))

    def test_ssn_rejects_invalid_area_900_range(self):
        self.assertNotIn("us_ssn", self._rules("Number 900-12-3456 on file."))

    def test_ssn_rejects_zero_serial(self):
        self.assertNotIn("us_ssn", self._rules("Number 123-45-0000 on file."))

    def test_ssn_rejects_publicly_leaked_sentinels(self):
        # 078-05-1120 was a real Woolworth wallet-display SSN that became a "never valid" sentinel.
        self.assertNotIn("us_ssn", self._rules("Test SSN 078-05-1120"))


class UsEinRecognizerTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _rules(self, text: str) -> set[str]:
        result = self.engine.review(
            text=text,
            source_jurisdiction="US",
            destination_jurisdiction="US",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
        )
        return {finding.rule for finding in result.findings}

    def test_ein_with_allocated_prefix_fires(self):
        self.assertIn("us_ein", self._rules("EIN: 12-3456789"))

    def test_ein_with_unallocated_prefix_rejected(self):
        # prefix 07 is not in the IRS allocated list.
        self.assertNotIn("us_ein", self._rules("EIN: 07-1234567"))

    def test_ein_anchor_required(self):
        # bare 2-7 digits without anchor should not fire (avoids false positives on
        # arbitrary dashed numbers).
        self.assertNotIn("us_ein", self._rules("Order ref 12-3456789 enclosed."))


class UkNinRecognizerTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _rules(self, text: str) -> set[str]:
        result = self.engine.review(
            text=text,
            source_jurisdiction="UK",
            destination_jurisdiction="UK",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
        )
        return {finding.rule for finding in result.findings}

    def test_nin_canonical_fires(self):
        self.assertIn("uk_nin", self._rules("NIN: AB 12 34 56 C"))

    def test_nin_compact_form_fires(self):
        self.assertIn("uk_nin", self._rules("National Insurance Number AB123456C"))

    def test_nin_reserved_prefix_rejected(self):
        # BG / GB / NK / KN / TN / NT / ZZ are reserved and never issued.
        self.assertNotIn("uk_nin", self._rules("NIN: BG123456C"))
        self.assertNotIn("uk_nin", self._rules("NIN: ZZ123456C"))

    def test_nin_administrative_first_letter_rejected(self):
        # D F I Q U V never appear as first letter on issued NINs.
        self.assertNotIn("uk_nin", self._rules("NIN: DA123456C"))

    def test_nin_bad_suffix_rejected(self):
        # suffix must be A B C or D.
        self.assertNotIn("uk_nin", self._rules("NIN: AB123456E"))


class JpPostalCodeTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _rules(self, text: str) -> set[str]:
        result = self.engine.review(
            text=text,
            source_jurisdiction="JP",
            destination_jurisdiction="JP",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
        )
        return {finding.rule for finding in result.findings}

    def test_postal_mark_form_fires(self):
        self.assertIn("jp_postal_code", self._rules("〒100-0001 Tokyo"))

    def test_anchored_form_fires(self):
        self.assertIn("jp_postal_code", self._rules("Postal code: 100-0001"))

    def test_bare_dashed_run_does_not_fire(self):
        # 3-4 digit dashed runs without an anchor are too noisy to claim.
        self.assertNotIn("jp_postal_code", self._rules("Document ref 100-0001 in folder."))


class AuPostalAddressTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _rules(self, text: str) -> set[str]:
        result = self.engine.review(
            text=text,
            source_jurisdiction="AU",
            destination_jurisdiction="AU",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
        )
        return {finding.rule for finding in result.findings}

    def test_state_plus_postcode_fires(self):
        self.assertIn("au_postal_address", self._rules("123 George St, Sydney NSW 2000"))

    def test_all_state_codes_fire(self):
        for state, postcode in [("VIC", "3000"), ("QLD", "4000"), ("WA", "6000"),
                                ("SA", "5000"), ("TAS", "7000"), ("ACT", "2600"), ("NT", "0800")]:
            self.assertIn("au_postal_address", self._rules(f"... {state} {postcode}"))

    def test_state_without_postcode_does_not_fire(self):
        self.assertNotIn("au_postal_address", self._rules("Met in NSW yesterday"))


class CitationRationaleTests(unittest.TestCase):
    def test_us_ssn_rationale_carries_us_suffix(self):
        text = pii_rationale(rule="us_ssn", jurisdiction="US", matched_text="123-45-6789")
        self.assertIn("Social Security", text)
        self.assertIn("US", text)

    def test_uk_nin_rationale_carries_uk_suffix(self):
        text = pii_rationale(rule="uk_nin", jurisdiction="UK", matched_text="AB123456C")
        self.assertIn("National Insurance", text)
        self.assertIn("UK GDPR", text)

    def test_jp_postal_rationale_carries_jp_suffix(self):
        text = pii_rationale(rule="jp_postal_code", jurisdiction="JP", matched_text="100-0001")
        self.assertIn("postal", text.lower())
        self.assertIn("APPI", text)

    def test_au_postal_rationale_carries_au_suffix(self):
        text = pii_rationale(rule="au_postal_address", jurisdiction="AU", matched_text="NSW 2000")
        self.assertIn("Privacy Act", text)


if __name__ == "__main__":
    unittest.main()
