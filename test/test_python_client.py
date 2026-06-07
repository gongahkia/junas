import asyncio
import json
import sys
import unittest
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kaypoh import AsyncKaypohClient, Classification, KaypohAPIError, KaypohClient, async_classify_text


def build_classify_payload(*, request_id: str, classification: str = "SAFE") -> dict:
    return {
        "request_id": request_id,
        "classification": classification,
        "lexicon": {
            "flagged": False,
            "high_risk_short_circuit": False,
            "total_score": 0.0,
            "score_threshold": 10.0,
            "score_threshold_exceeded": False,
            "hits": [],
            "restricted_entities": [],
        },
        "model1": {
            "label": "safe",
            "confidence": 0.91,
            "risk_score": 0.09,
        },
        "model2": None,
        "embedding": None,
        "clustering": None,
        "mosaic": None,
        "regression": None,
        "observability": {
            "degraded": False,
            "cache_status": "disabled",
            "active_pipeline": ["lexicon", "model1"],
            "executed_layers": ["lexicon", "model1"],
            "skipped_layers": [],
            "layer_errors": [],
        },
        "offending_spans": [],
        "timings_ms": {
            "lexicon": 0.8,
            "model1": 1.2,
            "total": 2.0,
        },
    }


def build_review_payload(*, request_id: str, classification: str = "LOW_RISK") -> dict:
    return {
        "request_id": request_id,
        "overall_risk": classification,
        "classification": classification,
        "document_score": 58.0,
        "pii_score": 58.0,
        "mnpi_score": 0.0,
        "source_jurisdiction": "SG",
        "destination_jurisdiction": "US",
        "jurisdictions_applied": ["SG", "US"],
        "jurisdiction_policy": "strictest_wins",
        "document_type": "generic",
        "review_profile": "strict",
        "document": {
            "filename": "inline.txt",
            "mime_type": "text/plain",
            "extraction_method": "inline_text",
            "page_count": None,
            "char_count": 48,
        },
        "findings": [
            {
                "id": "pii:email_address:10:28:0",
                "category": "PII",
                "rule": "email_address",
                "jurisdiction": "SG",
                "severity": "medium",
                "score": 55.0,
                "matched_text": "jane@example.com",
                "start_char": 10,
                "end_char": 26,
                "reason": "Email address can identify an individual",
                "legal_basis": "SG_PDPA_PERSONAL_DATA",
            }
        ],
        "suggestions": [
            {
                "id": "suggestion:0",
                "finding_id": "pii:email_address:10:28:0",
                "action": "redact",
                "replacement_text": "[REDACTED PERSONAL DATA]",
                "rationale": "Remove or mask personal data.",
            }
        ],
        "public_evidence": None,
        "llm_adjudication": None,
        "privacy_ledger": [],
        "timings_ms": {"extract": 0.1, "review": 0.4, "total": 0.5},
    }


def build_anonymize_payload(*, request_id: str, classification: str = "LOW_RISK") -> dict:
    payload = build_review_payload(request_id=request_id, classification=classification)
    payload.update(
        {
            "privacy_operation": "anonymize",
            "anonymization_mode": "placeholder_only",
            "anonymized_text": "Send [EMAIL_1]",
            "document_hash": "a" * 64,
            "mapping_persisted": False,
            "replacements": [
                {
                    "finding_id": "pii:email_address:10:28:0",
                    "placeholder": "[EMAIL_1]",
                    "entity_type": "EMAIL",
                    "start_char": 10,
                    "end_char": 26,
                }
            ],
        }
    )
    payload["timings_ms"] = {"extract": 0.1, "review": 0.4, "anonymize": 0.1, "total": 0.6}
    return payload


