"""Blackout-window calendrical detector (item 84).

Verifies the per-jurisdiction blackout-window registry (SGX MB 1207(19)(c) 14d/30d, HKEX
MB App C3 30d/60d, UK MAR Art 19(11) + UKLR 30d/30d, EU MAR Art 19(11) 30d/30d).
US Reg FD has no codified duration and is intentionally not registered.

Detection requires both a document-date anchor and an earnings-date anchor; period type
(annual / interim) is parsed from the earnings phrase and selects the right window.
"""

import unittest

from kaypoh.review.engine import PreSendReviewEngine


class BlackoutDetectorTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _blackouts(self, result):
        return [f for f in result.findings if f.rule == "blackout_period_reference"]

    def test_sg_q3_within_14_day_window(self):
        # SGX MB 1207(19)(c): 2 weeks before Q1-Q3 results
        text = "Date: 1 Aug 2026\n\nQ3 results to be announced on 10 Aug 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False,
        )
        b = self._blackouts(r)
        self.assertEqual(len(b), 1)
        self.assertIn("SG 14-day blackout window", b[0].reason)
        self.assertIn("delta=9 days", b[0].reason)

    def test_sg_q3_outside_14_day_window(self):
        text = "Date: 1 Aug 2026\n\nQ3 results to be announced on 31 Aug 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False,
        )
        self.assertEqual(self._blackouts(r), [])

    def test_sg_annual_30_day_window(self):
        # half-year / full-year: SG window is 30 days
        text = "Date: 1 Aug 2026\n\nFull-year results to be released on 25 August 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False,
        )
        b = self._blackouts(r)
        self.assertEqual(len(b), 1)
        self.assertIn("SG 30-day blackout window", b[0].reason)

    def test_hk_annual_60_day_window(self):
        # HKEX MB App C3: 60 days before annual results
        text = "Date: 1 Aug 2026\n\nAnnual results to be released on 15 September 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="HK", destination_jurisdiction="HK",
            entity_id=None, include_suggestions=False,
        )
        b = self._blackouts(r)
        self.assertEqual(len(b), 1)
        self.assertIn("HK 60-day blackout window", b[0].reason)

    def test_hk_interim_30_day_window(self):
        text = "Date: 1 Aug 2026\n\nInterim results to be announced on 20 August 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="HK", destination_jurisdiction="HK",
            entity_id=None, include_suggestions=False,
        )
        b = self._blackouts(r)
        self.assertEqual(len(b), 1)
        self.assertIn("HK 30-day blackout window", b[0].reason)

    def test_uk_mar_30_day_closed_period(self):
        text = "Date: 1 Aug 2026\n\nHalf-year results due on 25 August 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="UK", destination_jurisdiction="UK",
            entity_id=None, include_suggestions=False,
        )
        b = self._blackouts(r)
        self.assertEqual(len(b), 1)
        self.assertIn("UK 30-day blackout window", b[0].reason)

    def test_us_has_no_codified_window_no_fire(self):
        # US Reg FD has no codified duration; intentionally not registered
        text = "Date: 1 Aug 2026\n\nQ3 earnings to be announced on 10 Aug 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="US", destination_jurisdiction="US",
            entity_id=None, include_suggestions=False,
        )
        self.assertEqual(self._blackouts(r), [])

    def test_au_has_no_codified_window_no_fire(self):
        text = "Date: 1 Aug 2026\n\nQ3 results to be announced on 10 Aug 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="AU", destination_jurisdiction="AU",
            entity_id=None, include_suggestions=False,
        )
        self.assertEqual(self._blackouts(r), [])

    def test_no_doc_date_no_fire(self):
        text = "Q3 results to be announced on 10 Aug 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False,
        )
        self.assertEqual(self._blackouts(r), [])

    def test_no_earnings_date_no_fire(self):
        text = "Date: 1 Aug 2026\n\nDraft memo for internal review."
        r = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False,
        )
        self.assertEqual(self._blackouts(r), [])

    def test_dedup_specific_anchor_wins_over_generic(self):
        # both "Q3 results" (interim anchor) and generic "results" anchor match the same
        # earnings date — dedup should fire once
        text = "Date: 1 Aug 2026\n\nQ3 results to be announced on 10 Aug 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False,
        )
        self.assertEqual(len(self._blackouts(r)), 1)

    def test_iso_date_format(self):
        text = "Date: 2026-08-01\n\nAnnual results due on 2026-08-25."
        r = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False,
        )
        b = self._blackouts(r)
        self.assertEqual(len(b), 1)

    def test_us_routing_through_sg_uses_sg_window(self):
        # Cross-jurisdiction routing: source SG → dest US picks SG packs as well
        text = "Date: 1 Aug 2026\n\nQ3 results to be announced on 10 Aug 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="US",
            entity_id=None, include_suggestions=False,
        )
        self.assertEqual(len(self._blackouts(r)), 1)

    def test_earnings_date_before_doc_date_no_fire(self):
        # results already happened — no blackout exposure left
        text = "Date: 15 Aug 2026\n\nQ3 results were announced on 10 Aug 2026."
        r = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False,
        )
        self.assertEqual(self._blackouts(r), [])


if __name__ == "__main__":
    unittest.main()
