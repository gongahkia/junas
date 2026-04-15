from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from kt.realtime.hub import Connection, deserialize, serialize
from kt.realtime.session_engine import BadRequest, EngineError, PermissionDenied
from kt.repos.sessions_repo import SessionsRepo

router = APIRouter()


@router.websocket("/ws/sessions/{code}")
async def session_ws(ws: WebSocket, code: str):
    await ws.accept()
    hub = ws.app.state.hub
    repo = SessionsRepo()
    token = ws.query_params.get("token")
    if not token:
        await ws.send_text(serialize({"type": "error", "payload": {"error": "token_required"}}))
        await ws.close(code=4401)
        return
    claim = await repo.consume_ws_token(token)
    if not claim or claim["session_code"] != code:
        await ws.send_text(serialize({"type": "error", "payload": {"error": "invalid_token"}}))
        await ws.close(code=4401)
        return

    participant_id = claim["participant_id"]
    conn = Connection(participant_id=participant_id)
    live = await hub.attach(code, conn)
    if live is None:
        await ws.send_text(serialize({"type": "error", "payload": {"error": "session_not_found"}}))
        await ws.close(code=4404)
        return

    await ws.send_text(
        serialize({"type": "roomStateUpdate", "payload": live.state.to_dict()})
    )

    send_task = asyncio.create_task(_pump_outbound(ws, conn))
    try:
        while True:
            raw = await ws.receive_text()
            try:
                action = deserialize(raw)
            except Exception:
                await conn.send({"type": "error", "payload": {"error": "bad_json"}})
                continue
            try:
                await hub.apply(code, participant_id, action)
            except PermissionDenied as e:
                await conn.send({"type": "error", "payload": {"error": "forbidden", "detail": str(e)}})
            except BadRequest as e:
                await conn.send({"type": "error", "payload": {"error": "bad_request", "detail": str(e)}})
            except EngineError as e:
                await conn.send({"type": "error", "payload": {"error": "engine_error", "detail": str(e)}})
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        with contextlib.suppress(Exception):
            await send_task
        await hub.detach(code, participant_id)


async def _pump_outbound(ws: WebSocket, conn: Connection) -> None:
    try:
        while True:
            msg = await conn.queue.get()
            await ws.send_text(serialize(msg))
    except asyncio.CancelledError:
        return
    except Exception:
        return
