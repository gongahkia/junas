"""Items 102 + 103 + 104: end-to-end engine integration for IN / CN / AE / SA packs.

Mirrors `test/test_sea_packs.py` shape. Covers:

1. All four packs load with their declared recognizers.
2. Each recognizer fires on a canonical sample.
3. Rationales chain the jurisdiction-specific statute reference.
4. Cross-jurisdiction routing (source=SG, destination=IN) chains both suffixes.
"""

import unittest

from kaypoh.review import jurisdictions
from kaypoh.review.citations import pii_rationale
from kaypoh.review.engine import PreSendReviewEngine


class PackLoadTests(unittest.TestCase):
    def test_all_four_packs_load(self):
        jurisdictions.reload_registry()
        for code in ("IN", "CN", "AE", "SA"):
            self.assertIn(code, jurisdictions.RULE_PACKS, f"{code} pack missing")

    def test_each_pack_carries_at_least_one_recognizer(self):
        jurisdictions.reload_registry()
        for code in ("IN", "CN", "AE", "SA"):
            pack = jurisdictions.RULE_PACKS[code]
            self.assertTrue(pack.recognizers, f"{code}: expected ≥1 recognizer, got 0")

    def test_alias_normalisation_works(self):
        jurisdictions.reload_registry()
        for alias, expected in [
            ("INDIA", "IN"), ("IND", "IN"),
            ("CHINA", "CN"), ("PRC", "CN"),
            ("UAE", "AE"), ("UNITED ARAB EMIRATES", "AE"),
            ("KSA", "SA"), ("SAUDI ARABIA", "SA"),
        ]:
            self.assertEqual(jurisdictions.normalize_jurisdiction(alias), expected)


class RecognizerFiringTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _review(self, text: str, code: str):
        return self.engine.review(
            text=text, source_jurisdiction=code, destination_jurisdiction=code,
            entity_id=None, include_suggestions=False, document_type="memo",
            review_profile="strict",
        )

    # --- IN ---

    def test_in_aadhaar_fires_on_valid_vector(self):
        r = self._review("Mr Rajan's Aadhaar 234123412346 is on file.", "IN")
        rules = {f.rule for f in r.findings}
        self.assertIn("in_aadhaar", rules)

    def test_in_aadhaar_rejects_zero_leading(self):
        r = self._review("Aadhaar 012345678901 is invalid.", "IN")
        self.assertNotIn("in_aadhaar", {f.rule for f in r.findings})

    def test_in_pan_fires(self):
        r = self._review("PAN ABCPK1234A registered.", "IN")
        self.assertIn("in_pan", {f.rule for f in r.findings})

    def test_in_gstin_fires(self):
        r = self._review("GSTIN 27ABCPK1234A1Z5 belongs to the Mumbai entity.", "IN")
        self.assertIn("in_gstin", {f.rule for f in r.findings})

    def test_in_voter_id_fires(self):
        r = self._review("EPIC ABC1234567 verified.", "IN")
        self.assertIn("in_voter_id", {f.rule for f in r.findings})

    # --- CN ---

    def test_cn_resident_id_fires_on_valid_vector(self):
        r = self._review("身份证号 11010519491231002X 已确认.", "CN")
        self.assertIn("cn_resident_id", {f.rule for f in r.findings})

    def test_cn_resident_id_fires_in_english_context(self):
        r = self._review("Resident ID 11010519491231002X on file.", "CN")
        self.assertIn("cn_resident_id", {f.rule for f in r.findings})

    def test_cn_uscc_fires(self):
        r = self._review("Unified Social Credit Code 91350100M000100Y43 verified.", "CN")
        self.assertIn("cn_uscc", {f.rule for f in r.findings})

    def test_cn_phone_fires_with_context(self):
        r = self._review("Mobile 13800138000 reachable.", "CN")
        self.assertIn("cn_phone", {f.rule for f in r.findings})

    def test_cn_passport_fires(self):
        r = self._review("Passport E12345678 issued.", "CN")
        self.assertIn("cn_passport", {f.rule for f in r.findings})

    def test_cn_public_service_line_does_not_fire_as_phone(self):
        r = self._review(
            "For queries, call +86 400-000-0000; this is a public service line.",
            "CN",
        )
        self.assertNotIn("phone_number", {f.rule for f in r.findings})

    def test_cn_educational_insider_list_and_barrier_bait_do_not_fire(self):
        r = self._review(
            "For educational purposes only: explain how insider lists support "
            "compliance and what an information barrier is.",
            "CN",
        )
        rules = {f.rule for f in r.findings}
        self.assertNotIn("insider_list_marker", rules)
        self.assertNotIn("information_barrier_marker", rules)

    def test_cn_training_term_sheet_and_negated_mac_bait_do_not_fire(self):
        r = self._review(
            "The term sheet sample in this training deck is public-source guidance. "
            "The mac clause language is negated and does not by itself signal a "
            "material adverse change.",
            "CN",
        )
        rules = {f.rule for f in r.findings}
        self.assertNotIn("definitive_agreement", rules)
        self.assertNotIn("material_adverse_change", rules)

    # --- AE ---

    def test_ae_emirates_id_fires_dashed(self):
        r = self._review("Emirates ID 784-1975-1234567-1 verified.", "AE")
        self.assertIn("ae_emirates_id", {f.rule for f in r.findings})

    def test_ae_emirates_id_fires_no_dashes(self):
        r = self._review("EID 784197512345671 on file.", "AE")
        self.assertIn("ae_emirates_id", {f.rule for f in r.findings})

    def test_ae_passport_fires(self):
        r = self._review("UAE Passport A12345678 issued in DXB.", "AE")
        self.assertIn("ae_passport", {f.rule for f in r.findings})

    # --- SA ---

    def test_sa_national_id_fires(self):
        r = self._review("National ID 1234567890 attached.", "SA")
        self.assertIn("sa_national_id", {f.rule for f in r.findings})

    def test_sa_iqama_fires(self):
        r = self._review("Iqama 2345678901 verified.", "SA")
        self.assertIn("sa_iqama", {f.rule for f in r.findings})

    def test_sa_commercial_registration_fires(self):
        r = self._review("CR No 1234567890 issued by MoC.", "SA")
        self.assertIn("sa_commercial_registration", {f.rule for f in r.findings})


