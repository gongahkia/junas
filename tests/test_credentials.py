from datetime import UTC

from cryptography.fernet import Fernet

from kt.repos.credentials_repo import CredentialsRepo
from kt.security import CredentialCipher, hash_secret, new_secret, verify_secret


def test_cipher_roundtrip():
    key = Fernet.generate_key().decode()
    c = CredentialCipher(key)
    payload = {"username": "u", "password": "p"}
    enc = c.encrypt(payload)
    assert enc != "u" and "password" not in enc
    assert c.decrypt(enc) == payload


def test_cipher_rejects_empty_key():
    try:
        CredentialCipher("")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_secret_helpers():
    s = new_secret()
    assert len(s) > 20
    assert verify_secret(s, hash_secret(s))
    assert not verify_secret(s + "x", hash_secret(s))


async def test_repo_put_get_delete(db_ready, cred_key):
    # seed a session row to satisfy FK
    from datetime import datetime

    from kt.db import db

    now = datetime.now(UTC).isoformat()
    await db().execute(
        "INSERT INTO sessions(code, host_participant_id, host_secret_hash, enabled_providers, state_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        ("ABCDEF", "h1", "hh", "[]", "{}", now, now),
    )
    await db().commit()

    repo = CredentialsRepo(CredentialCipher(cred_key))
    await repo.put("ABCDEF", "tension", {"username": "u", "password": "p"})
    got = await repo.get("ABCDEF", "tension")
    assert got == {"username": "u", "password": "p"}
    assert await repo.list_providers("ABCDEF") == ["tension"]

    await repo.put("ABCDEF", "tension", {"username": "u2", "password": "p2"})
    assert (await repo.get("ABCDEF", "tension"))["username"] == "u2"

    await repo.delete_all("ABCDEF")
    assert await repo.get("ABCDEF", "tension") is None
