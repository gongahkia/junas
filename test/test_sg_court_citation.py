"""SG court neutral-citation detector (item 48 first slice).

Recall + adversarial precision lock for a wedge-relevant detector. The recognizer
ships in `src/kaypoh/review/jurisdictions_data/SG.toml` as `sg_court_citation`.

Positive corpus covers the SAL-published neutral citation forms across Court of Appeal,
High Court (General + Appellate + Family), DC, FC, MC. Negative corpus covers shapes that
look similar but must not fire — bracketed year alone, foreign citations, unrelated
bracket-year tokens. Held to recall=1.0 + precision=1.0 — same posture as the existing
adversarial precision baselines.
"""

import unittest

from kaypoh.review.engine import PreSendReviewEngine

POSITIVES = [
    ("[2024] SGCA 12", "Court of Appeal"),
    ("[2023] SGHC 145", "High Court General"),
    ("[2025] SGHC(A) 7", "High Court Appellate Division"),
    ("[2024] SGHCAR 22", "High Court Appellate Registry"),
    ("[2022] SGHCAF 3", "High Court Family Appellate"),
    ("[2024] SGHC/SIC 9", "Singapore International Commercial Court"),
    ("[2024] SGDC 412", "District Court"),
    ("[2023] SGFC 88", "Family Court"),
    ("[2021] SGMC 51", "Magistrates Court"),
    ("[2024] SGCRA 4", "Criminal Reference Application"),
]

# adversarial negatives — shapes that nearby tokens might trick a loose regex into matching.
NEGATIVES = [
    "[2024] EWCA Civ 12",                          # UK Court of Appeal — wrong country
    "[2024] HKCA 5",                               # Hong Kong — wrong country prefix
    "[2024] SGX 100",                              # SGX index reference — not a court
    "(2024) SGCA 12",                              # round brackets, not square — not SAL form
    "[2024] SG 12",                                # missing court code
    "[2024]CA12",                                  # no spaces — out of spec
    "section [2024] 12 of the Act",                # bracketed year in legislative ref
    "page [12] of [2024] report",                  # arbitrary bracketed numerals
    "[24] SGCA 12",                                # 2-digit year — out of spec
    "Schedule [2024] SGCA",                        # missing trailing decision number
]


class SgCourtCitationDetectorTests(unittest.TestCase):
    """Recall: every positive must produce exactly one sg_court_citation finding whose
    matched_text is the citation token. Precision: no negative may produce any
    sg_court_citation finding."""

    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings_for(self, text: str) -> list:
        result = self.engine.review(
            text=text, source_jurisdiction="SG", destination_jurisdiction="SG",
            entity_id=None, include_suggestions=False, document_type="generic",
            review_profile="strict",
        )
        return [f for f in result.findings if f.rule == "sg_court_citation"]

    def test_recall_one_positive_per_citation(self):
        for citation, label in POSITIVES:
            text = f"The judgment in {citation} ({label}) is on point here."
            with self.subTest(citation=citation):
                hits = self._findings_for(text)
                self.assertEqual(
                    len(hits), 1,
                    f"expected exactly one finding for {citation!r}, got {hits!r}",
                )
                self.assertEqual(hits[0].matched_text, citation)
                self.assertEqual(hits[0].severity, "medium")
                self.assertEqual(hits[0].category, "PII")

    def test_precision_zero_false_positives(self):
        for negative in NEGATIVES:
            text = f"Earlier we discussed {negative} in the brief."
            with self.subTest(negative=negative):
                hits = self._findings_for(text)
                self.assertEqual(
                    hits, [],
                    f"unexpected sg_court_citation finding on negative {negative!r}: {hits!r}",
                )

    def test_multiple_citations_in_same_document(self):
        text = (
            "We rely on [2024] SGCA 12 and [2023] SGHC 145 for the lead authorities, "
            "and distinguish [2022] SGDC 88 on its facts."
        )
        hits = self._findings_for(text)
        self.assertEqual(len(hits), 3)
        self.assertEqual({h.matched_text for h in hits}, {
            "[2024] SGCA 12", "[2023] SGHC 145", "[2022] SGDC 88",
        })


if __name__ == "__main__":
    unittest.main()
