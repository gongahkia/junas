"""SG wedge second slice (item 48).

Narrow, source-backed recognizers for SG matter/property/admin references:
IPOS TM numbers, ACRA/Bizfile transaction numbers, HDB matter refs, SLA lot/title-plan
refs, and URA planning submission/decision refs. Each rule has positive recall and
adversarial precision cases so generic business/property prose does not fire.
"""

import unittest

from junas.review.citations import pii_rationale
from junas.review.engine import PreSendReviewEngine


class _SgWedgeSecondSliceBase(unittest.TestCase):
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


class SgIposTmNumberTests(_SgWedgeSecondSliceBase):
    def test_legacy_tm_number_fires(self):
        hits = self._findings_by_rule("Application number: TM No. T8601301A", "sg_ipos_tm_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "T8601301A")

    def test_legacy_tm_number_with_suffix_fires(self):
        hits = self._findings_by_rule("Trade Mark Application No. T0722229A-02", "sg_ipos_tm_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "T0722229A-02")

    def test_newer_40_series_tm_number_fires(self):
        hits = self._findings_by_rule("IPOS trade mark: 40201515702X", "sg_ipos_tm_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "40201515702X")

    def test_tm_shaped_token_without_ipos_anchor_does_not_fire(self):
        hits = self._findings_by_rule("Internal SKU T8601301A ships tomorrow.", "sg_ipos_tm_number")
        self.assertEqual(hits, [])


class SgAcraTransactionTests(_SgWedgeSecondSliceBase):
    def test_bizfile_transaction_number_fires(self):
        hits = self._findings_by_rule("Bizfile Transaction No.: T250008051", "sg_acra_transaction_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "T250008051")

    def test_acra_lodgement_ref_fires(self):
        hits = self._findings_by_rule("ACRA lodgement ref: A250123456", "sg_acra_transaction_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "A250123456")

    def test_generic_transaction_date_does_not_fire(self):
        hits = self._findings_by_rule("Transaction number 20250101 was the invoice date.", "sg_acra_transaction_number")
        self.assertEqual(hits, [])


class SgHdbReferenceTests(_SgWedgeSecondSliceBase):
    def test_hfe_reference_fires(self):
        hits = self._findings_by_rule("HFE reference number: HFE202501234", "sg_hdb_reference")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "HFE202501234")

    def test_resale_case_number_fires(self):
        hits = self._findings_by_rule("Please quote resale case number RS2025001234.", "sg_hdb_reference")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "RS2025001234")

    def test_otp_serial_number_fires(self):
        hits = self._findings_by_rule("OTP Serial Number: 12345678", "sg_hdb_reference")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "12345678")

    def test_hdb_reference_label_required(self):
        hits = self._findings_by_rule("The HDB showroom code HFE202501234 is a sample.", "sg_hdb_reference")
        self.assertEqual(hits, [])


class SgSlaLotAndPlanTests(_SgWedgeSecondSliceBase):
    def test_mk_land_lot_fires(self):
        hits = self._findings_by_rule("SLA Lot Number and MK/TS: MK12 12345A", "sg_sla_lot_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "MK12 12345A")

    def test_ts_lot_with_part_suffix_fires(self):
        hits = self._findings_by_rule("URA mkts_lotno: TS13 01015C PT", "sg_sla_lot_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "TS13 01015C PT")

    def test_strata_lot_prefix_fires(self):
        hits = self._findings_by_rule("strata lot MK03 U12345X in the schedule", "sg_sla_lot_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "MK03 U12345X")

    def test_lot_without_check_alphabet_does_not_fire(self):
        hits = self._findings_by_rule("Lot Number MK12 12345 was typed without a check letter.", "sg_sla_lot_number")
        self.assertEqual(hits, [])

    def test_mcst_plan_number_fires(self):
        hits = self._findings_by_rule("MCST 1001 endorsed the submission.", "sg_sla_title_plan_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "1001")

    def test_rt_plan_number_fires(self):
        hits = self._findings_by_rule("Registrar of Title Plan No. RT12345", "sg_sla_title_plan_number")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "RT12345")

    def test_mcst_without_number_does_not_fire(self):
        hits = self._findings_by_rule(
            "The MCST committee will review the renovation guide.",
            "sg_sla_title_plan_number",
        )
        self.assertEqual(hits, [])


class SgUraPlanningReferenceTests(_SgWedgeSecondSliceBase):
    def test_parent_submission_number_fires(self):
        hits = self._findings_by_rule("parent submission number 010903-15A2", "sg_ura_planning_reference")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "010903-15A2")

    def test_decision_number_fires(self):
        hits = self._findings_by_rule("URA decision no: P291210-03B1-Z000", "sg_ura_planning_reference")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].matched_text, "P291210-03B1-Z000")

    def test_bare_submission_number_does_not_fire(self):
        hits = self._findings_by_rule("Reference 010903-15A2 in the internal folder.", "sg_ura_planning_reference")
        self.assertEqual(hits, [])


class SgWedgeSecondSliceCitationTests(unittest.TestCase):
    def test_new_rule_rationales_are_registered(self):
        for rule in [
            "sg_ipos_tm_number",
            "sg_acra_transaction_number",
            "sg_hdb_reference",
            "sg_sla_lot_number",
            "sg_sla_title_plan_number",
            "sg_ura_planning_reference",
        ]:
            with self.subTest(rule=rule):
                text = pii_rationale(rule=rule, jurisdiction="SG", matched_text="x")
                self.assertIn("Singapore", text)
                self.assertGreater(len(text), 40)


class SgWedgeSecondSliceMultiFiringTests(_SgWedgeSecondSliceBase):
    def test_all_second_slice_rules_can_fire_in_one_real_estate_memo(self):
        text = (
            "IPOS TM No. 40201515702X is attached. "
            "Bizfile Transaction No.: T250008051 remains pending. "
            "HFE reference number: HFE202501234; SLA Lot Number MK12 12345A; "
            "MCST 1001; URA decision no: P291210-03B1-Z000."
        )
        result = self.engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        rules = {f.rule for f in result.findings}
        self.assertIn("sg_ipos_tm_number", rules)
        self.assertIn("sg_acra_transaction_number", rules)
        self.assertIn("sg_hdb_reference", rules)
        self.assertIn("sg_sla_lot_number", rules)
        self.assertIn("sg_sla_title_plan_number", rules)
        self.assertIn("sg_ura_planning_reference", rules)


if __name__ == "__main__":
    unittest.main()
