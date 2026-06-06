from __future__ import annotations

from api.config import Settings


def test_settings_parses_api_keys_from_comma_env(monkeypatch) -> None:
    monkeypatch.setenv("API_KEYS", "alpha, beta")
    settings = Settings(_env_file=None)
    assert settings.api_keys == ["alpha", "beta"]


def test_settings_parses_api_keys_from_json_env(monkeypatch) -> None:
    monkeypatch.setenv("API_KEYS", '["alpha", "beta"]')
    settings = Settings(_env_file=None)
    assert settings.api_keys == ["alpha", "beta"]
