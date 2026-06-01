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

    def test_indonesian_no_mnpi_marker_does_not_fire(self):
        text = "Kesimpulan: tidak ada MNPI baru dalam materi publik ini."
        for rule, matched in _rules_matched(text, jurisdiction="ID"):
            self.assertNotEqual(
                rule,
                "nonpublic_marker",
                f"Indonesian no-MNPI marker should be suppressed; got {matched!r}",
            )

    def test_indonesian_public_transaction_status_does_not_fire_material_event(self):
        text = (
            "Public Transaction Status: the acquisition was announced on IDXNet on 12 May 2025, "
            "and no material non-public information remains in this memo."
        )
        for rule, matched in _rules_matched(text, jurisdiction="ID"):
            self.assertNotEqual(
                rule,
                "material_event",
                f"public/no-MNPI Indonesia transaction status should be suppressed; got {matched!r}",
            )

    def test_no_new_material_terms_line_does_not_fire_material_event(self):
        text = "No new material terms, pricing, or financing arrangements are included here."
        for rule, matched in _rules_matched(text, jurisdiction="ID"):
            self.assertNotEqual(
                rule,
                "material_event",
                f"no-new-material-terms line should not be material_event; got {matched!r}",
            )

    def test_indonesian_public_context_heading_does_not_fire_material_event(self):
        text = (
            "Corporate context: Indonesian fintech issuer with employment onboarding "
            "for post-acquisition integration."
        )
        for rule, matched in _rules_matched(text, jurisdiction="ID"):
            self.assertNotEqual(
                rule,
                "material_event",
                f"public context heading should not be material_event; got {matched!r}",
            )

    def test_anti_fraud_transfer_line_does_not_fire_material_event(self):
        text = "Cross-border transfer for anti-fraud analytics is approved under Data Export Approval DEA-2026-11."
        for rule, matched in _rules_matched(text, jurisdiction="ID"):
            self.assertNotEqual(
                rule,
                "material_event",
                f"anti-fraud privacy-transfer line should not be material_event; got {matched!r}",
            )

    def test_public_employment_integration_line_does_not_fire_material_event(self):
        text = "Employment integration (public): HR will roll out a voluntary wellness program post-closing."
        for rule, matched in _rules_matched(text, jurisdiction="ID"):
            self.assertNotEqual(
                rule,
                "material_event",
                f"public employment-integration line should not be material_event; got {matched!r}",
            )

    def test_indonesian_negated_mac_does_not_fire(self):
        text = "Draft SPA tidak memuat klausul material adverse change (bukan MAC)."
        for rule, matched in _rules_matched(text, jurisdiction="ID"):
            self.assertNotEqual(
                rule,
                "material_adverse_change",
                f"Indonesian negated MAC line should be suppressed; got {matched!r}",
            )

    def test_no_event_material_adverse_change_does_not_fire(self):
        text = "No event has occurred that would reasonably be expected to constitute a Material Adverse Change."
        for rule, matched in _rules_matched(text, jurisdiction="ID"):
            self.assertNotEqual(
                rule,
                "material_adverse_change",
                f"no-event MAC line should be suppressed; got {matched!r}",
            )

    def test_no_mac_explainer_does_not_fire_material_adverse_change(self):
        text = 'The phrase "no MAC" refers to material adverse change, not a hardware address.'
        for rule, matched in _rules_matched(text, jurisdiction="PH"):
            self.assertNotEqual(
                rule,
                "material_adverse_change",
                f"explanatory no-MAC line should be suppressed; got {matched!r}",
            )

    def test_not_intended_to_trigger_mae_clause_does_not_fire(self):
        text = "This sentence is not intended to trigger any MAC/MAE clause."
        for rule, matched in _rules_matched(text, jurisdiction="PH"):
            self.assertNotEqual(
                rule,
                "material_adverse_change",
                f"negated MAE-trigger line should be suppressed; got {matched!r}",
            )

    def test_vietnamese_negated_material_adverse_change_does_not_fire(self):
        text = 'Không phải là "material adverse change" theo điều 9.4 của hợp đồng tín dụng.'
        for rule, matched in _rules_matched(text, jurisdiction="VN"):
            self.assertNotEqual(
                rule,
                "material_adverse_change",
                f"Vietnamese negated MAC line should be suppressed; got {matched!r}",
            )

    def test_nothing_herein_material_adverse_change_does_not_fire(self):
        text = "For avoidance of doubt, nothing herein constitutes or admits a material adverse change."
        for rule, matched in _rules_matched(text, jurisdiction="VN"):
            self.assertNotEqual(
                rule,
                "material_adverse_change",
                f"nothing-herein MAC line should be suppressed; got {matched!r}",
            )

    def test_real_material_adverse_change_still_fires(self):
        text = "The lender may terminate if a material adverse change occurs before closing."
        self.assertIn(("material_adverse_change", "material adverse change"), _rules_matched(text, jurisdiction="VN"))

    def test_mae_clause_has_not_been_triggered_does_not_fire(self):
        text = "The definitive agreement is public; the mae clause has not been triggered."
        self.assertNotIn("material_adverse_change", {r for r, _ in _rules_matched(text, jurisdiction="EU")})

    def test_no_event_expected_to_result_in_mac_does_not_fire_contingent(self):
        text = (
            "No event has occurred that would reasonably be expected to result in "
            "a material adverse change as defined in the filed contract."
        )
        rules = {r for r, _ in _rules_matched(text, jurisdiction="EU")}
        self.assertNotIn("contingent_mnpi_language", rules)


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

    def test_phone_span_stops_before_following_list_number(self):
        text = "1. Lead contact phone: +65 9123 4567.\n\n2. Next party starts here."
        phones = [m for r, m in _rules_matched(text) if r == "phone_number"]
        self.assertIn("+65 9123 4567", phones)
        self.assertNotIn("+65 9123 4567.\n\n2", phones)

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

    def test_sg_country_code_toll_free_enquiries_line_does_not_fire(self):
        text = "For procedural queries only, call the fictional SGX Enquiries Line at +65 1800 222 0000."
        phones = [m for r, m in _rules_matched(text) if r == "phone_number"]
        self.assertNotIn("+65 1800 222 0000", phones)

    def test_public_hotline_and_public_line_do_not_fire(self):
        text = (
            "Public hotline for HR queries: 1-300-88-0000. "
            "The Exchange Investor Helpline is 03-6200 0000 (public line)."
        )
        phones = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "phone_number"]
        self.assertNotIn("1-300-88-0000", phones)
        self.assertNotIn("03-6200 0000", phones)

    def test_indonesian_toll_free_hotline_does_not_fire(self):
        text = "Hotline investor 0800-11-12345 adalah nomor publik dan bukan nomor pribadi."
        phones = [m for r, m in _rules_matched(text, jurisdiction="ID") if r == "phone_number"]
        self.assertNotIn("0800-11-12345", phones)

    def test_phone_does_not_fire_on_dates_or_ip_literals(self):
        text = "DOB 14-03-1990; session ref 2026-05-28; IP 192.0.2.17."
        phones = [m for r, m in _rules_matched(text) if r == "phone_number"]
        self.assertNotIn("14-03-1990", phones)
        self.assertNotIn("2026-05-28", phones)
        self.assertNotIn("192.0.2.17", phones)

    def test_phone_does_not_fire_on_dotted_eu_dates(self):
        text = "Board memo dated 31.05.2026; OAM filing was posted on 30.04.2026."
        phones = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "phone_number"]
        self.assertNotIn("31.05.2026", phones)
        self.assertNotIn("30.04.2026", phones)

    def test_phone_does_not_fire_on_obfuscated_vat_or_tax_id(self):
        text = "VAT N o .: N R 1 2 3 4 5 6 7 Q; branch tax ID L V 3 3 1 2 9 9 9 9 9."
        phones = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "phone_number"]
        self.assertNotIn("1 2 3 4 5 6 7", phones)
        self.assertNotIn("3 3 1 2 9 9 9 9 9", phones)

    def test_phone_does_not_fire_on_obfuscated_passport_digits(self):
        text = "Data subject row: pa s s p o r t N R - P 1 2 3 4 5 6 7."
        phones = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "phone_number"]
        self.assertNotIn("1 2 3 4 5 6 7", phones)

    def test_real_mobile_after_obfuscated_passport_still_fires(self):
        text = "Contact: pass port T H 9 1 2 3 4 5 6 7 (temporary issue), mobile 09-4556-2103."
        phones = [m for r, m in _rules_matched(text, jurisdiction="TH") if r == "phone_number"]
        self.assertIn("09-4556-2103", phones)

    def test_phone_does_not_fire_on_isin_or_lei_fragments(self):
        text = "Issuer identifiers: LEI 000000ORLANTASE01, ISIN ZX0000000001."
        phones = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "phone_number"]
        self.assertNotIn("0000000001", phones)

    def test_public_support_hotline_does_not_fire_as_phone(self):
        text = "Vendor support hotline +800 555 1212 is public and should not be captured as PII."
        phones = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "phone_number"]
        self.assertNotIn("+800 555 1212", phones)

    def test_phone_does_not_fire_inside_filing_reference(self):
        text = "Regulatory chronology: OCMA filing ref OCM-26-000000 submitted."
        phones = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "phone_number"]
        self.assertNotIn("26-000000", phones)

    def test_placeholder_country_code_phone_does_not_fire(self):
        text = "Contact placeholder tel: +3X-120-000-000; use a real number only after approval."
        phones = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "phone_number"]
        self.assertNotIn("120-000-000", phones)

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

    def test_phone_does_not_fire_on_indonesian_nib_npwp_or_rekening(self):
        text = (
            "NPWP 45.987.321.0-123.456, NIB 2315478901234, "
            "and no. rekening 065-889912-44 are identifiers, not personal phone numbers."
        )
        phones = [m for r, m in _rules_matched(text, jurisdiction="ID") if r == "phone_number"]
        self.assertNotIn("2315478901234", phones)
        self.assertNotIn("065-889912-44", phones)

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

    def test_phone_does_not_fire_on_thai_id_like_invalid_example(self):
        text = "Invalid Thai National ID 1-2345-67890-12-3 is example bait, not a phone."
        phones = [m for r, m in _rules_matched(text, jurisdiction="TH") if r == "phone_number"]
        self.assertNotIn("1-2345-67890-12-3", phones)

    def test_phone_does_not_fire_on_ph_benefit_identifier_fragments(self):
        text = "Pag-IBIG MID: 12-345678901-2 and PhilHealth No.: 17-123456789-3 are benefit IDs."
        phones = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "phone_number"]
        self.assertNotIn("12-345678901-2", phones)
        self.assertNotIn("17-123456789-3", phones)

    def test_phone_does_not_fire_on_ph_bankacct_ocr_or_doccode_fragments(self):
        text = (
            "BankAcct PH-9800  44  23-x9 is a masked account. "
            "Draft scan has OCR artifacts like R e f 1 7 - C - 0 5 - 2 2. "
            "doccode AZC-IR-2026-0715."
        )
        phones = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "phone_number"]
        self.assertNotIn("9800  44  23", phones)
        self.assertNotIn("0 5 - 2 2", phones)
        self.assertNotIn("2026-0715", phones)

    def test_ph_public_hr_helpdesk_general_line_does_not_fire(self):
        text = "Route staff to the HR helpdesk at +63 2 8555 0000 (general line)."
        phones = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "phone_number"]
        self.assertNotIn("+63 2 8555 0000", phones)

    def test_ph_obfuscated_mobile_still_fires(self):
        text = "Internal HR mobile contact: + 6 3 9 9 8  21  3 6 700."
        phones = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "phone_number"]
        self.assertIn("6 3 9 9 8  21  3 6 700", phones)

    def test_vietnamese_mst_vat_tin_values_do_not_fire_as_phone(self):
        text = (
            "ERC/MST: 0319123456; dependent branch MST 0319123456-001; "
            "vendor VAT/TINs example 0123456789 is invalid."
        )
        phones = [m for r, m in _rules_matched(text, jurisdiction="VN") if r == "phone_number"]
        self.assertNotIn("0319123456", phones)
        self.assertNotIn("0319123456-001", phones)
        self.assertNotIn("0123456789", phones)

    def test_vietnamese_mst_vat_tin_values_do_not_fire_as_large_number(self):
        text = (
            "ERC/MST: 0319123456; dependent branch MST 0319123456-001; "
            "vendor VAT/TINs example 0123456789 is invalid."
        )
        numbers = [m for r, m in _rules_matched(text, jurisdiction="VN") if r == "large_number"]
        self.assertNotIn("0319123456", numbers)
        self.assertNotIn("0123456789", numbers)

    def test_vietnamese_public_hotline_does_not_fire(self):
        text = "Đường dây tiếp nhận công bố: 1900 772 233 (tổng đài giả định dùng chung, công khai)."
        phones = [m for r, m in _rules_matched(text, jurisdiction="VN") if r == "phone_number"]
        self.assertNotIn("1900 772 233", phones)

    def test_vietnamese_mobile_still_fires(self):
        text = "Personal mobile for employee follow-up: +84 90 123 4567."
        phones = [m for r, m in _rules_matched(text, jurisdiction="VN") if r == "phone_number"]
        self.assertIn("+84 90 123 4567", phones)


