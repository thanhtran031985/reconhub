from __future__ import annotations

from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()

# Danh mục người dùng mẫu trên SSO nội bộ
# Trong thực tế có thể load từ SQLite hoặc file cấu hình
_SEED_USERS: dict[str, dict[str, Any]] = {
    "admin": {
        "password_hash": _hasher.hash("admin123"),
        "full_name": "Quản trị viên Hệ thống",
        "email": "admin@company.local",
        "roles": ["Admin"],
    },
    "thanh.tran": {
        "password_hash": _hasher.hash("password123"),
        "full_name": "Trần Thanh",
        "email": "thanh.tran@company.local",
        "roles": ["Operator"],
    },
    "operator1": {
        "password_hash": _hasher.hash("password123"),
        "full_name": "Nguyễn Văn A",
        "email": "operator1@company.local",
        "roles": ["Operator"],
    },
    "viewer1": {
        "password_hash": _hasher.hash("password123"),
        "full_name": "Lê Thị B",
        "email": "viewer1@company.local",
        "roles": ["Viewer"],
    },
}


def get_sso_user(username: str) -> dict[str, Any] | None:
    """Lấy thông tin người dùng theo username (chữ thường)."""
    norm = username.strip().lower()
    return _SEED_USERS.get(norm)


def verify_sso_user(username: str, plain_password: str) -> dict[str, Any] | None:
    """Xác thực người dùng với mật khẩu băm Argon2."""
    user = get_sso_user(username)
    if not user:
        return None
    try:
        if _hasher.verify(user["password_hash"], plain_password):
            return user
    except (VerifyMismatchError, InvalidHashError):
        pass
    return None
