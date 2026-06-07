import json
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as main

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "test" / "fixtures" / "openapi_contract_snapshot.json"


class OpenApiSnapshotTests(unittest.TestCase):
    def test_openapi_subset_matches_snapshot(self):
        @asynccontextmanager
        async def _noop_lifespan(app):
            yield

        main.app.router.lifespan_context = _noop_lifespan
        main.app.openapi_schema = None

        with TestClient(main.app) as client:
            response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        schemas = payload["components"]["schemas"]
        batch_items = schemas["BatchClassifyRequest"]["properties"]["items"]
        extracted = {
            "info": {
                "title": payload["info"]["title"],
                "version": payload["info"]["version"],
                "summary": payload["info"].get("summary"),
            },
            "tags": [item["name"] for item in payload.get("tags", [])],
            "paths": {
                path: {
                    method: {
                        "summary": details.get("summary"),
                        "tags": details.get("tags", []),
                        **(
                            {
                                "request_body_ref": details["requestBody"]["content"]["application/json"]["schema"][
                                    "$ref"
                                ]
                            }
                            if "requestBody" in details
                            else {}
                        ),
                        "response_ref": (
                            details["responses"]["200"]["content"]["application/json"]["schema"].get("$ref")
                            if details["responses"].get("200", {}).get("content")
                            else None
                        ),
                    }
                    for method, details in operations.items()
                }
                for path, operations in payload["paths"].items()
                if path in {
                    "/health",
                    "/ready",
                    "/diagnostics",
                    "/metrics",
                    "/classify",
                    "/classify/batch",
                    "/review",
                    "/pseudonymize",
                    "/anonymize",
                    "/redact",
                    "/reidentify",
                    "/documents/scrub",
                    "/review/{review_id}",
                    "/review/{review_id}/decision",
                }
            },
            "schemas": {
                "ClassifyRequest": {
                    "required": schemas["ClassifyRequest"].get("required", []),
                    "properties": {
                        name: {
                            "type": schema.get("type", [entry.get("type") for entry in schema.get("anyOf", [])]),
                            **({"maxLength": schema["maxLength"]} if "maxLength" in schema else {}),
                        }
                        for name, schema in schemas["ClassifyRequest"]["properties"].items()
                    },
                },
                "BatchClassifyRequest": {
                    "required": schemas["BatchClassifyRequest"].get("required", []),
                    "properties": {
                        "items": {
                            "type": batch_items["type"],
                            "minItems": batch_items["minItems"],
                            "maxItems": batch_items["maxItems"],
                            "itemsRef": batch_items["items"]["$ref"],
                        }
                    },
                },
                "OffendingSpanResponse": {
                    "required": schemas["OffendingSpanResponse"].get("required", []),
                    "properties": list(schemas["OffendingSpanResponse"]["properties"].keys()),
                },
                "ObservabilityResponse": {
                    "properties": list(schemas["ObservabilityResponse"]["properties"].keys()),
                },
                "MosaicResponse": {
                    "required": schemas["MosaicResponse"].get("required", []),
                    "properties": list(schemas["MosaicResponse"]["properties"].keys()),
                },
                "ReidentifyRequest": {
                    "required": schemas["ReidentifyRequest"].get("required", []),
                    "properties": list(schemas["ReidentifyRequest"]["properties"].keys()),
                },
                "ReidentifyResponse": {
                    "properties": list(schemas["ReidentifyResponse"]["properties"].keys()),
                },
                "DocumentScrubRequest": {
                    "required": schemas["DocumentScrubRequest"].get("required", []),
                    "properties": list(schemas["DocumentScrubRequest"]["properties"].keys()),
                },
                "DocumentScrubResponse": {
                    "properties": list(schemas["DocumentScrubResponse"]["properties"].keys()),
                },
                "ReviewDecisionRequest": {
                    "required": schemas["ReviewDecisionRequest"].get("required", []),
                    "properties": list(schemas["ReviewDecisionRequest"]["properties"].keys()),
                },
                "ReviewDecisionResponse": {
                    "properties": list(schemas["ReviewDecisionResponse"]["properties"].keys()),
                },
                "ReviewSessionStateResponse": {
                    "properties": list(schemas["ReviewSessionStateResponse"]["properties"].keys()),
                },
                "ReviewSessionFindingState": {
                    "required": schemas["ReviewSessionFindingState"].get("required", []),
                    "properties": list(schemas["ReviewSessionFindingState"]["properties"].keys()),
                },
                "AnonymizeResponse": {
                    "properties": list(schemas["AnonymizeResponse"]["properties"].keys()),
                },
                "PseudonymizeResponse": {
                    "properties": list(schemas["PseudonymizeResponse"]["properties"].keys()),
                },
                "RedactResponse": {
                    "properties": list(schemas["RedactResponse"]["properties"].keys()),
                },
                "ReviewResponse": {
                    "properties": list(schemas["ReviewResponse"]["properties"].keys()),
                },
            },
        }

        expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(extracted, expected)


if __name__ == "__main__":
    unittest.main()
