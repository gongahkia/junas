"""Pure session state machine: (state, action) -> (new_state, events)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from kt.realtime.state import (
    CompletedClimb,
    Participant,
    QueuedClimb,
    Role,
    SessionState,
    now_iso,
)


class EngineError(Exception):
    pass


class PermissionDenied(EngineError):
    pass


class BadRequest(EngineError):
    pass


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any]


def apply_action(
    state: SessionState, participant_id: str, action: dict[str, Any]
) -> tuple[SessionState, list[Event]]:
    t = action.get("type")
    if not t:
        raise BadRequest("missing action type")
    handler = _HANDLERS.get(t)
    if handler is None:
        raise BadRequest(f"unknown action: {t}")
    return handler(state, participant_id, action.get("payload") or {})


def _require(state: SessionState, participant_id: str, roles: set[Role]) -> Participant:
    p = state.participants.get(participant_id)
    if p is None:
        raise PermissionDenied("not in session")
    if p.role not in roles:
        raise PermissionDenied(f"requires role in {sorted(r.value for r in roles)}")
    return p


def _join(state, participant_id, payload):
    name = (payload.get("display_name") or "").strip()
    if not name or len(name) > 40:
        raise BadRequest("display_name required (<=40 chars)")
    role = Role.HOST if participant_id == state.host_id else Role.PARTICIPANT
    p = state.participants.get(participant_id)
    if p is None:
        new = {
            **state.participants,
            participant_id: Participant(
                id=participant_id, display_name=name, role=role, joined_at=now_iso()
            ),
        }
        state = replace(state, participants=new)
    return state, [Event("participantsUpdate", {"participants": [p_.__dict__ for p_ in state.participants.values()]})]


def _leave(state, participant_id, payload):
    if participant_id not in state.participants:
        return state, []
    if participant_id == state.host_id:
        raise PermissionDenied("host cannot leave; end session instead")
    parts = {k: v for k, v in state.participants.items() if k != participant_id}
    queue = [q for q in state.queue if q.added_by != participant_id]
    for q in queue:
        q.votes = [v for v in q.votes if v != participant_id]
    state = replace(state, participants=parts, queue=queue)
    return state, [Event("participantsUpdate", {"participants": [p.__dict__ for p in state.participants.values()]})]


def _set_role(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST})
    target = payload.get("participant_id")
    role_str = payload.get("role")
    if target not in state.participants or not role_str:
        raise BadRequest("participant_id and role required")
    try:
        new_role = Role(role_str)
    except ValueError as e:
        raise BadRequest("invalid role") from e
    if new_role == Role.HOST:
        raise BadRequest("cannot reassign host")
    parts = dict(state.participants)
    p = parts[target]
    parts[target] = Participant(
        id=p.id, display_name=p.display_name, role=new_role, joined_at=p.joined_at
    )
    state = replace(state, participants=parts)
    return state, [Event("participantsUpdate", {"participants": [p.__dict__ for p in state.participants.values()]})]


def _set_providers(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST})
    providers = payload.get("providers")
    if not isinstance(providers, list) or not all(isinstance(p, str) for p in providers):
        raise BadRequest("providers must be list[str]")
    state = replace(state, enabled_providers=list(dict.fromkeys(providers)))
    return state, [Event("providersUpdate", {"providers": state.enabled_providers})]


def _add_to_queue(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST, Role.PARTICIPANT})
    provider = payload.get("provider")
    climb_id = payload.get("climb_id")
    name = payload.get("name") or ""
    if not provider or not climb_id:
        raise BadRequest("provider and climb_id required")
    if provider not in state.enabled_providers:
        raise BadRequest("provider not enabled for this session")
    q_id = f"{provider}:{climb_id}"
    if any(q.id == q_id for q in state.queue):
        raise BadRequest("climb already queued")
    q = QueuedClimb(
        id=q_id,
        provider=provider,
        climb_id=climb_id,
        name=name,
        added_by=participant_id,
        votes=[],
        added_at=now_iso(),
    )
    state = replace(state, queue=[*state.queue, q])
    return state, [Event("queueUpdate", {"queue": [q.__dict__ for q in state.queue]})]


def _vote(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST, Role.PARTICIPANT})
    q_id = payload.get("queue_id")
    value = bool(payload.get("value", True))
    queue = [QueuedClimb(**{**q.__dict__}) for q in state.queue]
    found = False
    for q in queue:
        if q.id == q_id:
            found = True
            voted = participant_id in q.votes
            if value and not voted:
                q.votes.append(participant_id)
            elif not value and voted:
                q.votes.remove(participant_id)
    if not found:
        raise BadRequest("queue_id not found")
    state = replace(state, queue=queue)
    return state, [Event("queueUpdate", {"queue": [q.__dict__ for q in state.queue]})]


def _reorder(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST})
    order = payload.get("order")
    if not isinstance(order, list):
        raise BadRequest("order must be list[str]")
    by_id = {q.id: q for q in state.queue}
    if set(order) != set(by_id.keys()):
        raise BadRequest("order must reference every queued climb exactly once")
    new_queue = [by_id[qid] for qid in order]
    state = replace(state, queue=new_queue)
    return state, [Event("queueUpdate", {"queue": [q.__dict__ for q in state.queue]})]


def _remove(state, participant_id, payload):
    q_id = payload.get("queue_id")
    q = next((q for q in state.queue if q.id == q_id), None)
    if q is None:
        raise BadRequest("queue_id not found")
    me = state.participants.get(participant_id)
    if me is None:
        raise PermissionDenied("not in session")
    if me.role not in {Role.HOST, Role.COHOST} and q.added_by != participant_id:
        raise PermissionDenied("can only remove your own climb")
    state = replace(state, queue=[x for x in state.queue if x.id != q_id])
    finalists = [f for f in state.finalists if f != q_id]
    state = replace(state, finalists=finalists)
    return state, [Event("queueUpdate", {"queue": [q.__dict__ for q in state.queue]})]


def _mark_finalist(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST})
    q_id = payload.get("queue_id")
    if not any(q.id == q_id for q in state.queue):
        raise BadRequest("queue_id not found")
    if q_id in state.finalists:
        return state, []
    state = replace(state, finalists=[*state.finalists, q_id])
    return state, [Event("finalistsUpdate", {"finalists": list(state.finalists)})]


def _mark_completed(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST, Role.PARTICIPANT})
    q_id = payload.get("queue_id")
    result = payload.get("result") or "sent"
    q = next((q for q in state.queue if q.id == q_id), None)
    if q is None:
        raise BadRequest("queue_id not found")
    done = CompletedClimb(
        climb_id=q.climb_id,
        provider=q.provider,
        name=q.name,
        completed_by=participant_id,
        result=str(result),
        completed_at=now_iso(),
    )
    state = replace(
        state,
        queue=[x for x in state.queue if x.id != q_id],
        finalists=[f for f in state.finalists if f != q_id],
        history=[*state.history, done],
    )
    return state, [
        Event("queueUpdate", {"queue": [q.__dict__ for q in state.queue]}),
        Event("historyUpdate", {"history": [h.__dict__ for h in state.history]}),
    ]


_HANDLERS = {
    "joinRoom": _join,
    "leaveRoom": _leave,
    "setRole": _set_role,
    "setProviders": _set_providers,
    "addToQueue": _add_to_queue,
    "voteClimb": _vote,
    "reorderQueue": _reorder,
    "removeFromQueue": _remove,
    "markFinalist": _mark_finalist,
    "markCompleted": _mark_completed,
}
