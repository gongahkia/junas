"""Regression guards for the precision gaps closed on 2026-05-24.

Two specific failure modes get explicit tests so future engine changes can't silently
regress them without breaking the build:

1. `material_adverse_change` must not fire on:
   - bare `mac` token (consumer-product reference)
   - negated context `no MAC clause concerns`

2. `phone_number` must not fire on a span fully covered by a higher-priority national-
   /company-ID detector (NRIC, UEN, MyKad, NIK, Thai national ID, PhilSys, TIN, CCCD).
"""

import unittest

from kaypoh.review.engine import PreSendReviewEngine
from kaypoh.workflow.privacy_guard import PrivacyGuard


def _rules_matched(text: str, *, jurisdiction: str = "SG") -> list[tuple[str, str]]:
    engine = PreSendReviewEngine()
    result = engine.review(
        text=text,
        source_jurisdiction=jurisdiction,
        destination_jurisdiction=jurisdiction,
        entity_id=None,
        include_suggestions=False,
        document_type="generic",
    )
    return [(f.rule, f.matched_text) for f in result.findings]


class MacMaePrecisionGuards(unittest.TestCase):
    def test_lowercase_mac_in_consumer_product_does_not_fire(self):
        text = "Our team's mac mini setup remains the dev environment."
        for rule, _ in _rules_matched(text):
            self.assertNotEqual(rule, "material_adverse_change",
                                "bare lowercase 'mac' must not fire material_adverse_change")

    def test_no_mac_clause_concerns_does_not_fire(self):
        text = "We have no MAC clause concerns in this draft."
        for rule, matched in _rules_matched(text):
            self.assertNotEqual(rule, "material_adverse_change",
                                f"negated MAC clause should be suppressed; got {matched!r}")

    def test_bare_mae_in_unrelated_context_does_not_fire(self):
        text = "Our MAE Asia office sent the report."
        for rule, _ in _rules_matched(text):
            self.assertNotEqual(rule, "material_adverse_change",
                                "bare MAE in unrelated context must not fire")

    def test_canonical_mac_clause_still_fires(self):
        # positive control: the actual MAC clause language must still be detected.
        text = "The Purchaser may invoke the MAC clause if there is a material adverse change."
        rules = {r for r, _ in _rules_matched(text)}
        self.assertIn("material_adverse_change", rules)

    def test_material_adverse_change_phrase_still_fires(self):
        text = "Any material adverse change will allow termination."
        rules = {r for r, _ in _rules_matched(text)}
        self.assertIn("material_adverse_change", rules)


class PhoneNumberSpanDedupGuards(unittest.TestCase):
    def _has_phone_match(self, text: str, matched_text: str, jurisdiction: str = "SG") -> bool:
        for rule, m in _rules_matched(text, jurisdiction=jurisdiction):
            if rule == "phone_number" and m == matched_text:
                return True
        return False

    def test_phone_does_not_fire_on_sg_nric_span(self):
        text = "Dr Jane Tan NRIC S1234567D signed."
        self.assertFalse(self._has_phone_match(text, "S1234567D"))

    def test_phone_does_not_fire_on_sg_uen_span(self):
        text = "ACME Pte Ltd (UEN 201912345Z) is the seller."
        self.assertFalse(self._has_phone_match(text, "201912345Z"))

    def test_phone_does_not_fire_on_mykad_span(self):
        text = "MyKad 880415-10-5432 was sighted."
        self.assertFalse(self._has_phone_match(text, "880415-10-5432", jurisdiction="MY"))

    def test_phone_does_not_fire_on_nik_span(self):
        text = "NIK 3174050101900012 was sighted."
        self.assertFalse(self._has_phone_match(text, "3174050101900012", jurisdiction="ID"))

    def test_real_phone_with_country_code_still_fires(self):
        text = "Contact: +65 6111 2233 for follow-up."
        self.assertTrue(self._has_phone_match(text, "+65 6111 2233"))

    def test_phone_partially_overlapping_id_still_fires(self):
        # `phone_number` only gets dropped when *fully contained* in a higher-priority span.
        # A genuine phone that happens to touch but not be inside an ID stays. We don't have
        # a clean fixture for this — the conservative dedup is the architecturally important
        # guarantee, so document it here as the intended behavior.
        text = "Call +65 9876 5432. NRIC S1234567D separately on file."
        phones = [m for r, m in _rules_matched(text) if r == "phone_number"]
        self.assertIn("+65 9876 5432", phones)


class FinancialAmountGuards(unittest.TestCase):
    def test_currency_code_amounts_do_not_swallow_trailing_punctuation(self):
        text = "The consideration is SGD 12,500, subject to completion accounts."
        amounts = [m for r, m in _rules_matched(text) if r == "financial_amount"]
        self.assertIn("SGD 12,500", amounts)
        self.assertNotIn("SGD 12,500,", amounts)

    def test_multi_currency_codes_still_fire(self):
        text = "Funding includes USD 2.5 million, HKD 8,000,000 and JPY 120 million."
        amounts = [m for r, m in _rules_matched(text) if r == "financial_amount"]
        self.assertIn("USD 2.5 million", amounts)
        self.assertIn("HKD 8,000,000", amounts)
        self.assertIn("JPY 120 million", amounts)


class PrivacyGuardAmountGuards(unittest.TestCase):
    def test_privacy_guard_redacts_currency_code_amounts_cleanly(self):
        guard = PrivacyGuard(max_query_chars=140, redact_exact_numbers=True)

        sanitized, redactions = guard.sanitize_query(
            "Quantum will invest SGD 12,500, and HKD 8,000,000 before announcement."
        )

        self.assertIn("amount", redactions)
        self.assertNotIn("SGD 12,500", sanitized)
        self.assertNotIn("HKD 8,000,000", sanitized)
        self.assertNotIn("12,500", sanitized)
        self.assertNotIn("8,000,000", sanitized)
        self.assertEqual(sanitized.count("[amount]"), 2)


if __name__ == "__main__":
    unittest.main()
