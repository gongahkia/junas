from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from kt.api.deps import (
    get_credentials_repo,
    get_rate_limiter,
    get_sessions_repo,
    get_settings,
)
from kt.config import Settings
from kt.providers import registry
from kt.providers.base import ClimbQuery, ProviderAuthError, ProviderUnavailable
from kt.ratelimit import RateLimiter, client_key
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.schemas.api import ClimbOut, ClimbsResp, ProviderDescriptor

router = APIRouter(prefix="/api")


@router.get("/providers", response_model=list[ProviderDescriptor])
async def list_providers():
    return [ProviderDescriptor(**p) for p in registry.describe()]


@router.get("/sessions/{code}/climbs", response_model=ClimbsResp)
async def list_climbs(
    code: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[SessionsRepo, Depends(get_sessions_repo)],
    creds_repo: Annotated[CredentialsRepo, Depends(get_credentials_repo)],
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
    enabled_providers = row["enabled_providers"]
    if provider is None:
        if len(enabled_providers) != 1:
            raise HTTPException(400, {"error": "provider_required", "detail": enabled_providers})
        provider = enabled_providers[0]
    elif provider not in enabled_providers:
        raise HTTPException(400, {"error": "provider_not_enabled", "detail": enabled_providers})
    try:
        p = registry.get(provider)
    except KeyError:
        raise HTTPException(400, {"error": "unknown_provider"}) from None

    token = None
    if p.requires_credentials:
        creds = await creds_repo.get(code, provider)
        if creds is None:
            raise HTTPException(400, {"error": "no_credentials_for_provider"})
        try:
            token = await p.authenticate(creds)
        except ProviderAuthError as e:
            raise HTTPException(400, {"error": "auth_failed", "detail": str(e)}) from e
        except ProviderUnavailable as e:
            raise HTTPException(503, {"error": "provider_unavailable", "detail": str(e)}) from e

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

    return ClimbsResp(
        climbs=[
            ClimbOut(
                id=c.id,
                provider=c.provider,
                name=c.name,
                setter=c.setter,
                grade=c.grade,
                angle=c.angle,
                ascents=c.ascents,
            )
            for c in climbs
        ]
    )
