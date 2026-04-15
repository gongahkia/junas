from __future__ import annotations

from kt.providers.base import BoardProvider, ProviderStatus

_providers: dict[str, BoardProvider] = {}


def register(provider: BoardProvider) -> None:
    _providers[provider.key] = provider


def get(key: str) -> BoardProvider:
    try:
        return _providers[key]
    except KeyError as e:
        raise KeyError(f"unknown provider: {key}") from e


def all_providers() -> list[BoardProvider]:
    return list(_providers.values())


def describe() -> list[dict[str, object]]:
    return [
        {
            "key": p.key,
            "name": p.name,
            "status": p.status.value,
            "requires_credentials": p.requires_credentials,
        }
        for p in _providers.values()
    ]


def reset() -> None:
    _providers.clear()


def bootstrap() -> None:
    """Register all built-in providers. Called at app startup."""
    reset()
    from kt.providers.aurora.provider import AURORA_BOARDS, AuroraProvider
    from kt.providers.crux.provider import CruxProvider
    from kt.providers.kilter.provider import KilterProvider
    from kt.providers.moonboard.catalog_provider import MoonboardCatalogProvider
    from kt.providers.moonboard.provider import MoonboardProvider

    for key, label in AURORA_BOARDS.items():
        register(AuroraProvider(key=key, name=label))
    register(KilterProvider())
    register(MoonboardProvider())
    register(MoonboardCatalogProvider())
    register(CruxProvider())


__all__ = ["register", "get", "all_providers", "describe", "reset", "bootstrap", "ProviderStatus"]
