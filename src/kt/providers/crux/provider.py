"""CruxProvider — gym-scoped problem catalog from cruxapp.ca.

Crux is gym-centric: climbs belong to a wall in a gym. Use `query.layout_id`
as the gym slug (Crux's gym identifier). If the authenticated token is not
scoped to a default gym, layout discovery returns the user's available gyms.
"""

from __future__ import annotations

import re
from typing import Any

from kt.providers.base import (
    AuthToken,
    Climb,
    ClimbQuery,
    Layout,
    ProviderAuthError,
    ProviderStatus,
    ProviderUnavailable,
    matches_holds,
)
from kt.providers.crux.client import CruxClient


class CruxProvider:
    key = "crux"
    name = "Crux Climbing"
    status = ProviderStatus.OK
    requires_credentials = True

    def __init__(self, client: CruxClient | None = None) -> None:
        self._client = client or CruxClient()

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        token = _normalize_token(creds.get("token") or creds.get("api_token") or creds.get("bearer"))
        if not token:
            raise ProviderAuthError("crux requires `token` (Bearer) in credentials")
        try:
            me = await self._client.get_me(token)
        except ProviderUnavailable:
            raise
        except ProviderAuthError:
            raise
        except Exception as e:
            raise ProviderAuthError(str(e)) from e
        slug = str(creds.get("gym_slug") or "").strip()
        if slug:
            known_slugs = _user_gym_slugs(me)
            if known_slugs and slug not in known_slugs:
                raise ProviderAuthError(f"unknown gym_slug: {slug}")
            if not known_slugs:
                # Some Crux API responses may omit gym lists; validate directly as a fallback.
                await self._client.get_gym(token, slug)
        return AuthToken(
            provider=self.key,
            value=token,
            extras={
                "gym_slug": slug,
                "user_id": me.get("id"),
                "user_name": me.get("name"),
            },
        )

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        if token is None:
            raise ProviderAuthError("auth required")
        slug = token.extras.get("gym_slug")
        if not slug:
            me = await self._client.get_me(token.value)
            return [_gym_to_layout(gym) for gym in _user_gyms(me)]
        walls = await self._client.list_walls(token.value, slug)
        return [
            Layout(
                id=str(w.get("id")),
                name=str(w.get("name", "")),
                angles=_wall_angles(w),
                extras={
                    "kind": "wall",
                    "gym_slug": slug,
                    "parent_id": slug,
                    "angle_adjustable": bool(w.get("angle_adjustable")),
                    "image_url": w.get("image_url"),
                },
            )
            for w in walls
        ]

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        if token is None:
            raise ProviderAuthError("auth required")
        slug = query.layout_id or token.extras.get("gym_slug")
        if not slug:
            raise ProviderAuthError("crux requires gym_slug as layout_id")

        # Crux docs currently state no pagination, so fetch each catalog and window locally.
        official = await self._client.list_official_climbs(token.value, slug)
        custom = await self._client.list_custom_climbs(token.value, slug)
        rows = [*official, *custom]

        if query.text:
            t = query.text.lower()
            rows = [
                r
                for r in rows
                if t in str(r.get("name", "")).lower()
                or t in str(r.get("description", "")).lower()
            ]
        if query.angle is not None:
            rows = [r for r in rows if _parse_angle(r.get("angle")) == query.angle]
        if query.holds_required or query.holds_forbidden:
            rows = [
                r for r in rows
                if matches_holds(list(r.get("holds") or []), query.holds_required, query.holds_forbidden)
            ]
        rows = sorted(rows, key=_sort_key, reverse=True)

        return [_to_climb(r, slug) for r in rows[query.offset : query.offset + query.limit]]

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        if token is None:
            raise ProviderAuthError("auth required")
        return _to_climb(
            await self._client.get_climb(token.value, _external_climb_id(climb_id)),
            token.extras.get("gym_slug"),
        )


def _wall_angles(w: dict[str, Any]) -> list[int]:
    if not w.get("angle_adjustable"):
        return []
    lo = w.get("minimum_angle")
    hi = w.get("maximum_angle")
    if lo is None or hi is None:
        return []
    return list(range(int(lo), int(hi) + 1, 5))


def _gym_to_layout(gym: dict[str, Any]) -> Layout:
    slug = str(gym.get("url_slug") or gym.get("slug") or "")
    return Layout(
        id=slug,
        name=str(gym.get("name") or slug),
        angles=[],
        extras={
            "kind": "gym",
            "parent_id": "",
            "location": gym.get("location"),
            "icon_url": gym.get("icon_url"),
        },
    )


def _to_climb(r: dict[str, Any], fallback_gym_slug: str | None = None) -> Climb:
    image_url = r.get("image_url") or r.get("unedited_image_url")
    return Climb(
        id=f"crux:{r.get('id')}",
        provider="crux",
        name=str(r.get("name") or ""),
        setter=r.get("setter_name"),
        grade=r.get("grade"),
        angle=_parse_angle(r.get("angle")),
        ascents=r.get("number_of_sends"),
        holds=list(r.get("holds") or []),
        extras={
            k: v
            for k, v in r.items()
            if k
            not in {
                "id",
                "name",
                "setter_name",
                "grade",
                "angle",
                "number_of_sends",
                "holds",
            }
        } | {
            "external_id": str(r.get("id")),
            "description": r.get("description"),
            "gym_slug": r.get("gym_slug") or fallback_gym_slug,
            "gym_name": r.get("gym_name"),
            "image_url": image_url,
        },
    )


def _normalize_token(raw: Any) -> str:
    token = str(raw or "").strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token


def _user_gyms(me: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    gyms: list[dict[str, Any]] = []
    for key in ("administrated_gyms", "viewed_gyms"):
        for gym in me.get(key) or []:
            if not isinstance(gym, dict):
                continue
            slug = str(gym.get("url_slug") or gym.get("slug") or "")
            if slug and slug not in seen:
                seen.add(slug)
                gyms.append(gym)
    return sorted(gyms, key=lambda g: str(g.get("name") or "").lower())


def _user_gym_slugs(me: dict[str, Any]) -> set[str]:
    return {layout.id for layout in (_gym_to_layout(gym) for gym in _user_gyms(me)) if layout.id}


def _parse_angle(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    match = re.search(r"-?\d+", str(raw))
    return int(match.group(0)) if match else None


def _sort_key(row: dict[str, Any]) -> tuple[int, str, int]:
    return (
        _int_value(row.get("number_of_sends")),
        str(row.get("created_at") or ""),
        _int_value(row.get("id")),
    )


def _external_climb_id(climb_id: str) -> str:
    if climb_id.startswith("crux:"):
        return climb_id.split(":", 1)[1]
    return climb_id


def _int_value(raw: Any) -> int:
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0
