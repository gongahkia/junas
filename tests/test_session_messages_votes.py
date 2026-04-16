from __future__ import annotations

import json

from fastapi.testclient import TestClient

from kt.config import Settings
from kt.main import create_app


def _make_app(tmp_path):
    from cryptography.fernet import Fernet

    settings = Settings(
        db_path=tmp_path / "p4.db", cred_key=Fernet.generate_key().decode()
    )
    return create_app(settings)


def test_chat_messages_are_persisted_and_listable(tmp_path):
    app = _make_app(tmp_path)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/v1/sessions",
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        with tc.websocket_connect(
            f"/ws/sessions/{code}?token={create['host_ws_token']}"
        ) as ws:
            ws.receive_json()
            ws.send_text(
                json.dumps(
                    {"type": "sendChat", "payload": {"body": "Hello everyone"}}
                )
            )
            # chatMessage + roomStateUpdate
            msgs = [ws.receive_json() for _ in range(2)]
            types = {m["type"] for m in msgs}
            assert "chatMessage" in types

        r = tc.get(f"/api/v1/sessions/{code}/messages?kind=chat")
        assert r.status_code == 200
        body = r.json()
        assert len(body["messages"]) == 1
        assert body["messages"][0]["payload"]["body"] == "Hello everyone"


def test_beta_is_attached_to_queue_item(tmp_path):
    app = _make_app(tmp_path)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/v1/sessions",
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        with tc.websocket_connect(
            f"/ws/sessions/{code}?token={create['host_ws_token']}"
        ) as ws:
            ws.receive_json()
            ws.send_text(
                json.dumps(
                    {
                        "type": "addToQueue",
                        "payload": {"climb_id": "c1", "name": "Alpha"},
                    }
                )
            )
            ws.receive_json()  # queueUpdate
            ws.receive_json()  # room
            ws.send_text(
                json.dumps(
                    {
                        "type": "sendBeta",
                        "payload": {
                            "queue_id": "tension:c1",
                            "body": "drop knee at the third move",
                        },
                    }
                )
            )
            msgs = [ws.receive_json() for _ in range(2)]
            assert any(m["type"] == "betaMessage" for m in msgs)

        r = tc.get(f"/api/v1/sessions/{code}/messages?kind=beta").json()
        assert r["messages"][0]["payload"]["queue_id"] == "tension:c1"


def test_quality_and_grade_votes_aggregate_into_consensus(tmp_path):
    app = _make_app(tmp_path)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/v1/sessions",
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        host_secret = create["host_secret"]
        with tc.websocket_connect(
            f"/ws/sessions/{code}?token={create['host_ws_token']}"
        ) as ws:
            ws.receive_json()
            ws.send_text(
                json.dumps(
                    {
                        "type": "addToQueue",
                        "payload": {"climb_id": "c1", "name": "Alpha"},
                    }
                )
            )
            ws.receive_json()
            ws.receive_json()
            ws.send_text(
                json.dumps(
                    {
                        "type": "voteQuality",
                        "payload": {"queue_id": "tension:c1", "stars": 4.5},
                    }
                )
            )
            ws.receive_json()
            ws.receive_json()
            ws.send_text(
                json.dumps(
                    {
                        "type": "voteGrade",
                        "payload": {"queue_id": "tension:c1", "grade_v": 6},
                    }
                )
            )
            ws.receive_json()
            ws.receive_json()

        # Have a guest join and vote too
        guest = tc.post(
            f"/api/v1/sessions/{code}/join", json={"display_name": "Guest"}
        ).json()
        with tc.websocket_connect(
            f"/ws/sessions/{code}?token={guest['ws_token']}"
        ) as gws:
            gws.receive_json()
            gws.send_text(
                json.dumps(
                    {
                        "type": "voteQuality",
                        "payload": {"queue_id": "tension:c1", "stars": 3.0},
                    }
                )
            )
            gws.receive_json()
            gws.receive_json()
            gws.send_text(
                json.dumps(
                    {
                        "type": "voteGrade",
                        "payload": {"queue_id": "tension:c1", "grade_v": 7},
                    }
                )
            )
            gws.receive_json()
            gws.receive_json()

        r = tc.get(
            f"/api/v1/sessions/{code}/consensus?provider=tension&climb_id=c1"
        ).json()
        assert r["vote_count"] == 2
        assert abs(r["quality_avg"] - 3.75) < 1e-6
        assert r["grade_v_count"] == 2
        assert abs(r["grade_v_avg"] - 6.5) < 1e-6
        assert r["grade_v_distribution"] == {"6": 1, "7": 1}
        # silences unused var warning
        assert host_secret


def test_set_session_meta_and_export(tmp_path):
    app = _make_app(tmp_path)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/v1/sessions",
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        with tc.websocket_connect(
            f"/ws/sessions/{code}?token={create['host_ws_token']}"
        ) as ws:
            ws.receive_json()
            ws.send_text(
                json.dumps(
                    {
                        "type": "setSessionMeta",
                        "payload": {
                            "title": "Tuesday night sesh",
                            "description": "V3-V6 project",
                            "tags": ["crimpy", "power"],
                        },
                    }
                )
            )
            msgs = [ws.receive_json() for _ in range(2)]
            assert any(m["type"] == "sessionMetaUpdate" for m in msgs)

        exp = tc.get(f"/api/v1/sessions/{code}/export?format=json").json()
        assert exp["state"]["title"] == "Tuesday night sesh"
        assert "crimpy" in exp["state"]["tags"]

        csv_body = tc.get(f"/api/v1/sessions/{code}/export?format=csv").text
        assert csv_body.startswith("provider,climb_id,name,completed_by,result,completed_at")


def test_chat_rejects_blank_body(tmp_path):
    app = _make_app(tmp_path)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/v1/sessions",
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        with tc.websocket_connect(
            f"/ws/sessions/{code}?token={create['host_ws_token']}"
        ) as ws:
            ws.receive_json()
            ws.send_text(
                json.dumps({"type": "sendChat", "payload": {"body": "   "}})
            )
            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["payload"]["error"] == "bad_request"
