import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_product_value_report import build_report, main

METRICS_TEXT = """
junas_review_surface_total{endpoint="/review",surface="outlook",workflow="email_send",decision="block"} 2
junas_review_surface_total{endpoint="/review",surface="outlook",workflow="email_send",decision="warn"} 3
junas_review_surface_total{endpoint="/review",surface="browser_genai",workflow="prompt_submit",decision="allow"} 5
junas_policy_decisions_total{decision="block",surface="outlook",workflow="email_send"} 2
junas_policy_decisions_total{decision="warn",surface="outlook",workflow="email_send"} 3
junas_policy_decisions_total{decision="allow",surface="browser_genai",workflow="prompt_submit"} 5
junas_policy_required_actions_total{action="safe_rewrite",decision="rewrite_required",surface="outlook",\
workflow="email_send"} 2
junas_policy_required_actions_total{action="request_approval",decision="approval_required",surface="outlook",\
workflow="email_send"} 1
junas_approval_requests_total{status="pending",reason_code="rewrite_required"} 1
junas_approval_completed_total{action="approve"} 1
junas_safe_rewrite_applied_total{endpoint="/safe-rewrite",surface="outlook",workflow="email_send",\
action="safe_rewrite"} 4
junas_reviewer_decisions_total{action="reject",decision_taxonomy="false_positive"} 1
junas_reviewer_decisions_total{action="approve",decision_taxonomy="acceptable_risk"} 3
unrelated_metric{raw_text="secret prompt",filename="board.docx"} 1
"""


class ProductValueReportTests(unittest.TestCase):
    def test_report_aggregates_value_rates_without_raw_content(self):
        report = build_report(METRICS_TEXT)

        self.assertEqual(report["schema_version"], "junas.product_value_report.v1")
        self.assertEqual(report["summary"]["reviewed_documents_total"], 10)
        self.assertEqual(report["summary"]["reviewed_documents_by_surface"], {"browser_genai": 5, "outlook": 5})
        self.assertEqual(report["rates"]["block_rate"]["value"], 0.2)
        self.assertEqual(report["rates"]["warn_rate"]["value"], 0.3)
        self.assertEqual(report["rates"]["rewrite_rate"]["value"], 0.2)
        self.assertEqual(report["rates"]["approval_rate"]["value"], 0.1)
        self.assertEqual(report["rates"]["override_rate"]["value"], 0.25)
        outlook = next(row for row in report["by_surface"] if row["surface"] == "outlook")
        self.assertEqual(outlook["workflows"], {"email_send": 5})
        rendered = json.dumps(report, sort_keys=True)
        self.assertNotIn("secret prompt", rendered)
        self.assertNotIn("board.docx", rendered)
        self.assertNotIn("raw_text", rendered)

    def test_report_cli_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics_path = root / "metrics.prom"
            output_path = root / "value-report.json"
            metrics_path.write_text(METRICS_TEXT, encoding="utf-8")

            result = main(["--metrics", str(metrics_path), "--output", str(output_path)])

            self.assertEqual(result, 0)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["override_decisions_total"], 1)


if __name__ == "__main__":
    unittest.main()
