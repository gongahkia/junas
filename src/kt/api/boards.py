from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from kt.api.deps import (
    get_climbs_cache_repo,
    get_credentials_repo,
    get_rate_limiter,
    get_sessions_repo,
    get_settings,
)
from kt.config import Settings
from kt.grades import parse_to_v, system_value
from kt.providers import registry
from kt.providers.base import (
    AuthToken,
    BoardProvider,
    Climb,
    ClimbQuery,
    ProviderAuthError,
    ProviderUnavailable,
)
from kt.ratelimit import RateLimiter, client_key
from kt.repos.climbs_cache_repo import ClimbsCacheRepo
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.schemas.api import (
    ClimbOut,
    ClimbsResp,
    GradeOut,
    LayoutOut,
    LayoutsResp,
    MediaRef,
    ProviderDescriptor,
    SetterRef,
)
from kt.security import verify_secret

router = APIRouter()

_MAX_OVERFETCH_MULTIPLIER = 5
_MAX_OVERFETCH_CAP = 500
_ALLOWED_SORTS = {"stars", "ascents", "newest", "grade_asc", "grade_desc", "default"}


@router.get("/providers", response_model=list[ProviderDescriptor])
async def list_providers():
    return [ProviderDescriptor(**p) for p in registry.describe()]


def _select_provider(row: dict, provider: str | None) -> str:
    enabled_providers = row["enabled_providers"]
    if provider is None:
        if len(enabled_providers) != 1:
            raise HTTPException(400, {"error": "provider_required", "detail": enabled_providers})
        return enabled_providers[0]
    if provider not in enabled_providers:
        raise HTTPException(400, {"error": "provider_not_enabled", "detail": enabled_providers})
    return provider


def _require_read_token(read_token: str | None, row: dict) -> None:
    expected = row.get("read_token_hash")
    if not expected:
        raise HTTPException(503, {"error": "session_not_hardened"})
    if not read_token:
        raise HTTPException(401, {"error": "read_token_required"})
    if not verify_secret(read_token, expected):
        raise HTTPException(403, {"error": "bad_read_token"})


def _cache_key(code: str, kind: str, params: Mapping[str, object]) -> str:
    raw = json.dumps(
        {"session_code": code, "kind": kind, "params": params},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


async def _auth_token(
    code: str,
    provider: str,
    p: BoardProvider,
    creds_repo: CredentialsRepo,
) -> AuthToken | None:
    if not p.requires_credentials:
        return None
    creds = await creds_repo.get(code, provider)
    if creds is None:
        raise HTTPException(400, {"error": "no_credentials_for_provider"})
    try:
        return await p.authenticate(creds)
    except ProviderAuthError as e:
        raise HTTPException(400, {"error": "auth_failed", "detail": str(e)}) from e
    except ProviderUnavailable as e:
        raise HTTPException(503, {"error": "provider_unavailable", "detail": str(e)}) from e


def _encode_cursor(offset: int, query_hash: str) -> str:
    payload = json.dumps({"o": offset, "h": query_hash}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()


def _decode_cursor(cursor: str, expected_hash: str) -> int:
    try:
        pad = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + pad).decode())
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        raise HTTPException(400, {"error": "bad_cursor"}) from e
    if payload.get("h") != expected_hash:
        # Query shape changed; ask the client to restart pagination.
        raise HTTPException(400, {"error": "cursor_query_mismatch"})
    offset = int(payload.get("o") or 0)
    if offset < 0:
        raise HTTPException(400, {"error": "bad_cursor"})
    return offset


def _grade_raw(climb: Climb) -> str | None:
    if climb.grade:
        return str(climb.grade)
    extras = climb.extras or {}
    for k in ("grade", "grade_raw", "difficulty_string"):
        v = extras.get(k)
        if v:
            return str(v)
    return None


def _stars(climb: Climb) -> float | None:
    extras = climb.extras or {}
    for k in ("quality_average", "stars", "user_rating", "average_quality"):
        v = extras.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _tags(climb: Climb) -> list[str]:
    extras = climb.extras or {}
    raw = extras.get("tags")
    if isinstance(raw, list):
        return [str(t) for t in raw if t]
    return []


def _media(climb: Climb) -> list[MediaRef]:
    extras = climb.extras or {}
    out: list[MediaRef] = []
    for key, kind in (("image_url", "image"), ("thumbnail_url", "thumbnail"), ("video_url", "video")):
        url = extras.get(key)
        if url:
            out.append(MediaRef(kind=kind, url=str(url)))
    return out


