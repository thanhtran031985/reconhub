from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_run,
    recon_run_summary,
    recon_template,
    recon_user,
    recon_user_role,
)
from app.ui.pages.run_result import (
    render_detail_drawer,
    render_header,
    render_kpi_cards,
    render_ratio_bar_and_tabs,
    render_result_grid,
)


@pytest.fixture
def run_result_env(tmp_path, monkeypatch):
    db_file = tmp_path / "run_result_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        # User operator
        res_u = conn.execute(
            recon_user.insert().values(
                USERNAME="operator",
                FULL_NAME="Chuyên Viên Đối Soát",
                PASSWORD_HASH=hash_password("op123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        u_id = res_u.inserted_primary_key[0]
        conn.execute(recon_user_role.insert().values(USER_ID=u_id, ROLE="OPERATOR", CREATED_AT=now))

        # Data source & File
        from app.db.metadata import recon_data_source, recon_file

        res_ds = conn.execute(
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
        ds_id = res_ds.inserted_primary_key[0]

        res_f = conn.execute(
            recon_file.insert().values(
                ORIGINAL_NAME="dtp_sample_200.xlsx",
                SIZE_BYTES=31000,
                SHA256="abc12345",
                STORAGE_PATH="samples/dtp_sample_200.xlsx",
                UPLOADED_BY="operator",
                UPLOADED_AT=now,
            )
        )
        f_id = res_f.inserted_primary_key[0]

        # Template
        res_t = conn.execute(
            recon_template.insert().values(
                CODE="DTP_HOA_DON_TAC_NGHIEP",
                NAME="DTP – HĐ tác nghiệp",
                OWNER="owner",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        tmpl_id = res_t.inserted_primary_key[0]

        # Run 1042
        conn.execute(
            recon_run.insert().values(
                ID=1042,
                TEMPLATE_ID=tmpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="BY_INVOICE",
                DATA_SOURCE_ID=ds_id,
                FILE_ID=f_id,
                STATUS="DONE",
                STAGE=5,
                PROGRESS_PCT=100,
                P_FROM=datetime(2026, 2, 1, 0, 0, 0),
                P_TO=datetime(2026, 2, 5, 23, 59, 59),
                CREATED_BY="operator",
                CREATED_AT=now,
                STARTED_AT=now,
                FINISHED_AT=now,
                CHECKED_BY=None,
                CHECKED_AT=None,
                TEMP_PURGED_AT=None,
            )
        )

        # Summary
        conn.execute(
            recon_run_summary.insert().values(
                RUN_ID=1042,
                EXCEL_ROWS_READ=200,
                EXCEL_ROWS_OUT_OF_RANGE=0,
                EXCEL_ROWS_INVALID=0,
                EXCEL_GROUPS=190,
                DB_ROWS=190,
                DB_GROUPS=190,
                CNT_MATCHED=184,
                CNT_MISMATCH=4,
                CNT_MISSING_IN_DB=2,
                CNT_MISSING_IN_EXCEL=2,
                CNT_INCONSISTENT=0,
                CNT_DUPLICATE=0,
                CONTROL_TOTAL_FILE="366732000",
                CONTROL_TOTAL_CALC="366732000",
                CONTROL_TOTAL_OK="Y",
                MEASURE_TOTALS_JSON={"TOTAL_AMOUNT": {"excel": 366732000, "db": 367310000, "diff": -578000}},
                STATUS_AMOUNTS_JSON={},
                COLUMNS_JSON=[],
                DURATION_MS=3800,
            )
        )

    return engine


def test_render_header() -> None:
    run_info = {
        "id": 1042,
        "template_name": "DTP – HĐ tác nghiệp",
        "profile_code": "BY_INVOICE",
        "p_from": "2026-02-01T00:00:00",
        "p_to": "2026-02-05T23:59:59",
        "data_source_id": "ORACLE_TEST",
        "template_version": 1,
        "created_by": "operator",
        "created_at": "2026-10-31T18:20:05",
        "checked_at": None,
        "checked_by": None,
        "temp_purged_at": None,
    }
    header_ui = render_header(run_info)
    assert header_ui is not None
    s = str(header_ui)
    assert "Run #1042" in s
    assert "DTP – HĐ tác nghiệp" in s
    assert "Chưa kiểm tra" in s
    assert "Dữ liệu tạm còn" in s
    assert "Đã kiểm tra xong" in s
    assert "Export Excel" in s


def test_render_kpi_cards() -> None:
    summary = {
        "CONTROL_TOTAL_DIFF": 0,
        "EXCEL_TOTAL_AMOUNT": 366732000,
        "DB_TOTAL_AMOUNT": 367310000,
        "DIFF_TOTAL_AMOUNT": -578000,
        "EXCEL_ROWS_READ": 200,
        "DB_ROWS_READ": 190,
        "CNT_MATCHED": 184,
        "CNT_DIFF": 4,
    }
    kpi_ui = render_kpi_cards(summary)
    assert kpi_ui is not None
    s = str(kpi_ui)
    assert "Control total file" in s
    assert "Tổng tiền Excel (trong khoảng)" in s
    assert "Tổng tiền DB" in s
    assert "Chênh lệch" in s
    assert "366.732.000" in s
    assert "367.310.000" in s


def test_render_ratio_bar_and_tabs() -> None:
    summary = {
        "CNT_MATCHED": 184,
        "CNT_DIFF": 4,
        "CNT_MISSING_DB": 2,
        "CNT_MISSING_EXCEL": 2,
        "CNT_INCONSISTENT": 0,
        "CNT_DUPLICATE": 0,
        "CNT_INVALID": 0,
    }
    tabs_ui = render_ratio_bar_and_tabs(summary, active_tab="ALL")
    assert tabs_ui is not None
    s = str(tabs_ui)
    assert "Tất cả chênh lệch" in s
    assert "Khớp" in s
    assert "Lệch giá trị" in s
    assert "Thiếu trong DB" in s
    assert "Thiếu trong Excel" in s
    assert "184" in s


def test_render_result_grid_and_filters() -> None:
    measures = [{"name": "TOTAL_AMOUNT", "label": "Tổng tiền", "type": "number"}]
    sample_rows = [
        {
            "key": "C26TBD0031338",
            "status": "DIFF",
            "excel": {"TOTAL_AMOUNT": 2592000},
            "db": {"TOTAL_AMOUNT": 2430000},
            "diff": {"TOTAL_AMOUNT": 162000},
        },
        {
            "key": "C26TBD0031335",
            "status": "MATCHED",
            "excel": {"TOTAL_AMOUNT": 1620000},
            "db": {"TOTAL_AMOUNT": 1620000},
            "diff": {"TOTAL_AMOUNT": 0},
        },
    ]

    grid_ui = render_result_grid(
        measures=measures,
        rows=sample_rows,
        search_query="",
        only_diff_cols=False,
    )
    assert grid_ui is not None
    s = str(grid_ui)
    assert "C26TBD0031338" in s
    assert "C26TBD0031335" in s
    assert "Số hóa đơn" in s
    assert "Trạng thái" in s
    assert "Tổng tiền" in s
    assert "rh-diff" in s


def test_render_detail_drawer_temp_purged_and_active() -> None:
    # 1. Dữ liệu tạm còn
    drawer_active = render_detail_drawer(
        row_key="C26TBD0031338",
        status="DIFF",
        raw_excel_rows=[{"row_no": 5, "amount": 2592000, "inv_no": "C26TBD0031338"}],
        db_records=[{"inv_no": "C26TBD0031338", "amount": 2430000}],
        temp_purged_at=None,
    )
    assert drawer_active is not None
    s_act = str(drawer_active)
    assert "C26TBD0031338" in s_act
    assert "Dòng Excel gốc" in s_act
    assert "2.592.000" in s_act or "2592000" in s_act

    # 2. Dữ liệu tạm đã xóa
    drawer_purged = render_detail_drawer(
        row_key="C26TBD0031338",
        status="DIFF",
        raw_excel_rows=[],
        db_records=[{"inv_no": "C26TBD0031338", "amount": 2430000}],
        temp_purged_at="31/10/2026 18:45:00",
    )
    assert drawer_purged is not None
    s_purged = str(drawer_purged)
    assert "Dữ liệu Excel gốc đã xóa lúc 31/10/2026 18:45:00" in s_purged


def test_layout_and_modals(run_result_env, monkeypatch) -> None:
    from app.ui.pages.run_result import handle_check_and_purge_modals, layout

    ctx = Ctx(user_id=1, username="operator", full_name="Operator", roles=[Role.OPERATOR])
    monkeypatch.setattr("app.ui.pages.run_result.get_current_ctx", lambda: ctx)

    page_ui = layout(run_id=1042)
    assert page_ui is not None
    s = str(page_ui)
    assert "run-result-root" in s
    assert "Run #1042" in s
    assert "run-res-check-modal" in s

    # Test callback mark_checked with purge=True
    monkeypatch.setattr(
        "dash.callback_context",
        type("MockCtx", (), {"triggered": [{"prop_id": "run-res-check-modal-confirm.n_clicks"}]})(),
    )
    data_store = {
        "run": {"id": 1042, "checked_at": None, "checked_by": None, "temp_purged_at": None},
        "summary": {},
        "rows": [],
    }
    m_check, m_purge, new_hd, new_store = handle_check_and_purge_modals(
        None, None, 1, None, None, None, True, data_store
    )
    assert m_check is False
    assert m_purge is False
    assert new_store["run"]["checked_at"] is not None
    assert new_store["run"]["temp_purged_at"] is not None
    assert "Đã kiểm tra" in str(new_hd)
    assert "Dữ liệu tạm đã xóa" in str(new_hd)
