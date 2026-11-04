from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.context import Ctx, Role
from app.db.metadata import metadata, recon_user, recon_user_role
from app.schemas.template_config import TemplateConfig
from app.ui.pages.template_wizard import (
    config_to_form_state,
    form_state_to_config,
    layout,
)

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def load_sample_config() -> TemplateConfig:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TemplateConfig.model_validate(data)


@pytest.fixture
def wizard_env(monkeypatch, tmp_path):
    db_file = tmp_path / "wizard_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                ID=1,
                USERNAME="owner",
                FULL_NAME="Template Owner",
                EMAIL="owner@reconhub.vn",
                PASSWORD_HASH=hash_password("owner123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=1,
                ROLE="TEMPLATE_OWNER",
                CREATED_AT=now,
            )
        )

    return db_url


def test_config_to_form_state_and_reverse() -> None:
    cfg = load_sample_config()
    form_state = config_to_form_state(cfg)

    assert form_state is not None
    assert len(form_state["fields"]) == len(cfg.fields)
    assert form_state["db_source"]["table"] == "RECON_SRC.SRC_FACT_INVOICE_DTP"
    assert len(form_state["profiles"]) == len(cfg.profiles)

    # Convert back to TemplateConfig
    reconstructed_cfg, errors = form_state_to_config(form_state)
    assert errors == {}
    assert reconstructed_cfg is not None
    assert reconstructed_cfg.schema_version == cfg.schema_version
    assert len(reconstructed_cfg.fields) == len(cfg.fields)
    assert len(reconstructed_cfg.profiles) == len(cfg.profiles)


def test_validation_errors_mapped_to_form_fields() -> None:
    cfg = load_sample_config()
    form_state = config_to_form_state(cfg)

    # Cố tình gây lỗi tên trường không đúng định dạng
    form_state["fields"][0]["name"] = "123_invalid-name!"

    _, errors = form_state_to_config(form_state)
    assert len(errors) > 0
    # Lỗi phải trỏ tới path trường bị lỗi
    matched_key = any("fields" in k and "name" in k for k in errors.keys())
    assert matched_key or any("fields" in k for k in errors.keys())


def test_template_wizard_layout_renders_for_owner(wizard_env, monkeypatch) -> None:
    owner_ctx = Ctx(user_id=1, username="owner", full_name="Template Owner", roles=[Role.TEMPLATE_OWNER])
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: owner_ctx)

    content = layout()
    assert content is not None
    s = str(content)
    assert "wizard-page-root" in s
    assert "wizard-view-tabs" in s
    assert "wizard-stepper" in s
    assert "wizard-prev-btn" in s
    assert "wizard-save-draft-btn" in s
    assert "wizard-next-btn" in s


def test_template_wizard_forbidden_for_viewer(wizard_env, monkeypatch) -> None:
    viewer_ctx = Ctx(user_id=2, username="viewer", full_name="Viewer", roles=[Role.VIEWER])
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: viewer_ctx)

    content = layout()
    s = str(content)
    assert "/forbidden" in s or "Không có quyền" in s or "dcc.Location" in s


def test_render_step_1_and_step_2(wizard_env, monkeypatch) -> None:
    from app.ui.pages.template_wizard import render_step_1, render_step_2

    cfg = load_sample_config()
    form_state = config_to_form_state(cfg)

    # Step 1 render
    step1_ui = render_step_1(form_state)
    assert step1_ui is not None
    s1 = str(step1_ui)
    assert "File mẫu" in s1
    assert "Hệ thống phát hiện" in s1
    assert "Xem trước 5 dòng" in s1

    # Step 2 render
    step2_ui = render_step_2(form_state)
    assert step2_ui is not None
    s2 = str(step2_ui)
    assert "Cột Excel → Trường logic" in s2
    assert "INVOICE_NO" in s2
    assert "Gợi ý lại" in s2


def test_render_step_3_db_source(wizard_env, monkeypatch) -> None:
    from app.ui.pages.template_wizard import render_step_3

    cfg = load_sample_config()
    form_state = config_to_form_state(cfg)

    step3_ui = render_step_3(form_state)
    assert step3_ui is not None
    s3 = str(step3_ui)
    assert "Nguồn dữ liệu DB" in s3
    assert "Bảng/View nguồn" in s3
    assert "Điều kiện lọc theo tham số" in s3
    assert "Câu SELECT sinh ra" in s3
    assert "Cột DB → Trường logic" in s3
    assert "Lọc dữ liệu Excel theo cùng khoảng" in s3


