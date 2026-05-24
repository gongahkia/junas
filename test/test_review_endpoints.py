import importlib
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
        os.environ["KAYPOH_JOURNAL_DIR"] = str(self.tmpdir)
        os.environ["KAYPOH_JOURNAL_KEY"] = "test-key"
        os.environ["KAYPOH_REVIEW_PERSIST"] = "1"

        import kaypoh.review.journal as journal_mod
        import kaypoh.review.decisions as decisions_mod
        import backend.main as main_mod

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
        for var in ("KAYPOH_JOURNAL_DIR", "KAYPOH_JOURNAL_KEY", "KAYPOH_REVIEW_PERSIST"):
            os.environ.pop(var, None)
        import backend.main as main_mod
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

            updated = client.get(f"/review/{review_id}").json()
            updated_finding = next(f for f in updated["findings"] if f["id"] == target["id"])
            self.assertEqual(updated_finding["decision"], "reject")
            self.assertEqual(updated["decisions_recorded"], 1)

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


class ReviewSessionPersistenceDisabledTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("KAYPOH_REVIEW_PERSIST", None)
        import backend.main as main_mod
        importlib.reload(main_mod)
        self.main = main_mod
        self.main._state.clear()
        self.main.app.openapi_schema = None
        self.main.app.router.lifespan_context = _noop_lifespan

    def tearDown(self):
        import backend.main as main_mod
        importlib.reload(main_mod)

    def test_decision_endpoint_returns_409_when_persistence_disabled(self):
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review/anything/decision",
                json={"finding_id": "x", "action": "accept"},
            )
            self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