def _setter_ref(climb: Climb) -> SetterRef | None:
    if climb.setter:
        return SetterRef(name=str(climb.setter))
    extras = climb.extras or {}
    name = extras.get("setter_name") or extras.get("setter_username") or extras.get("setter")
    if name:
        return SetterRef(name=str(name))
    return None


def _grade_out(raw: str | None) -> GradeOut | None:
    if raw is None:
        return None
    v = parse_to_v(raw)
    if v is None:
        return GradeOut(raw=raw)
    return GradeOut(
        raw=raw,
        v=v,
        font=system_value(v, "font"),
        yds=system_value(v, "yds"),
        uiaa=system_value(v, "uiaa"),
    )


def _enrich(climb: Climb) -> ClimbOut:
    grade_raw = _grade_raw(climb)
    return ClimbOut(
        id=climb.id,
        provider=climb.provider,
        name=climb.name,
        setter=climb.setter,
        setter_ref=_setter_ref(climb),
        grade=grade_raw,
        grades=_grade_out(grade_raw),
        angle=climb.angle,
        ascents=climb.ascents,
        stars=_stars(climb),
        holds=climb.holds,
        tags=_tags(climb),
        media=_media(climb),
        extras=climb.extras,
    )


def _apply_post_filters(
    climbs: list[ClimbOut],
    *,
    sort: str,
    stars_min: float | None,
    grade_min_v: int | None,
    grade_max_v: int | None,
) -> list[ClimbOut]:
    if stars_min is not None:
        climbs = [c for c in climbs if (c.stars or 0) >= stars_min]
    if grade_min_v is not None or grade_max_v is not None:
        filtered: list[ClimbOut] = []
        for c in climbs:
            v = c.grades.v if c.grades else None
            if v is None:
                continue
            if grade_min_v is not None and v < grade_min_v:
                continue
            if grade_max_v is not None and v > grade_max_v:
                continue
            filtered.append(c)
        climbs = filtered
    if sort == "stars":
        climbs.sort(key=lambda c: (c.stars if c.stars is not None else -1.0), reverse=True)
    elif sort == "ascents":
        climbs.sort(key=lambda c: (c.ascents if c.ascents is not None else -1), reverse=True)
    elif sort == "grade_asc":
        climbs.sort(key=lambda c: (c.grades.v if c.grades and c.grades.v is not None else 99))
    elif sort == "grade_desc":
        climbs.sort(
            key=lambda c: (c.grades.v if c.grades and c.grades.v is not None else -1),
            reverse=True,
        )
    return climbs


