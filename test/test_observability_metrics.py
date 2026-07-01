import unittest

from junas.backend.observability import ObservabilityManager


class ObservabilityMetricsTests(unittest.TestCase):
    def test_product_metric_counters_export_expected_series(self):
        observability = ObservabilityManager()

        observability.observe_adapter_timeout("browser_genai", "prompt_submit", "mv3_content_script")
        observability.observe_degraded_mode(
            "/review",
            "outlook",
            "email_send",
            "image_ocr",
            "failed_open",
        )
        observability.observe_approval_requested("pending", "rewrite_required")
        observability.observe_approval_completed("approve")
        observability.observe_safe_rewrite_applied(
            "/safe-rewrite",
            "browser_genai",
            "prompt_submit",
            "safe_rewrite",
            2,
        )

        metrics = observability.render_metrics().decode("utf-8")
        self.assertIn(
            'junas_adapter_timeouts_total{adapter="mv3_content_script",'
            'surface="browser_genai",workflow="prompt_submit"} 1.0',
            metrics,
        )
        self.assertIn(
            'junas_degraded_modes_total{endpoint="/review",mode="image_ocr",'
            'status="failed_open",surface="outlook",workflow="email_send"} 1.0',
            metrics,
        )
        self.assertIn(
            'junas_approval_requests_total{reason_code="rewrite_required",status="pending"} 1.0',
            metrics,
        )
        self.assertIn('junas_approval_completed_total{action="approve"} 1.0', metrics)
        self.assertIn(
            'junas_safe_rewrite_applied_total{action="safe_rewrite",endpoint="/safe-rewrite",'
            'surface="browser_genai",workflow="prompt_submit"} 2.0',
            metrics,
        )


if __name__ == "__main__":
    unittest.main()