def test_render_step_4_profiles_and_measures(wizard_env, monkeypatch) -> None:
    from app.ui.pages.template_wizard import render_step_4

    cfg = load_sample_config()
    form_state = config_to_form_state(cfg)

    step4_ui = render_step_4(form_state)
    assert step4_ui is not None
    s4 = str(step4_ui)
    assert "Trường có sẵn" in s4
    assert "Group by" in s4
    assert "Measures và quy tắc so sánh" in s4
    assert "TOTAL_AMOUNT" in s4
    assert "SQL gộp sinh tự động" in s4


def test_render_step_5_dry_run_and_activate(wizard_env, monkeypatch) -> None:
    from app.ui.pages.template_wizard import render_step_5, validate_dry_run_params

    cfg = load_sample_config()
    form_state = config_to_form_state(cfg)

    # Render step 5 UI
    step5_ui = render_step_5(form_state)
    assert step5_ui is not None
    s5 = str(step5_ui)
    assert "Dry-run trên file mẫu" in s5
    assert "Từ ngày giờ" in s5
    assert "Đến ngày giờ" in s5
    assert "Chạy thử" in s5
    assert "Control total" in s5
    assert "Nhóm Excel / DB" in s5

    # Validate range
    err_valid = validate_dry_run_params("2026-02-01T00:00:00", "2026-02-05T23:59:59")
    assert err_valid is None

    err_invalid = validate_dry_run_params("2026-02-05T00:00:00", "2026-02-01T23:59:59")
    assert err_invalid is not None
    assert "Đến ngày giờ phải lớn hơn hoặc bằng Từ ngày giờ" in err_invalid


def test_render_diagrams_tab(wizard_env) -> None:
    from app.ui.pages.template_wizard import handle_switch_tabs, render_diagrams_tab

    cfg = load_sample_config()
    form_state = config_to_form_state(cfg)

    diag_ui = render_diagrams_tab(form_state)
    assert diag_ui is not None
    s_diag = str(diag_ui)
    # Check all 5 diagrams are present
    assert "1. Quy trình tổng quan 6 giai đoạn" in s_diag
    assert "2. Chuẩn hóa & Ánh xạ trường logic" in s_diag
    assert "3. Truy vấn DB & Điều kiện lọc thời gian" in s_diag
    assert "4. Phân cấp Profile & Nhóm đối soát" in s_diag
    assert "5. Quy tắc Kiểm soát tổng (Control Total)" in s_diag
    assert "mermaid" in s_diag

    # Test tab switching callback
    st_box, st_content, diag_content, ft_nav, diag_children = handle_switch_tabs("diagram", form_state)
    assert st_box["display"] == "none"
    assert st_content["display"] == "none"
    assert diag_content["display"] == "block"
    assert ft_nav["display"] == "none"
    assert diag_children is not None


def test_handle_wizard_file_upload(wizard_env, monkeypatch) -> None:
    import base64

    from app.ui.pages.template_wizard import handle_wizard_file_upload, render_step_1, render_step_2

    owner_ctx = Ctx(user_id=1, username="owner", full_name="Owner", roles=[Role.TEMPLATE_OWNER])
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: owner_ctx)

    sample_bytes = Path("samples/dtp_sample_200.xlsx").read_bytes()
    b64_content = "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," + base64.b64encode(
        sample_bytes
    ).decode("ascii")

    sample_file_data, cfg, err, notif = handle_wizard_file_upload(
        b64_content,
        "dtp_sample_200.xlsx",
        {},
    )

    assert err is None
    assert notif is not None
    assert sample_file_data is not None
    assert sample_file_data["filename"] == "dtp_sample_200.xlsx"
    assert sample_file_data["sheet"] == "BÁO CÁO DTP"
    assert sample_file_data["total_rows"] >= 200
    assert sample_file_data["total_cols"] >= 18
    assert len(sample_file_data["preview_rows"]) == 5
    assert len(sample_file_data["candidate_total_rows"]) >= 1

    assert cfg["file"]["sheet"] == "BÁO CÁO DTP"
    assert len(cfg["fields"]) >= 18

    # Render Step 1 with uploaded sample file data
    step1_ui = render_step_1(cfg, sample_data=sample_file_data)
    assert step1_ui is not None
    s1 = str(step1_ui)
    assert "dtp_sample_200.xlsx" in s1
    assert "BÁO CÁO DTP" in s1
    assert "Xem trước 5 dòng" in s1

    # Render Step 2 with populated fields
    step2_ui = render_step_2(cfg)
    assert step2_ui is not None
    s2 = str(step2_ui)
    assert "Cột Excel → Trường logic" in s2
    assert "SO_HOA_DON" in s2


