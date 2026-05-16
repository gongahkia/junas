from kt.repos.sessions_repo import SessionsRepo
from kt.security import hash_secret


async def test_create_get_save(db_ready):
    repo = SessionsRepo()
    await repo.create(
        "ABCDEF",
        "h1",
        hash_secret("s"),
        hash_secret("r"),
        "tension",
        {"foo": 1},
    )
    row = await repo.get("ABCDEF")
    assert row["host_participant_id"] == "h1"
    assert row["provider"] == "tension"
    assert row["state"] == {"foo": 1}
    assert row["read_token_hash"] == hash_secret("r")

    await repo.save_state("ABCDEF", {"foo": 2})
    row = await repo.get("ABCDEF")
    assert row["state"] == {"foo": 2}

    await repo.end("ABCDEF")
    row = await repo.get("ABCDEF")
    assert row["ended_at"] is not None
