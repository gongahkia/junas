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

        self.assertEqual(payload["info"]["title"], "Kaypoh MNPI Classifier")
        self.assertIn("backend-only", payload["info"]["description"])

        classify_operation = payload["paths"]["/classify"]["post"]
        batch_operation = payload["paths"]["/classify/batch"]["post"]
        review_operation = payload["paths"]["/review"]["post"]

        self.assertEqual(classify_operation["summary"], "Classify one document")
        self.assertEqual(batch_operation["summary"], "Classify multiple documents")
        self.assertEqual(review_operation["summary"], "Review a document before sending")
        self.assertIn("include_offending_spans", classify_operation["description"])
        self.assertIn("strictest-wins", review_operation["description"])

        schemas = payload["components"]["schemas"]
        classify_request = schemas["ClassifyRequest"]
        review_request = schemas["ReviewRequest"]
        review_response = schemas["ReviewResponse"]
        offending_span = schemas["OffendingSpanResponse"]
        mosaic_response = schemas["MosaicResponse"]

        self.assertIn("include_offending_spans", classify_request["properties"])
        self.assertIn("document_base64", review_request["properties"])
        self.assertIn("pii_score", review_response["properties"])
        self.assertIn("mnpi_score", review_response["properties"])
        self.assertIn("approximate classifier-window spans", classify_request["properties"]["include_offending_spans"]["description"])
        self.assertIn("context_before", offending_span["properties"])
        self.assertIn("window_token_count", offending_span["properties"])
        self.assertEqual(
            list(mosaic_response["properties"].keys()),
            [
                "entity_id",
                "escalated",
                "recent_event_count",
                "unique_fragment_count",
                "window_hours",
                "threshold",
                "escalation_reason",
                "matched_event_ids",
            ],
        )
        self.assertEqual(
            mosaic_response["required"],
            [
                "entity_id",
                "escalated",
                "recent_event_count",
                "unique_fragment_count",
                "window_hours",
                "threshold",
            ],
        )


if __name__ == "__main__":
    unittest.main()
