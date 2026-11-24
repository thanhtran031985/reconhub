from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select

from app.db.metadata import metadata, recon_audit_log, recon_role, recon_user
from app.schemas.errors import ErrorCode
from app.services.sso_client import sync_sso_user


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for code, name in [
            ("ADMIN", "Quản trị hệ thống"),
            ("TEMPLATE_OWNER", "Chủ sở hữu Template"),
            ("OPERATOR", "Vận hành"),
            ("VIEWER", "Chỉ xem"),
        ]:
            conn.execute(
                recon_role.insert().values(
                    CODE=code,
                    NAME=name,
                    IS_SYSTEM="Y",
                    IS_ACTIVE="Y",
                    CREATED_BY="SYSTEM",
                    CREATED_AT=now,
                    UPDATED_BY="SYSTEM",
                    UPDATED_AT=now,
                )
            )
    return engine


def test_sync_sso_user_new_user_jit_safe_role(sqlite_engine):
    profile = {
        "username": "new_employee",
        "full_name": "Nhân viên mới",
        "email": "new_emp@company.local",
        "roles": ["Operator"],
    }

    res = sync_sso_user(sqlite_engine, profile)
    assert res.ok is True
    assert res.data is not None
    assert res.data.username == "new_employee"
    assert res.data.full_name == "Nhân viên mới"
    assert "OPERATOR" in res.data.roles
    assert res.data.must_change_pw is False

    # Kiểm tra trong DB và RECON_AUDIT_LOG
    with sqlite_engine.connect() as conn:
        row = conn.execute(select(recon_user).where(recon_user.c.USERNAME == "new_employee")).mappings().first()
        assert row is not None
        assert row["IS_ACTIVE"] == "Y"
        assert row["PASSWORD_HASH"].startswith("!sso_managed_")

        audit_row = conn.execute(
            select(recon_audit_log).where(
                recon_audit_log.c.ACTION == "USER_JIT_PROVISION",
                recon_audit_log.c.ENTITY_ID == str(row["ID"]),
            )
        ).mappings().first()
        assert audit_row is not None
        assert audit_row["ENTITY"] == "USER"
        assert audit_row["ACTOR"] == "SSO"


def test_sync_sso_user_prevent_admin_escalation(sqlite_engine):
    # SSO gửi role Admin hoặc role lạ không nằm trong ALLOWED_JIT_ROLES
    profile = {
        "username": "sneaky_user",
        "full_name": "Kẻ muốn chiếm quyền Admin",
        "email": "hacker@company.local",
        "roles": ["Admin", "SuperUser", "CustomRole"],
    }

    res = sync_sso_user(sqlite_engine, profile)
    assert res.ok is True
    assert res.data is not None
    # Quyền Admin và role lạ bị loại bỏ, chỉ được gán VIEWER mặc định
    assert "ADMIN" not in res.data.roles
    assert "SUPERUSER" not in res.data.roles
    assert res.data.roles == ["VIEWER"]

    # Kiểm tra không có role mới lạ nào bị insert vào RECON_ROLE
    with sqlite_engine.connect() as conn:
        all_roles = conn.execute(select(recon_role.c.CODE)).scalars().all()
        assert "SUPERUSER" not in all_roles
        assert "CUSTOMROLE" not in all_roles


def test_sync_sso_user_existing_user(sqlite_engine):
    profile = {
        "username": "existing_emp",
        "full_name": "Nhân viên cũ",
        "email": "existing@company.local",
        "roles": ["Viewer"],
    }
    # Lần 1: Tạo mới
    res1 = sync_sso_user(sqlite_engine, profile)
    assert res1.ok is True
    user_id = res1.data.user_id

    # Lần 2: Đăng nhập lại
    res2 = sync_sso_user(sqlite_engine, profile)
    assert res2.ok is True
    assert res2.data.user_id == user_id
    assert res2.data.username == "existing_emp"


def test_sync_sso_user_inactive_user(sqlite_engine):
    profile = {
        "username": "disabled_emp",
        "full_name": "Nhân viên nghỉ việc",
        "roles": ["Viewer"],
    }
    # Tạo user
    res1 = sync_sso_user(sqlite_engine, profile)
    assert res1.ok is True
    user_id = res1.data.user_id

    # Đánh dấu vô hiệu hóa trong DB
    with sqlite_engine.begin() as conn:
        conn.execute(recon_user.update().where(recon_user.c.ID == user_id).values(IS_ACTIVE="N"))

    # Đăng nhập lại qua SSO -> Phải thất bại
    res2 = sync_sso_user(sqlite_engine, profile)
    assert res2.ok is False
    assert res2.code == ErrorCode.ACCOUNT_INACTIVE
