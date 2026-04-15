from contextlib import asynccontextmanager

from fastapi import FastAPI

from kt.api.health import router as health_router
from kt.config import Settings
from kt.db import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    await init_db(settings.db_path)
    try:
        yield
    finally:
        await close_db()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Kilter Together", version="2.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health_router)
    return app


app = create_app()
