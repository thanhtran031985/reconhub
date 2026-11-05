from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest
from sqlalchemy import create_engine, select

from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_excel_load,
    recon_excel_row,
    recon_file,
    recon_purge_log,
    recon_result_row,
    recon_run,
    recon_template,
    recon_template_version,
)
from app.schemas.errors import ErrorCode
from app.schemas.run import CreateRunParams, PurgeFilter
from app.services.run_executor import execute_run
from app.services.run_service import create_run
from app.services.temp_data import (
    mark_checked,
    preview,
    purge_filter,
    purge_runs,
    usage,
)

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_sample_config() -> dict:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "recon_test_purge.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_STORAGE_DIR", str(storage_dir))

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(
        db_url,
        connect_args={"timeout": 30},
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA auto_vacuum = INCREMENTAL")
        conn.exec_driver_sql("PRAGMA journal_mode = WAL")
        conn.exec_driver_sql("PRAGMA busy_timeout = 30000")

    metadata.create_all(engine)
    return engine


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])


@pytest.fixture
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="Operator", roles=[Role.OPERATOR])


@pytest.fixture
def purge_setup(test_db, operator_ctx, tmp_path):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Copy file mẫu vào storage
    storage_base = tmp_path / "storage" / "files"
    storage_base.mkdir(parents=True, exist_ok=True)
    f_path = storage_base / "dummy_file.xlsx"
    f_path.write_bytes(Path("samples/dtp_sample_200.xlsx").read_bytes())

    with test_db.begin() as conn:
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="ORACLE_DEV",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="orcl",
                USERNAME="RECON_SRC_RO",
                PASSWORD_ENC="dummy",
                DEFAULT_SCHEMA="RECON_SRC",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        f_id = conn.execute(
            recon_file.insert().values(
                SHA256="dummy_sha256",
                ORIGINAL_NAME="dtp_sample_200.xlsx",
                SIZE_BYTES=len(f_path.read_bytes()),
                STORAGE_PATH=str(f_path),
                SHEETS_JSON=["BÁO CÁO DTP"],
                UPLOADED_BY="admin",
                UPLOADED_AT=now,
            )
        ).inserted_primary_key[0]

        tmpl_id = conn.execute(
            recon_template.insert().values(
                CODE="DTP_HOA_DON",
                NAME="DTP Hóa đơn",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        cfg = get_sample_config()
        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tmpl_id,
                VERSION=1,
                STATUS="ACTIVE",
                CONFIG_JSON=cfg,
                DATA_SOURCE_ID=ds_id,
                DRY_RUN_OK="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                ACTIVATED_AT=now,
            )
        )

    # Tạo 2 runs dùng chung 1 file
    db_df = pl.read_parquet(Path("tests/golden/G01_dtp_by_invoice/db.parquet"))

    def mock_fetcher(config, profile, p_from, p_to, max_rows, timeout):
        return db_df

    # Run do operator tạo để kiểm tra phạm vi dữ liệu (Q11, task 19)
    res1 = create_run(
        operator_ctx,
        CreateRunParams(
            template_id=tmpl_id,
            file_id=f_id,
            profile_code="BY_INVOICE",
            p_from=datetime(2026, 2, 1, 0, 0, 0),
            p_to=datetime(2026, 2, 5, 23, 59, 59),
        ),
    )
    run_id1 = res1.data["run_id"]
    execute_run(run_id1, mock_fetcher=mock_fetcher)

    res2 = create_run(
        operator_ctx,
        CreateRunParams(
            template_id=tmpl_id,
            file_id=f_id,
            profile_code="BY_INVOICE",
            p_from=datetime(2026, 2, 1, 0, 0, 0),
            p_to=datetime(2026, 2, 5, 23, 59, 59),
        ),
    )
    run_id2 = res2.data["run_id"]
    execute_run(run_id2, mock_fetcher=mock_fetcher)

    return {
        "run_id1": run_id1,
        "run_id2": run_id2,
        "file_id": f_id,
        "f_path": f_path,
        "template_id": tmpl_id,
    }


def test_mark_checked_only(purge_setup, operator_ctx, test_db):
    run_id = purge_setup["run_id1"]
    res = mark_checked(operator_ctx, run_id=run_id, purge=False)
    assert res.ok
    assert res.data["is_checked"] is True
    assert res.data["purged"] is False

    with test_db.connect() as conn:
        r = conn.execute(select(recon_run).where(recon_run.c.ID == run_id)).mappings().first()
        assert r is not None
        assert r["CHECKED_AT"] is not None
        assert r["CHECKED_BY"] == "operator"
        assert r["TEMP_PURGED_AT"] is None


