from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateSessionReq(BaseModel):
    host_display_name: str = Field(min_length=1, max_length=40)
    enabled_providers: list[str] = Field(default_factory=list)


class CreateSessionResp(BaseModel):
    code: str
    host_participant_id: str
    host_secret: str


class JoinSessionReq(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)


class JoinSessionResp(BaseModel):
    participant_id: str
    ws_token: str


class SessionSummary(BaseModel):
    code: str
    enabled_providers: list[str]
    participant_count: int
    queue_length: int
    created_at: str
    ended_at: str | None


class AttachCredentialsReq(BaseModel):
    provider: str
    credentials: dict[str, Any]
    host_secret: str


class AttachCredentialsResp(BaseModel):
    provider: str
    ok: bool


class ProviderDescriptor(BaseModel):
    key: str
    name: str
    status: str
    requires_credentials: bool


class ClimbOut(BaseModel):
    id: str
    provider: str
    name: str
    setter: str | None
    grade: str | None
    angle: int | None
    ascents: int | None


class ClimbsResp(BaseModel):
    climbs: list[ClimbOut]


class ErrorResp(BaseModel):
    error: str
    detail: str | None = None
