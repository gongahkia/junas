async def test_create_session_and_get(client):
    r = await client.post(
        "/api/sessions",
        json={"host_display_name": "Alex", "provider": "tension"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    code = body["code"]
    assert len(code) == 6
    assert body["host_secret"] and body["host_participant_id"]

    r = await client.get(f"/api/sessions/{code}")
    assert r.status_code == 200
    s = r.json()
    assert s["provider"] == "tension"
    assert s["participant_count"] == 1
    assert s["queue_length"] == 0


async def test_create_session_unknown_provider(client):
    r = await client.post(
        "/api/sessions",
        json={"host_display_name": "Alex", "provider": "not-a-board"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "unknown_provider"


async def test_join_and_ws_token_issued(client):
    create = (
        await client.post(
            "/api/sessions",
            json={"host_display_name": "Alex", "provider": "tension"},
        )
    ).json()
    code = create["code"]
    r = await client.post(f"/api/sessions/{code}/join", json={"display_name": "Guest"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["participant_id"] and body["ws_token"]

    r = await client.get(f"/api/sessions/{code}")
    assert r.json()["participant_count"] == 2


async def test_end_session_requires_host_secret(client):
    create = (
        await client.post(
            "/api/sessions", json={"host_display_name": "A", "provider": "tension"}
        )
    ).json()
    code = create["code"]
    r = await client.delete(f"/api/sessions/{code}", params={"host_secret": "wrong"})
    assert r.status_code == 403
    r = await client.delete(
        f"/api/sessions/{code}", params={"host_secret": create["host_secret"]}
    )
    assert r.status_code == 200
    r = await client.get(f"/api/sessions/{code}")
    assert r.status_code == 404


async def test_list_providers(client):
    r = await client.get("/api/providers")
    assert r.status_code == 200
    keys = {p["key"] for p in r.json()}
    assert {"tension", "grasshopper", "decoy", "soill", "touchstone", "aurora", "moonboard", "moonboard_catalog", "kilter", "crux"} <= keys
    kilter = [p for p in r.json() if p["key"] == "kilter"][0]
    assert kilter["status"] == "experimental"
