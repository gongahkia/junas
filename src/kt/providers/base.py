from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class ProviderStatus(StrEnum):
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
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Climb:
    id: str
    provider: str
    name: str
    setter: str | None
    grade: str | None
    angle: int | None
    ascents: int | None
    holds: list[Any] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClimbQuery:
    layout_id: str | None = None
    angle: int | None = None
    grade_min: str | None = None
    grade_max: str | None = None
    text: str | None = None
    holds_required: tuple[str, ...] = ()
    holds_forbidden: tuple[str, ...] = ()
    limit: int = 50
    offset: int = 0


def matches_holds(
    climb_holds: Iterable[Any],
    required: tuple[str, ...],
    forbidden: tuple[str, ...],
) -> bool:
    """Return True if a climb's hold list satisfies the required/forbidden filter.

    Hold tokens are compared case-insensitively to be tolerant of formats like
    'C5' vs 'c5' across providers."""
    if not required and not forbidden:
        return True
    have = {str(h).upper() for h in climb_holds if h}
    for r in required:
        if r.upper() not in have:
            return False
    for f in forbidden:
        if f.upper() in have:
            return False
    return True


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
