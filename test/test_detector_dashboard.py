import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_detector_dashboard import build_dashboard
from scripts.generate_detector_dashboard import main as dashboard_main


def _write_eval_report(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "doc_count": 2,
                    "by_rule": {
                        "email_address": {"matched": 3, "missed": 1},
                        "phone_number": {"matched": 1, "missed": 0},
                    },
                },
                "documents": [
                    {
                        "source_jurisdiction": "SG",
                        "document_type": "memo",
                        "unexpected": [
                            {
                                "category": "PII",
                                "rule": "email_address",
                                "matched_text": "raw@example.test",
                            },
                            {
                                "category": "PII",
                                "rule": "phone_number",
                                "matched_text": "+65 5555 0101",
                            },
                        ],
                        "unexpected_triage": [
                            {
                                "bucket": "actual_detector_false_positive",
                                "rule": "email_address",
                                "matched_text": "raw@example.test",
                            },
                            {
                                "bucket": "taxonomy_model_label_mismatch",
                                "rule": "phone_number",
                                "matched_text": "+65 5555 0101",
                            },
                        ],
                        "must_not_detect_violations": [
                            {
                                "rule": "email_address",
                                "matched_text": "do-not-include@example.test",
                            }
                        ],
                    },
                    {
                        "source_jurisdiction": "US",
                        "document_type": "email",
                        "unexpected": [
                            {
                                "category": "PII",
                                "rule": "email_address",
                                "matched_text": "second@example.test",
                            }
                        ],
                        "unexpected_triage": [],
                        "must_not_detect_violations": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


class DetectorDashboardTests(unittest.TestCase):
    def test_dashboard_aggregates_override_signals_without_raw_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "eval.json"
            _write_eval_report(report_path)

            dashboard = build_dashboard([report_path], top=1)

        self.assertEqual(dashboard["schema_version"], "junas.detector_dashboard.v1")
        self.assertEqual(dashboard["summary"]["total_override_signals"], 4)
        self.assertEqual(dashboard["summary"]["top_override_rules"][0]["rule"], "email_address")
        email = next(item for item in dashboard["detectors"] if item["rule"] == "email_address")
        self.assertEqual(email["override_signals"], 3)
        self.assertEqual(email["unexpected"], 2)
        self.assertEqual(email["must_not_detect_violations"], 1)
        self.assertEqual(email["unexpected_triage"]["actual_detector_false_positive"], 1)
        self.assertEqual(email["by_jurisdiction"], {"SG": 2, "US": 1})
        rendered = json.dumps(dashboard, sort_keys=True)
        self.assertNotIn("matched_text", rendered)
        self.assertNotIn("raw@example.test", rendered)

    def test_dashboard_cli_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "eval.json"
            output = root / "dashboard.json"
            _write_eval_report(report_path)

            result = dashboard_main(["--eval-report", str(report_path), "--output", str(output), "--top", "2"])

            self.assertEqual(result, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["report_count"], 1)
            self.assertEqual(len(payload["summary"]["top_override_rules"]), 2)


if __name__ == "__main__":
    unittest.main()
