import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ProductValueMetricsDocsTests(unittest.TestCase):
    def test_privacy_safe_aggregation_docs_define_raw_free_value_measurement(self):
        text = (ROOT / "docs" / "product" / "value-metrics.md").read_text(encoding="utf-8")

        for token in (
            "## Privacy-Safe Aggregation Model",
            "Raw content is allowed only in the request body",
            "must not be copied into metrics stores",
            "`junas_review_surface_total`",
            "`junas_policy_decisions_total`",
            "`junas_policy_required_actions_total`",
            "`junas_adapter_timeouts_total`",
            "`junas_degraded_modes_total`",
            "`junas_approval_requests_total`",
            "`junas_approval_completed_total`",
            "`junas_safe_rewrite_applied_total`",
            "Top-N phrase, recipient, filename, subject, or excerpt reports",
            "denominator confidence: `complete`, `partial`, or `unknown`",
            "retention policy for the aggregate and the underlying event stream",
        ):
            self.assertIn(token, text)

    def test_docs_index_links_value_metrics_doc(self):
        text = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("product/value-metrics.md", text)


if __name__ == "__main__":
    unittest.main()
