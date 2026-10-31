from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select

from app.core.auth import hash_password
from app.core.context import Ctx, Role
from app.db.metadata import metadata, recon_audit_log, recon_user, recon_user_role
from app.schemas.errors import ErrorCode
from app.schemas.user import UserCreateDTO, UserUpdateDTO
from app.services.user import (
    change_password,
    create_user,
    reset_password,
    set_active,
    update_user,
)


@pytest.fixture
def user_service_env(monkeypatch, tmp_path):
    db_file = tmp_path / "user_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    # Tạo 1 admin ban đầu
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="rootadmin",
                FULL_NAME="Root Admin",
                PASSWORD_HASH=hash_password("adminpw123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        admin_id = res.inserted_primary_key[0]
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=admin_id,
                ROLE="ADMIN",
                CREATED_AT=now,
            )
        )

    admin_ctx = Ctx(user_id=admin_id, username="rootadmin", full_name="Root Admin", roles=[Role.ADMIN])
    viewer_ctx = Ctx(user_id=99, username="viewer", full_name="Viewer", roles=[Role.VIEWER])
    return engine, admin_ctx, viewer_ctx, admin_id


def test_viewer_cannot_call_admin_services(user_service_env) -> None:
    _, _, viewer_ctx, _ = user_service_env
    # Viewer gọi create_user bị FORBIDDEN
    res = create_user(
        viewer_ctx,
        UserCreateDTO(
            username="newuser",
            full_name="New User",
            password="pwd",
            roles=["OPERATOR"],
        ),
    )
    assert res.ok is False
    assert res.code == ErrorCode.FORBIDDEN


def test_create_user_and_duplicate_check(user_service_env) -> None:
    engine, admin_ctx, _, _ = user_service_env
    # Tạo user thành công
    res = create_user(
        admin_ctx,
        UserCreateDTO(
            username="Staff01",
            full_name="Nhân Viên 1",
            email="staff1@example.com",
            password="passStaff1",
            roles=["OPERATOR"],
            must_change_pw=True,
        ),
    )
    assert res.ok is True
    assert res.data is not None
    assert res.data.username == "staff01"
    assert res.data.roles == ["OPERATOR"]
    assert res.data.must_change_pw is True

    # Tạo lại cùng username (kể cả khác hoa thường) -> USERNAME_EXISTS
    res_dup = create_user(
        admin_ctx,
        UserCreateDTO(
            username="staff01",
            full_name="Nhân Viên Trùng",
            password="pass",
            roles=["VIEWER"],
        ),
    )
    assert res_dup.ok is False
    assert res_dup.code == ErrorCode.USERNAME_EXISTS


def test_last_admin_protection(user_service_env) -> None:
    _, admin_ctx, _, admin_id = user_service_env

    # 1. Thử deactive admin duy nhất -> LAST_ADMIN
    res_deact = set_active(admin_ctx, admin_id, False)
    assert res_deact.ok is False
    assert res_deact.code == ErrorCode.LAST_ADMIN

    # 2. Thử xóa role ADMIN của admin duy nhất -> LAST_ADMIN
    res_role = update_user(
        admin_ctx,
        admin_id,
        UserUpdateDTO(roles=["OPERATOR"]),
    )
    assert res_role.ok is False
    assert res_role.code == ErrorCode.LAST_ADMIN

    # 3. Tạo admin thứ hai -> lúc này có thể deactive admin thứ nhất
    res_admin2 = create_user(
        admin_ctx,
        UserCreateDTO(
            username="admin2",
            full_name="Admin Hai",
            password="pwd",
            roles=["ADMIN"],
        ),
    )
    assert res_admin2.ok is True

    # Giờ deactive admin đầu tiên thành công
    res_deact_ok = set_active(admin_ctx, admin_id, False)
    assert res_deact_ok.ok is True


def test_audit_log_masks_password(user_service_env) -> None:
    engine, admin_ctx, _, admin_id = user_service_env

    # Reset password
    res = reset_password(admin_ctx, admin_id, "VerySecretNewPassword")
    assert res.ok is True

    # Kiểm tra audit log không bao giờ chứa mật khẩu rõ
    with engine.connect() as conn:
        logs = conn.execute(select(recon_audit_log).where(recon_audit_log.c.ENTITY == "USER")).mappings().all()

        for log in logs:
            old_str = str(log["OLD_JSON"] or "")
            new_str = str(log["NEW_JSON"] or "")
            assert "VerySecretNewPassword" not in old_str
            assert "VerySecretNewPassword" not in new_str
            # Nếu có trường password thì phải được mask là '***'
            if "PASSWORD_HASH" in new_str or "password" in new_str.lower():
                assert "***" in new_str


def test_change_password_self(user_service_env) -> None:
    _, admin_ctx, _, admin_id = user_service_env

    # Đổi mật khẩu đúng old_pw
    res = change_password(admin_ctx, "adminpw123", "newSecretPass")
    assert res.ok is True

    # Thử đổi lại với mật khẩu cũ sai
    res_wrong = change_password(admin_ctx, "saiMatKhau", "anotherPass")
    assert res_wrong.ok is False
    assert res_wrong.code == ErrorCode.LOGIN_FAILED
