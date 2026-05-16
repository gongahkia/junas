from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from kt.boards.loader import ingest_geojson
from kt.config import Settings
from kt.logging import log


@dataclass(frozen=True)
class SyncResult:
    loaded: int
    source_name: str
    source_url: str | None
    source_version: str | None
    source_updated_at: str | None
    mode: str


async def sync_boards(settings: Settings, *, mode: str = "configured") -> SyncResult:
    selected_mode = _resolve_mode(settings, mode)
    if selected_mode == "sample":
        loaded = await ingest_geojson(
            source_name="bundled_sample",
            source_url=None,
            source_version=None,
            source_updated_at=None,
            ingestion_mode="sample",
        )
        return SyncResult(
            loaded=loaded,
            source_name="bundled_sample",
            source_url=None,
            source_version=None,
            source_updated_at=None,
            mode="sample",
        )

    raw, source_version, source_updated_at = await _fetch_remote_geojson(settings)
    loaded = await ingest_geojson(
        raw_text=raw,
        source_name=settings.boards_source_name,
        source_url=settings.boards_source_url or None,
        source_version=source_version,
        source_updated_at=source_updated_at,
        ingestion_mode="remote",
    )
    return SyncResult(
        loaded=loaded,
        source_name=settings.boards_source_name,
        source_url=settings.boards_source_url or None,
        source_version=source_version,
        source_updated_at=source_updated_at,
        mode="remote",
    )


async def run_forever(settings: Settings) -> None:
    interval = max(60, int(settings.boards_sync_interval_seconds))
    while True:
        try:
            result = await sync_boards(settings, mode="configured")
            log().info(
                "boards_sync.completed",
                loaded=result.loaded,
                source_name=result.source_name,
                source_version=result.source_version,
                mode=result.mode,
            )
        except Exception as e:
            log().warning("boards_sync.failed", error=str(e))
        await _sleep(interval)


async def _fetch_remote_geojson(settings: Settings) -> tuple[str, str | None, str | None]:
    url = (settings.boards_source_url or "").strip()
    if not url:
        raise RuntimeError("KT_BOARDS_SOURCE_URL must be set for remote sync mode")

    timeout = max(5, int(settings.boards_sync_timeout_seconds))
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
    response.raise_for_status()
    raw = response.text
    # Validate shape up front before mutating DB.
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise RuntimeError("remote board source is not a GeoJSON FeatureCollection")

    etag = response.headers.get("etag")
    version = etag.strip('"') if etag else hashlib.sha256(raw.encode("utf-8")).hexdigest()
    source_updated_at = response.headers.get("last-modified")
    if not source_updated_at:
        maybe_ts = payload.get("updated_at") or payload.get("generated_at")
        if maybe_ts:
            source_updated_at = str(maybe_ts)
        else:
            source_updated_at = datetime.now(UTC).isoformat()
    return raw, version, source_updated_at


def _resolve_mode(settings: Settings, mode: str) -> str:
    selected = (mode or "configured").strip().lower()
    if selected == "configured":
        selected = (settings.boards_source_mode or "sample").strip().lower()
    if selected not in {"sample", "remote", "auto"}:
        raise RuntimeError(f"unsupported boards sync mode: {selected}")
    if selected == "auto":
        return "remote" if (settings.boards_source_url or "").strip() else "sample"
    return selected


async def _sleep(seconds: int) -> None:
    import asyncio

    await asyncio.sleep(seconds)

