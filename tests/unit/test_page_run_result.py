from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
)
from app.ui.pages.run_result import (
    handle_compare_runs,
    render_compare_drawer_content,
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

    # Đồng bộ menu + vai trò seed (task 19) trước khi chèn user
    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

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
        seed_perm_basics(engine, {u_id: ["OPERATOR"]}, conn=conn)

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
    assert "So với run trước" in s


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

    # Bảng kết quả chính phải bật kẻ dọc giữa các cột
    import dash_mantine_components as dmc

    def _find_table(node):
        if isinstance(node, dmc.Table):
            return node
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            items = children
        elif children is not None and not isinstance(children, str):
            items = [children]
        else:
            items = []
        for child in items:
            found = _find_table(child)
            if found is not None:
                return found
        return None

    table = _find_table(grid_ui)
    assert table is not None
    assert table.withColumnBorders is True


def test_grid_measures_follow_profile_main_measure_not_hardcoded_total_amount(monkeypatch) -> None:
    """Lưới phải lấy measure chính của profile đã chạy, không hardcode TOTAL_AMOUNT.

    Tái hiện ảnh /runs/1012: profile BILL_VTOS dùng TOTAL_TONG_TIEN nên
    tra TOTAL_AMOUNT trong EXCEL_JSON/DB_JSON/DIFF_JSON ra None và hiện
    toàn "—", trong khi drawer chi tiết tự suy khóa nên vẫn có số.
    """
    from types import SimpleNamespace

    from app.ui.pages.run_result import _resolve_grid_measures

    run_info = {"template_id": 8, "template_version": 9, "profile_code": "BILL_VTOS"}

    # Đường config: ngay cả khi trang kết quả đang trống vẫn ra đúng measure.
    fake_res = SimpleNamespace(
        ok=True,
        data={
            "config": {
                "profiles": [
                    {
                        "code": "BILL_VTOS",
                        "main_measure": "TOTAL_TONG_TIEN",
                        "measures": [{"name": "TOTAL_TONG_TIEN", "label": "Tổng tiền"}],
                    }
                ]
            }
        },
    )
    monkeypatch.setattr("app.ui.pages.run_result.get_template", lambda *a, **k: fake_res)
    ctx = Ctx(user_id=1, username="operator", full_name="Operator", roles=[Role.OPERATOR])
    measures = _resolve_grid_measures(ctx, run_info, [])
    assert measures == [{"name": "TOTAL_TONG_TIEN", "label": "Tổng tiền", "type": "number"}]

    # Đường dự phòng khi không lấy được config: suy từ khóa JSON của dòng.
    monkeypatch.setattr(
        "app.ui.pages.run_result.get_template",
        lambda *a, **k: SimpleNamespace(ok=False, data=None),
    )
    rows = [
        {
            "key": "C26TBD0149467",
            "status": "MISSING_IN_DB",
            "excel": {"x__TOTAL_TONG_TIEN": 1425000},
            "db": {"d__TOTAL_TONG_TIEN": None},
            "diff": {"diff__TOTAL_TONG_TIEN": 1425000},
        }
    ]
    assert _resolve_grid_measures(None, run_info, rows)[0]["name"] == "TOTAL_TONG_TIEN"
    assert _resolve_grid_measures(None, {}, []) == [{"name": "TOTAL_AMOUNT", "label": "Tổng tiền", "type": "number"}]

    # Lưới với measure đúng phải hiện số, kể cả giá trị 0 (không rơi thành "—").
    grid_ui = render_result_grid(
        measures=[{"name": "TOTAL_TONG_TIEN", "label": "Tổng tiền", "type": "number"}],
        rows=rows
        + [
            {
                "key": "C26TBD0000000",
                "status": "MATCHED",
                "excel": {"x__TOTAL_TONG_TIEN": 0},
                "db": {"d__TOTAL_TONG_TIEN": 0},
                "diff": {"diff__TOTAL_TONG_TIEN": 0},
            }
        ],
    )
    s = str(grid_ui)
    assert "1.425.000" in s
    assert "Tổng tiền" in s
    # Dòng 0 phải hiện "0" ở cột Excel, không bị `or` đẩy thành "—".
    assert s.count("1.425.000") >= 2


def test_other_status_tabs_and_detail_drawer_use_profile_measure() -> None:
    """Các tab trạng thái khác và drawer chi tiết phải cùng hiện số Excel/DB.

    Tất cả tab trạng thái dùng chung render_result_grid nên chỉ cần measure
    đúng là đủ; riêng drawer trước đây hardcode TOTAL_AMOUNT ở 2 chỗ: dòng
    Excel gốc (Thành tiền ra 0) và bản ghi DB (ra 0, tiêu đề TOTAL_AMOUNT).
    """
    # Lưới: 4 trạng thái, cùng measure TOTAL_TONG_TIEN, đều phải hiện số.
    measures = [{"name": "TOTAL_TONG_TIEN", "label": "Tổng tiền", "type": "number"}]
    rows = [
        {
            "key": "K1",
            "status": "MATCHED",
            "excel": {"x__TOTAL_TONG_TIEN": 1000000},
            "db": {"d__TOTAL_TONG_TIEN": 1000000},
            "diff": {"diff__TOTAL_TONG_TIEN": 0},
        },
        {
            "key": "K2",
            "status": "MISMATCH",
            "excel": {"x__TOTAL_TONG_TIEN": 2000000},
            "db": {"d__TOTAL_TONG_TIEN": 1900000},
            "diff": {"diff__TOTAL_TONG_TIEN": 100000},
        },
        {
            "key": "K3",
            "status": "MISSING_IN_DB",
            "excel": {"x__TOTAL_TONG_TIEN": 1425000},
            "db": {"d__TOTAL_TONG_TIEN": None},
            "diff": {"diff__TOTAL_TONG_TIEN": 1425000},
        },
        {
            "key": "K4",
            "status": "MISSING_IN_EXCEL",
            "excel": {"x__TOTAL_TONG_TIEN": None},
            "db": {"d__TOTAL_TONG_TIEN": 900000},
            "diff": {"diff__TOTAL_TONG_TIEN": -900000},
        },
    ]
    s_grid = str(render_result_grid(measures=measures, rows=rows))
    for key in ("K1", "K2", "K3", "K4"):
        assert key in s_grid
    for amount in ("1.000.000", "2.000.000", "1.425.000", "900.000"):
        assert amount in s_grid

    # Drawer: dòng Excel gốc lấy theo trường của measure chính, bản ghi DB
    # lấy theo tên measure chính, không còn 0 do tra sai tên.
    drawer_ui = render_detail_drawer(
        row_detail={
            "key_text": "C26TBD0149467 | 2026-06-23 13:43:30",
            "status": "MISSING_IN_DB",
            "row_no": 1,
            "run_id": 1012,
            "issue": {},
            "excel_raw_rows": [
                {
                    "excel_row_no": 1525,
                    "data": {"HOA_DON": "C26TBD0149467", "TONG_TIEN": 1425000},
                }
            ],
            "excel": {"x__TOTAL_TONG_TIEN": 1425000},
            "db": {"d__TOTAL_TONG_TIEN": None},
            "diff": {"diff__TOTAL_TONG_TIEN": 1425000},
        },
        reasons_list=[],
        main_measure_name="TOTAL_TONG_TIEN",
        main_measure_field="TONG_TIEN",
        group_by_fields=["HOA_DON"],
    )
    s_drawer = str(drawer_ui)
    assert "1.425.000" in s_drawer
    assert "TOTAL_TONG_TIEN (DB)" in s_drawer
    # Dòng Excel gốc phải hiện đúng 1.425.000, không phải 0 do tra TOTAL_AMOUNT.
    assert s_drawer.count("1.425.000") >= 2

    # KPI: khi truyền tên measure chính thì lấy đúng chỉ tiêu đó, không lấy
    # measure đầu tiên trong dict (ở đây là số lượng).
    kpi_ui = render_kpi_cards(
        {
            "MEASURE_TOTALS_JSON": {
                "TOTAL_QTY": {"excel": 5, "db": 5, "diff": 0},
                "TOTAL_TONG_TIEN": {"excel": 1425000, "db": 0, "diff": 1425000},
            }
        },
        main_measure_name="TOTAL_TONG_TIEN",
    )
    assert "1.425.000" in str(kpi_ui)


def test_result_grid_headers_centered_rows_hoverable_and_tabs_xs() -> None:
    from pathlib import Path

    import dash_mantine_components as dmc

    # Header: 3 header tầng trên canh giữa
    from app.ui.pages.run_result import build_grid_headers

    thead = build_grid_headers([{"name": "TOTAL_AMOUNT", "label": "Tổng tiền"}])
    top_row = thead.children[0]
    for th in top_row.children[:3]:
        assert th.style.get("textAlign") == "center"

    # Dòng kết quả mang class run-res-row để CSS kẻ ngang + hover áp dụng
    grid_ui = render_result_grid(
        measures=[{"name": "TOTAL_AMOUNT", "label": "Tổng tiền"}],
        rows=[
            {
                "key": "X1",
                "status": "DIFF",
                "excel": {"TOTAL_AMOUNT": 1},
                "db": {"TOTAL_AMOUNT": 2},
                "diff": {"TOTAL_AMOUNT": 1},
            }
        ],
    )
    assert "run-res-row" in str(grid_ui)
    css = Path("app/ui/assets/custom.css").read_text(encoding="utf-8")
    assert ".run-res-row td" in css
    assert ".run-res-row:hover" in css

    # Tab: nút và badge đều xuống xs
    tabs_ui = render_ratio_bar_and_tabs({"CNT_MATCHED": 1, "CNT_MISMATCH": 2})
    tab_group = tabs_ui.children[1]
    first_btn = tab_group.children[0]
    assert isinstance(first_btn, dmc.Button)
    assert first_btn.size == "xs"
    badge = first_btn.children[1]
    assert isinstance(badge, dmc.Badge)
    assert badge.size == "xs"


def test_render_header_badges_moved_to_right() -> None:
    header = render_header(
        {
            "id": 1010,
            "template_name": "Doanh thu Vtos",
            "profile_code": "BY_INVOICE",
            "p_from": "2026-01-01",
            "p_to": "2026-07-31",
            "data_source_id": 2,
            "template_version": 3,
            "created_by": "admin",
            "created_at": "2026-11-04",
            "file_size": 1600000,
        }
    )
    left, right = header.children
    # Cột trái chỉ còn tiêu đề + metadata, không còn badge
    assert len(left.children) == 2
    assert "Chưa kiểm tra" not in str(left)
    # Cột phải chứa badge, canh phải
    assert "Chưa kiểm tra" in str(right)
    assert "Dữ liệu tạm còn" in str(right)


def test_render_header_xs_sizes() -> None:
    import dash_mantine_components as dmc

    header = render_header(
        {
            "id": 1010,
            "template_name": "Doanh thu Vtos",
            "profile_code": "BY_INVOICE",
            "p_from": "2026-01-01",
            "p_to": "2026-07-31",
            "data_source_id": 2,
            "template_version": 3,
            "created_by": "admin",
            "created_at": "2026-11-04",
            "file_size": 1600000,
        }
    )
    left, right = header.children
    # Dòng phụ giảm từ sm xuống xs để đỡ rớt dòng ở màn hình nhỏ
    assert left.children[1].size == "xs"
    btn_group, badge_group = right.children
    assert btn_group.gap == "xs"
    visible_btns = [b for b in btn_group.children if isinstance(b, dmc.Button)]
    assert visible_btns and all(b.size == "xs" for b in visible_btns)
    assert all(b.size == "xs" for b in badge_group.children)


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


def test_render_compare_drawer_content() -> None:
    empty_ui = render_compare_drawer_content(1041, 1042, None)
    assert "Không có run trước để so sánh" in str(empty_ui)

    compare_data = {
        "run_a": {"id": 1041, "created_at": "2026-02-01T10:00:00"},
        "run_b": {"id": 1042, "created_at": "2026-02-05T12:00:00"},
        "summary": {
            "count_only_in_a": 1,
            "count_only_in_b": 2,
            "count_status_changed": 1,
            "count_same_status": 6,
            "total_keys": 10,
        },
        "items": [
            {
                "key_text": "INV_001",
                "category": "ONLY_IN_A",
                "status_a": "DIFF",
                "status_b": None,
                "abs_diff_a": 100,
                "abs_diff_b": None,
            },
            {
                "key_text": "INV_002",
                "category": "ONLY_IN_B",
                "status_a": None,
                "status_b": "DIFF",
                "abs_diff_a": None,
                "abs_diff_b": 200,
            },
            {
                "key_text": "INV_003",
                "category": "STATUS_CHANGED",
                "status_a": "DIFF",
                "status_b": "MATCHED",
                "abs_diff_a": 50,
                "abs_diff_b": 0,
            },
        ],
    }

    content_ui = render_compare_drawer_content(1041, 1042, compare_data, active_tab="ALL")
    assert content_ui is not None
    s = str(content_ui)
    assert "#1041" in s
    assert "#1042" in s
    assert "Chỉ có ở Run A" in s
    assert "Chỉ có ở Run B" in s
    assert "Đổi trạng thái" in s
    assert "Giữ nguyên" in s
    assert "INV_001" in s
    assert "INV_002" in s
    assert "INV_003" in s


def test_handle_compare_runs_callback(monkeypatch) -> None:
    monkeypatch.setattr(
        "dash.callback_context",
        type("MockCtx", (), {"triggered": [{"prop_id": "run-res-compare-btn.n_clicks"}]})(),
    )
    data_store = {
        "run": {"id": 1042},
        "summary": {},
        "rows": [],
    }
    opened, ui, data, current_filter = handle_compare_runs(1, [], data_store, None, None)
    assert opened is True
    assert ui is not None
    assert current_filter == "ALL"
    assert data is not None


def test_handle_save_issue_from_drawer(run_result_env, monkeypatch) -> None:
    from app.schemas.errors import ServiceResult
    from app.ui.pages.run_result import handle_save_issue_from_drawer

    ctx = Ctx(user_id=1, username="operator", full_name="Operator", roles=[Role.OPERATOR])
    monkeypatch.setattr("app.ui.pages.run_result.get_current_ctx", lambda: ctx)
    monkeypatch.setattr(
        "app.ui.pages.run_result.upsert_issue_for_row", lambda *a, **kw: ServiceResult(ok=True, data={"issue_id": 1})
    )

    # 1. Test when no click or no meta
    fb, trig = handle_save_issue_from_drawer(None, "OPEN", None, None, None)
    assert trig == 0

    # 2. Test saving with valid meta
    meta = {"run_id": 1042, "row_no": 1}
    fb, trig = handle_save_issue_from_drawer(
        n_clicks=1,
        status_val="IN_PROGRESS",
        reason_code=None,
        note_val="Dang kiem tra chenh lech",
        meta=meta,
    )
    assert trig == 1
    assert "Đã lưu trạng thái đối soát" in str(fb)

    # 3. Test saving with meta as json string
    import json

    meta_str = json.dumps(meta)
    fb, trig = handle_save_issue_from_drawer(
        n_clicks=2,
        status_val="ACCEPTED",
        reason_code=None,
        note_val="Chap nhan lech",
        meta=meta_str,
    )
    assert trig == 2
    assert "Đã lưu trạng thái đối soát" in str(fb)


def test_handle_export_excel(run_result_env, monkeypatch, tmp_path) -> None:
    from app.schemas.errors import ServiceResult
    from app.ui.pages.run_result import handle_export_excel

    dummy_export = tmp_path / "export.xlsx"
    dummy_export.write_text("dummy")

    ctx = Ctx(user_id=1, username="operator", full_name="Operator", roles=[Role.OPERATOR])
    monkeypatch.setattr("app.ui.pages.run_result.get_current_ctx", lambda: ctx)
    monkeypatch.setattr(
        "app.ui.pages.run_result.export_run",
        lambda *a, **kw: ServiceResult(ok=True, data={"export_path": str(dummy_export)}),
    )

    data_store = {"run": {"id": 1042}}
    res = handle_export_excel(1, data_store)
    assert res is not None
    assert "filename" in res
    assert "ReconHub_Run_1042.xlsx" in res["filename"]


def test_handle_row_click_open_drawer(run_result_env: Any, monkeypatch: Any) -> None:
    from app.schemas.errors import ServiceResult
    from app.ui.pages.run_result import handle_row_click_open_drawer

    ctx = Ctx(user_id=1, username="operator", full_name="Operator", roles=[Role.OPERATOR])
    monkeypatch.setattr("app.ui.pages.run_result.get_current_ctx", lambda: ctx)

    mock_row_detail = {
        "run_id": 1042,
        "row_no": 2,
        "key_text": "C26TBD0031312 | 2026-02-01",
        "status": "MATCHED",
        "issue": {"STATUS": "OPEN"},
        "excel": {"TOTAL_AMOUNT": 1390000},
        "db": {"TOTAL_AMOUNT": 1390000},
        "diff": {"TOTAL_AMOUNT": 0},
    }
    monkeypatch.setattr(
        "app.ui.pages.run_result.get_row_detail",
        lambda *a, **kw: ServiceResult(ok=True, data=mock_row_detail),
    )
    monkeypatch.setattr(
        "app.ui.pages.run_result.list_reasons",
        lambda *a, **kw: ServiceResult(ok=True, data=[]),
    )

    data_store = {"run": {"id": 1042}}

    import dash

    monkeypatch.setattr(
        dash,
        "callback_context",
        type("Obj", (), {"triggered": [{"prop_id": '{"index":2,"type":"run-res-row"}.n_clicks', "value": 1}]}),
    )

    opened, drawer_ui = handle_row_click_open_drawer([1], data_store)
    assert opened is True
    assert drawer_ui is not None
    assert "C26TBD0031312" in str(drawer_ui)
