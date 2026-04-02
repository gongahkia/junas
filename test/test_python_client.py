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

from noupe import AsyncNoupeClient, Classification, NoupeAPIError, NoupeClient, async_classify_text


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


class NoupeClientTests(unittest.TestCase):
    def test_classify_sends_expected_payload_and_api_key(self):
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["method"] = request.method
            observed["path"] = request.url.path
            observed["api_key"] = request.headers.get("X-API-Key")
            observed["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=build_classify_payload(request_id="req-1", classification="LOW_RISK"))

        transport = httpx.MockTransport(handler)

        with NoupeClient("http://noupe.test", api_key="dev-secret", transport=transport) as client:
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

        with NoupeClient("http://noupe.test", transport=transport) as client:
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

    def test_http_errors_raise_noupe_api_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "invalid or missing API key"})

        transport = httpx.MockTransport(handler)

        with self.assertRaises(NoupeAPIError) as ctx:
            with NoupeClient("http://noupe.test", api_key="wrong-key", transport=transport) as client:
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
            async with AsyncNoupeClient("http://noupe.test", transport=transport) as client:
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

    def test_async_convenience_function_returns_typed_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=build_classify_payload(request_id="req-async-fn"))

        async def scenario() -> None:
            transport = httpx.MockTransport(handler)
            result = await async_classify_text(
                "Public update",
                base_url="http://noupe.test",
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
                    return httpx.Response(200, text="noupe_requests_total 1\n")
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
            async with AsyncNoupeClient("http://noupe.test", transport=transport) as client:
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
            self.assertIn("noupe_requests_total", metrics)
            self.assertEqual([result.request_id for result in batch.results], ["req-async-2", "req-async-3"])
            self.assertEqual([result.classification for result in many], [Classification.SAFE, Classification.LOW_RISK])

        asyncio.run(scenario())

    def test_async_http_errors_raise_noupe_api_error(self):
        async def scenario() -> None:
            def handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(401, json={"detail": "invalid or missing API key"})

            transport = httpx.MockTransport(handler)

            with self.assertRaises(NoupeAPIError) as ctx:
                async with AsyncNoupeClient("http://noupe.test", api_key="wrong-key", transport=transport) as client:
                    await client.classify(text="Public update")

            self.assertEqual(ctx.exception.status_code, 401)
            self.assertEqual(ctx.exception.detail, "invalid or missing API key")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