def build_pseudonymize_payload(*, request_id: str, classification: str = "LOW_RISK") -> dict:
    payload = build_review_payload(request_id=request_id, classification=classification)
    payload.update(
        {
            "privacy_operation": "pseudonymize",
            "pseudonymized_text": "Send [EMAIL_1]",
            "anonymized_text": "Send [EMAIL_1]",
            "document_hash": "b" * 64,
            "mapping_persisted": False,
            "mapping": [
                {
                    "placeholder": "[EMAIL_1]",
                    "entity_type": "EMAIL",
                    "original_text": "jane@example.com",
                    "occurrence_count": 1,
                }
            ],
            "replacements": [
                {
                    "finding_id": "pii:email_address:10:28:0",
                    "placeholder": "[EMAIL_1]",
                    "entity_type": "EMAIL",
                    "original_text": "jane@example.com",
                    "start_char": 10,
                    "end_char": 26,
                }
            ],
        }
    )
    payload["timings_ms"] = {"extract": 0.1, "review": 0.4, "pseudonymize": 0.1, "total": 0.6}
    return payload


def build_redact_payload(*, request_id: str, classification: str = "LOW_RISK") -> dict:
    payload = build_review_payload(request_id=request_id, classification=classification)
    for finding in payload["findings"]:
        finding.pop("matched_text", None)
    payload.update(
        {
            "suggestions": [],
            "privacy_operation": "redact",
            "redaction_style": "opaque_text_marker",
            "redacted_text": "Send [REDACTED_1]",
            "document_hash": "c" * 64,
            "mapping_persisted": False,
            "redactions": [
                {
                    "finding_id": "pii:email_address:10:28:0",
                    "marker": "[REDACTED_1]",
                    "start_char": 10,
                    "end_char": 26,
                }
            ],
        }
    )
    payload["timings_ms"] = {"extract": 0.1, "review": 0.4, "redact": 0.1, "total": 0.6}
    return payload


