from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select

from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_app_setting,
    recon_data_source,
    recon_metadata_migration,
    recon_purge_log,
    recon_run,
    recon_user,
)
from app.schemas.errors import ErrorCode
from app.services.metadata_migration import (
    clean_target_schema,
    delete_old_sqlite,
    get_migration_status,
    list_migrations,
    precheck,
    set_maintenance_mode,
    start_migration,
)


@pytest.fixture
def migration_env(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "recon_source.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")

    get_settings.cache_clear()

    src_engine = create_engine(db_url)
    metadata.create_all(src_engine)

    # Admin (ID 1) phải tồn tại trong DB kèm vai trò ADMIN để qua kiểm tra
    # menu/quyền (task 19); nếu không, user nguồn chèn sau sẽ chiếm ID 1.
    from tests.conftest import seed_perm_basics

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with src_engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                ID=1,
                USERNAME="admin_tester",
                FULL_NAME="Admin Tester",
                PASSWORD_HASH="hash",
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
    seed_perm_basics(src_engine, {1: ["ADMIN"]})

    admin_ctx = Ctx(
        user_id=1,
        username="admin_tester",
        roles=[Role.ADMIN],
        full_name="Admin Tester",
    )
    viewer_ctx = Ctx(
        user_id=2,
        username="viewer_tester",
        roles=[Role.VIEWER],
        full_name="Viewer Tester",
    )

    target_db = tmp_path / "target_recon.db"
    target_engine = create_engine(f"sqlite:///{target_db.as_posix()}")

    return src_engine, target_engine, admin_ctx, viewer_ctx


def test_permission_checks(migration_env):
    _, _, _, viewer_ctx = migration_env

    r1 = precheck(viewer_ctx, target_ds_id=99)
    assert r1.ok is False
    assert r1.code == ErrorCode.FORBIDDEN

    r2 = set_maintenance_mode(viewer_ctx, enabled=True)
    assert r2.ok is False
    assert r2.code == ErrorCode.FORBIDDEN

    r3 = clean_target_schema(viewer_ctx, target_ds_id=99, confirm_schema="TEST")
    assert r3.ok is False
    assert r3.code == ErrorCode.FORBIDDEN

    r4 = delete_old_sqlite(viewer_ctx, confirm_filename="recon_app.db")
    assert r4.ok is False
    assert r4.code == ErrorCode.FORBIDDEN


def test_precheck_target_not_found(migration_env):
    _, _, admin_ctx, _ = migration_env
    res = precheck(admin_ctx, target_ds_id=99999)
    assert res.ok is False
    assert res.code == ErrorCode.NOT_FOUND


def test_precheck_running_run_blocks(migration_env):
    src_engine, target_engine, admin_ctx, _ = migration_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Tạo một data source đích
    with src_engine.begin() as conn:
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="Target Oracle Mock",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                DEFAULT_SCHEMA="RECON_TEST",
                USERNAME="recon_test",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        # Tạo 1 run PROCESSING
        run_id = conn.execute(
            recon_run.insert().values(
                TEMPLATE_ID=1,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="DEFAULT",
                DATA_SOURCE_ID=ds_id,
                STATUS="PROCESSING",
                P_FROM=now,
                P_TO=now,
                CREATED_BY=admin_ctx.username,
                CREATED_AT=now,
            )
        ).inserted_primary_key[0]

    res = precheck(admin_ctx, target_ds_id=ds_id, mock_target_engine=target_engine)
    assert res.ok is False
    assert res.code == ErrorCode.MIGRATION_RUNNING

    # Dọn dẹp run processing
    with src_engine.begin() as conn:
        conn.execute(recon_run.delete().where(recon_run.c.ID == run_id))


