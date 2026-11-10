"""Tests cho trang Quản trị báo cáo + Wizard 6 bước — Bước 3 task 27.

T27-07 (wizard bước 1), T27-08 (nguồn dữ liệu), T27-09 (tham số & LOV),
T27-10 (cấu hình cột), T27-11 (dry-run), T27-12 (kích hoạt).
"""

from __future__ import annotations

from contextlib import contextmanager

from tests.unit.test_page_report_viewer import _dump
from tests.unit.test_report_run_execute import (
    ROWS,
    _mock_ora_conn,
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


def _fresh_state() -> dict:
    return {
        "mode": "wizard",
        "report_id": None,
        "template_id": None,
        "version_id": None,
        "version_status": "DRAFT",
        "step": 1,
        "max_step": 1,
        "analyzed": False,
        "dry_run_ok": False,
        "editing_param_id": None,
    }


def _draft_state(run_env) -> dict:
    state = _fresh_state()
    state.update(
        {
            "report_id": run_env.get("report_id"),
            "template_id": run_env.get("sql_template_id"),
            "version_id": run_env.get("draft_version_id"),
            "version_status": "DRAFT",
            "step": 2,
            "max_step": 2,
            "analyzed": False,
        }
    )
    return state


@contextmanager
def _fake_checked_conn():
    conn, _ = _mock_ora_conn(ROWS)
    yield conn


def _patch_describe(monkeypatch):
    """Giả Oracle describe: open_checked_connection -> mock conn."""
    import app.services.report_source as src

    monkeypatch.setattr(
        src,
        "open_checked_connection",
        lambda ds_id, timeout: _fake_checked_conn(),
    )


class TestAdminLayout:
    def test_layout_admin_shows_list(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        text = _dump(page.layout())
        assert "Quản trị báo cáo" in text
        assert "FIN_REVENUE" in text
        assert "Báo cáo mới" in text

    def test_layout_forbidden_for_operator(self, run_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        text = _dump(page.layout())
        assert "không có quyền" in text

    def test_render_report_list_actions(self, run_env, admin_ctx):
        import app.ui.pages.report_admin as page
        from app.services.report_template import list_templates

        templates = list_templates(admin_ctx, run_env["report_id"]).data
        from app.services.report_template import get_template

        templates = [get_template(admin_ctx, int(t["id"])).data for t in templates]
        reports = [
            {
                "id": run_env["report_id"],
                "code": "FIN_REVENUE",
                "name": "Báo cáo doanh thu",
                "category_code": "FINANCE",
                "templates": templates,
            }
        ]
        text = _dump(page.render_report_list(reports))
        assert "FIN_REVENUE" in text
        assert "SQL1" in text
        assert "DRAFT" in text
        assert "Sửa" in text and "Clone" in text and "Lưu trữ" in text

    def test_render_report_list_delete_action_for_template_less_report(self):
        import app.ui.pages.report_admin as page

        reports = [
            {
                "id": 7,
                "code": "FIN",
                "name": "BÁO CÁO FIN",
                "category_code": "FINANCE",
                "owner": "FIN",
                "is_active": True,
                "templates": [],
            }
        ]
        text = _dump(page.render_report_list(reports))
        assert "Chưa có template" in text
        assert "Hoạt động" in text
        assert "Xóa báo cáo" in text
        assert text.count("Xóa báo cáo") == 1

    def test_render_report_list_delete_action_once_per_report(self, run_env, admin_ctx):
        import app.ui.pages.report_admin as page
        from app.services.report_template import get_template, list_templates

        templates = list_templates(admin_ctx, run_env["report_id"]).data
        templates = [get_template(admin_ctx, int(t["id"])).data for t in templates]
        reports = [
            {
                "id": run_env["report_id"],
                "code": "FIN_REVENUE",
                "name": "Báo cáo doanh thu",
                "category_code": "FINANCE",
                "templates": templates,
            }
        ]
        text = _dump(page.render_report_list(reports))
        assert "Xóa báo cáo" in text
        assert text.count("Xóa báo cáo") == 1

    def test_delete_modal_guard_no_click(self, run_env, admin_ctx):
        from dash import no_update

        import app.ui.pages.report_admin as page

        trigger = {"type": "admin-delete-report", "index": run_env["report_id"]}
        opened, target, _desc = page.open_delete_modal_logic(None, trigger, admin_ctx)
        assert opened is False and target is None
        opened, target, _desc = page.open_delete_modal_logic([0], trigger, admin_ctx)
        assert opened is False and target is None
        opened, target, desc = page.open_delete_modal_logic(
            [1], "admin-delete-modal-cancel", admin_ctx
        )
        assert opened is False and target is None and desc is no_update

    def test_delete_modal_opens_once(self, run_env, admin_ctx):
        import app.ui.pages.report_admin as page

        trigger = {"type": "admin-delete-report", "index": run_env["report_id"]}
        opened, target, desc = page.open_delete_modal_logic([1], trigger, admin_ctx)
        assert opened is True
        assert target == run_env["report_id"]
        assert "FIN_REVENUE" in desc

    def test_delete_confirm_guard_and_delete(self, run_env, admin_ctx):
        import pytest
        from dash.exceptions import PreventUpdate

        import app.ui.pages.report_admin as page

        with pytest.raises(PreventUpdate):
            page.confirm_delete_logic(None, run_env["report_id"], admin_ctx)
        with pytest.raises(PreventUpdate):
            page.confirm_delete_logic(1, None, admin_ctx)
        alert, reports = page.confirm_delete_logic(1, run_env["report_id"], admin_ctx)
        assert "FIN_REVENUE" not in str(reports)
        assert reports == []

    def test_admin_filter_search_and_status(self, run_env, admin_ctx):
        import app.ui.pages.report_admin as page

        reports = [
            {
                "id": 1,
                "code": "FIN_REV",
                "name": "Báo cáo doanh thu",
                "category_code": "FINANCE",
                "templates": [{"versions": [{"status": "ACTIVE"}]}],
            },
            {
                "id": 2,
                "code": "OPS_SHIP",
                "name": "Vận chuyển",
                "category_code": "OPERATIONS",
                "templates": [{"versions": [{"status": "DRAFT"}]}],
            },
        ]
        # Test match search
        body, count = page.handle_admin_filter(reports, "doanh thu", "ALL", "ALL")
        text = _dump(body)
        assert "FIN_REV" in text
        assert "OPS_SHIP" not in text
        assert "1 mục" in count

        # Test filter status
        body, count = page.handle_admin_filter(reports, None, "DRAFT", "ALL")
        text = _dump(body)
        assert "OPS_SHIP" in text
        assert "FIN_REV" not in text
        assert "1 mục" in count

        # Test filter category
        body, count = page.handle_admin_filter(reports, None, "ALL", "FINANCE")
        text = _dump(body)
        assert "FIN_REV" in text
        assert "OPS_SHIP" not in text


class TestStep1:
    def test_render_step1_fields(self):
        import app.ui.pages.report_admin as page

        text = _dump(page.render_step_content(1, _fresh_state()))
        assert "Mã báo cáo" in text
        assert "Tên báo cáo" in text
        assert "Mã template" in text
        assert "Lưu và tiếp tục" in text

    def test_render_step1_keeps_stored_category(self, run_env, admin_ctx, monkeypatch):
        """Task 37: báo cáo cũ mã nhóm 'FIN' (không trong options chuẩn) vẫn hiện đúng trong Select."""
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        state["step"] = 1
        text = _dump(page.render_step_content(1, state))
        assert "value='FIN'" in text
        assert "{'label': 'FIN', 'value': 'FIN'}" in text

    def test_save_step1_unchanged_advances_silently(self, run_env, admin_ctx, monkeypatch):
        """Task 37: bấm Tiếp theo ở bước 1 mà không đổi gì thì qua bước 2 im lặng, không toast lưu."""
        import app.ui.pages.report_admin as page
        from app.services.report import get_report
        from app.services.report_template import get_template, get_version

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        state["step"] = 1
        rep = get_report(admin_ctx, int(state["report_id"])).data
        tpl = get_template(admin_ctx, int(state["template_id"])).data
        ver = get_version(admin_ctx, int(state["version_id"])).data
        new_state, alert = page.handle_save_step1(
            1,
            state,
            rep["code"],
            rep["name"],
            rep["category_code"],
            rep["owner"],
            rep["description"],
            rep["is_visible"],
            rep["default_favorite"],
            tpl["code"],
            tpl["name"],
            tpl["display_order"],
            ver["timeout_sec"],
            ver["preview_max_rows"],
            ver["export_max_rows"],
        )
        assert new_state["step"] == 2
        assert alert is None

    def test_save_step1_changed_still_toasts(self, run_env, admin_ctx, monkeypatch):
        """Task 37: bấm Tiếp theo ở bước 1 có đổi tên thì vẫn lưu + toast như cũ."""
        import app.ui.pages.report_admin as page
        from app.services.report import get_report
        from app.services.report_template import get_template, get_version

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        state["step"] = 1
        rep = get_report(admin_ctx, int(state["report_id"])).data
        tpl = get_template(admin_ctx, int(state["template_id"])).data
        ver = get_version(admin_ctx, int(state["version_id"])).data
        new_state, alert = page.handle_save_step1(
            1,
            state,
            rep["code"],
            "Doanh thu (đổi tên)",
            rep["category_code"],
            rep["owner"],
            rep["description"],
            rep["is_visible"],
            rep["default_favorite"],
            tpl["code"],
            tpl["name"],
            tpl["display_order"],
            ver["timeout_sec"],
            ver["preview_max_rows"],
            ver["export_max_rows"],
        )
        assert new_state["step"] == 2
        assert alert is not None
        assert "Đã lưu thông tin." in _dump(alert)
        assert get_report(admin_ctx, int(state["report_id"])).data["name"] == "Doanh thu (đổi tên)"

    def test_save_step1_creates_report_and_template(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state, alert = page.handle_save_step1(
            1,
            _fresh_state(),
            report_code="NEW_RPT",
            report_name="Báo cáo mới",
            category_code="FINANCE",
            owner="FIN",
            description="Mô tả",
            is_visible=True,
            default_favorite=False,
            tpl_code="NEW_TPL",
            tpl_name="Mẫu mới",
            display_order=10,
            timeout_sec=300,
            preview_max_rows=100,
            export_max_rows=1000000,
        )
        assert state["report_id"] is not None
        assert state["template_id"] is not None
        assert state["version_id"] is not None
        assert state["step"] == 2
        assert state["version_status"] == "DRAFT"
        assert alert is None or "Đã lưu" in _dump(alert)

    def test_save_step1_duplicate_code_errors(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state, alert = page.handle_save_step1(
            1,
            _fresh_state(),
            report_code="FIN_REVENUE",
            report_name="Trùng mã",
            category_code="FINANCE",
            owner="FIN",
            description="",
            is_visible=True,
            default_favorite=False,
            tpl_code="X1",
            tpl_name="X",
            display_order=10,
            timeout_sec=300,
            preview_max_rows=100,
            export_max_rows=1000000,
        )
        assert state["report_id"] is None
        assert alert is not None
        assert "đã tồn tại" in _dump(alert)

    def test_s1_save_callback_keeps_state_on_failure(self, run_env, admin_ctx, monkeypatch):
        """Lưu lỗi thì callback trả no_update cho state-store (không render lại).

        Hồi quy: trước sửa, callback trả state không đổi nên wizard render
        lại, form bước 1 bị dựng lại từ rỗng và mất hết dữ liệu vừa nhập.
        """
        import dash

        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state, alert = page.handle_s1_save(
            1,
            _fresh_state(),
            "FIN_REVENUE",
            "Trùng mã",
            "FINANCE",
            "FIN",
            "",
            True,
            False,
            "X1",
            "X",
            10,
            300,
            100,
            1000000,
        )
        assert state is dash.no_update
        assert alert is not None
        assert "đã tồn tại" in _dump(alert)

    def test_err_alert_names_the_invalid_field(self):
        """Lỗi validate hiển thị đúng trường + lý do, không chỉ câu chung.

        Hồi quy: service trả message chung 'Dữ liệu không hợp lệ', chi
        tiết trường nằm trong details.errors nên người dùng không biết
        sửa ô nào.
        """
        from types import SimpleNamespace

        import app.ui.pages.report_admin as page

        res = SimpleNamespace(
            message="Dữ liệu không hợp lệ",
            details={
                "errors": [
                    {"field": "code", "message": "String should match pattern", "type": "string_pattern_mismatch"},
                    {
                        "field": "owner",
                        "message": "String should have at least 1 character",
                        "type": "string_too_short",
                    },
                ]
            },
        )
        text = _dump(page._err_alert(res))
        assert "Dữ liệu không hợp lệ" in text
        assert "Mã: chỉ gồm chữ hoa, số và dấu gạch dưới, bắt đầu bằng chữ hoa." in text
        assert "Chủ sở hữu: không được để trống." in text

    def test_err_alert_falls_back_without_details(self):
        from types import SimpleNamespace

        import app.ui.pages.report_admin as page

        res = SimpleNamespace(message="Lỗi khác.", details=None)
        assert "Lỗi khác." in _dump(page._err_alert(res))

    def test_s1_save_callback_updates_state_on_success(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state, alert = page.handle_s1_save(
            1,
            _fresh_state(),
            "NEW_RPT2",
            "Báo cáo mới 2",
            "FINANCE",
            "FIN",
            "",
            True,
            False,
            "NEW_TPL2",
            "Mẫu mới 2",
            10,
            300,
            100,
            1000000,
        )
        assert isinstance(state, dict)
        assert state["step"] == 2
        assert state["report_id"] is not None
        assert alert is None or "Đã lưu" in _dump(alert)

    def test_save_step1_edit_updates(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report import get_report

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        state["step"] = 1
        state, _alert = page.handle_save_step1(
            1,
            state,
            report_code="FIN_REVENUE",
            report_name="Báo cáo doanh thu (sửa)",
            category_code="FINANCE",
            owner="FIN",
            description="",
            is_visible=True,
            default_favorite=False,
            tpl_code="SQL1",
            tpl_name="Mẫu SQL1 (sửa)",
            display_order=10,
            timeout_sec=300,
            preview_max_rows=100,
            export_max_rows=1000000,
        )
        assert state["step"] == 2
        assert get_report(admin_ctx, run_env["report_id"]).data["name"] == ("Báo cáo doanh thu (sửa)")


class TestStep2:
    def test_render_step2_fields(self):
        import app.ui.pages.report_admin as page

        text = _dump(page.render_step_content(2, _draft_state({})))
        assert "Nguồn dữ liệu" in text
        assert "Phân tích SQL" in text

    def test_analyze_sql_applies_diff(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_column import list_columns

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        # DRAFT1 chưa có cột nào: analyze SQL mẫu tạo 3 cột.
        state, alert = page.handle_analyze_sql(
            1,
            state,
            "SELECT amount, org, txn_date FROM fin_revenue WHERE org = :p_org",
        )
        assert state["analyzed"] is True
        assert alert is None or "Đã phân tích" in _dump(alert)
        cols = list_columns(admin_ctx, run_env["draft_version_id"]).data
        assert {c["field_name"] for c in cols} == {"AMOUNT", "ORG", "TXN_DATE"}

    def test_analyze_sql_invalid_shows_error(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        state, alert = page.handle_analyze_sql(1, state, "DROP TABLE fin_revenue")
        assert state["analyzed"] is False
        assert alert is not None
        assert "không hợp lệ" in _dump(alert).lower() or "SQL" in _dump(alert)


class TestStep3:
    def test_render_step3_shows_params(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        text = _dump(page.render_step_content(3, state))
        assert "Tham số" in text
        # Người dùng yêu cầu bỏ 3 nút: Thêm tham số, Thêm hàng, Tự sắp xếp (thao tác trực quan drag & drop)
        assert "Thêm tham số" not in text
        assert "Tự sắp xếp" not in text
        assert "param-canvas" in text
        assert "lovside" in text
        assert "Cấu hình LOV" in text

    def test_param_canvas_row_col_centered_nowrap(self):
        """Task 37: giá trị Hàng/Cột căn giữa (ẩn nút tăng/giảm), nhóm không rớt dòng trong box hẹp."""
        import app.ui.pages.report_admin as page

        params = [
            {
                "id": 1,
                "code": "p_org",
                "label": "Đơn vị",
                "data_type": "STRING",
                "control_type": "TEXT",
                "required": True,
                "display_row": 1,
                "display_order": 10,
                "grid_span": 2,
            }
        ]
        text = _dump(page._render_param_canvas(params, []))
        assert "hideControls" in text
        assert "nowrap" in text
        assert "textAlign" in text and "center" in text

    def test_param_create_and_delete(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_param import preview_layout

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        vid = run_env["draft_version_id"]
        param, _alert = page.handle_param_save(
            1,
            _draft_state(run_env),
            param_id=None,
            code="p_new",
            label="Tham số mới",
            data_type="STRING",
            control_type="TEXT",
            required=False,
            default_type="NONE",
            default_value=None,
            display_row=1,
            display_order=100,
            grid_span=3,
            filter_column="ORG",
            filter_operator="=",
            is_visible=True,
            lov_type="NONE",
            lov_sql=None,
            lov_lookup_type=None,
            lov_static_text=None,
        )
        assert param is not None and param["code"] == "p_new"
        layout = preview_layout(admin_ctx, vid)
        codes = [e["code"] for r in layout.data["rows"] for e in r["params"]]
        assert "p_new" in codes
        ok, _alert = page.handle_param_delete(1, _draft_state(run_env), param["id"])
        assert ok is True
        layout = preview_layout(admin_ctx, vid)
        codes = [e["code"] for r in layout.data["rows"] for e in r["params"]]
        assert "p_new" not in codes

    def test_param_move_and_auto_layout(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_param import preview_layout

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        vid = run_env["draft_version_id"]
        # Thêm 2 param rồi dời param thứ 2 lên đầu hàng.
        _, _ = page.handle_param_save(
            1,
            _draft_state(run_env),
            param_id=None,
            code="p_a",
            label="A",
            data_type="STRING",
            control_type="TEXT",
            required=False,
            default_type="NONE",
            default_value=None,
            display_row=2,
            display_order=10,
            grid_span=6,
            filter_column=None,
            filter_operator=None,
            is_visible=True,
            lov_type="NONE",
            lov_sql=None,
            lov_lookup_type=None,
            lov_static_text=None,
        )
        p_b, _ = page.handle_param_save(
            1,
            _draft_state(run_env),
            param_id=None,
            code="p_b",
            label="B",
            data_type="STRING",
            control_type="TEXT",
            required=False,
            default_type="NONE",
            default_value=None,
            display_row=2,
            display_order=20,
            grid_span=6,
            filter_column=None,
            filter_operator=None,
            is_visible=True,
            lov_type="NONE",
            lov_sql=None,
            lov_lookup_type=None,
            lov_static_text=None,
        )
        ok, _ = page.handle_param_move(1, _draft_state(run_env), p_b["id"], "up")
        assert ok is True
        ok, _ = page.handle_auto_layout(1, _draft_state(run_env))
        assert ok is True
        layout = preview_layout(admin_ctx, vid)
        assert layout.ok


class TestStep4:
    def _draft_with_columns(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        state, alert = page.handle_analyze_sql(
            1,
            state,
            "SELECT amount, org, txn_date FROM fin_revenue WHERE org = :p_org",
        )
        assert state["analyzed"] is True, _dump(alert)
        return run_env["draft_version_id"]

    def test_render_step4_shows_columns(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_column import list_columns

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        state = _draft_state(run_env)
        state["version_id"] = vid
        text = _dump(page.render_step_content(4, state))
        assert "Cấu hình cột" in text
        assert "AMOUNT" in text
        assert "Khôi phục thứ tự" in text

        # Kiểm tra preview cột có dữ liệu mẫu thực tế
        cols = list_columns(admin_ctx, vid).data
        preview = page._render_columns_preview(cols)
        tbody = preview.children.children[1]
        tbody_text = _dump(tbody)
        assert "Dữ liệu mẫu 1" in tbody_text or "10000000" in tbody_text

    def test_column_save_bulk(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_column import list_columns

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        cols = list_columns(admin_ctx, vid).data
        amount = next(c for c in cols if c["field_name"] == "AMOUNT")
        ok, _alert = page.handle_column_save(
            1,
            _draft_state(run_env) | {"version_id": vid},
            rows=[{"id": amount["id"], "label": "Số tiền"}],
        )
        assert ok is True
        cols = list_columns(admin_ctx, vid).data
        assert next(c for c in cols if c["field_name"] == "AMOUNT")["label"] == "Số tiền"

    def test_column_save_bulk_mixed_types_via_callback(self, run_env, admin_ctx, monkeypatch):
        """Hồi quy: lưu grid AgGrid lẫn kiểu qua callback thật (totals chỉ có ở cột NUMBER).

        Grid gửi nội dung ô qua rowData và thứ tự qua virtualRowData (rowData
        không đồng bộ sau kéo-thả — xem plan task 35).
        """
        import app.ui.pages.report_admin as page
        from app.db.metadata import recon_rpt_column
        from app.services.report_column import list_columns

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        cols = list_columns(admin_ctx, vid).data
        amount = next(c for c in cols if c["field_name"] == "AMOUNT")
        # Fixture describe giả trả kiểu None → analyze map hết về STRING;
        # đặt AMOUNT về NUMBER để grid lẫn kiểu đúng như thật.
        with run_env["engine"].begin() as db:
            db.execute(
                recon_rpt_column.update()
                .where(recon_rpt_column.c.ID == amount["id"])
                .values(DATA_TYPE="NUMBER")
            )
        cols = list_columns(admin_ctx, vid).data
        new_labels = {"AMOUNT": "Số tiền", "ORG": "Đơn vị", "TXN_DATE": "Ngày giao dịch"}
        row_data = []
        for c in cols:
            row = dict(c)
            row["label"] = new_labels[c["field_name"]]
            row["is_total"] = c["field_name"] == "AMOUNT"
            row_data.append(row)
        # Đổi thứ tự qua virtualRowData: ORG lên đầu.
        virtual_data = [row_data[1], row_data[0], row_data[2]]
        alert, preview = page.handle_col_save(
            1,
            _draft_state(run_env) | {"version_id": vid},
            row_data,
            virtual_data,
        )
        assert alert is not None
        cols = list_columns(admin_ctx, vid).data
        by_field = {c["field_name"]: c for c in cols}
        assert by_field["ORG"]["label"] == "Đơn vị"
        assert by_field["AMOUNT"]["is_total"] is True
        assert by_field["ORG"]["is_total"] is False
        assert by_field["TXN_DATE"]["is_total"] is False
        assert cols[0]["field_name"] == "ORG"
        # Preview vẽ lại từ DB mới nên header theo nhãn đã lưu.
        assert "Đơn vị" in _dump(preview)

    def test_column_grid_defs(self):
        """Grid AgGrid bước 4: đủ cột, đúng editor, Kiểu chỉ xem, Tổng chỉ NUMBER."""
        import app.ui.pages.report_admin as page

        defs = page._column_grid_column_defs(editable=True)
        by_field = {d.get("field"): d for d in defs if d.get("field")}
        assert defs[0].get("rowDrag") is True
        assert by_field["label"]["editable"] is True
        assert by_field["label"]["cellEditor"] == "agTextCellEditor"
        assert by_field["data_type"]["editable"] is False
        fmt = by_field["format_mask"]
        assert fmt["cellEditor"] == "agSelectCellEditor"
        assert "#,##0" in fmt["cellEditorParams"]["values"]
        assert "DD/MM/YYYY" in fmt["cellEditorParams"]["values"]
        assert "" in fmt["cellEditorParams"]["values"]
        assert by_field["alignment"]["cellEditorParams"]["values"] == ["LEFT", "CENTER", "RIGHT"]
        width = by_field["width"]
        assert width["cellEditor"] == "agNumberCellEditor"
        assert width["cellEditorParams"]["min"] == 40
        assert width["cellEditorParams"]["max"] == 400
        for f in ("web_visible", "excel_visible", "is_total"):
            assert by_field[f]["cellRenderer"] == "agCheckboxCellRenderer"
            assert by_field[f]["cellEditor"] == "agCheckboxCellEditor"
        total_editable = by_field["is_total"]["editable"]
        assert isinstance(total_editable, dict) and "NUMBER" in total_editable.get("function", "")

        locked = page._column_grid_column_defs(editable=False)
        assert locked[0].get("rowDrag") is False
        assert all(d.get("editable") is False for d in locked if "editable" in d)

    def test_column_grid_save_payload_merge(self):
        """Gộp thứ tự từ virtualRowData (đồng bộ sau kéo-thả) vào rowData."""
        import app.ui.pages.report_admin as page

        def row(cid, label="L"):
            return {
                "id": cid,
                "field_name": f"F{cid}",
                "label": label,
                "data_type": "STRING",
                "display_order": cid * 10,
                "web_visible": True,
                "excel_visible": True,
                "format_mask": "",
                "alignment": "LEFT",
                "width": "",
                "is_total": False,
            }

        rows, order = page._column_grid_save_payload([row(1), row(2), row(3)], [row(3), row(1), row(2)])
        assert order == [3, 1, 2]
        assert [r["id"] for r in rows] == [1, 2, 3]
        assert "field_name" not in rows[0] and "data_type" not in rows[0] and "display_order" not in rows[0]
        assert rows[0]["format_mask"] is None and rows[0]["width"] is None
        # Đang lọc tìm kiếm: chỉ 2 dòng visible, thứ tự visible gộp vào vị trí cũ.
        rows, order = page._column_grid_save_payload([row(1), row(2), row(3), row(4)], [row(3), row(1)])
        assert order == [3, 2, 1, 4]
        # Không có virtual: giữ nguyên thứ tự rowData.
        rows, order = page._column_grid_save_payload([row(1), row(2)], None)
        assert order == [1, 2]

    def test_column_delete_selected(self, run_env, admin_ctx, monkeypatch):
        import dash

        import app.ui.pages.report_admin as page
        from app.services.report_column import list_columns

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env) | {"version_id": vid}
        cols = list_columns(admin_ctx, vid).data
        amount = next(c for c in cols if c["field_name"] == "AMOUNT")
        new_state, _alert, _preview = page.handle_col_del_click(1, [{"id": amount["id"]}], state)
        assert new_state["rev"] == 1
        assert all(c["field_name"] != "AMOUNT" for c in list_columns(admin_ctx, vid).data)
        # Chưa chọn dòng nào: cảnh báo, không đổi state.
        no_state, warn, no_preview = page.handle_col_del_click(1, [], state)
        assert no_state is dash.no_update
        assert no_preview is dash.no_update
        assert "Chọn một dòng" in _dump(warn)

    def test_column_restore_order(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_column import list_columns, reorder_columns

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        cols = list_columns(admin_ctx, vid).data
        ids = [c["id"] for c in cols]
        reorder_columns(admin_ctx, vid, [ids[1], ids[0], ids[2]])
        assert list_columns(admin_ctx, vid).data[0]["field_name"] == "ORG"
        ok, _ = page.handle_restore_order(1, _draft_state(run_env) | {"version_id": vid})
        assert ok is True
        assert list_columns(admin_ctx, vid).data[0]["field_name"] == "AMOUNT"

    def test_column_grid_getrowid_is_function(self, run_env, admin_ctx, monkeypatch):
        """Task 37: getRowId dạng chuỗi biểu thức 'params.data.id.toString()'.

        Dạng chuỗi bare 'id' trả undefined (xóa rớt dòng), dạng dict function
        làm crash đồng bộ selectedRows của dash-ag-grid (ge.replaceAll).
        Dạng 'params.data.id' còn warning #25 (id số bị cast sang chuỗi).
        """
        import app.ui.pages.report_admin as page

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        state = _draft_state(run_env)
        state["version_id"] = vid
        text = _dump(page.render_step_content(4, state))
        assert "params.data.id.toString()" in text

    def test_column_move_row_helper(self):
        """Task 37: helper đổi vị trí dòng đã chọn lên/xuống 1 nấc (đầu/cuối và không chọn thì giữ nguyên)."""
        import app.ui.pages.report_admin as page

        rows = [{"id": 1}, {"id": 2}, {"id": 3}]
        assert [r["id"] for r in page._move_row_in_list(rows, 2, -1)] == [2, 1, 3]
        assert [r["id"] for r in page._move_row_in_list(rows, 2, 1)] == [1, 3, 2]
        assert [r["id"] for r in page._move_row_in_list(rows, 1, -1)] == [1, 2, 3]
        assert [r["id"] for r in page._move_row_in_list(rows, 3, 1)] == [1, 2, 3]
        assert [r["id"] for r in page._move_row_in_list(rows, 9, -1)] == [1, 2, 3]
        assert [r["id"] for r in page._move_row_in_list(rows, None, -1)] == [1, 2, 3]

    def test_column_move_up_down_callbacks(self):
        """Task 37: nút Lên/Xuống đổi thứ tự rowData; chưa chọn hoặc đã ở đầu/cuối thì no_update."""
        import dash

        import app.ui.pages.report_admin as page

        rows = [
            {"id": 1, "field_name": "AMOUNT"},
            {"id": 2, "field_name": "ORG"},
            {"id": 3, "field_name": "TXN_DATE"},
        ]
        moved = page.handle_col_move_up(1, rows, [{"id": 2}])
        assert [r["id"] for r in moved] == [2, 1, 3]
        moved = page.handle_col_move_down(1, rows, [{"id": 2}])
        assert [r["id"] for r in moved] == [1, 3, 2]
        assert page.handle_col_move_up(1, rows, []) is dash.no_update
        assert page.handle_col_move_up(1, rows, [{"id": 1}]) is dash.no_update
        assert page.handle_col_move_down(1, rows, [{"id": 3}]) is dash.no_update

    def test_column_grid_defs_flex(self):
        """Task 37: 2 cột text Trường DB/Nhãn flex để grid chiếm full chiều rộng."""
        import app.ui.pages.report_admin as page

        defs = {d["field"]: d for d in page._column_grid_column_defs(editable=True) if "field" in d}
        assert defs["field_name"].get("flex") == 1
        assert defs["label"].get("flex") == 1
        assert defs["field_name"].get("minWidth") == 170
        assert defs["label"].get("minWidth") == 180
        assert "flex" not in defs["width"]
        assert "flex" not in defs["web_visible"]

    def test_render_step4_grid_height_fits(self, run_env, admin_ctx, monkeypatch):
        """Task 37: grid cao calc(100vh - 380px) để card không tràn footer."""
        import app.ui.pages.report_admin as page

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        state = _draft_state(run_env)
        state["version_id"] = vid
        text = _dump(page.render_step_content(4, state))
        assert "calc(100vh - 380px)" in text

    def test_wizard_footer_compact(self):
        """Task 37: footer thu còn 26px (~1/2 của 48px)."""
        import app.ui.pages.report_admin as page

        text = _dump(page._render_wizard_footer(4, _fresh_state()))
        assert "26px" in text
        assert "48px" not in text

    def test_column_search_quick_filter(self):
        import app.ui.pages.report_admin as page

        opts = page.handle_col_search("AMO")
        assert opts["quickFilterText"] == "AMO"
        assert opts["rowDragManaged"] is True
        assert opts["rowSelection"] == "single"
        assert page.handle_col_search("")["quickFilterText"] == ""
        assert page.handle_col_delete_btn_state([]) is True
        assert page.handle_col_delete_btn_state([{"id": 1}]) is False


class TestStep5:
    def test_render_step5_shows_dry_run(self, run_env):
        import app.ui.pages.report_admin as page

        text = _dump(page.render_step_content(5, _draft_state(run_env)))
        assert "Xem trước" in text
        assert "Chạy dry-run" in text

    def test_dry_run_success(self, run_env, admin_ctx, monkeypatch):
        from unittest.mock import patch

        import app.ui.pages.report_admin as page
        from app.services.report_template import get_version

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        # DRAFT1: CUSTOM_SQL + param p_org; dry-run cần Oracle mock.
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            state, result, alert = page.handle_dry_run(1, state, values={"p_org": "HN"})
        assert state["dry_run_ok"] is True
        assert result is not None and result["total"] is None
        assert len(result["rows"]) == 3
        assert alert is None
        assert get_version(admin_ctx, run_env["draft_version_id"]).data["status"] == "DRY_RUN_OK"

    def test_dry_run_failure_blocks(self, run_env, admin_ctx, monkeypatch):
        from unittest.mock import patch

        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        with patch(
            "app.services.report_source.open_source_connection",
            side_effect=RuntimeError("ORA-12154: TNS:could not resolve"),
        ):
            state, result, alert = page.handle_dry_run(1, state, values={"p_org": "HN"})
        assert state["dry_run_ok"] is False
        assert result is None
        assert alert is not None

    def test_dry_run_click_no_banner_no_info(self, run_env, admin_ctx, monkeypatch):
        """Task 36: callback Chạy dry-run trả 4 giá trị, không banner, không dòng info, toast xem trước N dòng."""
        from unittest.mock import patch

        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            out = page.handle_dryrun_click(
                1, state, ["HN"], [{"type": "viewer-param", "index": "p_org"}]
            )
        assert len(out) == 4
        new_state, result, alert, result_area = out
        assert new_state["dry_run_ok"] is True
        assert result is not None and result["total"] is None
        area = _dump(result_area)
        assert "Tổng" not in area and "dòng mẫu" not in area
        assert "Dry-run OK" not in area and "Xem trước ACTIVE" not in area
        assert "HN" in area  # bảng kết quả vẫn hiện dòng dữ liệu
        assert "xem trước 3 dòng" in _dump(alert)

    def test_render_step5_no_alert_no_info(self, run_env, admin_ctx, monkeypatch):
        """Task 36: bước 5 có kết quả dry-run thì không còn alert cam, banner hay dòng info."""
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        state["dry_run_ok"] = True
        dry_run = {
            "total": None,
            "rows": [{"AMOUNT": 1000, "ORG": "HN", "TXN_DATE": "2026-02-01"}],
            "query_ms": 5,
        }
        text = _dump(page.render_step5(state, dry_run))
        assert "Preview dùng tối đa" not in text
        assert "Dry-run OK" not in text
        assert "Tổng" not in text and "dòng mẫu" not in text
        assert "HN" in text

    def test_dry_run_active_keeps_status(self, run_env, admin_ctx, monkeypatch):
        """Task 34: dry-run version ACTIVE chỉ xem trước, state giữ ACTIVE."""
        from unittest.mock import patch

        import app.ui.pages.report_admin as page
        from app.services.report_template import get_version

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        state.update(
            {
                "version_id": run_env["sql_version_id"],
                "version_status": "ACTIVE",
                "step": 5,
                "max_step": 6,
            }
        )
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            state, result, alert = page.handle_dry_run(1, state, values={"p_org": "HN"})
        assert state["dry_run_ok"] is True
        assert state["version_status"] == "ACTIVE"
        assert result is not None and result["total"] is None
        assert len(result["rows"]) == 3
        assert alert is None
        assert get_version(admin_ctx, run_env["sql_version_id"]).data["status"] == "ACTIVE"


class TestStep6:
    def test_render_step6_shows_activate(self, run_env):
        import app.ui.pages.report_admin as page

        state = _draft_state(run_env)
        state["dry_run_ok"] = True
        text = _dump(page.render_step_content(6, state))
        assert "Hoàn tất" in text
        assert "Kích hoạt template" in text

    def test_activate_after_dry_run(self, run_env, admin_ctx, monkeypatch):
        from unittest.mock import patch

        import app.ui.pages.report_admin as page
        from app.services.report_template import get_version

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            state, _result, _alert = page.handle_dry_run(1, state, values={"p_org": "HN"})
        state, alert = page.handle_activate(1, state)
        assert alert is None or "ACTIVE" in _dump(alert)
        assert get_version(admin_ctx, run_env["draft_version_id"]).data["status"] == "ACTIVE"

    def test_activate_without_dry_run_blocked(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        _state, alert = page.handle_activate(1, state)
        assert alert is not None

    def test_render_step6_active_shows_reopen(self, run_env):
        """Task 34: màn hình ACTIVE có nút Mở lại để sửa."""
        import app.ui.pages.report_admin as page

        state = _draft_state(run_env)
        state.update(
            {
                "version_id": run_env["sql_version_id"],
                "version_status": "ACTIVE",
                "step": 6,
                "max_step": 6,
            }
        )
        text = _dump(page.render_step_content(6, state))
        assert "Đã kích hoạt" in text
        assert "Mở lại để sửa" in text

    def test_open_reopen_modal_active(self, run_env, admin_ctx):
        """Task 34: bấm Mở lại ở version ACTIVE thì mở modal có cảnh báo."""
        import app.ui.pages.report_admin as page

        state = _draft_state(run_env)
        state.update(
            {
                "version_id": run_env["sql_version_id"],
                "version_status": "ACTIVE",
                "step": 6,
                "max_step": 6,
            }
        )
        opened, desc = page.open_reopen_modal_logic(1, "admin-reopen-btn", state, admin_ctx)
        assert opened is True
        assert "tạm ngưng" in _dump(desc)

    def test_open_reopen_modal_draft_blocked(self, run_env, admin_ctx):
        """Task 34: version DRAFT không mở modal mở lại."""
        import app.ui.pages.report_admin as page

        state = _draft_state(run_env)
        opened, _desc = page.open_reopen_modal_logic(1, "admin-reopen-btn", state, admin_ctx)
        assert opened is False

    def test_reopen_active_to_draft(self, run_env, admin_ctx):
        """Task 34: xác nhận mở lại ACTIVE → DRAFT, gỡ pointer, nhảy bước 4."""
        import app.ui.pages.report_admin as page
        from app.services.report_template import get_template, get_version

        state = _draft_state(run_env)
        state.update(
            {
                "version_id": run_env["sql_version_id"],
                "version_status": "ACTIVE",
                "step": 6,
                "max_step": 6,
            }
        )
        new_state, alert = page.confirm_reopen_logic(1, state, admin_ctx)
        assert alert is None or "DRAFT" in _dump(alert)
        assert new_state["version_status"] == "DRAFT"
        assert new_state["dry_run_ok"] is False
        assert new_state["step"] == 4
        assert get_version(admin_ctx, run_env["sql_version_id"]).data["status"] == "DRAFT"
        assert get_template(admin_ctx, run_env["sql_template_id"]).data["active_version_id"] is None

    def test_reopen_dry_run_ok_to_draft(self, run_env, admin_ctx, monkeypatch):
        """Task 34: version DRY_RUN_OK mở lại được về DRAFT để sửa tiếp."""
        from unittest.mock import patch

        import app.ui.pages.report_admin as page
        from app.services.report_template import get_version

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            state, _result, _alert = page.handle_dry_run(1, state, values={"p_org": "HN"})
        assert state["version_status"] == "DRY_RUN_OK"
        new_state, alert = page.confirm_reopen_logic(1, state, admin_ctx)
        assert new_state["version_status"] == "DRAFT"
        assert new_state["step"] == 4
        assert "DRAFT" in _dump(alert)
        assert get_version(admin_ctx, run_env["draft_version_id"]).data["status"] == "DRAFT"

    def test_clone_and_archive(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_template import get_version

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state, alert = page.handle_clone(1, run_env["sql_version_id"])
        assert state is not None and state["version_id"] != run_env["sql_version_id"]
        assert get_version(admin_ctx, state["version_id"]).data["status"] == "DRAFT"
        ok, _alert = page.handle_archive_version(1, state)
        assert ok is True
        assert get_version(admin_ctx, state["version_id"]).data["status"] == "ARCHIVED"


class TestWizardNav:
    def test_next_blocked_without_save(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state, alert = page.handle_next_step(1, _fresh_state())
        assert state["step"] == 1
        assert alert is not None

    def test_next_blocked_without_analyze(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        state["step"] = 2
        state, alert = page.handle_next_step(1, state)
        assert state["step"] == 2
        assert alert is not None

    def test_step_click_back_allowed_ahead_blocked(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        state.update({"step": 3, "max_step": 3, "analyzed": True})
        state, _ = page.handle_step_click(1, state, 1)
        assert state["step"] == 1
        state, alert = page.handle_step_click(1, state, 5)
        assert state["step"] == 1
        assert alert is not None

    def test_step_click_same_step_does_not_clear_alert(self, run_env, admin_ctx, monkeypatch):
        """Stepper dựng lại phát active đúng bước hiện tại: không làm gì.

        Hồi quy: trước sửa, callback stepper trả (state, None) và xóa alert
        lỗi vừa hiện sau khi Lưu bước 1 lỗi — người dùng thấy bấm không có
        tác dụng. Nay phải PreventUpdate để alert còn nguyên.
        """
        import pytest
        from dash.exceptions import PreventUpdate

        import app.ui.pages.report_admin as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        state.update({"step": 1, "max_step": 1})
        # active 0-based = bước 1 hiện tại (đường callback Dash).
        with pytest.raises(PreventUpdate):
            page.handle_step_click(0, state)
        # Đường test truyền step 1-based.
        with pytest.raises(PreventUpdate):
            page.handle_step_click(1, state, 1)

    def test_save_draft_step1_persists_changes(self, run_env, admin_ctx, monkeypatch):
        """Bấm Lưu nháp ở Step 1 cập nhật report_name và description vào DB."""
        import app.ui.pages.report_admin as page
        from app.services.report import get_report

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        state["step"] = 1

        new_state, notif = page.handle_save_draft_click(
            1,
            state,
            report_code="FIN_REVENUE",
            report_name="Doanh thu sửa mới",
            category_code="FINANCE",
            owner="FIN_LEAD",
            description="Mô tả vừa cập nhật",
            is_visible=True,
            default_favorite=False,
            tpl_code="REVENUE_DETAIL",
            tpl_name="Chi tiết doanh thu",
            display_order=10,
            timeout_sec=300,
            preview_max_rows=100,
            export_max_rows=1000000,
            s2_sql=None,
        )
        assert notif is not None
        assert "Đã lưu nháp" in _dump(notif)
        rep = get_report(admin_ctx, int(state["report_id"])).data
        assert rep["name"] == "Doanh thu sửa mới"
        assert rep["description"] == "Mô tả vừa cập nhật"

    def test_analyze_sql_auto_creates_new_bind_param(self, run_env, admin_ctx, monkeypatch):
        """Khi SQL có tham số bind :p_customer mới, phân tích SQL tự động tạo param."""
        import app.ui.pages.report_admin as page
        from app.services.report_template import get_version

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        _patch_describe(monkeypatch)
        state = _draft_state(run_env)
        sql_with_param = (
            "SELECT org_code, customer_id, amount "
            "FROM fin_revenue "
            "WHERE org_code = :p_org AND customer_id = :p_customer"
        )
        new_state, notif = page.handle_analyze_sql(1, state, sql_with_param)
        assert notif is not None
        assert "Đã phân tích" in _dump(notif)
        ver = get_version(admin_ctx, int(state["version_id"])).data
        param_codes = [p["code"] for p in ver["params"]]
        assert "p_customer" in param_codes

    def test_save_lov_updates_param_lov(self, run_env, admin_ctx, monkeypatch):
        """Lưu cấu hình LOV cho tham số."""
        import app.ui.pages.report_admin as page
        from app.services.report_template import get_version

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        state = _draft_state(run_env)
        ver = get_version(admin_ctx, int(state["version_id"])).data
        target_param = ver["params"][0]
        state["editing_param_id"] = target_param["id"]

        new_state, notif = page.handle_p_save_lov(
            1,
            state,
            lov_type="STATIC",
            lov_sql=None,
            lov_lookup=None,
            lov_static="ALL|Tất cả\nHN|Hà Nội\nHCM|TP Hồ Chí Minh",
            lov_cache=300,
        )
        assert notif is not None
        assert "Đã lưu cấu hình LOV" in _dump(notif)
        updated_ver = get_version(admin_ctx, int(state["version_id"])).data
        p_updated = next(p for p in updated_ver["params"] if p["id"] == target_param["id"])
        assert p_updated["lov"]["lov_type"] == "STATIC"
        assert len(p_updated["lov"]["static_json"]) == 3
