"""Quasi-identifier combination detection.

New rule `quasi_identifier_combination` fires when ≥3 distinct quasi-identifier rules
co-occur within a 500-char sliding window. Citation: PDPA s2 + GDPR Recital 26 +
CCPA §1798.140(v). Item 70 v2 activates SG strict with a population-prior k estimate.

The seed rule is deliberately conservative — it fires on count + proximity, not on a
full k-anonymity probability estimate. It remains as the audit_grade fallback.
"""

import unittest

from junas.review.citations import pii_rationale
from junas.review.engine import PreSendReviewEngine


class _Base(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _findings(self, text: str, review_profile: str = "audit_grade"):
        return self.engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile=review_profile,
        ).findings

    def _quasi_id_findings(self, text: str, **kw):
        return [f for f in self._findings(text, **kw) if f.rule == "quasi_identifier_combination"]


class ProfileGateTests(_Base):
    """SG strict activates item 70 v2; audit_grade keeps item 101 fallback."""

    def test_strict_mode_emits_sg_v2_combination(self):
        text = (
            "Dr Jane Tan (NRIC S1234567A, mobile +65 9123 4567, email jane.tan@example.sg) "
            "lives at 1 Address Lane Singapore 123456."
        )
        f = self._quasi_id_findings(text, review_profile="strict")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].metadata.get("layer"), "singling_out_v2")
        self.assertEqual(f[0].metadata.get("k_anonymity_equivalence"), 1)

    def test_audit_grade_emits_combination(self):
        text = (
            "Dr Jane Tan (NRIC S1234567A, mobile +65 9123 4567, email jane.tan@example.sg) "
            "lives at 1 Address Lane Singapore 123456."
        )
        f = self._quasi_id_findings(text, review_profile="audit_grade")
        self.assertEqual(len(f), 1, f"audit_grade should emit one combination finding; got {f!r}")
        self.assertEqual(f[0].severity, "medium")
        self.assertEqual(f[0].category, "PII")
        self.assertEqual(f[0].metadata.get("layer"), "quasi_identifier_seed")


class CountThresholdTests(_Base):
    """The minimum is 3 distinct quasi-identifier rules."""

    def test_two_quasi_ids_does_not_fire(self):
        # named_person + phone — only 2 distinct quasi-id rules.
        text = "Dr Jane Tan can be reached at +65 9123 4567."
        self.assertEqual(self._quasi_id_findings(text), [])

    def test_three_distinct_quasi_ids_fires(self):
        # named_person + phone + email = 3 distinct rules.
        text = "Dr Jane Tan can be reached at +65 9123 4567 or jane@example.sg."
        f = self._quasi_id_findings(text)
        self.assertEqual(len(f), 1)

    def test_three_findings_same_rule_does_not_fire(self):
        # Three phone numbers but only ONE distinct rule (phone_number). Must not fire.
        text = "Hotline: +65 9111 1111, +65 9222 2222, or +65 9333 3333."
        self.assertEqual(self._quasi_id_findings(text), [])


class WindowTests(_Base):
    """500-char sliding window — quasi-IDs spread further apart should not aggregate."""

    def test_three_quasi_ids_within_window_fires(self):
        text = "Dr Jane Tan, S1234567A, +65 9123 4567 in the same line."
        f = self._quasi_id_findings(text)
        self.assertEqual(len(f), 1)

    def test_three_quasi_ids_far_apart_does_not_fire(self):
        # Pad with neutral filler to push the third quasi-ID >500 chars from the first.
        padding = ". ".join(["Quarterly review continued"] * 30) + ". "
        text = "Dr Jane Tan in the preamble. " + padding + "S1234567A and email jane@example.sg later."
        # The NRIC + email are co-located but the named_person is far away — only 2 distinct
        # rules cluster within the window. No combination.
        self.assertEqual(self._quasi_id_findings(text), [])

    def test_each_cluster_emits_at_most_one_combination(self):
        # Two clusters, both with ≥3 distinct quasi-IDs, separated by >500 chars of padding.
        padding = ". ".join(["Quarterly review continued"] * 30) + ". "
        text = (
            "Dr Jane Tan (S1234567A, +65 9111 1111). "
            + padding
            + "Mr Tom Wong (S7654321Z, +65 9222 2222, email tom@example.sg)."
        )
        f = self._quasi_id_findings(text)
        # Each cluster contributes at most one combination finding. Two clusters → 2 findings.
        self.assertEqual(len(f), 2, f"expected exactly 2 cluster findings; got {f!r}")


class SpanTests(_Base):
    """Combination finding spans the union of the quasi-IDs in the cluster."""

    def test_combination_span_covers_cluster(self):
        text = "Dr Jane Tan, S1234567A, +65 9123 4567 in line."
        f = self._quasi_id_findings(text)
        self.assertEqual(len(f), 1)
        self.assertLess(f[0].start_char, f[0].end_char)
        # span should include at least "Jane Tan" through the phone number.
        self.assertLess(f[0].end_char - f[0].start_char, len(text))


class CitationTests(unittest.TestCase):
    def test_citation_cites_pdpa_and_gdpr_recital_26(self):
        text = pii_rationale(rule="quasi_identifier_combination", jurisdiction="SG",
                             matched_text="3 distinct quasi-identifiers")
        self.assertIn("PDPA s2", text)
        self.assertIn("Recital 26", text)

    def test_citation_cites_predicate_singling_out_and_sweeney_or_ccpa(self):
        text = pii_rationale(rule="quasi_identifier_combination", jurisdiction="US",
                             matched_text="3 distinct quasi-identifiers")
        self.assertIn("PNAS 2020", text)
        self.assertIn("predicate singling out", text)
        self.assertIn("10.1073/pnas.1914598117", text)
        self.assertTrue(
            "Sweeney" in text or "CCPA" in text,
            f"expected Sweeney or CCPA reference in rationale: {text!r}",
        )


if __name__ == "__main__":
    unittest.main()
