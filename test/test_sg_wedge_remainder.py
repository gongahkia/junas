import unittest

from kaypoh.review.citations import mnpi_rationale, pii_rationale
from kaypoh.review.engine import PreSendReviewEngine


class SgWedgeRemainderTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _rules(self, text: str) -> set[str]:
        result = self.engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        return {finding.rule for finding in result.findings}

    def test_insurance_crypto_and_tribunal_refs_fire_with_labels(self):
        text = (
            "Insurance Policy No.: PA-2026-000123 is attached. "
            "DPT wallet address: 0x52908400098527886E0F7030069857D2E4169EE7. "
            "SCT claim no: SCT-12345-2026 remains confidential."
        )
        rules = self._rules(text)

        self.assertIn("sg_insurance_policy_number", rules)
        self.assertIn("crypto_wallet_address", rules)
        self.assertIn("sg_tribunal_reference", rules)

    def test_wedge_remainder_requires_specific_anchors(self):
        rules = self._rules(
            "The policy number 42 was discussed. "
            "Wallet address formatting is in the public developer guide. "
            "The tribunal will hear submissions next week."
        )

        self.assertNotIn("sg_insurance_policy_number", rules)
        self.assertNotIn("crypto_wallet_address", rules)
        self.assertNotIn("sg_tribunal_reference", rules)

    def test_contract_commercial_terms_fire_as_mnpi(self):
        text = (
            "Unit price: SGD 12.50 per seat. "
            "Contract discount rate: 18%. "
            "Annual volume commitment: 250,000 units. "
            "Royalty rate: 7.5%. "
            "Total contract value: SGD 4,500,000."
        )
        rules = self._rules(text)

        self.assertIn("contract_unit_price", rules)
        self.assertIn("contract_discount_rate", rules)
        self.assertIn("volume_commitment", rules)
        self.assertIn("royalty_rate", rules)
        self.assertIn("total_contract_value", rules)

    def test_new_rule_rationales_are_registered(self):
        for rule in [
            "sg_insurance_policy_number",
            "crypto_wallet_address",
            "sg_tribunal_reference",
        ]:
            with self.subTest(rule=rule):
                self.assertGreater(len(pii_rationale(rule=rule, jurisdiction="SG", matched_text="x")), 40)
        for rule in [
            "contract_unit_price",
            "contract_discount_rate",
            "volume_commitment",
            "royalty_rate",
            "total_contract_value",
        ]:
            with self.subTest(rule=rule):
                self.assertGreater(
                    len(mnpi_rationale(rule=rule, jurisdiction="SG", severity="medium", matched_text="x")),
                    40,
                )


if __name__ == "__main__":
    unittest.main()
