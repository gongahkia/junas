from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class CreateSessionReq(BaseModel):
    host_display_name: str = Field(min_length=1, max_length=40)
    provider: str | None = Field(default=None, min_length=1)
    enabled_providers: list[str] | None = None

    @model_validator(mode="after")
    def normalize_providers(self) -> CreateSessionReq:
        enabled = [p.strip() for p in (self.enabled_providers or []) if p.strip()]
        if self.provider:
            primary = self.provider.strip()
            enabled = [primary, *(p for p in enabled if p != primary)]
        if not enabled:
            raise ValueError("provider or enabled_providers required")
        self.provider = self.provider or enabled[0]
        self.enabled_providers = enabled
        return self


class CreateSessionResp(BaseModel):
    code: str
    host_participant_id: str
    host_secret: str
    host_ws_token: str


class JoinSessionReq(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)


class JoinSessionResp(BaseModel):
    participant_id: str
    ws_token: str


class SessionSummary(BaseModel):
    code: str
    provider: str
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


class HostTokenReq(BaseModel):
    host_secret: str


class HostTokenResp(BaseModel):
    participant_id: str
    ws_token: str


class ProviderDescriptor(BaseModel):
    key: str
    name: str
    status: str
    requires_credentials: bool


class GradeOut(BaseModel):
    raw: str | None = None
    v: int | None = None
    font: str | None = None
    yds: str | None = None
    uiaa: str | None = None


class MediaRef(BaseModel):
    kind: str  # "image" | "video" | "thumbnail"
    url: str


class SetterRef(BaseModel):
    name: str | None = None
    url: str | None = None


class ClimbOut(BaseModel):
    id: str
    provider: str
    name: str
    setter: str | None  # legacy string form; prefer setter_ref
    setter_ref: SetterRef | None = None
    grade: str | None  # legacy raw grade string; prefer grades
    grades: GradeOut | None = None
    angle: int | None
    ascents: int | None
    stars: float | None = None
    holds: list[Any] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    media: list[MediaRef] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)


class ClimbsResp(BaseModel):
    climbs: list[ClimbOut]
    next_cursor: str | None = None
    total_estimate: int | None = None


class LayoutOut(BaseModel):
    id: str
    name: str
    angles: list[int]
    extras: dict[str, Any] = Field(default_factory=dict)


class LayoutsResp(BaseModel):
    layouts: list[LayoutOut]


class ErrorResp(BaseModel):
    error: str
    detail: str | None = None
