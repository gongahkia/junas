from __future__ import annotations

import json

from fastapi.testclient import TestClient
from httpx import AsyncClient

from kt.config import Settings
from kt.main import create_app


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correcthorse", "display_name": email[:8]},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_logbook_create_list_delete_roundtrip(client: AsyncClient):
    access = await _register(client, "lb@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    r = await client.post(
        "/api/v1/me/logbook",
        headers=headers,
        json={
            "provider": "tension",
            "climb_id": "abc123",
            "result": "sent",
            "name": "Alpha",
            "grade_at_send": "V6",
            "attempts": 3,
            "rpe": 8,
            "notes": "Sticky start crimp",
        },
    )
    assert r.status_code == 200, r.text
    entry = r.json()
    assert entry["grade_v_at_send"] == 6
    assert entry["result"] == "sent"

    page = await client.get("/api/v1/me/logbook", headers=headers)
    assert page.status_code == 200
    assert len(page.json()["entries"]) == 1

    d = await client.delete(f"/api/v1/me/logbook/{entry['id']}", headers=headers)
    assert d.status_code == 200
    empty = await client.get("/api/v1/me/logbook", headers=headers)
    assert empty.json()["entries"] == []


async def test_logbook_stats_count_sends_and_hardest(client: AsyncClient):
    access = await _register(client, "stats@example.com")
    headers = {"Authorization": f"Bearer {access}"}
    for g, res in [("V3", "sent"), ("V7", "flash"), ("V5", "attempted")]:
        await client.post(
            "/api/v1/me/logbook",
            headers=headers,
            json={
                "provider": "tension",
                "climb_id": f"c-{g}",
                "result": res,
                "grade_at_send": g,
            },
        )
    s = await client.get("/api/v1/me/stats", headers=headers)
    assert s.status_code == 200
    body = s.json()
    assert body["total_entries"] == 3
    assert body["hardest_v"] == 7  # attempts not counted
    assert body["by_grade_v"]["3"] == 1
    assert body["by_grade_v"]["7"] == 1


async def test_favorites_add_list_remove(client: AsyncClient):
    access = await _register(client, "fav@example.com")
    headers = {"Authorization": f"Bearer {access}"}
    r = await client.post(
        "/api/v1/me/favorites",
        headers=headers,
        json={"provider": "tension", "climb_id": "xyz"},
    )
    assert r.status_code == 200

    listing = await client.get("/api/v1/me/favorites", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()["entries"]) == 1

    rm = await client.request(
        "DELETE",
        "/api/v1/me/favorites",
        headers=headers,
        json={"provider": "tension", "climb_id": "xyz"},
    )
    assert rm.status_code == 200
    assert rm.json()["removed"] is True


async def test_climb_notes_put_get_delete(client: AsyncClient):
    access = await _register(client, "notes@example.com")
    headers = {"Authorization": f"Bearer {access}"}
    put = await client.put(
        "/api/v1/me/notes/tension/abc",
        headers=headers,
        json={"body": "drop knee on the right foot", "tags": ["beta"]},
    )
    assert put.status_code == 200
    assert put.json()["body"] == "drop knee on the right foot"

    got = await client.get("/api/v1/me/notes/tension/abc", headers=headers)
    assert got.status_code == 200
    assert got.json()["tags"] == ["beta"]

    d = await client.delete("/api/v1/me/notes/tension/abc", headers=headers)
    assert d.status_code == 200
    gone = await client.get("/api/v1/me/notes/tension/abc", headers=headers)
    assert gone.status_code == 404


async def test_boardlib_csv_import(client: AsyncClient):
    access = await _register(client, "imp@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    csv_data = (
        b"board,angle,climb_name,climb_uuid,date,displayed_grade,"
        b"logged_ascent_type,tries,is_mirror,comment\n"
        b"kilter,40,Alpha,UUID1,2026-01-02T10:00:00,V6,send,3,0,fun\n"
        b"tension,45,Bravo,UUID2,2026-01-03T10:00:00,V8,flash,1,1,smooth\n"
    )

    r = await client.post(
        "/api/v1/me/logbook/import",
        headers=headers,
        files={"file": ("test.csv", csv_data, "text/csv")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 2
    assert body["skipped"] == 0

    page = await client.get("/api/v1/me/logbook", headers=headers)
    entries = page.json()["entries"]
    assert len(entries) == 2
    # Most recent first
    assert entries[0]["climb_id"] == "UUID2"
    assert entries[0]["result"] == "flash"
    assert "mirror" in (entries[0]["notes"] or "")


async def test_logbook_export_json_and_csv(client: AsyncClient):
    access = await _register(client, "exp@example.com")
    headers = {"Authorization": f"Bearer {access}"}
    await client.post(
        "/api/v1/me/logbook",
        headers=headers,
        json={"provider": "tension", "climb_id": "e1", "result": "sent"},
    )
    j = await client.get("/api/v1/me/logbook/export?format=json", headers=headers)
    assert j.status_code == 200
    assert len(j.json()["entries"]) == 1

    c = await client.get("/api/v1/me/logbook/export?format=csv", headers=headers)
    assert c.status_code == 200
    body = c.text.splitlines()
    assert body[0].startswith("id,")
    assert len(body) == 2


def test_markcompleted_writes_logbook_for_authed_participant(tmp_path):
    from cryptography.fernet import Fernet

    settings = Settings(db_path=tmp_path / "lb.db", cred_key=Fernet.generate_key().decode())
    app = create_app(settings)
    with TestClient(app) as tc:
        reg = tc.post(
            "/api/v1/auth/register",
            json={
                "email": "host@example.com",
                "password": "correcthorse",
                "display_name": "Host",
            },
        ).json()
        access = reg["access_token"]
        headers = {"Authorization": f"Bearer {access}"}

        create = tc.post(
            "/api/v1/sessions",
            headers=headers,
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        host_tk = create["host_ws_token"]

        with tc.websocket_connect(f"/ws/sessions/{code}?token={host_tk}") as ws:
            ws.receive_json()
            ws.send_text(
                json.dumps(
                    {
                        "type": "addToQueue",
                        "payload": {"climb_id": "c1", "name": "Test"},
                    }
                )
            )
            ws.receive_json()  # queueUpdate
            ws.receive_json()  # roomStateUpdate
            ws.send_text(
                json.dumps(
                    {
                        "type": "markCompleted",
                        "payload": {
                            "queue_id": "tension:c1",
                            "result": "flash",
                            "attempts": 1,
                            "rpe": 7,
                            "notes": "easy",
                            "grade_at_send": "V5",
                        },
                    }
                )
            )
            ws.receive_json()
            ws.receive_json()
            ws.receive_json()

        lb = tc.get("/api/v1/me/logbook", headers=headers).json()
        assert len(lb["entries"]) == 1
        entry = lb["entries"][0]
        assert entry["result"] == "flash"
        assert entry["provider"] == "tension"
        assert entry["climb_id"] == "c1"
        assert entry["rpe"] == 7
        assert entry["grade_v_at_send"] == 5
        assert entry["session_code"] == code
