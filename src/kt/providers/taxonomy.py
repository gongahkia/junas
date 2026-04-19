from __future__ import annotations

from collections.abc import Mapping
from typing import Any

TAXONOMY_VERSION = "2026-04-aggregator-v1"

CAPABILITY_LIST_LAYOUTS = "list_layouts"
CAPABILITY_SEARCH_CLIMBS = "search_climbs"
CAPABILITY_GET_CLIMB = "get_climb"
CAPABILITY_LIVE_DATA = "live_data"

CAPABILITY_KEYS = (
    CAPABILITY_LIST_LAYOUTS,
    CAPABILITY_SEARCH_CLIMBS,
    CAPABILITY_GET_CLIMB,
    CAPABILITY_LIVE_DATA,
)


def normalize_capabilities(raw: Mapping[str, Any] | None) -> dict[str, bool]:
    caps = {k: False for k in CAPABILITY_KEYS}
    if raw is None:
        return caps
    for k in CAPABILITY_KEYS:
        if k in raw:
            caps[k] = bool(raw[k])
    return caps


def is_data_ready(capabilities: Mapping[str, bool]) -> bool:
    return bool(
        capabilities.get(CAPABILITY_LIST_LAYOUTS, False)
        and capabilities.get(CAPABILITY_SEARCH_CLIMBS, False)
    )


def normalize_provider_descriptor(desc: Mapping[str, Any]) -> dict[str, Any]:
    status = str(desc.get("status") or "unavailable")
    capabilities = normalize_capabilities(desc.get("capabilities"))
    data_ready = is_data_ready(capabilities)
    readiness = "ready" if data_ready else "limited"
    status_reason = desc.get("status_reason")
    status_reason_code = desc.get("status_reason_code")

    if status_reason and not status_reason_code:
        status_reason_code = "provider_limited"
    if not status_reason_code and status == "experimental":
        status_reason_code = "experimental_provider"
    if not status_reason_code and not data_ready:
        status_reason_code = "provider_not_data_ready"

    return {
        "key": str(desc.get("key") or ""),
        "name": str(desc.get("name") or ""),
        "status": status,
        "requires_credentials": bool(desc.get("requires_credentials")),
        "capabilities": capabilities,
        "source": desc.get("source"),
        "status_reason": status_reason,
        "status_reason_code": status_reason_code,
        "is_data_ready": data_ready,
        "readiness": readiness,
        "taxonomy_version": TAXONOMY_VERSION,
    }

