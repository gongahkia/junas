from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from kt.db import db
from kt.providers import registry

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, object]:
    db_ok = True
    active_sessions = 0
    try:
        async with db().execute("SELECT 1") as cur:
            await cur.fetchone()
        async with db().execute(
            "SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL"
        ) as cur:
            row = await cur.fetchone()
        active_sessions = int(row[0]) if row else 0
    except Exception:
        db_ok = False
    provider_statuses = {p.key: p.status.value for p in registry.all_providers()}
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "providers": provider_statuses,
        "active_sessions": active_sessions,
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(request: Request) -> PlainTextResponse:
    m = getattr(request.app.state, "metrics", None)
    if m is None:
        return PlainTextResponse("# metrics disabled\n", media_type="text/plain")
    return PlainTextResponse(m.expose(), media_type="text/plain; version=0.0.4")
