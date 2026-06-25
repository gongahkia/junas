"""Matter-scoped defined-term store for cross-session document review (item 55).

A "matter" is the M&A-realistic unit above `session_id`: 30+ documents over weeks
across multiple reviewers all share definitional context. session-scope (item 25)
was the right v1 but loses inheritance the moment the review session rotates.
Matter-scope persists across sessions; sessions belong to a matter.

Storage is per-matter JSON sidecar under
`${KAYPOH_JOURNAL_DIR}/matters/{matter_id}/defined_terms.json`:

    {"defined_terms": ["purchaser", "vendor", "spa", ...]}

Hierarchy on `engine.review()`:
    1. terms extracted from the current document
    2. union with session-scoped terms (item 25)
    3. union with matter-scoped terms (this module)

Tenant + matter isolation enforced via `journal_dir(tenant_id)` per item 42 plumbing.

Process-local thread lock protects writes within one process; cross-process
coordination is not attempted (single-tenant deployment is the normal case).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock

from kaypoh.review.journal import journal_dir

_matter_lock = Lock()

_MATTER_ID_RE = re.compile(r"^[A-Za-z0-9_\-:]{1,128}$")  # colon allowed for `{dms_vendor}:{matter_id}` keys


class MatterStoreError(RuntimeError):
    """Raised when matter-scoped defined terms cannot be read safely."""


def _matters_dir(tenant_id: str | None = None) -> Path:
    return journal_dir(tenant_id) / "matters"


def _validate_matter_id(matter_id: str) -> None:
    if not _MATTER_ID_RE.match(matter_id):
        raise ValueError(
            f"invalid matter_id {matter_id!r}: must match [A-Za-z0-9_\\-:]{{1,128}}"
        )


def matter_path(matter_id: str, tenant_id: str | None = None) -> Path:
    _validate_matter_id(matter_id)
    return _matters_dir(tenant_id) / matter_id / "defined_terms.json"


def load_defined_terms(matter_id: str, tenant_id: str | None = None) -> set[str]:
    """Return the casefolded set of defined terms previously accumulated for this matter.
    Empty set when the matter is new. Corrupt/unreadable sidecars fail closed."""
    path = matter_path(matter_id, tenant_id)
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MatterStoreError(f"cannot read matter defined-term sidecar: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MatterStoreError(f"matter defined-term sidecar is not valid JSON: {path}") from exc
    terms = payload.get("defined_terms", [])
    if not isinstance(terms, list):
        raise MatterStoreError(f"matter defined-term sidecar has invalid shape: {path}")
    return {str(t).strip().casefold() for t in terms if t}


def add_defined_terms(matter_id: str, terms: set[str], tenant_id: str | None = None) -> set[str]:
    """Union `terms` into the matter's stored set and return the merged result.
    Casefolds entries on the way in; idempotent on duplicates."""
    if not terms:
        return load_defined_terms(matter_id, tenant_id)
    with _matter_lock:
        existing = load_defined_terms(matter_id, tenant_id)
        merged = existing | {str(t).strip().casefold() for t in terms if t}
        path = matter_path(matter_id, tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"defined_terms": sorted(merged)}, indent=2) + "\n",
            encoding="utf-8",
        )
    return merged


def clear_matter(matter_id: str, tenant_id: str | None = None) -> None:
    """Remove the matter sidecar. Used by tests; not exposed via API."""
    path = matter_path(matter_id, tenant_id)
    if path.exists():
        path.unlink()
