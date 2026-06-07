"""Telemetry no-op contract: zero behavior unless LOGFIRE_TOKEN is set."""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture(autouse=True)
def _clean_env_and_module(monkeypatch):
    # ensure each test starts with a fresh, unconfigured module state
    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    import api.telemetry as t
    importlib.reload(t)
    yield t
    # re-reload to drop any per-test config side-effects
    importlib.reload(t)


def test_disabled_when_token_unset(_clean_env_and_module):
    t = _clean_env_and_module
    assert t.is_enabled() is False
    assert t.configure() is None


def test_span_is_noop_when_disabled(_clean_env_and_module):
    t = _clean_env_and_module
    with t.span("x.y", foo=1, score=0.5) as s:
        # nullcontext yields None
        assert s is None


def test_instrument_fastapi_noop_when_disabled(_clean_env_and_module):
    t = _clean_env_and_module
    # passes a sentinel; should never be touched
    sentinel = object()
    t.instrument_fastapi(sentinel)  # no exception, no attribute access


def test_token_blank_string_is_disabled(monkeypatch, _clean_env_and_module):
    monkeypatch.setenv("LOGFIRE_TOKEN", "   ")
    importlib.reload(_clean_env_and_module)
    assert _clean_env_and_module.is_enabled() is False


def test_set_span_attributes_handles_none(_clean_env_and_module):
    _clean_env_and_module.set_span_attributes(None, foo=1)  # must not raise
