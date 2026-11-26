from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SsoProviderType = Literal["INTERNAL", "OIDC"]

_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")


def _normalize_optional_url(val: str | None) -> str | None:
    if val is None:
        return None
    cleaned = val.strip()
    return cleaned or None


class SsoProviderCreateDTO(BaseModel):
    """Dữ liệu tạo mới một nhà cung cấp SSO."""

    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    provider_type: SsoProviderType = "OIDC"
    icon: str | None = Field(default=None, max_length=60)
    discovery_url: str | None = Field(default=None, max_length=500)
    issuer: str | None = Field(default=None, max_length=500)
    auth_url: str | None = Field(default=None, max_length=500)
    token_url: str | None = Field(default=None, max_length=500)
    userinfo_url: str | None = Field(default=None, max_length=500)
    jwks_uri: str | None = Field(default=None, max_length=500)
    client_id: str | None = Field(default=None, max_length=255)
    client_secret: str | None = Field(default=None, max_length=500)
    scopes: str = Field(default="openid profile email", min_length=1, max_length=300)
    allowed_domains: str | None = Field(default=None, max_length=500)
    jit_enabled: bool = True
    auto_link_email: bool = True
    is_active: bool = True
    sort_order: int = Field(default=10, ge=0, le=9999)

    @field_validator("code")
    @classmethod
    def _validate_code(cls, v: str) -> str:
        norm = v.strip().lower()
        if not _CODE_RE.match(norm):
            raise ValueError("Mã provider chỉ gồm chữ thường a-z, số 0-9, '-' hoặc '_', dài 2-40 ký tự")
        return norm

    @field_validator("discovery_url", "issuer", "auth_url", "token_url", "userinfo_url", "jwks_uri")
    @classmethod
    def _clean_urls(cls, v: str | None) -> str | None:
        return _normalize_optional_url(v)

    @model_validator(mode="after")
    def _validate_oidc_fields(self) -> SsoProviderCreateDTO:
        if self.provider_type == "OIDC":
            if not self.client_id or not self.client_id.strip():
                raise ValueError("Provider OIDC bắt buộc có Client ID")
            if not (self.discovery_url or (self.auth_url and self.token_url)):
                raise ValueError("Provider OIDC cần Discovery URL hoặc đủ Auth URL và Token URL")
        return self


class SsoProviderUpdateDTO(BaseModel):
    """Dữ liệu cập nhật nhà cung cấp SSO (không bắt buộc nhập lại secret)."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider_type: SsoProviderType | None = None
    icon: str | None = Field(default=None, max_length=60)
    discovery_url: str | None = Field(default=None, max_length=500)
    issuer: str | None = Field(default=None, max_length=500)
    auth_url: str | None = Field(default=None, max_length=500)
    token_url: str | None = Field(default=None, max_length=500)
    userinfo_url: str | None = Field(default=None, max_length=500)
    jwks_uri: str | None = Field(default=None, max_length=500)
    client_id: str | None = Field(default=None, max_length=255)
    client_secret: str | None = Field(default=None, max_length=500)
    scopes: str | None = Field(default=None, min_length=1, max_length=300)
    allowed_domains: str | None = Field(default=None, max_length=500)
    jit_enabled: bool | None = None
    auto_link_email: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=9999)

    @field_validator("discovery_url", "issuer", "auth_url", "token_url", "userinfo_url", "jwks_uri")
    @classmethod
    def _clean_urls(cls, v: str | None) -> str | None:
        return _normalize_optional_url(v)


class SsoProviderResponse(BaseModel):
    """Thông tin provider trả về giao diện (không bao gồm client_secret)."""

    id: int
    code: str
    name: str
    provider_type: SsoProviderType
    icon: str | None = None
    discovery_url: str | None = None
    issuer: str | None = None
    auth_url: str | None = None
    token_url: str | None = None
    userinfo_url: str | None = None
    jwks_uri: str | None = None
    client_id: str | None = None
    has_secret: bool = False
    scopes: str = "openid profile email"
    allowed_domains: str | None = None
    jit_enabled: bool = True
    auto_link_email: bool = True
    is_active: bool = True
    sort_order: int = 10
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime


class SsoLoginButton(BaseModel):
    """Thông tin rút gọn để dựng nút đăng nhập SSO trên /login."""

    code: str
    name: str
    provider_type: SsoProviderType
    icon: str | None = None


class SsoProviderRuntime(BaseModel):
    """Thông tin chạy luồng xác thực (chỉ dùng nội bộ server, không trả về UI)."""

    id: int
    code: str
    name: str
    provider_type: SsoProviderType
    discovery_url: str | None = None
    issuer: str | None = None
    auth_url: str | None = None
    token_url: str | None = None
    userinfo_url: str | None = None
    jwks_uri: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: str = "openid profile email"
    allowed_domains: list[str] = Field(default_factory=list)
    jit_enabled: bool = True
    auto_link_email: bool = True
