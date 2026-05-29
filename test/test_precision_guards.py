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

    def test_bare_ceo_or_cfo_role_does_not_fire_material_event(self):
        text = "The CEO and CFO attended the diligence call as role-only participants."
        for rule, matched in _rules_matched(text):
            self.assertNotEqual(
                rule,
                "material_event",
                f"bare executive role should not be a material_event; got {matched!r}",
            )

    def test_ceo_departure_still_fires_material_event(self):
        text = "The CEO stepped down before announcement."
        rules = {r for r, _ in _rules_matched(text)}
        self.assertIn("material_event", rules)

    def test_no_live_incident_or_breach_does_not_fire_material_event(self):
        text = "There is no live incident or breach in the training scenario."
        for rule, matched in _rules_matched(text):
            self.assertNotEqual(
                rule,
                "material_event",
                f"negated breach scenario should not be a material_event; got {matched!r}",
            )

    def test_not_profit_forecast_does_not_fire_material_event(self):
        text = "This operational update is not a profit forecast."
        for rule, matched in _rules_matched(text):
            self.assertNotEqual(
                rule,
                "material_event",
                f"negated profit forecast should not be a material_event; got {matched!r}",
            )

    def test_not_generally_available_acquisition_still_fires_material_event(self):
        text = "The acquisition is not generally available and remains confidential."
        rules = {r for r, _ in _rules_matched(text)}
        self.assertIn("material_event", rules)

    def test_generally_available_acquisition_context_does_not_fire_material_event(self):
        text = (
            "ACRA extracts are generally available; MAS approvals are not required "
            "for ordinary share acquisition below threshold."
        )
        for rule, matched in _rules_matched(text):
            self.assertNotEqual(
                rule,
                "material_event",
                f"public/approval-not-required acquisition context should be suppressed; got {matched!r}",
            )

    def test_previously_announced_financing_context_does_not_fire_material_event(self):
        text = (
            "As previously announced via Bursa on 2 April 2026, the board authorised "
            "exploration of a secured term facility; all references herein are to that "
            "public announcement and contain no new price-sensitive information."
        )
        for rule, matched in _rules_matched(text, jurisdiction="MY"):
            self.assertNotEqual(
                rule,
                "material_event",
                f"previously announced/no-new-price-sensitive context should be suppressed; got {matched!r}",
            )

    def test_negated_material_adverse_change_line_does_not_fire_material_event(self):
        text = "We note no material adverse change is triggered; this is not a MAC and not a profit warning."
        for rule, matched in _rules_matched(text):
            self.assertNotEqual(
                rule,
                "material_event",
                f"negated MAC/profit-warning line should not be material_event; got {matched!r}",
            )

    def test_nothing_herein_asserts_mac_does_not_fire(self):
        text = "For avoidance of doubt, nothing herein asserts a Material Adverse Change."
        for rule, matched in _rules_matched(text):
            self.assertNotEqual(rule, "material_adverse_change",
                                f"assertion-negated MAC phrase should be suppressed; got {matched!r}")

    def test_no_upsi_public_guidance_does_not_fire_material_event(self):
        text = (
            "This note contains no UPSI and references publicly announced FY25 guidance "
            "already disclosed on the exchange."
        )
        for rule, matched in _rules_matched(text, jurisdiction="IN"):
            self.assertNotEqual(
                rule,
                "material_event",
                f"no-UPSI public-guidance line should not be material_event; got {matched!r}",
            )

    def test_format_guidance_only_does_not_fire_material_event(self):
        text = "Supplier onboarding provides PAN and GSTIN format guidance only."
        for rule, matched in _rules_matched(text, jurisdiction="IN"):
            self.assertNotEqual(
                rule,
                "material_event",
                f"format-guidance line should not be material_event; got {matched!r}",
            )

    def test_non_production_guidance_example_does_not_fire_material_event(self):
        text = "Screenshots in internal guidance show masked digits and are non-production examples."
        for rule, matched in _rules_matched(text, jurisdiction="IN"):
            self.assertNotEqual(
                rule,
                "material_event",
                f"non-production guidance example should not be material_event; got {matched!r}",
            )

    def test_nonbinding_mou_not_upsi_does_not_fire_definitive_agreement(self):
        text = "A non-binding distributor MOU is not material and is not UPSI."
        for rule, matched in _rules_matched(text, jurisdiction="IN"):
            self.assertNotEqual(
                rule,
                "definitive_agreement",
                f"non-material non-UPSI MOU should not be definitive_agreement; got {matched!r}",
            )

    def test_not_mnpi_marker_does_not_fire_nonpublic_marker(self):
        text = "The questionnaire title says undisclosed, but the item is not MNPI."
        for rule, matched in _rules_matched(text, jurisdiction="IN"):
            self.assertNotEqual(
                rule,
                "nonpublic_marker",
                f"negated MNPI marker should be suppressed; got {matched!r}",
            )

    def test_mnpi_marker_heading_without_upsi_does_not_fire(self):
        text = 'MNPI markers: remove phrases like "not public" unless UPSI is actually present.'
        for rule, matched in _rules_matched(text, jurisdiction="IN"):
            self.assertNotEqual(
                rule,
                "nonpublic_marker",
                f"benign MNPI-marker heading should be suppressed; got {matched!r}",
            )


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

    def test_public_helpline_does_not_fire_as_phone(self):
        text = "General enquiries 1800 000 0000 is a public helpline and not personal data."
        phones = [m for r, m in _rules_matched(text) if r == "phone_number"]
        self.assertNotIn("1800 000 0000", phones)

    def test_public_helpdesk_phone_does_not_fire(self):
        text = "The vendor's public help desk help@example.com and +65 6100 0000 are not MNPI."
        phones = [m for r, m in _rules_matched(text) if r == "phone_number"]
        self.assertNotIn("+65 6100 0000", phones)

    def test_public_hotline_and_public_line_do_not_fire(self):
        text = (
            "Public hotline for HR queries: 1-300-88-0000. "
            "The Exchange Investor Helpline is 03-6200 0000 (public line)."
        )
        phones = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "phone_number"]
        self.assertNotIn("1-300-88-0000", phones)
        self.assertNotIn("03-6200 0000", phones)

    def test_phone_does_not_fire_on_dates_or_ip_literals(self):
        text = "DOB 14-03-1990; session ref 2026-05-28; IP 192.0.2.17."
        phones = [m for r, m in _rules_matched(text) if r == "phone_number"]
        self.assertNotIn("14-03-1990", phones)
        self.assertNotIn("2026-05-28", phones)
        self.assertNotIn("192.0.2.17", phones)

    def test_phone_does_not_fire_on_account_or_uen_fragments(self):
        text = "UEN: 2018 998765 K. Escrow account 123-456-789-0 is corporate."
        phones = [m for r, m in _rules_matched(text) if r == "phone_number"]
        self.assertNotIn("2018 998765", phones)
        self.assertNotIn("123-456-789-0", phones)

    def test_phone_does_not_fire_on_imei_like_bare_identifier(self):
        text = "IMEI 356000112233445 appears in logs."
        phones = [m for r, m in _rules_matched(text) if r == "phone_number"]
        self.assertNotIn("356000112233445", phones)

    def test_phone_does_not_fire_on_company_or_tax_identifiers(self):
        text = (
            "Company No.: 2022012345678-Z and Tax Ref No.: C8765432109 "
            "are identifiers, not phone numbers."
        )
        phones = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "phone_number"]
        self.assertNotIn("2022012345678", phones)
        self.assertNotIn("8765432109", phones)

    def test_phone_does_not_fire_on_ocr_account_or_url_id_fragments(self):
        text = (
            "OCR fragment Acc t: 142-7 78-009912-3. "
            "Project vault: https://example.my/r?id=E M B _0 7-2 0 2 6&sec=Q2."
        )
        phones = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "phone_number"]
        self.assertNotIn("142-7 78-009912-3", phones)
        self.assertNotIn("0 7-2 0 2 6", phones)

    def test_phone_does_not_fire_on_all_zero_placeholder(self):
        text = 'Example placeholder "0000 0000 0000" must never be stored as real data.'
        phones = [m for r, m in _rules_matched(text, jurisdiction="IN") if r == "phone_number"]
        self.assertNotIn("0000 0000 0000", phones)

    def test_phone_does_not_fire_on_aadhaar_placeholder(self):
        text = "Aadhaar: 0000 1111 2222 is illustrative and not linked to any individual."
        phones = [m for r, m in _rules_matched(text, jurisdiction="IN") if r == "phone_number"]
        self.assertNotIn("0000 1111 2222", phones)

    def test_phone_does_not_fire_on_repeated_digit_placeholder(self):
        text = "Use clearly invalid placeholders like 9999-9999-9999 in screenshots only."
        phones = [m for r, m in _rules_matched(text, jurisdiction="IN") if r == "phone_number"]
        self.assertNotIn("9999-9999-9999", phones)


