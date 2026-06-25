import base64
import hashlib
import hmac
import importlib
import json
import os
import tempfile
import time
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def _b64url(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _hs256_token(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    raw_header = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    raw_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{raw_header}.{raw_payload}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{raw_header}.{raw_payload}.{_b64url(signature)}"


class TenantIsolationTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        credentials = {
            "tenant-a-key": {
                "tenant_id": "tenant-a",
                "subject": "alice",
                "roles": ["reviewer", "maker", "auditor"],
            },
            "tenant-b-key": {
                "tenant_id": "tenant-b",
                "subject": "bob",
                "roles": ["reviewer", "maker", "auditor"],
            },
            "reviewer-only-key": {
                "tenant_id": "tenant-a",
                "subject": "readonly",
                "roles": ["reviewer"],
            },
        }
        self._env = {
            "JUNAS_TENANCY_ENABLED": "1",
            "JUNAS_TENANCY_AUTH_MODES": "api_key",
            "JUNAS_TENANT_CREDENTIALS_JSON": json.dumps(credentials),
            "JUNAS_JOURNAL_DIR": str(self.tmpdir),
            "JUNAS_JOURNAL_KEY": "tenant-test-key",
            "JUNAS_REVIEW_PERSIST": "1",
            "JUNAS_SUBJECT_INDEX_KEY": "subject-index-test-key",
        }
        self._old_env = {key: os.environ.get(key) for key in self._env}
        os.environ.update(self._env)

        import junas.anonymize.mapping_store as mapping_mod
        import junas.backend.main as main_mod
        import junas.review.decisions as decisions_mod
        import junas.review.journal as journal_mod

        importlib.reload(journal_mod)
        importlib.reload(decisions_mod)
        importlib.reload(mapping_mod)
        importlib.reload(main_mod)
        self.main = main_mod
        self.main.app.router.lifespan_context = _noop_lifespan
        self.main._state.clear()
        self.main.app.openapi_schema = None

    def tearDown(self):
        self._tmpdir.cleanup()
        for key, old_value in self._old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        import junas.backend.main as main_mod

        importlib.reload(main_mod)

    def _start_review(self, client: TestClient, api_key: str) -> str:
        response = client.post(
            "/review",
            headers={"X-API-Key": api_key},
            json={
                "text": "Dr Jane Tan signed at jane@example.com. The Purchaser is Acme Pte Ltd.",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "SG",
                "document_type": "SPA",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["request_id"]

    def test_review_state_and_decisions_are_tenant_scoped(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_review(client, "tenant-a-key")

            tenant_a_state = client.get(f"/review/{review_id}", headers={"X-API-Key": "tenant-a-key"})
            self.assertEqual(tenant_a_state.status_code, 200, tenant_a_state.text)
            target = tenant_a_state.json()["findings"][0]

            tenant_b_state = client.get(f"/review/{review_id}", headers={"X-API-Key": "tenant-b-key"})
            self.assertEqual(tenant_b_state.status_code, 404)

            tenant_b_decision = client.post(
                f"/review/{review_id}/decision",
                headers={"X-API-Key": "tenant-b-key"},
                json={"finding_id": target["id"], "action": "accept"},
            )
            self.assertEqual(tenant_b_decision.status_code, 404)

            tenant_b_approval = client.post(
                "/request-approval",
                headers={"X-API-Key": "tenant-b-key"},
                json={"review_id": review_id, "finding_ids": [target["id"]]},
            )
            self.assertEqual(tenant_b_approval.status_code, 404)

            tenant_a_approval = client.post(
                "/request-approval",
                headers={"X-API-Key": "tenant-a-key"},
                json={"review_id": review_id, "finding_ids": [target["id"]]},
            )
            self.assertEqual(tenant_a_approval.status_code, 200, tenant_a_approval.text)
            self.assertEqual(tenant_a_approval.json()["requester_id"], "alice")
            self.assertEqual(tenant_a_approval.json()["requester_identity_source"], "api_key")

            tenant_a_decision = client.post(
                f"/review/{review_id}/decision",
                headers={"X-API-Key": "tenant-a-key"},
                json={"finding_id": target["id"], "action": "accept"},
            )
            self.assertEqual(tenant_a_decision.status_code, 200)
            self.assertEqual(tenant_a_decision.json()["reviewer_id"], "alice")
            self.assertEqual(tenant_a_decision.json()["reviewer_identity_source"], "api_key")

    def test_mapping_store_reidentify_is_tenant_scoped_and_header_tenant_is_ignored(self):
        with TestClient(self.main.app) as client:
            anon = client.post(
                "/pseudonymize",
                headers={"X-API-Key": "tenant-a-key", "X-Tenant-ID": "tenant-b"},
                json={"text": "Send Dr Jane Tan S1234567D to jane@example.com."},
            )
            self.assertEqual(anon.status_code, 200, anon.text)
            payload = anon.json()
            self.assertTrue(payload["mapping_persisted"])

            wrong_tenant = client.post(
                "/reidentify",
                headers={"X-API-Key": "tenant-b-key"},
                json={"anonymized_text": payload["anonymized_text"], "document_hash": payload["document_hash"]},
            )
            self.assertEqual(wrong_tenant.status_code, 404)

            right_tenant = client.post(
                "/reidentify",
                headers={"X-API-Key": "tenant-a-key"},
                json={"anonymized_text": payload["anonymized_text"], "document_hash": payload["document_hash"]},
            )
            self.assertEqual(right_tenant.status_code, 200)
            self.assertIn("Dr Jane Tan", right_tenant.json()["text"])

    def test_insufficient_role_returns_403(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_review(client, "tenant-a-key")
            state = client.get(f"/review/{review_id}", headers={"X-API-Key": "tenant-a-key"}).json()
            response = client.post(
                f"/review/{review_id}/decision",
                headers={"X-API-Key": "reviewer-only-key"},
                json={"finding_id": state["findings"][0]["id"], "action": "accept"},
            )
            self.assertEqual(response.status_code, 403)

    def test_reviewer_role_cannot_read_audit_state(self):
        with TestClient(self.main.app) as client:
            review_id = self._start_review(client, "tenant-a-key")
            response = client.get(f"/review/{review_id}", headers={"X-API-Key": "reviewer-only-key"})

        self.assertEqual(response.status_code, 403)


class TenantJWTAuthTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        self.secret = "jwt-test-secret"
        self._env = {
            "JUNAS_TENANCY_ENABLED": "1",
            "JUNAS_TENANCY_AUTH_MODES": "jwt",
            "JUNAS_JWT_HS256_SECRET": self.secret,
            "JUNAS_JWT_ISSUER": "https://issuer.example",
            "JUNAS_JWT_AUDIENCE": "junas-api",
            "JUNAS_JOURNAL_DIR": str(self.tmpdir),
            "JUNAS_JOURNAL_KEY": "jwt-test-journal-key",
            "JUNAS_REVIEW_PERSIST": "1",
            "JUNAS_SUBJECT_INDEX_KEY": "subject-index-test-key",
        }
        self._old_env = {key: os.environ.get(key) for key in self._env}
        os.environ.update(self._env)

        import junas.backend.main as main_mod

        importlib.reload(main_mod)
        self.main = main_mod
        self.main.app.router.lifespan_context = _noop_lifespan
        self.main._state.clear()
        self.main.app.openapi_schema = None

    def tearDown(self):
        self._tmpdir.cleanup()
        for key, old_value in self._old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        import junas.backend.main as main_mod

        importlib.reload(main_mod)

    def _token(self, **overrides) -> str:
        payload = {
            "iss": "https://issuer.example",
            "aud": "junas-api",
            "sub": "user-1",
            "tenant_id": "tenant-jwt",
            "roles": ["reviewer"],
            "exp": int(time.time()) + 300,
        }
        payload.update(overrides)
        return _hs256_token(payload, self.secret)

    def test_jwt_resolves_tenant_and_roles(self):
        token = self._token()
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review",
                headers={"Authorization": f"Bearer {token}"},
                json={"text": "Send Dr Jane Tan to jane@example.com."},
            )

        self.assertEqual(response.status_code, 200, response.text)

    def test_jwt_subject_is_recorded_as_reviewer_identity(self):
        token = self._token(sub="casey", roles=["maker", "auditor"])
        with TestClient(self.main.app) as client:
            review = client.post(
                "/review",
                headers={"Authorization": f"Bearer {token}"},
                json={"text": "Send Dr Jane Tan to jane@example.com."},
            )
            self.assertEqual(review.status_code, 200, review.text)
            payload = review.json()
            decision = client.post(
                f"/review/{payload['request_id']}/decision",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Reviewer-ID": "spoofed@example.com",
                },
                json={
                    "finding_id": payload["findings"][0]["id"],
                    "action": "accept",
                    "reviewer_id": "body-spoof@example.com",
                },
            )
            self.assertEqual(decision.status_code, 200, decision.text)
            self.assertEqual(decision.json()["reviewer_id"], "casey")
            self.assertEqual(decision.json()["reviewer_identity_source"], "jwt")

            state = client.get(
                f"/review/{payload['request_id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(state.status_code, 200, state.text)
            finding = state.json()["findings"][0]
            self.assertEqual(finding["decision_reviewer_id"], "casey")
            self.assertEqual(finding["decision_reviewer_identity_source"], "jwt")

    def test_jwt_bad_audience_is_rejected(self):
        token = self._token(aud="other-api")
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review",
                headers={"Authorization": f"Bearer {token}"},
                json={"text": "Send Dr Jane Tan to jane@example.com."},
            )

        self.assertEqual(response.status_code, 401)

    def test_jwt_expired_token_is_rejected(self):
        token = self._token(exp=int(time.time()) - 1)
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review",
                headers={"Authorization": f"Bearer {token}"},
                json={"text": "Send Dr Jane Tan to jane@example.com."},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "bearer token expired")

    def test_jwt_signature_tampering_is_rejected(self):
        token = self._token()
        token = token[:-1] + ("A" if token[-1] != "A" else "B")
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review",
                headers={"Authorization": f"Bearer {token}"},
                json={"text": "Send Dr Jane Tan to jane@example.com."},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "invalid bearer token signature")


if __name__ == "__main__":
    unittest.main()
