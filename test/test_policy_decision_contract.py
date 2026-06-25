import json
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kaypoh.backend import main
from kaypoh.policy import WorkflowContext, evaluate_policy


class PolicyDecisionContractTests(unittest.TestCase):
    def test_policy_decision_shape_is_stable(self):
        decision = evaluate_policy(
            findings=[{"id": "p1", "category": "PII", "severity": "high"}],
            context=WorkflowContext(requested_action="send"),
            review_id="r1",
        ).as_dict()

        self.assertEqual(
            list(decision.keys()),
            [
                "decision",
                "send_allowed",
                "required_actions",
                "recommended_actions",
                "blocking_findings",
                "policy_id",
                "policy_version",
                "policy_reasons",
                "review_id",
            ],
        )

    def test_required_actions_and_reasons_are_sorted(self):
        decision = evaluate_policy(
            findings=[
                {"id": "p2", "category": "PII", "severity": "high"},
                {"id": "m1", "category": "MNPI", "severity": "high"},
                {"id": "p1", "category": "PII", "severity": "medium"},
            ],
            degraded_policy="block_send",
            degraded_modes=[{"mode": "document_ingest", "status": "failed_open"}],
            review_id="r1",
        )

        self.assertEqual(decision.required_actions, tuple(sorted(decision.required_actions)))
        self.assertEqual(decision.policy_reasons, tuple(sorted(decision.policy_reasons)))
        self.assertEqual(decision.blocking_findings, tuple(sorted(decision.blocking_findings)))

    def test_policy_reasons_are_deterministic(self):
        findings = [
            {"id": "m1", "category": "MNPI", "severity": "high"},
            {"id": "p1", "category": "PII", "severity": "high"},
        ]
        first = evaluate_policy(
            findings=findings,
            context=WorkflowContext(external_destination=True),
            degraded_policy="warn",
            review_id="r1",
        )
        second = evaluate_policy(
            findings=list(reversed(findings)),
            context=WorkflowContext(external_destination=True),
            degraded_policy="warn",
            review_id="r1",
        )

        self.assertEqual(first.policy_reasons, second.policy_reasons)
        self.assertEqual(first.required_actions, second.required_actions)
        self.assertEqual(first.blocking_findings, second.blocking_findings)

    def test_policy_metadata_does_not_include_raw_document_text(self):
        raw_text = "Send Dr Jane Tan S1234567D the confidential draft."
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "text": raw_text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        policy_blob = json.dumps(response.json()["policy_decision"], sort_keys=True)
        self.assertNotIn(raw_text, policy_blob)
        self.assertNotIn("Jane Tan", policy_blob)
        self.assertNotIn("S1234567D", policy_blob)


if __name__ == "__main__":
    unittest.main()