class KaypohClientTests(unittest.TestCase):
    def test_classify_sends_expected_payload_and_api_key(self):
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["api_key"] = request.headers.get("X-API-Key")
            observed["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=build_classify_payload(request_id="req-1", classification="LOW_RISK"))

        transport = httpx.MockTransport(handler)

        with KaypohClient("http://kaypoh.test", api_key="dev-secret", transport=transport) as client:
            result = client.classify(
                text="Acme Corp is acquiring GlobalTech next quarter.",
                entity_id="acme-corp",
                include_offending_spans=True,
            )

        self.assertEqual(result.classification, Classification.LOW_RISK)
        self.assertEqual(result.request_id, "req-1")
        self.assertEqual(observed["method"], "POST")
        self.assertEqual(observed["path"], "/classify")
        self.assertEqual(observed["api_key"], "dev-secret")
        self.assertEqual(
            observed["body"],
            {
                "text": "Acme Corp is acquiring GlobalTech next quarter.",
                "entity_id": "acme-corp",
                "debug": False,
                "include_offending_spans": True,
            },
        )

    def test_review_sends_expected_payload_and_returns_typed_response(self):
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=build_review_payload(request_id="review-1"))

        transport = httpx.MockTransport(handler)

        with KaypohClient("http://kaypoh.test", transport=transport) as client:
            result = client.review(
                text="Send to jane@example.com",
                source_jurisdiction="SG",
                destination_jurisdiction="US",
                document_type="email",
                include_suggestions=True,
            )

        self.assertEqual(result.classification, Classification.LOW_RISK)
        self.assertEqual(result.request_id, "review-1")
        self.assertEqual(observed["method"], "POST")
        self.assertEqual(observed["path"], "/review")
        self.assertEqual(
            observed["body"],
            {
                "text": "Send to jane@example.com",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "US",
                "document_type": "email",
                "review_profile": "strict",
                "include_suggestions": True,
            },
        )

    def test_anonymize_sends_expected_payload_and_returns_typed_response(self):
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=build_anonymize_payload(request_id="anon-1"))

        transport = httpx.MockTransport(handler)

        with KaypohClient("http://kaypoh.test", transport=transport) as client:
            result = client.anonymize(
                text="Send to jane@example.com",
                source_jurisdiction="SG",
                destination_jurisdiction="US",
                document_type="email",
                include_mnpi_scalars=False,
            )

        self.assertEqual(result.classification, Classification.LOW_RISK)
        self.assertEqual(result.request_id, "anon-1")
        self.assertEqual(result.anonymized_text, "Send [EMAIL_1]")
        self.assertEqual(result.privacy_operation, "anonymize")
        self.assertEqual(result.anonymization_mode, "placeholder_only")
        self.assertFalse(hasattr(result, "mapping"))
        self.assertFalse(hasattr(result.replacements[0], "original_text"))
        self.assertEqual(observed["method"], "POST")
        self.assertEqual(observed["path"], "/anonymize")
        self.assertEqual(
            observed["body"],
            {
                "text": "Send to jane@example.com",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "US",
                "document_type": "email",
                "review_profile": "strict",
                "include_suggestions": True,
                "include_mnpi_scalars": False,
            },
        )

    def test_pseudonymize_sends_expected_payload_and_returns_mapping(self):
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=build_pseudonymize_payload(request_id="pseudo-1"))

        transport = httpx.MockTransport(handler)

        with KaypohClient("http://kaypoh.test", transport=transport) as client:
            result = client.pseudonymize(
                text="Send to jane@example.com",
                source_jurisdiction="SG",
                destination_jurisdiction="US",
                document_type="email",
                include_mnpi_scalars=False,
                persist_mapping=False,
            )

        self.assertEqual(result.request_id, "pseudo-1")
        self.assertEqual(result.privacy_operation, "pseudonymize")
        self.assertEqual(result.pseudonymized_text, "Send [EMAIL_1]")
        self.assertEqual(result.mapping[0].original_text, "jane@example.com")
        self.assertEqual(observed["path"], "/pseudonymize")
        self.assertEqual(observed["body"]["persist_mapping"], False)

    def test_redact_sends_expected_payload_and_returns_opaque_markers(self):
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=build_redact_payload(request_id="redact-1"))

        transport = httpx.MockTransport(handler)

        with KaypohClient("http://kaypoh.test", transport=transport) as client:
            result = client.redact(
                text="Send to jane@example.com",
                source_jurisdiction="SG",
                destination_jurisdiction="US",
                document_type="email",
            )

        self.assertEqual(result.request_id, "redact-1")
        self.assertEqual(result.redaction_style, "opaque_text_marker")
        self.assertEqual(result.redactions[0].marker, "[REDACTED_1]")
        self.assertFalse(hasattr(result.findings[0], "matched_text"))
        self.assertEqual(observed["path"], "/redact")

    def test_classify_batch_and_runtime_methods_return_typed_models(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/ready":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "ready": True,
                        "pipeline": ["lexicon", "model1"],
                        "missing_required_layers": [],
                        "warming_required_layers": [],
                        "reasons": [],
                    },
                )
            if request.url.path == "/diagnostics":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "pipeline": ["lexicon", "model1"],
                        "loaded_layers": ["lexicon", "model1"],
                        "lazy_layers": [],
                        "warming_required_layers": [],
                        "load_errors": [],
                        "startup_timings_ms": {"lexicon": 1.1, "model1": 2.2, "total": 3.3},
                        "metrics_mode": "singleprocess",
                        "dependency_status": {},
                        "runtime_layer_errors": {},
                    },
                )
            if request.url.path == "/classify/batch":
                body = json.loads(request.content.decode("utf-8"))
                self.assertEqual(len(body["items"]), 2)
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            build_classify_payload(request_id="req-2"),
                            build_classify_payload(request_id="req-3"),
                        ]
                    },
                )
            raise AssertionError(f"unexpected path: {request.url.path}")

        transport = httpx.MockTransport(handler)

        with KaypohClient("http://kaypoh.test", transport=transport) as client:
            ready = client.ready()
            diagnostics = client.diagnostics()
            results = client.classify_many(
                [
                    {"text": "Quarterly board memo"},
                    {"text": "Public investor presentation"},
                ]
            )

        self.assertTrue(ready.ready)
        self.assertEqual(diagnostics.loaded_layers, ["lexicon", "model1"])
        self.assertEqual([result.request_id for result in results], ["req-2", "req-3"])

    def test_http_errors_raise_kaypoh_api_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "invalid or missing API key"})

        transport = httpx.MockTransport(handler)

        with self.assertRaises(KaypohAPIError) as ctx:
            with KaypohClient("http://kaypoh.test", api_key="wrong-key", transport=transport) as client:
                client.classify(text="Public update")

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "invalid or missing API key")

    def test_async_client_uses_same_backend_contract(self):
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=build_classify_payload(request_id="req-async", classification="HIGH_RISK"))

        async def scenario() -> None:
            transport = httpx.MockTransport(handler)
            async with AsyncKaypohClient("http://kaypoh.test", transport=transport) as client:
                result = await client.classify(
                    text="Restricted board draft",
                    entity_id="acme-board",
                    include_offending_spans=True,
                )
                self.assertEqual(result.classification, Classification.HIGH_RISK)
                self.assertEqual(result.request_id, "req-async")

        asyncio.run(scenario())

        self.assertEqual(observed["method"], "POST")
        self.assertEqual(observed["path"], "/classify")
        self.assertEqual(
            observed["body"],
            {
                "text": "Restricted board draft",
                "entity_id": "acme-board",
                "debug": False,
                "include_offending_spans": True,
            },
        )

    def test_async_review_uses_same_backend_contract(self):
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=build_review_payload(request_id="review-async", classification="HIGH_RISK"))

        async def scenario() -> None:
            transport = httpx.MockTransport(handler)
            async with AsyncKaypohClient("http://kaypoh.test", transport=transport) as client:
                result = await client.review(
                    document_base64="U2VuZCB0byBqYW5lQGV4YW1wbGUuY29t",
                    document_filename="memo.txt",
                    document_mime_type="text/plain",
                    source_jurisdiction="SG",
                    destination_jurisdiction="SEA",
                )
                self.assertEqual(result.classification, Classification.HIGH_RISK)
                self.assertEqual(result.request_id, "review-async")

        asyncio.run(scenario())

        self.assertEqual(observed["method"], "POST")
        self.assertEqual(observed["path"], "/review")
        self.assertEqual(
            observed["body"],
            {
                "document_base64": "U2VuZCB0byBqYW5lQGV4YW1wbGUuY29t",
                "document_filename": "memo.txt",
                "document_mime_type": "text/plain",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "SEA",
                "document_type": "generic",
                "review_profile": "strict",
                "include_suggestions": True,
            },
        )

    def test_async_anonymize_uses_same_backend_contract(self):
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=build_anonymize_payload(request_id="anon-async", classification="HIGH_RISK"))

        async def scenario() -> None:
            transport = httpx.MockTransport(handler)
            async with AsyncKaypohClient("http://kaypoh.test", transport=transport) as client:
                result = await client.anonymize(
                    document_base64="U2VuZCB0byBqYW5lQGV4YW1wbGUuY29t",
                    document_filename="memo.txt",
                    document_mime_type="text/plain",
                    source_jurisdiction="SG",
                    destination_jurisdiction="SEA",
                    include_mnpi_scalars=True,
                )
                self.assertEqual(result.classification, Classification.HIGH_RISK)
                self.assertEqual(result.request_id, "anon-async")
                self.assertEqual(result.anonymized_text, "Send [EMAIL_1]")
                self.assertEqual(result.privacy_operation, "anonymize")

        asyncio.run(scenario())

        self.assertEqual(observed["method"], "POST")
        self.assertEqual(observed["path"], "/anonymize")
        self.assertEqual(
            observed["body"],
            {
                "document_base64": "U2VuZCB0byBqYW5lQGV4YW1wbGUuY29t",
                "document_filename": "memo.txt",
                "document_mime_type": "text/plain",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "SEA",
                "document_type": "generic",
                "review_profile": "strict",
                "include_suggestions": True,
                "include_mnpi_scalars": True,
            },
        )

    def test_async_convenience_function_returns_typed_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=build_classify_payload(request_id="req-async-fn"))

        async def scenario() -> None:
            transport = httpx.MockTransport(handler)
            result = await async_classify_text(
                "Public update",
                base_url="http://kaypoh.test",
                transport=transport,
            )
            self.assertEqual(result.classification, Classification.SAFE)
            self.assertEqual(result.request_id, "req-async-fn")

        asyncio.run(scenario())

    def test_async_runtime_methods_and_batch_return_typed_models(self):
        async def scenario() -> None:
            def handler(request: httpx.Request) -> httpx.Response:
                if request.url.path == "/health":
                    return httpx.Response(
                        200,
                        json={
                            "status": "ok",
                            "lexicon_loaded": True,
                            "model1_loaded": True,
                            "model2_loaded": False,
                            "embedding_loaded": False,
                            "clustering_loaded": False,
                            "mosaic_loaded": False,
                            "regression_loaded": False,
                        },
                    )
                if request.url.path == "/ready":
                    return httpx.Response(
                        200,
                        json={
                            "status": "ok",
                            "ready": True,
                            "pipeline": ["lexicon", "model1"],
                            "missing_required_layers": [],
                            "warming_required_layers": [],
                            "reasons": [],
                        },
                    )
                if request.url.path == "/diagnostics":
                    return httpx.Response(
                        200,
                        json={
                            "status": "ok",
                            "pipeline": ["lexicon", "model1"],
                            "loaded_layers": ["lexicon", "model1"],
                            "lazy_layers": [],
                            "warming_required_layers": [],
                            "load_errors": [],
                            "startup_timings_ms": {"lexicon": 1.1, "model1": 2.2, "total": 3.3},
                            "metrics_mode": "singleprocess",
                            "dependency_status": {},
                            "runtime_layer_errors": {},
                        },
                    )
                if request.url.path == "/metrics":
                    return httpx.Response(200, text="kaypoh_requests_total 1\n")
                if request.url.path == "/classify/batch":
                    body = json.loads(request.content.decode("utf-8"))
                    self.assertEqual(len(body["items"]), 2)
                    return httpx.Response(
                        200,
                        json={
                            "results": [
                                build_classify_payload(request_id="req-async-2"),
                                build_classify_payload(request_id="req-async-3", classification="LOW_RISK"),
                            ]
                        },
                    )
                raise AssertionError(f"unexpected path: {request.url.path}")

            transport = httpx.MockTransport(handler)
            async with AsyncKaypohClient("http://kaypoh.test", transport=transport) as client:
                health = await client.health()
                ready = await client.ready()
                diagnostics = await client.diagnostics()
                metrics = await client.metrics()
                batch = await client.classify_batch(
                    [
                        {"text": "Quarterly board memo"},
                        {"text": "Public investor presentation"},
                    ]
                )
                many = await client.classify_many(
                    [
                        {"text": "Quarterly board memo"},
                        {"text": "Public investor presentation"},
                    ]
                )

            self.assertTrue(health.lexicon_loaded)
            self.assertTrue(ready.ready)
            self.assertEqual(diagnostics.loaded_layers, ["lexicon", "model1"])
            self.assertIn("kaypoh_requests_total", metrics)
            self.assertEqual([result.request_id for result in batch.results], ["req-async-2", "req-async-3"])
            self.assertEqual([result.classification for result in many], [Classification.SAFE, Classification.LOW_RISK])

        asyncio.run(scenario())

    def test_async_http_errors_raise_kaypoh_api_error(self):
        async def scenario() -> None:
            def handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(401, json={"detail": "invalid or missing API key"})

            transport = httpx.MockTransport(handler)

            with self.assertRaises(KaypohAPIError) as ctx:
                async with AsyncKaypohClient("http://kaypoh.test", api_key="wrong-key", transport=transport) as client:
                    await client.classify(text="Public update")

            self.assertEqual(ctx.exception.status_code, 401)
            self.assertEqual(ctx.exception.detail, "invalid or missing API key")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
