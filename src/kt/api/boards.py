from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
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
    Layout,
    ProviderAuthError,
    ProviderUnavailable,
)
from kt.ratelimit import RateLimiter, client_key
from kt.repos.climbs_cache_repo import ClimbsCacheRepo
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.schemas.api import (
    CacheMeta,
    ClimbOut,
    ClimbsResp,
    GradeOut,
    LayoutOut,
    LayoutsResp,
    MediaRef,
    ProviderDescriptor,
    ProviderWarning,
    ResponseMeta,
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


def _resolve_providers(row: dict, provider: str | None) -> tuple[list[str], bool]:
    enabled_providers = row["enabled_providers"]
    if provider is None:
        return enabled_providers, len(enabled_providers) > 1
    if provider not in enabled_providers:
        raise HTTPException(400, {"error": "provider_not_enabled", "detail": enabled_providers})
    return [provider], False


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


def _with_provenance(
    extras: dict[str, Any] | None,
    *,
    provider: str,
    fetched_at: str,
    normalized_fields: list[str],
) -> dict[str, Any]:
    out = dict(extras or {})
    out["_provenance"] = {
        "source_provider": provider,
        "fetched_at": fetched_at,
        "normalized_fields": normalized_fields,
    }
    return out


def _enrich(climb: Climb, fetched_at: str) -> ClimbOut:
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
        extras=_with_provenance(
            climb.extras,
            provider=climb.provider,
            fetched_at=fetched_at,
            normalized_fields=["name", "grade", "angle", "ascents", "holds"],
        ),
    )


