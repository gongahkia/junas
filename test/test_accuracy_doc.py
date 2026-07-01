import unittest
from pathlib import Path

from scripts.generate_accuracy_doc import DEFAULT_OUTPUT, render_accuracy_doc

ROOT = Path(__file__).resolve().parent.parent


class AccuracyDocTests(unittest.TestCase):
    def test_accuracy_doc_matches_locks(self):
        self.assertEqual(DEFAULT_OUTPUT.read_text(encoding="utf-8"), render_accuracy_doc())

    def test_accuracy_doc_contains_current_corpora_and_baselines(self):
        rendered = render_accuracy_doc()
        self.assertIn("default legal corpus", rendered)
        self.assertIn("adversarial corpus", rendered)
        self.assertIn("SEA jurisdiction corpus", rendered)
        self.assertIn("HK/AU/JP/KR jurisdiction corpus", rendered)
        self.assertIn("`sg_nric_fin`", rendered)
        self.assertIn("`my_mykad`", rendered)
        self.assertIn("`au_tfn`", rendered)
        self.assertIn("`jp_my_number`", rendered)
        self.assertIn("not locked", rendered)
        for token in (
            "## Comparative Baseline Context",
            "PIIBench",
            "F1=0.1385",
            "not as broad out-of-distribution coverage claims",
            "## Metric Convention",
            "Microsoft Presidio evaluation guidance",
            "beta=2 for pre-send safety",
            "## Promotion Claim Gate",
            "Fixture text and matching `.labels.json` sidecars",
            "`_human_review_status=approved`",
            "`scripts/recall_gate.py --update --require-human-reviewed`",
            "precision report or precision lock",
            "`scripts/generate_accuracy_doc.py --check` passes",
            "Candidate-only reports, demo screenshots, unpromoted sidecars",
            "## MNPI Benchmark Limitation",
            "No public MNPI text-detection benchmark",
            "Strict `conjunctive_mnpi` span placement includes detector reconciliation",
        ):
            self.assertIn(token, rendered)


if __name__ == "__main__":
    unittest.main()
