import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ProductUsabilityReportDocsTests(unittest.TestCase):
    def test_usability_report_records_local_runtime_evidence_and_limits(self):
        text = (ROOT / "docs" / "product" / "usability-pass-2026-07-04.md").read_text(encoding="utf-8")

        for token in (
            "local backend/API evaluation is usable from a checkout after prerequisites",
            "`./scripts/demo.sh`",
            "demo_completed: true",
            "en_core_web_sm",
            "Focused tests: 61 passed",
            "Backend smoke passed",
            "test/test_product_value_report.py",
            "SG NRIC in a GenAI prompt",
            "M&A MNPI before announcement",
            "Clean internal text",
            "Product-value metrics have a raw-free aggregation script and tests",
        ):
            self.assertIn(token, text)

    def test_usability_report_keeps_public_launch_on_hold(self):
        text = (ROOT / "docs" / "product" / "usability-pass-2026-07-04.md").read_text(encoding="utf-8")

        for token in (
            "public launch and broad adoption remain on hold",
            "Hosted demo work remains open in GitHub issues #84 and #85",
            "No external tester has run the current install/demo path",
            "Homebrew, Nix, signed DMG",
            "No pilot has measured avoided risky sends",
            "Hold public launch/adoption claims",
            "Forbidden wording",
            "launch-ready",
            "production-ready",
            "one-click install",
        ):
            self.assertIn(token, text)

    def test_docs_index_and_roadmap_reference_current_usability_state(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("product/usability-pass-2026-07-04.md", docs_index)
        self.assertNotIn("#76", roadmap)
        self.assertIn("#84", roadmap)
        self.assertIn("#85", roadmap)


if __name__ == "__main__":
    unittest.main()