def test_step_3_switch_db_mode() -> None:
    from app.ui.pages.template_wizard import handle_switch_db_mode

    # Switch to SQL mode
    t_style, s_style, gen_style, cfg = handle_switch_db_mode("sql", {"db_source": {}})
    assert t_style == {"display": "none"}
    assert s_style == {"display": "block"}
    assert gen_style == {"display": "none"}
    assert cfg["db_source"]["kind"] == "sql"

    # Switch back to Table mode
    t_style, s_style, gen_style, cfg = handle_switch_db_mode("table", cfg)
    assert t_style == {"display": "block"}
    assert s_style == {"display": "none"}
    assert gen_style == {"display": "block"}
    assert cfg["db_source"]["kind"] == "table"


def test_step_3_auto_match_db_columns() -> None:
    from app.ui.pages.template_wizard import _auto_match_db_columns

    fields = [
        {"name": "INVOICE_NO", "label": "Số hóa đơn", "excel": "Số hóa đơn", "db": None},
        {"name": "INV_DATETIME", "label": "Ngày lập", "excel": "Ngày lập hóa đơn", "db": None},
        {"name": "AMOUNT", "label": "Thành tiền", "excel": "Thành tiền", "db": None},
        {"name": "UNKNOWN_FIELD", "label": "Trường lạ", "excel": "Trường lạ", "db": None},
    ]

    db_cols = [
        ("INVOICE_NO", "VARCHAR2(30)"),
        ("INVOICE_DATE", "DATE"),
        ("AMOUNT", "NUMBER(18,2)"),
        ("CUSTOMER_ID", "NUMBER(10)"),
    ]

    updated = _auto_match_db_columns(fields, db_cols)
    matched_map = {f["name"]: f.get("db") for f in updated}
    assert matched_map["INVOICE_NO"] == "INVOICE_NO"
    assert matched_map["INV_DATETIME"] == "INVOICE_DATE"
    assert matched_map["AMOUNT"] == "AMOUNT"
    assert matched_map["UNKNOWN_FIELD"] is None


def test_step_3_handle_check_custom_sql(monkeypatch) -> None:
    from app.core.context import Ctx, Role
    from app.ui.pages.template_wizard import handle_check_custom_sql

    owner_ctx = Ctx(user_id=1, username="owner", full_name="Owner", roles=[Role.TEMPLATE_OWNER])
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: owner_ctx)

    # 1. Invalid SQL (disallowed command: DELETE)
    alert, chips, mapping, filters, cfg = handle_check_custom_sql(
        1,
        "DELETE FROM DATARAW.FACT_BILL",
        "GMD_DEV",
        {"fields": []},
    )
    assert alert is not None
    assert "không hợp lệ" in str(alert) or "Chỉ chấp nhận lệnh SELECT" in str(alert)

    # 2. Empty SQL
    alert, _, _, _, _ = handle_check_custom_sql(
        1,
        "   ",
        "GMD_DEV",
        {"fields": []},
    )
    assert alert is not None
    assert "Vui lòng nhập câu lệnh SQL" in str(alert)


