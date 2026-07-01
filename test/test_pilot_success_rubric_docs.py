import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class PilotSuccessRubricDocsTests(unittest.TestCase):
    def test_pilot_success_rubric_requires_core_measures(self):
        text = squash((ROOT / "docs" / "product" / "pilot-success-rubric.md").read_text(encoding="utf-8"))

        for token in (
            "Pilot Success Rubric",
            "Avoided risky sends/shares/submits",
            "Accepted rewrites",
            "Reviewer decisions",
            "Low false-positive fatigue",
            "false-positive override rate",
            "support-ticket trend",
            "expand, hold, or stop",
            "Do not use activation rate alone as a success claim",
        ):
            self.assertIn(token, text)

    def test_pilot_success_rubric_requires_raw_free_evidence_shape(self):
        text = squash((ROOT / "docs" / "product" / "pilot-success-rubric.md").read_text(encoding="utf-8"))

        for token in (
            "Backend metrics",
            "Review journal",
            "Adapter telemetry",
            "Audit pack",
            "Support intake",
            "denominator confidence",
            "raw prompt, email body, document text, matched span",
            "raw customer text pasted into tickets",
        ):
            self.assertIn(token, text)

    def test_docs_index_and_value_metrics_link_pilot_success_rubric(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        value_metrics = (ROOT / "docs" / "product" / "value-metrics.md").read_text(encoding="utf-8")

        self.assertIn("product/pilot-success-rubric.md", docs_index)
        self.assertIn("docs/product/pilot-success-rubric.md", value_metrics)


if __name__ == "__main__":
    unittest.main()
