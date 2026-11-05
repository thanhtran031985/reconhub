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
    render_execution_section,
    render_file_section,
    render_params_section,
    render_sql_preview_section,
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

    # Đồng bộ menu + gán vai trò cho operator (ID 3) để qua kiểm tra menu (task 19)
    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine, {3: ["OPERATOR"]})

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

    # Không còn giới hạn số ngày: khoảng 95 ngày vẫn hợp lệ
    f_94 = "2026-01-01T00:00:00"
    t_94 = (datetime(2026, 1, 1) + timedelta(days=95)).isoformat()
    assert validate_run_params(f_94, t_94) is None

    # Hợp lệ
    assert validate_run_params("2026-02-01T00:00:00", "2026-02-05T23:59:59") is None


def test_render_file_section_empty() -> None:
    empty_ui = render_file_section(None, None, [])
    assert empty_ui is not None
    s = str(empty_ui)
    assert "1. File dữ liệu" in s
    assert "new-run-upload" in s
    assert "new-run-manual-template-select" not in s


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
    assert "new-run-manual-template-select" not in s


def test_render_params_and_execution_section(new_run_env) -> None:
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
    assert "new-run-manual-template-select" in s_params
    assert "Chỉ định template đối soát" in s_params
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


def test_render_sql_preview_section() -> None:
    import json

    # 1. Khi chưa có template
    empty_sql_ui = render_sql_preview_section(None)
    assert "Câu lệnh SQL đối soát DB" in str(empty_sql_ui)
    assert "Vui lòng tải lên file hoặc chọn template" in str(empty_sql_ui)

    # 2. Khi có cấu hình template
    tmpl_cfg = json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
    template_info = {"code": "DTP_HOA_DON_TAC_NGHIEP", "config": tmpl_cfg}
    params = {"p_from": "2026-02-01 00:00:00", "p_to": "2026-02-05 23:59:59", "p_org": "BDP"}

    sql_ui = render_sql_preview_section(template_info, profile_code="BY_INVOICE", params=params)
    s_sql = str(sql_ui)
    assert "Câu lệnh SQL đối soát DB" in s_sql
    assert "Đẩy phép gộp xuống DB" in s_sql
    assert "INVOICE_NO" in s_sql
    assert "SRC_FACT_INVOICE_DTP" in s_sql
    assert ":p_from" in s_sql
    assert ":p_to" in s_sql
    assert ":p_org" in s_sql


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


def test_handle_execute_run_ignores_remount_with_n_clicks_zero(monkeypatch) -> None:
    """Nút dựng lại với n_clicks=0 (sau khi Card bị thay) không được tạo run mới."""
    from types import SimpleNamespace

    import app.ui.pages.new_run as new_run_page
    from app.ui.pages.new_run import handle_execute_run

    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(triggered=[{"prop_id": "new-run-execute-btn.n_clicks", "value": 0}]),
    )
    monkeypatch.setattr(
        new_run_page,
        "create_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_run must not be called on remount")),
    )
    result = handle_execute_run(0, None, None, None, None, None, None, None, None, None, None, None)
    assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update)


def test_handle_execute_run_ignores_click_while_running(monkeypatch) -> None:
    from types import SimpleNamespace

    import app.ui.pages.new_run as new_run_page
    from app.ui.pages.new_run import handle_execute_run

    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(triggered=[{"prop_id": "new-run-execute-btn.n_clicks", "value": 2}]),
    )
    monkeypatch.setattr(
        new_run_page,
        "create_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_run must not be called while running")),
    )
    result = handle_execute_run(
        2,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        {"is_running": True, "run_id": 123},
    )
    assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update)


def test_handle_progress_tick_unchanged_returns_no_update(monkeypatch) -> None:
    """Tiến độ không đổi thì không dựng lại Card, tránh giật và remount nút."""
    import app.ui.pages.new_run as new_run_page
    from app.ui.pages.new_run import handle_progress_tick

    row = {"STATUS": "QUEUED", "STAGE": "READ", "PROGRESS_PCT": 10, "ERROR_MSG": None}

    class _Mappings:
        def first(self):
            return row

    class _Result:
        def mappings(self):
            return _Mappings()

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args, **kwargs):
            return _Result()

    class _Engine:
        def connect(self):
            return _Conn()

    monkeypatch.setattr(new_run_page, "get_recon_engine", lambda: _Engine())
    ui, state, redirect = handle_progress_tick(5, {"is_running": True, "run_id": 999, "stage": 1, "pct": 10})
    assert ui is dash.no_update
    assert state is dash.no_update
    assert redirect is dash.no_update


def test_apply_excel_time_switch_defaults_unchecked() -> None:
    params_ui = render_params_section(
        template_info={
            "code": "DTP",
            "config": {"profiles": [{"code": "BY_INVOICE", "name": "Theo số hóa đơn", "is_default": True}]},
        },
        data_sources=[],
        active_templates=[],
    )
    assert "new-run-apply-excel-time" in str(params_ui)
    # Tìm component switch và kiểm tra checked=False
    import dash_mantine_components as dmc

    def _find(node):
        if getattr(node, "id", None) == "new-run-apply-excel-time":
            return node
        for child in getattr(node, "children", []) or []:
            if isinstance(child, (list, tuple)):
                for c in child:
                    found = _find(c)
                    if found is not None:
                        return found
            else:
                found = _find(child)
                if found is not None:
                    return found
        return None

    switch = _find(params_ui)
    assert switch is not None
    assert isinstance(switch, dmc.Switch)
    assert switch.checked is False


def test_layout_renders_with_active_templates(new_run_env, monkeypatch) -> None:
    ctx = Ctx(user_id=3, username="operator", full_name="Operator", roles=[Role.OPERATOR])
    monkeypatch.setattr("app.ui.pages.new_run.get_current_ctx", lambda: ctx)

    page_ui = layout()
    assert page_ui is not None
    s = str(page_ui)
    assert "new-run-root" in s
    assert "Chạy đối soát" in s
    assert "new-run-upload" in s
    assert "Câu lệnh SQL đối soát DB" in s
    # Card Thực thi phải đứng trên Card SQL để không phải kéo xuống
    # mỗi lần chạy.
    assert s.index("new-run-exec-container") < s.index("new-run-sql-container")
