"""Special-category PII v1 seed (item 98): religion / trade-union / political.

Strict context anchors keep precision survivable. False-positive corpus covers proper-name
colliders ("Christian Dior", "Hindu Kush"), place-name colliders ("Trade Union Square",
"Union Pacific"), and legal/court usage ("the opposition argued", "ruling party of the
contract"). Per-category opt-out via KAYPOH_SPECIAL_CATEGORY_DISABLE.
"""

import os
import unittest

from kaypoh.review.engine import PreSendReviewEngine


class _BaseSpecialCategoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings_for(self, text, rule, source="SG", dest="SG"):
        r = self.engine.review(
            text=text, source_jurisdiction=source, destination_jurisdiction=dest,
            entity_id=None, include_suggestions=False,
        )
        return [f for f in r.findings if f.rule == rule]


class ReligiousBeliefTests(_BaseSpecialCategoryTests):
    def test_devout_muslim_with_honorific(self):
        f = self._findings_for("Dr Jane Tan is a devout Muslim.", "religious_belief")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_attends_mosque(self):
        self.assertEqual(len(self._findings_for("He attends the mosque every Friday.", "religious_belief")), 1)

    def test_attends_temple(self):
        self.assertEqual(len(self._findings_for("She worships at the temple.", "religious_belief")), 1)

    def test_member_of_buddhist_community(self):
        self.assertEqual(
            len(self._findings_for("Members of the Buddhist community gathered.", "religious_belief")), 1
        )

    def test_explicit_faith_assignment(self):
        self.assertEqual(len(self._findings_for("Religion: Hindu", "religious_belief")), 1)

    def test_christian_dior_does_not_fire(self):
        self.assertEqual(len(self._findings_for("Christian Dior limited edition bag.", "religious_belief")), 0)

    def test_hindu_kush_geography_does_not_fire(self):
        self.assertEqual(len(self._findings_for("The Hindu Kush mountains border Afghanistan.", "religious_belief")), 0)

    def test_buddhist_art_history_does_not_fire(self):
        self.assertEqual(len(self._findings_for("Buddhist art history paper submitted.", "religious_belief")), 0)

    def test_atheist_with_marker(self):
        self.assertEqual(len(self._findings_for("Mr Tan identifies as atheist.", "religious_belief")), 1)


class TradeUnionMembershipTests(_BaseSpecialCategoryTests):
    def test_joined_ntuc(self):
        f = self._findings_for("Mr Tan joined the NTUC last year.", "trade_union_membership")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_member_of_trade_union(self):
        self.assertEqual(len(self._findings_for("She is a member of the trade union.", "trade_union_membership")), 1)

    def test_shop_steward_role(self):
        self.assertEqual(len(self._findings_for("Acting as shop steward for the unit.", "trade_union_membership")), 1)

    def test_collective_bargaining_agreement(self):
        self.assertEqual(
            len(self._findings_for("Collective bargaining agreement signed.", "trade_union_membership")), 1
        )

    def test_picket_line(self):
        self.assertEqual(len(self._findings_for("Workers crossed the picket line.", "trade_union_membership")), 1)

    def test_trade_union_square_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("Meeting at Trade Union Square at 9am.", "trade_union_membership")), 0
        )

    def test_union_pacific_railway_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("Union Pacific Railway annual report.", "trade_union_membership")), 0
        )

    def test_afl_premiership_does_not_fire(self):
        self.assertEqual(
            len(self._findings_for("AFL Premiership winners announced.", "trade_union_membership")), 0
        )


class PoliticalOpinionTests(_BaseSpecialCategoryTests):
    def test_member_of_pap(self):
        f = self._findings_for("Ms Lee is a member of the PAP.", "political_opinion")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "high")

    def test_donated_to_party(self):
        self.assertEqual(
            len(self._findings_for("She donated to the Democratic Party.", "political_opinion", source="US", dest="US")),
            1,
        )

    def test_voted_for_party(self):
        self.assertEqual(
            len(self._findings_for("He voted for Labour in the last election.", "political_opinion", source="UK", dest="UK")),
            1,
        )

    def test_party_affiliation_explicit(self):
        self.assertEqual(
            len(self._findings_for("Party affiliation: BJP", "political_opinion", source="IN", dest="IN")), 1
        )

    def test_the_opposition_argued_court_usage_does_not_fire(self):
        # "the opposition argued" without party-name suffix should not fire
        self.assertEqual(
            len(self._findings_for("The opposition argued in court yesterday.", "political_opinion", source="UK", dest="UK")),
            0,
        )

    def test_independent_counsel_does_not_fire(self):
        # "Independent counsel" — adjective usage, not party affiliation
        self.assertEqual(
            len(self._findings_for("Independent counsel filed a report.", "political_opinion", source="US", dest="US")),
            0,
        )


class OptOutTests(_BaseSpecialCategoryTests):
    def tearDown(self):
        os.environ.pop("KAYPOH_SPECIAL_CATEGORY_DISABLE", None)

    def test_disable_religion(self):
        os.environ["KAYPOH_SPECIAL_CATEGORY_DISABLE"] = "religion"
        self.assertEqual(len(self._findings_for("Dr Jane Tan is a devout Muslim.", "religious_belief")), 0)

    def test_disable_union(self):
        os.environ["KAYPOH_SPECIAL_CATEGORY_DISABLE"] = "union"
        self.assertEqual(len(self._findings_for("Mr Tan joined the NTUC.", "trade_union_membership")), 0)

    def test_disable_political(self):
        os.environ["KAYPOH_SPECIAL_CATEGORY_DISABLE"] = "political"
        self.assertEqual(len(self._findings_for("Ms Lee is a member of the PAP.", "political_opinion")), 0)

    def test_disable_multiple(self):
        os.environ["KAYPOH_SPECIAL_CATEGORY_DISABLE"] = "religion,union,political"
        text = "Dr Tan is a devout Muslim, joined the NTUC, and is a member of the PAP."
        for rule in ("religious_belief", "trade_union_membership", "political_opinion"):
            self.assertEqual(len(self._findings_for(text, rule)), 0, f"expected {rule} disabled")


class CitationsTests(_BaseSpecialCategoryTests):
    def test_religion_citation_includes_gdpr_art_9(self):
        from kaypoh.review.citations import pii_rationale
        rationale = pii_rationale(rule="religious_belief", jurisdiction="EU", matched_text="Muslim")
        self.assertIn("Art 9", rationale)

    def test_union_citation_includes_pipa_art_23(self):
        from kaypoh.review.citations import pii_rationale
        rationale = pii_rationale(rule="trade_union_membership", jurisdiction="KR", matched_text="NTUC")
        self.assertIn("PIPA Korea Art 23", rationale)

    def test_political_citation_includes_lgpd(self):
        from kaypoh.review.citations import pii_rationale
        rationale = pii_rationale(rule="political_opinion", jurisdiction="EU", matched_text="PAP")
        self.assertIn("LGPD", rationale)


if __name__ == "__main__":
    unittest.main()
