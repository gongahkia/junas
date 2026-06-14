from fastapi.testclient import TestClient

from api.main import create_app
from api.services.session_storage import SessionStorage


def _client(tmp_path):
    app = create_app()
    app.state.session_storage = SessionStorage(tmp_path / "sessions.sqlite3")
    return TestClient(app)


def test_sessions_crud_roundtrip(tmp_path):
    client = _client(tmp_path)
    node_map = {
        "u1": {"id": "u1", "role": "user", "content": "Review this PDPA clause", "childrenIds": ["a1"], "timestamp": 1},
        "a1": {"id": "a1", "role": "assistant", "content": "Clause reviewed.", "parentId": "u1", "childrenIds": [], "timestamp": 2},
    }

    created = client.post("/api/v1/sessions", json={"id": "conv-test", "node_map": node_map, "current_leaf_id": "a1"})
    assert created.status_code == 200
    body = created.json()
    assert body["id"] == "conv-test"
    assert body["title"] == "Review this PDPA clause"
    assert body["message_count"] == 2
    assert body["deleted_at"] is None

    listed = client.get("/api/v1/sessions")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == ["conv-test"]

    fetched = client.get("/api/v1/sessions/conv-test")
    assert fetched.status_code == 200
    assert fetched.json()["node_map"]["a1"]["content"] == "Clause reviewed."

    updated_map = {**node_map, "u2": {"id": "u2", "role": "user", "content": "Second turn", "childrenIds": [], "timestamp": 3}}
    updated = client.put("/api/v1/sessions/conv-test", json={"node_map": updated_map, "current_leaf_id": "u2"})
    assert updated.status_code == 200
    assert updated.json()["message_count"] == 3

    renamed = client.patch("/api/v1/sessions/conv-test", json={"title": "PDPA review"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "PDPA review"

    deleted = client.delete("/api/v1/sessions/conv-test")
    assert deleted.status_code == 200
    assert deleted.json() == {"id": "conv-test", "deleted": True}
    assert client.get("/api/v1/sessions/conv-test").status_code == 404
    assert client.get("/api/v1/sessions").json() == []


def test_session_rename_rejects_blank_title(tmp_path):
    client = _client(tmp_path)
    client.post("/api/v1/sessions", json={"id": "conv-test", "node_map": {}, "current_leaf_id": ""})
    response = client.patch("/api/v1/sessions/conv-test", json={"title": "   "})
    assert response.status_code == 422
