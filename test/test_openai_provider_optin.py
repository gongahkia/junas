"""OpenAI provider opt-in (item 5).

Two distinct gates protect provider=openai:
1. `allow_remote_base_url=True` — deployer-level: remote URLs are permitted at all.
2. `tenant_opt_in_openai=True` — tenant-level: this specific tenant has signed off
   on OpenAI as the LLM backend.

BOTH must be true. The check fires twice (once at config-load time in `runtime.py`,
once at adjudicate-time in `LocalLLMAdjudicator`) so a hot-reload or test-harness
mutation can't bypass the tenant opt-in.
"""

import json
import unittest
from types import SimpleNamespace

import httpx

from kaypoh.configs.runtime import ConfigError, _load_runtime_settings_from_inputs
from kaypoh.workflow.layer8_llm_adjudicator.inference import LocalLLMAdjudicator


def _llm_settings(
    *,
    provider: str = "openai",
    allow_remote: bool = True,
    tenant_opt_in: bool = True,
    base_url: str = "https://api.openai.com/v1",
) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        provider=provider,
        api_key="sk-test",
        base_url=base_url,
        model="gpt-4o-mini",
        timeout_seconds=2.0,
        allow_remote_base_url=allow_remote,
        tenant_opt_in_openai=tenant_opt_in,
    )


def _openai_chat_completion_response() -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "risk_label": "SAFE",
                        "public_status": "public",
                        "confidence": 0.9,
                        "materiality_reason": "matched a public source",
                        "matched_public_sources": ["https://example.com/x"],
                        "unverified_claims": [],
                        "review_recommendation": "no escalation",
                    })
                }
            }
        ]
    }


class AdjudicateTimeGateTests(unittest.TestCase):
    """Gate checks at adjudicate() time — the per-request defence."""

    def test_openai_provider_refused_without_tenant_opt_in(self):
        adj = LocalLLMAdjudicator(_llm_settings(tenant_opt_in=False))
        result = adj.adjudicate(text="x", current_classification="LOW_RISK")
        self.assertEqual(result["status"], "error")
        self.assertIn("tenant_opt_in_openai", result["review_recommendation"])

    def test_openai_provider_refused_without_remote_url_flag(self):
        # tenant said yes but the URL isn't loopback and the deployer hasn't said yes either
        adj = LocalLLMAdjudicator(_llm_settings(allow_remote=False))
        result = adj.adjudicate(text="x", current_classification="LOW_RISK")
        self.assertEqual(result["status"], "error")
        self.assertIn("not local/private", result["review_recommendation"])

    def test_openai_provider_runs_when_both_gates_pass(self):
        adj = LocalLLMAdjudicator(_llm_settings())

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_openai_chat_completion_response())

        transport = httpx.MockTransport(handler)
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        httpx.Client = factory  # type: ignore[assignment]
        try:
            result = adj.adjudicate(text="Acme acquisition.", current_classification="LOW_RISK")
        finally:
            httpx.Client = original  # type: ignore[assignment]

        self.assertEqual(result["status"], "adjudicated")
        self.assertEqual(result["risk_label"], "SAFE")
        self.assertEqual(result["provider"], "openai")


class ConfigLoadTimeGateTests(unittest.TestCase):
    """Gate checks at config-load time — the fail-fast defence."""

    def _load(self, *, provider: str, allow_remote: bool, tenant_opt_in: bool):
        cli = {
            ("llm", "enabled"): True,
            ("llm", "provider"): provider,
            ("llm", "base_url"): "https://api.openai.com/v1",
            ("llm", "model"): "gpt-4o-mini",
            ("llm", "allow_remote_base_url"): allow_remote,
            ("llm", "tenant_opt_in_openai"): tenant_opt_in,
        }
        return _load_runtime_settings_from_inputs(
            raw_config={}, cli_overrides=cli, environ={},
        )

    def test_openai_provider_rejected_when_remote_flag_missing(self):
        with self.assertRaises(ConfigError) as ctx:
            self._load(provider="openai", allow_remote=False, tenant_opt_in=True)
        self.assertIn("allow_remote_base_url", str(ctx.exception))

    def test_openai_provider_rejected_when_tenant_opt_in_missing(self):
        with self.assertRaises(ConfigError) as ctx:
            self._load(provider="openai", allow_remote=True, tenant_opt_in=False)
        self.assertIn("tenant_opt_in_openai", str(ctx.exception))

    def test_openai_provider_accepted_with_both_gates(self):
        settings = self._load(provider="openai", allow_remote=True, tenant_opt_in=True)
        self.assertEqual(settings.llm.provider, "openai")
        self.assertTrue(settings.llm.tenant_opt_in_openai)

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ConfigError):
            self._load(provider="claude", allow_remote=True, tenant_opt_in=True)

    def test_local_provider_does_not_need_tenant_flag(self):
        # vllm/ollama paths must not be affected by the new tenant gate
        settings = _load_runtime_settings_from_inputs(
            raw_config={}, cli_overrides={
                ("llm", "enabled"): True,
                ("llm", "provider"): "vllm",
                ("llm", "base_url"): "http://127.0.0.1:8001/v1",
            }, environ={},
        )
        self.assertEqual(settings.llm.provider, "vllm")
        self.assertFalse(settings.llm.tenant_opt_in_openai)


if __name__ == "__main__":
    unittest.main()
