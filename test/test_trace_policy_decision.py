import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "trace_policy_decision.sh"


class TracePolicyDecisionTests(unittest.TestCase):
    def test_trace_outputs_policy_metadata_and_siem_status_without_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            response = root / "review.json"
            siem_log = root / "siem.jsonl"
            response.write_text(
                json.dumps(
                    {
                        "request_id": "req-1",
                        "text": "Send Dr Jane Tan S1234567D",
                        "findings": [{"matched_text": "Dr Jane Tan"}],
                        "timings_ms": {"review": 4.2, "policy_decision_ms": 0.7, "total": 4.9},
                        "policy_decision": {
                            "policy_id": "default",
                            "policy_version": "2026-06-14",
                            "decision": "rewrite_required",
                            "send_allowed": False,
                            "policy_reasons": ["high-risk PII requires safe rewrite"],
                            "review_id": "req-1",
                        },
                    }
                ),
                encoding="utf-8",
            )
            siem_log.write_text(
                json.dumps(
                    {
                        "schema_version": "junas.siem.v1",
                        "event_type": "journal_event",
                        "action": "policy_decision_recorded",
                        "outcome": "sealed",
                        "request_id": "",
                        "review_id": "req-1",
                        "details": {
                            "journal_event_type": "policy_decision_recorded",
                            "policy_id": "default",
                            "policy_version": "2026-06-14",
                            "decision": "rewrite_required",
                            "payload_sha256": "a" * 64,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [str(SCRIPT), "--response-json", str(response), "--siem-log", str(siem_log), "--tail-lines", "20"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("request_id=req-1", result.stdout)
        self.assertIn("policy_id=default", result.stdout)
        self.assertIn("policy_version=2026-06-14", result.stdout)
        self.assertIn("decision=rewrite_required", result.stdout)
        self.assertIn('timings_ms={"policy_decision_ms":0.7,"review":4.2,"total":4.9}', result.stdout)
        self.assertIn("siem_event_status=found", result.stdout)
        self.assertNotIn("Dr Jane Tan", result.stdout)
        self.assertNotIn("S1234567D", result.stdout)
        self.assertNotIn("matched_text", result.stdout)
        self.assertNotIn("policy_reasons", result.stdout)

    def test_trace_marks_siem_not_checked_without_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            response = Path(tmp) / "review.json"
            response.write_text(
                json.dumps(
                    {
                        "request_id": "req-2",
                        "timings_ms": {"total": 1.0},
                        "policy_decision": {"policy_id": "default", "decision": "allow"},
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [str(SCRIPT), "--response-json", str(response)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("siem_event_status=not_checked", result.stdout)


if __name__ == "__main__":
    unittest.main()