class DeviceIdentifierPrecisionGuards(unittest.TestCase):
    def test_negated_mac_address_example_does_not_fire(self):
        text = "Security note: this is not a MAC address aa-bb-cc-dd-ee-ff."
        macs = [m for r, m in _rules_matched(text, jurisdiction="IN") if r == "mac_address"]
        self.assertNotIn("aa-bb-cc-dd-ee-ff", macs)

    def test_canonical_mac_address_still_fires(self):
        text = "Device MAC: aa-bb-cc-dd-ee-ff."
        macs = [m for r, m in _rules_matched(text, jurisdiction="IN") if r == "mac_address"]
        self.assertIn("aa-bb-cc-dd-ee-ff", macs)


class FunctionalContactGuards(unittest.TestCase):
    def test_role_based_legal_mailbox_does_not_fire(self):
        text = "For SGX submissions, counsel contact: legal@pryce-han.example; role-based signoff acceptable."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("legal@pryce-han.example", emails)

    def test_compliance_routing_mailbox_does_not_fire(self):
        text = "Contact Compliance at compliance@harbourpine.com.sg for listing-rule queries."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("compliance@harbourpine.com.sg", emails)

    def test_in_role_mailboxes_do_not_fire(self):
        text = (
            "Route to investor.relations@example.in, noreply@example.in, "
            "vendor.support@example.in, and infosec@example.in."
        )
        emails = [m for r, m in _rules_matched(text, jurisdiction="IN") if r == "email_address"]
        self.assertNotIn("investor.relations@example.in", emails)
        self.assertNotIn("noreply@example.in", emails)
        self.assertNotIn("vendor.support@example.in", emails)
        self.assertNotIn("infosec@example.in", emails)

    def test_region_prefixed_compliance_mailbox_does_not_fire(self):
        text = "Route enquiries to sgcompliance@seabrightdynamics.sg."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("sgcompliance@seabrightdynamics.sg", emails)

    def test_docroom_mailbox_does_not_fire(self):
        text = "Recipients sign wall-crossing acknowledgments via docroom@seabrightdynamics.sg."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("docroom@seabrightdynamics.sg", emails)

    def test_dpo_and_corpsec_role_mailboxes_do_not_fire(self):
        text = "Route privacy to dpo@example.sg and company-secretarial queries to corpsec@example.sg."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("dpo@example.sg", emails)
        self.assertNotIn("corpsec@example.sg", emails)

    def test_dotted_compliance_mailbox_does_not_fire(self):
        text = "Contact the listing compliance desk at sgx.compliance@issuer.example."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("sgx.compliance@issuer.example", emails)

    def test_role_only_company_secretary_mailbox_does_not_fire(self):
        text = "Deal lead is named separately; role-only contact: Company Secretary, cosec@velorise.com.sg."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("cosec@velorise.com.sg", emails)

    def test_personal_email_still_fires(self):
        text = "Contact Ms Jane Tan at jane.tan@example.sg."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertIn("jane.tan@example.sg", emails)

    def test_personal_email_before_later_role_only_contact_still_fires(self):
        text = (
            "Deal lead: Mr. Adrian Khoo, adrian.khoo@velorise.com.sg; "
            "role-only contact: Company Secretary, cosec@velorise.com.sg."
        )
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertIn("adrian.khoo@velorise.com.sg", emails)
        self.assertNotIn("cosec@velorise.com.sg", emails)

    def test_unqualified_legal_mailbox_still_fires(self):
        text = "For inquiries, email legal@techinsights.sg."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertIn("legal@techinsights.sg", emails)


