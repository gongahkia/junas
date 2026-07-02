import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ManualRedactorClaimDocsTests(unittest.TestCase):
    def test_manual_redactor_adoption_claim_and_task_study_scope_are_removed(self):
        limitations = (ROOT / "docs" / "known-limitations.md").read_text(encoding="utf-8")
        buyer_objections = (ROOT / "docs" / "faq" / "buyer-objections.md").read_text(
            encoding="utf-8"
        )
        combined = f"{limitations}\n{buyer_objections}"

        self.assertIn("deployed workflow telemetry", buyer_objections)
        self.assertNotIn("manual task study", combined)
        self.assertNotIn("task-study evidence", combined)
        self.assertNotIn("standalone manual redaction", combined)

        for forbidden in (
            "Standalone manual redaction has lower expected adoption",
            "manual redactor is not enough",
            "users will adopt standalone manual redaction",
            "standalone copy-paste redaction",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
