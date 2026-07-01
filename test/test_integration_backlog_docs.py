import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class IntegrationBacklogDocsTests(unittest.TestCase):
    def test_integration_backlog_defines_required_categories_without_fabricated_requests(self):
        text = squash((ROOT / "docs" / "product" / "integration-backlog.md").read_text(encoding="utf-8"))

        for token in (
            "User-Requested Integration Backlog",
            "No validated user-requested integration rows are recorded yet",
            "`direct API`",
            "`Outlook`",
            "`browser`",
            "`DMS`",
            "`Slack`",
            "`Google Workspace`",
            "`unsupported`",
            "Do not treat roadmap research as a user request",
        ):
            self.assertIn(token, text)

    def test_integration_backlog_requires_source_status_and_evidence_fields(self):
        text = squash((ROOT / "docs" / "product" / "integration-backlog.md").read_text(encoding="utf-8"))

        for token in (
            "Request id",
            "Date",
            "Source",
            "User segment",
            "Workflow requested",
            "Category",
            "Status",
            "Evidence",
            "`new`",
            "`researching`",
            "`planned`",
            "`rejected`",
            "`shipped`",
        ):
            self.assertIn(token, text)

    def test_docs_index_and_roadmap_link_integration_backlog(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("product/integration-backlog.md", docs_index)
        self.assertIn("docs/product/integration-backlog.md", roadmap)
        for category in ("direct API", "Outlook", "browser", "DMS", "Slack", "Google Workspace", "unsupported"):
            self.assertIn(category, roadmap)


if __name__ == "__main__":
    unittest.main()
