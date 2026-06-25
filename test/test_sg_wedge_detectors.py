"""SG wedge detector slice (item 100 follow-up).

Three new SG-specific detectors in `src/junas/review/jurisdictions_data/SG.toml`:
    sg_paynow       — PayNow identifier (UEN / NRIC / mobile), anchored on PayNow context
    sg_mas_licence  — MAS-issued CMS / FA licence number, anchored on MAS / licence context
    sg_sgx_counter  — SGX counter / cashtag, anchored on SGX context, case-sensitive capture

Each detector ships with adversarial precision coverage against the false-positive surface
called out in the architecture doc (CMS as 'Content Management System', FA as initials,
3-letter currency codes, 'SGX is...' lowercase tokens, landline numbers in PayNow context).
Held to recall=1.0 + precision=1.0 on the inline corpus — same posture as sg_court_citation.
"""

import unittest

from junas.review.engine import PreSendReviewEngine


class _SgWedgeBase(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings_by_rule(self, text: str, rule: str) -> list:
        result = self.engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        return [f for f in result.findings if f.rule == rule]


class SgPayNowRecallTests(_SgWedgeBase):
    """Each canonical PayNow variant must fire exactly one sg_paynow finding capturing
    only the identifier (capture_group=1) — not the leading PayNow anchor word."""

    def test_paynow_nric(self):
        hits = self._findings_by_rule("Please PayNow to S1234567D for the balance.", "sg_paynow")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "S1234567D")
        self.assertEqual(hits[0].severity, "high")

    def test_paynow_uen_legacy(self):
        hits = self._findings_by_rule("PayNow ID: 201912345A — confirm receipt.", "sg_paynow")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "201912345A")

    def test_paynow_uen_tformat(self):
        hits = self._findings_by_rule("PAYNOW account T20ME0123F (entity).", "sg_paynow")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "T20ME0123F")

    def test_paynow_mobile_with_country_code(self):
        hits = self._findings_by_rule("Pay Now to +65 9123 4567 thanks.", "sg_paynow")
        self.assertEqual(len(hits), 1)
        self.assertIn("9123", hits[0].matched_text)

    def test_paynow_mobile_bare(self):
        hits = self._findings_by_rule("PayNow 91234567 by 5pm.", "sg_paynow")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "91234567")

    def test_paynow_mobile_with_dash(self):
        hits = self._findings_by_rule("PayNow to +65-8234-5678 today.", "sg_paynow")
        self.assertEqual(len(hits), 1)


class SgPayNowPrecisionTests(_SgWedgeBase):
    """Adversarial precision — PayNow-context tokens that must NOT fire."""

    def test_paynow_landline_does_not_fire(self):
        # SG landlines start with 6; PayNow regex requires 8 or 9 prefix.
        hits = self._findings_by_rule("PayNow customer support 6225 1234 weekdays.", "sg_paynow")
        self.assertEqual(hits, [])

    def test_pay_now_as_imperative_does_not_fire(self):
        # "Pay now" as an imperative verb without an identifier afterwards.
        hits = self._findings_by_rule("Please pay now or face a late fee penalty.", "sg_paynow")
        self.assertEqual(hits, [])

    def test_paynow_no_identifier_does_not_fire(self):
        hits = self._findings_by_rule("Visit the PayNow website for instructions.", "sg_paynow")
        self.assertEqual(hits, [])


class SgMasLicenceRecallTests(_SgWedgeBase):
    def test_cms_with_mas_licence_anchor(self):
        hits = self._findings_by_rule(
            "Licensed by MAS: CMS100099 (capital markets services).",
            "sg_mas_licence",
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "CMS100099")
        self.assertEqual(hits[0].severity, "medium")

    def test_fa_with_licence_no_anchor(self):
        hits = self._findings_by_rule(
            "Licence no. FA654321 issued under the FA Act.",
            "sg_mas_licence",
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "FA654321")

    def test_cms_with_mas_no_anchor(self):
        hits = self._findings_by_rule("MAS No. CMS123456 (active).", "sg_mas_licence")
        self.assertEqual(len(hits), 1)

    def test_mas_register_anchor(self):
        # MAS Register-anchor form. The regex requires the licence id to follow the anchor
        # directly (separated only by punctuation/whitespace), not by an intervening word.
        hits = self._findings_by_rule("MAS Register: CMS300401 (active).", "sg_mas_licence")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "CMS300401")


class SgMasLicencePrecisionTests(_SgWedgeBase):
    """Adversarial precision — CMS / FA prefix collisions in non-MAS contexts."""

    def test_cms_as_content_management_system_does_not_fire(self):
        hits = self._findings_by_rule(
            "Our CMS123456 ticket on the Content Management System remains open.",
            "sg_mas_licence",
        )
        self.assertEqual(hits, [])

    def test_fa_cup_year_does_not_fire(self):
        hits = self._findings_by_rule(
            "The FA Cup 1987654 was a memorable year for Arsenal.",
            "sg_mas_licence",
        )
        self.assertEqual(hits, [])

    def test_cms_bare_without_mas_context_does_not_fire(self):
        # Bare "CMS123456" without MAS / licence anchor must not fire.
        hits = self._findings_by_rule(
            "Reference CMS123456 in your reply.",
            "sg_mas_licence",
        )
        self.assertEqual(hits, [])


