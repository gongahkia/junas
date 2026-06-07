import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_ID = "20260606-strict-item120"
REPORT_DIR = REPO_ROOT / "reports" / "layer-attribution"


class LayerAttributionNoCostReportTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((REPORT_DIR / f"{RUN_ID}_manifest.json").read_text(encoding="utf-8"))

    def test_manifest_is_strict_only(self):
        self.assertEqual(list(self.manifest["profiles"].keys()), ["strict"])
        self.assertNotIn("audit_grade", self.manifest["profiles"])
        self.assertIn("Strict is deterministic/free", self.manifest["note"])

    def test_report_files_exist_without_paid_profile_outputs(self):
        strict = self.manifest["profiles"]["strict"]
        for key in ("candidate_report", "bucket_report", "concentration_report"):
            path = Path(strict[key])
            self.assertTrue(path.exists(), f"missing {key}: {path}")
            self.assertIn("strict", path.name)
            self.assertNotIn("audit_grade", path.name)

    def test_report_reflects_post_120_conjunctive_findings(self):
        candidate_path = Path(self.manifest["profiles"]["strict"]["candidate_report"])
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
        count = 0
        for doc in payload["documents"]:
            count += sum(1 for finding in doc.get("unexpected", []) if finding.get("rule") == "conjunctive_mnpi")
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
