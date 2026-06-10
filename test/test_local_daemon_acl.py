import importlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from kaypoh.backend import main


class LocalDaemonAclTests(unittest.TestCase):
    def setUp(self):
        main._state.clear()

    def tearDown(self):
        main._state.clear()

    def _env(self) -> dict[str, str]:
        return {
            "KAYPOH_API_KEY": "",
            "KAYPOH_LOCAL_DAEMON_ACL_ENABLED": "1",
            "KAYPOH_LOCAL_DAEMON_TOKEN": "local-test-token",
            "KAYPOH_LOCAL_DAEMON_ALLOWED_ORIGINS": "https://chatgpt.com,chrome-extension://*",
        }

    def test_rejects_disallowed_browser_origin(self):
        with patch.dict(os.environ, self._env(), clear=False):
            with TestClient(main.app) as client:
                response = client.post(
                    "/classify",
                    json={"text": "public update"},
                    headers={
                        "Origin": "https://evil.example",
                        "X-Kaypoh-Local-Token": "local-test-token",
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
                        "X-Kaypoh-Local-Token": "local-test-token",
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

    def test_cors_preflight_allows_configured_origin_without_token(self):
        with patch.dict(os.environ, self._env(), clear=False):
            app_main = importlib.reload(main)
            with TestClient(app_main.app) as client:
                response = client.options(
                    "/classify",
                    headers={
                        "Origin": "https://chatgpt.com",
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type,x-kaypoh-local-token",
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
