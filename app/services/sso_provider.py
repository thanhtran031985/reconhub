from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import Engine, delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect

from app.core.audit import write_audit_log
from app.core.config import get_settings
from app.core.context import Ctx
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.engine import get_recon_engine
from app.db.metadata import recon_sso_provider
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.sso import (
    SsoLoginButton,
    SsoProviderCreateDTO,
    SsoProviderResponse,
    SsoProviderRuntime,
    SsoProviderType,
    SsoProviderUpdateDTO,
)
from app.services import service
from app.services.perm import require_admin, requires_menu

# Mẫu gợi ý nhanh khi đăng ký SSO trên giao diện Admin
SSO_PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "google": {
        "code": "google",
        "name": "Đăng nhập với Google",
        "provider_type": "OIDC",
        "icon": "lucide:globe",
        "discovery_url": "https://accounts.google.com/.well-known/openid-configuration",
        "scopes": "openid email profile",
    },
    "microsoft": {
        "code": "microsoft",
        "name": "Đăng nhập với Microsoft",
        "provider_type": "OIDC",
        "icon": "lucide:building-2",
        "discovery_url": "https://login.microsoftonline.com/<TENANT_ID>/v2.0/.well-known/openid-configuration",
        "scopes": "openid profile email",
    },
    "oidc": {
        "code": "oidc-custom",
        "name": "Đăng nhập SSO Bên thứ 3 (OIDC)",
        "provider_type": "OIDC",
        "icon": "lucide:key-round",
        "discovery_url": "https://<idp-domain>/.well-known/openid-configuration",
        "scopes": "openid profile email",
    },
    "internal": {
        "code": "internal",
        "name": "SSO Doanh nghiệp (Nội bộ)",
        "provider_type": "INTERNAL",
        "icon": "lucide:shield-check",
        "scopes": "openid profile email",
    },
}


def _parse_allowed_domains(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [d.strip().lower().lstrip("@") for d in raw.split(",") if d.strip()]


def _normalize_domains_str(raw: str | None) -> str | None:
    domains = _parse_allowed_domains(raw)
    return ", ".join(domains) if domains else None


def _build_provider_response(row: Any) -> SsoProviderResponse:
    p_type: SsoProviderType = "INTERNAL" if str(row["PROVIDER_TYPE"]).upper() == "INTERNAL" else "OIDC"
    return SsoProviderResponse(
        id=int(row["ID"]),
        code=str(row["CODE"]),
        name=str(row["NAME"]),
        provider_type=p_type,
        icon=row["ICON"],
        discovery_url=row["DISCOVERY_URL"],
        issuer=row["ISSUER"],
        auth_url=row["AUTH_URL"],
        token_url=row["TOKEN_URL"],
        userinfo_url=row["USERINFO_URL"],
        jwks_uri=row["JWKS_URI"],
        client_id=row["CLIENT_ID"],
        has_secret=bool(row["CLIENT_SECRET_ENC"]),
        scopes=str(row["SCOPES"] or "openid profile email"),
        allowed_domains=row["ALLOWED_DOMAINS"],
        jit_enabled=(row["JIT_ENABLED"] == "Y"),
        auto_link_email=(row["AUTO_LINK_EMAIL"] == "Y"),
        is_active=(row["IS_ACTIVE"] == "Y"),
        sort_order=int(row["SORT_ORDER"] or 10),
        created_by=str(row["CREATED_BY"]),
        created_at=row["CREATED_AT"],
        updated_by=str(row["UPDATED_BY"]),
        updated_at=row["UPDATED_AT"],
    )


def _audit_payload(row: Any) -> dict[str, Any]:
    """Chuẩn bị bản ghi audit không bao gồm secret."""
    return {
        "code": str(row["CODE"]),
        "name": str(row["NAME"]),
        "provider_type": str(row["PROVIDER_TYPE"]),
        "discovery_url": row["DISCOVERY_URL"],
        "issuer": row["ISSUER"],
        "auth_url": row["AUTH_URL"],
        "token_url": row["TOKEN_URL"],
        "client_id": row["CLIENT_ID"],
        "has_secret": bool(row["CLIENT_SECRET_ENC"]),
        "scopes": row["SCOPES"],
        "allowed_domains": row["ALLOWED_DOMAINS"],
        "jit_enabled": row["JIT_ENABLED"],
        "auto_link_email": row["AUTO_LINK_EMAIL"],
        "is_active": row["IS_ACTIVE"],
        "sort_order": int(row["SORT_ORDER"] or 10),
    }


def _validate_discovery_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https":
        return cleaned
    if parsed.scheme == "http" and host in {"localhost", "127.0.0.1"}:
        return cleaned
    raise ServiceError(
        ErrorCode.SSO_DISCOVERY_FAILED,
        "Discovery URL phải dùng HTTPS (hoặc HTTP với localhost khi phát triển)",
    )


def fetch_oidc_discovery_doc(discovery_url: str, timeout: int = 8) -> dict[str, str | None]:
    """Tải và trích xuất các endpoint chuẩn từ .well-known/openid-configuration."""
    url = _validate_discovery_url(discovery_url)
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            doc = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ServiceError(
            ErrorCode.SSO_DISCOVERY_FAILED,
            f"Không thể tải cấu hình OIDC Discovery (HTTP {exc.code})",
        ) from exc
    except Exception as exc:
        raise ServiceError(
            ErrorCode.SSO_DISCOVERY_FAILED,
            f"Lỗi kết nối khi tải OIDC Discovery: {exc!s}",
        ) from exc

    if not isinstance(doc, dict) or not doc.get("authorization_endpoint") or not doc.get("token_endpoint"):
        raise ServiceError(
            ErrorCode.SSO_DISCOVERY_FAILED,
            "Tài liệu OIDC Discovery thiếu authorization_endpoint hoặc token_endpoint",
        )

    return {
        "issuer": str(doc["issuer"]) if doc.get("issuer") else None,
        "auth_url": str(doc["authorization_endpoint"]),
        "token_url": str(doc["token_endpoint"]),
        "userinfo_url": str(doc["userinfo_endpoint"]) if doc.get("userinfo_endpoint") else None,
        "jwks_uri": str(doc["jwks_uri"]) if doc.get("jwks_uri") else None,
    }


@service
@requires_menu("sso_flow")
def fetch_oidc_discovery(ctx: Ctx, discovery_url: str) -> dict[str, str | None]:
    """Kiểm tra và trích xuất endpoint từ OIDC Discovery URL (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    return fetch_oidc_discovery_doc(discovery_url)


@service
@requires_menu("sso_flow")
def list_sso_providers(ctx: Ctx) -> list[SsoProviderResponse]:
    """Danh sách tất cả nhà cung cấp SSO đã đăng ký (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(recon_sso_provider).order_by(recon_sso_provider.c.SORT_ORDER, recon_sso_provider.c.ID)
            )
            .mappings()
            .all()
        )
        return [_build_provider_response(r) for r in rows]


