from __future__ import annotations

import argparse

import pytest
from sqlalchemy import create_engine, select

from app.cli import seed_cmd
from app.core.config import get_settings
from app.db.metadata import metadata, recon_data_source
from app.services.data_source import sync_current_metadata_source


@pytest.fixture
def startup_db_env(tmp_path, monkeypatch):
    db_file = tmp_path / "recon_test_startup.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("APP_ENV", "dev")

    get_settings.cache_clear()
    engine = create_engine(db_url)
    metadata.create_all(engine)
    return engine, db_file


def test_sync_current_metadata_source_creates_single_record(startup_db_env) -> None:
    engine, db_file = startup_db_env

    # Lần 1: Gọi đồng bộ metadata lúc khởi động
    sync_current_metadata_source(engine)

    with engine.connect() as conn:
        rows = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.IS_CURRENT_METADATA == "Y"))
            .mappings()
            .all()
        )
        assert len(rows) == 1
        curr = rows[0]
        assert curr["DB_TYPE"] == "SQLITE"
        assert curr["PURPOSE"] == "METADATA"
        assert curr["FILE_PATH"] == str(db_file)
        assert curr["IS_ACTIVE"] == "Y"

    # Lần 2: Gọi lại -> không tạo thêm, vẫn chỉ đúng 1 bản ghi
    sync_current_metadata_source(engine)
    with engine.connect() as conn:
        rows_again = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.IS_CURRENT_METADATA == "Y"))
            .mappings()
            .all()
        )
        assert len(rows_again) == 1


def test_seed_oracle_test_data_source(startup_db_env, monkeypatch) -> None:
    engine, _ = startup_db_env
    # Giả lập có biến môi trường ORACLE_TEST_*
    monkeypatch.setenv("ORACLE_TEST_HOST", "192.168.10.100")
    monkeypatch.setenv("ORACLE_TEST_PORT", "1521")
    monkeypatch.setenv("ORACLE_TEST_SERVICE", "ORCLPDB")
    monkeypatch.setenv("ORACLE_TEST_USER", "RECON_TEST_USER")
    monkeypatch.setenv("ORACLE_TEST_PASSWORD", "SecretPassTest")
    monkeypatch.setenv("ORACLE_TEST_SRC_SCHEMA", "RECON_SRC")
    get_settings.cache_clear()

    args = argparse.Namespace()
    # Chạy seed lần 1
    seed_cmd(args)

    with engine.connect() as conn:
        ds = conn.execute(select(recon_data_source).where(recon_data_source.c.NAME == "ORACLE_TEST")).mappings().first()
        assert ds is not None
        assert ds["HOST"] == "192.168.10.100"
        assert ds["USERNAME"] == "RECON_TEST_USER"
        assert ds["PURPOSE"] == "SOURCE"

    # Chạy seed lần 2 -> idempotent, không tạo trùng
    seed_cmd(args)
    with engine.connect() as conn:
        all_ds = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.NAME == "ORACLE_TEST")).mappings().all()
        )
        assert len(all_ds) == 1
