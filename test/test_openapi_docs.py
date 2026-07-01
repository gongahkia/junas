import ast
import json
import os
import subprocess
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import junas.backend.main as main
import junas.backend.schemas as schema_models
from junas.backend.schemas import ReviewRequest

ROOT = Path(__file__).resolve().parent.parent
POLICY_EXAMPLE_SNAPSHOT = ROOT / "test" / "fixtures" / "openapi_policy_examples_snapshot.json"
DOCS_API = ROOT / "docs" / "api"
POLICY_EXAMPLE_NAMES = (
    "POST /review - Outlook Smart Alerts email send",
    "POST /review - Browser GenAI prompt submit",
    "POST /hold-until-public",
    "POST /cite-public-source",
)
EXPECTED_POSTMAN_STATUSES = {
    "POST /anonymize": {200},
    "POST /cite-public-source": {409},
    "POST /classify": {200},
    "POST /classify/batch": {200},
    "GET /demo": {404},
    "POST /demo/review": {404},
    "GET /diagnostics": {200},
    "POST /documents/scrub": {422},
    "GET /health": {200},
    "POST /hold-until-public": {200},
    "POST /local/pairing/approve": {409},
    "POST /local/pairing/claim": {409},
    "POST /local/pairing/start": {409},
    "GET /local/pairing/status": {200},
    "GET /metrics": {200, 503},
    "POST /pseudonymize": {200},
    "GET /ready": {200},
    "POST /redact": {200},
    "POST /redact-pii": {200},
    "POST /reidentify": {200},
    "POST /request-approval": {409},
    "POST /review - Outlook Smart Alerts email send": {200},
    "POST /review - Browser GenAI prompt submit": {200},
    "POST /review - DMS document upload": {200},
    "POST /review - Desktop watcher file review": {200},
    "POST /review - Direct API review": {200},
    "POST /safe-rewrite": {200},
}


def _policy_example_subset(payload: dict) -> dict:
    policy_decision = dict(payload["policy_decision"])
    policy_decision.pop("review_id", None)
    return {
        "send_allowed": payload.get("send_allowed"),
        "action_catalog": payload.get("action_catalog"),
        "policy_decision": policy_decision,
    }