class BankAccountGuards(unittest.TestCase):
    def test_bank_account_proof_sentence_does_not_eat_prose(self):
        text = "Bank account proof is reviewed without retaining images."
        accounts = [m for r, m in _rules_matched(text) if r == "bank_account"]
        self.assertEqual(accounts, [])

    def test_bank_account_numbers_phrase_does_not_eat_prose(self):
        text = "Do not collect bank account numbers unless necessary."
        accounts = [m for r, m in _rules_matched(text) if r == "bank_account"]
        self.assertEqual(accounts, [])

    def test_zero_placeholder_account_does_not_fire(self):
        text = "The form says Account No.: 00000000 as a generic placeholder."
        accounts = [m for r, m in _rules_matched(text) if r == "bank_account"]
        self.assertNotIn("00000000", accounts)

    def test_placeholder_bank_account_does_not_fire(self):
        text = "Finance provided vendor bank a/c 033-123456-0X (placeholder)."
        accounts = [m for r, m in _rules_matched(text) if r == "bank_account"]
        self.assertNotIn("033-123456-0X", accounts)

    def test_training_placeholder_account_does_not_fire(self):
        text = 'Test fields in the KYC form show "Account No.: 1234-XXXX-XXXX".'
        accounts = [m for r, m in _rules_matched(text) if r == "bank_account"]
        self.assertNotIn("1234-XXXX-XXXX", accounts)

    def test_explicit_bank_account_number_still_fires(self):
        text = "Escrow account 123-456-789-0 is held at East Harbor Bank."
        accounts = [m for r, m in _rules_matched(text) if r == "bank_account"]
        self.assertIn("123-456-789-0", accounts)

    def test_partial_bank_account_ending_still_fires(self):
        text = "Payroll bank account ending -4421 was used for reimbursement."
        accounts = [m for r, m in _rules_matched(text) if r == "bank_account"]
        self.assertIn("bank account ending -4421", accounts)


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

    def test_currency_amount_does_not_swallow_next_word_unit_letter(self):
        text = "Financing includes S$120,000,000 bridge debt."
        amounts = [m for r, m in _rules_matched(text) if r == "financial_amount"]
        self.assertIn("S$120,000,000", amounts)
        self.assertNotIn("S$120,000,000 b", amounts)

    def test_decimal_currency_amount_still_fires_as_whole_amount(self):
        text = "Unpublished valuation range is S$4.20–S$4.60 per share."
        amounts = [m for r, m in _rules_matched(text) if r == "financial_amount"]
        self.assertIn("S$4.20", amounts)
        self.assertIn("S$4.60", amounts)
        self.assertNotIn("S$4", amounts)

    def test_uen_like_token_does_not_fire_as_financial_amount(self):
        text = "Issuer UEN 201912345K appears on the cover page."
        amounts = [m for r, m in _rules_matched(text) if r == "financial_amount"]
        self.assertNotIn("201912345K", amounts)

    def test_public_acra_amount_does_not_fire_as_financial_amount(self):
        text = "Obsidian's 2023 revenue S$80m per public ACRA abstracts."
        amounts = [m for r, m in _rules_matched(text) if r == "financial_amount"]
        self.assertNotIn("S$80m", amounts)

    def test_personal_reimbursement_does_not_fire_as_mnpi_amount(self):
        text = "May expenses included a SGD 9,800 reimbursement paid to Seahaven Commercial Bank."
        amounts = [m for r, m in _rules_matched(text) if r == "financial_amount"]
        self.assertNotIn("SGD 9,800", amounts)

    def test_public_last_traded_price_does_not_fire_as_mnpi_amount(self):
        text = "The last traded price on 12 Jul 2026 was S$1.42 per share (public information)."
        amounts = [m for r, m in _rules_matched(text) if r == "financial_amount"]
        self.assertNotIn("S$1.42", amounts)

    def test_percent_encoded_url_fragment_does_not_fire_as_percentage(self):
        text = "Working link: https://example.sg/annc?ref=HPHL%2F2026-05-28%2F0059"
        percentages = [m for r, m in _rules_matched(text) if r == "financial_percentage"]
        self.assertNotIn("28%", percentages)

    def test_spa_day_does_not_fire_as_definitive_agreement(self):
        text = "Wellness note: spa-day vouchers are unrelated to the deal."
        agreements = [m for r, m in _rules_matched(text) if r == "definitive_agreement"]
        self.assertNotIn("spa", agreements)

    def test_passport_words_without_digits_do_not_fire(self):
        text = "External releases should mask passport digits and no passport numbers are processed."
        passports = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "passport_number"]
        self.assertNotIn("digits", passports)
        self.assertNotIn("numbers", passports)

    def test_negated_genetic_data_context_does_not_fire(self):
        text = "References to genetic algorithms are software features and not about any person's genetic data."
        findings = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "genetic_data"]
        self.assertNotIn("genetic data", findings)


