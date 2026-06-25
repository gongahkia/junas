import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from junas.backend.schemas import ReviewRequest


class ReviewRequestWorkflowContextTests(unittest.TestCase):
    def _payload(self, **overrides):
        payload = {"text": "Send Dr Jane Tan S1234567D the confidential draft."}
        payload.update(overrides)
        return payload

    def test_accepts_workflow_context_fields(self):
        req = ReviewRequest.model_validate(
            self._payload(
                surface="outlook",
                workflow="email_send",
                actor_role="end_user",
                recipient_domains=[" Example.COM. ", "law.example"],
                recipient_count=2,
                attachment_count=1,
                sensitivity_label=" confidential ",
                external_destination=True,
                requested_action="send",
            )
        )

        self.assertEqual(req.surface, "outlook")
        self.assertEqual(req.workflow, "email_send")
        self.assertEqual(req.actor_role, "end_user")
        self.assertEqual(req.recipient_domains, ["example.com", "law.example"])
        self.assertEqual(req.recipient_count, 2)
        self.assertEqual(req.attachment_count, 1)
        self.assertEqual(req.sensitivity_label, "confidential")
        self.assertTrue(req.external_destination)
        self.assertEqual(req.requested_action, "send")

    def test_backward_compatible_without_workflow_context(self):
        req = ReviewRequest.model_validate(self._payload())

        self.assertIsNone(req.surface)
        self.assertIsNone(req.workflow)
        self.assertIsNone(req.actor_role)
        self.assertIsNone(req.recipient_domains)
        self.assertIsNone(req.recipient_count)
        self.assertIsNone(req.attachment_count)
        self.assertIsNone(req.sensitivity_label)
        self.assertIsNone(req.external_destination)
        self.assertIsNone(req.requested_action)

    def test_empty_recipient_domains_allowed(self):
        req = ReviewRequest.model_validate(self._payload(recipient_domains=[]))

        self.assertEqual(req.recipient_domains, [])

    def test_allowed_enum_values(self):
        valid_values = {
            "surface": [
                "api",
                "outlook",
                "browser_genai",
                "dms",
                "desktop",
                "word",
                "slack",
                "google_workspace",
                "other",
            ],
            "workflow": [
                "api_review",
                "email_send",
                "prompt_submit",
                "document_upload",
                "document_review",
                "desktop_watch",
                "reviewer_override",
                "auditor_export",
                "collaboration_message",
                "other",
            ],
            "actor_role": [
                "end_user",
                "legal_reviewer",
                "compliance_admin",
                "security_engineer",
                "platform_integrator",
                "auditor",
                "service_account",
                "other",
            ],
            "requested_action": [
                "review",
                "send",
                "submit",
                "upload",
                "safe_rewrite",
                "redact_pii",
                "pseudonymize",
                "anonymize",
                "request_approval",
                "hold_until_public",
                "cite_public_source",
                "proceed_with_warning",
                "other",
            ],
        }
        for field, values in valid_values.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    req = ReviewRequest.model_validate(self._payload(**{field: value}))
                    self.assertEqual(getattr(req, field), value)

    def test_unknown_enum_values_rejected(self):
        for field in ("surface", "workflow", "actor_role", "requested_action"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    ReviewRequest.model_validate(self._payload(**{field: "not_allowed"}))

    def test_max_lengths_and_count_bounds(self):
        invalid_payloads = [
            self._payload(recipient_domains=["example.com"] * 101),
            self._payload(recipient_domains=["a" * 254]),
            self._payload(recipient_domains=["bad domain.example"]),
            self._payload(recipient_count=-1),
            self._payload(recipient_count=10001),
            self._payload(attachment_count=-1),
            self._payload(attachment_count=1001),
            self._payload(sensitivity_label="x" * 129),
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    ReviewRequest.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
