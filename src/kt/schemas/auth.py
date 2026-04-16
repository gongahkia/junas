from __future__ import annotations

from pydantic import BaseModel, Field

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterReq(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=40)
    grade_system_pref: str = Field(default="font", pattern=r"^(font|v|yds|uiaa)$")


class LoginReq(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class MagicLinkReq(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)
    display_name: str | None = Field(default=None, max_length=40)


class MagicLinkResp(BaseModel):
    ok: bool
    token: str | None = None  # only returned when KT_AUTH_RETURN_MAGIC_LINKS=true


class MagicLinkVerifyReq(BaseModel):
    token: str = Field(min_length=1, max_length=256)


class RefreshReq(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=256)


class LogoutReq(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=256)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_at: str
    refresh_expires_at: str
    user_id: str


class UserOut(BaseModel):
    id: str
    email: str | None
    display_name: str
    grade_system_pref: str
    created_at: str
    last_login_at: str | None


class UpdateProfileReq(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    grade_system_pref: str | None = Field(default=None, pattern=r"^(font|v|yds|uiaa)$")
