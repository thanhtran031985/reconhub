from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select

from app.core.context import Ctx, Role
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.metadata import metadata, recon_data_source
from app.schemas.data_source import DataSourceCreateDTO, DataSourceUpdateDTO
from app.schemas.errors import ErrorCode
from app.services.data_source import (
    create_data_source,
    deactivate_data_source,
    list_data_sources,
    options_data_sources,
    update_data_source,
)


@pytest.fixture
def ds_service_env(tmp_path, monkeypatch):
    db_file = tmp_path / "ds_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])
    viewer_ctx = Ctx(user_id=2, username="viewer", full_name="Viewer", roles=[Role.VIEWER])
    return engine, admin_ctx, viewer_ctx


def test_crypto_fernet() -> None:
    secret = "OracleSuperSecretPassword!@#"
    enc = encrypt_secret(secret)
    assert enc != secret
    dec = decrypt_secret(enc)
    assert dec == secret


def test_viewer_permissions_on_data_source(ds_service_env) -> None:
    _, _, viewer_ctx = ds_service_env

    # Viewer xem options thì được
    res_opt = options_data_sources(viewer_ctx)
    assert res_opt.ok is True

    # Nhưng gọi CRUD thì bị FORBIDDEN
    res_list = list_data_sources(viewer_ctx)
    assert res_list.ok is False
    assert res_list.code == ErrorCode.FORBIDDEN

    res_create = create_data_source(
        viewer_ctx,
        DataSourceCreateDTO(
            name="DS_ORACLE_DEV",
            env="DEV",
            purpose="SOURCE",
            host="10.0.0.1",
            username="test_ro",
            password="pwd",
        ),
    )
    assert res_create.ok is False
    assert res_create.code == ErrorCode.FORBIDDEN


def test_create_and_list_data_source(ds_service_env) -> None:
    engine, admin_ctx, _ = ds_service_env

    # Admin tạo DataSource mới
    res = create_data_source(
        admin_ctx,
        DataSourceCreateDTO(
            name="ORACLE_PROD_SRC",
            env="PROD",
            purpose="SOURCE",
            host="192.168.1.100",
            port=1521,
            service_name="ORCLPDB",
            username="RECON_RO",
            password="MySecretOraclePassword",
            default_schema="RECON_SRC",
            call_timeout_s=300,
        ),
    )
    assert res.ok is True
    assert res.data is not None
    assert res.data.name == "ORACLE_PROD_SRC"
    assert res.data.is_active is True
    # Kiểm tra không có password trong response
    assert not hasattr(res.data, "password")
    assert not hasattr(res.data, "password_enc")

    # Kiểm tra trong DB: mật khẩu đã được mã hóa Fernet
    with engine.connect() as conn:
        row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == res.data.id)).mappings().first()
        assert row is not None
        assert row["PASSWORD_ENC"] is not None
        assert row["PASSWORD_ENC"] != "MySecretOraclePassword"
        # Giải mã ra đúng mật khẩu ban đầu
        assert decrypt_secret(row["PASSWORD_ENC"]) == "MySecretOraclePassword"


def test_update_data_source_preserves_password_when_empty(ds_service_env) -> None:
    engine, admin_ctx, _ = ds_service_env

    # Tạo trước 1 Data Source
    res_create = create_data_source(
        admin_ctx,
        DataSourceCreateDTO(
            name="ORACLE_UAT",
            env="UAT",
            purpose="SOURCE",
            host="192.168.1.50",
            username="UAT_USER",
            password="OriginalPassword",
        ),
    )
    assert res_create.ok is True
    ds_id = res_create.data.id

    # Update thông tin nhưng password để trống
    res_update = update_data_source(
        admin_ctx,
        ds_id,
        DataSourceUpdateDTO(
            host="192.168.1.55",
            password="",  # Để trống -> giữ nguyên mật khẩu cũ
        ),
    )
    assert res_update.ok is True
    assert res_update.data.host == "192.168.1.55"

    # Kiểm tra mật khẩu trong DB vẫn giải mã ra OriginalPassword
    with engine.connect() as conn:
        row = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().first()
        assert decrypt_secret(row["PASSWORD_ENC"]) == "OriginalPassword"


def test_cannot_deactivate_current_metadata_source(ds_service_env) -> None:
    engine, admin_ctx, _ = ds_service_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Giả lập bản ghi IS_CURRENT_METADATA='Y'
    with engine.begin() as conn:
        res = conn.execute(
            recon_data_source.insert().values(
                NAME="CURRENT_SQLITE",
                ENV="DEV",
                PURPOSE="METADATA",
                DB_TYPE="SQLITE",
                FILE_PATH="data/recon_app.db",
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="Y",
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        curr_id = res.inserted_primary_key[0]

    # Deactivate nguồn này -> bị từ chối DS_CURRENT_METADATA_LOCKED
    res_deact = deactivate_data_source(admin_ctx, curr_id)
    assert res_deact.ok is False
    assert res_deact.code == ErrorCode.DS_CURRENT_METADATA_LOCKED