def _schema_ref(operation: dict, direction: str) -> str | None:
    if direction == "request":
        schema = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
    else:
        schema = (
            operation.get("responses", {})
            .get("200", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
        )
    ref = schema.get("$ref") if isinstance(schema, dict) else None
    return ref.rsplit("/", 1)[-1] if isinstance(ref, str) else None


def _validate_schema_ref(ref: str, payload: dict) -> None:
    getattr(schema_models, ref).model_validate(payload)


def _postman_path(item: dict) -> str:
    return item["request"]["url"]["raw"].replace("{{baseUrl}}", "")


def _postman_headers(item: dict) -> dict[str, str]:
    replacements = {
        "{{junasApiKey}}": "dev-secret",
        "{{junasLocalToken}}": "dev-local-token",
    }
    return {
        header["key"]: replacements.get(header["value"], header["value"])
        for header in item["request"].get("header", [])
    }


def _postman_body(item: dict) -> dict | None:
    raw = item["request"].get("body", {}).get("raw")
    return json.loads(raw) if raw else None


def _markdown_code_blocks(path: Path) -> list[tuple[str, str]]:
    blocks = []
    lang = ""
    lines: list[str] = []
    in_block = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            if in_block:
                blocks.append((lang, "\n".join(lines) + "\n"))
                lines = []
                in_block = False
                continue
            lang = line.removeprefix("```").strip()
            in_block = True
            continue
        if in_block:
            lines.append(line)
    return blocks


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

        self.assertEqual(payload["info"]["title"], "Junas Document Safety API")
        self.assertIn("pre-send safety engine", payload["info"]["description"])

        cite_public_source_operation = payload["paths"]["/cite-public-source"]["post"]
        classify_operation = payload["paths"]["/classify"]["post"]
        batch_operation = payload["paths"]["/classify/batch"]["post"]
        hold_until_public_operation = payload["paths"]["/hold-until-public"]["post"]
        review_operation = payload["paths"]["/review"]["post"]
        pseudonymize_operation = payload["paths"]["/pseudonymize"]["post"]
        anonymize_operation = payload["paths"]["/anonymize"]["post"]
        redact_operation = payload["paths"]["/redact"]["post"]
        redact_pii_operation = payload["paths"]["/redact-pii"]["post"]
        request_approval_operation = payload["paths"]["/request-approval"]["post"]
        safe_rewrite_operation = payload["paths"]["/safe-rewrite"]["post"]
        scrub_operation = payload["paths"]["/documents/scrub"]["post"]

        self.assertEqual(cite_public_source_operation["summary"], "Cite audit-grade public evidence")
        self.assertEqual(classify_operation["summary"], "Classify one document")
        self.assertEqual(batch_operation["summary"], "Classify multiple documents")
        self.assertEqual(hold_until_public_operation["summary"], "Hold high-risk MNPI until public")
        self.assertEqual(review_operation["summary"], "Review a document before sending")
        self.assertEqual(pseudonymize_operation["summary"], "Pseudonymize a document before sending")
        self.assertEqual(anonymize_operation["summary"], "Anonymize a document irreversibly")
        self.assertEqual(redact_operation["summary"], "Redact a document with opaque markers")
        self.assertEqual(redact_pii_operation["summary"], "Redact PII only")
        self.assertEqual(request_approval_operation["summary"], "Request reviewer approval")
        self.assertEqual(safe_rewrite_operation["summary"], "Safely rewrite a document deterministically")
        self.assertEqual(scrub_operation["summary"], "Scrub document metadata")
        self.assertIn("privacy-ledger entry", cite_public_source_operation["description"])
        self.assertIn("deterministic review engine", classify_operation["description"])
        self.assertIn("audit-ready rationale", hold_until_public_operation["description"])
        self.assertIn("strictest-wins", review_operation["description"])
        self.assertIn("deterministic reversible placeholders", pseudonymize_operation["description"])
        self.assertIn("without returning or persisting a mapping", anonymize_operation["description"])
        self.assertIn("opaque redaction markers", redact_operation["description"])
        self.assertIn("MNPI passages remain visible", redact_pii_operation["description"])
        self.assertIn("reviewer roles required", request_approval_operation["description"])
        self.assertIn("does not call an LLM", safe_rewrite_operation["description"])

        schemas = payload["components"]["schemas"]
        anonymize_request = schemas["AnonymizeRequest"]
        anonymize_response = schemas["AnonymizeResponse"]
        cite_public_source_request = schemas["CitePublicSourceRequest"]
        cite_public_source_response = schemas["CitePublicSourceResponse"]
        pseudonymize_request = schemas["PseudonymizeRequest"]
        pseudonymize_response = schemas["PseudonymizeResponse"]
        redact_response = schemas["RedactResponse"]
        hold_until_public_request = schemas["HoldUntilPublicRequest"]
        hold_until_public_response = schemas["HoldUntilPublicResponse"]
        hold_reason_response = schemas["HoldUntilPublicReasonResponse"]
        public_source_citation_response = schemas["PublicSourceCitationResponse"]
        redact_pii_request = schemas["RedactPiiRequest"]
        redact_pii_response = schemas["RedactPiiResponse"]
        request_approval_request = schemas["RequestApprovalRequest"]
        request_approval_response = schemas["RequestApprovalResponse"]
        safe_rewrite_request = schemas["SafeRewriteRequest"]
        safe_rewrite_response = schemas["SafeRewriteResponse"]
        classify_request = schemas["ClassifyRequest"]
        review_request = schemas["ReviewRequest"]
        review_response = schemas["ReviewResponse"]
        scrub_request = schemas["DocumentScrubRequest"]
        scrub_response = schemas["DocumentScrubResponse"]

        self.assertIn("include_offending_spans", classify_request["properties"])
        self.assertIn("document_base64", review_request["properties"])
        self.assertIn("degraded_policy", review_request["properties"])
        self.assertIn("include_mnpi_scalars", anonymize_request["properties"])
        self.assertIn("persist_mapping", pseudonymize_request["properties"])
        self.assertIn("pii_score", review_response["properties"])
        self.assertIn("mnpi_score", review_response["properties"])
        self.assertIn("send_allowed", review_response["properties"])
        self.assertIn("review_expires_at", review_response["properties"])
        self.assertIn("document_base64", scrub_request["properties"])
        self.assertIn("metadata_findings", scrub_response["properties"])
        self.assertIn("anonymized_text", anonymize_response["properties"])
        self.assertIn("anonymization_mode", anonymize_response["properties"])
        self.assertIn("replacements", anonymize_response["properties"])
        self.assertNotIn("mapping", anonymize_response["properties"])
        self.assertIn("review_profile", cite_public_source_request["properties"])
        self.assertIn("citations", cite_public_source_response["properties"])
        self.assertIn("privacy_ledger_entry", public_source_citation_response["properties"])
        self.assertIn("pseudonymized_text", pseudonymize_response["properties"])
        self.assertIn("mapping", pseudonymize_response["properties"])
        self.assertIn("redacted_text", redact_response["properties"])
        self.assertIn("redactions", redact_response["properties"])
        self.assertIn("allowed_actions", hold_until_public_request["properties"])
        self.assertIn("hold_reasons", hold_until_public_response["properties"])
        self.assertIn("audit_rationale", hold_reason_response["properties"])
        self.assertIn("allowed_actions", redact_pii_request["properties"])
        self.assertIn("rewritten_text", redact_pii_response["properties"])
        self.assertIn("skipped_findings", redact_pii_response["properties"])
        self.assertIn("review_id", request_approval_request["properties"])
        self.assertIn("required_reviewer_roles", request_approval_response["properties"])
        self.assertIn("required_policy_actor_roles", request_approval_response["properties"])
        self.assertIn("allowed_actions", safe_rewrite_request["properties"])
        self.assertIn("rewritten_text", safe_rewrite_response["properties"])
        self.assertIn("skipped_findings", safe_rewrite_response["properties"])
        self.assertIn("policy_exception", schemas["ReviewDecisionRequest"]["properties"]["action"]["description"])
        include_spans_description = classify_request["properties"]["include_offending_spans"]["description"]
        self.assertIn("Deprecated compatibility flag", include_spans_description)
        classify_response = schemas["ClassifyResponse"]
        self.assertIn("findings", classify_response["properties"])
        self.assertIn("Deprecated compatibility field", classify_response["properties"]["mosaic"]["description"])

    def test_review_openapi_examples_cover_adapter_surfaces(self):
        main.app.openapi_schema = None
        with TestClient(main.app) as client:
            response = client.get("/openapi.json")
            self.assertEqual(response.status_code, 200)
        payload = response.json()

        examples = payload["paths"]["/review"]["post"]["requestBody"]["content"]["application/json"]["examples"]
        artifact = json.loads((ROOT / "docs" / "api" / "adapter_surface_review_examples.json").read_text())
        expected_surfaces = {"outlook", "browser_genai", "dms", "desktop", "api"}
        self.assertEqual({example["value"]["surface"] for example in examples.values()}, expected_surfaces)
        self.assertEqual({entry["value"]["surface"] for entry in artifact["examples"].values()}, expected_surfaces)
        for key in (
            "outlook_email_send",
            "browser_genai_prompt_submit",
            "dms_document_upload",
            "desktop_watch",
            "api_review",
        ):
            self.assertIn(key, examples)
            self.assertIn(key, artifact["examples"])

    def test_adapter_surface_doc_examples_validate_as_review_requests(self):
        main.app.openapi_schema = None
        with TestClient(main.app) as client:
            response = client.get("/openapi.json")
            self.assertEqual(response.status_code, 200)
        payload = response.json()

        openapi_examples = payload["paths"]["/review"]["post"]["requestBody"]["content"]["application/json"][
            "examples"
        ]
        artifact = json.loads((ROOT / "docs" / "api" / "adapter_surface_review_examples.json").read_text())
        doc_examples = artifact["examples"]
        self.assertEqual({key: example["value"] for key, example in openapi_examples.items()}, {
            key: example["value"] for key, example in doc_examples.items()
        })

        for key, example in doc_examples.items():
            with self.subTest(example=key):
                request = ReviewRequest.model_validate(example["value"])
                self.assertEqual(request.surface, example["value"]["surface"])
                self.assertTrue(request.text or request.document_base64)

    def test_generated_policy_examples_match_snapshot(self):
        collection = json.loads((ROOT / "docs" / "api" / "junas.postman_collection.json").read_text())
        postman_examples = {}
        for item in collection["item"]:
            if item["name"] not in POLICY_EXAMPLE_NAMES:
                continue
            postman_examples[item["name"]] = _policy_example_subset(json.loads(item["response"][0]["body"]))
        hero = _policy_example_subset(json.loads((ROOT / "docs" / "api" / "review_hero_response.json").read_text()))
        extracted = {
            "postman_examples": postman_examples,
            "review_hero_response": hero,
            "schema": "junas.openapi_policy_examples_snapshot.v1",
        }
        expected = json.loads(POLICY_EXAMPLE_SNAPSHOT.read_text())
        self.assertEqual(set(postman_examples), set(POLICY_EXAMPLE_NAMES))
        self.assertEqual(extracted, expected)

    def test_docs_api_machine_examples_execute_or_validate(self):
        main.app.openapi_schema = None
        with patch.dict(os.environ, {"JUNAS_API_KEY": ""}, clear=False):
            with TestClient(main.app) as client:
                response = client.get("/openapi.json")
                self.assertEqual(response.status_code, 200)
                openapi = response.json()

                collection = json.loads((DOCS_API / "junas.postman_collection.json").read_text())
                self.assertEqual(
                    set(EXPECTED_POSTMAN_STATUSES) | {"GET /review/{review_id}", "POST /review/{review_id}/decision"},
                    {item["name"] for item in collection["item"]},
                )
                for item in collection["item"]:
                    with self.subTest(postman_item=item["name"]):
                        path = _postman_path(item)
                        method = item["request"]["method"].lower()
                        operation = openapi["paths"][path][method]
                        covered = False

                        request_ref = _schema_ref(operation, "request")
                        body = _postman_body(item)
                        if body is not None and request_ref is not None:
                            _validate_schema_ref(request_ref, body)
                            covered = True

                        response_ref = _schema_ref(operation, "response")
                        for example_response in item.get("response", []):
                            raw_response = example_response.get("body")
                            if raw_response and response_ref is not None:
                                _validate_schema_ref(response_ref, json.loads(raw_response))
                                covered = True

                        if item["name"] in EXPECTED_POSTMAN_STATUSES:
                            response = client.request(
                                item["request"]["method"],
                                path,
                                headers=_postman_headers(item),
                                json=body,
                            )
                            self.assertIn(response.status_code, EXPECTED_POSTMAN_STATUSES[item["name"]])
                            covered = True

                        self.assertTrue(covered)

        ReviewRequest.model_validate(json.loads((DOCS_API / "review_hero_request.json").read_text()))
        schema_models.ReviewResponse.model_validate(json.loads((DOCS_API / "review_hero_response.json").read_text()))
        adapter_examples = json.loads((DOCS_API / "adapter_surface_review_examples.json").read_text())["examples"]
        for key, example in adapter_examples.items():
            with self.subTest(adapter_surface_example=key):
                ReviewRequest.model_validate(example["value"])

    def test_docs_api_text_examples_are_syntax_checked(self):
        curl_syntax = subprocess.run(
            ["bash", "-n", str(DOCS_API / "curl_snippets.sh")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(curl_syntax.returncode, 0, curl_syntax.stderr)

        for path in DOCS_API.glob("*.md"):
            for lang, block in _markdown_code_blocks(path):
                with self.subTest(path=path.name, lang=lang):
                    if lang == "python":
                        ast.parse(block)
                    elif lang in {"sh", "bash"}:
                        result = subprocess.run(["bash", "-n"], input=block, check=False, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