def _layout_out(layout: Layout, provider: str, fetched_at: str) -> LayoutOut:
    return LayoutOut(
        id=layout.id,
        name=layout.name,
        angles=layout.angles,
        extras=_with_provenance(
            layout.extras,
            provider=provider,
            fetched_at=fetched_at,
            normalized_fields=["id", "name", "angles"],
        ),
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


def _warning(
    provider: str,
    *,
    error: str,
    detail: str | None = None,
    stale_cache_served: bool = False,
) -> ProviderWarning:
    return ProviderWarning(
        provider=provider,
        error=error,
        detail=detail,
        stale_cache_served=stale_cache_served,
    )


def _classify_unavailable(detail: str | None) -> str:
    lower = (detail or "").lower()
    if "timeout" in lower:
        return "provider_timeout"
    if "network" in lower:
        return "provider_network_error"
    return "provider_unavailable"


def _cache_meta_from_entry(entry: dict[str, Any], *, hit: bool) -> CacheMeta:
    return CacheMeta(
        hit=hit,
        stale=bool(entry.get("stale")),
        cached_at=entry.get("created_at"),
        expires_at=entry.get("expires_at"),
    )


def _merge_cache_meta(metas: list[CacheMeta]) -> CacheMeta:
    if not metas:
        return CacheMeta(hit=False, stale=False)
    cached_ats = [m.cached_at for m in metas if m.cached_at]
    expires_ats = [m.expires_at for m in metas if m.expires_at]
    return CacheMeta(
        hit=all(m.hit for m in metas),
        stale=any(m.stale for m in metas),
        cached_at=min(cached_ats) if cached_ats else None,
        expires_at=min(expires_ats) if expires_ats else None,
    )


def _overfetch_limit(
    *,
    limit: int,
    sort: str,
    stars_min: float | None,
    grade_min_v: int | None,
    grade_max_v: int | None,
) -> int:
    if (
        stars_min is not None
        or grade_min_v is not None
        or grade_max_v is not None
        or sort != "default"
    ):
        return min(max(limit * _MAX_OVERFETCH_MULTIPLIER, limit), _MAX_OVERFETCH_CAP)
    return limit


def _cache_expiry_iso(fetched_at: str, ttl_seconds: int) -> str:
    return (datetime.fromisoformat(fetched_at) + timedelta(seconds=ttl_seconds)).isoformat()


def _response_meta(provider: str, cache: CacheMeta, served_by: list[str]) -> ResponseMeta:
    return ResponseMeta(
        provider=provider,
        fetched_at=datetime.now(UTC).isoformat(),
        cache=cache,
        served_by=served_by,
    )


async def _auth_token_for_provider(
    *,
    code: str,
    provider_key: str,
    provider: BoardProvider,
    creds_repo: CredentialsRepo,
) -> tuple[AuthToken | None, ProviderWarning | None]:
    if not provider.requires_credentials:
        return None, None
    creds = await creds_repo.get(code, provider_key)
    if creds is None:
        return None, _warning(provider_key, error="no_credentials_for_provider")
    try:
        token = await provider.authenticate(creds)
        return token, None
    except ProviderAuthError as e:
        return None, _warning(provider_key, error="auth_failed", detail=str(e))
    except ProviderUnavailable as e:
        return None, _warning(
            provider_key,
            error=_classify_unavailable(str(e)),
            detail=str(e),
        )


async def _fetch_climbs_for_provider(
    *,
    code: str,
    provider_key: str,
    query: ClimbQuery,
    cache_key: str,
    settings: Settings,
    creds_repo: CredentialsRepo,
    cache_repo: ClimbsCacheRepo,
) -> tuple[list[ClimbOut], CacheMeta, int, ProviderWarning | None]:
    try:
        provider = registry.get(provider_key)
    except KeyError:
        return [], CacheMeta(hit=False, stale=False), 0, _warning(
            provider_key,
            error="unknown_provider",
        )

    fresh_entry = await cache_repo.get_with_meta(provider_key, cache_key, allow_stale=False)
    if fresh_entry is not None:
        climbs = [ClimbOut(**c) for c in fresh_entry["payload"]]
        return climbs, _cache_meta_from_entry(fresh_entry, hit=True), len(climbs), None

    token, auth_warning = await _auth_token_for_provider(
        code=code,
        provider_key=provider_key,
        provider=provider,
        creds_repo=creds_repo,
    )
    if auth_warning is not None:
        stale_entry = await cache_repo.get_with_meta(provider_key, cache_key, allow_stale=True)
        if stale_entry is not None:
            climbs = [ClimbOut(**c) for c in stale_entry["payload"]]
            return climbs, _cache_meta_from_entry(stale_entry, hit=True), len(climbs), _warning(
                provider_key,
                error=auth_warning.error,
                detail=auth_warning.detail,
                stale_cache_served=True,
            )
        return [], CacheMeta(hit=False, stale=False), 0, auth_warning

    try:
        climbs_raw = await provider.search_climbs(token, query)
    except ProviderUnavailable as e:
        stale_entry = await cache_repo.get_with_meta(provider_key, cache_key, allow_stale=True)
        if stale_entry is not None:
            climbs = [ClimbOut(**c) for c in stale_entry["payload"]]
            return climbs, _cache_meta_from_entry(stale_entry, hit=True), len(climbs), _warning(
                provider_key,
                error=_classify_unavailable(str(e)),
                detail=str(e),
                stale_cache_served=True,
            )
        return [], CacheMeta(hit=False, stale=False), 0, _warning(
            provider_key,
            error=_classify_unavailable(str(e)),
            detail=str(e),
        )
    except ProviderAuthError as e:
        stale_entry = await cache_repo.get_with_meta(provider_key, cache_key, allow_stale=True)
        if stale_entry is not None:
            climbs = [ClimbOut(**c) for c in stale_entry["payload"]]
            return climbs, _cache_meta_from_entry(stale_entry, hit=True), len(climbs), _warning(
                provider_key,
                error="auth_failed",
                detail=str(e),
                stale_cache_served=True,
            )
        return [], CacheMeta(hit=False, stale=False), 0, _warning(
            provider_key,
            error="auth_failed",
            detail=str(e),
        )

    fetched_at = datetime.now(UTC).isoformat()
    climbs = [_enrich(c, fetched_at) for c in climbs_raw]
    payload = [c.model_dump() for c in climbs]
    await cache_repo.put(provider_key, cache_key, payload, settings.cache_ttl_seconds)
    return climbs, CacheMeta(
        hit=False,
        stale=False,
        cached_at=fetched_at,
        expires_at=_cache_expiry_iso(fetched_at, settings.cache_ttl_seconds),
    ), len(climbs_raw), None


async def _fetch_layouts_for_provider(
    *,
    code: str,
    provider_key: str,
    cache_key: str,
    settings: Settings,
    creds_repo: CredentialsRepo,
    cache_repo: ClimbsCacheRepo,
) -> tuple[list[LayoutOut], CacheMeta, ProviderWarning | None]:
    try:
        provider = registry.get(provider_key)
    except KeyError:
        return [], CacheMeta(hit=False, stale=False), _warning(provider_key, error="unknown_provider")

    fresh_entry = await cache_repo.get_with_meta(provider_key, cache_key, allow_stale=False)
    if fresh_entry is not None:
        layouts = [LayoutOut(**layout) for layout in fresh_entry["payload"]]
        return layouts, _cache_meta_from_entry(fresh_entry, hit=True), None

    token, auth_warning = await _auth_token_for_provider(
        code=code,
        provider_key=provider_key,
        provider=provider,
        creds_repo=creds_repo,
    )
    if auth_warning is not None:
        stale_entry = await cache_repo.get_with_meta(provider_key, cache_key, allow_stale=True)
        if stale_entry is not None:
            layouts = [LayoutOut(**layout) for layout in stale_entry["payload"]]
            return layouts, _cache_meta_from_entry(stale_entry, hit=True), _warning(
                provider_key,
                error=auth_warning.error,
                detail=auth_warning.detail,
                stale_cache_served=True,
            )
        return [], CacheMeta(hit=False, stale=False), auth_warning

    try:
        layouts_raw = await provider.list_layouts(token)
    except ProviderUnavailable as e:
        stale_entry = await cache_repo.get_with_meta(provider_key, cache_key, allow_stale=True)
        if stale_entry is not None:
            layouts = [LayoutOut(**layout) for layout in stale_entry["payload"]]
            return layouts, _cache_meta_from_entry(stale_entry, hit=True), _warning(
                provider_key,
                error=_classify_unavailable(str(e)),
                detail=str(e),
                stale_cache_served=True,
            )
        return [], CacheMeta(hit=False, stale=False), _warning(
            provider_key,
            error=_classify_unavailable(str(e)),
            detail=str(e),
        )
    except ProviderAuthError as e:
        stale_entry = await cache_repo.get_with_meta(provider_key, cache_key, allow_stale=True)
        if stale_entry is not None:
            layouts = [LayoutOut(**layout) for layout in stale_entry["payload"]]
            return layouts, _cache_meta_from_entry(stale_entry, hit=True), _warning(
                provider_key,
                error="auth_failed",
                detail=str(e),
                stale_cache_served=True,
            )
        return [], CacheMeta(hit=False, stale=False), _warning(
            provider_key,
            error="auth_failed",
            detail=str(e),
        )

    fetched_at = datetime.now(UTC).isoformat()
    layouts = [_layout_out(layout, provider_key, fetched_at) for layout in layouts_raw]
    payload = [layout.model_dump() for layout in layouts]
    await cache_repo.put(provider_key, cache_key, payload, settings.cache_ttl_seconds)
    return layouts, CacheMeta(
        hit=False,
        stale=False,
        cached_at=fetched_at,
        expires_at=_cache_expiry_iso(fetched_at, settings.cache_ttl_seconds),
    ), None


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

    provider_keys, is_multi = _resolve_providers(row, provider)

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

    if is_multi and cursor is not None:
        raise HTTPException(400, {"error": "cursor_requires_provider"})

    if cursor is not None:
        offset = _decode_cursor(cursor, query_hash)

    overfetch = _overfetch_limit(
        limit=limit,
        sort=sort,
        stars_min=stars_min,
        grade_min_v=grade_min_v,
        grade_max_v=grade_max_v,
    )

    all_climbs: list[ClimbOut] = []
    warnings: list[ProviderWarning] = []
    cache_metas: list[CacheMeta] = []
    served_by: list[str] = []
    max_raw_count = 0

    for provider_key in provider_keys:
        cache_key_params = dict(shape_params)
        cache_key_params["limit"] = overfetch
        cache_key_params["offset"] = offset
        cache_key = _cache_key(code, "climbs", cache_key_params)

        climbs, cache_meta, raw_count, warning = await _fetch_climbs_for_provider(
            code=code,
            provider_key=provider_key,
            query=ClimbQuery(
                layout_id=layout_id,
                angle=angle,
                text=text,
                holds_required=tuple(holds_required or ()),
                holds_forbidden=tuple(holds_forbidden or ()),
                limit=overfetch,
                offset=offset,
            ),
            cache_key=cache_key,
            settings=settings,
            creds_repo=creds_repo,
            cache_repo=cache_repo,
        )
        if climbs:
            all_climbs.extend(climbs)
            served_by.append(provider_key)
        cache_metas.append(cache_meta)
        max_raw_count = max(max_raw_count, raw_count)
        if warning is not None:
            warnings.append(warning)

    if not is_multi and not all_climbs and warnings:
        first = warnings[0]
        if first.error in {"auth_failed", "no_credentials_for_provider"}:
            raise HTTPException(400, {"error": first.error, "detail": first.detail})
        raise HTTPException(503, {"error": first.error, "detail": first.detail})

    filtered = _apply_post_filters(
        all_climbs,
        sort=sort,
        stars_min=stars_min,
        grade_min_v=grade_min_v,
        grade_max_v=grade_max_v,
    )
    window = filtered[:limit]

    next_cursor = None
    if not is_multi and max_raw_count >= overfetch:
        next_cursor = _encode_cursor(offset + overfetch, query_hash)

    await repo.touch(code)
    return ClimbsResp(
        climbs=window,
        next_cursor=next_cursor,
        meta=_response_meta(
            "multi" if is_multi else provider_keys[0],
            _merge_cache_meta(cache_metas),
            served_by,
        ),
        warnings=warnings,
    )


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

    provider_keys, is_multi = _resolve_providers(row, provider)

    all_layouts: list[LayoutOut] = []
    warnings: list[ProviderWarning] = []
    cache_metas: list[CacheMeta] = []
    served_by: list[str] = []

    for provider_key in provider_keys:
        cache_key = _cache_key(code, "layouts", {})
        layouts, cache_meta, warning = await _fetch_layouts_for_provider(
            code=code,
            provider_key=provider_key,
            cache_key=cache_key,
            settings=settings,
            creds_repo=creds_repo,
            cache_repo=cache_repo,
        )
        if layouts:
            all_layouts.extend(layouts)
            served_by.append(provider_key)
        cache_metas.append(cache_meta)
        if warning is not None:
            warnings.append(warning)

    if not is_multi and not all_layouts and warnings:
        first = warnings[0]
        if first.error in {"auth_failed", "no_credentials_for_provider"}:
            raise HTTPException(400, {"error": first.error, "detail": first.detail})
        raise HTTPException(503, {"error": first.error, "detail": first.detail})

    await repo.touch(code)
    return LayoutsResp(
        layouts=all_layouts,
        meta=_response_meta(
            "multi" if is_multi else provider_keys[0],
            _merge_cache_meta(cache_metas),
            served_by,
        ),
        warnings=warnings,
    )
