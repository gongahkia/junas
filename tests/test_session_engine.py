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
        provider="tension",
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


def test_host_can_kick_participant():
    s = _state()
    s, _ = apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "G"}})
    s, evs = apply_action(
        s, "h1", {"type": "kickParticipant", "payload": {"participant_id": "g1"}}
    )
    assert "g1" not in s.participants
    assert any(e.type == "participantKicked" for e in evs)


def test_host_cannot_kick_self():
    s = _state()
    with pytest.raises(BadRequest):
        apply_action(s, "h1", {"type": "kickParticipant", "payload": {"participant_id": "h1"}})


def test_non_host_cannot_kick():
    s = _state()
    s, _ = apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "G"}})
    s, _ = apply_action(s, "g2", {"type": "joinRoom", "payload": {"display_name": "G2"}})
    with pytest.raises(PermissionDenied):
        apply_action(s, "g1", {"type": "kickParticipant", "payload": {"participant_id": "g2"}})


def test_add_to_queue_requires_session_provider():
    s = SessionState(
        code="ABCDEF", host_id="h1", provider="",
        participants={"h1": Participant(id="h1", display_name="H", role=Role.HOST, joined_at=now_iso())},
    )
    with pytest.raises(BadRequest):
        apply_action(s, "h1", {"type": "addToQueue", "payload": {"climb_id": "c1"}})


def test_add_to_queue_dedup():
    s = _state()
    s, _ = apply_action(s, "h1", {"type": "addToQueue", "payload": {"climb_id": "c1", "name": "x"}})
    with pytest.raises(BadRequest):
        apply_action(s, "h1", {"type": "addToQueue", "payload": {"climb_id": "c1", "name": "x"}})


def test_add_to_queue_can_target_enabled_provider():
    s = _state()
    s = SessionState(
        code=s.code,
        host_id=s.host_id,
        provider="tension",
        enabled_providers=["tension", "moonboard_catalog"],
        participants=s.participants,
    )
    s, _ = apply_action(
        s,
        "h1",
        {
            "type": "addToQueue",
            "payload": {
                "provider": "moonboard_catalog",
                "climb_id": "m1",
                "name": "Moon",
            },
        },
    )
    assert s.queue[0].id == "moonboard_catalog:m1"
    assert s.queue[0].provider == "moonboard_catalog"


def test_add_to_queue_rejects_disabled_provider():
    s = _state()
    with pytest.raises(BadRequest):
        apply_action(
            s,
            "h1",
            {
                "type": "addToQueue",
                "payload": {"provider": "crux", "climb_id": "c1", "name": "x"},
            },
        )


def test_set_providers_updates_session_and_prunes_disabled_queue_entries():
    s = _state()
    s = SessionState(
        code=s.code,
        host_id=s.host_id,
        provider="tension",
        enabled_providers=["tension", "moonboard_catalog"],
        participants=s.participants,
    )
    s, _ = apply_action(
        s,
        "h1",
        {
            "type": "addToQueue",
            "payload": {"provider": "tension", "climb_id": "t1", "name": "Tension"},
        },
    )
    s, _ = apply_action(
        s,
        "h1",
        {
            "type": "addToQueue",
            "payload": {
                "provider": "moonboard_catalog",
                "climb_id": "m1",
                "name": "Moon",
            },
        },
    )
    s, _ = apply_action(
        s,
        "h1",
        {"type": "markFinalist", "payload": {"queue_id": "tension:t1"}},
    )
    s, evs = apply_action(
        s,
        "h1",
        {"type": "setProviders", "payload": {"enabled_providers": ["moonboard_catalog"]}},
    )
    assert s.provider == "moonboard_catalog"
    assert s.enabled_providers == ["moonboard_catalog"]
    assert [q.id for q in s.queue] == ["moonboard_catalog:m1"]
    assert s.finalists == []
    assert any(e.type == "providersUpdate" for e in evs)


def test_vote_idempotent_and_toggle():
    s = _state()
    s, _ = apply_action(s, "h1", {"type": "addToQueue", "payload": {"climb_id": "c1", "name": "x"}})
    qid = s.queue[0].id
    s, _ = apply_action(s, "h1", {"type": "voteClimb", "payload": {"queue_id": qid}})
    assert s.queue[0].votes == ["h1"]
    s, _ = apply_action(s, "h1", {"type": "voteClimb", "payload": {"queue_id": qid}})
    assert s.queue[0].votes == ["h1"]
    s, _ = apply_action(s, "h1", {"type": "voteClimb", "payload": {"queue_id": qid, "value": False}})
    assert s.queue[0].votes == []


def test_reorder_must_be_complete_permutation():
    s = _state()
    s, _ = apply_action(s, "h1", {"type": "addToQueue", "payload": {"climb_id": "a", "name": "x"}})
    s, _ = apply_action(s, "h1", {"type": "addToQueue", "payload": {"climb_id": "b", "name": "y"}})
    with pytest.raises(BadRequest):
        apply_action(s, "h1", {"type": "reorderQueue", "payload": {"order": ["tension:a"]}})
    s2, _ = apply_action(
        s, "h1", {"type": "reorderQueue", "payload": {"order": ["tension:b", "tension:a"]}},
    )
    assert [q.climb_id for q in s2.queue] == ["b", "a"]


def test_remove_self_only_for_participant():
    s = _state()
    s, _ = apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "G"}})
    s, _ = apply_action(s, "h1", {"type": "addToQueue", "payload": {"climb_id": "c1", "name": "x"}})
    qid = s.queue[0].id
    with pytest.raises(PermissionDenied):
        apply_action(s, "g1", {"type": "removeFromQueue", "payload": {"queue_id": qid}})
    s2, _ = apply_action(s, "h1", {"type": "removeFromQueue", "payload": {"queue_id": qid}})
    assert s2.queue == []


def test_complete_moves_to_history():
    s = _state()
    s, _ = apply_action(s, "h1", {"type": "addToQueue", "payload": {"climb_id": "c1", "name": "x"}})
    qid = s.queue[0].id
    s, _ = apply_action(s, "h1", {"type": "markFinalist", "payload": {"queue_id": qid}})
    assert s.finalists == [qid]
    s, _ = apply_action(s, "h1", {"type": "markCompleted", "payload": {"queue_id": qid, "result": "sent"}})
    assert s.queue == [] and s.finalists == []
    assert len(s.history) == 1 and s.history[0].result == "sent"


def test_unknown_action():
    s = _state()
    with pytest.raises(BadRequest):
        apply_action(s, "h1", {"type": "noSuchAction", "payload": {}})


def test_state_roundtrip():
    s = _state()
    s, _ = apply_action(s, "g1", {"type": "joinRoom", "payload": {"display_name": "G"}})
    s, _ = apply_action(s, "h1", {"type": "addToQueue", "payload": {"climb_id": "c", "name": "n"}})
    d = s.to_dict()
    s2 = SessionState.from_dict(d)
    assert s2.to_dict() == d
