from __future__ import annotations

from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

import aiosqlite

_db: aiosqlite.Connection | None = None
_db_path: Path | None = None


async def init_db(path: Path) -> None:
    global _db, _db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    _db_path = path
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")
    await _db.commit()
    await _run_migrations(_db)


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("db not initialized")
    return _db


async def _applied_versions(conn: aiosqlite.Connection) -> set[int]:
    async with conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ) as cur:
        if not await cur.fetchone():
            return set()
    async with conn.execute("SELECT version FROM schema_version") as cur:
        return {row[0] async for row in cur}


async def _run_migrations(conn: aiosqlite.Connection) -> None:
    applied = await _applied_versions(conn)
    files = sorted(
        (p for p in resources.files("kt.migrations").iterdir() if p.name.endswith(".sql")),
        key=lambda p: p.name,
    )
    for f in files:
        version = int(f.name.split("_", 1)[0])
        if version in applied:
            continue
        sql = f.read_text()
        await conn.executescript(sql)
        await conn.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
            (version, datetime.now(UTC).isoformat()),
        )
        await conn.commit()
