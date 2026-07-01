import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from junas.backend import main

ROOT = Path(__file__).resolve().parent.parent


class E2EReviewFixtureTests(unittest.TestCase):
    def _load_fixture(self, name: str) -> dict:
        path = ROOT / "test" / "fixtures" / "e2e" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_high_risk_external_email_blocks_and_requires_approval(self):
        fixture = self._load_fixture("high_risk_external_email_review.json")

        with TestClient(main.app) as client:
            response = client.post("/review", json=fixture["request"])

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        policy = body["policy_decision"]
        expected = fixture["expected"]
        self.assertEqual(policy["decision"], expected["decision"])
        self.assertEqual(policy["send_allowed"], expected["send_allowed"])
        self.assertFalse(body["send_allowed"])
        for action in expected["required_actions"]:
            self.assertIn(action, policy["required_actions"])
            self.assertIn(action, body["action_catalog"])
        self.assertTrue(policy["blocking_findings"])
        self.assertTrue(
            any(
                finding["category"] == expected["finding"]["category"]
                and finding["severity"] == expected["finding"]["severity"]
                for finding in body["findings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
