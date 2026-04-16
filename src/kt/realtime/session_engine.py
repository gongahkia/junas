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


def _kick(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST})
    target = payload.get("participant_id")
    if not target or target not in state.participants:
        raise BadRequest("participant_id required")
    if target == state.host_id:
        raise BadRequest("cannot kick host")
    parts = {k: v for k, v in state.participants.items() if k != target}
    queue = [q for q in state.queue if q.added_by != target]
    for q in queue:
        q.votes = [v for v in q.votes if v != target]
    kept_ids = {q.id for q in queue}
    finalists = [f for f in state.finalists if f in kept_ids]
    state = replace(state, participants=parts, queue=queue, finalists=finalists)
    return state, [
        Event("participantsUpdate", {"participants": [p.__dict__ for p in state.participants.values()]}),
        Event("queueUpdate", {"queue": [q.__dict__ for q in state.queue]}),
        Event("participantKicked", {"participant_id": target}),
    ]


def _add_to_queue(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST, Role.PARTICIPANT})
    climb_id = payload.get("climb_id")
    name = payload.get("name") or ""
    if not climb_id:
        raise BadRequest("climb_id required")
    enabled_providers = state.providers()
    if not enabled_providers:
        raise BadRequest("session has no provider")
    provider = payload.get("provider") or state.provider or enabled_providers[0]
    if provider not in enabled_providers:
        raise BadRequest("provider not enabled for session")
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


def _set_providers(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST})
    raw = payload.get("enabled_providers", payload.get("providers"))
    if not isinstance(raw, list):
        raise BadRequest("enabled_providers must be list[str]")
    enabled_providers = []
    for provider in raw:
        if not isinstance(provider, str) or not provider.strip():
            raise BadRequest("enabled_providers must be list[str]")
        provider = provider.strip()
        if provider not in enabled_providers:
            enabled_providers.append(provider)
    if not enabled_providers:
        raise BadRequest("at least one provider required")

    kept_ids = {q.id for q in state.queue if q.provider in enabled_providers}
    queue = [q for q in state.queue if q.id in kept_ids]
    finalists = [f for f in state.finalists if f in kept_ids]
    state = replace(
        state,
        provider=enabled_providers[0],
        enabled_providers=enabled_providers,
        queue=queue,
        finalists=finalists,
    )
    return state, [
        Event("providersUpdate", {"enabled_providers": enabled_providers}),
        Event("queueUpdate", {"queue": [q.__dict__ for q in state.queue]}),
    ]


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


def _send_chat(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST, Role.PARTICIPANT})
    body = str(payload.get("body") or "").strip()
    if not body or len(body) > 1000:
        raise BadRequest("body required (<= 1000 chars)")
    return state, [
        Event(
            "chatMessage",
            {
                "participant_id": participant_id,
                "body": body,
                "sent_at": now_iso(),
            },
        )
    ]


def _send_beta(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST, Role.PARTICIPANT})
    q_id = payload.get("queue_id")
    body = str(payload.get("body") or "").strip()
    if not q_id or not any(q.id == q_id for q in state.queue):
        raise BadRequest("queue_id not found")
    if not body or len(body) > 1000:
        raise BadRequest("body required (<= 1000 chars)")
    return state, [
        Event(
            "betaMessage",
            {
                "participant_id": participant_id,
                "queue_id": q_id,
                "body": body,
                "sent_at": now_iso(),
            },
        )
    ]


def _vote_quality(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST, Role.PARTICIPANT})
    q_id = payload.get("queue_id")
    stars = payload.get("stars")
    q = next((x for x in state.queue if x.id == q_id), None)
    if q is None:
        raise BadRequest("queue_id not found")
    if not isinstance(stars, (int, float)) or not (0 <= float(stars) <= 5):
        raise BadRequest("stars must be 0..5")
    return state, [
        Event(
            "qualityVote",
            {
                "participant_id": participant_id,
                "queue_id": q_id,
                "provider": q.provider,
                "climb_id": q.climb_id,
                "stars": float(stars),
            },
        )
    ]


def _vote_grade(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST, Role.COHOST, Role.PARTICIPANT})
    q_id = payload.get("queue_id")
    grade_v = payload.get("grade_v")
    q = next((x for x in state.queue if x.id == q_id), None)
    if q is None:
        raise BadRequest("queue_id not found")
    if not isinstance(grade_v, int) or not (0 <= grade_v <= 17):
        raise BadRequest("grade_v must be an int in 0..17")
    return state, [
        Event(
            "gradeVote",
            {
                "participant_id": participant_id,
                "queue_id": q_id,
                "provider": q.provider,
                "climb_id": q.climb_id,
                "grade_v": grade_v,
            },
        )
    ]


def _set_session_meta(state, participant_id, payload):
    _require(state, participant_id, {Role.HOST})
    changes: dict[str, Any] = {}
    if "title" in payload:
        changes["title"] = str(payload.get("title") or "").strip()[:200]
    if "description" in payload:
        changes["description"] = str(payload.get("description") or "").strip()[:1000]
    if "tags" in payload:
        raw = payload.get("tags")
        if not isinstance(raw, list):
            raise BadRequest("tags must be list[str]")
        cleaned = []
        for t in raw:
            tag = str(t).strip()[:40]
            if tag and tag not in cleaned:
                cleaned.append(tag)
        changes["tags"] = cleaned
    if not changes:
        return state, []
    state = replace(state, **changes)
    return state, [Event("sessionMetaUpdate", changes)]


_HANDLERS = {
    "joinRoom": _join,
    "leaveRoom": _leave,
    "setRole": _set_role,
    "setProviders": _set_providers,
    "kickParticipant": _kick,
    "addToQueue": _add_to_queue,
    "voteClimb": _vote,
    "reorderQueue": _reorder,
    "removeFromQueue": _remove,
    "markFinalist": _mark_finalist,
    "markCompleted": _mark_completed,
    "sendChat": _send_chat,
    "sendBeta": _send_beta,
    "voteQuality": _vote_quality,
    "voteGrade": _vote_grade,
    "setSessionMeta": _set_session_meta,
}
