import unittest

from kaypoh.review.engine import PreSendReviewEngine
from kaypoh.review.singling_out.scorer import _load_sg_tables


class SinglingOutV2Tests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _quasi(self, text: str):
        result = self.engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
        )
        return [f for f in result.findings if f.rule == "quasi_identifier_combination"]

    def test_sg_frequency_manifest_loads(self):
        tables = _load_sg_tables()
        self.assertGreater(tables.total_population, 4_000_000)
        self.assertIn("population_by_area_age", tables.loaded_tables)
        self.assertIn("postal_sector_population", tables.loaded_tables)
        for prefix in ("12", "46", "54", "61", "65"):
            with self.subTest(prefix=prefix):
                self.assertIn(prefix, tables.postal_population)

    def test_strict_sg_v2_emits_k_metadata_for_unique_contact_cluster(self):
        findings = self._quasi(
            "Dr Jane Tan can be reached at +65 9123 4567 or jane.tan@example.sg."
        )
        self.assertEqual(len(findings), 1)
        metadata = findings[0].metadata
        self.assertEqual(metadata["layer"], "singling_out_v2")
        self.assertEqual(metadata["k_anonymity_equivalence"], 1)
        self.assertEqual(metadata["re_identification_estimate"], 1.0)
        self.assertEqual(metadata["singling_out_scope"], "paragraph")

    def test_identifiers_in_separate_paragraphs_do_not_aggregate(self):
        text = "Dr Jane Tan leads the team.\n\nPhone: +65 9123 4567.\n\nEmail: jane.tan@example.sg."
        self.assertEqual(self._quasi(text), [])


if __name__ == "__main__":
    unittest.main()
