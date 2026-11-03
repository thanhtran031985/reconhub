from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select

from app.core.auth import (
    authenticate_user,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.db.metadata import metadata, recon_login_log, recon_user, recon_user_role
from app.schemas.errors import ErrorCode, ServiceError


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def test_hash_and_verify_password() -> None:
    pw = "Secret123"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(hashed, pw) is True
    assert verify_password(hashed, "WrongPassword") is False
    assert needs_rehash(hashed) is False


def test_hash_empty_password_fails() -> None:
    with pytest.raises(ServiceError) as exc_info:
        hash_password("")
    assert exc_info.value.code == ErrorCode.PASSWORD_EMPTY


def test_authenticate_success(test_db) -> None:
    engine = test_db
    now = datetime.now(timezone.utc)
    pw_hash = hash_password("matkhau123")

    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="nhanvien",
                FULL_NAME="Nhân Viên",
                EMAIL="nv@company.com",
                PASSWORD_HASH=pw_hash,
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                FAILED_COUNT=0,
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        user_id = res.inserted_primary_key[0]
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=user_id,
                ROLE="OPERATOR",
                CREATED_AT=now,
            )
        )

    auth_res = authenticate_user(engine, "NhanVien", "matkhau123", ip="127.0.0.1")
    assert auth_res.ok is True
    assert auth_res.data is not None
    assert auth_res.data.user_id == user_id
    assert auth_res.data.username == "nhanvien"
    assert "OPERATOR" in auth_res.data.roles
    assert auth_res.data.must_change_pw is False

    # Kiểm tra log đăng nhập
    with engine.connect() as conn:
        log = conn.execute(select(recon_login_log)).mappings().first()
        assert log is not None
        assert log["USERNAME"] == "nhanvien"
        assert log["SUCCESS"] == "Y"
        assert log["IP"] == "127.0.0.1"


def test_authenticate_wrong_password_and_lock(test_db) -> None:
    engine = test_db
    now = datetime.now(timezone.utc)
    pw_hash = hash_password("dungmatkhau")

    with engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                USERNAME="operator",
                FULL_NAME="Vận Hành",
                PASSWORD_HASH=pw_hash,
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                FAILED_COUNT=0,
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    # Thử sai 4 lần -> LOGIN_FAILED
    for _ in range(4):
        res = authenticate_user(engine, "operator", "saimatkhau")
        assert res.ok is False
        assert res.code == ErrorCode.LOGIN_FAILED
        assert "không đúng" in res.message

    # Lần thứ 5 -> ACCOUNT_LOCKED
    res5 = authenticate_user(engine, "operator", "saimatkhau")
    assert res5.ok is False
    assert res5.code == ErrorCode.ACCOUNT_LOCKED
    assert "tạm khóa" in res5.message

    # Lần thứ 6 dù gõ đúng mật khẩu vẫn bị khóa
    res6 = authenticate_user(engine, "operator", "dungmatkhau")
    assert res6.ok is False
    assert res6.code == ErrorCode.ACCOUNT_LOCKED


def test_authenticate_lock_expires(test_db) -> None:
    engine = test_db
    now = datetime.now(timezone.utc)
    pw_hash = hash_password("pass123")

    with engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                USERNAME="locked_user",
                FULL_NAME="User Bị Khóa",
                PASSWORD_HASH=pw_hash,
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                FAILED_COUNT=5,
                LOCKED_UNTIL=now - timedelta(minutes=1),  # Đã hết hạn khóa
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    # Đăng nhập lại với mật khẩu đúng sau khi hết hạn khóa -> Thành công
    res = authenticate_user(engine, "locked_user", "pass123")
    assert res.ok is True
    assert res.data.username == "locked_user"

    # Kiểm tra FAILED_COUNT và LOCKED_UNTIL đã được reset
    with engine.connect() as conn:
        user = conn.execute(select(recon_user).where(recon_user.c.USERNAME == "locked_user")).mappings().first()
        assert user["FAILED_COUNT"] == 0
        assert user["LOCKED_UNTIL"] is None


def test_authenticate_inactive_user(test_db) -> None:
    engine = test_db
    now = datetime.now(timezone.utc)
    pw_hash = hash_password("pass123")

    with engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                USERNAME="inactive_user",
                FULL_NAME="User Vô Hiệu",
                PASSWORD_HASH=pw_hash,
                IS_ACTIVE="N",
                MUST_CHANGE_PW="N",
                FAILED_COUNT=0,
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    res = authenticate_user(engine, "inactive_user", "pass123")
    assert res.ok is False
    assert res.code == ErrorCode.ACCOUNT_INACTIVE


def test_authenticate_nonexistent_user_generic_message(test_db) -> None:
    engine = test_db
    res = authenticate_user(engine, "ghost_user", "some_password")
    assert res.ok is False
    assert res.code == ErrorCode.LOGIN_FAILED
    # Thông báo giống hệt khi sai mật khẩu
    assert "Tên đăng nhập hoặc mật khẩu không đúng" in res.message


def test_logout_flask_endpoint() -> None:
    from app.ui.app import server

    client = server.test_client()
    res = client.get("/logout")
    assert res.status_code == 302
    assert "/login" in res.headers.get("Location", "")
