from kt.repos.sessions_repo import SessionsRepo
from kt.security import hash_secret


async def test_create_get_save(db_ready):
    repo = SessionsRepo()
    await repo.create("ABCDEF", "h1", hash_secret("s"), "tension", {"foo": 1})
    row = await repo.get("ABCDEF")
    assert row["host_participant_id"] == "h1"
    assert row["provider"] == "tension"
    assert row["state"] == {"foo": 1}

    await repo.save_state("ABCDEF", {"foo": 2})
    row = await repo.get("ABCDEF")
    assert row["state"] == {"foo": 2}

    await repo.end("ABCDEF")
    row = await repo.get("ABCDEF")
    assert row["ended_at"] is not None


async def test_ws_token_one_shot(db_ready):
    repo = SessionsRepo()
    await repo.create("XYZ123", "h1", hash_secret("s"), "tension", {})
    await repo.put_ws_token("tk", "XYZ123", "p1", ttl_seconds=60)
    claim = await repo.consume_ws_token("tk")
    assert claim == {"session_code": "XYZ123", "participant_id": "p1"}
    assert await repo.consume_ws_token("tk") is None  # one-shot
