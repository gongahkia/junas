import importlib
import json
import os
import sys
import tempfile
import textwrap
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from junas.policy import WorkflowContext, evaluate_policy, load_policy_profile


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class PolicyDeterminismTests(unittest.TestCase):
    def _write_policy_config(self) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        path = Path(tempdir.name) / "policy.toml"
        path.write_text(
            textwrap.dedent(
                """
                [policy]
                policy_id = "default"
                policy_version = "2026-06-14"
                internal_domains = ["example.com"]

                [tenants.tenant-a]
                policy_id = "tenant-a-strict"
                policy_version = "2026-06-14-tenant-a"
                high_pii_required_actions = ["request_approval", "safe_rewrite", "redact_pii"]
                high_mnpi_external_actions = ["request_approval", "hold_until_public"]
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_policy_engine_is_deterministic_for_same_context_config_and_tenant(self):
        profile = load_policy_profile(self._write_policy_config(), tenant_id="tenant-a", production=True)
        findings = [
            {"id": "pii:sg_nric_fin:25:34:0", "category": "PII", "severity": "high"},
            {"id": "mnpi:deal_codename:42:55:0", "category": "MNPI", "severity": "high"},
        ]
        context = WorkflowContext(
            source_jurisdiction="SG",
            destination_jurisdiction="US",
            surface="outlook",
            workflow="email_send",
            actor_role="end_user",
            recipient_domains=("external.example",),
            recipient_count=2,
            attachment_count=1,
            sensitivity_label="confidential",
            external_destination=True,
            requested_action="send",
        )

        decisions = [
            evaluate_policy(
                findings=findings,
                context=context,
                profile=profile,
                degraded_policy="warn",
                review_id="review-1",
            ).as_dict()
            for _ in range(3)
        ]

        self.assertEqual(decisions[0], decisions[1])
        self.assertEqual(decisions[1], decisions[2])
        self.assertEqual(decisions[0]["policy_id"], "tenant-a-strict")
        self.assertEqual(decisions[0]["policy_version"], "2026-06-14-tenant-a")

    def test_review_endpoint_policy_decision_is_deterministic_for_same_text_context_and_tenant(self):
        credentials = {
            "tenant-a-key": {
                "tenant_id": "tenant-a",
                "subject": "alice",
                "roles": ["reviewer"],
            }
        }
        env = {
            "JUNAS_TENANCY_ENABLED": "1",
            "JUNAS_TENANCY_AUTH_MODES": "api_key",
            "JUNAS_TENANT_CREDENTIALS_JSON": json.dumps(credentials),
        }
        old_env = {key: os.environ.get(key) for key in env}
        os.environ.update(env)
        try:
            import junas.backend.main as main_mod

            importlib.reload(main_mod)
            main_mod.app.router.lifespan_context = _noop_lifespan
            main_mod._state.clear()
            payload = {
                "text": "Send Dr Jane Tan S1234567D to external counsel before announcement.",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "US",
                "document_type": "email",
                "surface": "outlook",
                "workflow": "email_send",
                "actor_role": "end_user",
                "recipient_domains": ["external.example"],
                "recipient_count": 1,
                "attachment_count": 0,
                "sensitivity_label": "confidential",
                "external_destination": True,
                "requested_action": "send",
            }
            with TestClient(main_mod.app) as client:
                responses = [
                    client.post("/review", headers={"X-API-Key": "tenant-a-key"}, json=payload)
                    for _ in range(2)
                ]
        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value
            import junas.backend.main as main_mod

            importlib.reload(main_mod)

        for response in responses:
            self.assertEqual(response.status_code, 200, response.text)

        decisions = [response.json()["policy_decision"] for response in responses]
        normalized = []
        for decision in decisions:
            copy = dict(decision)
            copy.pop("review_id")
            normalized.append(copy)

        self.assertEqual(normalized[0], normalized[1])
        self.assertEqual(responses[0].json()["send_allowed"], responses[1].json()["send_allowed"])
        self.assertEqual(responses[0].json()["action_catalog"], responses[1].json()["action_catalog"])


if __name__ == "__main__":
    unittest.main()
