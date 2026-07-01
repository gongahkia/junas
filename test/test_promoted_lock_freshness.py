import unittest

from scripts.check_promoted_lock_freshness import evaluate_changed_paths, is_promoted_fixture_input


class PromotedLockFreshnessTests(unittest.TestCase):
    def test_detects_promoted_fixture_inputs(self):
        self.assertTrue(
            is_promoted_fixture_input(
                "test/fixtures/legal-corpus-reviewed-candidates/sg_sample.labels.json"
            )
        )
        self.assertTrue(
            is_promoted_fixture_input("test/fixtures/legal-corpus-reviewed-candidates/sg_sample.txt")
        )
        self.assertFalse(
            is_promoted_fixture_input("test/fixtures/legal-corpus-candidates/sg_sample.labels.json")
        )
        self.assertFalse(
            is_promoted_fixture_input(
                "test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json"
            )
        )

    def test_requires_lock_and_accuracy_doc_when_promoted_label_changes(self):
        result = evaluate_changed_paths([
            "test/fixtures/legal-corpus-reviewed-candidates/sg_sample.labels.json",
        ])

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["missing_updates"],
            [
                "docs/accuracy.md",
                "test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json",
            ],
        )

    def test_passes_when_required_updates_are_in_same_diff(self):
        result = evaluate_changed_paths([
            "test/fixtures/legal-corpus-reviewed-candidates/sg_sample.labels.json",
            "test/fixtures/legal-corpus-reviewed-candidates/legal-corpus-reviewed-candidates.lock.json",
            "docs/accuracy.md",
        ])

        self.assertTrue(result["ok"])
        self.assertEqual(result["missing_updates"], [])

    def test_ignores_non_promoted_corpus_changes(self):
        result = evaluate_changed_paths([
            "test/fixtures/legal-corpus-candidates/sg_sample.labels.json",
            "src/junas/review/engine.py",
        ])

        self.assertTrue(result["ok"])
        self.assertEqual(result["promoted_inputs"], [])


if __name__ == "__main__":
    unittest.main()