@service
@requires_menu("sso_flow")
def create_sso_provider(ctx: Ctx, dto: SsoProviderCreateDTO) -> SsoProviderResponse:
    """Đăng ký mới một nhà cung cấp SSO (chỉ Admin)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    issuer = dto.issuer
    auth_url = dto.auth_url
    token_url = dto.token_url
    userinfo_url = dto.userinfo_url
    jwks_uri = dto.jwks_uri

    # Nếu OIDC chỉ truyền discovery_url mà chưa điền auth/token -> tự fetch
    if dto.provider_type == "OIDC" and dto.discovery_url and not (auth_url and token_url):
        discovered = fetch_oidc_discovery_doc(dto.discovery_url)
        issuer = issuer or discovered["issuer"]
        auth_url = auth_url or discovered["auth_url"]
        token_url = token_url or discovered["token_url"]
        userinfo_url = userinfo_url or discovered["userinfo_url"]
        jwks_uri = jwks_uri or discovered["jwks_uri"]

    secret_enc = encrypt_secret(dto.client_secret.strip()) if dto.client_secret and dto.client_secret.strip() else None

    with engine.begin() as conn:
        exists = conn.execute(
            select(recon_sso_provider.c.ID).where(recon_sso_provider.c.CODE == dto.code)
        ).scalar_one_or_none()
        if exists is not None:
            raise ServiceError(ErrorCode.SSO_PROVIDER_EXISTS, f"Mã nhà cung cấp SSO '{dto.code}' đã tồn tại")

        res = conn.execute(
            recon_sso_provider.insert().values(
                CODE=dto.code,
                NAME=dto.name.strip(),
                PROVIDER_TYPE=dto.provider_type,
                ICON=dto.icon.strip() if dto.icon else None,
                DISCOVERY_URL=dto.discovery_url,
                ISSUER=issuer,
                AUTH_URL=auth_url,
                TOKEN_URL=token_url,
                USERINFO_URL=userinfo_url,
                JWKS_URI=jwks_uri,
                CLIENT_ID=dto.client_id.strip() if dto.client_id else None,
                CLIENT_SECRET_ENC=secret_enc,
                SCOPES=dto.scopes.strip(),
                ALLOWED_DOMAINS=_normalize_domains_str(dto.allowed_domains),
                JIT_ENABLED="Y" if dto.jit_enabled else "N",
                AUTO_LINK_EMAIL="Y" if dto.auto_link_email else "N",
                IS_ACTIVE="Y" if dto.is_active else "N",
                SORT_ORDER=dto.sort_order,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        new_id = int(res.inserted_primary_key[0])  # type: ignore[index]
        created = conn.execute(select(recon_sso_provider).where(recon_sso_provider.c.ID == new_id)).mappings().one()
        write_audit_log(
            conn=conn,
            entity="SSO_PROVIDER",
            entity_id=new_id,
            action="CREATE",
            actor=ctx.username,
            new_data=_audit_payload(created),
            now=now,
        )
        return _build_provider_response(created)


@service
@requires_menu("sso_flow")
def update_sso_provider(ctx: Ctx, provider_id: int, dto: SsoProviderUpdateDTO) -> SsoProviderResponse:
    """Cập nhật cấu hình nhà cung cấp SSO (chỉ Admin). Giữ nguyên secret nếu không nhập mới."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        existing = (
            conn.execute(select(recon_sso_provider).where(recon_sso_provider.c.ID == provider_id)).mappings().first()
        )
        if existing is None:
            raise ServiceError(ErrorCode.SSO_PROVIDER_NOT_FOUND, "Không tìm thấy nhà cung cấp SSO")

        old_audit = _audit_payload(existing)
        values: dict[str, Any] = {
            "UPDATED_BY": ctx.username,
            "UPDATED_AT": now,
            "ROW_VERSION": int(existing["ROW_VERSION"] or 1) + 1,
        }

        if dto.name is not None:
            values["NAME"] = dto.name.strip()
        if dto.provider_type is not None:
            values["PROVIDER_TYPE"] = dto.provider_type
        if dto.icon is not None:
            values["ICON"] = dto.icon.strip() or None
        if dto.discovery_url is not None:
            values["DISCOVERY_URL"] = dto.discovery_url
        if dto.issuer is not None:
            values["ISSUER"] = dto.issuer
        if dto.auth_url is not None:
            values["AUTH_URL"] = dto.auth_url
        if dto.token_url is not None:
            values["TOKEN_URL"] = dto.token_url
        if dto.userinfo_url is not None:
            values["USERINFO_URL"] = dto.userinfo_url
        if dto.jwks_uri is not None:
            values["JWKS_URI"] = dto.jwks_uri
        if dto.client_id is not None:
            values["CLIENT_ID"] = dto.client_id.strip() or None
        if dto.client_secret is not None and dto.client_secret.strip():
            values["CLIENT_SECRET_ENC"] = encrypt_secret(dto.client_secret.strip())
        if dto.scopes is not None:
            values["SCOPES"] = dto.scopes.strip()
        if dto.allowed_domains is not None:
            values["ALLOWED_DOMAINS"] = _normalize_domains_str(dto.allowed_domains)
        if dto.jit_enabled is not None:
            values["JIT_ENABLED"] = "Y" if dto.jit_enabled else "N"
        if dto.auto_link_email is not None:
            values["AUTO_LINK_EMAIL"] = "Y" if dto.auto_link_email else "N"
        if dto.is_active is not None:
            values["IS_ACTIVE"] = "Y" if dto.is_active else "N"
        if dto.sort_order is not None:
            values["SORT_ORDER"] = dto.sort_order

        conn.execute(update(recon_sso_provider).where(recon_sso_provider.c.ID == provider_id).values(**values))
        updated = (
            conn.execute(select(recon_sso_provider).where(recon_sso_provider.c.ID == provider_id)).mappings().one()
        )
        write_audit_log(
            conn=conn,
            entity="SSO_PROVIDER",
            entity_id=provider_id,
            action="UPDATE",
            actor=ctx.username,
            old_data=old_audit,
            new_data=_audit_payload(updated),
            now=now,
        )
        return _build_provider_response(updated)


