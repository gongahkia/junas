"""Items 95 + 96: contingent + tipping MNPI lexicons with co-occurrence amplifier.

The two rules ship at severity `low` standalone. The post-pass amplifier in
`engine.review()` lifts severity to `medium` when the match lies within ±200 chars of a
deal substrate (transaction_codename, definitive_agreement, material_adverse_change,
material_event, embargo_marker, nonpublic_marker).
"""

import unittest

from kaypoh.review.citations import mnpi_rationale
from kaypoh.review.engine import PreSendReviewEngine


class _ReviewHelper(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings(self, text: str, document_type: str = "generic"):
        return self.engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type=document_type,
            review_profile="strict",
        ).findings

    def _by_rule(self, findings, rule: str):
        return [f for f in findings if f.rule == rule]


class ContingentMnpiRecallTests(_ReviewHelper):
    """Each canonical contingent phrase must fire exactly one finding."""

    def test_subject_to_board_approval(self):
        f = self._by_rule(self._findings("The transaction is subject to board approval."),
                          "contingent_mnpi_language")
        self.assertTrue(f, "subject to board approval should fire")

    def test_subject_to_regulatory_clearance(self):
        f = self._by_rule(self._findings("Closing subject to regulatory clearance."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_subject_to_regulatory_approvals_plural(self):
        f = self._by_rule(self._findings("Completion remains subject to regulatory approvals."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_subject_to_investment_committee_approval(self):
        f = self._by_rule(self._findings("The disposal is subject to investment committee approval."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_pending_board_approval(self):
        f = self._by_rule(self._findings("Signing remains pending board approval."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_if_approved(self):
        f = self._by_rule(self._findings("If approved, the deal closes Q3."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_should_the_board_agree(self):
        f = self._by_rule(self._findings("Should the board agree, we proceed."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_under_consideration(self):
        f = self._by_rule(self._findings("The acquisition is under consideration."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_in_discussions(self):
        f = self._by_rule(self._findings("Management has been in discussions with counterparty."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_in_advanced_negotiations(self):
        f = self._by_rule(self._findings("We are in advanced negotiations on the SPA."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_non_binding_discussions(self):
        f = self._by_rule(self._findings("The issuer is in non-binding discussions with the target."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_management_believes(self):
        f = self._by_rule(self._findings("Management believes Q3 results will surprise."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_exploratory_talks(self):
        f = self._by_rule(self._findings("Currently in exploratory talks with the target."),
                          "contingent_mnpi_language")
        self.assertTrue(f)

    def test_likely_to_close_gated_verb(self):
        f = self._by_rule(self._findings("The deal is likely to close by year-end."),
                          "contingent_mnpi_language")
        self.assertTrue(f)


class ContingentMnpiPrecisionTests(_ReviewHelper):
    """Patterns that look contingent but should not fire."""

    def test_bare_likely_to_does_not_fire(self):
        # bare "likely to" without a deal-stage verb is too generic.
        f = self._by_rule(self._findings("Sales are likely to remain flat."),
                          "contingent_mnpi_language")
        self.assertFalse(f, f"bare 'likely to remain' should not fire, got: {f!r}")

    def test_bare_expected_to_does_not_fire(self):
        f = self._by_rule(self._findings("Costs are expected to remain stable."),
                          "contingent_mnpi_language")
        self.assertFalse(f)

    def test_negated_in_discussions_does_not_fire(self):
        # "no longer in discussions" — negation guard should suppress.
        f = self._by_rule(self._findings("We are no longer in discussions with them."),
                          "contingent_mnpi_language")
        self.assertFalse(f, f"negated context should suppress, got: {f!r}")

    def test_negated_under_consideration_does_not_fire(self):
        f = self._by_rule(self._findings("This is not under consideration at this time."),
                          "contingent_mnpi_language")
        self.assertFalse(f)

    def test_employment_contingent_background_check_does_not_fire(self):
        f = self._by_rule(
            self._findings("This employment offer is contingent on background checks."),
            "contingent_mnpi_language",
        )
        self.assertFalse(f)

    def test_hr_under_consideration_fires_only_low_when_generic(self):
        f = self._by_rule(
            self._findings("The HR policy remains under consideration by management."),
            "contingent_mnpi_language",
        )
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low")


class TippingLanguageRecallTests(_ReviewHelper):
    def test_please_share_with(self):
        f = self._by_rule(self._findings("Please share with the analyst team before close."),
                          "tipping_language")
        self.assertTrue(f)

    def test_feel_free_to_circulate(self):
        f = self._by_rule(self._findings("Feel free to circulate to your contacts."),
                          "tipping_language")
        self.assertTrue(f)

    def test_passing_this_along(self):
        f = self._by_rule(self._findings("Passing this along for your review."),
                          "tipping_language")
        self.assertTrue(f)

    def test_select_investors(self):
        f = self._by_rule(self._findings("Materials prepared for select investors only."),
                          "tipping_language")
        self.assertTrue(f)

    def test_institutional_holders_only(self):
        f = self._by_rule(self._findings("Distribution restricted to institutional holders only."),
                          "tipping_language")
        self.assertTrue(f)

    def test_largest_holders(self):
        f = self._by_rule(self._findings("Briefing scheduled with our largest holders."),
                          "tipping_language")
        self.assertTrue(f)

    def test_sell_side_mailing(self):
        f = self._by_rule(self._findings("Sell-side mailing list updated."),
                          "tipping_language")
        self.assertTrue(f)


class TippingLanguagePrecisionTests(_ReviewHelper):
    def test_generic_share_does_not_fire(self):
        # "share" alone (no "please share with/to") should not fire.
        f = self._by_rule(self._findings("Market share rose to 22%."),
                          "tipping_language")
        self.assertFalse(f)

    def test_generic_circulate_does_not_fire(self):
        # bare "circulate" outside the tipping idioms.
        f = self._by_rule(self._findings("Air must circulate freely in the warehouse."),
                          "tipping_language")
        self.assertFalse(f)


class CoOccurrenceAmplifierTests(_ReviewHelper):
    """Standalone phrase → severity low; adjacent to deal substrate → severity medium."""

    def test_contingent_alone_stays_low(self):
        f = self._by_rule(
            self._findings("Sales are in discussions about a possible improvement plan."),
            "contingent_mnpi_language",
        )
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low",
                         f"alone, should remain low; got {f[0].severity}")

    def test_contingent_adjacent_to_codename_amplifies(self):
        text = "Project Sapphire is under consideration by the board."
        f = self._by_rule(self._findings(text), "contingent_mnpi_language")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium",
                         f"adjacent to codename should escalate; got {f[0].severity}")

    def test_contingent_adjacent_to_definitive_agreement_amplifies(self):
        text = "We are in advanced negotiations on the SPA with the target."
        f = self._by_rule(self._findings(text), "contingent_mnpi_language")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_tipping_alone_stays_low(self):
        f = self._by_rule(self._findings("Please share with the office before lunch."),
                          "tipping_language")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low")

    def test_tipping_adjacent_to_embargo_amplifies(self):
        text = "Closing date 15 October. Please share with the analyst team before then."
        f = self._by_rule(self._findings(text), "tipping_language")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_tipping_far_from_substrate_stays_low(self):
        # >200 chars distance: should NOT escalate. Padding with neutral filler.
        padding = ". ".join(["Quarterly review continued"] * 30) + ". "
        text = "Project Sapphire announced. " + padding + "Please share with the team."
        f = self._by_rule(self._findings(text), "tipping_language")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low",
                         "phrase >200 chars from substrate should not amplify")

    def test_reason_carries_escalation_note(self):
        text = "Project Sapphire is under consideration."
        f = self._by_rule(self._findings(text), "contingent_mnpi_language")
        self.assertTrue(f)
        self.assertIn("escalated", f[0].reason.lower())


class CitationTests(unittest.TestCase):
    def test_contingent_rationale_carries_basic_v_levinson(self):
        text = mnpi_rationale(
            rule="contingent_mnpi_language",
            jurisdiction="US",
            severity="medium",
            matched_text="under consideration",
        )
        self.assertIn("Basic v. Levinson", text)

    def test_tipping_rationale_carries_juris_statutes(self):
        text = mnpi_rationale(
            rule="tipping_language",
            jurisdiction="SG",
            severity="medium",
            matched_text="please share with the team",
        )
        self.assertIn("s219", text)
        self.assertIn("Securities and Futures Act", text)


if __name__ == "__main__":
    unittest.main()
