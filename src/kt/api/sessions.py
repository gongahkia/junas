from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Request

from kt.api.deps import (
    get_cipher,
    get_credentials_repo,
    get_hub,
    get_rate_limiter,
    get_sessions_repo,
    get_settings,
)
from kt.config import Settings
from kt.providers import registry
from kt.ratelimit import RateLimiter, client_key
from kt.realtime.hub import SessionHub
from kt.realtime.state import Participant, Role, SessionState, now_iso
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.schemas.api import (
    AttachCredentialsReq,
    AttachCredentialsResp,
    CreateSessionReq,
    CreateSessionResp,
    JoinSessionReq,
    JoinSessionResp,
    SessionSummary,
)
from kt.security import CredentialCipher, hash_secret, new_secret, verify_secret

router = APIRouter(prefix="/api/sessions")

_ALPHABET = string.ascii_uppercase + "23456789"


def _code(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


@router.post("", response_model=CreateSessionResp)
async def create_session(
    req: CreateSessionReq,
    request: Request,
    settings: Settings = Depends(get_settings),
    repo: SessionsRepo = Depends(get_sessions_repo),
    rl: RateLimiter = Depends(get_rate_limiter),
):
    rl.check(client_key(request), "create_session", settings.rl_create_session_per_min)
    known = {p["key"] for p in registry.describe()}
    if req.provider not in known:
        raise HTTPException(400, {"error": "unknown_provider", "detail": req.provider})

    code = _code(settings.session_code_len)
    host_id = secrets.token_urlsafe(9)
    host_secret = new_secret()
    state = SessionState(
        code=code,
        host_id=host_id,
        provider=req.provider,
        participants={
            host_id: Participant(
                id=host_id,
                display_name=req.host_display_name,
                role=Role.HOST,
                joined_at=now_iso(),
            )
        },
    )
    await repo.create(
        code=code,
        host_participant_id=host_id,
        host_secret_hash=hash_secret(host_secret),
        provider=req.provider,
        state=state.to_dict(),
    )
    return CreateSessionResp(code=code, host_participant_id=host_id, host_secret=host_secret)


@router.get("/{code}", response_model=SessionSummary)
async def get_session(code: str, repo: SessionsRepo = Depends(get_sessions_repo)):
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    state = row["state"]
    return SessionSummary(
        code=row["code"],
        provider=row["provider"],
        participant_count=len(state.get("participants") or {}),
        queue_length=len(state.get("queue") or []),
        created_at=row["created_at"],
        ended_at=row["ended_at"],
    )


@router.post("/{code}/join", response_model=JoinSessionResp)
async def join_session(
    code: str,
    req: JoinSessionReq,
    request: Request,
    settings: Settings = Depends(get_settings),
    repo: SessionsRepo = Depends(get_sessions_repo),
    hub: SessionHub = Depends(get_hub),
    rl: RateLimiter = Depends(get_rate_limiter),
):
    rl.check(client_key(request), "join_session", settings.rl_join_per_min)
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})

    participant_id = secrets.token_urlsafe(9)
    live = await hub.load_or_restore(code)
    assert live is not None
    async with live.lock:
        live.state.participants[participant_id] = Participant(
            id=participant_id,
            display_name=req.display_name,
            role=Role.PARTICIPANT,
            joined_at=now_iso(),
        )
        await repo.save_state(code, live.state.to_dict())

    ws_token = new_secret()
    await repo.put_ws_token(ws_token, code, participant_id, settings.ws_token_ttl_seconds)
    return JoinSessionResp(participant_id=participant_id, ws_token=ws_token)


@router.delete("/{code}")
async def end_session(
    code: str,
    host_secret: str,
    repo: SessionsRepo = Depends(get_sessions_repo),
    creds_repo: CredentialsRepo = Depends(get_credentials_repo),
    hub: SessionHub = Depends(get_hub),
):
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    if not verify_secret(host_secret, row["host_secret_hash"]):
        raise HTTPException(403, {"error": "bad_host_secret"})
    await creds_repo.delete_all(code)
    await hub.end(code)
    return {"ended": True}


@router.post("/{code}/credentials", response_model=AttachCredentialsResp)
async def attach_credentials(
    code: str,
    req: AttachCredentialsReq,
    repo: SessionsRepo = Depends(get_sessions_repo),
    creds_repo: CredentialsRepo = Depends(get_credentials_repo),
    cipher: CredentialCipher = Depends(get_cipher),
    hub: SessionHub = Depends(get_hub),
):
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    if not verify_secret(req.host_secret, row["host_secret_hash"]):
        raise HTTPException(403, {"error": "bad_host_secret"})
    if req.provider != row["provider"]:
        raise HTTPException(400, {"error": "provider_mismatch", "detail": row["provider"]})
    try:
        provider = registry.get(req.provider)
    except KeyError:
        raise HTTPException(400, {"error": "unknown_provider"}) from None

    if provider.requires_credentials:
        try:
            await provider.authenticate(req.credentials)
        except Exception as e:
            raise HTTPException(400, {"error": "auth_failed", "detail": str(e)}) from e

    await creds_repo.put(code, req.provider, req.credentials)
    _ = hub  # kept for signature stability; no state change required
    return AttachCredentialsResp(provider=req.provider, ok=True)
