from __future__ import annotations

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


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("db not initialized")
    return _db