@router.get("/sessions/{code}/climbs", response_model=ClimbsResp)
async def list_climbs(
    code: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[SessionsRepo, Depends(get_sessions_repo)],
    creds_repo: Annotated[CredentialsRepo, Depends(get_credentials_repo)],
    cache_repo: Annotated[ClimbsCacheRepo, Depends(get_climbs_cache_repo)],
    rl: Annotated[RateLimiter, Depends(get_rate_limiter)],
    text: Annotated[str | None, Query()] = None,
    angle: Annotated[int | None, Query()] = None,
    layout_id: Annotated[str | None, Query()] = None,
    provider: Annotated[str | None, Query()] = None,
    holds_required: Annotated[list[str] | None, Query()] = None,
    holds_forbidden: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    cursor: Annotated[str | None, Query()] = None,
    sort: Annotated[str, Query()] = "default",
    stars_min: Annotated[float | None, Query(ge=0, le=5)] = None,
    grade_min_v: Annotated[int | None, Query(ge=0, le=17)] = None,
    grade_max_v: Annotated[int | None, Query(ge=0, le=17)] = None,
    read_token: Annotated[str | None, Header(alias="X-Session-Read-Token")] = None,
):
    rl.check(client_key(request), "list_climbs", settings.rl_climbs_per_min)
    if sort not in _ALLOWED_SORTS:
        raise HTTPException(400, {"error": "bad_sort", "detail": sorted(_ALLOWED_SORTS)})
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    _require_read_token(read_token, row)
    provider = _select_provider(row, provider)
    try:
        p = registry.get(provider)
    except KeyError:
        raise HTTPException(400, {"error": "unknown_provider"}) from None

    # Hash only the query shape (not offset/limit) so cursor stays valid while paging.
    shape_params: dict[str, Any] = {
        "text": text,
        "angle": angle,
        "layout_id": layout_id,
        "holds_required": holds_required or [],
        "holds_forbidden": holds_forbidden or [],
        "sort": sort,
        "stars_min": stars_min,
        "grade_min_v": grade_min_v,
        "grade_max_v": grade_max_v,
    }
    query_hash = _cache_key(code, "climbs_shape", shape_params)

    if cursor is not None:
        offset = _decode_cursor(cursor, query_hash)

    overfetch = (
        min(max(limit * _MAX_OVERFETCH_MULTIPLIER, limit), _MAX_OVERFETCH_CAP)
        if (
            stars_min is not None
            or grade_min_v is not None
            or grade_max_v is not None
            or sort != "default"
        )
        else limit
    )

    cache_key_params = dict(shape_params)
    cache_key_params["limit"] = overfetch
    cache_key_params["offset"] = offset
    cache_key = _cache_key(code, "climbs", cache_key_params)
    cached = await cache_repo.get(provider, cache_key)
    if cached is not None:
        cached_climbs = [ClimbOut(**c) for c in cached]
        filtered = _apply_post_filters(
            cached_climbs,
            sort=sort,
            stars_min=stars_min,
            grade_min_v=grade_min_v,
            grade_max_v=grade_max_v,
        )
        window = filtered[:limit]
        next_cursor = (
            _encode_cursor(offset + overfetch, query_hash)
            if len(cached_climbs) >= overfetch
            else None
        )
        await repo.touch(code)
        return ClimbsResp(climbs=window, next_cursor=next_cursor)

    token = await _auth_token(code, provider, p, creds_repo)

    try:
        climbs = await p.search_climbs(
            token,
            ClimbQuery(
                layout_id=layout_id,
                angle=angle,
                text=text,
                holds_required=tuple(holds_required or ()),
                holds_forbidden=tuple(holds_forbidden or ()),
                limit=overfetch,
                offset=offset,
            ),
        )
    except ProviderUnavailable as e:
        raise HTTPException(503, {"error": "provider_unavailable", "detail": str(e)}) from e
    except ProviderAuthError as e:
        raise HTTPException(400, {"error": "auth_failed", "detail": str(e)}) from e

    enriched = [_enrich(c) for c in climbs]
    payload = [c.model_dump() for c in enriched]
    await cache_repo.put(provider, cache_key, payload, settings.cache_ttl_seconds)

    filtered = _apply_post_filters(
        enriched,
        sort=sort,
        stars_min=stars_min,
        grade_min_v=grade_min_v,
        grade_max_v=grade_max_v,
    )
    window = filtered[:limit]
    next_cursor = (
        _encode_cursor(offset + overfetch, query_hash)
        if len(climbs) >= overfetch
        else None
    )
    await repo.touch(code)
    return ClimbsResp(climbs=window, next_cursor=next_cursor)


@router.get("/sessions/{code}/layouts", response_model=LayoutsResp)
async def list_layouts(
    code: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[SessionsRepo, Depends(get_sessions_repo)],
    creds_repo: Annotated[CredentialsRepo, Depends(get_credentials_repo)],
    cache_repo: Annotated[ClimbsCacheRepo, Depends(get_climbs_cache_repo)],
    rl: Annotated[RateLimiter, Depends(get_rate_limiter)],
    provider: Annotated[str | None, Query()] = None,
    read_token: Annotated[str | None, Header(alias="X-Session-Read-Token")] = None,
):
    rl.check(client_key(request), "list_layouts", settings.rl_layouts_per_min)
    row = await repo.get(code)
    if not row or row["ended_at"]:
        raise HTTPException(404, {"error": "not_found"})
    _require_read_token(read_token, row)
    provider = _select_provider(row, provider)
    try:
        p = registry.get(provider)
    except KeyError:
        raise HTTPException(400, {"error": "unknown_provider"}) from None

    cache_key = _cache_key(code, "layouts", {})
    cached = await cache_repo.get(provider, cache_key)
    if cached is not None:
        await repo.touch(code)
        return LayoutsResp(layouts=[LayoutOut(**layout) for layout in cached])

    token = await _auth_token(code, provider, p, creds_repo)
    try:
        layouts = await p.list_layouts(token)
    except ProviderUnavailable as e:
        raise HTTPException(503, {"error": "provider_unavailable", "detail": str(e)}) from e
    except ProviderAuthError as e:
        raise HTTPException(400, {"error": "auth_failed", "detail": str(e)}) from e

    payload = [
        LayoutOut(
            id=layout.id,
            name=layout.name,
            angles=layout.angles,
            extras=layout.extras,
        ).model_dump()
        for layout in layouts
    ]
    await cache_repo.put(provider, cache_key, payload, settings.cache_ttl_seconds)
    await repo.touch(code)
    return LayoutsResp(layouts=[LayoutOut(**layout) for layout in payload])
