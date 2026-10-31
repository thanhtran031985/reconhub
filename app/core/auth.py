from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from pydantic import BaseModel
from sqlalchemy import Engine, select, update

from app.core.config import get_settings
from app.db.metadata import recon_login_log, recon_user, recon_user_role
from app.schemas.errors import ErrorCode, ServiceError, ServiceResult

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Băm mật khẩu bằng Argon2id.

    Mật khẩu có thể tự do nhưng không được để rỗng.
    """
    if not plain:
        raise ServiceError(ErrorCode.PASSWORD_EMPTY, "Mật khẩu không được để trống")
    return _hasher.hash(plain)


def verify_password(hash_val: str, plain: str) -> bool:
    """Kiểm tra mật khẩu khớp với giá trị băm Argon2id."""
    if not plain or not hash_val:
        return False
    try:
        return _hasher.verify(hash_val, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(hash_val: str) -> bool:
    """Kiểm tra xem giá trị băm có cần nâng cấp thông số thuật toán không."""
    try:
        return _hasher.check_needs_rehash(hash_val)
    except Exception:
        return True


class LoginData(BaseModel):
    """Thông tin xác thực thành công của người dùng."""

    user_id: int
    username: str
    full_name: str
    roles: list[str]
    must_change_pw: bool
    session_version: int


def _record_login_log(
    conn: Any,
    username: str,
    user_id: int | None,
    success: bool,
    reason: str,
    ip: str | None,
    now: datetime,
) -> None:
    """Ghi lại lịch sử đăng nhập vào RECON_LOGIN_LOG."""
    conn.execute(
        recon_login_log.insert().values(
            USERNAME=username,
            USER_ID=user_id,
            SUCCESS="Y" if success else "N",
            REASON=reason,
            IP=ip,
            CREATED_AT=now,
        )
    )


def authenticate_user(
    engine: Engine,
    username: str,
    plain_password: str,
    ip: str | None = None,
) -> ServiceResult[LoginData]:
    """Xác thực đăng nhập người dùng.

    Xử lý:
    - Chuẩn hóa username về chữ thường.
    - Ghi log mọi lần thử đăng nhập vào RECON_LOGIN_LOG.
    - Kiểm tra tài khoản vô hiệu hoặc đang bị khóa.
    - Khóa tài khoản sau 5 lần sai liên tiếp trong 15 phút.
    - Rehash mật khẩu nếu cần.
    - Trả về thông báo lỗi chung an toàn nếu thông tin sai.
    """
    settings = get_settings()
    norm_username = username.strip().lower()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        # Tìm thông tin người dùng
        user = conn.execute(select(recon_user).where(recon_user.c.USERNAME == norm_username)).mappings().first()

        if user is None:
            _record_login_log(conn, norm_username, None, False, "USER_NOT_FOUND", ip, now)
            return ServiceResult.fail(
                ErrorCode.LOGIN_FAILED,
                "Tên đăng nhập hoặc mật khẩu không đúng",
            )

        user_id = int(user["ID"])

        # Kiểm tra trạng thái hoạt động
        if user["IS_ACTIVE"] != "Y":
            _record_login_log(conn, norm_username, user_id, False, "ACCOUNT_INACTIVE", ip, now)
            return ServiceResult.fail(
                ErrorCode.ACCOUNT_INACTIVE,
                "Tài khoản đã bị vô hiệu hóa, vui lòng liên hệ quản trị viên",
            )

        # Kiểm tra khóa tạm thời
        locked_until = user["LOCKED_UNTIL"]
        if locked_until is not None:
            # Chuyển về naive nếu DB trả về aware
            if locked_until.tzinfo is not None:
                locked_until = locked_until.astimezone(timezone.utc).replace(tzinfo=None)

            if locked_until > now:
                _record_login_log(conn, norm_username, user_id, False, "ACCOUNT_LOCKED", ip, now)
                lock_str = locked_until.strftime("%H:%M %d/%m/%Y")
                return ServiceResult.fail(
                    ErrorCode.ACCOUNT_LOCKED,
                    f"Tài khoản tạm khóa đến {lock_str} do đăng nhập sai nhiều lần",
                )

        # Kiểm tra mật khẩu
        pw_ok = verify_password(user["PASSWORD_HASH"], plain_password)
        if not pw_ok:
            failed_count = int(user["FAILED_COUNT"] or 0) + 1
            if failed_count >= settings.LOGIN_MAX_FAILS:
                lock_duration = timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
                new_locked_until = now + lock_duration
                conn.execute(
                    update(recon_user)
                    .where(recon_user.c.ID == user_id)
                    .values(
                        FAILED_COUNT=failed_count,
                        LOCKED_UNTIL=new_locked_until,
                        UPDATED_AT=now,
                    )
                )
                _record_login_log(conn, norm_username, user_id, False, "ACCOUNT_LOCKED_TRIGGERED", ip, now)
                lock_str = new_locked_until.strftime("%H:%M %d/%m/%Y")
                return ServiceResult.fail(
                    ErrorCode.ACCOUNT_LOCKED,
                    f"Tài khoản tạm khóa đến {lock_str} do đăng nhập sai nhiều lần",
                )
            else:
                conn.execute(
                    update(recon_user)
                    .where(recon_user.c.ID == user_id)
                    .values(
                        FAILED_COUNT=failed_count,
                        UPDATED_AT=now,
                    )
                )
                _record_login_log(conn, norm_username, user_id, False, "WRONG_PASSWORD", ip, now)
                return ServiceResult.fail(
                    ErrorCode.LOGIN_FAILED,
                    "Tên đăng nhập hoặc mật khẩu không đúng",
                )

        # Đăng nhập thành công: reset lỗi & cập nhật thời gian
        update_values: dict[str, Any] = {
            "FAILED_COUNT": 0,
            "LOCKED_UNTIL": None,
            "LAST_LOGIN_AT": now,
            "UPDATED_AT": now,
        }

        # Tự động nâng cấp hash nếu cần
        if needs_rehash(user["PASSWORD_HASH"]):
            update_values["PASSWORD_HASH"] = hash_password(plain_password)

        conn.execute(update(recon_user).where(recon_user.c.ID == user_id).values(**update_values))

        _record_login_log(conn, norm_username, user_id, True, "SUCCESS", ip, now)

        # Lấy danh sách vai trò
        roles_rows = (
            conn.execute(select(recon_user_role.c.ROLE).where(recon_user_role.c.USER_ID == user_id)).scalars().all()
        )

        return ServiceResult.success(
            LoginData(
                user_id=user_id,
                username=norm_username,
                full_name=user["FULL_NAME"],
                roles=list(roles_rows),
                must_change_pw=(user["MUST_CHANGE_PW"] == "Y"),
                session_version=int(user["SESSION_VERSION"] or 1),
            )
        )
