from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionResponse(BaseModel):
    token: str
    username: str


class SurfaceRequest(BaseModel):
    secret: dict[str, str] = {}
    parent_id: str | None = None


class ClimbQueryRequest(BaseModel):
    secret: dict[str, str] = {}
    surface_id: str | None = None
    context: dict[str, str] = {}
    q: str | None = None
    sort: str | None = "popular"
    cursor: str | None = None
    grade_min: str | None = None
    grade_max: str | None = None
    page_size: int = 10


class ClimbSelection(BaseModel):
    board_hold_id: str
    role: str


class UpdateBoardHoldsRequest(BaseModel):
    holds: list[dict[str, object]]
    publish: bool = True


class CreateClimbRequest(BaseModel):
    board_id: str
    name: str
    grade: str
    description: str = ""
    holds: list[ClimbSelection]


class AttemptRequest(BaseModel):
    tries: int = Field(ge=1, le=999)


class RatingRequest(BaseModel):
    value: int = Field(ge=-1, le=1)
