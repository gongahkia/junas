"""Tests for the Tinyfish public-source adapter and the opt-in remote-LLM path.

Both code paths are wrapped in `httpx.MockTransport` so no real network calls happen.
"""

import json
import unittest
from types import SimpleNamespace

import httpx

from kaypoh.workflow.layer7_public_evidence.inference import PublicEvidenceRetriever
from kaypoh.workflow.layer8_llm_adjudicator.inference import LocalLLMAdjudicator
from kaypoh.workflow.privacy_guard import PrivacyGuard


def _tinyfish_settings(api_key: str = "tf-test-key", endpoint: str = "https://api.search.tinyfish.ai/") -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        provider="tinyfish",
        api_key=api_key,
        endpoint=endpoint,
        max_results=3,
        timeout_seconds=2.0,
    )


class TinyfishAdapterTests(unittest.TestCase):
    def test_tinyfish_search_translates_results_and_uses_x_api_key_header(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["x_api_key"] = request.headers.get("X-API-Key", "")
            captured["query"] = request.url.params.get("query", "")
            payload = {
                "query": captured["query"],
                "total_results": 2,
                "page": 0,
                "results": [
                    {
                        "position": 1,
                        "site_name": "Reuters",
                        "snippet": "Acme announced the transaction publicly today.",
                        "title": "Acme announces acquisition",
                        "url": "https://example.com/acme",
                    },
                    {
                        "position": 2,
                        "site_name": "Bloomberg",
                        "snippet": "Acme press release detailing the deal terms.",
                        "title": "Press release: Acme + GlobalTech",
                        "url": "https://example.com/acme-press",
                    },
                ],
            }
            return httpx.Response(200, json=payload)

        retriever = PublicEvidenceRetriever(_tinyfish_settings(), PrivacyGuard())
        transport = httpx.MockTransport(handler)
        # patch the client factory used by _search_tinyfish for the duration of the test.
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        httpx.Client = factory  # type: ignore[assignment]
        try:
            payload = retriever.retrieve(
                text="Acme Corp acquisition press release.", entity_id="Acme Corp"
            )
        finally:
            httpx.Client = original  # type: ignore[assignment]

        self.assertEqual(payload["status"], "queried")
        self.assertEqual(payload["provider"], "tinyfish")
        self.assertTrue(payload["sources"], payload)
        first = payload["sources"][0]
        self.assertEqual(first["title"], "Acme announces acquisition")
        self.assertEqual(first["url"], "https://example.com/acme")
        self.assertEqual(first["author"], "Reuters")
        self.assertEqual(captured["x_api_key"], "tf-test-key")
        self.assertIn("Acme", captured["query"])
        # privacy guard must approve at least one sanitized query for the request to reach the adapter
        self.assertTrue(any(entry["allowed"] for entry in payload["privacy_ledger"]))

    def test_tinyfish_skipped_when_api_key_missing(self):
        retriever = PublicEvidenceRetriever(_tinyfish_settings(api_key=""), PrivacyGuard())
        payload = retriever.retrieve(text="Acme Corp acquisition.", entity_id="Acme Corp")
        self.assertEqual(payload["status"], "skipped")
        self.assertIn("TINYFISH_API_KEY", payload["detail"])
        self.assertEqual(payload["sources"], [])

    def test_unknown_provider_returns_error(self):
        retriever = PublicEvidenceRetriever(
            SimpleNamespace(
                enabled=True,
                provider="bogus",
                api_key="x",
                endpoint="https://example.com/",
                max_results=3,
                timeout_seconds=1.0,
            ),
            PrivacyGuard(),
        )
        payload = retriever.retrieve(text="Acme Corp acquisition.", entity_id="Acme Corp")
        self.assertEqual(payload["status"], "error")
        self.assertIn("unsupported public evidence provider", payload["detail"])


def _llm_settings(*, base_url: str, allow_remote: bool) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        provider="vllm",
        api_key="",
        base_url=base_url,
        model="gpt-oss-20b",
        timeout_seconds=2.0,
        allow_remote_base_url=allow_remote,
    )


class RemoteLLMOptInTests(unittest.TestCase):
    def _adjudicator_response_payload(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "risk_label": "SAFE",
                                "public_status": "public",
                                "confidence": 0.9,
                                "materiality_reason": "matched a press release",
                                "matched_public_sources": ["https://example.com/press"],
                                "unverified_claims": [],
                                "review_recommendation": "no escalation",
                            }
                        )
                    }
                }
            ]
        }

    def test_remote_base_url_refused_without_explicit_opt_in(self):
        adjudicator = LocalLLMAdjudicator(_llm_settings(base_url="https://llm.example.com/v1", allow_remote=False))
        result = adjudicator.adjudicate(text="Acme acquisition.", current_classification="LOW_RISK")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["risk_label"], None)
        self.assertIn("not local/private", result["review_recommendation"])

    def test_remote_base_url_runs_when_opt_in_flag_set(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(200, json=self._adjudicator_response_payload())

        adjudicator = LocalLLMAdjudicator(_llm_settings(base_url="https://llm.example.com/v1", allow_remote=True))
        transport = httpx.MockTransport(handler)
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        httpx.Client = factory  # type: ignore[assignment]
        try:
            result = adjudicator.adjudicate(text="Acme acquisition.", current_classification="LOW_RISK")
        finally:
            httpx.Client = original  # type: ignore[assignment]

        self.assertEqual(result["status"], "adjudicated")
        self.assertEqual(result["risk_label"], "SAFE")
        self.assertEqual(result["public_status"], "public")
        self.assertIn("llm.example.com", captured["url"])

    def test_loopback_base_url_runs_without_opt_in(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            return httpx.Response(200, json=self._adjudicator_response_payload())

        adjudicator = LocalLLMAdjudicator(_llm_settings(base_url="http://127.0.0.1:8001/v1", allow_remote=False))
        transport = httpx.MockTransport(handler)
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        httpx.Client = factory  # type: ignore[assignment]
        try:
            result = adjudicator.adjudicate(text="Acme acquisition.", current_classification="LOW_RISK")
        finally:
            httpx.Client = original  # type: ignore[assignment]

        self.assertEqual(result["status"], "adjudicated")
        self.assertIn("127.0.0.1", captured["url"])


if __name__ == "__main__":
    unittest.main()
