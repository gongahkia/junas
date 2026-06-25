import importlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from junas.backend import main


class LocalDaemonAclTests(unittest.TestCase):
    def setUp(self):
        main._state.clear()

    def tearDown(self):
        main._state.clear()

    def _env(self) -> dict[str, str]:
        return {
            "JUNAS_API_KEY": "",
            "JUNAS_LOCAL_DAEMON_ACL_ENABLED": "1",
            "JUNAS_LOCAL_DAEMON_TOKEN": "local-test-token",
            "JUNAS_LOCAL_DAEMON_ALLOWED_ORIGINS": "https://chatgpt.com,chrome-extension://*",
        }

    def test_rejects_disallowed_browser_origin(self):
        with patch.dict(os.environ, self._env(), clear=False):
            with TestClient(main.app) as client:
                response = client.post(
                    "/classify",
                    json={"text": "public update"},
                    headers={
                        "Origin": "https://evil.example",
                        "X-Junas-Local-Token": "local-test-token",
                    },
                )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "origin not allowed for local daemon")

    def test_rejects_missing_local_token_on_protected_endpoint(self):
        with patch.dict(os.environ, self._env(), clear=False):
            with TestClient(main.app) as client:
                response = client.post(
                    "/classify",
                    json={"text": "public update"},
                    headers={"Origin": "https://chatgpt.com"},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "missing or invalid local daemon token")

    def test_rewrite_endpoints_require_local_token(self):
        with patch.dict(os.environ, self._env(), clear=False):
            with TestClient(main.app) as client:
                for endpoint in ("/pseudonymize", "/anonymize", "/redact"):
                    with self.subTest(endpoint=endpoint):
                        response = client.post(
                            endpoint,
                            json={"text": "Dr Jane Tan holds NRIC S1234567D."},
                            headers={"Origin": "https://chatgpt.com"},
                        )

                        self.assertEqual(response.status_code, 401)
                        self.assertEqual(response.json()["detail"], "missing or invalid local daemon token")

    def test_accepts_allowed_origin_with_local_token(self):
        with patch.dict(os.environ, self._env(), clear=False):
            with TestClient(main.app) as client:
                response = client.post(
                    "/classify",
                    json={"text": "public update"},
                    headers={
                        "Origin": "chrome-extension://abcdef",
                        "X-Junas-Local-Token": "local-test-token",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classification"], "SAFE")

    def test_runtime_status_is_open_but_does_not_return_token(self):
        with patch.dict(os.environ, self._env(), clear=False):
            with TestClient(main.app) as client:
                response = client.get(
                    "/local/pairing/status",
                    headers={"Origin": "https://chatgpt.com"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["acl_enabled"])
        self.assertTrue(payload["token_provisioned"])
        self.assertNotIn("local-test-token", response.text)

    def test_first_connect_pairing_issues_signed_client_token(self):
        with patch.dict(os.environ, self._env(), clear=False):
            with TestClient(main.app) as client:
                start = client.post(
                    "/local/pairing/start",
                    json={"client_name": "test extension"},
                    headers={"Origin": "https://chatgpt.com"},
                )
                self.assertEqual(start.status_code, 200, start.text)
                started = start.json()
                self.assertIn("pairing_id", started)
                self.assertIn("pairing_code", started)
                self.assertNotIn("client_token", started)

                pending = client.post(
                    "/local/pairing/claim",
                    json={
                        "pairing_id": started["pairing_id"],
                        "pairing_code": started["pairing_code"],
                    },
                    headers={"Origin": "https://chatgpt.com"},
                )
                self.assertEqual(pending.status_code, 202, pending.text)
                self.assertFalse(pending.json()["approved"])

                approve = client.post(
                    "/local/pairing/approve",
                    json={
                        "pairing_id": started["pairing_id"],
                        "pairing_code": started["pairing_code"],
                    },
                    headers={
                        "Origin": "https://chatgpt.com",
                        "X-Junas-Local-Token": "local-test-token",
                    },
                )
                self.assertEqual(approve.status_code, 200, approve.text)
                self.assertTrue(approve.json()["approved"])
                self.assertNotIn("client_token", approve.text)

                claim = client.post(
                    "/local/pairing/claim",
                    json={
                        "pairing_id": started["pairing_id"],
                        "pairing_code": started["pairing_code"],
                    },
                    headers={"Origin": "https://chatgpt.com"},
                )
                self.assertEqual(claim.status_code, 200, claim.text)
                token = claim.json()["client_token"]
                self.assertGreaterEqual(token.count("."), 2)

                response = client.post(
                    "/classify",
                    json={"text": "public update"},
                    headers={
                        "Origin": "https://chatgpt.com",
                        "X-Junas-Local-Token": token,
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["classification"], "SAFE")

    def test_pairing_approval_rejects_signed_client_token(self):
        with patch.dict(os.environ, self._env(), clear=False):
            signed = main.sign_local_client_token(
                "local-test-token",
                client_id="client-1",
                client_name="test extension",
                origin="https://chatgpt.com",
                ttl_seconds=300,
            )
            with TestClient(main.app) as client:
                start = client.post(
                    "/local/pairing/start",
                    json={"client_name": "test extension"},
                    headers={"Origin": "https://chatgpt.com"},
                ).json()
                response = client.post(
                    "/local/pairing/approve",
                    json={
                        "pairing_id": start["pairing_id"],
                        "pairing_code": start["pairing_code"],
                    },
                    headers={
                        "Origin": "https://chatgpt.com",
                        "X-Junas-Local-Token": signed,
                    },
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "missing or invalid local daemon approval token")

    def test_cors_preflight_allows_configured_origin_without_token(self):
        with patch.dict(os.environ, self._env(), clear=False):
            app_main = importlib.reload(main)
            with TestClient(app_main.app) as client:
                response = client.options(
                    "/classify",
                    headers={
                        "Origin": "https://chatgpt.com",
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type,x-junas-local-token",
                    },
                )
            importlib.reload(main)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://chatgpt.com")

    def test_cors_preflight_rejects_unconfigured_origin(self):
        with patch.dict(os.environ, self._env(), clear=False):
            app_main = importlib.reload(main)
            with TestClient(app_main.app) as client:
                response = client.options(
                    "/classify",
                    headers={
                        "Origin": "https://evil.example",
                        "Access-Control-Request-Method": "POST",
                    },
                )
            importlib.reload(main)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "origin not allowed for local daemon")


if __name__ == "__main__":
    unittest.main()
