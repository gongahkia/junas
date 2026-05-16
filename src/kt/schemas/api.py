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
    host_secret: str
    session_read_token: str


class SessionSummary(BaseModel):
    code: str
    provider: str
    enabled_providers: list[str]
    attached_providers: list[str]
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
    capabilities: dict[str, bool] = Field(default_factory=dict)
    source: str | None = None
    status_reason: str | None = None
    status_reason_code: str | None = None
    is_data_ready: bool = False
    readiness: str = "limited"
    taxonomy_version: str = "2026-04-aggregator-v1"


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


class CacheMeta(BaseModel):
    hit: bool
    stale: bool
    cached_at: str | None = None
    expires_at: str | None = None


class ResponseMeta(BaseModel):
    provider: str
    fetched_at: str
    cache: CacheMeta
    served_by: list[str] = Field(default_factory=list)


class ProviderWarning(BaseModel):
    provider: str
    error: str
    detail: str | None = None
    stale_cache_served: bool = False


class ClimbsResp(BaseModel):
    climbs: list[ClimbOut]
    next_cursor: str | None = None
    total_estimate: int | None = None
    meta: ResponseMeta | None = None
    warnings: list[ProviderWarning] = Field(default_factory=list)


class LayoutOut(BaseModel):
    id: str
    name: str
    angles: list[int]
    extras: dict[str, Any] = Field(default_factory=dict)


class LayoutsResp(BaseModel):
    layouts: list[LayoutOut]
    meta: ResponseMeta | None = None
    warnings: list[ProviderWarning] = Field(default_factory=list)


class ErrorResp(BaseModel):
    error: str
    detail: str | None = None
