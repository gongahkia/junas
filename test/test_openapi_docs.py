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
        main.app.openapi_schema = None
        with TestClient(main.app) as client:
            response = client.get("/openapi.json")
            self.assertEqual(response.status_code, 200)
            payload = response.json()

        self.assertEqual(payload["info"]["title"], "Kaypoh Document Safety API")
        self.assertIn("pre-send safety engine", payload["info"]["description"])

        classify_operation = payload["paths"]["/classify"]["post"]
        batch_operation = payload["paths"]["/classify/batch"]["post"]
        review_operation = payload["paths"]["/review"]["post"]
        pseudonymize_operation = payload["paths"]["/pseudonymize"]["post"]
        anonymize_operation = payload["paths"]["/anonymize"]["post"]
        redact_operation = payload["paths"]["/redact"]["post"]
        scrub_operation = payload["paths"]["/documents/scrub"]["post"]

        self.assertEqual(classify_operation["summary"], "Classify one document")
        self.assertEqual(batch_operation["summary"], "Classify multiple documents")
        self.assertEqual(review_operation["summary"], "Review a document before sending")
        self.assertEqual(pseudonymize_operation["summary"], "Pseudonymize a document before sending")
        self.assertEqual(anonymize_operation["summary"], "Anonymize a document irreversibly")
        self.assertEqual(redact_operation["summary"], "Redact a document with opaque markers")
        self.assertEqual(scrub_operation["summary"], "Scrub document metadata")
        self.assertIn("deterministic review engine", classify_operation["description"])
        self.assertIn("strictest-wins", review_operation["description"])
        self.assertIn("deterministic reversible placeholders", pseudonymize_operation["description"])
        self.assertIn("without returning or persisting a mapping", anonymize_operation["description"])
        self.assertIn("opaque redaction markers", redact_operation["description"])

        schemas = payload["components"]["schemas"]
        anonymize_request = schemas["AnonymizeRequest"]
        anonymize_response = schemas["AnonymizeResponse"]
        pseudonymize_request = schemas["PseudonymizeRequest"]
        pseudonymize_response = schemas["PseudonymizeResponse"]
        redact_response = schemas["RedactResponse"]
        classify_request = schemas["ClassifyRequest"]
        review_request = schemas["ReviewRequest"]
        review_response = schemas["ReviewResponse"]
        scrub_request = schemas["DocumentScrubRequest"]
        scrub_response = schemas["DocumentScrubResponse"]

        self.assertIn("include_offending_spans", classify_request["properties"])
        self.assertIn("document_base64", review_request["properties"])
        self.assertIn("include_mnpi_scalars", anonymize_request["properties"])
        self.assertIn("persist_mapping", pseudonymize_request["properties"])
        self.assertIn("pii_score", review_response["properties"])
        self.assertIn("mnpi_score", review_response["properties"])
        self.assertIn("document_base64", scrub_request["properties"])
        self.assertIn("metadata_findings", scrub_response["properties"])
        self.assertIn("anonymized_text", anonymize_response["properties"])
        self.assertIn("anonymization_mode", anonymize_response["properties"])
        self.assertIn("replacements", anonymize_response["properties"])
        self.assertNotIn("mapping", anonymize_response["properties"])
        self.assertIn("pseudonymized_text", pseudonymize_response["properties"])
        self.assertIn("mapping", pseudonymize_response["properties"])
        self.assertIn("redacted_text", redact_response["properties"])
        self.assertIn("redactions", redact_response["properties"])
        include_spans_description = classify_request["properties"]["include_offending_spans"]["description"]
        self.assertIn("Deprecated compatibility flag", include_spans_description)
        classify_response = schemas["ClassifyResponse"]
        self.assertIn("findings", classify_response["properties"])
        self.assertIn("Deprecated compatibility field", classify_response["properties"]["mosaic"]["description"])


if __name__ == "__main__":
    unittest.main()