@service
@requires_menu("sso_flow")
def delete_sso_provider(ctx: Ctx, provider_id: int) -> dict[str, Any]:
    """Xóa một nhà cung cấp SSO ngoài (chỉ Admin). Không xóa provider nội bộ mặc định."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        existing = (
            conn.execute(select(recon_sso_provider).where(recon_sso_provider.c.ID == provider_id)).mappings().first()
        )
        if existing is None:
            raise ServiceError(ErrorCode.SSO_PROVIDER_NOT_FOUND, "Không tìm thấy nhà cung cấp SSO")
        if str(existing["CODE"]) == "internal":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Không thể xóa SSO nội bộ mặc định; bạn có thể tắt trạng thái hoạt động nếu không dùng",
            )

        old_audit = _audit_payload(existing)
        conn.execute(delete(recon_sso_provider).where(recon_sso_provider.c.ID == provider_id))
        write_audit_log(
            conn=conn,
            entity="SSO_PROVIDER",
            entity_id=provider_id,
            action="DELETE",
            actor=ctx.username,
            old_data=old_audit,
            now=now,
        )
        return {"deleted_id": provider_id, "code": str(existing["CODE"])}


def _provider_table_exists(engine: Engine) -> bool:
    try:
        return "RECON_SSO_PROVIDER" in inspect(engine).get_table_names()
    except SQLAlchemyError:
        return False


def list_active_login_providers(engine: Engine) -> list[SsoLoginButton]:
    """Lấy danh sách provider đang hoạt động để hiển thị trên màn hình /login."""
    if not _provider_table_exists(engine):
        return [
            SsoLoginButton(
                code="internal",
                name="Đăng nhập qua SSO Doanh nghiệp",
                provider_type="INTERNAL",
                icon="lucide:shield-check",
            )
        ]

    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(
                    recon_sso_provider.c.CODE,
                    recon_sso_provider.c.NAME,
                    recon_sso_provider.c.PROVIDER_TYPE,
                    recon_sso_provider.c.ICON,
                )
                .where(recon_sso_provider.c.IS_ACTIVE == "Y")
                .order_by(recon_sso_provider.c.SORT_ORDER, recon_sso_provider.c.ID)
            )
            .mappings()
            .all()
        )
        return [
            SsoLoginButton(
                code=str(r["CODE"]),
                name=str(r["NAME"]),
                provider_type="INTERNAL" if str(r["PROVIDER_TYPE"]).upper() == "INTERNAL" else "OIDC",
                icon=r["ICON"],
            )
            for r in rows
        ]


def get_sso_provider_for_auth(engine: Engine, code: str) -> SsoProviderRuntime | None:
    """Lấy cấu hình runtime (kèm client_secret giải mã) cho provider đang active."""
    norm_code = code.strip().lower()
    settings = get_settings()

    if not _provider_table_exists(engine):
        if norm_code == "internal":
            return SsoProviderRuntime(
                id=0,
                code="internal",
                name="SSO Doanh nghiệp (Nội bộ)",
                provider_type="INTERNAL",
                auth_url=f"{settings.SSO_SERVER_URL.rstrip('/')}/login",
                token_url=f"{settings.SSO_SERVER_URL.rstrip('/')}/api/verify-code",
                client_secret=settings.SSO_CLIENT_SECRET,
            )
        return None

    with engine.connect() as conn:
        row = (
            conn.execute(
                select(recon_sso_provider).where(
                    recon_sso_provider.c.CODE == norm_code,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            # Nếu test DB dùng metadata.create_all() chưa chạy seed migration cho 'internal'
            if norm_code == "internal":
                return SsoProviderRuntime(
                    id=0,
                    code="internal",
                    name="SSO Doanh nghiệp (Nội bộ)",
                    provider_type="INTERNAL",
                    auth_url=f"{settings.SSO_SERVER_URL.rstrip('/')}/login",
                    token_url=f"{settings.SSO_SERVER_URL.rstrip('/')}/api/verify-code",
                    client_secret=settings.SSO_CLIENT_SECRET,
                )
            return None

        if row["IS_ACTIVE"] != "Y":
            return None

        p_type: SsoProviderType = "INTERNAL" if str(row["PROVIDER_TYPE"]).upper() == "INTERNAL" else "OIDC"
        secret = decrypt_secret(row["CLIENT_SECRET_ENC"]) if row["CLIENT_SECRET_ENC"] else None
        auth_url = row["AUTH_URL"]
        token_url = row["TOKEN_URL"]

        # Fallback cho provider internal khi chưa nhập URL/Secret riêng trong DB
        if p_type == "INTERNAL":
            base_url = settings.SSO_SERVER_URL.rstrip("/")
            auth_url = auth_url or f"{base_url}/login"
            token_url = token_url or f"{base_url}/api/verify-code"
            secret = secret or settings.SSO_CLIENT_SECRET

        return SsoProviderRuntime(
            id=int(row["ID"]),
            code=str(row["CODE"]),
            name=str(row["NAME"]),
            provider_type=p_type,
            discovery_url=row["DISCOVERY_URL"],
            issuer=row["ISSUER"],
            auth_url=auth_url,
            token_url=token_url,
            userinfo_url=row["USERINFO_URL"],
            jwks_uri=row["JWKS_URI"],
            client_id=row["CLIENT_ID"],
            client_secret=secret,
            scopes=str(row["SCOPES"] or "openid profile email"),
            allowed_domains=_parse_allowed_domains(row["ALLOWED_DOMAINS"]),
            jit_enabled=(row["JIT_ENABLED"] == "Y"),
            auto_link_email=(row["AUTO_LINK_EMAIL"] == "Y"),
        )
