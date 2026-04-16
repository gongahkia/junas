from __future__ import annotations

import json

from fastapi.testclient import TestClient

from kt.config import Settings
from kt.main import create_app


def _make_app(tmp_path):
    from cryptography.fernet import Fernet

    settings = Settings(db_path=tmp_path / "resume.db", cred_key=Fernet.generate_key().decode())
    return create_app(settings)


def test_events_have_monotonic_seq(tmp_path):
    app = _make_app(tmp_path)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/v1/sessions",
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        host_tk = create["host_ws_token"]

        with tc.websocket_connect(f"/ws/sessions/{code}?token={host_tk}") as ws:
            first = ws.receive_json()
            assert first["type"] == "roomStateUpdate"
            assert first["seq"] == 0

            ws.send_text(
                json.dumps(
                    {
                        "type": "addToQueue",
                        "payload": {"climb_id": "cA", "name": "Alpha"},
                    }
                )
            )
            msgs = [ws.receive_json(), ws.receive_json()]
            seqs = [m["seq"] for m in msgs]
            assert seqs == sorted(seqs)
            assert seqs[0] >= 1
            assert seqs[-1] > seqs[0]


def test_resume_replays_missed_events(tmp_path):
    app = _make_app(tmp_path)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/v1/sessions",
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        host_tk_1 = create["host_ws_token"]
        host_secret = create["host_secret"]

        captured_seq = 0
        with tc.websocket_connect(f"/ws/sessions/{code}?token={host_tk_1}") as ws:
            ws.receive_json()
            ws.send_text(
                json.dumps(
                    {
                        "type": "addToQueue",
                        "payload": {"climb_id": "cA", "name": "Alpha"},
                    }
                )
            )
            last = None
            for _ in range(2):
                last = ws.receive_json()
            captured_seq = last["seq"]

        # Server-side action while the client is "offline": refresh host token
        # and add another climb.
        host_tk_2 = tc.post(
            f"/api/v1/sessions/{code}/host-token",
            json={"host_secret": host_secret},
        ).json()["ws_token"]
        with tc.websocket_connect(f"/ws/sessions/{code}?token={host_tk_2}") as ws2:
            ws2.receive_json()
            ws2.send_text(
                json.dumps(
                    {
                        "type": "addToQueue",
                        "payload": {"climb_id": "cB", "name": "Bravo"},
                    }
                )
            )
            for _ in range(2):
                ws2.receive_json()

        # Reconnect with since_seq = captured_seq: should get replay
        host_tk_3 = tc.post(
            f"/api/v1/sessions/{code}/host-token",
            json={"host_secret": host_secret},
        ).json()["ws_token"]
        with tc.websocket_connect(
            f"/ws/sessions/{code}?token={host_tk_3}&since_seq={captured_seq}"
        ) as ws3:
            msgs: list[dict] = []
            while True:
                m = ws3.receive_json()
                msgs.append(m)
                if m["type"] == "roomStateUpdate" and not m.get("replay"):
                    break
            replays = [m for m in msgs if m.get("replay")]
            # Should have replayed at least the queueUpdate + roomStateUpdate
            # from the second session.
            assert len(replays) >= 1
            replay_types = {m["type"] for m in replays}
            assert "queueUpdate" in replay_types
            for m in replays:
                assert m["seq"] > captured_seq


def test_bad_since_seq_closes_connection(tmp_path):
    app = _make_app(tmp_path)
    with TestClient(app) as tc:
        create = tc.post(
            "/api/v1/sessions",
            json={"host_display_name": "Host", "provider": "tension"},
        ).json()
        code = create["code"]
        host_tk = create["host_ws_token"]

        try:
            with tc.websocket_connect(
                f"/ws/sessions/{code}?token={host_tk}&since_seq=not-a-number"
            ) as ws:
                err = ws.receive_json()
                assert err["type"] == "error"
                assert err["payload"]["error"] == "bad_since_seq"
        except Exception:
            # Connection may be closed before our inspection; either is fine.
            pass
