from datetime import datetime, timedelta, timezone

from kt.db import db
from kt.repos.credentials_repo import CredentialsRepo
from kt.repos.sessions_repo import SessionsRepo
from kt.security import CredentialCipher, hash_secret
from kt.sweeper import sweep_once


async def test_sweep_ends_idle_and_drops_creds(db_ready, cred_key):
    repo = SessionsRepo()
    creds = CredentialsRepo(CredentialCipher(cred_key))

    await repo.create("OLDONE", "h1", hash_secret("s"), ["tension"], {})
    await repo.create("FRESH1", "h2", hash_secret("s"), ["tension"], {})
    await creds.put("OLDONE", "tension", {"u": "x"})
    await creds.put("FRESH1", "tension", {"u": "y"})

    old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    await db().execute("UPDATE sessions SET updated_at=? WHERE code=?", (old, "OLDONE"))
    await db().commit()

    n = await sweep_once(idle_max_hours=24)
    assert n == 1
    assert (await repo.get("OLDONE"))["ended_at"] is not None
    assert (await repo.get("FRESH1"))["ended_at"] is None
    assert await creds.get("OLDONE", "tension") is None
    assert await creds.get("FRESH1", "tension") == {"u": "y"}
