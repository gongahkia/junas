from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "cornifer.sqlite3"


def _open_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        init_db()
    return _open_connection()


def init_db() -> None:
    connection = _open_connection()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS boards (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              location TEXT NOT NULL,
              description TEXT NOT NULL,
              creator_id TEXT NOT NULL REFERENCES users(id),
              image_filename TEXT NOT NULL,
              draft INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS board_holds (
              id TEXT PRIMARY KEY,
              board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
              position INTEGER NOT NULL,
              centroid_x REAL NOT NULL,
              centroid_y REAL NOT NULL,
              contour_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS climbs (
              id TEXT PRIMARY KEY,
              board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
              creator_id TEXT NOT NULL REFERENCES users(id),
              name TEXT NOT NULL,
              grade TEXT NOT NULL,
              description TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS climb_holds (
              id TEXT PRIMARY KEY,
              climb_id TEXT NOT NULL REFERENCES climbs(id) ON DELETE CASCADE,
              board_hold_id TEXT NOT NULL REFERENCES board_holds(id) ON DELETE CASCADE,
              role TEXT NOT NULL,
              color TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attempts (
              id TEXT PRIMARY KEY,
              climb_id TEXT NOT NULL REFERENCES climbs(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL REFERENCES users(id),
              tries INTEGER NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ratings (
              id TEXT PRIMARY KEY,
              climb_id TEXT NOT NULL REFERENCES climbs(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL REFERENCES users(id),
              value INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(climb_id, user_id)
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def decode_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
