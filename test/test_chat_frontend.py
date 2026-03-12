import unittest
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

import backend.main as main


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


class ChatFrontendRouteTests(unittest.TestCase):
    def test_chat_index_is_served(self):
        with TestClient(main.app) as client:
            response = client.get("/chat/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/html", response.headers.get("content-type", ""))
            self.assertIn("Noupe Chat Guard", response.text)

    def test_chat_assets_are_served(self):
        with TestClient(main.app) as client:
            response = client.get("/chat/style.css")
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/css", response.headers.get("content-type", ""))
            self.assertIn("--noupe-red", response.text)

    def test_health_route_still_works(self):
        with TestClient(main.app) as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "ok")


if __name__ == "__main__":
    unittest.main()
