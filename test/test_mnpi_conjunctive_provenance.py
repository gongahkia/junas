import unittest
from pathlib import Path

from scripts.check_mnpi_conjunctive_provenance import DEFAULT_OUTPUT, build_manifest

ROOT = Path(__file__).resolve().parent.parent


class MnpiConjunctiveProvenanceTests(unittest.TestCase):
    def test_manifest_matches_reviewed_candidate_labels(self):
        expected = build_manifest()
        actual = DEFAULT_OUTPUT.read_text(encoding="utf-8")

        import json

        self.assertEqual(json.loads(actual), expected)
        self.assertEqual(expected["counts"]["label_files"], 1356)
        self.assertEqual(expected["counts"]["label_items"], 1358)
        self.assertEqual(expected["counts"]["detector_label_source_items"], 0)
        self.assertIn("project-owner manual review", expected["non_detector_author_provenance"]["basis"])
        self.assertIn("detector-reconciled", expected["independence_disclosure"])
        self.assertIn("No public MNPI text-detection benchmark", expected["source_review"]["result"])

    def test_known_limitations_discloses_mnpi_benchmark_boundary(self):
        text = (ROOT / "docs" / "known-limitations.md").read_text(encoding="utf-8")

        self.assertIn("No public MNPI text-detection benchmark", text)
        self.assertIn("internal expert-labelled/project-owner-reviewed fixtures", text)
        self.assertIn("Strict `conjunctive_mnpi` span placement includes detector reconciliation", text)
        self.assertIn("market gap Junas targets", text)


if __name__ == "__main__":
    unittest.main()
