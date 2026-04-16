from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from kt.config import Settings
from kt.db import close_db, init_db
from kt.main import create_app


@pytest.fixture
def cred_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def settings(tmp_path: Path, cred_key: str) -> Settings:
    return Settings(
        db_path=tmp_path / "test.db",
        cred_key=cred_key,
        boards_reload_secret="reload-secret",
    )


@pytest.fixture
async def db_ready(settings: Settings) -> AsyncIterator[None]:
    await init_db(settings.db_path)
    try:
        yield
    finally:
        await close_db()


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            yield ac


@pytest.fixture(autouse=True)
def _env_cleanup():
    keep = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(keep)
