"""Azure OpenAI client + synth pipeline wiring."""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from api.services import llm_client
from benchmark.synthetic import generator as synth_generator
from benchmark.synthetic.planner import ESTIMATED_COST_PER_EXAMPLE_USD, parse_providers


def _fake_openai_module(call_log: list, *, reject_legacy_max_tokens: bool = False) -> types.SimpleNamespace:
    """Build a stub ``openai`` module exposing ``AsyncAzureOpenAI``.

    When ``reject_legacy_max_tokens`` is True, the stub raises on the
    legacy ``max_tokens`` parameter — exercising the fall-forward path
    documented in ``AzureOpenAIClient.generate``.
    """

    class _Choices:
        def __init__(self, content: str) -> None:
            self.message = SimpleNamespace(content=content)

    class _Response:
        def __init__(self, content: str) -> None:
            self.choices = [_Choices(content)]

    class _Completions:
        async def create(self, **kwargs):
            call_log.append(kwargs)
            if reject_legacy_max_tokens and "max_completion_tokens" in kwargs:
                raise RuntimeError(
                    "Unsupported parameter: 'max_completion_tokens' is not supported "
                    "with this model. Use 'max_tokens' instead."
                )
            return _Response("hello from azure")

    class _Chat:
        def __init__(self) -> None:
            self.completions = _Completions()

    class _AsyncAzureOpenAI:
        def __init__(self, *, api_key: str, api_version: str, azure_endpoint: str) -> None:
            self.api_key = api_key
            self.api_version = api_version
            self.azure_endpoint = azure_endpoint
            self.chat = _Chat()

    return types.SimpleNamespace(AsyncAzureOpenAI=_AsyncAzureOpenAI)


def test_get_llm_client_azure_happy_path(monkeypatch):
    settings = SimpleNamespace(
        llm_provider="azure",
        azure_openai_api_key="kkkk",
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_version="2024-08-01-preview",
        azure_openai_deployment="gpt-4o-mini",
    )
    calls: list = []
    monkeypatch.setitem(sys.modules, "openai", _fake_openai_module(calls))
    client = llm_client.get_llm_client(settings)
    assert isinstance(client, llm_client.AzureOpenAIClient)
    assert client.deployment == "gpt-4o-mini"


def test_get_llm_client_azure_missing_env_raises():
    settings = SimpleNamespace(
        llm_provider="azure",
        azure_openai_api_key="",
        azure_openai_endpoint="",
        azure_openai_api_version="",
        azure_openai_deployment="",
    )
    with pytest.raises(RuntimeError) as exc:
        llm_client.get_llm_client(settings)
    msg = str(exc.value)
    assert "AZURE_OPENAI_API_KEY" in msg
    assert "AZURE_OPENAI_ENDPOINT" in msg
    assert "AZURE_OPENAI_DEPLOYMENT" in msg


def test_azure_client_generate_passes_deployment_as_model(monkeypatch):
    calls: list = []
    monkeypatch.setitem(sys.modules, "openai", _fake_openai_module(calls))
    client = llm_client.AzureOpenAIClient(
        api_key="k",
        endpoint="https://e.example",
        api_version="v",
        deployment="deploy-A",
    )

    import asyncio

    out = asyncio.run(client.generate([{"role": "user", "content": "hi"}], max_tokens=64))
    assert out == "hello from azure"
    assert calls[0]["model"] == "deploy-A"
    # Newer Azure deployments use max_completion_tokens; we floor the caller's
    # budget at _REASONING_BUDGET_FLOOR so reasoning models have room.
    assert calls[0]["max_completion_tokens"] == llm_client.AzureOpenAIClient._REASONING_BUDGET_FLOOR
    # temperature intentionally omitted (reasoning models reject non-default).
    assert "temperature" not in calls[0]


def test_azure_client_honours_caller_budget_when_above_floor(monkeypatch):
    calls: list = []
    monkeypatch.setitem(sys.modules, "openai", _fake_openai_module(calls))
    client = llm_client.AzureOpenAIClient(
        api_key="k",
        endpoint="https://e.example",
        api_version="v",
        deployment="d",
    )

    import asyncio

    big = llm_client.AzureOpenAIClient._REASONING_BUDGET_FLOOR + 4096
    asyncio.run(client.generate([{"role": "user", "content": "hi"}], max_tokens=big))
    assert calls[0]["max_completion_tokens"] == big


def test_azure_client_falls_back_to_max_tokens_for_legacy_deployment(monkeypatch):
    calls: list = []
    monkeypatch.setitem(
        sys.modules,
        "openai",
        _fake_openai_module(calls, reject_legacy_max_tokens=True),
    )
    client = llm_client.AzureOpenAIClient(
        api_key="k",
        endpoint="https://e.example",
        api_version="v",
        deployment="legacy",
    )

    import asyncio

    out = asyncio.run(client.generate([{"role": "user", "content": "hi"}], max_tokens=32))
    assert out == "hello from azure"
    # Floored on first attempt (newer-API path).
    assert calls[0]["max_completion_tokens"] == llm_client.AzureOpenAIClient._REASONING_BUDGET_FLOOR
    # Legacy retry preserves the caller's budget (non-reasoning, hard cap).
    assert calls[1]["max_tokens"] == 32


def test_get_llm_model_name_returns_deployment_for_azure():
    settings = SimpleNamespace(llm_provider="azure", azure_openai_deployment="deploy-B")
    assert llm_client.get_llm_model_name(settings) == "deploy-B"


def test_planner_accepts_azure_provider():
    assert "azure" in ESTIMATED_COST_PER_EXAMPLE_USD
    parsed = parse_providers("anthropic,azure")
    assert "azure" in parsed


def test_synth_settings_for_azure_reads_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key123")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://r.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "deploy-C")
    settings = synth_generator._settings_for_provider("azure")
    assert settings.llm_provider == "azure"
    assert settings.azure_openai_api_key == "key123"
    assert settings.azure_openai_endpoint == "https://r.openai.azure.com/"
    assert settings.azure_openai_deployment == "deploy-C"


def test_synth_preflight_azure_reports_missing(monkeypatch):
    for k in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT",
        "JUNAS_SYNTH_AZURE_DEPLOYMENT",
    ):
        monkeypatch.delenv(k, raising=False)
    result = synth_generator.preflight_providers("azure")
    assert result["ok"] is False
    assert "AZURE_OPENAI_API_KEY" in result["missing"]
    assert "AZURE_OPENAI_ENDPOINT" in result["missing"]
    assert "AZURE_OPENAI_DEPLOYMENT" in result["missing"]


def test_synth_preflight_azure_ok_with_full_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://r.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "deploy")
    result = synth_generator.preflight_providers("azure")
    assert result["ok"] is True
    assert "azure" in result["configured_models"]


def test_synth_generator_model_name_azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "deploy-D")
    assert synth_generator.generator_model_name("azure") == "azure:deploy-D"