class LargeNumberPrecisionGuards(unittest.TestCase):
    def test_large_number_inside_financial_amount_still_fires_for_locked_recall(self):
        text = "Consideration is S$120,000,000 cash."
        numbers = [m for r, m in _rules_matched(text) if r == "large_number"]
        self.assertIn("120,000,000", numbers)

    def test_large_number_inside_postal_code_is_suppressed(self):
        text = "Registered office: Singapore 049899."
        numbers = [m for r, m in _rules_matched(text) if r == "large_number"]
        self.assertNotIn("049899", numbers)

    def test_large_number_inside_account_reference_is_suppressed(self):
        text = "Finance provided vendor bank a/c 033-123456-0X (placeholder)."
        numbers = [m for r, m in _rules_matched(text) if r == "large_number"]
        self.assertNotIn("123456", numbers)

    def test_large_number_inside_company_number_is_suppressed(self):
        text = "Company No.: 2022012345678-Z and Reg. No.: 201801023456 are registry identifiers."
        numbers = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "large_number"]
        self.assertNotIn("2022012345678", numbers)
        self.assertNotIn("201801023456", numbers)

    def test_large_number_inside_url_identifier_is_suppressed(self):
        text = "Draft link: https://example.my/deal?uid=EID-840102145019&co=201901012345."
        numbers = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "large_number"]
        self.assertNotIn("840102145019", numbers)
        self.assertNotIn("201901012345", numbers)

    def test_large_number_inside_url_path_is_suppressed(self):
        text = "Reference: https://filings.example.my/annc/2025/08/ABBR-20250812-0001.pdf."
        numbers = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "large_number"]
        self.assertNotIn("20250812", numbers)

    def test_zero_mykad_placeholder_is_suppressed(self):
        text = "Prior draft showing NRIC: 000000-00-0000 is invalid and must be purged."
        mykad = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "my_mykad"]
        self.assertNotIn("000000-00-0000", mykad)

    def test_standalone_large_share_count_still_fires(self):
        text = "The seller will transfer 100,000 ordinary shares of Acme Pte. Ltd., UEN 199999999K."
        numbers = [m for r, m in _rules_matched(text) if r == "large_number"]
        self.assertIn("100,000", numbers)


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