def test_purge_running_forbidden(purge_setup, admin_ctx, test_db):
    # Đưa run_id1 về RUNNING
    run_id = purge_setup["run_id1"]
    with test_db.begin() as conn:
        conn.execute(recon_run.update().where(recon_run.c.ID == run_id).values(STATUS="RUNNING"))

    res = purge_runs(admin_ctx, [run_id])
    assert not res.ok
    assert res.code == ErrorCode.RUN_BUSY


def test_operator_forbidden_from_bulk_purge(purge_setup, operator_ctx):
    # Xóa hàng loạt (2 run) cần ADMIN; xóa 1 run của mình thì được (Q11)
    res = purge_runs(operator_ctx, [purge_setup["run_id1"], purge_setup["run_id2"]])
    assert not res.ok
    assert res.code == ErrorCode.FORBIDDEN


def test_shared_data_lifecycle_and_purge(purge_setup, admin_ctx, test_db):
    run1 = purge_setup["run_id1"]
    run2 = purge_setup["run_id2"]
    f_path = purge_setup["f_path"]

    # 1. Đánh dấu kiểm tra và xóa run 1
    res1 = mark_checked(admin_ctx, run_id=run1, purge=True)
    assert res1.ok
    assert res1.data["purged"] is True

    # Do run 2 vẫn đang dùng chung file và excel load, RECON_EXCEL_ROW và file chưa bị xóa!
    with test_db.connect() as conn:
        r1 = conn.execute(select(recon_run).where(recon_run.c.ID == run1)).mappings().first()
        assert r1["TEMP_PURGED_AT"] is not None

        # Excel load chưa bị xóa (PURGED_AT is None)
        load_row = conn.execute(select(recon_excel_load).where(recon_excel_load.c.PURGED_AT.is_(None))).first()
        assert load_row is not None

        # Các dòng kết quả RECON_RESULT_ROW của run 1 vẫn còn nguyên (kết quả không bị xóa)
        res_rows1 = conn.execute(select(recon_result_row).where(recon_result_row.c.RUN_ID == run1)).all()
        assert len(res_rows1) == 192

        # File gốc vẫn còn tồn tại
        assert f_path.exists()

    # 2. Xóa tiếp run 2
    res2 = mark_checked(admin_ctx, run_id=run2, purge=True)
    assert res2.ok

    # Bây giờ không còn run nào dùng chung nữa, RECON_EXCEL_ROW và file gốc được dọn dẹp sạch!
    with test_db.connect() as conn:
        # Load đã đánh dấu PURGED_AT
        load_row_purged = conn.execute(
            select(recon_excel_load).where(recon_excel_load.c.PURGED_AT.is_not(None))
        ).first()
        assert load_row_purged is not None

        # RECON_EXCEL_ROW đã bị xóa sạch (0 dòng)
        ex_rows = conn.execute(select(recon_excel_row)).all()
        assert len(ex_rows) == 0

        # File gốc đã bị xóa
        assert not f_path.exists()

        f_rec = conn.execute(select(recon_file).where(recon_file.c.ID == purge_setup["file_id"])).mappings().first()
        assert f_rec["PURGED_AT"] is not None
        assert f_rec["STORAGE_PATH"] is None


def test_purge_filter_confirm_mismatch(purge_setup, admin_ctx):
    # Nhập từ khóa không đúng "XOA" -> PURGE_CONFIRM_MISMATCH
    res = purge_filter(
        admin_ctx,
        PurgeFilter(template_id=purge_setup["template_id"], only_checked=False),
        confirm_text="KHONG_DUNG",
    )
    assert not res.ok
    assert res.code == ErrorCode.PURGE_CONFIRM_MISMATCH


def test_preview_and_purge_filter_success(purge_setup, admin_ctx, test_db):
    # Preview
    prev_res = preview(
        admin_ctx,
        PurgeFilter(template_id=purge_setup["template_id"], only_checked=False),
    )
    assert prev_res.ok
    assert prev_res.data["run_count"] == 2
    assert prev_res.data["rows_estimated"] > 0

    # Purge với confirm_text="XOA"
    res = purge_filter(
        admin_ctx,
        PurgeFilter(template_id=purge_setup["template_id"], only_checked=False),
        confirm_text="XOA",
    )
    assert res.ok
    assert res.data["runs_purged"] == 2

    # Kiểm tra RECON_PURGE_LOG được ghi nhận
    with test_db.connect() as conn:
        p_log = conn.execute(select(recon_purge_log)).mappings().first()
        assert p_log is not None
        assert p_log["SCOPE"] == "FILTER"
        assert p_log["RUN_COUNT"] == 2
        assert p_log["ACTOR"] == "admin"


def test_usage_metrics(purge_setup, admin_ctx):
    res = usage(admin_ctx)
    assert res.ok
    data = res.data
    assert "total_bytes" in data
    assert "runs_unpurged_count" in data
    assert "runs_unchecked_count" in data
    assert "is_warning" in data
