from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
from sqlalchemy import Engine, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect

from app.core.audit import write_audit_log
from app.core.auth import LoginData
from app.db.metadata import recon_role, recon_user, recon_user_identity, recon_user_role
from app.schemas.errors import ErrorCode, ServiceResult
from app.schemas.sso import SsoProviderRuntime
from app.services.sso_provider import fetch_oidc_discovery_doc

ALLOWED_JIT_ROLES = {"VIEWER", "OPERATOR", "TEMPLATE_OWNER"}


def generate_pkce_pair() -> tuple[str, str]:
    """Sinh cặp PKCE (code_verifier, code_challenge S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_oidc_authorize_url(
    provider: SsoProviderRuntime,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    """Dựng URL chuyển hướng tới Authorization Endpoint của provider OIDC."""
    if not provider.auth_url:
        raise ValueError(f"Provider '{provider.code}' chưa cấu hình auth_url")
    params = {
        "client_id": provider.client_id or "",
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": provider.scopes or "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    sep = "&" if "?" in provider.auth_url else "?"
    return f"{provider.auth_url}{sep}{urllib.parse.urlencode(params)}"


def verify_sso_code(
    sso_server_url: str,
    code: str,
    client_secret: str | None = None,
    timeout: int = 5,
    endpoint_url: str | None = None,
) -> ServiceResult[dict[str, Any]]:
    """Gửi yêu cầu xác minh mã xác thực sang SSO Server nội bộ qua giao thức Back-channel."""
    endpoint = endpoint_url or f"{sso_server_url.rstrip('/')}/api/verify-code"
    payload = json.dumps({"code": code, "client_secret": client_secret}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return ServiceResult.success(data)
            return ServiceResult.fail(
                ErrorCode.LOGIN_FAILED,
                data.get("message", "Mã xác thực SSO không hợp lệ"),
            )
    except urllib.error.HTTPError as err:
        try:
            err_data = json.loads(err.read().decode("utf-8"))
            msg = err_data.get("message", "Mã xác thực không hợp lệ hoặc đã hết hạn")
        except Exception:
            msg = f"Lỗi từ SSO Server: HTTP {err.code}"
        return ServiceResult.fail(ErrorCode.LOGIN_FAILED, msg)
    except Exception as exc:
        return ServiceResult.fail(
            ErrorCode.LOGIN_FAILED,
            f"Không thể kết nối tới máy chủ SSO: {exc!s}",
        )


def _fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = 8) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Phản hồi JSON không hợp lệ")
        return data


def _select_jwk_key(jwks_doc: dict[str, Any], kid: str | None) -> Any:
    keys = jwks_doc.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ValueError("JWKS không có khóa công khai nào")

    chosen: dict[str, Any] | None = None
    if kid:
        for k in keys:
            if isinstance(k, dict) and k.get("kid") == kid:
                chosen = k
                break
    if chosen is None and len(keys) == 1 and isinstance(keys[0], dict):
        chosen = keys[0]
    if chosen is None:
        raise ValueError("Không tìm thấy khóa JWKS khớp với kid của id_token")

    kty = str(chosen.get("kty", "")).upper()
    jwk_json = json.dumps(chosen)
    if kty == "RSA":
        return RSAAlgorithm.from_jwk(jwk_json)
    if kty == "EC":
        return ECAlgorithm.from_jwk(jwk_json)
    raise ValueError(f"Thuật toán khóa JWK '{kty}' chưa được hỗ trợ")


def exchange_oidc_code(
    provider: SsoProviderRuntime,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    expected_nonce: str,
    timeout: int = 8,
) -> ServiceResult[dict[str, Any]]:
    """Đổi authorization code tại token_endpoint, xác thực id_token bằng JWKS và chuẩn hóa profile."""
    token_url = provider.token_url
    jwks_uri = provider.jwks_uri
    userinfo_url = provider.userinfo_url
    issuer = provider.issuer

    if (not token_url or not jwks_uri) and provider.discovery_url:
        try:
            doc = fetch_oidc_discovery_doc(provider.discovery_url, timeout=timeout)
            token_url = token_url or doc["token_url"]
            jwks_uri = jwks_uri or doc["jwks_uri"]
            userinfo_url = userinfo_url or doc["userinfo_url"]
            issuer = issuer or doc["issuer"]
        except Exception as exc:
            return ServiceResult.fail(ErrorCode.LOGIN_FAILED, f"Không thể tải OIDC Discovery: {exc!s}")

    if not token_url:
        return ServiceResult.fail(ErrorCode.LOGIN_FAILED, "Provider OIDC thiếu token_url")

    form_data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": provider.client_id or "",
        "code_verifier": code_verifier,
    }
    if provider.client_secret:
        form_data["client_secret"] = provider.client_secret

    encoded_body = urllib.parse.urlencode(form_data).encode("utf-8")
    req = urllib.request.Request(
        token_url,
        data=encoded_body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            token_res = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return ServiceResult.fail(ErrorCode.LOGIN_FAILED, f"Đổi mã OIDC thất bại (HTTP {err.code})")
    except Exception as exc:
        return ServiceResult.fail(ErrorCode.LOGIN_FAILED, f"Không thể kết nối tới token endpoint: {exc!s}")

    id_token = token_res.get("id_token")
    access_token = token_res.get("access_token")
    claims: dict[str, Any] = {}

    if id_token:
        if not jwks_uri:
            return ServiceResult.fail(ErrorCode.LOGIN_FAILED, "Provider OIDC thiếu jwks_uri để xác thực id_token")
        try:
            header = jwt.get_unverified_header(id_token)
            jwks_doc = _fetch_json(jwks_uri, timeout=timeout)
            pub_key = _select_jwk_key(jwks_doc, header.get("kid"))
            claims = jwt.decode(
                id_token,
                key=pub_key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                audience=provider.client_id,
                issuer=issuer if issuer else None,
                options={"verify_iss": bool(issuer)},
            )
        except Exception as exc:
            return ServiceResult.fail(ErrorCode.LOGIN_FAILED, f"Xác thực chữ ký id_token không hợp lệ: {exc!s}")

        token_nonce = str(claims.get("nonce") or "")
        if not expected_nonce or not token_nonce or not hmac.compare_digest(token_nonce, expected_nonce):
            return ServiceResult.fail(ErrorCode.LOGIN_FAILED, "Nonce trong id_token không khớp phiên đăng nhập")

    # Lấy bổ sung UserInfo nếu thiếu email hoặc name
    if (not claims.get("email") or not claims.get("name")) and userinfo_url and access_token:
        try:
            ui_data = _fetch_json(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=timeout,
            )
            for k, v in ui_data.items():
                claims.setdefault(k, v)
        except Exception:
            pass

    subject = str(claims.get("sub") or "").strip()
    if not subject:
        return ServiceResult.fail(ErrorCode.LOGIN_FAILED, "Phản hồi OIDC thiếu định danh 'sub'")

    raw_email = claims.get("email") or claims.get("preferred_username") or claims.get("upn")
    email = str(raw_email).strip().lower() if raw_email else ""
    email_verified = claims.get("email_verified")
    # Microsoft Entra ID đôi khi không trả claim email_verified với tài khoản tenant nội bộ khi có email/upn
    if email_verified is None and email:
        email_verified = True

    full_name = str(claims.get("name") or email or subject).strip()
    roles_raw = claims.get("roles")
    roles = list(roles_raw) if isinstance(roles_raw, list) else []

    return ServiceResult.success(
        {
            "provider_code": provider.code,
            "subject": subject,
            "email": email,
            "email_verified": bool(email_verified),
            "full_name": full_name,
            "username": email or subject,
            "roles": roles,
        }
    )


def _derive_username_from_email(email: str) -> str:
    """Chuyển email thành USERNAME tối đa 60 ký tự (giới hạn bảng RECON_USER)."""
    norm = email.strip().lower()
    if len(norm) <= 60:
        return norm
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:8]
    return f"{norm[:51]}~{digest}"


def _identity_table_exists(engine: Engine) -> bool:
    try:
        return "RECON_USER_IDENTITY" in inspect(engine).get_table_names()
    except SQLAlchemyError:
        return False


def _upsert_user_identity(
    conn: Any,
    has_identity_table: bool,
    user_id: int,
    provider_code: str,
    subject: str,
    email: str | None,
    now: datetime,
) -> None:
    if not has_identity_table or not subject:
        return
    existing_id = conn.execute(
        select(recon_user_identity.c.ID).where(
            recon_user_identity.c.PROVIDER_CODE == provider_code,
            recon_user_identity.c.SUBJECT == subject,
        )
    ).scalar_one_or_none()
    if existing_id is None:
        conn.execute(
            recon_user_identity.insert().values(
                USER_ID=user_id,
                PROVIDER_CODE=provider_code,
                SUBJECT=subject,
                EMAIL_AT_PROVIDER=email,
                LAST_LOGIN_AT=now,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
    else:
        conn.execute(
            update(recon_user_identity)
            .where(recon_user_identity.c.ID == existing_id)
            .values(
                USER_ID=user_id,
                EMAIL_AT_PROVIDER=email,
                LAST_LOGIN_AT=now,
                UPDATED_AT=now,
            )
        )


def sync_sso_user(
    engine: Engine,
    sso_profile: dict[str, Any],
    provider: SsoProviderRuntime | None = None,
) -> ServiceResult[LoginData]:
    """Đồng bộ tài khoản từ SSO vào RECON_USER, dùng email làm account & tự động liên kết."""
    provider_code = (provider.code if provider else str(sso_profile.get("provider_code") or "internal")).strip().lower()
    is_oidc = (provider.provider_type == "OIDC") if provider else (provider_code != "internal")

    raw_email = str(sso_profile.get("email") or "").strip().lower() or None
    raw_username_input = str(sso_profile.get("username") or "").strip().lower()
    subject = str(sso_profile.get("subject") or sso_profile.get("sub") or raw_username_input or raw_email or "").strip()

    if is_oidc:
        if not raw_email or "@" not in raw_email:
            return ServiceResult.fail(ErrorCode.LOGIN_FAILED, "Tài khoản SSO không cung cấp địa chỉ email hợp lệ")
        if not bool(sso_profile.get("email_verified", False)):
            return ServiceResult.fail(ErrorCode.LOGIN_FAILED, "Email từ nhà cung cấp SSO chưa được xác minh")
        if provider and provider.allowed_domains:
            domain = raw_email.rsplit("@", 1)[-1].lower()
            if domain not in provider.allowed_domains:
                return ServiceResult.fail(
                    ErrorCode.SSO_DOMAIN_NOT_ALLOWED,
                    f"Tên miền email '{domain}' không nằm trong danh sách được phép truy cập",
                )

    if not raw_username_input and not raw_email:
        return ServiceResult.fail(ErrorCode.LOGIN_FAILED, "Dữ liệu người dùng từ SSO thiếu thông tin định danh")

    full_name = str(sso_profile.get("full_name") or raw_email or raw_username_input)
    raw_roles = sso_profile.get("roles") or ["Viewer"]
    if not isinstance(raw_roles, list) or not raw_roles:
        raw_roles = ["Viewer"]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    has_identity_table = _identity_table_exists(engine)

    with engine.begin() as conn:
        user: Any = None

        # 1. Tìm qua liên kết định danh bất biến (PROVIDER_CODE, SUBJECT)
        if has_identity_table and subject:
            ident_row = (
                conn.execute(
                    select(recon_user_identity.c.USER_ID).where(
                        recon_user_identity.c.PROVIDER_CODE == provider_code,
                        recon_user_identity.c.SUBJECT == subject,
                    )
                )
                .mappings()
                .first()
            )
            if ident_row is not None:
                user = (
                    conn.execute(select(recon_user).where(recon_user.c.ID == int(ident_row["USER_ID"])))
                    .mappings()
                    .first()
                )

        # 2. Tự động liên kết theo EMAIL hoặc USERNAME trùng email nếu được bật
        auto_link = provider.auto_link_email if provider else True
        if user is None and raw_email and auto_link:
            user = (
                conn.execute(
                    select(recon_user).where(
                        (func.lower(recon_user.c.EMAIL) == raw_email)
                        | (func.lower(recon_user.c.USERNAME) == raw_email)
                    )
                )
                .mappings()
                .first()
            )

        # 3. Tương thích ngược cho INTERNAL SSO tìm theo username truyền vào
        if user is None and not is_oidc and raw_username_input:
            user = (
                conn.execute(select(recon_user).where(recon_user.c.USERNAME == raw_username_input))
                .mappings()
                .first()
            )

        if user is None:
            jit_enabled = provider.jit_enabled if provider else True
            if not jit_enabled:
                return ServiceResult.fail(
                    ErrorCode.LOGIN_FAILED,
                    "Tài khoản chưa được cấp trong ReconHub (tự động tạo tài khoản đang tắt)",
                )

            # Với OIDC (Google, MS, bên thứ 3): lấy email làm USERNAME luôn
            if is_oidc and raw_email:
                target_username = _derive_username_from_email(raw_email)
            elif raw_username_input:
                target_username = _derive_username_from_email(raw_username_input) if len(raw_username_input) > 60 else raw_username_input
            else:
                assert raw_email is not None
                target_username = _derive_username_from_email(raw_email)

            dummy_pw = f"!sso_managed_{secrets.token_hex(16)}"
            res = conn.execute(
                recon_user.insert().values(
                    USERNAME=target_username,
                    FULL_NAME=full_name,
                    EMAIL=raw_email,
                    PASSWORD_HASH=dummy_pw,
                    IS_ACTIVE="Y",
                    MUST_CHANGE_PW="N",
                    SESSION_VERSION=1,
                    CREATED_BY="SSO",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                    LAST_LOGIN_AT=now,
                )
            )
            user_id = int(res.inserted_primary_key[0])  # type: ignore[index]

            assigned_roles: list[str] = []
            for r_code in raw_roles:
                code_upper = str(r_code).strip().upper()
                # Chỉ chấp nhận role nằm trong ALLOWED_JIT_ROLES (tuyệt đối không tự cấp ADMIN qua JIT)
                if code_upper not in ALLOWED_JIT_ROLES:
                    continue
                role_id = conn.execute(
                    select(recon_role.c.ID).where(recon_role.c.CODE == code_upper)
                ).scalar_one_or_none()

                if role_id is not None:
                    conn.execute(
                        recon_user_role.insert().values(
                            USER_ID=user_id,
                            ROLE_ID=role_id,
                            ASSIGNED_BY="SSO",
                            ASSIGNED_AT=now,
                            CREATED_AT=now,
                        )
                    )
                    assigned_roles.append(code_upper)

            if not assigned_roles:
                viewer_role_id = conn.execute(
                    select(recon_role.c.ID).where(recon_role.c.CODE == "VIEWER")
                ).scalar_one_or_none()
                if viewer_role_id is None:
                    ins_viewer = conn.execute(
                        recon_role.insert().values(
                            CODE="VIEWER",
                            NAME="Chỉ xem",
                            IS_SYSTEM="Y",
                            IS_ACTIVE="Y",
                            CREATED_BY="SSO",
                            CREATED_AT=now,
                            UPDATED_BY="SSO",
                            UPDATED_AT=now,
                        )
                    )
                    viewer_role_id = ins_viewer.inserted_primary_key[0]  # type: ignore[index]

                conn.execute(
                    recon_user_role.insert().values(
                        USER_ID=user_id,
                        ROLE_ID=viewer_role_id,
                        ASSIGNED_BY="SSO",
                        ASSIGNED_AT=now,
                        CREATED_AT=now,
                    )
                )
                assigned_roles = ["VIEWER"]

            roles = assigned_roles
            session_ver = 1
            effective_username = target_username
            effective_full_name = full_name

            _upsert_user_identity(conn, has_identity_table, user_id, provider_code, subject, raw_email, now)

            write_audit_log(
                conn=conn,
                entity="USER",
                entity_id=user_id,
                action="USER_JIT_PROVISION",
                actor="SSO",
                new_data={
                    "provider_code": provider_code,
                    "username": target_username,
                    "full_name": full_name,
                    "email": raw_email,
                    "roles": roles,
                },
                now=now,
            )
        else:
            user_id = int(user["ID"])
            if user["IS_ACTIVE"] != "Y":
                return ServiceResult.fail(
                    ErrorCode.ACCOUNT_INACTIVE,
                    "Tài khoản đã bị vô hiệu hóa trong hệ thống ReconHub",
                )

            session_ver = int(user["SESSION_VERSION"] or 1)
            effective_username = str(user["USERNAME"])
            effective_full_name = str(user["FULL_NAME"] or full_name)
            db_roles = (
                conn.execute(
                    select(recon_role.c.CODE)
                    .select_from(recon_user_role.join(recon_role, recon_user_role.c.ROLE_ID == recon_role.c.ID))
                    .where(recon_user_role.c.USER_ID == user_id)
                )
                .scalars()
                .all()
            )
            roles = [str(r).upper() for r in db_roles] if db_roles else ["VIEWER"]

            user_updates: dict[str, Any] = {"LAST_LOGIN_AT": now, "UPDATED_AT": now}
            if raw_email and not user["EMAIL"]:
                user_updates["EMAIL"] = raw_email
            conn.execute(update(recon_user).where(recon_user.c.ID == user_id).values(**user_updates))

            _upsert_user_identity(conn, has_identity_table, user_id, provider_code, subject, raw_email, now)

    login_data = LoginData(
        user_id=user_id,
        username=effective_username,
        full_name=effective_full_name,
        roles=roles,
        must_change_pw=False,
        session_version=session_ver,
    )
    return ServiceResult.success(login_data)