class DeviceIdentifierPrecisionGuards(unittest.TestCase):
    def test_negated_mac_address_example_does_not_fire(self):
        text = "Security note: this is not a MAC address aa-bb-cc-dd-ee-ff."
        macs = [m for r, m in _rules_matched(text, jurisdiction="IN") if r == "mac_address"]
        self.assertNotIn("aa-bb-cc-dd-ee-ff", macs)

    def test_canonical_mac_address_still_fires(self):
        text = "Device MAC: aa-bb-cc-dd-ee-ff."
        macs = [m for r, m in _rules_matched(text, jurisdiction="IN") if r == "mac_address"]
        self.assertIn("aa-bb-cc-dd-ee-ff", macs)


class PhilippinesPrivacyAndTaxGuards(unittest.TestCase):
    def test_fulfilled_dsar_without_pending_request_does_not_fire(self):
        text = (
            "A DSAR (Ref: HR-DSAR-0041) was fulfilled on 2026-05-12. "
            "No DSARs are pending, and no request for correction is currently in flight."
        )
        markers = [
            m for r, m in _rules_matched(text, jurisdiction="PH")
            if r == "consent_withdrawal_marker"
        ]
        self.assertNotIn("DSAR", markers)
        self.assertNotIn("DSARs", markers)

    def test_live_dsar_still_fires(self):
        text = "DSAR received: Mr. Iker Malonzo requested access to his personnel file."
        markers = [
            m for r, m in _rules_matched(text, jurisdiction="PH")
            if r == "consent_withdrawal_marker"
        ]
        self.assertIn("DSAR", markers)

    def test_ph_tin_inside_bank_account_line_does_not_fire(self):
        text = "Temporary Account No.: 0012-345-678-901 for settlement testing."
        tins = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "ph_tin"]
        self.assertNotIn("345-678-901", tins)

    def test_ph_invalid_sample_tin_does_not_fire(self):
        text = "The sample identifier TIN 123-456-789-001 is invalid and for training only."
        tins = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "ph_tin"]
        self.assertNotIn("123-456-789-001", tins)

    def test_ph_real_tin_still_fires(self):
        text = "Payroll tax details under TIN 074-882-619-000 are stored in HRMS."
        tins = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "ph_tin"]
        self.assertIn("074-882-619-000", tins)

    def test_ph_philsys_positive_does_not_become_phone(self):
        text = "PhilSys PSN: 1234-5678-9012 belongs to the employee file."
        rules = _rules_matched(text, jurisdiction="PH")
        self.assertIn(("ph_philsys", "1234-5678-9012"), rules)
        self.assertNotIn(("phone_number", "1234-5678-9012"), rules)


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

    def test_personal_email_after_company_line_still_fires(self):
        text = "Ms. Clara Lim\nHuman Resources Manager\nQuantum Insights Pte. Ltd.  \nclara.lim@quantuminsights.sg"
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertIn("clara.lim@quantuminsights.sg", emails)

    def test_ph_role_mailboxes_do_not_fire(self):
        text = (
            "Route disclosure to disclosure@example.ph, privacydesk@example.ph, "
            "walloffice@example.ph, and irmailbox@example.ph."
        )
        emails = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "email_address"]
        self.assertNotIn("disclosure@example.ph", emails)
        self.assertNotIn("privacydesk@example.ph", emails)
        self.assertNotIn("walloffice@example.ph", emails)
        self.assertNotIn("irmailbox@example.ph", emails)

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

    def test_public_contacts_non_pii_email_does_not_fire(self):
        text = "Public contacts that are non-PII: careers@example.sg and generic form labels."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("careers@example.sg", emails)

    def test_generic_mailbox_channel_does_not_fire(self):
        text = "Submission channels prefer generic mailboxes such as mna-team@example.sg."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("mna-team@example.sg", emails)

    def test_procedural_enquiries_mailbox_does_not_fire(self):
        text = "For procedural queries only, write to sgx-enquiries@public.example.com."
        emails = [m for r, m in _rules_matched(text) if r == "email_address"]
        self.assertNotIn("sgx-enquiries@public.example.com", emails)


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

    def test_ocr_mixed_case_employee_id_does_not_partial_match(self):
        text = "Catatan sensitif disimpan under id karyawan EMP-2O26-l1l."
        employees = [m for r, m in _rules_matched(text, jurisdiction="ID") if r == "employee_id"]
        self.assertNotIn("2O26-", employees)

    def test_audit_hash_employee_like_token_does_not_fire(self):
        text = "The Q2 auto-deletion job completed with audit hash A-EMP-26-044."
        employees = [m for r, m in _rules_matched(text, jurisdiction="ID") if r == "employee_id"]
        self.assertNotIn("26-044", employees)

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

    def test_already_public_exchange_budget_does_not_fire_as_mnpi_amount(self):
        text = "Plant expansion budget THB 450m is already public per SETNews filing."
        amounts = [m for r, m in _rules_matched(text, jurisdiction="TH") if r == "financial_amount"]
        self.assertNotIn("THB 450m", amounts)

    def test_percent_encoded_url_fragment_does_not_fire_as_percentage(self):
        text = "Working link: https://example.sg/annc?ref=HPHL%2F2026-05-28%2F0059"
        percentages = [m for r, m in _rules_matched(text) if r == "financial_percentage"]
        self.assertNotIn("28%", percentages)

    def test_spa_day_does_not_fire_as_definitive_agreement(self):
        text = "Wellness note: spa-day vouchers are unrelated to the deal."
        agreements = [m for r, m in _rules_matched(text) if r == "definitive_agreement"]
        self.assertNotIn("spa", agreements)

    def test_spa_day_with_space_does_not_fire_as_definitive_agreement(self):
        text = "Book HR spa day pilot Friday at 14:00."
        agreements = [m for r, m in _rules_matched(text) if r == "definitive_agreement"]
        self.assertNotIn("spa", agreements)

    def test_wellness_spa_room_does_not_fire_as_definitive_agreement(self):
        text = "Book the small conference room, not the spa, and ignore the wellness-week vouchers."
        agreements = [m for r, m in _rules_matched(text, jurisdiction="VN") if r == "definitive_agreement"]
        self.assertNotIn("spa", agreements)

    def test_share_purchase_agreement_abbreviation_still_fires(self):
        text = "Draft SPA for the private placement remains confidential before announcement."
        agreements = [m for r, m in _rules_matched(text, jurisdiction="VN") if r == "definitive_agreement"]
        self.assertIn("SPA", agreements)

    def test_passport_words_without_digits_do_not_fire(self):
        text = "External releases should mask passport digits and no passport numbers are processed."
        passports = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "passport_number"]
        self.assertNotIn("digits", passports)
        self.assertNotIn("numbers", passports)

    def test_negated_genetic_data_context_does_not_fire(self):
        text = "References to genetic algorithms are software features and not about any person's genetic data."
        findings = [m for r, m in _rules_matched(text, jurisdiction="MY") if r == "genetic_data"]
        self.assertNotIn("genetic data", findings)

    def test_no_genetic_data_kept_context_does_not_fire(self):
        text = "Ms. Hana Noor had her leave schedule accessed; no genetic data was kept in this repository."
        findings = [m for r, m in _rules_matched(text) if r == "genetic_data"]
        self.assertNotIn("genetic data", findings)

    def test_genetic_data_category_label_only_does_not_fire(self):
        text = "The term genetic data is a category label only and does not describe any person's sensitive data."
        findings = [m for r, m in _rules_matched(text) if r == "genetic_data"]
        self.assertNotIn("genetic data", findings)

    def test_no_material_nonpublic_information_does_not_fire_marker(self):
        text = "No material non-public information under the SRC should be circulated outside the blackout list."
        markers = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "nonpublic_marker"]
        self.assertNotIn("material non-public information", markers)

    def test_ph_mnpi_control_and_bait_lines_do_not_fire_marker(self):
        text = (
            "MNPI controls are reviewed quarterly. "
            "This promo should not be treated as PII or MNPI. "
            "Operational details could be construed as MNPI, so they were avoided."
        )
        markers = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "nonpublic_marker"]
        self.assertEqual(markers, [])

    def test_ph_public_reference_materials_do_not_fire_material_event(self):
        text = "Reference materials are public: the press release on dividend policy is posted on our website."
        events = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "material_event"]
        self.assertEqual(events, [])

    def test_ph_compliance_or_npc_guidance_does_not_fire_material_event(self):
        text = "Compliance guidance on cyber tabletop protocols follows NPC guidance and contains no live incident."
        events = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "material_event"]
        self.assertEqual(events, [])

    def test_ph_training_week_wall_crossing_does_not_fire(self):
        text = "Information barriers use a wall-crossing role mailbox during blackout training weeks."
        rules = _rules_matched(text, jurisdiction="PH")
        self.assertNotIn(("insider_list_marker", "wall-crossing"), rules)
        self.assertNotIn(("information_barrier_marker", "Information barriers"), rules)

    def test_ph_fully_announced_term_sheet_does_not_fire(self):
        text = (
            "The term sheet excerpts cited in the deck are from transactions that closed in 2022 "
            "and have been fully announced."
        )
        agreements = [m for r, m in _rules_matched(text, jurisdiction="PH") if r == "definitive_agreement"]
        self.assertNotIn("term sheet", agreements)

    def test_negated_special_category_list_does_not_fire(self):
        text = (
            "Do not include any religion, union membership, political opinions, "
            "biometric templates, genetic data, or sexual orientation."
        )
        findings = [
            m for r, m in _rules_matched(text, jurisdiction="PH")
            if r in {"genetic_data", "sexual_orientation", "religious_belief"}
        ]
        self.assertEqual(findings, [])


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

    def test_large_number_inside_indonesian_nib_and_rekening_is_suppressed(self):
        text = "NIB 9999999999999 and no. rekening 065-889912-44 are registry/payment identifiers."
        numbers = [m for r, m in _rules_matched(text, jurisdiction="ID") if r == "large_number"]
        self.assertNotIn("9999999999999", numbers)
        self.assertNotIn("889912", numbers)

    def test_large_number_inside_indonesian_wallet_or_wa_link_is_suppressed(self):
        text = "Akun internal 88-120394-07 is not bank data; wa.me/6281123456789 is a contact link."
        numbers = [m for r, m in _rules_matched(text, jurisdiction="ID") if r == "large_number"]
        self.assertNotIn("120394", numbers)
        self.assertNotIn("12345678", numbers)

    def test_large_number_inside_phone_number_is_suppressed(self):
        text = "Contact finance at 021-12345678 for scheduling."
        numbers = [m for r, m in _rules_matched(text, jurisdiction="ID") if r == "large_number"]
        self.assertNotIn("12345678", numbers)

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


