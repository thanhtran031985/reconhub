from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select

from app.core.context import Ctx, Role
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_data_source
from app.services.data_source import test_data_source as service_test_data_source


@pytest.fixture
def test_conn_env(tmp_path, monkeypatch):
    db_file = tmp_path / "conn_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])
    return engine, admin_ctx, db_file


def test_test_data_source_sqlite(test_conn_env) -> None:
    engine, admin_ctx, db_file = test_conn_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Thêm data source sqlite
    with engine.begin() as conn:
        res = conn.execute(
            recon_data_source.insert().values(
                NAME="LOCAL_SQLITE",
                ENV="DEV",
                PURPOSE="METADATA",
                DB_TYPE="SQLITE",
                FILE_PATH=str(db_file),
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = res.inserted_primary_key[0]

    # Kiểm tra kết nối
    res_test = service_test_data_source(admin_ctx, ds_id)
    assert res_test.ok is True
    assert res_test.data is not None
    assert res_test.data["ok"] is True
    assert "thành công" in res_test.data["message"].lower()

    # Kiểm tra DB đã cập nhật LAST_TEST_*
    with engine.connect() as conn:
        row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().first()
        assert row["LAST_TEST_OK"] == "Y"
        assert row["LAST_TEST_AT"] is not None
        assert row["LAST_TEST_MS"] is not None


def test_test_data_source_oracle_source_warning_write_privs(test_conn_env) -> None:
    engine, admin_ctx, _ = test_conn_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        res = conn.execute(
            recon_data_source.insert().values(
                NAME="ORA_SRC",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="10.0.0.1",
                PORT=1521,
                SERVICE_NAME="TESTPDB",
                USERNAME="RECON_RO",
                PASSWORD_ENC=encrypt_secret("pwd"),
                DEFAULT_SCHEMA="RECON_SRC",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = res.inserted_primary_key[0]

    # Mock oracledb connection
    mock_conn = MagicMock()
    mock_conn.version = "19.3.0.0.0"
    mock_cursor = MagicMock()
    # Giả lập trả về có quyền CREATE TABLE (không phải read-only)
    mock_cursor.fetchall.return_value = [("CREATE TABLE",)]
    mock_conn.cursor.return_value = mock_cursor

    with patch("oracledb.connect", return_value=mock_conn):
        res_test = service_test_data_source(admin_ctx, ds_id)
        assert res_test.ok is True
        assert res_test.data["ok"] is True
        assert res_test.data.get("read_only") is False
        assert "quyền ghi" in res_test.data["message"].lower() or "cảnh báo" in res_test.data["message"].lower()


def test_test_data_source_oracle_metadata_target(test_conn_env) -> None:
    engine, admin_ctx, _ = test_conn_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        res = conn.execute(
            recon_data_source.insert().values(
                NAME="ORA_METADATA",
                ENV="UAT",
                PURPOSE="METADATA",
                DB_TYPE="ORACLE",
                HOST="10.0.0.2",
                PORT=1521,
                SERVICE_NAME="TESTPDB",
                USERNAME="RECON_APP",
                PASSWORD_ENC=encrypt_secret("pwd"),
                DEFAULT_SCHEMA="RECON_APP",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = res.inserted_primary_key[0]

    # Mock oracledb connection
    mock_conn = MagicMock()
    mock_conn.version = "19.3.0.0.0"
    mock_cursor = MagicMock()
    # Đếm số bảng RECON_* = 0 (schema trống)
    mock_cursor.fetchone.return_value = (0,)
    mock_conn.cursor.return_value = mock_cursor

    with patch("oracledb.connect", return_value=mock_conn):
        res_test = service_test_data_source(admin_ctx, ds_id)
        assert res_test.ok is True
        assert res_test.data["ok"] is True
        assert res_test.data["recon_tables_count"] == 0
        assert "sẵn sàng" in res_test.data["message"].lower() or "trống" in res_test.data["message"].lower()