def test_step_4_grain_and_sql_helpers() -> None:
    from app.ui.pages.template_wizard import _calculate_grain_info, _render_profile_grouped_sql

    tot, grp, desc = _calculate_grain_info(["INVOICE_NO"], {"total_rows": 200})
    assert tot == 200
    # Không có cột mẫu để khớp thì không tự điền số nhóm giả.
    assert grp == 0
    assert "Chưa tính được" in desc
    tot2, grp2, _desc2 = _calculate_grain_info(
        ["INVOICE_NO"],
        {
            "total_rows": 200,
            "columns": [{"name": "INVOICE_NO", "suggested_field_name": "INVOICE_NO", "unique_count": 190}],
        },
    )
    assert tot2 == 200
    assert grp2 == 190

    config = {
        "db_source": {
            "source_id": "GMD_DEV",
            "table": "DATARAW.FACT_BILL",
            "params": [
                {"name": "p_from", "db_col": "INVOICE_DATE", "op": ">=", "type": "datetime"},
                {"name": "p_to", "db_col": "INVOICE_DATE", "op": "<=", "type": "datetime"},
            ],
        }
    }
    sql = _render_profile_grouped_sql(
        config,
        ["INVOICE_NO"],
        [{"name": "TOTAL_AMOUNT", "agg": "sum", "field": "AMOUNT"}],
    )
    assert "GROUP BY" in sql
    assert 'UPPER(TRIM(src."INVOICE_NO"))' in sql
    assert 'SUM(src."AMOUNT")' in sql
    assert "FROM" in sql and ") src" in sql


def test_step_4_callbacks(monkeypatch) -> None:
    import json
    from types import SimpleNamespace

    from app.ui.pages.template_wizard import handle_step4_interaction, handle_step4_measure_edits

    cfg = {
        "fields": [
            {"name": "INVOICE_NO", "label": "Số HĐ", "type": "text"},
            {"name": "AMOUNT", "label": "Tiền", "type": "number"},
            {"name": "LINE_NO", "label": "Dòng", "type": "integer"},
        ],
        "profiles": [
            {
                "code": "BY_INVOICE",
                "name": "Theo số hóa đơn",
                "group_by": ["INVOICE_NO"],
                "measures": [
                    {
                        "name": "TOTAL_AMOUNT",
                        "label": "Tổng tiền",
                        "agg": "sum",
                        "field": "AMOUNT",
                        "compare": "abs_tol",
                        "tolerance": 1,
                    }
                ],
                "main_measure": "TOTAL_AMOUNT",
            }
        ],
    }

    # 1. Test adding a profile
    mock_ctx = SimpleNamespace(triggered=[{"prop_id": "wizard-add-profile-btn.n_clicks", "value": 1}])
    monkeypatch.setattr("dash.callback_context", mock_ctx)
    right_ui, cfg_out, active_store, left_ui, tabs_ui, tab_val = handle_step4_interaction(
        None, 1, None, None, None, None, None, [], [], [], [], cfg, "BY_INVOICE", None
    )
    assert len(cfg_out["profiles"]) == 2
    assert active_store == cfg_out["profiles"][1]["code"]

    # 2. Test toggling group_by key
    key_prop = json.dumps({"type": "wizard-field-key-btn", "index": "AMOUNT"}) + ".n_clicks"
    mock_ctx = SimpleNamespace(triggered=[{"prop_id": key_prop, "value": 1}])
    monkeypatch.setattr("dash.callback_context", mock_ctx)
    right_ui2, cfg_out2, _, _, _, _ = handle_step4_interaction(
        None, None, None, None, None, None, None, [1], [], [], [], cfg, "BY_INVOICE", None
    )
    assert "AMOUNT" in cfg_out2["profiles"][0]["group_by"]

    # 3. Test renaming profile name
    mock_ctx = SimpleNamespace(triggered=[{"prop_id": "wizard-profile-name-input.value", "value": "Theo đơn hàng"}])
    monkeypatch.setattr("dash.callback_context", mock_ctx)
    _, cfg_out3, _, _, tabs_ui3, _ = handle_step4_interaction(
        None, None, None, "Theo đơn hàng", None, None, None, [], [], [], [], cfg_out2, "BY_INVOICE", None
    )
    assert cfg_out3["profiles"][0]["name"] == "Theo đơn hàng"
    assert "Theo đơn hàng" in str(tabs_ui3)

    # 4. Test renaming profile code
    mock_ctx = SimpleNamespace(triggered=[{"prop_id": "wizard-profile-code-input.value", "value": "BY_ORDER"}])
    monkeypatch.setattr("dash.callback_context", mock_ctx)
    _, cfg_out4, act_store4, _, _, tab_v4 = handle_step4_interaction(
        None, None, None, None, "BY_ORDER", None, None, [], [], [], [], cfg_out3, "BY_INVOICE", None
    )
    assert cfg_out4["profiles"][0]["code"] == "BY_ORDER"
    assert act_store4 == "BY_ORDER"
    assert tab_v4 == "BY_ORDER"

    # 5. Test deleting profile (when 2 profiles exist)
    cfg_2profs = {
        **cfg_out4,
        "profiles": [
            *cfg_out4["profiles"],
            {"code": "BY_DATE", "name": "Theo ngày", "group_by": ["INV_DATE"], "measures": []},
        ],
    }
    mock_ctx = SimpleNamespace(triggered=[{"prop_id": "wizard-delete-profile-btn.n_clicks", "value": 1}])
    monkeypatch.setattr("dash.callback_context", mock_ctx)
    right_ui5, cfg_out5, act_store5, _, _, tab_v5 = handle_step4_interaction(
        None, None, 1, None, None, None, None, [], [], [], [], cfg_2profs, "BY_DATE", None
    )
    assert len(cfg_out5["profiles"]) == 1
    assert cfg_out5["profiles"][0]["code"] == "BY_ORDER"
    assert act_store5 == "BY_ORDER"
    assert tab_v5 == "BY_ORDER"

    # 6. Test measure edits
    edit_prop = json.dumps({"type": "wizard-m-tol", "index": 0}) + ".value"
    mock_ctx = SimpleNamespace(triggered=[{"prop_id": edit_prop, "value": 5}])
    monkeypatch.setattr("dash.callback_context", mock_ctx)
    cfg_edit, sql_code = handle_step4_measure_edits(
        ["TOTAL_AMOUNT"],
        ["Tổng tiền"],
        ["sum"],
        ["AMOUNT"],
        ["abs_tol"],
        [5],
        [0],
        None,
        None,
        cfg,
        "BY_INVOICE",
    )
    assert cfg_edit["profiles"][0]["measures"][0]["tolerance"] == 5
    assert 'SUM(src."AMOUNT")' in str(sql_code)