def test_precheck_target_not_empty(migration_env):
    src_engine, target_engine, admin_ctx, _ = migration_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Khởi tạo bảng ở target_engine và chèn dữ liệu
    metadata.create_all(target_engine)
    with target_engine.begin() as t_conn:
        t_conn.execute(
            recon_user.insert().values(
                USERNAME="target_existing_user",
                FULL_NAME="Existing",
                PASSWORD_HASH="hash",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    with src_engine.begin() as conn:
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="Target Oracle Mock 2",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                DEFAULT_SCHEMA="RECON_TEST",
                USERNAME="recon_test",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

    res = precheck(admin_ctx, target_ds_id=ds_id, mock_target_engine=target_engine)
    assert res.ok is False
    assert res.code == ErrorCode.MIGRATION_TARGET_NOT_EMPTY


def test_clean_target_schema(migration_env):
    src_engine, target_engine, admin_ctx, _ = migration_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with src_engine.begin() as conn:
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="Target Clean Test",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                DEFAULT_SCHEMA="RECON_SCHEMA_XYZ",
                USERNAME="recon_test",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

    # Khởi tạo bảng trên target_engine
    metadata.create_all(target_engine)

    # 1. Sai tên confirm
    res_err = clean_target_schema(
        admin_ctx,
        target_ds_id=ds_id,
        confirm_schema="WRONG_NAME",
        mock_target_engine=target_engine,
    )
    assert res_err.ok is False
    assert res_err.code == ErrorCode.VALIDATION_ERROR

    # 2. Đúng tên confirm
    res = clean_target_schema(
        admin_ctx,
        target_ds_id=ds_id,
        confirm_schema="RECON_SCHEMA_XYZ",
        mock_target_engine=target_engine,
    )
    assert res.ok is True
    assert res.data["cleaned"] is True


def test_set_maintenance_mode(migration_env):
    src_engine, _, admin_ctx, _ = migration_env

    res_on = set_maintenance_mode(admin_ctx, enabled=True)
    assert res_on.ok is True
    assert res_on.data["maintenance"] == "Y"

    with src_engine.connect() as conn:
        val = conn.execute(select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == "MAINTENANCE")).scalar()
        assert val == "Y"

    res_off = set_maintenance_mode(admin_ctx, enabled=False)
    assert res_off.ok is True
    assert res_off.data["maintenance"] == "N"


def test_start_migration_success(migration_env):
    src_engine, target_engine, admin_ctx, _ = migration_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Tạo đích trống
    with src_engine.begin() as conn:
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="Target Migration Live",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                DEFAULT_SCHEMA="RECON_LIVE",
                USERNAME="recon_live",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        # Thêm 1 user nguồn để có dữ liệu copy
        conn.execute(
            recon_user.insert().values(
                USERNAME="source_user_mig",
                FULL_NAME="Source User",
                PASSWORD_HASH="hash123",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    # Precheck
    pre = precheck(admin_ctx, target_ds_id=ds_id, mode="NO_TEMP", mock_target_engine=target_engine)
    assert pre.ok is True
    assert pre.data["ready"] is True

    # Chạy migration
    res = start_migration(admin_ctx, target_ds_id=ds_id, mode="NO_TEMP", mock_target_engine=target_engine)
    assert res.ok is True
    migration_id = res.data["migration_id"]
    assert res.data["status"] == "DONE"

    # Kiểm tra target_engine có dữ liệu
    with target_engine.connect() as t_conn:
        user_rows = t_conn.execute(select(recon_user.c.USERNAME)).fetchall()
        usernames = [r[0] for r in user_rows]
        assert "source_user_mig" in usernames

    # Kiểm tra status & list
    st = get_migration_status(admin_ctx, migration_id=migration_id)
    assert st.ok is True
    assert st.data["STATUS"] == "DONE"
    assert "RECON_USER" in st.data["REPORT_JSON"]

    lst = list_migrations(admin_ctx)
    assert lst.ok is True
    assert len(lst.data) >= 1


def test_start_migration_failure_preserves_source(migration_env):
    src_engine, target_engine, admin_ctx, _ = migration_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with src_engine.begin() as conn:
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="Target Fail Test",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                DEFAULT_SCHEMA="RECON_FAIL",
                USERNAME="recon_fail",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

    # Precheck
    pre = precheck(admin_ctx, target_ds_id=ds_id, mode="NO_TEMP", mock_target_engine=target_engine)
    assert pre.ok is True

    # Giả lập lỗi khi sao chép
    with patch(
        "app.services.metadata_migration._copy_table_data", side_effect=RuntimeError("Lỗi kết nối giả lập giữa chừng")
    ):
        res = start_migration(admin_ctx, target_ds_id=ds_id, mode="NO_TEMP", mock_target_engine=target_engine)
        assert res.ok is False
        assert res.code == ErrorCode.INTERNAL_ERROR

    # Kiểm tra record trong RECON_METADATA_MIGRATION có STATUS = FAILED
    with src_engine.connect() as conn:
        failed_mig = (
            conn.execute(select(recon_metadata_migration).where(recon_metadata_migration.c.TARGET_DS_ID == ds_id))
            .mappings()
            .first()
        )
        assert failed_mig is not None
        assert failed_mig["STATUS"] == "FAILED"
        assert "Lỗi kết nối giả lập" in str(failed_mig["ERROR_MSG"])

        # Kiểm tra SQLite nguồn vẫn còn nguyên
        ds_rows = conn.execute(select(recon_data_source.c.ID)).fetchall()
        assert len(ds_rows) >= 1


def test_delete_old_sqlite_restrictions(migration_env, tmp_path: Path):
    src_engine, _, admin_ctx, _ = migration_env

    # Khi đang chạy trên SQLite (mặc định của migration_env)
    r_err = delete_old_sqlite(admin_ctx, confirm_filename="recon_app.db")
    assert r_err.ok is False
    assert r_err.code == ErrorCode.FORBIDDEN
    assert "chỉ được xóa bản lưu sqlite cũ sau khi" in r_err.message.lower()

    # Giả lập chạy trên Oracle và xóa file sqlite
    sqlite_file = tmp_path / "recon_old.db"
    sqlite_file.write_bytes(b"dummy sqlite database contents")
    assert sqlite_file.exists()

    with patch("app.services.metadata_migration.get_recon_engine") as mock_engine_fn:
        mock_eng = mock_engine_fn.return_value
        mock_eng.dialect.name = "oracle"
        mock_eng.connect.return_value = src_engine.connect()
        mock_eng.begin.return_value = src_engine.begin()

        # 1. Sai tên confirm
        res_mismatch = delete_old_sqlite(
            admin_ctx,
            confirm_filename="wrong.db",
            target_sqlite_path=str(sqlite_file),
        )
        assert res_mismatch.ok is False
        assert res_mismatch.code == ErrorCode.VALIDATION_ERROR

        # 2. Đúng tên confirm
        res = delete_old_sqlite(
            admin_ctx,
            confirm_filename=sqlite_file.name,
            target_sqlite_path=str(sqlite_file),
        )
        assert res.ok is True
        assert not sqlite_file.exists()
        assert res.data["bytes_freed"] > 0

        # Kiểm tra RECON_PURGE_LOG đã ghi
        with src_engine.connect() as conn:
            purge_row = conn.execute(
                select(recon_purge_log).where(recon_purge_log.c.ACTOR == admin_ctx.username)
            ).first()
            assert purge_row is not None


def _seed_report_data(src_engine, now):
    """Seed 1 report đầy đủ config + 1 run + 1 export (để phân biệt scope)."""
    from app.db.metadata import (
        recon_report,
        recon_report_run,
        recon_report_template,
        recon_rpt_column,
        recon_rpt_export,
        recon_rpt_favorite,
        recon_rpt_param,
        recon_rpt_param_lov,
        recon_rpt_preset,
        recon_rpt_tpl_ver,
    )

    with src_engine.begin() as conn:
        rep_id = conn.execute(
            recon_report.insert().values(
                CODE="MIG_RPT",
                NAME="Báo cáo chuyển",
                OWNER="FIN",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_BY="admin",
                UPDATED_AT=now,
            )
        ).lastrowid
        tpl_id = conn.execute(
            recon_report_template.insert().values(
                REPORT_ID=rep_id,
                CODE="MIG1",
                NAME="Template chuyển",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_BY="admin",
                UPDATED_AT=now,
            )
        ).lastrowid
        ver_id = conn.execute(
            recon_rpt_tpl_ver.insert().values(
                TEMPLATE_ID=tpl_id,
                VERSION_NO=1,
                STATUS="DRAFT",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_BY="admin",
                UPDATED_AT=now,
            )
        ).lastrowid
        param_id = conn.execute(
            recon_rpt_param.insert().values(
                VERSION_ID=ver_id,
                CODE="p_org",
                LABEL="Đơn vị",
                DATA_TYPE="STRING",
                CONTROL_TYPE="TEXT",
            )
        ).lastrowid
        conn.execute(
            recon_rpt_param_lov.insert().values(
                PARAM_ID=param_id, LOV_TYPE="NONE"
            )
        )
        conn.execute(
            recon_rpt_column.insert().values(
                VERSION_ID=ver_id,
                FIELD_NAME="AMOUNT",
                LABEL="Số tiền",
                DATA_TYPE="NUMBER",
            )
        )
        conn.execute(
            recon_rpt_preset.insert().values(
                USER_ID=1,
                REPORT_ID=rep_id,
                TEMPLATE_ID=tpl_id,
                NAME="Preset chuyển",
                PARAMS_JSON={},
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_BY="admin",
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_rpt_favorite.insert().values(
                USER_ID=1, REPORT_ID=rep_id, CREATED_AT=now
            )
        )
        run_id = conn.execute(
            recon_report_run.insert().values(
                REPORT_ID=rep_id,
                TEMPLATE_ID=tpl_id,
                VERSION_ID=ver_id,
                PARAMS_JSON={},
                STATUS="DONE",
                CREATED_BY="admin",
                CREATED_AT=now,
            )
        ).lastrowid
        conn.execute(
            recon_rpt_export.insert().values(
                RUN_ID=run_id,
                FORMAT="CSV",
                STATUS="DONE",
                CREATED_BY="admin",
                CREATED_AT=now,
            )
        )
    return {"report_id": rep_id, "run_id": run_id}


def _target_ds_id(src_engine, now):
    with src_engine.begin() as conn:
        return conn.execute(
            recon_data_source.insert().values(
                NAME="Target Migration Report",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                DEFAULT_SCHEMA="RECON_RPT",
                USERNAME="recon_rpt",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]


def test_config_only_includes_report_config_tables(migration_env):
    src_engine, target_engine, admin_ctx, _ = migration_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    _seed_report_data(src_engine, now)
    ds_id = _target_ds_id(src_engine, now)

    pre = precheck(
        admin_ctx, target_ds_id=ds_id, mode="CONFIG_ONLY",
        mock_target_engine=target_engine,
    )
    assert pre.ok is True, pre.message
    tables = {t["table"] for t in pre.data["tables"]}
    for expected in (
        "RECON_REPORT",
        "RECON_REPORT_TEMPLATE",
        "RECON_RPT_TPL_VER",
        "RECON_RPT_PARAM",
        "RECON_RPT_PARAM_LOV",
        "RECON_RPT_COLUMN",
        "RECON_RPT_PRESET",
        "RECON_RPT_FAVORITE",
    ):
        assert expected in tables, f"CONFIG_ONLY thiếu {expected}"
    # Lịch sử + cache phái sinh không đi theo CONFIG_ONLY.
    for excluded in ("RECON_REPORT_RUN", "RECON_RPT_EXPORT", "RECON_RPT_LOV_CACHE"):
        assert excluded not in tables, f"CONFIG_ONLY không được có {excluded}"


def test_no_temp_includes_report_history(migration_env):
    src_engine, target_engine, admin_ctx, _ = migration_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    _seed_report_data(src_engine, now)
    ds_id = _target_ds_id(src_engine, now)

    pre = precheck(
        admin_ctx, target_ds_id=ds_id, mode="NO_TEMP",
        mock_target_engine=target_engine,
    )
    assert pre.ok is True, pre.message
    tables = {t["table"] for t in pre.data["tables"]}
    for expected in (
        "RECON_REPORT",
        "RECON_REPORT_RUN",
        "RECON_RPT_EXPORT",
        "RECON_RPT_LOV_CACHE",
    ):
        assert expected in tables, f"NO_TEMP thiếu {expected}"
    assert "RECON_EXCEL_LOAD" not in tables
    assert "RECON_EXCEL_ROW" not in tables


def test_start_migration_config_only_copies_report_config(migration_env):
    from sqlalchemy import func as _func

    from app.db.metadata import recon_report, recon_report_run, recon_rpt_export

    src_engine, target_engine, admin_ctx, _ = migration_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    _seed_report_data(src_engine, now)
    ds_id = _target_ds_id(src_engine, now)

    res = start_migration(
        admin_ctx, target_ds_id=ds_id, mode="CONFIG_ONLY",
        mock_target_engine=target_engine,
    )
    assert res.ok is True, res.message
    assert res.data["status"] == "DONE"
    report = res.data["report"]
    assert "RECON_REPORT" in report
    assert "RECON_REPORT_RUN" not in report
    assert "RECON_RPT_EXPORT" not in report
    with target_engine.connect() as t_conn:
        assert (
            t_conn.execute(select(_func.count()).select_from(recon_report)).scalar()
            == 1
        )
        assert (
            t_conn.execute(select(_func.count()).select_from(recon_report_run)).scalar()
            == 0
        )
        assert (
            t_conn.execute(select(_func.count()).select_from(recon_rpt_export)).scalar()
            == 0
        )
