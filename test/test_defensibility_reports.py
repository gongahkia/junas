import unittest
from pathlib import Path

from kaypoh.review import jurisdictions


REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = REPO_ROOT / "docs" / "defensibility"


class DefensibilityReportDriftTests(unittest.TestCase):
    def setUp(self):
        jurisdictions.reload_registry()

    def test_every_runtime_pack_has_report(self):
        for code in jurisdictions.RULE_PACKS:
            path = REPORT_DIR / f"{code}.md"
            self.assertTrue(path.exists(), f"missing defensibility report for runtime pack {code}")

    def test_reports_reference_required_defensibility_sections(self):
        for code, pack in jurisdictions.RULE_PACKS.items():
            path = REPORT_DIR / f"{code}.md"
            text = path.read_text(encoding="utf-8")
            self.assertIn("Statutory Coverage", text)
            self.assertIn("Known Gaps", text)
            self.assertIn("Operational Controls", text)
            self.assertIn("not legal advice", text.lower())
            self.assertIn("docs/statutory-coverage.md", text)
            self.assertIn(pack.label, text)
            for reference in pack.references:
                self.assertIn(reference, text)

    def test_sea_baseline_report_is_explicit(self):
        text = (REPORT_DIR / "SEA.md").read_text(encoding="utf-8")
        self.assertIn("regional baseline pack", text)
        self.assertIn("Southeast Asia baseline", text)


if __name__ == "__main__":
    unittest.main()
