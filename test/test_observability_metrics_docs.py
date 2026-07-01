import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ObservabilityMetricsDocsTests(unittest.TestCase):
    def test_all_backend_metrics_are_documented_with_siem_boundary(self):
        source = (ROOT / "src" / "junas" / "backend" / "observability.py").read_text(encoding="utf-8")
        doc = (ROOT / "docs" / "observability-metrics.md").read_text(encoding="utf-8")
        metric_names = sorted(set(re.findall(r'"(junas_[a-z0-9_]+)"', source)))
        metric_names.append("junas_preflight_check_status")

        for metric_name in metric_names:
            with self.subTest(metric_name=metric_name):
                self.assertIn(f"`{metric_name}`", doc)

    def test_metrics_doc_defines_siem_local_and_disabled_boundaries(self):
        doc = (ROOT / "docs" / "observability-metrics.md").read_text(encoding="utf-8")

        for token in (
            "## SIEM-Safe Metrics",
            "## Local-Only Or Rollup-Only Metrics",
            "## Disabled Or Prohibited Metrics",
            "raw prompts",
            "matched_text",
            "local pairing token",
            "keyed hashes",
            "deploy/prometheus/junas-alerts.yml",
        ):
            self.assertIn(token, doc)

    def test_docs_index_links_metrics_boundary_doc(self):
        text = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("observability-metrics.md", text)


if __name__ == "__main__":
    unittest.main()
