async def test_create_session_and_get(client):
    r = await client.post(
        "/api/sessions",
        json={"host_display_name": "Alex", "provider": "tension"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    code = body["code"]
    assert len(code) == 6
    assert body["host_secret"]
    assert body["session_read_token"]
    read_headers = {"X-Session-Read-Token": body["session_read_token"]}

    r = await client.get(f"/api/sessions/{code}", headers=read_headers)
    assert r.status_code == 200
    s = r.json()
    assert s["provider"] == "tension"
    assert s["enabled_providers"] == ["tension"]
    assert s["attached_providers"] == []


async def test_create_session_with_multiple_enabled_providers(client):
    r = await client.post(
        "/api/sessions",
        json={
            "host_display_name": "Alex",
            "enabled_providers": ["moonboard_catalog", "crux"],
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    code = payload["code"]
    read_headers = {"X-Session-Read-Token": payload["session_read_token"]}

    r = await client.get(f"/api/sessions/{code}", headers=read_headers)
    assert r.status_code == 200
    assert r.json()["provider"] == "moonboard_catalog"
    assert r.json()["enabled_providers"] == ["moonboard_catalog", "crux"]


async def test_create_session_unknown_provider(client):
    r = await client.post(
        "/api/sessions",
        json={"host_display_name": "Alex", "provider": "not-a-board"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "unknown_provider"


async def test_create_session_unknown_enabled_provider(client):
    r = await client.post(
        "/api/sessions",
        json={"host_display_name": "Alex", "enabled_providers": ["tension", "bad"]},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "unknown_provider"
    assert r.json()["detail"]["detail"] == "bad"


async def test_attach_credentials_and_reflect_in_summary(client):
    create = (
        await client.post(
            "/api/sessions",
            json={
                "host_display_name": "Alex",
                "enabled_providers": ["moonboard_catalog", "crux"],
            },
        )
    ).json()
    code = create["code"]
    host_secret = create["host_secret"]
    read_headers = {"X-Session-Read-Token": create["session_read_token"]}

    bad = await client.post(
        f"/api/sessions/{code}/credentials",
        json={
            "provider": "moonboard_catalog",
            "credentials": {"token": "irrelevant"},
            "host_secret": "wrong",
        },
    )
    assert bad.status_code == 403

    ok = await client.post(
        f"/api/sessions/{code}/credentials",
        json={
            "provider": "moonboard_catalog",
            "credentials": {"token": "irrelevant"},
            "host_secret": host_secret,
        },
    )
    assert ok.status_code == 200
    assert ok.json() == {"provider": "moonboard_catalog", "ok": True}

    summary = await client.get(f"/api/sessions/{code}", headers=read_headers)
    assert summary.status_code == 200
    assert summary.json()["attached_providers"] == ["moonboard_catalog"]


async def test_end_session_requires_host_secret(client):
    create = (
        await client.post(
            "/api/sessions", json={"host_display_name": "A", "provider": "tension"}
        )
    ).json()
    code = create["code"]
    r = await client.delete(
        f"/api/sessions/{code}", headers={"X-Host-Secret": "wrong"}
    )
    assert r.status_code == 403
    r = await client.delete(
        f"/api/sessions/{code}",
        headers={"X-Host-Secret": create["host_secret"]},
    )
    assert r.status_code == 200
    r = await client.get(
        f"/api/sessions/{code}",
        headers={"X-Session-Read-Token": create["session_read_token"]},
    )
    assert r.status_code == 404


async def test_list_providers(client):
    r = await client.get("/api/providers")
    assert r.status_code == 200
    keys = {p["key"] for p in r.json()}
    assert {
        "tension",
        "grasshopper",
        "decoy",
        "soill",
        "touchstone",
        "aurora",
        "moonboard",
        "moonboard_catalog",
        "kilter",
        "kilter_legacy",
        "crux",
    } <= keys
    kilter = [p for p in r.json() if p["key"] == "kilter"][0]
    assert kilter["status"] == "experimental"
    assert "capabilities" in kilter
    assert {"list_layouts", "search_climbs", "get_climb", "live_data"} == set(
        kilter["capabilities"]
    )
    assert kilter["taxonomy_version"] == "2026-04-aggregator-v1"
    assert "readiness" in kilter
    assert "is_data_ready" in kilter


async def test_create_session_rejects_not_ready_provider(client):
    from kt.providers import registry
    from kt.providers.base import AuthToken, Climb, ClimbQuery, Layout, ProviderStatus

    class NotReadyProvider:
        key = "notready"
        name = "NotReady"
        status = ProviderStatus.EXPERIMENTAL
        requires_credentials = False
        capabilities = {
            "list_layouts": False,
            "search_climbs": False,
            "get_climb": False,
            "live_data": False,
        }

        async def authenticate(self, creds):
            return AuthToken(provider=self.key, value="na")

        async def list_layouts(self, token):
            return [Layout(id="na", name="NA")]

        async def search_climbs(self, token, query: ClimbQuery):
            return []

        async def get_climb(self, token, climb_id: str):
            return Climb(
                id=climb_id,
                provider=self.key,
                name="x",
                setter=None,
                grade=None,
                angle=None,
                ascents=None,
            )

    registry.register(NotReadyProvider())
    try:
        r = await client.post(
            "/api/sessions",
            json={"host_display_name": "Alex", "provider": "notready"},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "provider_not_ready"
        detail = r.json()["detail"]["detail"]
        assert detail["provider"] == "notready"
    finally:
        registry.bootstrap()


async def test_read_token_required_for_session_summary(client):
    create = (
        await client.post(
            "/api/sessions",
            json={"host_display_name": "Alex", "provider": "tension"},
        )
    ).json()
    code = create["code"]
    missing = await client.get(f"/api/sessions/{code}")
    assert missing.status_code == 401

    bad = await client.get(
        f"/api/sessions/{code}", headers={"X-Session-Read-Token": "bad"}
    )
    assert bad.status_code == 403
