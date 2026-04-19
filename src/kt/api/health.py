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
async def readyz(request: Request) -> dict[str, object]:
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
    provider_statuses = {
        p["key"]: {
            "status": p["status"],
            "source": p.get("source"),
            "capabilities": p.get("capabilities") or {},
            "status_reason": p.get("status_reason"),
        }
        for p in registry.describe()
    }
    rl = getattr(request.app.state, "rate_limiter", None)
    rl_status = rl.status() if rl and hasattr(rl, "status") else {}
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "rate_limiter_backend": rl_status.get(
            "active_backend",
            getattr(request.app.state.settings, "rl_backend", "in_memory"),
        ),
        "rate_limiter_configured_backend": rl_status.get(
            "configured_backend",
            getattr(request.app.state.settings, "rl_backend", "in_memory"),
        ),
        "rate_limiter_error": rl_status.get("last_backend_error"),
        "providers": provider_statuses,
        "provider_count": len(provider_statuses),
        "active_sessions": active_sessions,
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(request: Request) -> PlainTextResponse:
    m = getattr(request.app.state, "metrics", None)
    if m is None:
        return PlainTextResponse("# metrics disabled\n", media_type="text/plain")
    return PlainTextResponse(m.expose(), media_type="text/plain; version=0.0.4")
