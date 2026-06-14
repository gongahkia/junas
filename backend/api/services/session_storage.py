from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from api.models.sessions import SessionCreate, SessionDetail, SessionMeta, SessionUpdate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _title_from_node_map(node_map: dict[str, Any]) -> str:
    nodes = [node for node in node_map.values() if isinstance(node, dict)]
    user_nodes = [node for node in nodes if node.get("role") == "user" and str(node.get("content") or "").strip()]
    if not user_nodes:
        return "Untitled"
    first = sorted(user_nodes, key=lambda node: int(node.get("timestamp") or 0))[0]
    return str(first.get("content") or "Untitled").replace("\n", " ").strip()[:60] or "Untitled"


class SessionStorage:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS copilot_sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    user_id TEXT NULL,
                    node_map_json TEXT NOT NULL DEFAULT '{}',
                    current_leaf_id TEXT NOT NULL DEFAULT '',
                    message_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_copilot_sessions_updated_at ON copilot_sessions(updated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_copilot_sessions_deleted_at ON copilot_sessions(deleted_at)")

    def list_sessions(self) -> list[SessionMeta]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, user_id, message_count, created_at, updated_at, deleted_at
                FROM copilot_sessions
                WHERE deleted_at IS NULL
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [self._meta_from_row(row) for row in rows]

    def get_session(self, session_id: str) -> SessionDetail | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, user_id, node_map_json, current_leaf_id, message_count, created_at, updated_at, deleted_at
                FROM copilot_sessions
                WHERE id = ? AND deleted_at IS NULL
                """,
                (session_id,),
            ).fetchone()
        return self._detail_from_row(row) if row else None

    def create_session(self, payload: SessionCreate) -> SessionDetail:
        session_id = payload.id or str(uuid4())
        return self.save_session(
            session_id=session_id,
            payload=SessionUpdate(
                title=payload.title,
                node_map=payload.node_map,
                current_leaf_id=payload.current_leaf_id,
                user_id=payload.user_id,
            ),
            create=True,
        )

    def save_session(self, session_id: str, payload: SessionUpdate, create: bool = False) -> SessionDetail:
        existing = self.get_session(session_id)
        if existing is None and not create:
            raise KeyError(session_id)

        node_map = payload.node_map if payload.node_map is not None else (existing.node_map if existing else {})
        current_leaf_id = payload.current_leaf_id if payload.current_leaf_id is not None else (existing.current_leaf_id if existing else "")
        title = payload.title or (existing.title if existing else "") or _title_from_node_map(node_map)
        user_id = payload.user_id if payload.user_id is not None else (existing.user_id if existing else None)
        created_at = existing.created_at.isoformat() if existing else _now()
        updated_at = _now()
        message_count = len(node_map)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO copilot_sessions (
                    id, title, user_id, node_map_json, current_leaf_id,
                    message_count, created_at, updated_at, deleted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    user_id = excluded.user_id,
                    node_map_json = excluded.node_map_json,
                    current_leaf_id = excluded.current_leaf_id,
                    message_count = excluded.message_count,
                    updated_at = excluded.updated_at,
                    deleted_at = NULL
                """,
                (
                    session_id,
                    title,
                    user_id,
                    json.dumps(node_map, sort_keys=True),
                    current_leaf_id,
                    message_count,
                    created_at,
                    updated_at,
                ),
            )
        detail = self.get_session(session_id)
        if detail is None:
            raise RuntimeError("session save failed")
        return detail

    def rename_session(self, session_id: str, title: str) -> SessionDetail:
        clean = title.strip()
        if not clean:
            raise ValueError("title must not be empty")
        updated_at = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE copilot_sessions
                SET title = ?, updated_at = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (clean[:255], updated_at, session_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(session_id)
        detail = self.get_session(session_id)
        if detail is None:
            raise RuntimeError("session rename failed")
        return detail

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE copilot_sessions
                SET deleted_at = ?, updated_at = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (_now(), _now(), session_id),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _meta_from_row(row: sqlite3.Row) -> SessionMeta:
        return SessionMeta(
            id=row["id"],
            title=row["title"],
            user_id=row["user_id"],
            message_count=row["message_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"],
        )

    @classmethod
    def _detail_from_row(cls, row: sqlite3.Row) -> SessionDetail:
        meta = cls._meta_from_row(row)
        try:
            node_map = json.loads(row["node_map_json"] or "{}")
        except json.JSONDecodeError:
            node_map = {}
        return SessionDetail(
            **meta.model_dump(),
            node_map=node_map if isinstance(node_map, dict) else {},
            current_leaf_id=row["current_leaf_id"] or "",
        )
