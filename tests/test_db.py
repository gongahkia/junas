from kt.db import db, init_db, close_db


async def test_migrations_apply(tmp_path):
    p = tmp_path / "x.db"
    await init_db(p)
    try:
        async with db().execute("SELECT version FROM schema_version") as cur:
            versions = [r[0] async for r in cur]
        assert 1 in versions
        async with db().execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
            tables = {r[0] async for r in cur}
        for t in ("sessions", "host_credentials", "climbs_cache", "ws_tokens"):
            assert t in tables
    finally:
        await close_db()


async def test_migrations_idempotent(tmp_path):
    p = tmp_path / "y.db"
    await init_db(p)
    await close_db()
    await init_db(p)
    try:
        async with db().execute("SELECT COUNT(*) FROM schema_version") as cur:
            (n,) = await cur.fetchone()
        assert n == 1
    finally:
        await close_db()
