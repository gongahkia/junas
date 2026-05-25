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
                            {"request_body_ref": details["requestBody"]["content"]["application/json"]["schema"]["$ref"]}
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
                    "/anonymize",
                    "/reidentify",
                    "/documents/scrub",
                    "/review/{review_id}",
                    "/review/{review_id}/decision",
                }
            },
            "schemas": {
                "ClassifyRequest": {
                    "required": payload["components"]["schemas"]["ClassifyRequest"].get("required", []),
                    "properties": {
                        name: {
                            "type": schema.get("type", [entry.get("type") for entry in schema.get("anyOf", [])]),
                            **({"maxLength": schema["maxLength"]} if "maxLength" in schema else {}),
                        }
                        for name, schema in payload["components"]["schemas"]["ClassifyRequest"]["properties"].items()
                    },
                },
                "BatchClassifyRequest": {
                    "required": payload["components"]["schemas"]["BatchClassifyRequest"].get("required", []),
                    "properties": {
                        "items": {
                            "type": payload["components"]["schemas"]["BatchClassifyRequest"]["properties"]["items"]["type"],
                            "minItems": payload["components"]["schemas"]["BatchClassifyRequest"]["properties"]["items"]["minItems"],
                            "maxItems": payload["components"]["schemas"]["BatchClassifyRequest"]["properties"]["items"]["maxItems"],
                            "itemsRef": payload["components"]["schemas"]["BatchClassifyRequest"]["properties"]["items"]["items"]["$ref"],
                        }
                    },
                },
                "OffendingSpanResponse": {
                    "required": payload["components"]["schemas"]["OffendingSpanResponse"].get("required", []),
                    "properties": list(payload["components"]["schemas"]["OffendingSpanResponse"]["properties"].keys()),
                },
                "ObservabilityResponse": {
                    "properties": list(payload["components"]["schemas"]["ObservabilityResponse"]["properties"].keys()),
                },
                "MosaicResponse": {
                    "required": payload["components"]["schemas"]["MosaicResponse"].get("required", []),
                    "properties": list(payload["components"]["schemas"]["MosaicResponse"]["properties"].keys()),
                },
                "ReidentifyRequest": {
                    "required": payload["components"]["schemas"]["ReidentifyRequest"].get("required", []),
                    "properties": list(payload["components"]["schemas"]["ReidentifyRequest"]["properties"].keys()),
                },
                "ReidentifyResponse": {
                    "properties": list(payload["components"]["schemas"]["ReidentifyResponse"]["properties"].keys()),
                },
                "DocumentScrubRequest": {
                    "required": payload["components"]["schemas"]["DocumentScrubRequest"].get("required", []),
                    "properties": list(payload["components"]["schemas"]["DocumentScrubRequest"]["properties"].keys()),
                },
                "DocumentScrubResponse": {
                    "properties": list(payload["components"]["schemas"]["DocumentScrubResponse"]["properties"].keys()),
                },
                "ReviewDecisionRequest": {
                    "required": payload["components"]["schemas"]["ReviewDecisionRequest"].get("required", []),
                    "properties": list(payload["components"]["schemas"]["ReviewDecisionRequest"]["properties"].keys()),
                },
                "ReviewDecisionResponse": {
                    "properties": list(payload["components"]["schemas"]["ReviewDecisionResponse"]["properties"].keys()),
                },
                "ReviewSessionStateResponse": {
                    "properties": list(payload["components"]["schemas"]["ReviewSessionStateResponse"]["properties"].keys()),
                },
                "ReviewSessionFindingState": {
                    "required": payload["components"]["schemas"]["ReviewSessionFindingState"].get("required", []),
                    "properties": list(payload["components"]["schemas"]["ReviewSessionFindingState"]["properties"].keys()),
                },
                "AnonymizeResponse": {
                    "properties": list(payload["components"]["schemas"]["AnonymizeResponse"]["properties"].keys()),
                },
                "ReviewResponse": {
                    "properties": list(payload["components"]["schemas"]["ReviewResponse"]["properties"].keys()),
                },
            },
        }

        expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(extracted, expected)


if __name__ == "__main__":
    unittest.main()
