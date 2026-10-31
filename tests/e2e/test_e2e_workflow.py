from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.core.session import invalidate_user_session_cache
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_template,
    recon_template_version,
    recon_user,
    recon_user_role,
)
from app.schemas.run import CreateRunParams, RunListFilter
from app.services.file_service import upload_file
from app.services.run_executor import execute_run
from app.services.run_service import create_run, get_row_detail, get_run, list_runs
from app.services.temp_data import mark_checked, purge_runs
from app.ui.pages.dashboard import fetch_dashboard_stats


@pytest.fixture
def workflow_env(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "e2e_workflow.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_STORAGE_DIR", str(storage_dir))
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        # 1. Admin
        res_adm = conn.execute(
            recon_user.insert().values(
                USERNAME="admin_user",
                FULL_NAME="Quản Trị Viên",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        adm_id = res_adm.inserted_primary_key[0]
        conn.execute(recon_user_role.insert().values(USER_ID=adm_id, ROLE=Role.ADMIN.value, CREATED_AT=now))

        # 2. Operator
        res_op = conn.execute(
            recon_user.insert().values(
                USERNAME="op_user",
                FULL_NAME="Vận Hành Viên",
                PASSWORD_HASH=hash_password("op123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        op_id = res_op.inserted_primary_key[0]
        conn.execute(recon_user_role.insert().values(USER_ID=op_id, ROLE=Role.OPERATOR.value, CREATED_AT=now))

        # 3. Viewer
        res_vw = conn.execute(
            recon_user.insert().values(
                USERNAME="viewer_user",
                FULL_NAME="Người Xem",
                PASSWORD_HASH=hash_password("vw123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        vw_id = res_vw.inserted_primary_key[0]
        conn.execute(recon_user_role.insert().values(USER_ID=vw_id, ROLE=Role.VIEWER.value, CREATED_AT=now))

        # Data source
        res_ds = conn.execute(
            recon_data_source.insert().values(
                NAME="ORCL_TEST",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                USERNAME="recon_test",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="admin_user",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = res_ds.inserted_primary_key[0]

        # Template DTP
        import json

        with open("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json", "r", encoding="utf-8") as f:
            tpl_config = json.load(f)

        res_tpl = conn.execute(
            recon_template.insert().values(
                CODE="DTP_HOA_DON_TAC_NGHIEP",
                NAME="DTP – Hóa đơn tác nghiệp",
                OWNER="admin_user",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        tpl_id = res_tpl.inserted_primary_key[0]

        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tpl_id,
                VERSION=1,
                CONFIG_JSON=tpl_config,
                STATUS="ACTIVE",
                CREATED_BY="admin_user",
                CREATED_AT=now,
            )
        )

    return {
        "engine": engine,
        "admin_ctx": Ctx(user_id=adm_id, username="admin_user", full_name="Quản Trị Viên", roles=[Role.ADMIN]),
        "op_ctx": Ctx(user_id=op_id, username="op_user", full_name="Vận Hành Viên", roles=[Role.OPERATOR]),
        "vw_ctx": Ctx(user_id=vw_id, username="viewer_user", full_name="Người Xem", roles=[Role.VIEWER]),
        "ds_id": ds_id,
        "tpl_id": tpl_id,
    }


def test_e2e_spec_07_section_4_flow(workflow_env, monkeypatch):
    """Kiểm thử luồng nghiệp vụ toàn diện theo đặc tả spec 07 mục 4:

    - Operator upload file và tạo run đối soát
    - Worker xử lý và hoàn tất so khớp
    - Operator xem kết quả, kiểm tra xong kèm xóa dữ liệu tạm
    - Lịch sử hiển thị trạng thái đã kiểm tra và đã xóa dữ liệu tạm
    - Admin xóa dữ liệu tạm hàng loạt
    - Viewer bị chặn quyền tạo run và xóa tạm
    - Dashboard hiển thị tổng hợp chính xác
    """
    op_ctx = workflow_env["op_ctx"]
    admin_ctx = workflow_env["admin_ctx"]
    vw_ctx = workflow_env["vw_ctx"]
    tpl_id = workflow_env["tpl_id"]
    ds_id = workflow_env["ds_id"]

    # 1. Operator upload file sample
    sample_path = Path("samples/dtp_sample_200.xlsx")
    assert sample_path.exists(), "File mẫu dtp_sample_200.xlsx phải tồn tại"

    with open(sample_path, "rb") as f:
        file_bytes = f.read()

    upload_res = upload_file(op_ctx, "dtp_sample_200.xlsx", file_bytes)
    assert upload_res.ok
    file_id = upload_res.data["id"]

    # 2. Operator tạo run đối soát
    p_from = datetime(2026, 2, 1, 0, 0, 0)
    p_to = datetime(2026, 2, 5, 23, 59, 59)
    run_params = CreateRunParams(
        template_id=tpl_id,
        template_version=1,
        profile_code="BY_INVOICE",
        file_id=file_id,
        data_source_id=ds_id,
        p_from=p_from,
        p_to=p_to,
        apply_range_excel=True,
    )

    # Viewer cố tạo run -> FORBIDDEN
    vw_create_res = create_run(vw_ctx, run_params)
    assert not vw_create_res.ok
    assert "FORBIDDEN" in str(vw_create_res.code) or "không có quyền" in str(vw_create_res.message).lower()

    # Operator tạo run hợp lệ
    create_res = create_run(op_ctx, run_params)
    assert create_res.ok
    run_id = create_res.data["run_id"]

    # 3. Giả lập execute_run với golden db.parquet của G01
    golden_parquet = Path("tests/golden/G01_dtp_by_invoice/db.parquet")
    assert golden_parquet.exists()
    db_df = pl.read_parquet(golden_parquet)

    def mock_fetcher(config, profile, p_from, p_to, max_rows, timeout):
        return db_df

    exec_res = execute_run(run_id, mock_fetcher=mock_fetcher)
    assert exec_res["status"] == "DONE"

    # Kiểm tra số liệu kết quả run
    run_detail = get_run(op_ctx, run_id)
    assert run_detail.ok
    summary = run_detail.data["summary"]
    assert summary["CNT_MATCHED"] > 0

    # 4. Operator bấm "Đã kiểm tra xong" có xóa dữ liệu tạm
    chk_res = mark_checked(op_ctx, run_id, purge=True)
    assert chk_res.ok
    assert chk_res.data["is_checked"] is True
    assert chk_res.data["purged"] is True

    # Kiểm tra chi tiết dòng sau khi xóa tạm
    row_det = get_row_detail(op_ctx, run_id, row_no=1)
    assert row_det.ok
    assert row_det.data.get("purged_at") is not None and row_det.data.get("excel_raw_rows") is None

    # 5. Màn lịch sử hiển thị run với thông tin đã kiểm tra và đã xóa tạm
    hist_res = list_runs(op_ctx, RunListFilter(is_checked=True, is_temp_purged=True))
    assert hist_res.ok
    assert any(r["id"] == run_id for r in hist_res.data["items"])

    # 6. Admin xóa dữ liệu tạm hàng loạt
    purge_bulk_res = purge_runs(admin_ctx, [run_id])
    assert purge_bulk_res.ok

    # Viewer thử xóa tạm -> bị chặn
    vw_purge_res = purge_runs(vw_ctx, [run_id])
    assert not vw_purge_res.ok

    # 7. Dashboard phản ánh chính xác
    dash_stats = fetch_dashboard_stats(op_ctx)
    assert dash_stats["total_runs"] >= 1
    assert any(r["id"] == run_id for r in dash_stats["recent_runs"])
