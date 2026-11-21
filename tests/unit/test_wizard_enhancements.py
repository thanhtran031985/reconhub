"""Unit tests for Template Wizard enhancements:
1. Step 2: Re-suggest missing columns from sample file
2. Step 2: Add derived field modal & submission
3. Step 3: 3-card layout & double-click column chip to insert into SELECT
4. Step 4: 3-card layout (Trường có sẵn, Thông tin Profile, SQL gộp sinh tự động)
"""

import time
from unittest.mock import MagicMock

import dash
import pytest

from app.ui.pages.template_wizard import (
    handle_double_click_db_column,
    handle_re_suggest_fields,
    handle_submit_derived_field,
    handle_toggle_derived_modal,
    render_step_3,
    render_step_4,
)


def test_toggle_derived_modal_requires_clicks(monkeypatch):
    """Modal không được tự bật khi chưa bấm nút (open_clicks is None/0)."""
    ctx_mock = MagicMock()
    ctx_mock.triggered = [{"prop_id": "wizard-add-derived-btn.n_clicks", "value": None}]
    monkeypatch.setattr("dash.callback_context", ctx_mock)

    with pytest.raises(dash.exceptions.PreventUpdate):
        handle_toggle_derived_modal(None, None, False)

    with pytest.raises(dash.exceptions.PreventUpdate):
        handle_toggle_derived_modal(0, None, False)


def test_toggle_derived_modal_opens_on_click(monkeypatch):
    """Khi bấm nút wizard-add-derived-btn (open_clicks=1), modal mở."""
    ctx_mock = MagicMock()
    ctx_mock.triggered = [{"prop_id": "wizard-add-derived-btn.n_clicks", "value": 1}]
    monkeypatch.setattr("dash.callback_context", ctx_mock)

    opened, name, label, args = handle_toggle_derived_modal(1, None, False)
    assert opened is True
    assert name == ""


def test_submit_derived_field():
    """Thêm trường dẫn xuất hợp lệ vào config."""
    cfg = {"fields": [], "derived": []}
    new_cfg, is_opened, step2_ui, notif = handle_submit_derived_field(
        1,
        "NAM_THANG",
        "Năm tháng",
        "text",
        "FORMAT_DATE",
        "INV_DATE, YYYY-MM",
        cfg,
    )
    assert is_opened is False
    assert len(new_cfg["derived"]) == 1
    d = new_cfg["derived"][0]
    assert d["name"] == "NAM_THANG"
    assert d["label"] == "Năm tháng"
    assert d["expr"]["fn"] == "FORMAT_DATE"
    assert "INV_DATE" in d["expr"]["args"]


def test_re_suggest_fields():
    """Gợi ý lại bổ sung các cột còn thiếu từ sample file mà vẫn giữ cấu hình cũ."""
    existing_cfg = {
        "fields": [{"name": "INVOICE_NO", "label": "Số HĐ", "excel": "Số hóa đơn", "type": "text", "db": "INVOICE_NO"}],
        "derived": [],
    }
    sample_data = {
        "columns": [
            {"name": "Số hóa đơn", "suggested_field_name": "INVOICE_NO", "suggested_type": "text"},
            {"name": "Mã giao dịch", "suggested_field_name": "MA_GIAO_DICH", "suggested_type": "text"},
            {"name": "Thành tiền", "suggested_field_name": "TOTAL_AMOUNT", "suggested_type": "number"},
        ]
    }

    new_cfg, step2_ui, notif = handle_re_suggest_fields(1, existing_cfg, sample_data, None)
    fields = new_cfg["fields"]
    # Vẫn giữ INVOICE_NO cũ (với label Số HĐ)
    assert fields[0]["name"] == "INVOICE_NO"
    assert fields[0]["label"] == "Số HĐ"
    # Bổ sung thêm 2 cột mới từ sample file
    assert len(fields) == 3
    field_names = [f["name"] for f in fields]
    assert "MA_GIAO_DICH" in field_names
    assert "TOTAL_AMOUNT" in field_names


