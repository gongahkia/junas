from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionMeta(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    deleted_at: datetime | None = None
    user_id: str | None = None


class SessionDetail(SessionMeta):
    node_map: dict[str, Any] = Field(default_factory=dict)
    current_leaf_id: str = ""


class SessionCreate(BaseModel):
    id: str | None = None
    title: str | None = None
    node_map: dict[str, Any] = Field(default_factory=dict)
    current_leaf_id: str = ""
    user_id: str | None = None


class SessionUpdate(BaseModel):
    title: str | None = None
    node_map: dict[str, Any] | None = None
    current_leaf_id: str | None = None
    user_id: str | None = None


class SessionRename(BaseModel):
    title: str
