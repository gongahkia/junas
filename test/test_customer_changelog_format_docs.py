import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class CustomerChangelogFormatDocsTests(unittest.TestCase):
    def test_customer_changelog_format_separates_required_sections(self):
        text = squash((ROOT / "docs" / "customer-changelog-format.md").read_text(encoding="utf-8"))

        for token in (
            "Customer-Facing Changelog Format",
            "Detector Accuracy Changes",
            "Policy Behavior Changes",
            "Adapter Behavior Changes",
            "Security Fixes",
            "Action required",
            "Rollback reference",
            "customer impact",
        ):
            self.assertIn(token, text)

    def test_customer_changelog_format_requires_evidence_and_claim_review(self):
        text = squash((ROOT / "docs" / "customer-changelog-format.md").read_text(encoding="utf-8"))

        for token in (
            "eval report, test, fixture, or lock evidence",
            "audit/journal effect",
            "privacy/storage/telemetry impact",
            "tests/scans/SBOM evidence",
            "Do not describe detector changes as accuracy improvements without committed eval evidence",
            "docs/product/claim-review-checklist.md",
            "write `None` rather than omitting the section",
        ):
            self.assertIn(token, text)

    def test_docs_index_links_customer_changelog_format(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("customer-changelog-format.md", docs_index)


if __name__ == "__main__":
    unittest.main()
