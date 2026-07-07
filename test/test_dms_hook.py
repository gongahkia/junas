import json
import unittest

from junas.integrations.dms import (
    DmsAuthError,
    DmsBackendTimeout,
    DmsCheckInRequest,
    DmsValidationError,
    InMemoryDmsAuditRepository,
    MockDmsCheckInHook,
)


def _review_payload(decision: str, *, send_allowed: bool = False, degraded_modes=None):
    return {
        "request_id": f"req-{decision}",
        "review_id": f"rev-{decision}",
        "send_allowed": send_allowed,
        "policy_decision": {
            "decision": decision,
            "send_allowed": send_allowed,
            "required_actions": ["redact_pii"] if decision != "allow" else [],
            "recommended_actions": ["safe_rewrite"] if decision == "warn" else [],
            "policy_id": "default",
            "policy_version": "2026-07-07",
        },
        "review_expires_at": "2026-07-07T00:05:00Z",
        "overall_risk": "HIGH_RISK" if decision != "allow" else "SAFE",
        "pii_score": 88.0 if decision != "allow" else 0.0,
        "mnpi_score": 0.0,
        "degraded_modes": degraded_modes or [],
        "findings": [{"rule": "sg_nric_fin", "matched_text": "S1234567D"}] if decision != "allow" else [],
    }


class FakeReviewClient:
    def __init__(self, response=None, exc=None):
        self.response = response or _review_payload("allow", send_allowed=True)
        self.exc = exc
        self.calls = []

    def review(self, payload, *, idempotency_key):
        self.calls.append((dict(payload), idempotency_key))
        if self.exc:
            raise self.exc
        return dict(self.response)


class DmsHookTests(unittest.TestCase):
    def _request(self, *, text="Draft includes Dr Jane Tan S1234567D."):
        return DmsCheckInRequest(
            dms="mockdms",
            matter_id="mockdms:M123",
            document_id="D-100",
            dms_version_id="v1",
            text=text,
            actor_id="alice@example.com",
            source_jurisdiction="SG",
            destination_jurisdiction="US",
            recipient_domains=("outside-counsel.example",),
            sensitivity_label="confidential",
        )

    def test_mock_hook_calls_review_with_dms_surface_before_check_in(self):
        client = FakeReviewClient(_review_payload("allow", send_allowed=True))
        result = MockDmsCheckInHook(client).check_in(self._request())

        self.assertTrue(result.check_in_allowed)
        self.assertEqual(result.status, "allowed")
        self.assertEqual(len(client.calls), 1)
        payload, idempotency_key = client.calls[0]
        self.assertEqual(payload["surface"], "dms")
        self.assertEqual(payload["workflow"], "document_upload")
        self.assertEqual(payload["matter_id"], "mockdms:M123")
        self.assertEqual(payload["degraded_policy"], "block_send")
        self.assertTrue(idempotency_key.startswith("dms:"))
        self.assertNotIn("Dr Jane Tan", idempotency_key)

    def test_decision_mapping(self):
        cases = {
            "allow": ("allowed", True, True),
            "warn": ("warned", True, True),
            "approval_required": ("held_for_approval", False, False),
            "rewrite_required": ("held_for_rewrite", False, False),
            "block": ("blocked", False, False),
        }
        for decision, (status, allowed, send_allowed) in cases.items():
            with self.subTest(decision=decision):
                client = FakeReviewClient(_review_payload(decision, send_allowed=send_allowed))
                result = MockDmsCheckInHook(client).check_in(self._request())
                self.assertEqual(result.status, status)
                self.assertEqual(result.check_in_allowed, allowed)

    def test_degraded_review_holds_check_in(self):
        client = FakeReviewClient(
            _review_payload("allow", send_allowed=True, degraded_modes=[{"mode": "pdf_text_sparse"}])
        )
        result = MockDmsCheckInHook(client).check_in(self._request())

        self.assertEqual(result.status, "held_degraded")
        self.assertFalse(result.check_in_allowed)
        self.assertEqual(result.audit_fields["degraded_modes"], ["pdf_text_sparse"])

    def test_timeout_auth_backend_validation_and_local_validation_fail_closed(self):
        cases = (
            (DmsBackendTimeout("timeout"), self._request(), "backend_timeout"),
            (DmsAuthError("denied"), self._request(), "auth_failed"),
            (DmsValidationError("invalid"), self._request(), "validation_failed"),
            (None, self._request(text=" "), "validation_failed"),
        )
        for exc, req, expected in cases:
            with self.subTest(expected=expected):
                client = FakeReviewClient(exc=exc) if exc else FakeReviewClient()
                result = MockDmsCheckInHook(client).check_in(req)
                self.assertEqual(result.status, expected)
                self.assertFalse(result.check_in_allowed)

    def test_idempotent_retry_does_not_duplicate_audit_record_or_review_call(self):
        repository = InMemoryDmsAuditRepository()
        client = FakeReviewClient(_review_payload("approval_required", send_allowed=False))
        hook = MockDmsCheckInHook(client, repository=repository)
        req = self._request()

        first = hook.check_in(req)
        second = hook.check_in(req)

        self.assertEqual(first.status, "held_for_approval")
        self.assertEqual(second.status, "held_for_approval")
        self.assertTrue(second.duplicate)
        self.assertEqual(repository.count, 1)
        self.assertEqual(len(client.calls), 1)

    def test_audit_fields_exclude_raw_document_matched_text_auth_and_rationale(self):
        client = FakeReviewClient(_review_payload("block", send_allowed=False))
        result = MockDmsCheckInHook(client).check_in(self._request())
        serialized = json.dumps(result.audit_fields, sort_keys=True)

        self.assertEqual(result.audit_fields["schema_version"], "junas.dms.audit.v1")
        self.assertEqual(result.audit_fields["policy_decision"]["decision"], "block")
        self.assertEqual(result.audit_fields["finding_count"], 1)
        self.assertEqual(result.audit_fields["finding_rules"], ["sg_nric_fin"])
        self.assertIn("text_hash", result.audit_fields)
        for forbidden in (
            "Dr Jane Tan",
            "S1234567D",
            "matched_text",
            "Authorization",
            "Bearer",
            "reviewer rationale",
            "alice@example.com",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
