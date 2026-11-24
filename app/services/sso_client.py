from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, select, update

from app.core.audit import write_audit_log
from app.core.auth import LoginData
from app.db.metadata import recon_role, recon_user, recon_user_role
from app.schemas.errors import ErrorCode, ServiceResult

ALLOWED_JIT_ROLES = {"VIEWER", "OPERATOR", "TEMPLATE_OWNER"}


def verify_sso_code(
    sso_server_url: str,
    code: str,
    client_secret: str | None = None,
    timeout: int = 5,
) -> ServiceResult[dict[str, Any]]:
    """Gửi yêu cầu xác minh mã xác thực sang SSO Server qua giao thức Back-channel."""
    endpoint = f"{sso_server_url.rstrip('/')}/api/verify-code"
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


def sync_sso_user(engine: Engine, sso_profile: dict[str, Any]) -> ServiceResult[LoginData]:
    """Đồng bộ tài khoản từ SSO vào RECON_USER (JIT Provisioning) và cấp LoginData."""
    raw_username = str(sso_profile.get("username", "")).strip().lower()
    if not raw_username:
        return ServiceResult.fail(ErrorCode.LOGIN_FAILED, "Dữ liệu người dùng từ SSO thiếu username")

    full_name = str(sso_profile.get("full_name") or raw_username)
    email = sso_profile.get("email")
    raw_roles = sso_profile.get("roles") or ["Viewer"]
    if not isinstance(raw_roles, list) or not raw_roles:
        raw_roles = ["Viewer"]

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        # Tìm người dùng trong RECON_USER
        user = conn.execute(select(recon_user).where(recon_user.c.USERNAME == raw_username)).mappings().first()

        if user is None:
            # JIT: Tạo tài khoản mới tự động
            dummy_pw = f"!sso_managed_{secrets.token_hex(16)}"
            res = conn.execute(
                recon_user.insert().values(
                    USERNAME=raw_username,
                    FULL_NAME=full_name,
                    EMAIL=email,
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
                # Chỉ chấp nhận role nằm trong ALLOWED_JIT_ROLES (tuyệt đối không cho phép tự cấp ADMIN qua JIT)
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

            # Nếu không có role hợp lệ nào, gán role mặc định an toàn VIEWER
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

            # Ghi nhật ký kiểm toán RECON_AUDIT_LOG cho hành động JIT cấp tài khoản
            write_audit_log(
                conn=conn,
                entity="USER",
                entity_id=user_id,
                action="USER_JIT_PROVISION",
                actor="SSO",
                new_data={
                    "username": raw_username,
                    "full_name": full_name,
                    "email": email,
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
            # Lấy vai trò hiện có trong hệ thống ReconHub
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

            # Cập nhật thời điểm đăng nhập gần nhất
            conn.execute(update(recon_user).where(recon_user.c.ID == user_id).values(LAST_LOGIN_AT=now, UPDATED_AT=now))

    login_data = LoginData(
        user_id=user_id,
        username=raw_username,
        full_name=full_name,
        roles=roles,
        must_change_pw=False,
        session_version=session_ver,
    )
    return ServiceResult.success(login_data)