def test_step_1_clean_state_when_no_sample_file() -> None:
    from app.ui.pages.template_wizard import build_default_config, render_step_1

    default_cfg = build_default_config()
    assert default_cfg["file"]["sheet"] == ""
    assert default_cfg["fields"] == []
    assert default_cfg["profiles"][0]["code"] == "PROFILE_1"

    # Render Step 1 with empty config and no sample_data
    step1_ui = render_step_1(default_cfg, sample_data=None)
    assert step1_ui is not None
    s1 = str(step1_ui)
    assert "Kéo thả file Excel hoặc CSV vào đây" in s1
    assert "Chưa có dữ liệu xem trước" in s1
    assert "dtp_sample_200.xlsx" not in s1


def test_wizard_layout_edit_existing_template_by_code(wizard_env: object, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.context import Ctx, Role
    from app.services.template import save_draft_template
    from app.ui.pages.template_wizard import layout

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: admin_ctx)

    cfg = load_sample_config()
    res = save_draft_template(admin_ctx, code="BILL_SMART_PORT_BDP", name="Doanh thu smartport BDP", config=cfg)
    assert res.ok

    page = layout(template_id="BILL_SMART_PORT_BDP")
    assert page is not None
    page_str = str(page)

    assert "Sửa template: BILL_SMART_PORT_BDP" in page_str


def test_code_block_contrast() -> None:
    from app.ui.components.code_block import code_block

    cb = code_block("SELECT * FROM FACT_BILL", language="sql")
    assert cb is not None
    style = getattr(cb, "style", {})
    assert style.get("backgroundColor") == "var(--code-bg, #0F1B33)"
    assert style.get("color") == "var(--code-ink, #D6E2FF)"


