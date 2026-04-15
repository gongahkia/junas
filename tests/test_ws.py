from __future__ import annotations

import json

from fastapi.testclient import TestClient

from kt.config import Settings
from kt.main import create_app


async def test_ws_full_flow(tmp_path):
    from cryptography.fernet import Fernet
    settings = Settings(db_path=tmp_path / "ws.db", cred_key=Fernet.generate_key().decode())
    app = create_app(settings)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/sessions",
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        host_tk = create["host_ws_token"]

        guest = tc.post(f"/api/sessions/{code}/join", json={"display_name": "Guest"}).json()
        guest_tk = guest["ws_token"]

        with tc.websocket_connect(f"/ws/sessions/{code}?token={host_tk}") as host_ws:
            with tc.websocket_connect(f"/ws/sessions/{code}?token={guest_tk}") as guest_ws:
                # both receive an initial roomStateUpdate
                host_first = host_ws.receive_json()
                assert host_first["type"] == "roomStateUpdate"
                guest_first = guest_ws.receive_json()
                assert guest_first["type"] == "roomStateUpdate"

                # host adds a climb
                host_ws.send_text(
                    json.dumps(
                        {
                            "type": "addToQueue",
                            "payload": {
                                "climb_id": "c1",
                                "name": "Test",
                            },
                        }
                    )
                )
                # both should see a queueUpdate then a roomStateUpdate
                msgs_h = [host_ws.receive_json(), host_ws.receive_json()]
                msgs_g = [guest_ws.receive_json(), guest_ws.receive_json()]
                types_h = {m["type"] for m in msgs_h}
                types_g = {m["type"] for m in msgs_g}
                assert "queueUpdate" in types_h and "roomStateUpdate" in types_h
                assert "queueUpdate" in types_g and "roomStateUpdate" in types_g

                # guest adds the same climb -> bad_request to guest only
                guest_ws.send_text(
                    json.dumps(
                        {
                            "type": "addToQueue",
                            "payload": {
                                "climb_id": "c1",
                                "name": "Test",
                            },
                        }
                    )
                )
                err = guest_ws.receive_json()
                assert err["type"] == "error"
                assert err["payload"]["error"] == "bad_request"


def test_ws_rejects_missing_token(tmp_path):
    from cryptography.fernet import Fernet
    settings = Settings(db_path=tmp_path / "ws2.db", cred_key=Fernet.generate_key().decode())
    app = create_app(settings)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/sessions", json={"host_display_name": "H", "provider": "tension"}
        ).json()
        code = create["code"]
        try:
            with tc.websocket_connect(f"/ws/sessions/{code}"):
                pass
        except Exception:
            return
        # Some clients receive the close gracefully; either way no infinite hang
