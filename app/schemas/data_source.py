from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DataSourceCreateDTO(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    env: str = Field(pattern="^(DEV|UAT|PROD)$")
    purpose: str = Field(pattern="^(SOURCE|METADATA)$")
    db_type: str = Field(default="ORACLE", pattern="^(ORACLE|SQLITE)$")
    host: str | None = Field(default=None, max_length=200)
    port: int = Field(default=1521, ge=1, le=65535)
    service_name: str | None = Field(default=None, max_length=100)
    file_path: str | None = Field(default=None, max_length=400)
    username: str | None = Field(default=None, max_length=60)
    password: str | None = None
    default_schema: str | None = Field(default=None, max_length=60)
    call_timeout_s: int = Field(default=600, ge=5, le=3600)
    max_rows: int = Field(default=1000000, ge=1000, le=10000000)


class DataSourceUpdateDTO(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    host: str | None = Field(default=None, max_length=200)
    port: int | None = Field(default=None, ge=1, le=65535)
    service_name: str | None = Field(default=None, max_length=100)
    file_path: str | None = Field(default=None, max_length=400)
    username: str | None = Field(default=None, max_length=60)
    password: str | None = None  # None hoặc rỗng = giữ nguyên mật khẩu cũ
    default_schema: str | None = Field(default=None, max_length=60)
    call_timeout_s: int | None = Field(default=None, ge=5, le=3600)
    max_rows: int | None = Field(default=None, ge=1000, le=10000000)
    is_active: bool | None = None


class DataSourceResponse(BaseModel):
    id: int
    name: str
    env: str
    purpose: str
    db_type: str
    host: str | None = None
    port: int | None = None
    service_name: str | None = None
    file_path: str | None = None
    username: str | None = None
    default_schema: str | None = None
    call_timeout_s: int
    max_rows: int
    is_active: bool
    is_current_metadata: bool
    last_test_at: datetime | None = None
    last_test_ok: str | None = None
    last_test_msg: str | None = None
    last_test_ms: int | None = None
    template_count: int = 0
    created_by: str
    created_at: datetime
    updated_at: datetime


class DataSourceOption(BaseModel):
    id: int
    name: str
    env: str
    purpose: str
    db_type: str
    default_schema: str | None = None