def test_step3_sql_input_change() -> None:
    from app.ui.pages.template_wizard import handle_sql_input_change

    cfg = {"db_source": {"kind": "sql", "sql": "SELECT 1"}}
    updated = handle_sql_input_change("SELECT 2 FROM DUAL", cfg)
    assert updated["db_source"]["sql"] == "SELECT 2 FROM DUAL"


def test_validate_wizard_step_blocks_each_step() -> None:
    from app.ui.pages.template_wizard import validate_wizard_step

    assert validate_wizard_step({}, 0)
    assert validate_wizard_step({"template_code": "T1", "name": "Test", "fields": []}, 0)
    assert (
        validate_wizard_step(
            {"template_code": "T1", "name": "Test", "fields": [{"name": "AMOUNT", "excel": "AMOUNT"}]},
            1,
        )
        == []
    )
    assert validate_wizard_step(
        {"fields": [{"name": "AMOUNT", "excel": "AMOUNT"}, {"name": "AMOUNT", "excel": "AMOUNT2"}]},
        1,
    )
    assert validate_wizard_step({"db_source": {"kind": "table", "table": "", "filters": []}}, 2)
    assert (
        validate_wizard_step(
            {
                "db_source": {
                    "source_id": "TEST_DS",
                    "kind": "table",
                    "table": "SCHEMA.TBL",
                    "filters": [
                        {"param": "p_from", "column": "CREATED_AT"},
                        {"param": "p_to", "column": "CREATED_AT"},
                    ],
                }
            },
            2,
        )
        == []
    )
    assert validate_wizard_step({"profiles": [{"code": "P1", "group_by": [], "measures": []}]}, 3)


def test_step2_field_edits_save_and_rename_propagates() -> None:
    from app.ui.pages.template_wizard import handle_step2_field_edits

    cfg = {
        "fields": [
            {"name": "AMOUNT", "label": "Tiền", "excel": "AMOUNT", "type": "number"},
            {"name": "QTY", "label": "SL", "excel": "QTY", "type": "number"},
        ],
        "derived": [],
        "profiles": [
            {
                "code": "P1",
                "group_by": ["AMOUNT"],
                "measures": [{"name": "M1", "field": "AMOUNT"}],
                "main_measure": "M1",
            }
        ],
    }
    updated = handle_step2_field_edits(
        ["TOTAL_AMT", "QTY"],
        ["Tổng tiền", "SL"],
        ["number", "number"],
        [True, False],
        [],
        [],
        [],
        cfg,
    )
    assert updated["fields"][0]["name"] == "TOTAL_AMT"
    assert updated["fields"][0]["label"] == "Tổng tiền"
    assert updated["fields"][1]["excel"] is None
    assert updated["fields"][1]["_unused_excel"] == "QTY"
    assert updated["profiles"][0]["group_by"] == ["TOTAL_AMT"]
    assert updated["profiles"][0]["measures"][0]["field"] == "TOTAL_AMT"


def test_step3_no_dtp_fallback_for_empty_config(wizard_env, monkeypatch) -> None:
    from app.core.context import Ctx, Role
    from app.ui.pages.template_wizard import build_default_config, render_step_3

    owner_ctx = Ctx(user_id=1, username="owner", full_name="Owner", roles=[Role.TEMPLATE_OWNER])
    monkeypatch.setattr("app.ui.pages.template_wizard.get_current_ctx", lambda: owner_ctx)
    ui = render_step_3(build_default_config())
    s = str(ui)
    assert "FACT_BILL" not in s
    assert "INVOICE_DATE" not in s
    assert "Chưa chọn bảng nguồn" in s or "Chưa có thông tin cột nguồn" in s


def test_dry_run_no_longer_returns_simulated_numbers() -> None:
    import dash

    from app.ui.pages.template_wizard import handle_run_dry_run

    err, data, _meta = handle_run_dry_run(
        1,
        "2026-02-01 00:00:00",
        "2026-02-05 23:59:59",
        "",
        {},
        {},
        None,
    )
    assert "190" not in str(data)
    assert data is dash.no_update or (data or {}).get("dry_run_ok") is not True


