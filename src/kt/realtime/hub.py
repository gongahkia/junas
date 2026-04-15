"""In-process session hub: owns live sessions and fans out events."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from kt.realtime.session_engine import Event, apply_action
from kt.realtime.state import SessionState
from kt.repos.sessions_repo import SessionsRepo


@dataclass
class Connection:
    participant_id: str
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(maxsize=256))

    async def send(self, msg: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass


@dataclass
class LiveSession:
    state: SessionState
    conns: dict[str, Connection] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionHub:
    def __init__(self, repo: SessionsRepo) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._repo = repo
        self._global_lock = asyncio.Lock()

    async def load_or_restore(self, code: str) -> LiveSession | None:
        async with self._global_lock:
            if code in self._sessions:
                return self._sessions[code]
            row = await self._repo.get(code)
            if not row or row["ended_at"]:
                return None
            state = SessionState.from_dict(row["state"])
            self._sessions[code] = LiveSession(state=state)
            return self._sessions[code]

    def get(self, code: str) -> LiveSession | None:
        return self._sessions.get(code)

    async def attach(self, code: str, conn: Connection) -> LiveSession | None:
        live = await self.load_or_restore(code)
        if live is None:
            return None
        live.conns[conn.participant_id] = conn
        return live

    async def detach(self, code: str, participant_id: str) -> None:
        live = self._sessions.get(code)
        if live is None:
            return
        live.conns.pop(participant_id, None)

    async def apply(
        self, code: str, participant_id: str, action: dict[str, Any]
    ) -> list[Event]:
        live = await self.load_or_restore(code)
        if live is None:
            raise KeyError("session not found")
        async with live.lock:
            new_state, events = apply_action(live.state, participant_id, action)
            live.state = new_state
            await self._repo.save_state(code, new_state.to_dict())
        for ev in events:
            await self._broadcast(live, ev)
        await self._send_room_state(live)
        return events

    async def _broadcast(self, live: LiveSession, event: Event) -> None:
        msg = {"type": event.type, "payload": event.payload}
        for c in list(live.conns.values()):
            await c.send(msg)

    async def _send_room_state(self, live: LiveSession) -> None:
        snapshot = {"type": "roomStateUpdate", "payload": live.state.to_dict()}
        for c in list(live.conns.values()):
            await c.send(snapshot)

    async def end(self, code: str) -> None:
        live = self._sessions.pop(code, None)
        if live:
            for c in live.conns.values():
                await c.send({"type": "sessionEnded", "payload": {}})
        await self._repo.end(code)


def serialize(msg: dict[str, Any]) -> str:
    return json.dumps(msg)


def deserialize(raw: str) -> dict[str, Any]:
    return json.loads(raw)