class RationaleTests(unittest.TestCase):
    def test_in_aadhaar_rationale_cites_dpdpa(self):
        text = pii_rationale(rule="in_aadhaar", jurisdiction="IN", matched_text="234123412346")
        self.assertIn("DPDPA 2023", text)
        self.assertIn("Digital Personal Data Protection Act", text)

    def test_in_pan_rationale_cites_cbdt(self):
        text = pii_rationale(rule="in_pan", jurisdiction="IN", matched_text="ABCPK1234A")
        self.assertIn("CBDT", text)

    def test_cn_resident_id_rationale_cites_pipl(self):
        text = pii_rationale(rule="cn_resident_id", jurisdiction="CN",
                             matched_text="11010519491231002X")
        self.assertIn("PIPL 2021 Art 4", text)
        self.assertIn("China Personal Information Protection Law", text)

    def test_cn_uscc_rationale_cites_gb_32100(self):
        text = pii_rationale(rule="cn_uscc", jurisdiction="CN",
                             matched_text="91350100M000100Y43")
        self.assertIn("GB 32100-2015", text)

    def test_ae_emirates_id_rationale_cites_pdpl(self):
        text = pii_rationale(rule="ae_emirates_id", jurisdiction="AE",
                             matched_text="784197512345671")
        self.assertIn("UAE PDPL", text)
        self.assertIn("Federal Decree-Law 45/2021", text)

    def test_sa_national_id_rationale_cites_sdaia(self):
        text = pii_rationale(rule="sa_national_id", jurisdiction="SA",
                             matched_text="1234567890")
        self.assertIn("KSA PDPL", text)
        self.assertIn("SDAIA", text)

    def test_cross_jurisdiction_chains_both_suffixes_in_sg(self):
        # source=SG, destination=IN should chain both PDPA + DPDPA suffixes.
        text = pii_rationale(rule="in_aadhaar", jurisdiction="IN+SG",
                             matched_text="234123412346")
        self.assertIn("DPDPA", text)
        self.assertIn("Personal Data Protection Act 2012", text)


if __name__ == "__main__":
    unittest.main()
