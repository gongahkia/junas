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


if __name__ == "__main__":
    unittest.main()
