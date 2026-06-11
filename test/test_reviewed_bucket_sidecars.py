import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = REPO_ROOT / "reports" / "current" / "reviewed_bucket_sidecars_20260606.json"


class ReviewedBucketSidecarTests(unittest.TestCase):
    def setUp(self):
        self.summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    def test_reviewed_sample_is_large_and_caveated(self):
        self.assertGreaterEqual(self.summary["miss_count"], 50)
        self.assertEqual(self.summary["review_status"], "reviewed_representative_internal_benchmark")
        scope = self.summary["review_scope"].lower()
        self.assertIn("internal benchmarking", scope)
        self.assertIn("not procurement-grade legal review", scope)
        self.assertIn("not legal advice", scope)

    def test_sample_covers_requested_jurisdictions_and_buckets(self):
        for jurisdiction in ("IN", "CN", "EU", "SG"):
            self.assertGreater(self.summary["by_jurisdiction"].get(jurisdiction, 0), 0)
        for bucket in (
            "coverage_gap",
            "conjunction_miss",
            "singling_out_miss",
            "needs_review",
            "true_inference_miss",
        ):
            self.assertGreater(self.summary["by_bucket"].get(bucket, 0), 0)

    def test_sidecar_schema_and_entry_status(self):
        for path_text in self.summary["sidecar_paths"]:
            path = REPO_ROOT / path_text
            self.assertTrue(path.exists(), f"missing sidecar {path_text}")
            body = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(body["review_status"], "reviewed_representative_internal_benchmark")
            self.assertIn("not legal advice", body["review_scope"].lower())
            self.assertTrue(body["miss_buckets"])
            for entry in body["miss_buckets"]:
                self.assertEqual(entry["review_status"], "reviewed_representative_internal_benchmark")
                self.assertIn("not procurement-grade legal review", entry["review_note"])


if __name__ == "__main__":
    unittest.main()
