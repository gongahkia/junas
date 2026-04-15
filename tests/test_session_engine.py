from __future__ import annotations

import pytest

from kt.realtime.session_engine import (
    BadRequest,
    PermissionDenied,
    apply_action,
)
from kt.realtime.state import Participant, Role, SessionState, now_iso


def _state(host="h1") -> SessionState:
    return SessionState(
        code="ABCDEF",
        host_id=host,
        enabled_providers=["tension"],
        participants={
            host: Participant(id=host, display_name="H", role=Role.HOST, joined_at=now_iso())
        },
    )


def test_join_adds_participant():
    s = _state()
    s2, evs = apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "Guest"}})
    assert "g1" in s2.participants
    assert s2.participants["g1"].role is Role.PARTICIPANT
    assert evs and evs[0].type == "participantsUpdate"


def test_join_rejects_long_name():
    s = _state()
    with pytest.raises(BadRequest):
        apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "x" * 41}})


def test_host_cannot_leave():
    s = _state()
    with pytest.raises(PermissionDenied):
        apply_action(s, "h1", {"type": "leaveRoom", "payload": {}})


def test_set_role_promotes_cohost():
    s = _state()
    s, _ = apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "Guest"}})
    s, _ = apply_action(
        s, "h1", {"type": "setRole", "payload": {"participant_id": "g1", "role": "cohost"}}
    )
    assert s.participants["g1"].role is Role.COHOST


def test_only_host_sets_providers():
    s = _state()
    s, _ = apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "G"}})
    with pytest.raises(PermissionDenied):
        apply_action(s, "g1", {"type": "setProviders", "payload": {"providers": ["moonboard"]}})


def test_add_to_queue_requires_enabled_provider():
    s = _state()
    with pytest.raises(BadRequest):
        apply_action(
            s, "h1",
            {"type": "addToQueue", "payload": {"provider": "moonboard", "climb_id": "c1", "name": "x"}},
        )


def test_add_to_queue_dedup():
    s = _state()
    s, _ = apply_action(
        s, "h1",
        {"type": "addToQueue", "payload": {"provider": "tension", "climb_id": "c1", "name": "x"}},
    )
    with pytest.raises(BadRequest):
        apply_action(
            s, "h1",
            {"type": "addToQueue", "payload": {"provider": "tension", "climb_id": "c1", "name": "x"}},
        )


def test_vote_idempotent_and_toggle():
    s = _state()
    s, _ = apply_action(
        s, "h1",
        {"type": "addToQueue", "payload": {"provider": "tension", "climb_id": "c1", "name": "x"}},
    )
    qid = s.queue[0].id
    s, _ = apply_action(s, "h1", {"type": "voteClimb", "payload": {"queue_id": qid}})
    assert s.queue[0].votes == ["h1"]
    s, _ = apply_action(s, "h1", {"type": "voteClimb", "payload": {"queue_id": qid}})
    assert s.queue[0].votes == ["h1"]  # idempotent on add
    s, _ = apply_action(
        s, "h1", {"type": "voteClimb", "payload": {"queue_id": qid, "value": False}}
    )
    assert s.queue[0].votes == []


def test_reorder_must_be_complete_permutation():
    s = _state()
    s, _ = apply_action(
        s, "h1",
        {"type": "addToQueue", "payload": {"provider": "tension", "climb_id": "a", "name": "x"}},
    )
    s, _ = apply_action(
        s, "h1",
        {"type": "addToQueue", "payload": {"provider": "tension", "climb_id": "b", "name": "y"}},
    )
    with pytest.raises(BadRequest):
        apply_action(
            s, "h1", {"type": "reorderQueue", "payload": {"order": ["tension:a"]}}
        )
    s2, _ = apply_action(
        s, "h1",
        {"type": "reorderQueue", "payload": {"order": ["tension:b", "tension:a"]}},
    )
    assert [q.climb_id for q in s2.queue] == ["b", "a"]


def test_remove_self_only_for_participant():
    s = _state()
    s, _ = apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "G"}})
    s, _ = apply_action(
        s, "h1",
        {"type": "addToQueue", "payload": {"provider": "tension", "climb_id": "c1", "name": "x"}},
    )
    qid = s.queue[0].id
    with pytest.raises(PermissionDenied):
        apply_action(s, "g1", {"type": "removeFromQueue", "payload": {"queue_id": qid}})
    # host can remove
    s2, _ = apply_action(s, "h1", {"type": "removeFromQueue", "payload": {"queue_id": qid}})
    assert s2.queue == []


def test_complete_moves_to_history():
    s = _state()
    s, _ = apply_action(
        s, "h1",
        {"type": "addToQueue", "payload": {"provider": "tension", "climb_id": "c1", "name": "x"}},
    )
    qid = s.queue[0].id
    s, _ = apply_action(s, "h1", {"type": "markFinalist", "payload": {"queue_id": qid}})
    assert s.finalists == [qid]
    s, _ = apply_action(
        s, "h1",
        {"type": "markCompleted", "payload": {"queue_id": qid, "result": "sent"}},
    )
    assert s.queue == [] and s.finalists == []
    assert len(s.history) == 1 and s.history[0].result == "sent"


def test_unknown_action():
    s = _state()
    with pytest.raises(BadRequest):
        apply_action(s, "h1", {"type": "noSuchAction", "payload": {}})


def test_state_roundtrip():
    s = _state()
    s, _ = apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "G"}})
    s, _ = apply_action(
        s, "h1",
        {"type": "addToQueue", "payload": {"provider": "tension", "climb_id": "c", "name": "n"}},
    )
    d = s.to_dict()
    s2 = SessionState.from_dict(d)
    assert s2.to_dict() == d
