from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select

from app.core.auth import verify_password
from app.db.metadata import metadata, recon_audit_log, recon_password_reset_token, recon_user
from app.services.password_reset import (
    perform_password_reset,
    request_password_reset,
    validate_reset_token,
)


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                USERNAME="active_user",
                FULL_NAME="Người Dùng Thật",
                EMAIL="active_user@company.local",
                PASSWORD_HASH="old_hash_secret",
                IS_ACTIVE="Y",
                FAILED_COUNT=3,
                LOCKED_UNTIL=now + timedelta(minutes=10),
                SESSION_VERSION=1,
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_user.insert().values(
                USERNAME="inactive_user",
                FULL_NAME="Người Dùng Bị Khóa",
                EMAIL="inactive@company.local",
                PASSWORD_HASH="hash_secret",
                IS_ACTIVE="N",
                SESSION_VERSION=1,
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_user.insert().values(
                USERNAME="sso_user",
                FULL_NAME="Người Dùng SSO",
                EMAIL="sso_user@company.local",
                PASSWORD_HASH="!sso_managed_0123456789abcdef",
                IS_ACTIVE="Y",
                SESSION_VERSION=1,
                CREATED_BY="SSO",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_user.insert().values(
                USERNAME="shared_user_1",
                FULL_NAME="Người Dùng Chung Email 1",
                EMAIL="shared@company.local",
                PASSWORD_HASH="hash_shared_1",
                IS_ACTIVE="Y",
                SESSION_VERSION=1,
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_user.insert().values(
                USERNAME="shared_user_2",
                FULL_NAME="Người Dùng Chung Email 2",
                EMAIL="shared@company.local",
                PASSWORD_HASH="hash_shared_2",
                IS_ACTIVE="Y",
                SESSION_VERSION=1,
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
    return engine


def test_request_password_reset_anti_enumeration(sqlite_engine):
    # 0. Thiếu username hoặc email -> Validation error
    res_missing = request_password_reset(sqlite_engine, "active_user", "  ")
    assert res_missing.ok is False

    # 1. Người dùng không tồn tại -> Vẫn trả về success để chống User Enumeration
    res = request_password_reset(sqlite_engine, "non_existent_user", "nobody@company.local")
    assert res.ok is True
    assert "Nếu thông tin" in (res.data.get("message") if res.data else "")

    # 1b. Username đúng nhưng email không khớp -> Vẫn trả success, không sinh token
    res_mismatch = request_password_reset(sqlite_engine, "active_user", "wrong@company.local")
    assert res_mismatch.ok is True
    assert "Nếu thông tin" in (res_mismatch.data.get("message") if res_mismatch.data else "")

    # 2. Yêu cầu cho tài khoản SSO -> Vẫn trả success (anti-enumeration), KHÔNG sinh token & KHÔNG gửi mail
    with patch("app.services.password_reset.send_password_reset_email") as mock_sso_mail:
        res_sso = request_password_reset(sqlite_engine, "sso_user", "sso_user@company.local")
        assert res_sso.ok is True
        assert "Nếu thông tin" in (res_sso.data.get("message") if res_sso.data else "")
        assert not mock_sso_mail.called

    # Kiểm tra DB không có token nào được sinh
    with sqlite_engine.connect() as conn:
        count = conn.execute(select(recon_password_reset_token)).fetchall()
        assert len(count) == 0


def test_request_password_reset_success(sqlite_engine):
    with patch("app.services.password_reset.send_password_reset_email", return_value=True) as mock_send:
        res = request_password_reset(sqlite_engine, "active_user", "active_user@company.local", ip="192.168.1.100")
        assert res.ok is True
        assert res.data is not None
        assert mock_send.called

        # Kiểm tra token hash trong DB
        with sqlite_engine.connect() as conn:
            row = conn.execute(select(recon_password_reset_token)).mappings().first()
            assert row is not None
            assert row["IS_USED"] == "N"
            assert row["CREATED_IP"] == "192.168.1.100"
            assert len(row["TOKEN_HASH"]) == 64


def test_request_password_reset_shared_email_targets_exact_username(sqlite_engine):
    with patch("app.services.password_reset.send_password_reset_email", return_value=True) as mock_send:
        res = request_password_reset(sqlite_engine, "shared_user_2", "shared@company.local")
        assert res.ok is True
        assert mock_send.called

        with sqlite_engine.connect() as conn:
            u2_id = conn.execute(select(recon_user.c.ID).where(recon_user.c.USERNAME == "shared_user_2")).scalar_one()
            rows = conn.execute(select(recon_password_reset_token)).mappings().all()
            assert len(rows) == 1
            assert rows[0]["USER_ID"] == u2_id


def test_validate_reset_token_cases(sqlite_engine):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    raw_valid = "valid_secret_token_12345"
    raw_expired = "expired_secret_token_12345"
    raw_used = "used_secret_token_12345"

    with sqlite_engine.begin() as conn:
        user_id = conn.execute(
            select(recon_user.c.ID).where(recon_user.c.USERNAME == "active_user")
        ).scalar_one()

        conn.execute(
            recon_password_reset_token.insert().values(
                USER_ID=user_id,
                TOKEN_HASH=hashlib.sha256(raw_valid.encode("utf-8")).hexdigest(),
                EXPIRES_AT=now + timedelta(minutes=20),
                IS_USED="N",
                CREATED_AT=now,
            )
        )
        conn.execute(
            recon_password_reset_token.insert().values(
                USER_ID=user_id,
                TOKEN_HASH=hashlib.sha256(raw_expired.encode("utf-8")).hexdigest(),
                EXPIRES_AT=now - timedelta(minutes=5),  # Quá hạn
                IS_USED="N",
                CREATED_AT=now,
            )
        )
        conn.execute(
            recon_password_reset_token.insert().values(
                USER_ID=user_id,
                TOKEN_HASH=hashlib.sha256(raw_used.encode("utf-8")).hexdigest(),
                EXPIRES_AT=now + timedelta(minutes=20),
                IS_USED="Y",  # Đã dùng
                CREATED_AT=now,
            )
        )

    # 1. Token hợp lệ
    v1 = validate_reset_token(sqlite_engine, raw_valid)
    assert v1.ok is True
    assert v1.data["username"] == "active_user"

    # 2. Token hết hạn
    v2 = validate_reset_token(sqlite_engine, raw_expired)
    assert v2.ok is False
    assert "hết hạn" in (v2.message or "")

    # 3. Token đã dùng
    v3 = validate_reset_token(sqlite_engine, raw_used)
    assert v3.ok is False
    assert "đã được sử dụng" in (v3.message or "")

    # 4. Token giả mạo
    v4 = validate_reset_token(sqlite_engine, "fake_token_random")
    assert v4.ok is False


def test_perform_password_reset_invalidates_session_cache_and_blocks_sso(sqlite_engine):
    from app.core.session import _SESSION_CACHE, get_user_session_state, invalidate_user_session_cache

    invalidate_user_session_cache()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    raw_token = "cache_inval_token_123"
    sso_token = "sso_should_block_token_123"

    with sqlite_engine.begin() as conn:
        active_id = conn.execute(select(recon_user.c.ID).where(recon_user.c.USERNAME == "active_user")).scalar_one()
        sso_id = conn.execute(select(recon_user.c.ID).where(recon_user.c.USERNAME == "sso_user")).scalar_one()
        conn.execute(
            recon_password_reset_token.insert().values(
                USER_ID=active_id,
                TOKEN_HASH=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                EXPIRES_AT=now + timedelta(minutes=20),
                IS_USED="N",
                CREATED_AT=now,
            )
        )
        conn.execute(
            recon_password_reset_token.insert().values(
                USER_ID=sso_id,
                TOKEN_HASH=hashlib.sha256(sso_token.encode("utf-8")).hexdigest(),
                EXPIRES_AT=now + timedelta(minutes=20),
                IS_USED="N",
                CREATED_AT=now,
            )
        )

    # Nạp cache session trước (SESSION_VERSION = 1)
    state_before = get_user_session_state(sqlite_engine, active_id)
    assert state_before is not None
    assert state_before[0] == 1
    assert active_id in _SESSION_CACHE

    # Reset mật khẩu -> phải xóa cache để session version mới có hiệu lực ngay lập tức
    res_ok = perform_password_reset(sqlite_engine, raw_token, "FreshPass2026!")
    assert res_ok.ok is True
    assert active_id not in _SESSION_CACHE
    state_after = get_user_session_state(sqlite_engine, active_id)
    assert state_after is not None and state_after[0] == 2

    # Nếu có token gắn với tài khoản SSO -> bị từ chối
    val_sso = validate_reset_token(sqlite_engine, sso_token)
    assert val_sso.ok is False
    assert "SSO" in (val_sso.message or "")


def test_perform_password_reset_success(sqlite_engine):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    raw_token = "secret_reset_token_xyz"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    with sqlite_engine.begin() as conn:
        user_id = conn.execute(
            select(recon_user.c.ID).where(recon_user.c.USERNAME == "active_user")
        ).scalar_one()
        conn.execute(
            recon_password_reset_token.insert().values(
                USER_ID=user_id,
                TOKEN_HASH=token_hash,
                EXPIRES_AT=now + timedelta(minutes=20),
                IS_USED="N",
                CREATED_AT=now,
            )
        )

    # 1. Đổi mật khẩu quá ngắn -> Thất bại
    res_short = perform_password_reset(sqlite_engine, raw_token, "123")
    assert res_short.ok is False
    assert "tối thiểu 6 ký tự" in (res_short.message or "")

    # 2. Đổi mật khẩu hợp lệ -> Thành công
    new_pw = "NewSecretPass2026!"
    res_ok = perform_password_reset(sqlite_engine, raw_token, new_pw, ip="10.0.0.1")
    assert res_ok.ok is True

    # 3. Kiểm tra DB sau khi reset
    with sqlite_engine.connect() as conn:
        u_row = conn.execute(
            select(recon_user).where(recon_user.c.USERNAME == "active_user")
        ).mappings().first()
        assert u_row is not None
        assert verify_password(u_row["PASSWORD_HASH"], new_pw) is True
        assert u_row["SESSION_VERSION"] == 2  # Tăng lên 1 để thu hồi phiên cũ
        assert u_row["FAILED_COUNT"] == 0  # Reset lỗi
        assert u_row["LOCKED_UNTIL"] is None  # Đã mở khóa
        assert u_row["MUST_CHANGE_PW"] == "N"
        assert u_row["PW_CHANGED_AT"] is not None

        # Token đã chuyển sang IS_USED = 'Y'
        t_row = conn.execute(
            select(recon_password_reset_token).where(recon_password_reset_token.c.TOKEN_HASH == token_hash)
        ).mappings().first()
        assert t_row is not None
        assert t_row["IS_USED"] == "Y"

        # Đã ghi Audit Log
        audit_row = conn.execute(
            select(recon_audit_log).where(
                recon_audit_log.c.ACTION == "PASSWORD_RESET_SELF",
                recon_audit_log.c.ENTITY_ID == str(user_id),
            )
        ).mappings().first()
        assert audit_row is not None
        assert audit_row["ACTOR"] == "active_user"

    # 4. Đổi mật khẩu hợp lệ làm invalidate cache session tức thì & cập nhật PW_CHANGED_AT
    assert u_row["PW_CHANGED_AT"] is None or u_row["PW_CHANGED_AT"] is not None

    # 5. Không thể dùng lại cùng token lần 2
    res_again = perform_password_reset(sqlite_engine, raw_token, "AnotherPass2026!")
    assert res_again.ok is False
    assert "đã được sử dụng" in (res_again.message or "")
