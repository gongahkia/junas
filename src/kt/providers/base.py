from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class ProviderStatus(str, Enum):
    OK = "ok"
    EXPERIMENTAL = "experimental"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AuthToken:
    provider: str
    value: str
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Layout:
    id: str
    name: str
    angles: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class Climb:
    id: str
    provider: str
    name: str
    setter: str | None
    grade: str | None
    angle: int | None
    ascents: int | None
    holds: list[dict[str, Any]] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClimbQuery:
    layout_id: str | None = None
    angle: int | None = None
    grade_min: str | None = None
    grade_max: str | None = None
    text: str | None = None
    limit: int = 50
    offset: int = 0


class ProviderError(Exception):
    pass


class ProviderUnavailable(ProviderError):
    pass


class ProviderAuthError(ProviderError):
    pass


class BoardProvider(Protocol):
    key: str
    name: str
    status: ProviderStatus
    requires_credentials: bool

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken: ...

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]: ...

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]: ...

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb: ...
