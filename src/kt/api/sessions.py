from __future__ import annotations

import secrets
import string
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from kt.api.deps import (
    get_credentials_repo,
    get_rate_limiter,
    get_sessions_repo,
    get_settings,
)
from kt.config import Settings
from kt.providers import registry
from kt.providers.base import ProviderAuthError, ProviderUnavailable
from kt.ratelimit import RateLimiter, client_key
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.schemas.api import (
    AttachCredentialsReq,
    AttachCredentialsResp,
    CreateSessionReq,
    CreateSessionResp,
    SessionSummary,
)
from kt.security import hash_secret, new_secret, verify_secret

router = APIRouter(prefix="/sessions")

_ALPHABET = string.ascii_uppercase + "23456789"


def _code(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def _validate_providers(providers: list[str]) -> list[str]:
    known = {p["key"] for p in registry.describe()}
    unknown = [p for p in providers if p not in known]
    if unknown:
        raise HTTPException(400, {"error": "unknown_provider", "detail": unknown[0]})
    return providers


def _require_read_token(read_token: str | None, row: dict) -> None:
    expected = row.get("read_token_hash")
    if not expected:
        raise HTTPException(503, {"error": "session_not_hardened"})
    if not read_token:
        raise HTTPException(401, {"error": "read_token_required"})
    if not verify_secret(read_token, expected):
        raise HTTPException(403, {"error": "bad_read_token"})


@router.post("", response_model=CreateSessionResp)
async def create_session(
    req: CreateSessionReq,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[SessionsRepo, Depends(get_sessions_repo)],
    rl: Annotated[RateLimiter, Depends(get_rate_limiter)],
):
    rl.check(client_key(request), "create_session", settings.rl_create_session_per_min)
    enabled_providers = _validate_providers(req.enabled_providers or [req.provider or ""])
    provider = req.provider or enabled_providers[0]

    host_secret = new_secret()
    session_read_token = new_secret()
    host_participant_id = secrets.token_urlsafe(9)
    code = ""
    for _ in range(10):
        code = _code(settings.session_code_len)
        state = {
            "owner_display_name": req.host_display_name,
            "provider": provider,
            "enabled_providers": enabled_providers,
        }
        try:
            await repo.create(
                code=code,
                host_participant_id=host_participant_id,
                host_secret_hash=hash_secret(host_secret),
                read_token_hash=hash_secret(session_read_token),
                provider=provider,
                enabled_providers=enabled_providers,
                state=state,
            )
            break
        except aiosqlite.IntegrityError:
            code = ""
    if not code:
        raise HTTPException(503, {"error": "session_code_exhausted"})
    return CreateSessionResp(
        code=code,
        host_secret=host_secret,
        session_read_token=session_read_token,
    )


@router.get("/{code}", response_model=SessionSummary)
async def get_session(
    code: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    rl: Annotated[RateLimiter, Depends(get_rate_limiter)],
    repo: Annotated[SessionsRepo, Depends(get_sessions_repo)],
    creds_repo: Annotated[CredentialsRepo, Depends(get_credentials_repo)],
    read_token: Annotated[str | None, Header(alias="X-Session-Read-Token")] = None,
):
    rl.check(client_key(request), "get_session", settings.rl_get_session_per_min)
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    _require_read_token(read_token, row)
    await repo.touch(code)
    attached = await creds_repo.list_providers(code)
    return SessionSummary(
        code=row["code"],
        provider=row["provider"],
        enabled_providers=row["enabled_providers"],
        attached_providers=attached,
        created_at=row["created_at"],
        ended_at=row["ended_at"],
    )


@router.delete("/{code}")
async def end_session(
    code: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    rl: Annotated[RateLimiter, Depends(get_rate_limiter)],
    repo: Annotated[SessionsRepo, Depends(get_sessions_repo)],
    creds_repo: Annotated[CredentialsRepo, Depends(get_credentials_repo)],
    host_secret: Annotated[str | None, Header(alias="X-Host-Secret")] = None,
):
    rl.check(client_key(request), "end_session", settings.rl_end_session_per_min)
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    if not host_secret:
        raise HTTPException(401, {"error": "host_secret_required"})
    if not verify_secret(host_secret, row["host_secret_hash"]):
        raise HTTPException(403, {"error": "bad_host_secret"})
    await creds_repo.delete_all(code)
    await repo.end(code)
    return {"ended": True}


@router.post("/{code}/credentials", response_model=AttachCredentialsResp)
async def attach_credentials(
    code: str,
    req: AttachCredentialsReq,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    rl: Annotated[RateLimiter, Depends(get_rate_limiter)],
    repo: Annotated[SessionsRepo, Depends(get_sessions_repo)],
    creds_repo: Annotated[CredentialsRepo, Depends(get_credentials_repo)],
):
    rl.check(
        client_key(request),
        "attach_credentials",
        settings.rl_attach_credentials_per_min,
    )
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    if not verify_secret(req.host_secret, row["host_secret_hash"]):
        raise HTTPException(403, {"error": "bad_host_secret"})
    if req.provider not in row["enabled_providers"]:
        raise HTTPException(
            400,
            {"error": "provider_not_enabled", "detail": row["enabled_providers"]},
        )
    try:
        provider = registry.get(req.provider)
    except KeyError:
        raise HTTPException(400, {"error": "unknown_provider"}) from None

    if provider.requires_credentials:
        try:
            await provider.authenticate(req.credentials)
        except ProviderAuthError as e:
            raise HTTPException(400, {"error": "auth_failed", "detail": str(e)}) from e
        except ProviderUnavailable as e:
            raise HTTPException(
                503, {"error": "provider_unavailable", "detail": str(e)}
            ) from e
        except Exception as e:
            raise HTTPException(
                500,
                {"error": "provider_validation_failed", "detail": "unexpected provider error"},
            ) from e

    await creds_repo.put(code, req.provider, req.credentials)
    await repo.touch(code)
    return AttachCredentialsResp(provider=req.provider, ok=True)
