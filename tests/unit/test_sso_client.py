from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select

from app.db.metadata import metadata, recon_user
from app.schemas.errors import ErrorCode
from app.services.sso_client import sync_sso_user


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def test_sync_sso_user_new_user_jit(sqlite_engine):
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

    # Kiểm tra trong DB
    with sqlite_engine.connect() as conn:
        row = conn.execute(select(recon_user).where(recon_user.c.USERNAME == "new_employee")).mappings().first()
        assert row is not None
        assert row["IS_ACTIVE"] == "Y"
        assert row["PASSWORD_HASH"].startswith("!sso_managed_")


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
