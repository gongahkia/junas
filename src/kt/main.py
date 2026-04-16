import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware

from kt.api.auth import me_router
from kt.api.auth import router as auth_router
from kt.api.boards import router as boards_router
from kt.api.boards_directory import router as boards_directory_router
from kt.api.grades import router as grades_router
from kt.api.health import router as health_router
from kt.api.logbook import router as logbook_router
from kt.api.sessions import router as sessions_router
from kt.api.ws import router as ws_router
from kt.boards.loader import ingest_geojson
from kt.config import Settings
from kt.db import close_db, init_db
from kt.logging import configure_logging, log
from kt.metrics import Metrics
from kt.providers import registry
from kt.ratelimit import RateLimiter
from kt.realtime.hub import SessionHub
from kt.repos.boards_repo import BoardsRepo
from kt.repos.climb_votes_repo import ClimbVotesRepo
from kt.repos.logbook_repo import LogbookRepo
from kt.repos.session_events_repo import SessionEventsRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.sweeper import run_forever as sweeper_run_forever

LEGACY_API_SUNSET = "Wed, 01 Jul 2026 00:00:00 GMT"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    if not settings.cred_key:  # dev convenience: ephemeral key + warning (creds lost on restart)
        from cryptography.fernet import Fernet
        settings.cred_key = Fernet.generate_key().decode()
        log().warning("cred_key_autogen", msg="KT_CRED_KEY unset — generated ephemeral key; set KT_CRED_KEY to persist credentials across restarts")
    await init_db(settings.db_path)
    registry.bootstrap()
    app.state.hub = SessionHub(
        SessionsRepo(),
        SessionEventsRepo(),
        logbook_repo=LogbookRepo(),
        votes_repo=ClimbVotesRepo(),
    )
    app.state.rate_limiter = RateLimiter()
    app.state.metrics = Metrics()
    if await BoardsRepo().count() == 0 and settings.boards_autoload_sample:
        try:
            loaded = await ingest_geojson()
            log().info("boards_autoload", loaded=loaded)
        except Exception as e:
            log().warning("boards_autoload_failed", error=str(e))
    sweeper = asyncio.create_task(
        sweeper_run_forever(settings.session_idle_max_hours, settings.sweep_interval_seconds)
    )
    log().info("startup", db=str(settings.db_path), providers=len(registry.all_providers()))
    try:
        yield
    finally:
        sweeper.cancel()
        try:
            await sweeper
        except (asyncio.CancelledError, Exception):
            pass
        await close_db()


async def _legacy_api_deprecation(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/v1/"):
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = LEGACY_API_SUNSET
        response.headers["Link"] = (
            f'<{path.replace("/api/", "/api/v1/", 1)}>; rel="successor-version"'
        )
    return response


async def _metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    metrics: Metrics | None = getattr(request.app.state, "metrics", None)
    if metrics is not None:
        route = request.scope.get("route")
        # Prefer the template path (e.g. /api/v1/sessions/{code}) over the literal URL.
        route_path = getattr(route, "path", None) or request.url.path
        metrics.observe_http(
            method=request.method,
            route=route_path,
            status=response.status_code,
            duration=elapsed,
        )
    return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Kilter Together", version="2.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.middleware("http")(_metrics_middleware)
    app.middleware("http")(_legacy_api_deprecation)
    app.include_router(health_router)
    app.include_router(ws_router)
    for prefix in ("/api/v1", "/api"):
        app.include_router(sessions_router, prefix=prefix)
        app.include_router(boards_router, prefix=prefix)
        app.include_router(auth_router, prefix=prefix)
        app.include_router(me_router, prefix=prefix)
        app.include_router(grades_router, prefix=prefix)
        app.include_router(logbook_router, prefix=prefix)
        app.include_router(boards_directory_router, prefix=prefix)
    return app


app = create_app()
