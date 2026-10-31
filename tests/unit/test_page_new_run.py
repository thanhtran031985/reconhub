from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dash
import pytest
from sqlalchemy import create_engine, select, update

from app.cli import seed_cmd
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import metadata, recon_data_source, recon_template, recon_template_version
from app.ui.pages.new_run import (
    compute_quick_range,
    layout,
    process_uploaded_file,
    render_file_section,
    validate_run_params,
)

SAMPLE_PATH = Path("samples/dtp_sample_200.xlsx")


@pytest.fixture
def new_run_env(tmp_path, monkeypatch):
    db_file = tmp_path / "new_run_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    # Seed users and templates
    seed_cmd(argparse.Namespace())

    # Kích hoạt template DTP_HOA_DON_TAC_NGHIEP
    with engine.begin() as conn:
        tmpl_id = conn.scalar(select(recon_template.c.ID).where(recon_template.c.CODE == "DTP_HOA_DON_TAC_NGHIEP"))
        if tmpl_id:
            conn.execute(
                update(recon_template).where(recon_template.c.ID == tmpl_id).values(STATUS="ACTIVE", CURRENT_VERSION=1)
            )
            conn.execute(
                update(recon_template_version)
                .where(recon_template_version.c.TEMPLATE_ID == tmpl_id)
                .values(STATUS="ACTIVE")
            )

        # Thêm 2 Data Sources: 1 DEV và 1 PROD
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conn.execute(
            recon_data_source.insert().values(
                NAME="ORACLE_TEST",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="TESTSVC",
                USERNAME="recon_test",
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="test",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_data_source.insert().values(
                NAME="DWH_FIN",
                ENV="PROD",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="prod-host",
                PORT=1521,
                SERVICE_NAME="PRODSVC",
                USERNAME="recon_prod",
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="test",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    return engine


def test_quick_range_calculation() -> None:
    fixed_now = datetime(2026, 2, 6, 12, 0, 0)
    # Yesterday
    f_y, t_y = compute_quick_range("yesterday", now_dt=fixed_now)
    assert f_y == "2026-02-05T00:00:00"
    assert t_y == "2026-02-05T23:59:59"

    # Last month
    f_m, t_m = compute_quick_range("last_month", now_dt=fixed_now)
    assert f_m == "2026-01-01T00:00:00"
    assert t_m == "2026-01-31T23:59:59"


def test_validate_run_params() -> None:
    # Thiếu trường
    assert validate_run_params(None, "2026-02-05T23:59:59") == "Nhập Từ ngày giờ."
    assert validate_run_params("2026-02-01T00:00:00", "") == "Nhập Đến ngày giờ."

    # Từ > Đến
    err_rev = validate_run_params("2026-02-05T00:00:00", "2026-02-01T00:00:00")
    assert err_rev == "Từ ngày giờ phải nhỏ hơn hoặc bằng Đến ngày giờ."

    # Quá 93 ngày
    f_94 = "2026-01-01T00:00:00"
    t_94 = (datetime(2026, 1, 1) + timedelta(days=95)).isoformat()
    assert validate_run_params(f_94, t_94) == "Khoảng tìm kiếm tối đa 93 ngày."

    # Hợp lệ
    assert validate_run_params("2026-02-01T00:00:00", "2026-02-05T23:59:59") is None


def test_render_file_section_empty() -> None:
    empty_ui = render_file_section(None, None, [])
    assert empty_ui is not None
    s = str(empty_ui)
    assert "1. File dữ liệu" in s
    assert "new-run-upload" in s


def test_process_uploaded_file_and_render(new_run_env) -> None:
    ctx = Ctx(user_id=3, username="operator", full_name="Operator", roles=[Role.OPERATOR])
    file_bytes = SAMPLE_PATH.read_bytes()

    res = process_uploaded_file(ctx, "dtp_sample_200.xlsx", file_bytes)
    assert res is not None
    assert res["file_id"] > 0
    assert res["detected_template"] is not None
    assert res["detected_template"]["code"] == "DTP_HOA_DON_TAC_NGHIEP"
    assert res["valid_rows"] == 200
    assert res["footer_rows"] == 1
    assert res["control_total_diff"] == 0

    # Test render section with uploaded file
    file_ui = render_file_section(res["file_data"], res["detected_template"], [])
    s = str(file_ui)
    assert "dtp_sample_200.xlsx" in s
    assert "DTP_HOA_DON_TAC_NGHIEP" in s
    assert "200 dòng hợp lệ" in s
    assert "1 dòng tổng đã loại" in s
    assert "Control total khớp" in s


def test_render_params_and_execution_section(new_run_env) -> None:
    from app.ui.pages.new_run import render_execution_section, render_params_section

    # 1. Render params section
    ds_list = [
        {"id": 1, "name": "ORACLE_TEST", "env": "DEV", "label": "ORACLE_TEST (DEV)"},
        {"id": 2, "name": "DWH_FIN", "env": "PROD", "label": "DWH_FIN (PROD)"},
    ]
    precheck_info = {
        "est_excel_rows": 200,
        "p_from_str": "01/02/2026 00:00:00",
        "p_to_str": "05/02/2026 23:59:59",
    }
    params_ui = render_params_section(
        template_info={
            "code": "DTP",
            "config": {"profiles": [{"code": "BY_INVOICE", "name": "Theo số hóa đơn", "is_default": True}]},
        },
        data_sources=ds_list,
        precheck_info=precheck_info,
        err_msg=None,
    )
    s_params = str(params_ui)
    assert "2. Profile và tham số tìm kiếm" in s_params
    assert "new-run-p-from" in s_params
    assert "new-run-p-to" in s_params
    assert "new-run-p-org" in s_params
    assert "Hôm qua" in s_params
    assert "Tháng trước" in s_params
    assert "Oracle truy vấn với :p_from" in s_params

    # 2. Render execution section
    exec_ui_ready = render_execution_section(is_ready=True, lock_reason="")
    s_exec = str(exec_ui_ready)
    assert "3. Thực thi" in s_exec
    assert "Chạy đối soát" in s_exec

    exec_ui_running = render_execution_section(
        is_ready=False,
        lock_reason="",
        is_running=True,
        current_stage=3,
        stage_desc="Truy vấn Oracle (qua VPN)",
        progress_pct=60,
    )
    s_running = str(exec_ui_running)
    assert "3/5 Truy vấn Oracle (qua VPN)" in s_running


def test_handle_progress_tick_stages_and_redirect() -> None:
    from app.ui.pages.new_run import handle_progress_tick

    # Stage 1 -> Stage 2
    state1 = {"is_running": True, "run_id": 999, "stage": 1, "pct": 20}
    ui, state2, redirect = handle_progress_tick(1, state1)
    assert state2["stage"] == 2
    assert state2["pct"] == 40
    assert redirect == dash.no_update

    # Stage at 100% -> redirects to /runs/999
    state_done = {"is_running": True, "run_id": 999, "stage": 5, "pct": 100}
    _, state_fin, redirect_done = handle_progress_tick(5, state_done)
    assert state_fin["is_running"] is False
    assert redirect_done == "/runs/999"


def test_layout_renders_with_active_templates(new_run_env, monkeypatch) -> None:
    ctx = Ctx(user_id=3, username="operator", full_name="Operator", roles=[Role.OPERATOR])
    monkeypatch.setattr("app.ui.pages.new_run.get_current_ctx", lambda: ctx)

    page_ui = layout()
    assert page_ui is not None
    s = str(page_ui)
    assert "new-run-root" in s
    assert "Chạy đối soát" in s
    assert "new-run-upload" in s
