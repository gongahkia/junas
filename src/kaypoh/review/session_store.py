"""Session-scoped defined-term store for cross-document review sessions.

A "review session" groups documents that share a definitional context: a SPA defines `the
"Purchaser"`, and the matching disclosure schedule a few minutes later should treat
`Purchaser` as suppressed even though that document doesn't define it itself.

Storage is per-session JSON sidecar under `${KAYPOH_JOURNAL_DIR}/sessions/{session_id}.json`:

    {"defined_terms": ["purchaser", "vendor", "spa", ...]}

Terms are casefolded before storage (matching `extract_defined_terms`'s output). Adding a
term that already exists is a no-op.

This module is process-local for now: a thread lock protects writes within one process; we
do not coordinate across processes. The journal directory is normally single-tenant per
deployment, so concurrent writers from different processes is an acceptable rare race.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock

from kaypoh.review.journal import journal_dir

_session_lock = Lock()

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


def _sessions_dir(tenant_id: str | None = None) -> Path:
    return journal_dir(tenant_id) / "sessions"


def _validate_session_id(session_id: str) -> None:
    if not _SESSION_ID_RE.match(session_id):
        raise ValueError(
            f"invalid session_id {session_id!r}: must match [A-Za-z0-9_-]{{1,128}}"
        )


def session_path(session_id: str, tenant_id: str | None = None) -> Path:
    _validate_session_id(session_id)
    return _sessions_dir(tenant_id) / f"{session_id}.json"


def load_defined_terms(session_id: str, tenant_id: str | None = None) -> set[str]:
    """Return the casefolded set of defined terms previously accumulated for this session.
    Empty set when the session is new or the file is missing/corrupt."""
    path = session_path(session_id, tenant_id)
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    terms = payload.get("defined_terms", [])
    if not isinstance(terms, list):
        return set()
    return {str(t).strip().casefold() for t in terms if t}


def add_defined_terms(session_id: str, terms: set[str], tenant_id: str | None = None) -> set[str]:
    """Union `terms` into the session's stored set and return the merged result.
    Casefolds entries on the way in; idempotent on duplicates."""
    if not terms:
        return load_defined_terms(session_id, tenant_id)
    with _session_lock:
        existing = load_defined_terms(session_id, tenant_id)
        merged = existing | {str(t).strip().casefold() for t in terms if t}
        path = session_path(session_id, tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"defined_terms": sorted(merged)}, indent=2) + "\n",
            encoding="utf-8",
        )
    return merged


def clear_session(session_id: str, tenant_id: str | None = None) -> None:
    """Remove the session sidecar. Used by tests; not exposed via API."""
    path = session_path(session_id, tenant_id)
    if path.exists():
        path.unlink()