def test_step4_available_fields_only_mapped_db_columns() -> None:
    from app.ui.pages.template_wizard import _mapped_fields_info, render_step_4, validate_wizard_step

    cfg = {
        "fields": [
            {"name": "INVOICE_NO", "label": "Số HĐ", "excel": "Số HĐ", "db": "INVOICE_NO", "type": "text"},
            {"name": "SERVICE_NAME", "label": "Dịch vụ", "excel": "Dịch vụ", "db": None, "type": "text"},
            {"name": "QTY", "label": "SL", "excel": "SL", "db": "QUANTITY", "type": "number"},
            {"name": "UNUSED", "label": "Không dùng", "excel": None, "db": "UNUSED_COL", "type": "text"},
        ],
        "derived": [
            {
                "name": "INV_DATE",
                "label": "Ngày HĐ",
                "type": "date",
                "expr": {"fn": "trunc_day", "args": ["INV_DATETIME"]},
            },
            {
                "name": "BAD_DERIVED",
                "label": "Xấu",
                "type": "date",
                "expr": {"fn": "trunc_day", "args": ["SERVICE_NAME"]},
            },
        ],
        "profiles": [{"code": "PROFILE_1", "name": "Profile 1", "is_default": True, "group_by": [], "measures": []}],
    }
    # INV_DATETIME chưa có trong fields nên INV_DATE không đủ điều kiện map.
    names = [f["name"] for f in _mapped_fields_info(cfg)]
    assert names == ["INVOICE_NO", "QTY"]
    # Thêm trường gốc đã map cho derived thì derived mới vào danh sách.
    cfg["fields"].append(
        {"name": "INV_DATETIME", "label": "Ngày", "excel": "Ngày", "db": "INVOICE_DATE", "type": "datetime"}
    )
    names = [f["name"] for f in _mapped_fields_info(cfg)]
    assert "INV_DATE" in names
    assert "SERVICE_NAME" not in names
    assert "BAD_DERIVED" not in names
    assert "UNUSED" not in names

    ui = render_step_4(cfg)
    s = str(ui)
    assert "SERVICE_NAME" not in s or "chưa map" in s

    # Validate chặn Group by / measure dùng trường chưa map.
    cfg["profiles"][0]["group_by"] = ["SERVICE_NAME"]
    cfg["profiles"][0]["measures"] = [{"name": "M1", "field": "SERVICE_NAME"}]
    errs = validate_wizard_step(cfg, 3)
    assert any("SERVICE_NAME" in e and "chưa map cột DB" in e for e in errs)


def test_default_profile_is_empty_not_guessed() -> None:
    from app.ui.pages.template_wizard import _build_default_profiles_from_fields

    profs = _build_default_profiles_from_fields([{"name": "INVOICE_NO"}, {"name": "AMOUNT"}, {"name": "QTY"}])
    assert len(profs) == 1
    assert profs[0]["group_by"] == []
    assert profs[0]["measures"] == []
    assert profs[0]["main_measure"] is None
    assert "BY_INVOICE" not in str(profs)
    assert "TOTAL_AMOUNT" not in str(profs)


def test_dry_run_error_survives_step5_rerender() -> None:
    from app.ui.pages.template_wizard import handle_run_dry_run, render_step_5

    err_box, store, _meta = handle_run_dry_run(
        1,
        "2026-02-01 00:00:00",
        "2026-02-05 23:59:59",
        "",
        {},
        {},
        None,
    )
    assert store["stage"] == "validate"
    assert store["error"]
    assert "Kiểm tra cấu hình" in str(err_box)
    # Render lại Bước 5 từ store vẫn phải hiện đúng lỗi, không bị xóa.
    ui = render_step_5({}, dry_run_data=store)
    s = str(ui)
    assert store["error"] in s
    assert "Tiến trình Dry-run" in s


def test_step5_timeline_shows_failed_dry_run_stage() -> None:
    from app.ui.pages.template_wizard import render_step_5

    store = {
        "dry_run_ok": False,
        "stage": "dry_run",
        "stage_label": "3. Chạy đối soát thật",
        "error": "Dry-run thất bại: ORA-00942: table or view does not exist (mã: SOURCE_QUERY_FAILED)",
        "summary": {},
        "grain_warnings": [],
    }
    ui = render_step_5({}, dry_run_data=store)
    s = str(ui)
    assert "ORA-00942" in s
    assert "Chạy đối soát thật" in s
