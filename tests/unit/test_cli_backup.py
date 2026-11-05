from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text

from app.cli import backup_cmd, restore_cmd
from app.core.config import get_settings
from app.db.metadata import metadata, recon_user


@pytest.fixture
def backup_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "recon_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                USERNAME="backup_tester",
                FULL_NAME="Backup Tester",
                PASSWORD_HASH="hash123",
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    backup_dir = tmp_path / "backups"
    return {
        "engine": engine,
        "db_file": db_file,
        "backup_dir": backup_dir,
    }


def test_backup_creates_valid_sqlite_file(backup_env):
    b_dir = backup_env["backup_dir"]
    args = argparse.Namespace(dest=str(b_dir), keep=14)

    backup_cmd(args)

    backups = list(b_dir.glob("recon_app_*.db"))
    assert len(backups) == 1
    bf = backups[0]
    assert bf.stat().st_size > 0

    # Mở file backup và truy vấn kiểm tra dữ liệu toàn vẹn
    bk_engine = create_engine(f"sqlite:///{bf.as_posix()}")
    with bk_engine.connect() as conn:
        user_cnt = conn.execute(select(recon_user).where(recon_user.c.USERNAME == "backup_tester")).fetchall()
        assert len(user_cnt) == 1


def test_backup_rotation_keeps_max_files(backup_env):
    b_dir = backup_env["backup_dir"]
    b_dir.mkdir(parents=True, exist_ok=True)

    # Tạo 16 file giả lập với mtime tăng dần
    now_ts = time.time()
    for i in range(16):
        dummy_file = b_dir / f"recon_app_20261101_{i:06d}.db"
        dummy_file.write_text("dummy")
        # Set mtime
        mtime = now_ts + i * 10
        import os

        os.utime(dummy_file, (mtime, mtime))

    assert len(list(b_dir.glob("recon_app_*.db"))) == 16

    # Chạy backup_cmd với keep=14
    args = argparse.Namespace(dest=str(b_dir), keep=14)
    backup_cmd(args)

    # Sau khi chạy backup mới (16 + 1 = 17 file) và xoay vòng, chỉ còn đúng 14 file
    remaining = list(b_dir.glob("recon_app_*.db"))
    assert len(remaining) == 14


def test_restore_database(backup_env):
    b_dir = backup_env["backup_dir"]
    db_file = backup_env["db_file"]

    # 1. Tạo backup
    args = argparse.Namespace(dest=str(b_dir), keep=14)
    backup_cmd(args)
    bf = list(b_dir.glob("recon_app_*.db"))[0]

    # 2. Xóa dữ liệu ở database hiện tại
    engine = backup_env["engine"]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM RECON_USER"))
        users_after_delete = conn.execute(select(recon_user)).fetchall()
        assert len(users_after_delete) == 0

    engine.dispose()
    import gc

    gc.collect()

    # 3. Chạy restore_cmd
    restore_args = argparse.Namespace(file=str(bf))
    restore_cmd(restore_args)

    # 4. Kiểm tra dữ liệu đã phục hồi thành công
    restored_engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    with restored_engine.connect() as conn:
        users_restored = conn.execute(select(recon_user)).fetchall()
        assert len(users_restored) == 1
        assert users_restored[0].USERNAME == "backup_tester"
