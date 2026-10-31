from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
import polars as pl
import pytest
from sqlalchemy import create_engine

from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_file,
    recon_template,
    recon_template_version,
)
from app.schemas.run import CreateRunParams, RunListFilter, RunRowsFilter
from app.services.run_executor import execute_run
from app.services.run_service import (
    create_run,
    export_run,
    get_invalid_rows,
    get_row_detail,
    get_run,
    get_run_columns,
    get_run_rows,
    list_runs,
)

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_sample_config() -> dict:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "recon_test_query.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(
        db_url,
        connect_args={"timeout": 30},
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA busy_timeout=30000")

    metadata.create_all(engine)
    return engine


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])


@pytest.fixture
def completed_g01_run(test_db, admin_ctx):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
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
                SIZE_BYTES=1024,
                STORAGE_PATH="samples/dtp_sample_200.xlsx",
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

    # Tạo run
    res = create_run(
        admin_ctx,
        CreateRunParams(
            template_id=tmpl_id,
            file_id=f_id,
            profile_code="BY_INVOICE",
            p_from=datetime(2026, 2, 1, 0, 0, 0),
            p_to=datetime(2026, 2, 5, 23, 59, 59),
        ),
    )
    run_id = res.data["run_id"]

    # Mock fetcher từ G01 parquet
    db_df = pl.read_parquet(Path("tests/golden/G01_dtp_by_invoice/db.parquet"))

    def mock_fetcher(config, profile, p_from, p_to, max_rows, timeout):
        return db_df

    # Thực thi run
    execute_run(run_id, mock_fetcher=mock_fetcher)
    return {"run_id": run_id, "template_id": tmpl_id}


def test_get_run_and_summary(completed_g01_run, admin_ctx):
    run_id = completed_g01_run["run_id"]
    res = get_run(admin_ctx, run_id)
    assert res.ok
    data = res.data
    assert data["id"] == run_id
    assert data["status"] == "DONE"
    assert data["progress_pct"] == 100
    assert data["template_code"] == "DTP_HOA_DON"

    summ = data["summary"]
    assert summ["CNT_MATCHED"] == 184
    assert summ["CNT_MISMATCH"] == 4
    assert summ["CNT_MISSING_IN_DB"] == 2
    assert summ["CNT_MISSING_IN_EXCEL"] == 2
    assert summ["CONTROL_TOTAL_OK"] == "Y"


def test_list_runs(completed_g01_run, admin_ctx):
    res = list_runs(admin_ctx, RunListFilter(page=1, page_size=10))
    assert res.ok
    data = res.data
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["items"][0]["status"] == "DONE"


def test_get_run_columns(completed_g01_run, admin_ctx):
    run_id = completed_g01_run["run_id"]
    res = get_run_columns(admin_ctx, run_id)
    assert res.ok
    cols = res.data
    fields = [c["field"] for c in cols]
    assert "INVOICE_NO" in fields
    assert "STATUS" in fields
    assert "x__TOTAL_AMOUNT" in fields
    assert "d__TOTAL_AMOUNT" in fields
    assert "diff__TOTAL_AMOUNT" in fields


def test_get_run_rows_filter_and_pagination(completed_g01_run, admin_ctx):
    run_id = completed_g01_run["run_id"]

    # 1. Lọc tất cả các dòng (total = 192)
    res_all = get_run_rows(admin_ctx, run_id, RunRowsFilter(page=1, page_size=50))
    assert res_all.ok
    assert res_all.data["total"] == 192
    assert len(res_all.data["items"]) == 50

    # 2. Lọc chỉ trạng thái MISMATCH (total = 4)
    res_mismatch = get_run_rows(admin_ctx, run_id, RunRowsFilter(status="MISMATCH", page=1, page_size=10))
    assert res_mismatch.ok
    assert res_mismatch.data["total"] == 4
    assert len(res_mismatch.data["items"]) == 4
    for r in res_mismatch.data["items"]:
        assert r["status"] == "MISMATCH"


def test_get_row_detail_with_raw_excel(completed_g01_run, admin_ctx):
    run_id = completed_g01_run["run_id"]

    # Lấy row số 1
    res = get_row_detail(admin_ctx, run_id=run_id, row_no=1)
    assert res.ok
    data = res.data
    assert data["row_no"] == 1
    assert "key_text" in data
    assert "status" in data
    # Có danh sách dòng thô từ RECON_EXCEL_ROW
    assert "excel_raw_rows" in data


def test_get_invalid_rows(completed_g01_run, admin_ctx):
    run_id = completed_g01_run["run_id"]
    res = get_invalid_rows(admin_ctx, run_id=run_id, page=1, page_size=20)
    assert res.ok
    assert res.data["total"] == 0  # G01 không có dòng invalid


def test_export_run(completed_g01_run, admin_ctx, tmp_path):
    run_id = completed_g01_run["run_id"]
    out_file = tmp_path / "export_g01.xlsx"

    res = export_run(admin_ctx, run_id=run_id, output_path=out_file)
    assert res.ok
    assert out_file.exists()

    wb = openpyxl.load_workbook(out_file, data_only=True)
    assert "Tổng hợp" in wb.sheetnames
    assert "Khớp" in wb.sheetnames
    assert "Lệch giá trị" in wb.sheetnames

