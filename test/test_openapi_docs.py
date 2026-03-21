import unittest
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

import backend.main as main


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


class OpenApiDocsTests(unittest.TestCase):
    def test_openapi_metadata_matches_current_api_surface(self):
        with TestClient(main.app) as client:
            response = client.get("/openapi.json")
            self.assertEqual(response.status_code, 200)
            payload = response.json()

        self.assertEqual(payload["info"]["title"], "Noupe MNPI Classifier")
        self.assertIn("backend-only", payload["info"]["description"])

        classify_operation = payload["paths"]["/classify"]["post"]
        batch_operation = payload["paths"]["/classify/batch"]["post"]

        self.assertEqual(classify_operation["summary"], "Classify one document")
        self.assertEqual(batch_operation["summary"], "Classify multiple documents")
        self.assertIn("include_offending_spans", classify_operation["description"])

        schemas = payload["components"]["schemas"]
        classify_request = schemas["ClassifyRequest"]
        offending_span = schemas["OffendingSpanResponse"]

        self.assertIn("include_offending_spans", classify_request["properties"])
        self.assertIn("approximate classifier-window spans", classify_request["properties"]["include_offending_spans"]["description"])
        self.assertIn("context_before", offending_span["properties"])
        self.assertIn("window_token_count", offending_span["properties"])


if __name__ == "__main__":
    unittest.main()
