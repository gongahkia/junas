from __future__ import annotations

from pydantic import BaseModel, Field

_RESULT_PATTERN = r"^(sent|flash|onsight|attempted|project|repeat)$"


class LogbookCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    climb_id: str = Field(min_length=1, max_length=128)
    result: str = Field(pattern=_RESULT_PATTERN)
    name: str | None = Field(default=None, max_length=200)
    grade_at_send: str | None = Field(default=None, max_length=16)
    attempts: int | None = Field(default=None, ge=0, le=10_000)
    rpe: int | None = Field(default=None, ge=1, le=10)
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
    angle: int | None = Field(default=None, ge=0, le=90)
    notes: str | None = Field(default=None, max_length=2000)
    climbed_at: str | None = None
    session_code: str | None = Field(default=None, max_length=16)


class LogbookOut(BaseModel):
    id: str
    user_id: str
    provider: str
    climb_id: str
    name: str | None
    session_code: str | None
    grade_at_send: str | None
    grade_v_at_send: int | None
    result: str
    attempts: int | None
    rpe: int | None
    duration_seconds: int | None
    angle: int | None
    notes: str | None
    climbed_at: str
    created_at: str


class LogbookPage(BaseModel):
    entries: list[LogbookOut]
    next_before: str | None = None


class FavoriteOut(BaseModel):
    provider: str
    climb_id: str
    list_name: str = Field(alias="list")
    position: int
    added_at: str

    model_config = {"populate_by_name": True}


class FavoritesPage(BaseModel):
    list_name: str = Field(alias="list")
    entries: list[FavoriteOut]

    model_config = {"populate_by_name": True}


class FavoriteToggleReq(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    climb_id: str = Field(min_length=1, max_length=128)
    list_name: str = Field(alias="list", default="favorites", min_length=1, max_length=64)

    model_config = {"populate_by_name": True}


class NoteReq(BaseModel):
    body: str = Field(min_length=0, max_length=4000)
    tags: list[str] | None = Field(default=None, max_length=30)


class NoteOut(BaseModel):
    user_id: str
    provider: str
    climb_id: str
    body: str
    tags: list[str]
    updated_at: str


class ImportResp(BaseModel):
    imported: int
    skipped: int
    errors: list[str]
