"""Tests for the Tinyfish public-source adapter and the opt-in remote-LLM path.

Both code paths are wrapped in `httpx.MockTransport` so no real network calls happen.
"""

import json
import unittest
from types import SimpleNamespace

import httpx

from kaypoh.external.public_evidence.inference import PublicEvidenceRetriever
from kaypoh.advisory.llm_adjudicator.helpers import RuntimeLLMCoverageAuditor
from kaypoh.advisory.llm_adjudicator.inference import LocalLLMAdjudicator
from kaypoh.external.privacy_guard import PrivacyGuard


def _tinyfish_settings(
    api_key: str = "tf-test-key",
    endpoint: str = "https://api.search.tinyfish.ai/",
) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        provider="tinyfish",
        api_key=api_key,
        endpoint=endpoint,
        max_results=3,
        timeout_seconds=2.0,
    )


def _provider_settings(
    *,
    provider: str,
    api_key: str = "test-key",
    backup_api_key: str = "",
    endpoint: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        provider=provider,
        api_key=api_key,
        backup_api_key=backup_api_key,
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

    def test_serper_search_translates_organic_results(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["x_api_key"] = request.headers.get("X-API-KEY", "")
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "organic": [
                        {
                            "title": "Acme acquisition announced",
                            "link": "https://example.com/serper-acme",
                            "snippet": "Acme publicly announced the acquisition.",
                            "date": "May 26, 2026",
                            "source": "Example Wire",
                        }
                    ]
                },
            )

        retriever = PublicEvidenceRetriever(
            _provider_settings(
                provider="serper",
                endpoint="https://google.serper.dev/search",
            ),
            PrivacyGuard(),
        )
        transport = httpx.MockTransport(handler)
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        httpx.Client = factory  # type: ignore[assignment]
        try:
            payload = retriever.retrieve(text="Acme Corp acquisition press release.", entity_id="Acme Corp")
        finally:
            httpx.Client = original  # type: ignore[assignment]

        self.assertEqual(payload["status"], "queried")
        self.assertEqual(payload["provider"], "serper")
        self.assertEqual(payload["sources"][0]["url"], "https://example.com/serper-acme")
        self.assertEqual(payload["sources"][0]["author"], "Example Wire")
        self.assertEqual(captured["x_api_key"], "test-key")
        self.assertEqual(captured["body"]["num"], 3)
        self.assertIn("Acme", captured["body"]["q"])

    def test_serpapi_search_translates_organic_results(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["params"] = dict(request.url.params)
            return httpx.Response(
                200,
                json={
                    "organic_results": [
                        {
                            "title": "Acme acquisition filing",
                            "link": "https://example.com/serpapi-acme",
                            "snippet": "The acquisition was disclosed in a filing.",
                            "date": "May 26, 2026",
                            "source": "Example Search",
                        }
                    ]
                },
            )

        retriever = PublicEvidenceRetriever(
            _provider_settings(
                provider="serpapi",
                endpoint="https://serpapi.com/search.json",
            ),
            PrivacyGuard(),
        )
        transport = httpx.MockTransport(handler)
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        httpx.Client = factory  # type: ignore[assignment]
        try:
            payload = retriever.retrieve(text="Acme Corp acquisition press release.", entity_id="Acme Corp")
        finally:
            httpx.Client = original  # type: ignore[assignment]

        self.assertEqual(payload["status"], "queried")
        self.assertEqual(payload["provider"], "serpapi")
        self.assertEqual(payload["sources"][0]["url"], "https://example.com/serpapi-acme")
        self.assertEqual(captured["params"]["engine"], "google")
        self.assertEqual(captured["params"]["api_key"], "test-key")
        self.assertEqual(captured["params"]["num"], "3")

    def test_serpapi_retries_backup_key_on_primary_auth_failure(self):
        seen_keys: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            api_key = request.url.params.get("api_key", "")
            seen_keys.append(api_key)
            if api_key == "primary-key":
                return httpx.Response(429, json={"error": "quota exhausted"})
            return httpx.Response(
                200,
                json={
                    "organic_results": [
                        {
                            "title": "Backup result",
                            "link": "https://example.com/backup",
                            "snippet": "Backup key succeeded.",
                        }
                    ]
                },
            )

        retriever = PublicEvidenceRetriever(
            _provider_settings(
                provider="serpapi",
                api_key="primary-key",
                backup_api_key="backup-key",
                endpoint="https://serpapi.com/search.json",
            ),
            PrivacyGuard(),
        )
        transport = httpx.MockTransport(handler)
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        httpx.Client = factory  # type: ignore[assignment]
        try:
            payload = retriever.retrieve(text="Acme Corp acquisition press release.", entity_id="Acme Corp")
        finally:
            httpx.Client = original  # type: ignore[assignment]

        self.assertEqual(payload["status"], "queried")
        self.assertEqual(payload["sources"][0]["url"], "https://example.com/backup")
        self.assertEqual(seen_keys, ["primary-key", "backup-key"])


def _llm_settings(
    *,
    base_url: str,
    allow_remote: bool,
    provider: str = "vllm",
    tenant_opt_in_openai: bool = False,
    tenant_opt_in_azure_openai: bool = False,
    azure_api_version: str = "",
    llm_input_mode: str | None = None,
    allow_remote_raw_text: bool = False,
    distilled_adapter_path: str = "",
) -> SimpleNamespace:
    payload = {
        "enabled": True,
        "provider": provider,
        "api_key": "",
        "base_url": base_url,
        "model": "gpt-oss-20b",
        "timeout_seconds": 2.0,
        "allow_remote_base_url": allow_remote,
        "tenant_opt_in_openai": tenant_opt_in_openai,
        "tenant_opt_in_azure_openai": tenant_opt_in_azure_openai,
        "azure_api_version": azure_api_version,
        "allow_remote_raw_text": allow_remote_raw_text,
        "distilled_adapter_path": distilled_adapter_path,
        "distilled_base_model": "Qwen/Qwen2.5-1.5B-Instruct",
    }
    if llm_input_mode is not None:
        payload["llm_input_mode"] = llm_input_mode
    return SimpleNamespace(**payload)


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

    def test_adjudicator_health_reports_remote_base_url_refusal(self):
        adjudicator = LocalLLMAdjudicator(_llm_settings(base_url="https://llm.example.com/v1", allow_remote=False))
        health = adjudicator.health()

        self.assertEqual(health["status"], "down")
        self.assertFalse(health["healthy"])
        self.assertIn("allow_remote_base_url=true", health["detail"])

    def test_adjudicator_health_reports_remote_raw_text_refusal(self):
        adjudicator = LocalLLMAdjudicator(
            _llm_settings(
                base_url="https://llm.example.com/v1",
                allow_remote=True,
                llm_input_mode="raw_text",
                allow_remote_raw_text=False,
            )
        )
        health = adjudicator.health()

        self.assertEqual(health["status"], "down")
        self.assertFalse(health["healthy"])
        self.assertIn("allow_remote_raw_text=true", health["detail"])

    def test_adjudicator_health_reports_azure_missing_api_version(self):
        adjudicator = LocalLLMAdjudicator(
            _llm_settings(
                base_url="https://example.openai.azure.com/openai/v1",
                allow_remote=True,
                provider="azure_openai",
                tenant_opt_in_azure_openai=True,
                azure_api_version="",
            )
        )
        health = adjudicator.health()

        self.assertEqual(health["status"], "down")
        self.assertFalse(health["healthy"])
        self.assertIn("azure_api_version", health["detail"])

    def test_adjudicator_health_reports_missing_distilled_adapter(self):
        adjudicator = LocalLLMAdjudicator(
            _llm_settings(
                base_url="",
                allow_remote=False,
                provider="local_distilled",
                distilled_adapter_path="/definitely/missing/kaypoh-adapter",
            )
        )
        health = adjudicator.health()

        self.assertEqual(health["status"], "down")
        self.assertFalse(health["healthy"])
        self.assertIn("adapter path not found", health["detail"])

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
        self.assertEqual(result["input_mode"], "structured_tokens")
        self.assertIn("llm.example.com", captured["url"])

    def test_remote_raw_text_refused_without_raw_text_opt_in(self):
        adjudicator = LocalLLMAdjudicator(
            _llm_settings(
                base_url="https://llm.example.com/v1",
                allow_remote=True,
                llm_input_mode="raw_text",
            )
        )
        result = adjudicator.adjudicate(text="Acme acquisition.", current_classification="LOW_RISK")
        self.assertEqual(result["status"], "error")
        self.assertIn("allow_remote_raw_text", result["review_recommendation"])

    def test_remote_raw_text_runs_with_raw_text_opt_in(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=self._adjudicator_response_payload())

        adjudicator = LocalLLMAdjudicator(
            _llm_settings(
                base_url="https://llm.example.com/v1",
                allow_remote=True,
                llm_input_mode="raw_text",
                allow_remote_raw_text=True,
            )
        )
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
        self.assertEqual(result["input_mode"], "raw_text")
        user_message = next(m for m in captured["body"]["messages"] if m["role"] == "user")
        self.assertIn("Acme acquisition.", user_message["content"])

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

    def test_azure_openai_uses_deployment_url_and_api_key_header(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["api_key"] = request.headers.get("api-key", "")
            captured["authorization"] = request.headers.get("Authorization", "")
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=self._adjudicator_response_payload())

        adjudicator = LocalLLMAdjudicator(
            _llm_settings(
                base_url="https://example.openai.azure.com",
                allow_remote=True,
                provider="azure_openai",
                tenant_opt_in_azure_openai=True,
                azure_api_version="2025-03-01-preview",
            )
        )
        adjudicator.api_key = "az-test"
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
        self.assertIn("/openai/deployments/gpt-oss-20b/chat/completions", captured["url"])
        self.assertIn("api-version=2025-03-01-preview", captured["url"])
        self.assertEqual(captured["api_key"], "az-test")
        self.assertEqual(captured["authorization"], "")
        self.assertNotIn("model", captured["body"])

    def test_azure_openai_falls_back_to_responses_when_chat_unsupported(self):
        calls: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(
                {
                    "url": str(request.url),
                    "api_key": request.headers.get("api-key", ""),
                    "body": json.loads(request.content.decode("utf-8")),
                }
            )
            if len(calls) == 1:
                return httpx.Response(400, json={"error": {"message": "The requested operation is unsupported."}})
            return httpx.Response(
                200,
                json={"output_text": self._adjudicator_response_payload()["choices"][0]["message"]["content"]},
            )

        adjudicator = LocalLLMAdjudicator(
            _llm_settings(
                base_url="https://example.openai.azure.com",
                allow_remote=True,
                provider="azure_openai",
                tenant_opt_in_azure_openai=True,
                azure_api_version="2025-03-01-preview",
            )
        )
        adjudicator.api_key = "az-test"
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
        self.assertIn("/openai/deployments/gpt-oss-20b/chat/completions", str(calls[0]["url"]))
        self.assertEqual(calls[0]["api_key"], "az-test")
        self.assertIn("/openai/v1/responses", str(calls[1]["url"]))
        self.assertEqual(calls[1]["api_key"], "az-test")
        self.assertEqual(calls[1]["body"]["model"], "gpt-oss-20b")
        self.assertFalse(calls[1]["body"]["store"])

    def test_azure_helper_falls_back_to_responses_when_chat_unsupported(self):
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if len(calls) == 1:
                return httpx.Response(400, json={"error": {"message": "The requested operation is unsupported."}})
            return httpx.Response(200, json={"output_text": json.dumps({"warnings": ["check provenance"]})})

        auditor = RuntimeLLMCoverageAuditor(
            _llm_settings(
                base_url="https://example.openai.azure.com",
                allow_remote=True,
                provider="azure_openai",
                tenant_opt_in_azure_openai=True,
                azure_api_version="2025-03-01-preview",
            )
        )
        auditor.api_key = "az-test"
        transport = httpx.MockTransport(handler)
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        httpx.Client = factory  # type: ignore[assignment]
        try:
            warnings = auditor.audit(findings=[], body_hash="abc", document_type="email")
        finally:
            httpx.Client = original  # type: ignore[assignment]

        self.assertEqual(warnings, ["check provenance"])
        self.assertIn("/openai/deployments/gpt-oss-20b/chat/completions", calls[0])
        self.assertIn("/openai/v1/responses", calls[1])


if __name__ == "__main__":
    unittest.main()
