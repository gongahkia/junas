"""Item 115: insider-list + information-barrier MNPI markers with co-occurrence amplifier.

Both rules ship at severity `low` standalone. The post-pass amplifier in
`engine.review()` lifts severity to `medium` when the match lies within ±200 chars of a
deal substrate (transaction_codename, definitive_agreement, material_adverse_change,
material_event, embargo_marker, nonpublic_marker). Negation guard reused — "no insider
list maintained" / "without any Chinese wall" do not fire.
"""

import unittest

from junas.review.citations import mnpi_rationale
from junas.review.engine import PreSendReviewEngine


class _ReviewHelper(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings(self, text: str, document_type: str = "generic",
                  source_jurisdiction: str = "SG", destination_jurisdiction: str = "SG"):
        return self.engine.review(
            text=text,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction,
            entity_id=None,
            include_suggestions=False,
            document_type=document_type,
            review_profile="strict",
        ).findings

    def _by_rule(self, findings, rule: str):
        return [f for f in findings if f.rule == rule]


class InsiderListRecallTests(_ReviewHelper):
    def test_insider_list(self):
        f = self._by_rule(self._findings("Add the new joiners to the insider list."),
                          "insider_list_marker")
        self.assertTrue(f, "bare 'insider list' should fire")

    def test_restricted_list(self):
        f = self._by_rule(self._findings("The issuer was added to the restricted list yesterday."),
                          "insider_list_marker")
        self.assertTrue(f)

    def test_watch_list(self):
        f = self._by_rule(self._findings("The counterparty has been moved to our watch list."),
                          "insider_list_marker")
        self.assertTrue(f)

    def test_wall_crossed_hyphen(self):
        f = self._by_rule(self._findings("Three analysts were wall-crossed last week."),
                          "insider_list_marker")
        self.assertTrue(f)

    def test_wall_crossing_space(self):
        f = self._by_rule(self._findings("A formal wall crossing was completed Tuesday."),
                          "insider_list_marker")
        self.assertTrue(f)

    def test_crossed_over_the_wall(self):
        f = self._by_rule(self._findings("Two PMs were crossed over the wall this morning."),
                          "insider_list_marker")
        self.assertTrue(f)

    def test_brought_over_the_wall(self):
        f = self._by_rule(self._findings("Compliance brought the team over the wall on Friday."),
                          "insider_list_marker")
        self.assertTrue(f)


class InformationBarrierRecallTests(_ReviewHelper):
    def test_chinese_wall(self):
        f = self._by_rule(self._findings("A Chinese wall separates the M&A and research desks."),
                          "information_barrier_marker")
        self.assertTrue(f)

    def test_information_barrier(self):
        f = self._by_rule(self._findings("The information barrier between corporate and sales must be respected."),
                          "information_barrier_marker")
        self.assertTrue(f)

    def test_ethical_wall(self):
        f = self._by_rule(self._findings("An ethical wall is in place for this engagement."),
                          "information_barrier_marker")
        self.assertTrue(f)

    def test_ethical_screen(self):
        f = self._by_rule(self._findings("Ethical screens have been implemented across the matter team."),
                          "information_barrier_marker")
        self.assertTrue(f)


class InsiderListPrecisionTests(_ReviewHelper):
    def test_negated_insider_list_does_not_fire(self):
        f = self._by_rule(self._findings("No insider list was maintained for that quarter."),
                          "insider_list_marker")
        self.assertFalse(f, f"negated context should suppress, got: {f!r}")

    def test_negated_restricted_list_does_not_fire(self):
        f = self._by_rule(self._findings("There is not a restricted list applicable here."),
                          "insider_list_marker")
        self.assertFalse(f)

    def test_negated_wall_cross_does_not_fire(self):
        f = self._by_rule(self._findings("No wall-crossing has occurred this quarter."),
                          "insider_list_marker")
        self.assertFalse(f)


class InformationBarrierPrecisionTests(_ReviewHelper):
    def test_negated_chinese_wall_does_not_fire(self):
        f = self._by_rule(self._findings("Without any Chinese wall, the trade would be improper."),
                          "information_barrier_marker")
        self.assertFalse(f)

    def test_negated_information_barrier_does_not_fire(self):
        f = self._by_rule(self._findings("No information barrier was in place at the time."),
                          "information_barrier_marker")
        self.assertFalse(f)


class CoOccurrenceAmplifierTests(_ReviewHelper):
    """Standalone phrase → severity low; adjacent to deal substrate → severity medium."""

    def test_insider_list_alone_stays_low(self):
        f = self._by_rule(self._findings("Maintain the insider list per policy."),
                          "insider_list_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low",
                         f"alone, should remain low; got {f[0].severity}")

    def test_insider_list_adjacent_to_codename_amplifies(self):
        text = "Project Sapphire requires updating the insider list with the new joiners."
        f = self._by_rule(self._findings(text), "insider_list_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium",
                         f"adjacent to codename should escalate; got {f[0].severity}")

    def test_wall_cross_adjacent_to_definitive_agreement_amplifies(self):
        text = "Two analysts were wall-crossed before the SPA was finalised."
        f = self._by_rule(self._findings(text), "insider_list_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_chinese_wall_alone_stays_low(self):
        f = self._by_rule(self._findings("A Chinese wall is standard operating procedure."),
                          "information_barrier_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low")

    def test_chinese_wall_adjacent_to_embargo_amplifies(self):
        text = "Closing Date: 30 June. The Chinese wall must remain intact until then."
        f = self._by_rule(self._findings(text), "information_barrier_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_information_barrier_adjacent_to_mac_amplifies(self):
        text = "An information barrier was raised given the material adverse change clause."
        f = self._by_rule(self._findings(text), "information_barrier_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")

    def test_insider_list_far_from_substrate_stays_low(self):
        padding = ". ".join(["Quarterly review continued"] * 30) + ". "
        text = "Project Sapphire announced. " + padding + "Maintain the insider list."
        f = self._by_rule(self._findings(text), "insider_list_marker")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low",
                         "phrase >200 chars from substrate should not amplify")

    def test_reason_carries_escalation_note(self):
        text = "Project Sapphire requires an updated insider list."
        f = self._by_rule(self._findings(text), "insider_list_marker")
        self.assertTrue(f)
        self.assertIn("escalated", f[0].reason.lower())


class CitationTests(unittest.TestCase):
    def test_insider_list_rationale_carries_mar_art18(self):
        text = mnpi_rationale(
            rule="insider_list_marker",
            jurisdiction="EU",
            severity="medium",
            matched_text="insider list",
        )
        self.assertIn("MAR Art 18", text)

    def test_insider_list_rationale_carries_sg_suffix(self):
        text = mnpi_rationale(
            rule="insider_list_marker",
            jurisdiction="SG",
            severity="medium",
            matched_text="insider list",
        )
        self.assertIn("Securities and Futures Act", text)

    def test_information_barrier_rationale_carries_sysc10(self):
        text = mnpi_rationale(
            rule="information_barrier_marker",
            jurisdiction="UK",
            severity="medium",
            matched_text="Chinese wall",
        )
        self.assertIn("SYSC 10", text)

    def test_information_barrier_rationale_carries_us_suffix(self):
        text = mnpi_rationale(
            rule="information_barrier_marker",
            jurisdiction="US",
            severity="medium",
            matched_text="Chinese wall",
        )
        self.assertIn("Regulation FD", text)


if __name__ == "__main__":
    unittest.main()
