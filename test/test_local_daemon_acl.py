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


if __name__ == "__main__":
    unittest.main()
