"""In-process session hub: owns live sessions and fans out events."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from kt.providers import registry
from kt.realtime.session_engine import BadRequest, Event, apply_action
from kt.realtime.state import SessionState
from kt.repos.climb_votes_repo import ClimbVotesRepo
from kt.repos.logbook_repo import LogbookRepo
from kt.repos.session_events_repo import SessionEventsRepo
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
    last_seq: int = 0


class SessionHub:
    def __init__(
        self,
        repo: SessionsRepo,
        events_repo: SessionEventsRepo | None = None,
        logbook_repo: LogbookRepo | None = None,
        votes_repo: ClimbVotesRepo | None = None,
    ) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._repo = repo
        self._events_repo = events_repo or SessionEventsRepo()
        self._logbook_repo = logbook_repo or LogbookRepo()
        self._votes_repo = votes_repo or ClimbVotesRepo()
        self._global_lock = asyncio.Lock()

    async def load_or_restore(self, code: str) -> LiveSession | None:
        async with self._global_lock:
            if code in self._sessions:
                return self._sessions[code]
            row = await self._repo.get(code)
            if not row or row["ended_at"]:
                return None
            state = SessionState.from_dict(row["state"])
            last_seq = await self._events_repo.latest_seq(code)
            self._sessions[code] = LiveSession(state=state, last_seq=last_seq)
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
        if action.get("type") == "setProviders":
            _validate_known_providers(action)
        async with live.lock:
            prev_queue_by_id = {q.id: q for q in live.state.queue}
            new_state, events = apply_action(live.state, participant_id, action)
            live.state = new_state
            await self._repo.save_state(code, new_state.to_dict())
            logged: list[tuple[Event, int]] = []
            for ev in events:
                seq = await self._events_repo.append(code, ev.type, ev.payload)
                live.last_seq = seq
                logged.append((ev, seq))
            snapshot_seq = await self._events_repo.append(
                code, "roomStateUpdate", new_state.to_dict()
            )
            live.last_seq = snapshot_seq
        action_type = action.get("type")
        if action_type == "markCompleted":
            await self._maybe_write_logbook(
                code, new_state, participant_id, action, prev_queue_by_id
            )
        elif action_type in {"voteQuality", "voteGrade"}:
            await self._persist_vote(code, action_type, events)
        for ev, seq in logged:
            await self._broadcast(live, ev, seq)
        await self._send_room_state(live, snapshot_seq)
        return events

    async def _persist_vote(
        self, code: str, action_type: str, events: list[Event]
    ) -> None:
        for ev in events:
            payload = ev.payload
            if action_type == "voteQuality" and ev.type == "qualityVote":
                await self._votes_repo.upsert(
                    session_code=code,
                    participant_id=str(payload.get("participant_id")),
                    provider=str(payload.get("provider")),
                    climb_id=str(payload.get("climb_id")),
                    quality=payload.get("stars"),
                )
            elif action_type == "voteGrade" and ev.type == "gradeVote":
                await self._votes_repo.upsert(
                    session_code=code,
                    participant_id=str(payload.get("participant_id")),
                    provider=str(payload.get("provider")),
                    climb_id=str(payload.get("climb_id")),
                    grade_v=payload.get("grade_v"),
                )

    async def _maybe_write_logbook(
        self,
        code: str,
        state: SessionState,
        participant_id: str,
        action: dict[str, Any],
        prev_queue_by_id: dict[str, Any],
    ) -> None:
        participant = state.participants.get(participant_id)
        if participant is None or not participant.user_id:
            return
        payload = action.get("payload") or {}
        q_id = payload.get("queue_id")
        q = prev_queue_by_id.get(q_id) if q_id else None
        if q is None:
            return
        try:
            await self._logbook_repo.add(
                user_id=participant.user_id,
                provider=q.provider,
                climb_id=q.climb_id,
                result=str(payload.get("result") or "sent"),
                name=q.name,
                session_code=code,
                grade_at_send=payload.get("grade_at_send"),
                attempts=_maybe_int(payload.get("attempts")),
                rpe=_maybe_int(payload.get("rpe")),
                duration_seconds=_maybe_int(payload.get("duration_seconds")),
                notes=payload.get("notes"),
            )
        except ValueError:
            # Invalid fields (e.g. bad result / out-of-range rpe) — skip write.
            return

    async def _broadcast(self, live: LiveSession, event: Event, seq: int) -> None:
        msg = {"type": event.type, "payload": event.payload, "seq": seq}
        for c in list(live.conns.values()):
            await c.send(msg)

    async def _send_room_state(self, live: LiveSession, seq: int) -> None:
        snapshot = {
            "type": "roomStateUpdate",
            "payload": live.state.to_dict(),
            "seq": seq,
        }
        for c in list(live.conns.values()):
            await c.send(snapshot)

    async def consensus_for(
        self, code: str, provider: str, climb_id: str
    ) -> dict[str, Any]:
        return await self._votes_repo.consensus(code, provider, climb_id)

    async def events_since(self, code: str, since_seq: int) -> list[dict[str, Any]]:
        return await self._events_repo.list_since(code, since_seq)

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


def _maybe_int(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _validate_known_providers(action: dict[str, Any]) -> None:
    payload = action.get("payload") or {}
    raw = payload.get("enabled_providers", payload.get("providers"))
    if not isinstance(raw, list):
        return
    known = {p["key"] for p in registry.describe()}
    unknown = [provider for provider in raw if provider not in known]
    if unknown:
        raise BadRequest(f"unknown provider: {unknown[0]}")
