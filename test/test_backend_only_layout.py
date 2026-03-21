import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as main


ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


class BackendOnlyLayoutTests(unittest.TestCase):
    def test_frontend_routes_are_not_mounted(self):
        with TestClient(main.app) as client:
            for path in ("/chat/", "/email/", "/slack/"):
                response = client.get(path)
                self.assertEqual(response.status_code, 404)

    def test_archived_demo_assets_exist(self):
        expected_paths = [
            ROOT / "archive" / "frontend-demos" / "legacy" / "index.html",
            ROOT / "archive" / "frontend-demos" / "chat" / "index.html",
            ROOT / "archive" / "frontend-demos" / "email" / "index.html",
            ROOT / "archive" / "frontend-demos" / "slack" / "index.html",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing archived demo asset: {path}")

    def test_launch_scripts_exist(self):
        expected_paths = [
            ROOT / "scripts" / "clean_dev.sh",
            ROOT / "scripts" / "launch" / "common.sh",
            ROOT / "scripts" / "launch" / "run_dev.sh",
            ROOT / "scripts" / "launch" / "run_prod.sh",
            ROOT / "scripts" / "launch" / "run_backend_only.sh",
            ROOT / "scripts" / "train_dev.sh",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing launcher: {path}")


if __name__ == "__main__":
    unittest.main()
