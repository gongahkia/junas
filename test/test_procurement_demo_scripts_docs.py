import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class ProcurementDemoScriptsDocsTests(unittest.TestCase):
    def test_procurement_demo_scripts_cover_required_flows(self):
        text = squash((ROOT / "docs" / "product" / "procurement-demo-scripts.md").read_text(encoding="utf-8"))

        for token in (
            "Procurement Demo Scripts",
            "## Backend API Only",
            "surface=\"api\"",
            "workflow=\"gateway_review\"",
            "## Outlook Pre-Send",
            "scripts/render_outlook_manifest.py",
            "scripts/validate_outlook_manifest.py",
            "## Browser GenAI Prompt",
            "integrations/browser_extension/",
            "## DMS Upload",
            "scripts/scan_dms_manifest.py",
            "surface=\"dms\"",
            "workflow=\"document_upload\"",
            "## Audit Export",
            "scripts/export_audit_pack.py",
            "scripts/verify_audit_pack.py",
            "scripts/verify_journal.py",
        ):
            self.assertIn(token, text)

    def test_procurement_demo_scripts_enforce_synthetic_data_and_no_overclaiming(self):
        text = squash((ROOT / "docs" / "product" / "procurement-demo-scripts.md").read_text(encoding="utf-8"))

        for token in (
            "Use synthetic content only",
            "Do not paste buyer confidential text into a demo",
            "Do not claim Outlook, browser, Word, DMS, Slack, or Google Workspace coverage",
            "Do not claim mobile Outlook send-time enforcement",
            "Do not claim universal browser DLP",
            "Do not claim iManage, NetDocuments, Google Drive, SharePoint",
            "Do not attach raw customer content to procurement follow-ups",
        ):
            self.assertIn(token, text)

    def test_docs_index_and_procurement_faq_link_demo_scripts(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        procurement = (ROOT / "docs" / "faq" / "procurement.md").read_text(encoding="utf-8")

        self.assertIn("product/procurement-demo-scripts.md", docs_index)
        self.assertIn("docs/product/procurement-demo-scripts.md", procurement)


if __name__ == "__main__":
    unittest.main()