def test_double_click_db_column_inserts_into_sql(monkeypatch):
    """Nhấp đúp vào chip cột DB chèn tên cột vào mệnh đề SELECT của câu SQL, đổi màu chip và không bắn toast message."""
    ctx_mock = MagicMock()
    ctx_mock.triggered = [{"prop_id": '{"col":"STT","type":"wizard-db-col-chip"}.n_clicks', "value": 2}]
    monkeypatch.setattr("dash.callback_context", ctx_mock)

    # Lần click thứ 2 ngay sau lần 1 (cách nhau 0.1s)
    click_store = {"STT": time.time() - 0.1}
    current_sql = "SELECT\n    INVOICE_NO\nFROM DATARAW.FACT_BILL\nWHERE 1=1"
    current_cfg = {
        "db_source": {
            "table": "FACT_BILL",
            "sql": current_sql,
            "_columns": [("INVOICE_NO", "VARCHAR2"), ("STT", "NUMBER")],
        },
        "fields": [],
    }

    new_sql, cfg, updated_store, notif, gen_sql_ui, chips_ui, mapping_ui = handle_double_click_db_column(
        [2], current_sql, current_cfg, click_store, "sql"
    )

    assert "STT" in new_sql
    assert "SELECT" in new_sql
    assert "FROM DATARAW.FACT_BILL" in new_sql
    # Cột STT phải nằm trước FROM
    from_idx = new_sql.find("FROM")
    stt_idx = new_sql.find("STT")
    assert stt_idx < from_idx

    # Đã bỏ message toast notification
    assert notif is dash.no_update

    # Chips UI được render lại và cột STT đổi sang màu blue / variant filled
    chips_str = str(chips_ui)
    assert "STT" in chips_str
    assert "blue" in chips_str


def test_render_step_3_three_card_layout():
    """Bước 3 hiển thị 3 card bằng nhau, bỏ title Câu lệnh SQL, ẩn Data Source/Cách khai báo/Đẩy phép gộp."""
    cfg = {
        "db_source": {
            "source_id": "GMD_DEV",
            "kind": "table",
            "table": "FACT_BILL",
            "filters": [],
            "_columns": [("INVOICE_NO", "VARCHAR2"), ("INV_DATE", "DATE")],
        },
        "fields": [],
    }
    ui = render_step_3(cfg)
    ui_str = str(ui)
    # Không còn tiêu đề "Câu lệnh SQL" (thay bằng trực tiếp khối Bảng/View hoặc SQL chi tiết)
    assert "Title(children='Câu lệnh SQL'" not in ui_str
    assert "Cột bảng nguồn" in ui_str
    assert "Điều kiện lọc theo tham số" in ui_str
    assert "Mapping DB — Trường logic" in ui_str


def test_step3_tab_switch_no_toast_notification(monkeypatch):
    """Khi chuyển tab sang Bước 3 (trigger là wizard-input-table mount hoặc fetch button mount với n_clicks=None), không bắn notification Đã tải thành công cột."""
    from app.ui.pages.template_wizard import handle_select_or_fetch_table

    ctx_mock = MagicMock()
    ctx_mock.triggered = [{"prop_id": "wizard-input-table.value", "value": "DATARAW.FACT_BILL"}]
    monkeypatch.setattr("dash.callback_context", ctx_mock)

    # Mock get_current_ctx và describe_source
    mock_ctx = MagicMock()
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: mock_ctx)
    monkeypatch.setattr("app.ui.pages.template_wizard._resolve_ds_id_and_schema", lambda ctx, ds: (1, "DATARAW"))

    from app.schemas.errors import ServiceResult
    monkeypatch.setattr(
        "app.ui.pages.template_wizard.describe_source",
        lambda *args, **kwargs: ServiceResult(ok=True, data=[{"name": "COL1", "data_type": "VARCHAR2"}]),
    )

    cfg = {"db_source": {"table": "DATARAW.FACT_BILL"}, "fields": []}
    chips_ui, mapping_ui, filters_ui, gen_sql_ui, succ_alert, new_cfg = handle_select_or_fetch_table(
        "DATARAW.FACT_BILL", None, "GMD_DEV", cfg
    )

    # succ_alert phải là None khi chuyển tab
    assert succ_alert is None

    # Khi nút fetch mount lần đầu với n_clicks=None trong triggered, succ_alert vẫn phải là None
    ctx_mock.triggered = [{"prop_id": "wizard-fetch-table-cols-btn.n_clicks", "value": None}]
    _, _, _, _, succ_alert_mount, _ = handle_select_or_fetch_table(
        "DATARAW.FACT_BILL", None, "GMD_DEV", cfg
    )
    assert succ_alert_mount is None

    # Nhưng khi trigger là wizard-fetch-table-cols-btn (bấm nút tay, _fetch_clicks > 0), succ_alert phải có
    ctx_mock.triggered = [{"prop_id": "wizard-fetch-table-cols-btn.n_clicks", "value": 1}]
    _, _, _, _, succ_alert_manual, _ = handle_select_or_fetch_table(
        "DATARAW.FACT_BILL", 1, "GMD_DEV", cfg
    )
    assert succ_alert_manual is not None
    assert "Đã tải thành công 1 cột" in str(succ_alert_manual)


