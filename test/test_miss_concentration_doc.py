import json
import unittest
from pathlib import Path

from scripts.miss_concentration import render_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "reports" / "miss_concentration_2026-06-02.json"
DOC = REPO_ROOT / "docs" / "miss_concentration.md"


class MissConcentrationDocTests(unittest.TestCase):
    def test_miss_concentration_doc_matches_report(self):
        payload = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(DOC.read_text(encoding="utf-8"), render_markdown(payload))


if __name__ == "__main__":
    unittest.main()
