from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from kt.api.deps import get_auth_service, get_magic_links_repo, get_settings, get_users_repo
from kt.auth.passwords import hash_password, verify_password
from kt.auth.service import AuthService
from kt.auth.tokens import new_token, token_hash
from kt.config import Settings
from kt.repos.magic_links_repo import MagicLinksRepo
from kt.repos.users_repo import UsersRepo
from kt.schemas.auth import (
    LoginReq,
    LogoutReq,
    MagicLinkReq,
    MagicLinkResp,
    MagicLinkVerifyReq,
    RefreshReq,
    RegisterReq,
    TokenPair,
    UpdateProfileReq,
    UserOut,
)

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=TokenPair)
async def register(
    req: RegisterReq,
    users: Annotated[UsersRepo, Depends(get_users_repo)],
    svc: Annotated[AuthService, Depends(get_auth_service)],
):
    existing = await users.get_by_email(req.email)
    if existing is not None:
        raise HTTPException(409, {"error": "email_taken"})
    try:
        ph = hash_password(req.password)
    except ValueError as e:
        raise HTTPException(400, {"error": "weak_password", "detail": str(e)}) from e
    user = await users.create(
        email=req.email,
        display_name=req.display_name,
        password_hash=ph,
        grade_system_pref=req.grade_system_pref,
    )
    tokens = await svc.issue_tokens(user["id"])
    return TokenPair(**tokens)


@router.post("/login", response_model=TokenPair)
async def login(
    req: LoginReq,
    users: Annotated[UsersRepo, Depends(get_users_repo)],
    svc: Annotated[AuthService, Depends(get_auth_service)],
):
    user = await users.get_by_email(req.email)
    if not user or not user.get("password_hash"):
        raise HTTPException(401, {"error": "invalid_credentials"})
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, {"error": "invalid_credentials"})
    tokens = await svc.issue_tokens(user["id"])
    return TokenPair(**tokens)


@router.post("/magic-link", response_model=MagicLinkResp)
async def request_magic_link(
    req: MagicLinkReq,
    settings: Annotated[Settings, Depends(get_settings)],
    links: Annotated[MagicLinksRepo, Depends(get_magic_links_repo)],
):
    raw = new_token()
    await links.put(
        token_hash=token_hash(raw),
        email=req.email,
        purpose="login",
        ttl_seconds=settings.auth_magic_link_ttl_seconds,
    )
    # Note: production deployments must plug in an email sender and flip
    # KT_AUTH_RETURN_MAGIC_LINKS to false. Otherwise the token leaks here.
    return MagicLinkResp(
        ok=True, token=raw if settings.auth_return_magic_links else None
    )


@router.post("/magic-link/verify", response_model=TokenPair)
async def verify_magic_link(
    req: MagicLinkVerifyReq,
    users: Annotated[UsersRepo, Depends(get_users_repo)],
    links: Annotated[MagicLinksRepo, Depends(get_magic_links_repo)],
    svc: Annotated[AuthService, Depends(get_auth_service)],
):
    claim = await links.consume(token_hash(req.token))
    if not claim:
        raise HTTPException(400, {"error": "invalid_or_expired_token"})
    user = await users.get_by_email(claim["email"])
    if user is None:
        try:
            user = await users.create(
                email=claim["email"],
                display_name=claim["email"].split("@", 1)[0][:40],
                password_hash=None,
            )
        except ValueError as e:
            raise HTTPException(400, {"error": str(e)}) from e
    tokens = await svc.issue_tokens(user["id"])
    return TokenPair(**tokens)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    req: RefreshReq,
    svc: Annotated[AuthService, Depends(get_auth_service)],
):
    tokens = await svc.rotate(req.refresh_token)
    if tokens is None:
        raise HTTPException(401, {"error": "invalid_refresh_token"})
    return TokenPair(**tokens)


@router.post("/logout")
async def logout(
    req: LogoutReq,
    svc: Annotated[AuthService, Depends(get_auth_service)],
):
    revoked = await svc.logout(req.refresh_token)
    return {"revoked": bool(revoked)}


async def _bearer_user(
    authorization: str | None,
    svc: AuthService,
) -> dict | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    return await svc.user_by_access(token)


async def get_optional_user(
    request: Request,
    svc: Annotated[AuthService, Depends(get_auth_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict | None:
    user = await _bearer_user(authorization, svc)
    request.state.user = user
    return user


async def require_user(
    svc: Annotated[AuthService, Depends(get_auth_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    user = await _bearer_user(authorization, svc)
    if user is None:
        raise HTTPException(401, {"error": "unauthorized"})
    return user


me_router = APIRouter(prefix="/me")


@me_router.get("", response_model=UserOut)
async def me(user: Annotated[dict, Depends(require_user)]):
    return UserOut(**user)


@me_router.patch("", response_model=UserOut)
async def update_me(
    req: UpdateProfileReq,
    user: Annotated[dict, Depends(require_user)],
    users: Annotated[UsersRepo, Depends(get_users_repo)],
):
    updated = await users.update_profile(
        user["id"],
        display_name=req.display_name,
        grade_system_pref=req.grade_system_pref,
    )
    return UserOut(**updated)  # type: ignore[arg-type]
