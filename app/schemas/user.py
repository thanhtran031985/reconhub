from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreateDTO(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    full_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    password: str = Field(min_length=1)
    roles: list[str] = Field(default_factory=lambda: ["VIEWER"])
    must_change_pw: bool = True


class UserUpdateDTO(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    roles: list[str] | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: str | None = None
    is_active: bool
    must_change_pw: bool
    roles: list[str]
    failed_count: int = 0
    locked_until: datetime | None = None
    last_login_at: datetime | None = None
    pw_changed_at: datetime | None = None
    created_at: datetime
    created_by: str


class ChangePasswordDTO(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class ResetPasswordDTO(BaseModel):
    new_password: str = Field(min_length=1)
