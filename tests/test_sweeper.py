from datetime import UTC, datetime, timedelta

from kt.db import db
from kt.repos.climbs_cache_repo import ClimbsCacheRepo
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.security import CredentialCipher, hash_secret
from kt.sweeper import sweep_once


async def test_sweep_ends_idle_and_drops_creds(db_ready, cred_key):
    repo = SessionsRepo()
    creds = CredentialsRepo(CredentialCipher(cred_key))

    await repo.create("OLDONE", "h1", hash_secret("s"), "tension", {})
    await repo.create("FRESH1", "h2", hash_secret("s"), "tension", {})
    await creds.put("OLDONE", "tension", {"u": "x"})
    await creds.put("FRESH1", "tension", {"u": "y"})

    old = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    await db().execute("UPDATE sessions SET updated_at=? WHERE code=?", (old, "OLDONE"))
    await db().commit()

    n = await sweep_once(idle_max_hours=24)
    assert n == 1
    assert (await repo.get("OLDONE"))["ended_at"] is not None
    assert (await repo.get("FRESH1"))["ended_at"] is None
    assert await creds.get("OLDONE", "tension") is None
    assert await creds.get("FRESH1", "tension") == {"u": "y"}


async def test_sweep_prunes_expired_tokens_and_cache(db_ready):
    repo = SessionsRepo()
    await repo.create("TOKENS", "h1", hash_secret("s"), "moonboard_catalog", {})
    await repo.put_ws_token("expired", "TOKENS", "h1", ttl_seconds=-1)
    await repo.put_ws_token("fresh", "TOKENS", "h1", ttl_seconds=60)

    cache = ClimbsCacheRepo()
    await cache.put("moonboard_catalog", "expired", {"x": 1}, ttl_seconds=-1)
    await cache.put("moonboard_catalog", "fresh", {"x": 2}, ttl_seconds=60)

    await sweep_once(idle_max_hours=24)

    assert await repo.consume_ws_token("expired") is None
    assert await repo.consume_ws_token("fresh") == {
        "session_code": "TOKENS",
        "participant_id": "h1",
    }
    assert await cache.get("moonboard_catalog", "expired") is None
    assert await cache.get("moonboard_catalog", "fresh") == {"x": 2}
