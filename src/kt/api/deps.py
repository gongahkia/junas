from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from kt.config import Settings
from kt.realtime.hub import SessionHub
from kt.repos.climbs_cache_repo import ClimbsCacheRepo
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.sessions_repo import SessionsRepo
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
