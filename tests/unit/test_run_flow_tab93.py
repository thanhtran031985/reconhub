"""Task 93 — tab "Luồng xử lý" trên trang run.

Test đỏ trước (plan bước 2): tab hiện đúng dữ liệu của run đang mở
(file, bảng, nguồn DB, group_by, measure, CNT_*), không hardcode
BILL_VTOS; run FAILED không summary vẫn render; 2 tab cũ không đổi.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_file,
    recon_result_row,
    recon_run,
    recon_run_summary,
    recon_template,
    recon_template_version,
    recon_user,
)
from app.ui.pages.run_result import (
    _flow_context,
    render_flow_tab_content,
    render_result_grid,
    render_sql_tab_content,
)

RUN_ID = 1040


def _bill_vtos_config() -> dict[str, Any]:
    """Config BILL_VTOS v4 như check-88f, thêm db_source (bảng + nguồn)."""
    _fields = [
        ("STT", "STT", None),
        ("SO_HD", "Số HĐ", "INVOICE_NO"),
        ("NGAY_HD", "Ngày HĐ", "INVOICE_DATE"),
        ("SO_PTC", "Số PTC", None),
        ("SO_LENH", "Số Lệnh", None),
        ("SO_PINCODE", "Số PinCode", None),
        ("TAU_CHUYEN", "Tàu Chuyến", None),
        ("MA_BIEU_CUOC", "Mã Biểu Cước", None),
        ("DIEN_GIAI", "Diễn Giải", None),
        ("HANG_KT", "Hãng KT", None),
        ("KICH_CO", "Kích Cỡ", None),
        ("SO_LUONG", "Số Lượng", None),
        ("THANH_TIEN", "Thành Tiền", None),
        ("CHIET_KHAU", "Chiết Khấu", None),
        ("THUE", "% Thuế", None),
        ("TIEN_THUE", "Tiền Thuế", None),
        ("TONG_TIEN", "Tổng Tiền", None),
        ("LOAI_HD", "Loại HĐ", None),
        ("HTTT", "HTTT", None),
        ("DTTT", "ĐTTT", None),
        ("MST", "MST", None),
        ("LAP_BOI", "Lập Bởi", None),
        ("DEPOT", "Depot", None),
        ("GHI_CHU", "Ghi Chú", None),
    ]
    _num = {"SO_LUONG", "THANH_TIEN", "CHIET_KHAU", "THUE", "TIEN_THUE", "TONG_TIEN"}
    return {
        "fields": [
            {
                "name": n,
                "label": xl,
                "excel": xl,
                "excel_aliases": [],
                "db": db,
                "type": "number" if n in _num else ("datetime" if n == "NGAY_HD" else "text"),
                "norm": [],
            }
            for n, xl, db in _fields
        ],
        "db_source": {
            "kind": "table",
            "table": "DATARAW.FACT_BILL",
            "source_id": "GMD_DEV",
            "filters": [
                {"param": "p_from", "column": "INVOICE_DATE", "op": ">="},
                {"param": "p_to", "column": "INVOICE_DATE", "op": "<="},
                {"param": "p_app", "column": "APP", "op": "="},
                {"param": "p_org", "column": "ORG", "op": "="},
            ],
            "params": [
                {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày", "required": True},
                {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày", "required": True},
                {"name": "p_app", "type": "text", "source": "default", "default": "VTOS", "label": "Ứng dụng"},
                {"name": "p_org", "type": "text", "source": "default", "default": "BDP", "label": "Đơn vị"},
            ],
            "pushdown_aggregate": True,
        },
        "profiles": [
            {
                "code": "BY_INVOICE_VTOS",
                "name": "Theo số hóa đơn",
                "is_default": True,
                "aggregate": True,
                "group_by": ["INVOICE_DATE", "INVOICE_NO"],
                "filters": [],
                "main_measure": "TOTAL_AMOUNT",
                "measures": [
                    {
                        "name": "TOTAL_AMOUNT",
                        "label": "Tổng tiền",
                        "agg": "sum",
                        "field": "TONG_TIEN",
                        "compare": "abs_tol",
                        "tolerance": 1,
                        "round": 0,
                    }
                ],
            }
        ],
    }


def _key_hash(key_text: str) -> str:
    return hashlib.sha256(key_text.encode("utf-8")).hexdigest()


@pytest.fixture
def flow_env(tmp_path, monkeypatch):
    db_file = tmp_path / "flow_tab93_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res_u = conn.execute(
            recon_user.insert().values(
                USERNAME="admin",
                FULL_NAME="Quản trị viên",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        u_id = res_u.inserted_primary_key[0]
        seed_perm_basics(engine, {u_id: ["ADMIN"]}, conn=conn)

        res_ds = conn.execute(
            recon_data_source.insert().values(
                NAME="GMD_DEV",
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
                ORIGINAL_NAME="vtos_2026-07.xlsx",
                SIZE_BYTES=31000,
                SHA256="abc12345",
                STORAGE_PATH="vtos_2026-07.xlsx",
                UPLOADED_BY="admin",
                UPLOADED_AT=now,
            )
        )
        f_id = res_f.inserted_primary_key[0]

        res_t = conn.execute(
            recon_template.insert().values(
                CODE="BILL_VTOS",
                NAME="Doanh thu Vtos",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                ROW_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        tmpl_id = res_t.inserted_primary_key[0]
        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tmpl_id,
                VERSION=1,
                STATUS="ACTIVE",
                CONFIG_JSON=_bill_vtos_config(),
                DATA_SOURCE_ID=ds_id,
                DRY_RUN_OK="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                ACTIVATED_AT=now,
            )
        )

        conn.execute(
            recon_run.insert().values(
                ID=RUN_ID,
                TEMPLATE_ID=tmpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="BY_INVOICE_VTOS",
                DATA_SOURCE_ID=ds_id,
                FILE_ID=f_id,
                SHEET_NAME="Sheet1",
                STATUS="DONE",
                STAGE=5,
                PROGRESS_PCT=100,
                P_FROM=datetime(2026, 7, 1, 0, 0, 0),
                P_TO=datetime(2026, 7, 31, 23, 59, 59),
                CREATED_BY="admin",
                CREATED_AT=now,
                STARTED_AT=now,
                FINISHED_AT=now,
                CHECKED_BY=None,
                CHECKED_AT=None,
                TEMP_PURGED_AT=None,
            )
        )
        conn.execute(
            recon_run_summary.insert().values(
                RUN_ID=RUN_ID,
                EXCEL_ROWS_READ=10749,
                EXCEL_ROWS_OUT_OF_RANGE=0,
                EXCEL_ROWS_INVALID=0,
                EXCEL_GROUPS=6718,
                DB_ROWS=1073,
                DB_GROUPS=1073,
                CNT_MATCHED=604,
                CNT_MISMATCH=0,
                CNT_MISSING_IN_DB=6114,
                CNT_MISSING_IN_EXCEL=469,
                CNT_INCONSISTENT=0,
                CNT_DUPLICATE=0,
                CONTROL_TOTAL_FILE="48165766039",
                CONTROL_TOTAL_CALC="48165766039",
                CONTROL_TOTAL_OK="Y",
                MEASURE_TOTALS_JSON={"TOTAL_AMOUNT": {"excel": 48165766039, "db": 90797240197, "diff": -42631474158}},
                STATUS_AMOUNTS_JSON={},
                COLUMNS_JSON=[],
                DURATION_MS=1000,
            )
        )
        conn.execute(
            recon_result_row.insert().values(
                RUN_ID=RUN_ID,
                ROW_NO=1,
                KEY_TEXT="2026-04-29 11:00:45 | C26TBD0100011",
                KEY_HASH=_key_hash("2026-04-29 11:00:45 | C26TBD0100011"),
                STATUS="MISSING_IN_DB",
                KEY_JSON={"INVOICE_NO": "C26TBD0100011"},
                EXCEL_JSON={"x__TOTAL_AMOUNT": 624500000},
                DB_JSON={"d__TOTAL_AMOUNT": None},
                DIFF_JSON={"diff__TOTAL_AMOUNT": 624500000},
                EXCEL_ROW_NOS="4104,4105",
                ABS_DIFF_MAIN=None,
                ABS_DIFF_SORT=624500000.0,
            )
        )
        conn.execute(
            recon_result_row.insert().values(
                RUN_ID=RUN_ID,
                ROW_NO=2,
                KEY_TEXT="2026-07-01 | C26TBD0157530",
                KEY_HASH=_key_hash("2026-07-01 | C26TBD0157530"),
                STATUS="MATCHED",
                KEY_JSON={"INVOICE_NO": "C26TBD0157530"},
                EXCEL_JSON={"x__TOTAL_AMOUNT": 1620000},
                DB_JSON={"d__TOTAL_AMOUNT": 1620000},
                DIFF_JSON={"diff__TOTAL_AMOUNT": 0},
                EXCEL_ROW_NOS="",
                ABS_DIFF_MAIN=None,
                ABS_DIFF_SORT=0.0,
            )
        )

    ctx = Ctx(user_id=int(u_id), username="admin", full_name="Quản trị viên", roles=[Role.ADMIN])
    return {"engine": engine, "ctx": ctx, "tmpl_id": int(tmpl_id), "ds_id": int(ds_id)}


def _bill_vtos_run_info(**overrides: Any) -> dict[str, Any]:
    run_info: dict[str, Any] = {
        "id": RUN_ID,
        "template_id": 1,
        "template_code": "BILL_VTOS",
        "template_name": "Doanh thu Vtos",
        "template_version": 1,
        "profile_code": "BY_INVOICE_VTOS",
        "status": "DONE",
        "filename": "vtos_2026-07.xlsx",
        "data_source_id": 1,
        "p_from": "2026-07-01T00:00:00",
        "p_to": "2026-07-31T23:59:59",
    }
    run_info.update(overrides)
    return run_info


def _bill_vtos_summary(**overrides: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "EXCEL_ROWS_READ": 10749,
        "EXCEL_GROUPS": 6718,
        "DB_ROWS": 1073,
        "DB_GROUPS": 1073,
        "CNT_MATCHED": 604,
        "CNT_MISMATCH": 0,
        "CNT_MISSING_IN_DB": 6114,
        "CNT_MISSING_IN_EXCEL": 469,
        "CNT_INCONSISTENT": 0,
        "CNT_DUPLICATE": 0,
        "EXCEL_ROWS_INVALID": 0,
        "SOURCE_SQL": "SELECT 1 FROM DUAL",
        "DURATION_MS": 1000,
    }
    summary.update(overrides)
    return summary


def _bill_vtos_flow_ctx() -> dict[str, Any]:
    return {
        "template_code": "BILL_VTOS",
        "template_name": "Doanh thu Vtos",
        "template_version": 1,
        "profile_code": "BY_INVOICE_VTOS",
        "profile_name": "Theo số hóa đơn",
        "db_table": "DATARAW.FACT_BILL",
        "db_source": "GMD_DEV",
        "db_kind": "table",
        "db_sql": None,
        "pushdown": True,
        "group_by": ["INVOICE_DATE", "INVOICE_NO"],
        "measures": [
            {
                "name": "TOTAL_AMOUNT",
                "label": "Tổng tiền",
                "agg": "sum",
                "field": "TONG_TIEN",
                "compare": "abs_tol",
                "tolerance": 1,
                "round": 0,
            }
        ],
        "main_measure": {
            "name": "TOTAL_AMOUNT",
            "label": "Tổng tiền",
            "compare": "abs_tol",
            "tolerance": 1,
            "round": 0,
        },
        "field_count": 24,
        "filter_params": ["p_from", "p_to", "p_app", "p_org"],
    }


def _bill_vtos_rows() -> list[dict[str, Any]]:
    return [
        {
            "row_no": 1,
            "key_text": "2026-04-29 11:00:45 | C26TBD0100011",
            "status": "MISSING_IN_DB",
            "key": {"INVOICE_NO": "C26TBD0100011"},
            "excel": {"x__TOTAL_AMOUNT": 624500000},
            "db": {"d__TOTAL_AMOUNT": None},
            "diff": {"diff__TOTAL_AMOUNT": 624500000},
            "row_nos": "4104,4105",
        },
        {
            "row_no": 2,
            "key_text": "2026-07-01 | C26TBD0157530",
            "status": "MATCHED",
            "key": {"INVOICE_NO": "C26TBD0157530"},
            "excel": {"x__TOTAL_AMOUNT": 1620000},
            "db": {"d__TOTAL_AMOUNT": 1620000},
            "diff": {"diff__TOTAL_AMOUNT": 0},
            "row_nos": "",
        },
    ]


def test_flow_context_bill_vtos(flow_env) -> None:
    """_flow_context trích đúng db_source + profile từ config thật trong DB."""
    run_info = {
        "template_id": flow_env["tmpl_id"],
        "template_version": 1,
        "profile_code": "BY_INVOICE_VTOS",
    }
    fc = _flow_context(flow_env["ctx"], run_info)
    assert fc is not None
    assert fc["db_table"] == "DATARAW.FACT_BILL"
    assert fc["db_source"] == "GMD_DEV"
    assert fc["db_kind"] == "table"
    assert fc["pushdown"] is True
    assert fc["group_by"] == ["INVOICE_DATE", "INVOICE_NO"]
    assert fc["main_measure"]["name"] == "TOTAL_AMOUNT"
    assert fc["main_measure"]["label"] == "Tổng tiền"
    assert fc["main_measure"]["compare"] == "abs_tol"
    assert fc["main_measure"]["tolerance"] == 1
    assert fc["main_measure"]["round"] == 0
    assert fc["field_count"] == 24
    assert fc["profile_code"] == "BY_INVOICE_VTOS"


def test_flow_context_none_when_template_missing(monkeypatch) -> None:
    """Không lấy được config → None (nơi gọi dự phòng '—', không raise)."""
    monkeypatch.setattr(
        "app.ui.pages.run_result.get_template",
        lambda *a, **k: SimpleNamespace(ok=False, data=None),
    )
    ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])
    run_info = {"template_id": 999, "template_version": 1, "profile_code": "X"}
    assert _flow_context(ctx, run_info) is None
    assert _flow_context(None, run_info) is None
    assert _flow_context(ctx, {}) is None


def test_render_flow_tab_bill_vtos() -> None:
    """Tab hiện đúng dữ liệu run BILL_VTOS: file, bảng, nguồn, group_by,
    measure, CNT_*, 4 chặng + 4 thẻ + ô ví dụ + tên hàm xử lý."""
    ui = render_flow_tab_content(_bill_vtos_run_info(), _bill_vtos_summary(), _bill_vtos_rows(), _bill_vtos_flow_ctx())
    s = str(ui)
    assert "vtos_2026-07.xlsx" in s
    assert "DATARAW.FACT_BILL" in s
    assert "GMD_DEV" in s
    assert "INVOICE_DATE" in s
    assert "INVOICE_NO" in s
    assert "TOTAL_AMOUNT" in s
    assert "10.749" in s
    assert "6.718" in s
    assert "1.073" in s
    assert "6.114" in s
    assert "469" in s
    assert "624,500,000" in s
    assert "C26TBD0100011" in s
    assert "Thiếu trong DB" in s
    for stage in ("Nguồn & lấy dữ liệu", "Chuẩn hóa & gộp", "Ghép & kết luận", "Kết quả"):
        assert stage in s, stage
    for fn in (
        "reader.read_sheets",
        "mapping.resolve_columns",
        "sql_builder.build_source_sql",
        "fetch.fetch_df",
        "normalize.normalize",
        "aggregate.aggregate",
        "compare.compare",
        "compare._evaluate_measure",
        "run_executor.execute_run",
        "pipeline.run_pipeline",
    ):
        assert fn in s, fn


def test_render_flow_tab_other_template() -> None:
    """Template khác tên → tab hiện đúng tên/bảng/measure của run đó,
    không dính hardcode BILL_VTOS."""
    flow_ctx = {
        "template_code": "SALES_DAILY",
        "template_name": "Doanh thu ngày",
        "template_version": 2,
        "profile_code": "BY_DAY_STORE",
        "profile_name": "Theo ngày + cửa hàng",
        "db_table": "SALES.FACT_DAILY",
        "db_source": "PROD_DB",
        "db_kind": "table",
        "db_sql": None,
        "pushdown": False,
        "group_by": ["SALE_DATE", "STORE_ID"],
        "measures": [
            {
                "name": "AMOUNT_TOTAL",
                "label": "Tổng doanh thu",
                "agg": "sum",
                "field": "AMOUNT",
                "compare": "exact",
                "tolerance": None,
                "round": 0,
            }
        ],
        "main_measure": {
            "name": "AMOUNT_TOTAL",
            "label": "Tổng doanh thu",
            "compare": "exact",
            "tolerance": None,
            "round": 0,
        },
        "field_count": 5,
        "filter_params": ["p_from", "p_to"],
    }
    run_info = _bill_vtos_run_info(
        template_code="SALES_DAILY",
        template_name="Doanh thu ngày",
        template_version=2,
        profile_code="BY_DAY_STORE",
        filename="sales_2026-07.xlsx",
    )
    rows = [
        {
            "row_no": 1,
            "key_text": "2026-07-01 | STORE_01",
            "status": "MATCHED",
            "key": {"STORE_ID": "STORE_01"},
            "excel": {"x__AMOUNT_TOTAL": 5000000},
            "db": {"d__AMOUNT_TOTAL": 5000000},
            "diff": {"diff__AMOUNT_TOTAL": 0},
            "row_nos": "",
        }
    ]
    ui = render_flow_tab_content(run_info, _bill_vtos_summary(), rows, flow_ctx)
    s = str(ui)
    assert "sales_2026-07.xlsx" in s
    assert "SALES.FACT_DAILY" in s
    assert "PROD_DB" in s
    assert "SALE_DATE" in s
    assert "STORE_ID" in s
    assert "AMOUNT_TOTAL" in s
    assert "5,000,000" in s
    assert "BILL_VTOS" not in s
    assert "FACT_BILL" not in s
    assert "TOTAL_AMOUNT" not in s
    assert "GMD_DEV" not in s


def test_render_flow_tab_failed_no_summary() -> None:
    """Run FAILED không có summary: tab vẫn render, số thiếu hiện '—',
    có alert lỗi (như tab SQL)."""
    run_info = _bill_vtos_run_info(
        status="FAILED",
        error_msg="Lỗi kết nối Oracle",
        filename="vtos_2026-07.xlsx",
    )
    ui = render_flow_tab_content(run_info, {}, [], None)
    s = str(ui)
    assert "Lỗi kết nối Oracle" in s
    assert "—" in s


def test_render_flow_tab_empty_rows_hides_example() -> None:
    """Không có dòng kết quả thì ẩn ô ví dụ (không hiện 'Ví dụ')."""
    ui = render_flow_tab_content(_bill_vtos_run_info(), _bill_vtos_summary(), [], _bill_vtos_flow_ctx())
    s = str(ui)
    assert "Ví dụ" not in s
    # Sơ đồ và thẻ bước vẫn hiện.
    assert "Chuẩn hóa & gộp" in s


def test_regression_old_tabs_unchanged() -> None:
    """Hồi quy D10: tab SQL + grid cũ render như trước, không đổi."""
    run_info = _bill_vtos_run_info()
    summary = _bill_vtos_summary()
    sql_ui = render_sql_tab_content(run_info, summary)
    s = str(sql_ui)
    assert "Câu lệnh SQL đối soát DB (Oracle)" in s
    assert "Tham số ràng buộc" in s
    grid_ui = render_result_grid(
        measures=[{"name": "TOTAL_AMOUNT", "label": "Tổng tiền", "type": "number"}],
        rows=_bill_vtos_rows(),
    )
    assert "C26TBD0100011" in str(grid_ui)


def test_layout_has_flow_tab(flow_env, monkeypatch) -> None:
    """layout() có tab 'Luồng xử lý' với nội dung từ config thật của run,
    2 tab cũ vẫn hiện."""
    from app.ui.pages.run_result import layout

    monkeypatch.setattr("app.ui.pages.run_result.get_current_ctx", lambda: flow_env["ctx"])
    page_ui = layout(run_id=RUN_ID)
    assert page_ui is not None
    s = str(page_ui)
    assert "Luồng xử lý" in s
    assert "DATARAW.FACT_BILL" in s
    assert "GMD_DEV" in s
    assert "Kết quả đối soát" in s
    assert "Câu lệnh SQL đối soát DB" in s
