import importlib
import json
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class ReviewSessionEndpointsTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        os.environ["JUNAS_JOURNAL_DIR"] = str(self.tmpdir)
        os.environ["JUNAS_JOURNAL_KEY"] = "test-key"
        os.environ["JUNAS_REVIEW_PERSIST"] = "1"
        os.environ["JUNAS_MAPPING_STORE_KEY"] = "q5cVCBcQ0PHsgxBpwoXOrp0tGSgZBz7oBfZmuZBFLJk="
        os.environ["JUNAS_SUBJECT_INDEX_KEY"] = "subject-index-test-key"

        import junas.backend.main as main_mod
        import junas.review.decisions as decisions_mod
        import junas.review.journal as journal_mod

        importlib.reload(journal_mod)
        importlib.reload(decisions_mod)
        # main.py imported decisions at startup; reload it so the symbols rebind to the
        # reloaded module instance the tests are inspecting.
        importlib.reload(main_mod)
        self.main = main_mod
        self.main._state.clear()
        self.main.app.openapi_schema = None
        self.main.app.router.lifespan_context = _noop_lifespan

    def tearDown(self):
        self._tmpdir.cleanup()
        for var in (
            "JUNAS_JOURNAL_DIR",
            "JUNAS_JOURNAL_KEY",
            "JUNAS_REVIEW_PERSIST",
            "JUNAS_MAPPING_STORE_KEY",
            "JUNAS_SUBJECT_INDEX_KEY",
            "JUNAS_DEV_AUTH",
        ):
            os.environ.pop(var, None)
        import junas.backend.main as main_mod
        importlib.reload(main_mod)

    def _start_session(self, client: TestClient) -> str:
        response = client.post(
            "/review",
            json={
                "text": "Dr Jane Tan signed at jane@example.com. The Purchaser is Acme Pte Ltd.",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "SG",
                "document_type": "SPA",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["findings"])
        return payload["request_id"]

    def test_review_started_journal_omits_raw_matched_text_by_default(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)

        import junas.review.decisions as decisions_mod
        import junas.review.journal as journal_mod

        review_events = [
            entry
            for entry in journal_mod.read_journal(review_id=review_id)
            if entry.event_type == decisions_mod.EVENT_REVIEW_STARTED
        ]
        self.assertEqual(len(review_events), 1)
        serialized = json.dumps(review_events[0].payload, sort_keys=True)
        findings = review_events[0].payload["findings"]
        self.assertTrue(findings)
        self.assertTrue(all("matched_text" not in finding for finding in findings))
        self.assertTrue(any("matched_text_sha256" in finding for finding in findings))
        self.assertTrue(all("start_char" in finding and "end_char" in finding for finding in findings))
        self.assertTrue(all("rule" in finding for finding in findings))
        self.assertNotIn("Dr Jane Tan", serialized)
        self.assertNotIn("jane@example.com", serialized)

    def test_round_trip_review_decision_and_state(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)
            state = client.get(f"/review/{review_id}").json()
            findings = state["findings"]
            self.assertTrue(findings)
            self.assertTrue(all(f["decision"] is None for f in findings))

            target = findings[0]
            decision_resp = client.post(
                f"/review/{review_id}/decision",
                json={"finding_id": target["id"], "action": "reject", "rationale": "false positive"},
            )
            self.assertEqual(decision_resp.status_code, 200)
            self.assertEqual(decision_resp.json()["action"], "reject")
            self.assertEqual(decision_resp.json()["reviewer_id"], "")
            self.assertEqual(decision_resp.json()["reviewer_identity_source"], "none")

            updated = client.get(f"/review/{review_id}").json()
            updated_finding = next(f for f in updated["findings"] if f["id"] == target["id"])
            self.assertEqual(updated_finding["decision"], "reject")
            self.assertEqual(updated["decisions_recorded"], 1)

    def test_reviewer_id_header_is_ignored_without_dev_auth(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)
            state = client.get(f"/review/{review_id}").json()
            target = state["findings"][0]

            resp = client.post(
                f"/review/{review_id}/decision",
                json={"finding_id": target["id"], "action": "accept"},
                headers={"X-Reviewer-ID": "priya.raman@example.bank"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["reviewer_id"], "")
            self.assertEqual(resp.json()["reviewer_identity_source"], "none")

            updated = client.get(f"/review/{review_id}").json()
            updated_finding = next(f for f in updated["findings"] if f["id"] == target["id"])
            self.assertEqual(updated_finding["decision_reviewer_id"], "")
            self.assertEqual(updated_finding["decision_reviewer_identity_source"], "none")

    def test_request_body_reviewer_id_is_not_authoritative(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)
            target = client.get(f"/review/{review_id}").json()["findings"][0]

            resp = client.post(
                f"/review/{review_id}/decision",
                json={
                    "finding_id": target["id"],
                    "action": "accept",
                    "reviewer_id": "sarah.lim@example.law",
                },
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["reviewer_id"], "")
            self.assertEqual(resp.json()["reviewer_identity_source"], "none")

    def test_reviewer_id_header_is_dev_only_and_overrides_body(self):
        os.environ["JUNAS_DEV_AUTH"] = "1"
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)
            target = client.get(f"/review/{review_id}").json()["findings"][0]

            resp = client.post(
                f"/review/{review_id}/decision",
                json={
                    "finding_id": target["id"],
                    "action": "accept",
                    "reviewer_id": "body.identity@example.com",
                },
                headers={"X-Reviewer-ID": "header.identity@example.com"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["reviewer_id"], "header.identity@example.com")
            self.assertEqual(resp.json()["reviewer_identity_source"], "dev_header")

    def test_unknown_finding_returns_404(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)
            response = client.post(
                f"/review/{review_id}/decision",
                json={"finding_id": "no-such-finding", "action": "accept"},
            )
            self.assertEqual(response.status_code, 404)

    def test_unknown_review_id_returns_404(self):
        with TestClient(self.main.app) as client:
            self._start_session(client)
            response = client.get("/review/nope-not-a-real-id")
            self.assertEqual(response.status_code, 404)

    def test_invalid_action_returns_422(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)
            state = client.get(f"/review/{review_id}").json()
            target = state["findings"][0]
            response = client.post(
                f"/review/{review_id}/decision",
                json={"finding_id": target["id"], "action": "archive"},
            )
            self.assertEqual(response.status_code, 422)

    def test_extended_review_decision_actions_replay_latest(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)
            target = client.get(f"/review/{review_id}").json()["findings"][0]

            approve = client.post(
                f"/review/{review_id}/decision",
                json={"finding_id": target["id"], "action": "approve"},
            )
            self.assertEqual(approve.status_code, 200, approve.text)
            self.assertEqual(approve.json()["action"], "approve")

            exception = client.post(
                f"/review/{review_id}/decision",
                json={"finding_id": target["id"], "action": "policy_exception"},
            )
            self.assertEqual(exception.status_code, 200, exception.text)
            self.assertEqual(exception.json()["action"], "policy_exception")

            updated = client.get(f"/review/{review_id}").json()
            updated_finding = next(f for f in updated["findings"] if f["id"] == target["id"])
            self.assertEqual(updated_finding["decision"], "policy_exception")
            self.assertEqual(updated["decisions_recorded"], 1)

    def test_request_approval_records_pending_state_and_role_requirements(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)
            target = client.get(f"/review/{review_id}").json()["findings"][0]
            response = client.post(
                "/request-approval",
                json={
                    "review_id": review_id,
                    "finding_ids": [target["id"]],
                    "reason_code": "rewrite_required",
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["approval_status"], "pending")
            self.assertEqual(payload["requested_action"], "request_approval")
            self.assertEqual(payload["requested_finding_ids"], [target["id"]])
            self.assertEqual(payload["required_reviewer_roles"], ["maker", "checker", "admin"])
            self.assertEqual(payload["required_policy_actor_roles"], ["legal_reviewer", "compliance_admin"])
            self.assertEqual(payload["reason_code"], "rewrite_required")
            self.assertEqual(payload["requester_id"], "")
            self.assertEqual(payload["requester_identity_source"], "none")
            self.assertEqual(len(payload["hmac"]), 64)

            updated = client.get(f"/review/{review_id}").json()
            self.assertEqual(updated["approvals_requested"], 1)
            pending = updated["pending_approvals"][0]
            self.assertEqual(pending["finding_ids"], [target["id"]])
            self.assertEqual(pending["required_reviewer_roles"], ["maker", "checker", "admin"])

        import junas.review.decisions as decisions_mod
        import junas.review.journal as journal_mod

        approval_events = [
            entry for entry in journal_mod.read_journal(review_id=review_id)
            if entry.event_type == decisions_mod.EVENT_APPROVAL_REQUESTED
        ]
        self.assertEqual(len(approval_events), 1)
        serialized = json.dumps(approval_events[0].payload, sort_keys=True)
        self.assertNotIn("Dr Jane Tan", serialized)
        self.assertNotIn("jane@example.com", serialized)

    def test_request_approval_rejects_unknown_finding(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_session(client)
            response = client.post(
                "/request-approval",
                json={"review_id": review_id, "finding_ids": ["missing-finding"]},
            )
            self.assertEqual(response.status_code, 404)


class ReviewSessionPersistenceDisabledTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("JUNAS_REVIEW_PERSIST", None)
        import junas.backend.main as main_mod
        importlib.reload(main_mod)
        self.main = main_mod
        self.main._state.clear()
        self.main.app.openapi_schema = None
        self.main.app.router.lifespan_context = _noop_lifespan

    def tearDown(self):
        import junas.backend.main as main_mod
        importlib.reload(main_mod)

    def test_decision_endpoint_returns_409_when_persistence_disabled(self):
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review/anything/decision",
                json={"finding_id": "x", "action": "accept"},
            )
            self.assertEqual(response.status_code, 409)

    def test_request_approval_returns_409_when_persistence_disabled(self):
        with TestClient(self.main.app) as client:
            response = client.post(
                "/request-approval",
                json={"review_id": "anything"},
            )
            self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
