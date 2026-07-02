import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports/current/layer_attribution_post_detection_delta_20260701.json"


class ResidualLLMTierDocsTests(unittest.TestCase):
    def test_residual_slice_is_documented_from_committed_report(self):
        payload = json.loads(REPORT.read_text(encoding="utf-8"))
        buckets = payload["post_detection"]["bucket_counts"]
        residual_total = buckets["needs_review"] + buckets["true_inference_miss"]
        ideal_misses = sum(buckets.values())
        residual_share = residual_total / ideal_misses * 100

        self.assertEqual(buckets["needs_review"], 336)
        self.assertEqual(buckets["true_inference_miss"], 24)
        self.assertEqual(residual_total, 360)
        self.assertEqual(ideal_misses, 23170)
        self.assertAlmostEqual(residual_share, 1.55, places=2)

        docs = {
            "accuracy": ROOT / "docs/accuracy.md",
            "governance": ROOT / "docs/llm-governance.md",
            "deployment": ROOT / "docs/deployment-managed-llm.md",
            "limitations": ROOT / "docs/known-limitations.md",
        }
        for name, path in docs.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(doc=name):
                self.assertIn("360", text)
                self.assertIn("336", text)
                self.assertIn("24", text)
                self.assertIn("1.55%", text)
                self.assertIn("server-only", text)
                self.assertIn("human-adjudicated", text)

    def test_docs_state_not_a_deterministic_layer_target(self):
        for rel in (
            "docs/accuracy.md",
            "docs/llm-governance.md",
            "docs/known-limitations.md",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            flattened = " ".join(text.split())
            with self.subTest(doc=rel):
                self.assertIn("deterministic", text)
                deterministic_target_phrase = (
                    "Do not describe these residual buckets as work the deterministic layer should reach"
                )
                self.assertTrue(
                    "not a deterministic-layer target" in flattened
                    or deterministic_target_phrase in flattened
                    or "`needs_review` or `true_inference_miss` as buckets the deterministic layer should reach"
                    in flattened
                )


if __name__ == "__main__":
    unittest.main()
