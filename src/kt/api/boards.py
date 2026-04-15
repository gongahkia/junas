from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from kt.api.deps import (
    get_climbs_cache_repo,
    get_credentials_repo,
    get_rate_limiter,
    get_sessions_repo,
    get_settings,
)
from kt.config import Settings
from kt.providers import registry
from kt.providers.base import (
    AuthToken,
    BoardProvider,
    ClimbQuery,
    ProviderAuthError,
    ProviderUnavailable,
)
from kt.ratelimit import RateLimiter, client_key
from kt.repos.climbs_cache_repo import ClimbsCacheRepo
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.schemas.api import ClimbOut, ClimbsResp, LayoutOut, LayoutsResp, ProviderDescriptor

router = APIRouter(prefix="/api")


@router.get("/providers", response_model=list[ProviderDescriptor])
async def list_providers():
    return [ProviderDescriptor(**p) for p in registry.describe()]


def _select_provider(row: dict, provider: str | None) -> str:
    enabled_providers = row["enabled_providers"]
    if provider is None:
        if len(enabled_providers) != 1:
            raise HTTPException(400, {"error": "provider_required", "detail": enabled_providers})
        return enabled_providers[0]
    if provider not in enabled_providers:
        raise HTTPException(400, {"error": "provider_not_enabled", "detail": enabled_providers})
    return provider


def _cache_key(code: str, kind: str, params: Mapping[str, object]) -> str:
    raw = json.dumps(
        {"session_code": code, "kind": kind, "params": params},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


async def _auth_token(
    code: str,
    provider: str,
    p: BoardProvider,
    creds_repo: CredentialsRepo,
) -> AuthToken | None:
    if not p.requires_credentials:
        return None
    creds = await creds_repo.get(code, provider)
    if creds is None:
        raise HTTPException(400, {"error": "no_credentials_for_provider"})
    try:
        return await p.authenticate(creds)
    except ProviderAuthError as e:
        raise HTTPException(400, {"error": "auth_failed", "detail": str(e)}) from e
    except ProviderUnavailable as e:
        raise HTTPException(503, {"error": "provider_unavailable", "detail": str(e)}) from e


@router.get("/sessions/{code}/climbs", response_model=ClimbsResp)
async def list_climbs(
    code: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[SessionsRepo, Depends(get_sessions_repo)],
    creds_repo: Annotated[CredentialsRepo, Depends(get_credentials_repo)],
    cache_repo: Annotated[ClimbsCacheRepo, Depends(get_climbs_cache_repo)],
    rl: Annotated[RateLimiter, Depends(get_rate_limiter)],
    text: Annotated[str | None, Query()] = None,
    angle: Annotated[int | None, Query()] = None,
    layout_id: Annotated[str | None, Query()] = None,
    provider: Annotated[str | None, Query()] = None,
    holds_required: Annotated[list[str] | None, Query()] = None,
    holds_forbidden: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    rl.check(client_key(request), "list_climbs", settings.rl_climbs_per_min)
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    provider = _select_provider(row, provider)
    try:
        p = registry.get(provider)
    except KeyError:
        raise HTTPException(400, {"error": "unknown_provider"}) from None

    params = {
        "text": text,
        "angle": angle,
        "layout_id": layout_id,
        "holds_required": holds_required or [],
        "holds_forbidden": holds_forbidden or [],
        "limit": limit,
        "offset": offset,
    }
    cache_key = _cache_key(code, "climbs", params)
    cached = await cache_repo.get(provider, cache_key)
    if cached is not None:
        return ClimbsResp(climbs=[ClimbOut(**c) for c in cached])

    token = await _auth_token(code, provider, p, creds_repo)

    try:
        climbs = await p.search_climbs(
            token,
            ClimbQuery(
                layout_id=layout_id,
                angle=angle,
                text=text,
                holds_required=tuple(holds_required or ()),
                holds_forbidden=tuple(holds_forbidden or ()),
                limit=limit,
                offset=offset,
            ),
        )
    except ProviderUnavailable as e:
        raise HTTPException(503, {"error": "provider_unavailable", "detail": str(e)}) from e
    except ProviderAuthError as e:
        raise HTTPException(400, {"error": "auth_failed", "detail": str(e)}) from e

    payload = [
        ClimbOut(
            id=c.id,
            provider=c.provider,
            name=c.name,
            setter=c.setter,
            grade=c.grade,
            angle=c.angle,
            ascents=c.ascents,
            holds=c.holds,
            extras=c.extras,
        ).model_dump()
        for c in climbs
    ]
    await cache_repo.put(provider, cache_key, payload, settings.cache_ttl_seconds)
    return ClimbsResp(climbs=[ClimbOut(**c) for c in payload])


@router.get("/sessions/{code}/layouts", response_model=LayoutsResp)
async def list_layouts(
    code: str,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[SessionsRepo, Depends(get_sessions_repo)],
    creds_repo: Annotated[CredentialsRepo, Depends(get_credentials_repo)],
    cache_repo: Annotated[ClimbsCacheRepo, Depends(get_climbs_cache_repo)],
    provider: Annotated[str | None, Query()] = None,
):
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    provider = _select_provider(row, provider)
    try:
        p = registry.get(provider)
    except KeyError:
        raise HTTPException(400, {"error": "unknown_provider"}) from None

    cache_key = _cache_key(code, "layouts", {})
    cached = await cache_repo.get(provider, cache_key)
    if cached is not None:
        return LayoutsResp(layouts=[LayoutOut(**layout) for layout in cached])

    token = await _auth_token(code, provider, p, creds_repo)
    try:
        layouts = await p.list_layouts(token)
    except ProviderUnavailable as e:
        raise HTTPException(503, {"error": "provider_unavailable", "detail": str(e)}) from e
    except ProviderAuthError as e:
        raise HTTPException(400, {"error": "auth_failed", "detail": str(e)}) from e

    payload = [
        LayoutOut(
            id=layout.id,
            name=layout.name,
            angles=layout.angles,
            extras=layout.extras,
        ).model_dump()
        for layout in layouts
    ]
    await cache_repo.put(provider, cache_key, payload, settings.cache_ttl_seconds)
    return LayoutsResp(layouts=[LayoutOut(**layout) for layout in payload])
