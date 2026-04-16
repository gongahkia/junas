from __future__ import annotations

from httpx import AsyncClient


async def test_register_login_me_flow(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alex@example.com",
            "password": "correcthorse",
            "display_name": "Alex",
        },
    )
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]
    access = tokens["access_token"]

    me = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "alex@example.com"
    assert body["display_name"] == "Alex"
    assert body["grade_system_pref"] == "font"

    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "alex@example.com", "password": "wrong"},
    )
    assert bad.status_code == 401

    ok = await client.post(
        "/api/v1/auth/login",
        json={"email": "alex@example.com", "password": "correcthorse"},
    )
    assert ok.status_code == 200
    assert ok.json()["user_id"] == body["id"]


async def test_register_rejects_duplicate_email(client: AsyncClient):
    payload = {
        "email": "dup@example.com",
        "password": "correcthorse",
        "display_name": "D",
    }
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 200
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"] == "email_taken"


async def test_refresh_rotates_tokens(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rot@example.com",
            "password": "correcthorse",
            "display_name": "R",
        },
    )
    tokens = r.json()
    old_access = tokens["access_token"]
    old_refresh = tokens["refresh_token"]

    rot = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert rot.status_code == 200
    rotated = rot.json()
    assert rotated["access_token"] != old_access
    assert rotated["refresh_token"] != old_refresh

    # Old refresh should no longer work (it was rotated into a new one).
    bad = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert bad.status_code == 401


async def test_logout_invalidates_refresh(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bye@example.com",
            "password": "correcthorse",
            "display_name": "B",
        },
    )
    refresh = r.json()["refresh_token"]
    out = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh}
    )
    assert out.status_code == 200
    assert out.json()["revoked"] is True
    bad = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh}
    )
    assert bad.status_code == 401


async def test_magic_link_flow_dev_mode(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/magic-link", json={"email": "magic@example.com"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    # KT_AUTH_RETURN_MAGIC_LINKS defaults to true for tests
    assert body["token"]

    v = await client.post(
        "/api/v1/auth/magic-link/verify", json={"token": body["token"]}
    )
    assert v.status_code == 200
    assert v.json()["user_id"]

    # Token can only be used once.
    again = await client.post(
        "/api/v1/auth/magic-link/verify", json={"token": body["token"]}
    )
    assert again.status_code == 400


async def test_patch_me_updates_profile(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "p@example.com",
            "password": "correcthorse",
            "display_name": "Old",
        },
    )
    access = r.json()["access_token"]
    upd = await client.patch(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {access}"},
        json={"display_name": "New", "grade_system_pref": "v"},
    )
    assert upd.status_code == 200
    assert upd.json()["display_name"] == "New"
    assert upd.json()["grade_system_pref"] == "v"


async def test_bearer_session_join_links_user(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "h@example.com",
            "password": "correcthorse",
            "display_name": "Host",
        },
    )
    access = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    created = await client.post(
        "/api/v1/sessions",
        headers=headers,
        json={"host_display_name": "Host", "provider": "tension"},
    )
    assert created.status_code == 200
    code = created.json()["code"]

    # Rejoin with same bearer should reuse participant_id
    join1 = await client.post(
        f"/api/v1/sessions/{code}/join",
        headers=headers,
        json={"display_name": "Host"},
    )
    join2 = await client.post(
        f"/api/v1/sessions/{code}/join",
        headers=headers,
        json={"display_name": "Host"},
    )
    assert join1.status_code == 200 and join2.status_code == 200
    assert join1.json()["participant_id"] == join2.json()["participant_id"]
