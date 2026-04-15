from contextlib import asynccontextmanager

from fastapi import FastAPI

from kt.api.boards import router as boards_router
from kt.api.health import router as health_router
from kt.api.sessions import router as sessions_router
from kt.api.ws import router as ws_router
import asyncio

from kt.config import Settings
from kt.db import close_db, init_db
from kt.logging import configure_logging, log
from kt.providers import registry
from kt.ratelimit import RateLimiter
from kt.realtime.hub import SessionHub
from kt.repos.sessions_repo import SessionsRepo
from kt.sweeper import run_forever as sweeper_run_forever


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    configure_logging(settings.log_level)
    await init_db(settings.db_path)
    registry.bootstrap()
    app.state.hub = SessionHub(SessionsRepo())
    app.state.rate_limiter = RateLimiter()
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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Kilter Together", version="2.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(boards_router)
    app.include_router(ws_router)
    return app


app = create_app()
