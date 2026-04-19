from __future__ import annotations

from kt.providers.base import BoardProvider, ProviderStatus
from kt.providers.taxonomy import normalize_provider_descriptor

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
    out: list[dict[str, object]] = []
    for p in _providers.values():
        inferred_capabilities = {
            "list_layouts": callable(getattr(p, "list_layouts", None)),
            "search_climbs": callable(getattr(p, "search_climbs", None)),
            "get_climb": callable(getattr(p, "get_climb", None)),
            "live_data": False,
        }
        declared_capabilities = dict(getattr(p, "capabilities", {}) or {})
        inferred_capabilities.update(declared_capabilities)
        base: dict[str, object] = {
            "key": p.key,
            "name": p.name,
            "status": p.status.value,
            "requires_credentials": p.requires_credentials,
            "capabilities": inferred_capabilities,
            "source": getattr(p, "source", None),
            "status_reason": None,
        }
        custom_describe = getattr(p, "describe", None)
        if callable(custom_describe):
            extra = custom_describe()
            if isinstance(extra, dict):
                base.update(extra)
        out.append(normalize_provider_descriptor(base))
    return out


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
