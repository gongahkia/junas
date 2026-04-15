"""Session state data model (pure, no IO)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Role(str, Enum):
    HOST = "host"
    COHOST = "cohost"
    PARTICIPANT = "participant"


@dataclass
class Participant:
    id: str
    display_name: str
    role: Role
    joined_at: str


@dataclass
class QueuedClimb:
    id: str
    provider: str
    climb_id: str
    name: str
    added_by: str
    votes: list[str] = field(default_factory=list)
    added_at: str = ""


@dataclass
class CompletedClimb:
    climb_id: str
    provider: str
    name: str
    completed_by: str
    result: str
    completed_at: str


@dataclass
class SessionState:
    code: str
    host_id: str
    enabled_providers: list[str] = field(default_factory=list)
    participants: dict[str, Participant] = field(default_factory=dict)
    queue: list[QueuedClimb] = field(default_factory=list)
    finalists: list[str] = field(default_factory=list)
    history: list[CompletedClimb] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "host_id": self.host_id,
            "enabled_providers": list(self.enabled_providers),
            "participants": {pid: asdict(p) for pid, p in self.participants.items()},
            "queue": [asdict(q) for q in self.queue],
            "finalists": list(self.finalists),
            "history": [asdict(h) for h in self.history],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SessionState:
        parts = {
            pid: Participant(
                id=p["id"],
                display_name=p["display_name"],
                role=Role(p["role"]),
                joined_at=p["joined_at"],
            )
            for pid, p in d.get("participants", {}).items()
        }
        queue = [QueuedClimb(**q) for q in d.get("queue", [])]
        history = [CompletedClimb(**h) for h in d.get("history", [])]
        return cls(
            code=d["code"],
            host_id=d["host_id"],
            enabled_providers=list(d.get("enabled_providers") or []),
            participants=parts,
            queue=queue,
            finalists=list(d.get("finalists") or []),
            history=history,
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
