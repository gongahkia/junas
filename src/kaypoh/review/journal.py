"""Append-only HMAC-chained event journal for review decisions and audit-pack contents.

Every event written here is sealed: it carries `prev_hash` (the HMAC of the previous entry)
and `hmac` (HMAC-SHA256 of the canonical event message keyed by `KAYPOH_JOURNAL_KEY`). Any
mutation to a prior line invalidates every subsequent HMAC, so internal audit can detect
tampering with a single sweep.

Storage is a single append-only JSONL file at `${KAYPOH_JOURNAL_DIR:-./kaypoh-journal}/journal.jsonl`.
One file simplifies chain verification at the cost of unbounded growth; rotation is a future
concern that needs a documented cross-file chain link.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any


GENESIS_HASH = "GENESIS"
DEFAULT_JOURNAL_DIR_NAME = "kaypoh-journal"
DEFAULT_DEV_KEY = b"kaypoh-default-dev-key"  # production must set KAYPOH_JOURNAL_KEY

_journal_lock = Lock()


@dataclass(frozen=True)
class JournalEntry:
    seq: int
    ts: str
    event_type: str
    review_id: str
    payload: dict[str, Any]
    prev_hash: str
    hmac: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "seq": self.seq,
                "ts": self.ts,
                "event_type": self.event_type,
                "review_id": self.review_id,
                "payload": self.payload,
                "prev_hash": self.prev_hash,
                "hmac": self.hmac,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JournalEntry":
        return cls(
            seq=int(data["seq"]),
            ts=str(data["ts"]),
            event_type=str(data["event_type"]),
            review_id=str(data["review_id"]),
            payload=dict(data["payload"]),
            prev_hash=str(data["prev_hash"]),
            hmac=str(data["hmac"]),
        )


def journal_dir() -> Path:
    return Path(os.environ.get("KAYPOH_JOURNAL_DIR", f"./{DEFAULT_JOURNAL_DIR_NAME}"))


def journal_path() -> Path:
    return journal_dir() / "journal.jsonl"


def _journal_key() -> bytes:
    key = os.environ.get("KAYPOH_JOURNAL_KEY", "")
    return key.encode("utf-8") if key else DEFAULT_DEV_KEY


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_hmac(
    *, seq: int, ts: str, event_type: str, review_id: str, payload: dict[str, Any], prev_hash: str
) -> str:
    message = f"{seq}|{ts}|{event_type}|{review_id}|{_canonical_payload(payload)}|{prev_hash}".encode("utf-8")
    return hmac.new(_journal_key(), message, hashlib.sha256).hexdigest()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_last_entry(path: Path) -> JournalEntry | None:
    if not path.exists():
        return None
    last_line: str | None = None
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if last_line is None:
        return None
    return JournalEntry.from_dict(json.loads(last_line))


def append_event(*, event_type: str, review_id: str, payload: dict[str, Any]) -> JournalEntry:
    """Append a single event, chained to the previous entry. Thread-safe within a process."""
    with _journal_lock:
        path = journal_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        last = _read_last_entry(path)
        seq = (last.seq + 1) if last else 0
        prev_hash = last.hmac if last else GENESIS_HASH
        ts = _now_iso()
        entry_hmac = _compute_hmac(
            seq=seq, ts=ts, event_type=event_type, review_id=review_id, payload=payload, prev_hash=prev_hash
        )
        entry = JournalEntry(
            seq=seq,
            ts=ts,
            event_type=event_type,
            review_id=review_id,
            payload=payload,
            prev_hash=prev_hash,
            hmac=entry_hmac,
        )
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry.to_json() + "\n")
        return entry


def read_journal(*, review_id: str | None = None) -> list[JournalEntry]:
    path = journal_path()
    if not path.exists():
        return []
    entries: list[JournalEntry] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            entry = JournalEntry.from_dict(json.loads(stripped))
            if review_id is None or entry.review_id == review_id:
                entries.append(entry)
    return entries


def verify_chain(entries: list[JournalEntry] | None = None) -> tuple[bool, list[str]]:
    """Recompute the HMAC chain over `entries` (or the whole journal). Returns (valid, errors)."""
    if entries is None:
        entries = read_journal()
    errors: list[str] = []
    prev_hash = GENESIS_HASH
    expected_seq = 0
    for entry in entries:
        if entry.seq != expected_seq:
            errors.append(f"seq mismatch at expected {expected_seq}: got {entry.seq}")
        if entry.prev_hash != prev_hash:
            errors.append(f"prev_hash mismatch at seq {entry.seq}")
        expected_hmac = _compute_hmac(
            seq=entry.seq,
            ts=entry.ts,
            event_type=entry.event_type,
            review_id=entry.review_id,
            payload=entry.payload,
            prev_hash=entry.prev_hash,
        )
        if entry.hmac != expected_hmac:
            errors.append(f"hmac mismatch at seq {entry.seq}")
        prev_hash = entry.hmac
        expected_seq = entry.seq + 1
    return len(errors) == 0, errors