class EuCandidatePrecisionGuards(unittest.TestCase):
    def test_split_obfuscated_email_fragment_does_not_fire(self):
        text = "Contact Ms. Petra Kovacs at petra.kov   acs@lunara.eu after approval."
        emails = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "email_address"]
        self.assertNotIn("acs@lunara.eu", emails)

    def test_role_placeholder_email_does_not_fire(self):
        text = "Generic form placeholder: Email [role@auroracarbon.eu]."
        emails = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "email_address"]
        self.assertNotIn("role@auroracarbon.eu", emails)

    def test_passport_template_value_does_not_fire(self):
        text = "Passport field in HR template reads Passport No: ORD0000000 solely as a format example."
        passports = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "passport_number"]
        self.assertNotIn("ORD0000000", passports)

    def test_real_passport_survives_neighboring_invalid_hkid_note(self):
        text = "Employee secondee: Ms. Li Mei-yan (HKSAR Passport K1234567; HKID W 1 2 3 4 5 6 (3) invalid in scan)."
        passports = [m for r, m in _rules_matched(text, jurisdiction="HK") if r == "passport_number"]
        self.assertIn("K1234567", passports)

    def test_large_number_inside_eu_registry_identifiers_is_suppressed(self):
        text = (
            "Oridonia Companies Register No. OCR-2023-004512; "
            "identifier placeholders include ISIN: ZZ-ARX-123456 and branch tax ID NR-TAX-8842012."
        )
        numbers = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "large_number"]
        self.assertNotIn("004512", numbers)
        self.assertNotIn("123456", numbers)
        self.assertNotIn("8842012", numbers)

    def test_log_id_fragment_does_not_fire_as_financial_amount(self):
        text = "Last purge deleted hashes only, log id: PRG-A9-7b."
        amounts = [m for r, m in _rules_matched(text, jurisdiction="EU") if r == "financial_amount"]
        self.assertNotIn("7b", amounts)


class EducationalMnpiMarkerGuards(unittest.TestCase):
    def test_training_insider_list_reference_does_not_fire(self):
        text = "Training materials only reference insider lists and blackout windows; they are educational."
        rules = [r for r, _ in _rules_matched(text, jurisdiction="ID")]
        self.assertNotIn("insider_list_marker", rules)

    def test_policy_training_information_barrier_reference_does_not_fire(self):
        text = "Policy training example: information barrier and blackout are not market-moving events."
        rules = [r for r, _ in _rules_matched(text, jurisdiction="ID")]
        self.assertNotIn("information_barrier_marker", rules)


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
