import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DeploymentDocsTests(unittest.TestCase):
    def test_subject_erasure_runbook_names_backfill_and_retention_limits(self):
        text = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")

        self.assertIn("Subject Erasure Runbook", text)
        self.assertIn("--backfill", text)
        self.assertIn("--dry-run", text)
        self.assertIn("subject_erasure_recorded", text)
        self.assertIn("SIEM exports", text)
        self.assertIn("backups", text)
        self.assertIn("retention", text)


if __name__ == "__main__":
    unittest.main()
