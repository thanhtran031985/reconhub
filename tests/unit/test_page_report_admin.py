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


class TestStep1:
    def test_render_step1_fields(self):
        import app.ui.pages.report_admin as page

        text = _dump(page.render_step_content(1, _fresh_state()))
        assert "Mã báo cáo" in text
        assert "Tên báo cáo" in text
        assert "Mã template" in text
        assert "Lưu và tiếp tục" in text

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
        assert "Thêm tham số" in text
        assert "Tự sắp xếp" in text

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

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        state = _draft_state(run_env)
        state["version_id"] = vid
        text = _dump(page.render_step_content(4, state))
        assert "Cấu hình cột" in text
        assert "AMOUNT" in text
        assert "Khôi phục thứ tự" in text

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

    def test_column_move_and_restore(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.report_admin as page
        from app.services.report_column import list_columns

        vid = self._draft_with_columns(run_env, admin_ctx, monkeypatch)
        cols = list_columns(admin_ctx, vid).data
        first = cols[0]
        ok, _ = page.handle_column_move(1, _draft_state(run_env) | {"version_id": vid}, first["id"], "down")
        assert ok is True
        ok, _ = page.handle_restore_order(1, _draft_state(run_env) | {"version_id": vid})
        assert ok is True
        cols = list_columns(admin_ctx, vid).data
        assert cols[0]["field_name"] == "AMOUNT"


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
        assert result is not None and result["total"] == 3
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
        assert "dry-run" in _dump(alert).lower()

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