def test_render_step_4_three_card_layout():
    """Bước 4 hiển thị đúng 3 card đều nhau và đã bỏ alert dòng Excel -> nhóm."""
    cfg = {
        "fields": [
            {"name": "INVOICE_NO", "label": "Số hóa đơn", "excel": "Số hóa đơn", "db": "INVOICE_NO", "type": "text"}
        ],
        "derived": [],
        "profiles": [
            {
                "code": "BY_INVOICE",
                "name": "Theo hóa đơn",
                "group_by": ["INVOICE_NO"],
                "measures": [{"field": "*", "fn": "COUNT"}],
            }
        ],
    }
    ui = render_step_4(cfg)
    ui_str = str(ui)
    assert "Trường có sẵn" in ui_str
    assert "Thông tin Profile" in ui_str
    assert "SQL gộp sinh tự động (chỉ đọc)" in ui_str
    # Không còn alert số dòng Excel -> số nhóm
    assert "dòng Excel →" not in ui_str


def test_form_state_to_config_auto_maps_group_by_sql_col():
    """Kiểm tra form_state_to_config tự động map cột DB cho trường group_by khi trường đó có trong câu lệnh SQL."""
    from app.ui.pages.template_wizard import form_state_to_config

    form_data = {
        "file": {"sheet": "Sheet1", "header_row": 1, "data_start_row": 2},
        "fields": [
            {"name": "INVOICE_NO", "label": "Số HĐ", "excel": "Số hóa đơn", "db": "INVOICE_NO", "type": "text"},
            {"name": "CONT_OPR_CODE", "label": "Hãng tàu", "excel": "Hãng tàu", "db": None, "type": "text"},
        ],
        "derived": [],
        "db_source": {
            "kind": "sql",
            "source_id": "GMD_DEV",
            "table": "DATARAW.FACT_BILL",
            "sql": "SELECT INVOICE_NO, CONT_OPR_CODE FROM DATARAW.FACT_BILL WHERE 1=1",
            "filters": [],
            "params": [
                {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày", "required": True},
                {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày", "required": True},
            ],
        },
        "profiles": [
            {
                "code": "BY_INVOICE",
                "name": "Theo số hóa đơn",
                "is_default": True,
                "group_by": ["INVOICE_NO"],
                "measures": [{"name": "COUNT_ROWS", "label": "Số dòng", "agg": "count", "field": None}],
            },
            {
                "code": "BY_CONT_OPR",
                "name": "Theo hãng tàu",
                "is_default": False,
                "group_by": ["CONT_OPR_CODE"],
                "measures": [{"name": "COUNT_ROWS", "label": "Số dòng", "agg": "count", "field": None}],
            },
        ],
    }

    cfg, errors = form_state_to_config(form_data)
    # Phải thành công và không bị lỗi 'Trường group_by CONT_OPR_CODE không có cột tương ứng phía DB'
    assert cfg is not None
    assert errors == {}
    cont_f = next(f for f in cfg.fields if f.name == "CONT_OPR_CODE")
    assert cont_f.db == "CONT_OPR_CODE"


def test_handle_check_custom_sql_fetches_source_table_columns(monkeypatch):
    """Khi bấm Kiểm tra & lấy cột, lấy toàn bộ cột của bảng nguồn từ Oracle và map các cột trong SELECT."""
    from app.schemas.errors import ServiceResult
    from app.ui.pages.template_wizard import handle_check_custom_sql

    ctx_mock = MagicMock()
    ctx_mock.triggered = [{"prop_id": "wizard-check-sql-btn.n_clicks", "value": 1}]
    monkeypatch.setattr("dash.callback_context", ctx_mock)
    mock_ctx = MagicMock()
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: mock_ctx)
    monkeypatch.setattr("app.ui.pages.template_wizard._resolve_ds_id_and_schema", lambda ctx, ds: (1, "DATARAW"))

    # Mock describe_source: khi sql thì trả 2 cột, khi table_name thì trả 119 cột
    def mock_describe_source(*args, **kwargs):
        if kwargs.get("sql"):
            return ServiceResult(
                ok=True,
                data=[{"name": "INVOICE_NO", "data_type": "VARCHAR2"}, {"name": "CONT_OPR_CODE", "data_type": "VARCHAR2"}],
            )
        if kwargs.get("table_name"):
            return ServiceResult(
                ok=True,
                data=[
                    {"name": "INVOICE_NO", "data_type": "VARCHAR2"},
                    {"name": "CONT_OPR_CODE", "data_type": "VARCHAR2"},
                    {"name": "EXTRA_COL_3", "data_type": "DATE"},
                ],
            )
        return ServiceResult(ok=False, message="Not found")

    monkeypatch.setattr("app.ui.pages.template_wizard.describe_source", mock_describe_source)

    valid_sql = "SELECT INVOICE_NO, CONT_OPR_CODE FROM DATARAW.FACT_BILL WHERE INVOICE_DATE >= :p_from AND INVOICE_DATE <= :p_to"
    cfg = {
        "db_source": {
            "table": "DATARAW.FACT_BILL",
            "sql": valid_sql,
        },
        "fields": [{"name": "CONT_OPR_CODE", "excel": "Hãng tàu", "db": None}],
    }

    succ_alert, chips_ui, mapping_ui, filters_ui, new_cfg = handle_check_custom_sql(
        1, valid_sql, "GMD_DEV", cfg
    )

    assert "Đã tải 3 cột từ bảng 'DATARAW.FACT_BILL' trên Oracle" in str(succ_alert)
    # CONT_OPR_CODE phải được tự động gán db
    cont_field = next(f for f in new_cfg["fields"] if f["name"] == "CONT_OPR_CODE")
    assert cont_field["db"] == "CONT_OPR_CODE"


def test_render_split_db_mapping_cards():
    """Bảng ánh xạ Cột DB -> Trường logic được chia đều thành 2 card (mỗi card có số trường/cột bằng nhau)."""
    from app.ui.pages.template_wizard import _render_split_db_mapping_cards

    fields = [
        {"name": f"FIELD_{i}", "label": f"Field {i}", "excel": f"COL_{i}", "db": f"COL_{i}"}
        for i in range(1, 9)  # 8 trường
    ]
    db_cols_chips = [(f"COL_{i}", "VARCHAR2") for i in range(1, 9)]

    ui = _render_split_db_mapping_cards(fields, db_cols_chips)
    ui_str = str(ui)

    assert "Cột DB → Trường logic (1)" in ui_str
    assert "Cột DB → Trường logic (2)" in ui_str
    assert "4 trường" in ui_str  # Cả 2 card đều có badge 4 trường (8 / 2 = 4)


def test_extract_sql_select_columns_list():
    """Kiểm tra trích xuất chính xác danh sách cột trong mệnh đề SELECT."""
    from app.ui.pages.template_wizard import _extract_sql_select_columns_list

    sql_1 = """SELECT INVOICE_NO, INVOICE_DATE,
TOTAL_AMOUNT, PTNR_CODE, org_code,
CONT_OPR_CODE
FROM DATARAW.FACT_BILL
WHERE INVOICE_DATE >= :p_from"""
    cols_1 = _extract_sql_select_columns_list(sql_1)
    assert cols_1 == ["INVOICE_NO", "INVOICE_DATE", "TOTAL_AMOUNT", "PTNR_CODE", "org_code", "CONT_OPR_CODE"]

    sql_2 = "SELECT f.INVOICE_NO, TO_CHAR(f.INVOICE_DATE, 'YYYY-MM-DD') AS INV_DATE, \"TOTAL_AMOUNT\" FROM TBL f"
    cols_2 = _extract_sql_select_columns_list(sql_2)
    assert cols_2 == ["INVOICE_NO", "INV_DATE", "TOTAL_AMOUNT"]


def test_db_mapping_table_options_limited_to_sql():
    """Chỗ chọn cột DB trong Mapping DB - Trường logic giới hạn lấy các cột trong câu SQL, không lấy hết bảng nguồn."""
    from app.ui.pages.template_wizard import _render_db_mapping_table

    # Giả lập bảng nguồn có 10 cột
    db_cols_chips = [(f"COL_{i}", "VARCHAR2") for i in range(1, 11)]

    fields = [
        {"name": "SO_HD", "label": "Số HĐ", "excel": "Số HĐ", "db": "COL_1"},
        {"name": "NGAY_HD", "label": "Ngày HĐ", "excel": "Ngày HĐ", "db": None},
    ]

    # 1. Khi có câu SQL chỉ select COL_1 và COL_2:
    sql_text = "SELECT COL_1, COL_2 FROM DATARAW.FACT_BILL WHERE 1=1"
    table_ui = _render_db_mapping_table(fields, db_cols_chips, sql_text=sql_text)

    # Tìm Select component trong hàng của NGAY_HD
    tbody = table_ui.children[1]  # html.Tbody
    rows = tbody.children
    select_comp = rows[1].children[1].children  # td 1 -> dmc.Select
    opts = select_comp.data
    opt_values = [o["value"] for o in opts]

    # Chỉ có COL_1, COL_2 và "— Không có —", KHÔNG có COL_3 .. COL_10
    assert "COL_1" in opt_values
    assert "COL_2" in opt_values
    assert "— Không có —" in opt_values
    assert "COL_3" not in opt_values
    assert "COL_10" not in opt_values
    # Không có giá trị trùng lặp
    assert len(opt_values) == len(set(opt_values))


def test_step4_groupby_and_measures_options_deduplicated():
    """Bước 4 Profile so sánh: không bị lỗi duplicate options khi nhiều trường logic map cùng 1 cột DB."""
    from app.ui.pages.template_wizard import _render_measures_table, _render_step_4_right_panel

    config = {
        "fields": [
            {"name": "SO_HD", "label": "Số HĐ", "excel": "Số HĐ", "db": "INVOICE_NO", "type": "text"},
            {"name": "NGAY_HD", "label": "Ngày HĐ", "excel": "Ngày HĐ", "db": "INVOICE_DATE", "type": "date"},
            {"name": "INVOICE_DATE", "label": "INVOICE_DATE", "excel": "INVOICE_DATE", "db": "INVOICE_DATE", "type": "date"},
            {"name": "TONG_TIEN", "label": "Tổng tiền", "excel": "Tổng tiền", "db": "TOTAL_AMOUNT", "type": "number"},
        ],
        "derived": [],
        "profiles": [
            {
                "code": "BY_INVOICE",
                "name": "Theo số hóa đơn",
                "is_default": True,
                "group_by": ["INVOICE_DATE", "INVOICE_NO"],
                "measures": [
                    {"name": "M_1", "label": "Tổng tiền", "agg": "sum", "field": "TONG_TIEN", "compare": "exact"}
                ],
            }
        ],
    }

    active_prof = config["profiles"][0]
    avail_field_names = ["SO_HD", "NGAY_HD", "INVOICE_DATE", "TONG_TIEN"]

    panel_ui = _render_step_4_right_panel(active_prof, avail_field_names, config)

    # Lấy MultiSelect wizard-groupby-select
    multiselect = panel_ui.children[0].children.children[1].children[2]
    assert getattr(multiselect, "id", None) == "wizard-groupby-select"

    data_options = multiselect.data
    values = [o["value"] for o in data_options]

    # Kiểm tra tuyệt đối không có option nào bị duplicate
    assert len(values) == len(set(values)), f"Duplicate options detected: {values}"
    assert values.count("INVOICE_DATE") == 1

    # Kiểm tra _render_measures_table cũng không có duplicate fields
    measures_table_ui = _render_measures_table(active_prof["measures"], avail_field_names, "M_1")
    assert measures_table_ui is not None


def test_cleanup_phantom_db_fields_and_no_append():
    """Kiểm tra trường logic bắt nguồn từ Excel ở Bước 2, không tự ý chèn cột DB làm trường logic mới."""
    from app.ui.pages.template_wizard import _cleanup_phantom_db_fields

    fields_with_phantoms = [
        {"name": "SO_HD", "label": "Số HĐ", "excel": "Số HĐ", "db": "INVOICE_NO"},
        {"name": "NGAY_HD", "label": "Ngày HĐ", "excel": "Ngày HĐ", "db": "INVOICE_DATE"},
        {"name": "HANG_KT", "label": "Hãng KT", "excel": "Hãng KT", "db": "CONT_OPR_CODE"},
        # 4 trường ma bị chèn từ DB
        {"name": "INVOICE_NO", "label": "INVOICE_NO", "excel": "INVOICE_NO", "db": "INVOICE_NO"},
        {"name": "INVOICE_DATE", "label": "INVOICE_DATE", "excel": "INVOICE_DATE", "db": "INVOICE_DATE"},
        {"name": "CONT_OPR_CODE", "label": "CONT_OPR_CODE", "excel": "CONT_OPR_CODE", "db": "CONT_OPR_CODE"},
        {"name": "TRANSACTION_DATE", "label": "TRANSACTION_DATE", "excel": None, "db": "TRANSACTION_DATE"},
    ]

    cleaned = _cleanup_phantom_db_fields(fields_with_phantoms)
    cleaned_names = [f["name"] for f in cleaned]

    # Các trường ma phải bị loại bỏ hoàn toàn
    assert "INVOICE_NO" not in cleaned_names
    assert "INVOICE_DATE" not in cleaned_names
    assert "CONT_OPR_CODE" not in cleaned_names
    assert "TRANSACTION_DATE" not in cleaned_names

    # Các trường logic gốc từ Excel được giữ nguyên
    assert "SO_HD" in cleaned_names
    assert "NGAY_HD" in cleaned_names
    assert "HANG_KT" in cleaned_names
    assert len(cleaned) == 3


def test_step4_card1_reduced_span_and_scroll():
    """Card 1 ở Bước 4 giảm span còn 3 (tức ~2/3 trước), có scroll khi nhiều trường."""
    cfg = {
        "fields": [
            {"name": f"FIELD_{i}", "label": f"Field {i}", "excel": f"Col_{i}", "db": f"DB_{i}", "type": "text"}
            for i in range(20)
        ],
        "derived": [],
        "profiles": [
            {
                "code": "PROF_1",
                "name": "Profile 1",
                "group_by": ["DB_0"],
                "measures": [{"name": "M_1", "field": "DB_1", "agg": "count"}],
            }
        ],
    }
    ui = render_step_4(cfg)
    grid = ui.children[1]
    card1_col = grid.children[0]
    right_col = grid.children[1]

    assert card1_col.span == {"base": 12, "lg": 3}
    assert right_col.span == {"base": 12, "lg": 9}

    # Card 1 container có overflowY auto
    left_fields_div = card1_col.children.children[2]
    assert left_fields_div.style.get("overflowY") == "auto"
    assert "maxHeight" in left_fields_div.style


def test_table_compact_paddings():
    """Bảng Bước 2, Bước 3, Bước 4 dùng padding tinh gọn (<= 6px)."""
    from app.ui.pages.template_wizard import _render_db_mapping_table, _render_measures_table, render_step_2

    cfg = {
        "fields": [
            {"name": "SO_HD", "label": "Số HĐ", "excel": "Số HĐ", "db": "INVOICE_NO", "type": "text"}
        ],
        "derived": [],
        "profiles": [],
    }
    step2_ui = render_step_2(cfg)
    # Thead Th padding
    table = step2_ui.children[1].children
    th0 = table.children[0].children.children[0]
    assert th0.style.get("padding") == "6px 6px"

    # Step 3 table
    step3_ui = _render_db_mapping_table(cfg["fields"], [("INVOICE_NO", "VARCHAR2")])
    th3 = step3_ui.children[0].children.children[0]
    assert th3.style.get("padding") == "6px 6px"

    # Step 4 measures table
    step4_ui = _render_measures_table([{"name": "M1", "field": "SO_HD", "agg": "sum"}], ["SO_HD"])
    th4 = step4_ui.children.children[0].children.children[0]
    assert th4.style.get("padding") == "4px 4px"


def test_pipeline_header_row_auto_fallback():
    """Pipeline tự động khôi phục header_row khi cấu hình template bị lệch với file Excel."""
    from pathlib import Path

    from app.engine.pipeline import run_pipeline
    from app.schemas.template_config import TemplateConfig

    excel_file = Path("storage/files/6aa0b757b953c6c5286cbfc30e246f50edcc8a157c0c2592d226060679127910.xlsx")
    if not excel_file.exists():
        pytest.skip("Test sample file not found")

    cfg_dict = {
        "schema_version": 1,
        "template_code": "TEST_VTOS",
        "name": "Test VTOS",
        "file": {
            "sheet": "Sheet1",
            "header_row": 1,  # Cố tình đặt 1 trong khi file có header ở dòng 2
            "data_start_row": 2,
            "skip_footer_rows": 0,
            "detect_by_headers": ["STT"],
            "row_filters": {"drop_if": [], "keep_if": []},
            "thousand_sep": ",",
            "decimal_sep": ".",
        },
        "fields": [
            {"name": "SO_HD", "label": "Số HĐ", "excel": "Số HĐ", "db": "INVOICE_NO", "type": "text"},
            {"name": "NGAY_HD", "label": "Ngày HĐ", "excel": "Ngày HĐ", "db": "INVOICE_DATE", "type": "datetime"},
            {"name": "TONG_TIEN", "label": "Tổng Tiền", "excel": "Tổng Tiền", "db": "TOTAL_AMOUNT", "type": "number"},
        ],
        "derived": [],
        "db_source": {
            "kind": "table",
            "table": "DATARAW.FACT_BILL",
            "filters": [
                {"param": "p_from", "column": "INVOICE_DATE", "op": ">=", "cast": "none"},
                {"param": "p_to", "column": "INVOICE_DATE", "op": "<=", "cast": "none"},
            ],
            "params": [
                {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ", "required": True},
                {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến", "required": True},
            ],
        },
        "profiles": [
            {
                "code": "BY_INVOICE",
                "name": "Theo hóa đơn",
                "is_default": True,
                "group_by": ["INVOICE_NO"],
                "measures": [{"name": "M_TOTAL", "label": "Tổng", "agg": "sum", "field": "TONG_TIEN", "compare": "exact"}],
            }
        ],
    }
    tmpl_cfg = TemplateConfig(**cfg_dict)

    # Mock DB fetcher
    mock_fetcher = MagicMock()
    import polars as pl
    mock_fetcher.return_value = pl.DataFrame({
        "K__INVOICE_NO": ["C26TBD0186517"],
        "M__TOTAL": [100000.0],
    })

    res = run_pipeline(
        excel_path=excel_file,
        config=tmpl_cfg,
        params={"p_from": "2026-07-01 00:00:00", "p_to": "2026-08-01 00:00:00"},
        fetcher=mock_fetcher,
    )
    assert res.result_df is not None
    assert len(res.result_df) > 0




