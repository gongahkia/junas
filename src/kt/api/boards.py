from __future__ import annotations

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
    text: str | None = Query(None),
    angle: int | None = Query(None),
    layout_id: str | None = Query(None),
    holds_required: list[str] = Query(default_factory=list),
    holds_forbidden: list[str] = Query(default_factory=list),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    settings: Settings = Depends(get_settings),
    repo: SessionsRepo = Depends(get_sessions_repo),
    creds_repo: CredentialsRepo = Depends(get_credentials_repo),
    rl: RateLimiter = Depends(get_rate_limiter),
):
    rl.check(client_key(request), "list_climbs", settings.rl_climbs_per_min)
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    provider = row["provider"]
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
                holds_required=tuple(holds_required),
                holds_forbidden=tuple(holds_forbidden),
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
