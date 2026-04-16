from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from kt.auth.service import AuthService
from kt.config import Settings
from kt.realtime.hub import SessionHub
from kt.repos.auth_sessions_repo import AuthSessionsRepo
from kt.repos.climbs_cache_repo import ClimbsCacheRepo
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.magic_links_repo import MagicLinksRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.repos.users_repo import UsersRepo
from kt.security import CredentialCipher


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_sessions_repo() -> SessionsRepo:
    return SessionsRepo()


def get_cipher(settings: Annotated[Settings, Depends(get_settings)]) -> CredentialCipher:
    return CredentialCipher(settings.cred_key)


def get_credentials_repo(
    cipher: Annotated[CredentialCipher, Depends(get_cipher)],
) -> CredentialsRepo:
    return CredentialsRepo(cipher)


def get_climbs_cache_repo() -> ClimbsCacheRepo:
    return ClimbsCacheRepo()


def get_hub(request: Request) -> SessionHub:
    return request.app.state.hub


def get_rate_limiter(request: Request):
    return request.app.state.rate_limiter


def get_users_repo() -> UsersRepo:
    return UsersRepo()


def get_auth_sessions_repo() -> AuthSessionsRepo:
    return AuthSessionsRepo()


def get_magic_links_repo() -> MagicLinksRepo:
    return MagicLinksRepo()


def get_auth_service(
    settings: Annotated[Settings, Depends(get_settings)],
    users: Annotated[UsersRepo, Depends(get_users_repo)],
    sessions: Annotated[AuthSessionsRepo, Depends(get_auth_sessions_repo)],
) -> AuthService:
    return AuthService(settings=settings, users=users, auth_sessions=sessions)
