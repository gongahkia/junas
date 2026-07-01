import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ManualRedactorClaimDocsTests(unittest.TestCase):
    def test_manual_redactor_adoption_claim_is_removed_until_validation_exists(self):
        limitations = (ROOT / "docs" / "known-limitations.md").read_text(encoding="utf-8")
        buyer_objections = (ROOT / "docs" / "faq" / "buyer-objections.md").read_text(
            encoding="utf-8"
        )
        combined = f"{limitations}\n{buyer_objections}"

        self.assertIn("No validated task-study evidence", limitations)
        self.assertIn("standalone manual redaction", limitations)
        self.assertIn("docs/product/value-metrics.md", limitations)
        self.assertIn("without task-study evidence", buyer_objections)

        for forbidden in (
            "Standalone manual redaction has lower expected adoption",
            "manual redactor is not enough",
            "users will adopt standalone manual redaction",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
