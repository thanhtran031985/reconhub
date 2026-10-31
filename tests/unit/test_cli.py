from __future__ import annotations

import argparse

import pytest
from sqlalchemy import create_engine, select

from app.cli import create_admin_cmd, migrate_metadata_cmd, reset_password_cmd, seed_cmd
from app.core.auth import verify_password
from app.db.metadata import metadata, recon_user, recon_user_role


@pytest.fixture
def cli_db(monkeypatch, tmp_path):
    db_file = tmp_path / "cli_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)
    return engine


def test_cli_create_admin_and_force(cli_db) -> None:
    engine = cli_db

    # Tạo admin đầu tiên
    args = argparse.Namespace(
        username="superadmin",
        full_name="Super Admin",
        password="adminSecretPassword",
        force=False,
    )
    create_admin_cmd(args)

    with engine.connect() as conn:
        admin = conn.execute(select(recon_user).where(recon_user.c.USERNAME == "superadmin")).mappings().first()
        assert admin is not None
        assert verify_password(admin["PASSWORD_HASH"], "adminSecretPassword") is True
        roles = (
            conn.execute(select(recon_user_role.c.ROLE).where(recon_user_role.c.USER_ID == admin["ID"])).scalars().all()
        )
        assert "ADMIN" in roles

    # Tạo lại không có --force -> bị từ chối
    args2 = argparse.Namespace(
        username="admin2",
        full_name="Admin Hai",
        password="pass",
        force=False,
    )
    with pytest.raises(SystemExit) as exc:
        create_admin_cmd(args2)
    assert exc.value.code != 0

    # Tạo lại với --force -> thành công
    args2.force = True
    create_admin_cmd(args2)

    with engine.connect() as conn:
        admin2 = conn.execute(select(recon_user).where(recon_user.c.USERNAME == "admin2")).mappings().first()
        assert admin2 is not None


def test_cli_reset_password(cli_db) -> None:
    engine = cli_db
    # Tạo trước 1 user
    args_admin = argparse.Namespace(
        username="user1",
        full_name="User Một",
        password="oldPass",
        force=True,
    )
    create_admin_cmd(args_admin)

    # Reset password qua CLI
    args_reset = argparse.Namespace(
        username="user1",
        password="newPassWord123",
    )
    reset_password_cmd(args_reset)

    with engine.connect() as conn:
        user = conn.execute(select(recon_user).where(recon_user.c.USERNAME == "user1")).mappings().first()
        assert user is not None
        assert verify_password(user["PASSWORD_HASH"], "newPassWord123") is True
        assert user["MUST_CHANGE_PW"] == "Y"


def test_cli_seed_idempotent(cli_db) -> None:
    engine = cli_db
    args = argparse.Namespace()

    # Chạy lần 1
    seed_cmd(args)

    with engine.connect() as conn:
        users = conn.execute(select(recon_user)).mappings().all()
        assert len(users) == 4
        usernames = {u["USERNAME"] for u in users}
        assert usernames == {"admin", "owner", "operator", "viewer"}

    # Chạy lần 2 -> không tạo trùng, vẫn là 4 user
    seed_cmd(args)
    with engine.connect() as conn:
        users_again = conn.execute(select(recon_user)).mappings().all()
        assert len(users_again) == 4


def test_cli_migrate_metadata_missing_target(cli_db) -> None:
    args = argparse.Namespace(target_ds=None)
    with pytest.raises(SystemExit) as exc:
        migrate_metadata_cmd(args)
    assert exc.value.code != 0

