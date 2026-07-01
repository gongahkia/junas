import importlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from junas.backend import main


class CorsConfigurationTests(unittest.TestCase):
    def tearDown(self):
        importlib.reload(main)

    def test_hosted_server_cors_allows_configured_origin_without_credentials(self):
        with patch.dict(
            os.environ,
            {
                "JUNAS_ALLOWED_ORIGINS": "https://app.example.com",
                "JUNAS_LOCAL_DAEMON_ACL_ENABLED": "0",
            },
            clear=False,
        ):
            app_main = importlib.reload(main)
            with TestClient(app_main.app) as client:
                response = client.options(
                    "/review",
                    headers={
                        "Origin": "https://app.example.com",
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type,authorization",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://app.example.com")
        self.assertIn("authorization", response.headers["access-control-allow-headers"].lower())
        self.assertNotEqual(response.headers.get("access-control-allow-credentials"), "true")

    def test_hosted_server_cors_rejects_unconfigured_origin(self):
        with patch.dict(
            os.environ,
            {
                "JUNAS_ALLOWED_ORIGINS": "https://app.example.com",
                "JUNAS_LOCAL_DAEMON_ACL_ENABLED": "0",
            },
            clear=False,
        ):
            app_main = importlib.reload(main)
            with TestClient(app_main.app) as client:
                response = client.options(
                    "/review",
                    headers={
                        "Origin": "https://evil.example",
                        "Access-Control-Request-Method": "POST",
                    },
                )

        self.assertEqual(response.status_code, 400)
        self.assertNotEqual(response.headers.get("access-control-allow-credentials"), "true")

    def test_local_daemon_cors_allows_configured_origin_without_credentials(self):
        with patch.dict(
            os.environ,
            {
                "JUNAS_ALLOWED_ORIGINS": "http://localhost,http://127.0.0.1",
                "JUNAS_LOCAL_DAEMON_ACL_ENABLED": "1",
                "JUNAS_LOCAL_DAEMON_ALLOWED_ORIGINS": "https://chatgpt.com,chrome-extension://*",
                "JUNAS_LOCAL_DAEMON_TOKEN": "local-test-token",
            },
            clear=False,
        ):
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "https://chatgpt.com")
        self.assertIn("x-junas-local-token", response.headers["access-control-allow-headers"].lower())
        self.assertNotEqual(response.headers.get("access-control-allow-credentials"), "true")


if __name__ == "__main__":
    unittest.main()