class SgSgxCounterRecallTests(_SgWedgeBase):
    def test_sgx_colon_counter(self):
        hits = self._findings_by_rule("Reference SGX: DBS in the memo.", "sg_sgx_counter")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "DBS")
        self.assertEqual(hits[0].severity, "low")

    def test_sgx_letter_digit_code(self):
        # D05 (DBS holdings), U11 (UOB) — letter + digits format.
        hits = self._findings_by_rule("Counter SGX: D05 is the holdings vehicle.", "sg_sgx_counter")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "D05")

    def test_sgx_counter_word_anchor(self):
        hits = self._findings_by_rule("SGX counter ABC1 reported.", "sg_sgx_counter")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "ABC1")

    def test_ticker_sgx_form(self):
        hits = self._findings_by_rule("Ticker SGX: U11 holds steady.", "sg_sgx_counter")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "U11")

    def test_listed_on_sgx_form(self):
        hits = self._findings_by_rule("The issuer is listed on SGX as F34.", "sg_sgx_counter")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "F34")


class SgSgxCounterPrecisionTests(_SgWedgeBase):
    """Adversarial precision — SGX-context tokens that must NOT fire as counter codes."""

    def test_sgx_index_word_does_not_fire(self):
        # "SGX index" — "index" is lowercase, case-sensitive capture (?-i:...) rejects.
        hits = self._findings_by_rule("The SGX index closed up 0.5% today.", "sg_sgx_counter")
        self.assertEqual(hits, [])

    def test_sgx_is_does_not_fire(self):
        hits = self._findings_by_rule("SGX is the Singapore Exchange.", "sg_sgx_counter")
        self.assertEqual(hits, [])

    def test_sgx_in_does_not_fire(self):
        hits = self._findings_by_rule("Trading volume on SGX in Q3 was elevated.", "sg_sgx_counter")
        self.assertEqual(hits, [])

    def test_sgx_st_exchange_suffix_does_not_fire(self):
        hits = self._findings_by_rule("The issuer is listed on SGX-ST Mainboard.", "sg_sgx_counter")
        self.assertEqual(hits, [])

    def test_sgx_listing_rule_abbreviation_does_not_fire(self):
        hits = self._findings_by_rule("Follow SGX LR 703 for disclosure timing.", "sg_sgx_counter")
        self.assertEqual(hits, [])

    def test_bare_three_letter_uppercase_without_sgx_anchor(self):
        # "DBS is a major bank" — "DBS" alone without SGX anchor must not fire.
        hits = self._findings_by_rule("DBS is a major bank in Singapore.", "sg_sgx_counter")
        self.assertEqual(hits, [])

    def test_3letter_currency_code_does_not_fire(self):
        # "SGD" / "USD" / "EUR" must not fire as SGX counters.
        hits = self._findings_by_rule("Total consideration in USD across the deal.", "sg_sgx_counter")
        self.assertEqual(hits, [])


class SgWedgeCitationTests(unittest.TestCase):
    """Citation rationales must carry the SG statute anchor for each new rule."""

    def setUp(self):
        from junas.review.citations import pii_rationale
        self.pii = pii_rationale

    def test_paynow_citation_carries_pdpa_and_psa(self):
        text = self.pii(rule="sg_paynow", jurisdiction="SG", matched_text="S1234567D")
        self.assertIn("PDPA", text)
        self.assertIn("PayNow", text)

    def test_mas_licence_citation_carries_sfa(self):
        text = self.pii(rule="sg_mas_licence", jurisdiction="SG", matched_text="CMS123456")
        self.assertIn("MAS", text)
        self.assertIn("Securities and Futures Act", text)

    def test_sgx_counter_citation_carries_sfa_s218(self):
        text = self.pii(rule="sg_sgx_counter", jurisdiction="SG", matched_text="DBS")
        self.assertIn("SGX", text)
        self.assertIn("s218", text)


class SgWedgeMultiFiringTests(_SgWedgeBase):
    """Multiple wedge detectors firing in the same document must each produce its own finding."""

    def test_paynow_plus_mas_plus_sgx_all_fire(self):
        text = (
            "Please PayNow to S1234567D for advisory fees. "
            "The advisor is licensed by MAS: CMS100099. "
            "Target counter SGX: DBS will be embargoed."
        )
        result = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="strict",
        )
        rules_fired = {f.rule for f in result.findings}
        self.assertIn("sg_paynow", rules_fired)
        self.assertIn("sg_mas_licence", rules_fired)
        self.assertIn("sg_sgx_counter", rules_fired)


if __name__ == "__main__":
    unittest.main()
