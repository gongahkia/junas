"""Item 97: Reg FD selective-disclosure red-flags (17 CFR 243.100).

New rule `selective_disclosure_risk` fires only when packs include US (Reg FD is
US-specific). Vocabulary derived from Reg FD §100(b)(1) recipient categories — verified
against 17 CFR 243.100 (Cornell LII, 2026-05-26):
    (i)   brokers/dealers
    (ii)  investment advisers / 13F-filer institutional investment managers
    (iii) investment companies / affiliated persons
    (iv)  holders of the issuer's securities reasonably foreseeable to trade

Co-occurrence amplifier (shared with items 95/96): severity low standalone, medium when
within ±200 chars of an MNPI substrate (transaction_codename, definitive_agreement,
material_adverse_change, material_event, embargo_marker, nonpublic_marker).
"""

import unittest

from kaypoh.review.citations import mnpi_rationale
from kaypoh.review.engine import PreSendReviewEngine


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings(self, text: str, destination: str = "US", source: str = "SG", **kw):
        return self.engine.review(
            text=text,
            source_jurisdiction=source,
            destination_jurisdiction=destination,
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
            **kw,
        ).findings

    def _by_rule(self, text: str, rule: str, **kw):
        return [f for f in self._findings(text, **kw) if f.rule == rule]


class JurisdictionGateTests(_Base):
    """Reg FD is US-only. The rule must fire when US is in packs, must NOT fire otherwise."""

    def test_fires_when_destination_us(self):
        f = self._by_rule(
            "Schedule the analyst day next Tuesday for Project Sapphire.",
            "selective_disclosure_risk",
            destination="US", source="SG",
        )
        self.assertTrue(f)

    def test_fires_when_source_us(self):
        # source=US, destination=SG → US pack still loaded under strictest-wins.
        f = self._by_rule(
            "Schedule the analyst day next Tuesday for Project Sapphire.",
            "selective_disclosure_risk",
            destination="SG", source="US",
        )
        self.assertTrue(f)

    def test_does_not_fire_for_purely_sg_routing(self):
        f = self._by_rule(
            "Schedule the analyst day next Tuesday for Project Sapphire.",
            "selective_disclosure_risk",
            destination="SG", source="SG",
        )
        self.assertEqual(f, [], "Reg FD must not fire outside US scope")

    def test_does_not_fire_for_purely_uk_routing(self):
        f = self._by_rule(
            "Schedule the analyst day next Tuesday for Project Sapphire.",
            "selective_disclosure_risk",
            destination="UK", source="UK",
        )
        self.assertEqual(f, [])


class RecallTests(_Base):
    """Each Reg FD recipient-category vocabulary must fire."""

    def test_analyst_day(self):
        self.assertTrue(self._by_rule("Plan the analyst day for next Friday.", "selective_disclosure_risk"))

    def test_sell_side_mailing(self):
        self.assertTrue(self._by_rule("Sell-side mailing list updated this week.", "selective_disclosure_risk"))

    def test_buy_side_outreach(self):
        self.assertTrue(self._by_rule("Begin buy-side outreach Monday morning.", "selective_disclosure_risk"))

    def test_one_on_one_with(self):
        self.assertTrue(self._by_rule("One-on-one call with Morgan analysts.", "selective_disclosure_risk"))

    def test_institutional_holders_only(self):
        self.assertTrue(self._by_rule(
            "Distribution restricted to institutional holders only.",
            "selective_disclosure_risk",
        ))

    def test_13f_filer(self):
        # Reg FD §100(b)(1)(ii) — Form 13F institutional investment manager.
        self.assertTrue(self._by_rule("Briefing for 13F filer audience this Q.", "selective_disclosure_risk"))

    def test_top_ten_holders(self):
        self.assertTrue(self._by_rule("Met our top-ten holders last week.", "selective_disclosure_risk"))

    def test_broker_dealer_outreach(self):
        self.assertTrue(self._by_rule("Broker-dealer outreach is scheduled.", "selective_disclosure_risk"))


class PrecisionTests(_Base):
    """Patterns that look like Reg FD vocabulary but should not fire."""

    def test_analyst_alone_does_not_fire(self):
        self.assertEqual(
            self._by_rule("The analyst is preparing the report.", "selective_disclosure_risk"),
            [],
        )

    def test_one_on_one_without_with_does_not_fire(self):
        # "one-on-one" without "with [recipient]" is generic.
        self.assertEqual(
            self._by_rule("One-on-one feedback was helpful.", "selective_disclosure_risk"),
            [],
        )


class AmplifierTests(_Base):
    """selective_disclosure_risk participates in the items 95/96 co-occurrence amplifier."""

    def test_alone_stays_low(self):
        # Reg FD vocabulary alone — no MNPI substrate within ±200 chars.
        f = self._by_rule("Plan the analyst day next Friday.", "selective_disclosure_risk")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "low",
                         f"alone, selective_disclosure_risk should be low; got {f[0].severity}")

    def test_adjacent_to_codename_amplifies(self):
        text = "Project Sapphire scheduled — analyst day next Friday."
        f = self._by_rule(text, "selective_disclosure_risk")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium",
                         f"adjacent to codename should escalate; got {f[0].severity}")

    def test_adjacent_to_definitive_agreement_amplifies(self):
        text = "Counsel circulated the Share Purchase Agreement — analyst day TBD."
        f = self._by_rule(text, "selective_disclosure_risk")
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "medium")


class CitationTests(unittest.TestCase):
    def test_citation_carries_17_cfr_243_100(self):
        text = mnpi_rationale(
            rule="selective_disclosure_risk", jurisdiction="US",
            severity="medium", matched_text="analyst day",
        )
        self.assertIn("17 CFR 243.100", text)
        self.assertIn("Reg FD", text)

    def test_citation_lists_recipient_categories(self):
        text = mnpi_rationale(
            rule="selective_disclosure_risk", jurisdiction="US",
            severity="medium", matched_text="analyst day",
        )
        # Reg FD §100(b)(1) recipient categories should appear in rationale.
        for category in ["broker", "investment adviser", "13f", "holder"]:
            self.assertIn(category, text.lower(),
                          f"citation should mention {category!r} recipient category: {text!r}")


if __name__ == "__main__":
    unittest.main()
