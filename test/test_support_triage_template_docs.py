import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class SupportTriageTemplateDocsTests(unittest.TestCase):
    def test_support_triage_template_covers_required_issue_classes(self):
        text = squash((ROOT / "docs" / "support-triage-template.md").read_text(encoding="utf-8"))

        for token in (
            "Support Triage Template",
            "## Detector Miss",
            "## False Positive",
            "## Adapter Failure",
            "## Auth Failure",
            "## Policy Dispute",
            "## Audit Export Issue",
            "request_id",
            "review_id",
            "policy id",
            "policy version",
        ):
            self.assertIn(token, text)

    def test_support_triage_template_blocks_sensitive_ticket_data(self):
        text = squash((ROOT / "docs" / "support-triage-template.md").read_text(encoding="utf-8"))

        for token in (
            "Do not collect raw prompts",
            "email bodies",
            "auth headers",
            "local daemon tokens",
            "Do not attach raw customer samples",
            "Do not paste API keys",
            "Do not attach unredacted audit packs",
        ):
            self.assertIn(token, text)

    def test_docs_index_links_support_triage_template(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("support-triage-template.md", docs_index)


if __name__ == "__main__":
    unittest.main()
