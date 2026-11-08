"""Tests cho trang Xem báo cáo — Bước 2 task 27 (test viết trước).

T27-03 (template tabs), T27-04 (dynamic controls/LOV), T27-05 (row/span
layout), T27-06 (server pagination).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.context import Ctx
from tests.unit.test_report_export_queue import _done_run, export_env
from tests.unit.test_report_run_execute import (
    ROWS,
    _mock_ora_conn,
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)
from tests.unit.test_report_run_page import ALL_ROWS, _paged_conn

__all__ = ["export_env", "run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


def _dump(component) -> str:
    import json

    def conv(obj):
        if hasattr(obj, "to_plotly_json"):
            return obj.to_plotly_json()
        if isinstance(obj, (list, tuple)):
            return [conv(o) for o in obj]
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        return obj

    return json.dumps(conv(component), ensure_ascii=False, default=str)


class TestFormatCell:
    def test_number_masks(self):
        import app.ui.pages.report_viewer as page

        col = {"data_type": "NUMBER", "format_mask": "#,##0"}
        assert page._format_cell(10000000, col) == "10.000.000"
        col = {"data_type": "NUMBER", "format_mask": "#,##0.00"}
        assert page._format_cell(10000000, col) == "10.000.000,00"
        col = {"data_type": "NUMBER", "format_mask": "#,##0%"}
        assert page._format_cell(0.358, col) == "35,80%"
        assert page._format_cell(None, col) == "—"

    def test_date_masks(self):
        import app.ui.pages.report_viewer as page

        col = {"data_type": "DATE", "format_mask": "DD/MM/YYYY"}
        assert page._format_cell("2026-02-01", col) == "01/02/2026"
        col = {"data_type": "DATETIME", "format_mask": "DD/MM/YYYY HH:mm"}
        assert page._format_cell("2026-02-01T10:30:00", col) == "01/02/2026 10:30"

    def test_string_keeps_leading_zero(self):
        import app.ui.pages.report_viewer as page

        col = {"data_type": "STRING", "format_mask": None}
        assert page._format_cell("00123", col) == "00123"


class TestParamControls:
    def test_control_by_type(self):
        import app.ui.pages.report_viewer as page

        base = {"id": 1, "code": "p_x", "label": "X", "required": False, "grid_span": 3, "lov": {"lov_type": "NONE"}}
        date_c = page.render_param_control({**base, "data_type": "DATE", "control_type": "DATE"}, None)
        assert "DateInput" in _dump(date_c)
        text_c = page.render_param_control({**base, "data_type": "STRING", "control_type": "TEXT"}, None)
        assert "TextInput" in _dump(text_c)
        num_c = page.render_param_control({**base, "data_type": "NUMBER", "control_type": "NUMBER"}, None)
        assert "NumberInput" in _dump(num_c)
        sel_c = page.render_param_control(
            {
                **base,
                "data_type": "STRING",
                "control_type": "SELECT",
                "lov": {"lov_type": "STATIC", "static_values": [["A", "Mục A"], ["B", "Mục B"]]},
            },
            None,
        )
        dumped = _dump(sel_c)
        assert "Select" in dumped and "Mục A" in dumped
        multi_c = page.render_param_control(
            {
                **base,
                "data_type": "STRING",
                "control_type": "MULTI_SELECT",
                "lov": {"lov_type": "STATIC", "static_values": [["A", "Mục A"]]},
            },
            None,
        )
        assert "MultiSelect" in _dump(multi_c)
        range_c = page.render_param_control({**base, "data_type": "DATE", "control_type": "DATE_RANGE"}, None)
        assert _dump(range_c).count("DateInput") == 2

    def test_required_marker(self):
        import app.ui.pages.report_viewer as page

        param = {
            "id": 1,
            "code": "p_org",
            "label": "Đơn vị",
            "required": True,
            "data_type": "STRING",
            "control_type": "TEXT",
            "grid_span": 3,
            "lov": {"lov_type": "NONE"},
        }
        assert " *" in _dump(page.render_param_control(param, None))


class TestResultTable:
    def test_headers_and_rows(self):
        import app.ui.pages.report_viewer as page

        layout = {
            "columns": [
                {
                    "field_name": "AMOUNT",
                    "label": "Số tiền",
                    "data_type": "NUMBER",
                    "format_mask": "#,##0",
                    "alignment": "RIGHT",
                    "width": 120,
                    "is_total": False,
                },
                {
                    "field_name": "ORG",
                    "label": "Đơn vị",
                    "data_type": "STRING",
                    "format_mask": None,
                    "alignment": "LEFT",
                    "width": 180,
                    "is_total": False,
                },
            ]
        }
        rows = [{"AMOUNT": 10000000, "ORG": "00123"}, {"AMOUNT": 2000, "ORG": "HN"}]
        text = _dump(page.render_result_table(layout, rows))
        assert "Số tiền" in text and "Đơn vị" in text
        assert "10.000.000" in text
        assert "00123" in text

    def test_empty_rows(self):
        import app.ui.pages.report_viewer as page

        layout = {
            "columns": [
                {
                    "field_name": "AMOUNT",
                    "label": "Số tiền",
                    "data_type": "NUMBER",
                    "format_mask": None,
                    "alignment": "RIGHT",
                    "width": 120,
                    "is_total": False,
                },
            ]
        }
        text = _dump(page.render_result_table(layout, []))
        assert "Không có dòng nào" in text


class TestViewerLayout:
    def test_layout_operator_renders_tabs_and_form(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        text = _dump(page.layout(report_id=export_env["report_id"]))
        assert "Báo cáo doanh thu" in text or "FIN_REVENUE" in text
        assert "SQL1" in text  # tab template
        assert "Đơn vị" in text  # param p_org
        assert "Xem báo cáo" in text
        assert "Nhập tham số và bấm Xem báo cáo." in text

    def test_layout_no_active_version_note(self, export_env, operator_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        # Report chỉ có DRAFT: tạo report mới không template ACTIVE.
        # (pytest 9 cấm gọi fixture trực tiếp nên dựng Ctx admin tại chỗ.)
        from app.services.report import create_report

        res = create_report(
            Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"]),
            {"code": "DRAFT_ONLY", "name": "Chỉ nháp", "category_code": "FINANCE", "owner": "FIN"},
        )
        assert res.ok, res.message
        text = _dump(page.layout(report_id=res.data["id"]))
        assert "Chưa có template ACTIVE" in text

    def test_layout_forbidden_for_norole(self, export_env, norole_ctx, monkeypatch):
        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: norole_ctx)
        text = _dump(page.layout(report_id=export_env["report_id"]))
        assert "không có quyền" in text


class TestViewerRun:
    def test_run_without_click_noop(self, export_env, operator_ctx, monkeypatch):
        from dash.exceptions import PreventUpdate

        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        with pytest.raises(PreventUpdate):
            page.handle_run_click(None, 1, 1, ["HN"], [{"type": "viewer-param", "index": "p_org"}], 50)

    def test_run_renders_first_page(self, export_env, operator_ctx, monkeypatch):
        from unittest.mock import patch

        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            run_store, page_store, _error = page.handle_run_click(
                1,
                export_env["report_id"],
                export_env["sql_template_id"],
                ["HN"],
                [{"type": "viewer-param", "index": "p_org"}],
                50,
            )
            assert run_store["run_id"] is not None
            assert page_store == 1
            result_html, _count = page.handle_result_render(run_store, 1, [], 50)
        text = _dump(result_html)
        assert "1.000" in text
        assert "HN" in text

    def test_run_failed_shows_error(self, export_env, operator_ctx, monkeypatch):
        from unittest.mock import patch

        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        with patch(
            "app.services.report_source.open_source_connection",
            side_effect=RuntimeError("ORA-12154: TNS:could not resolve"),
        ):
            run_store, page_store, error = page.handle_run_click(
                1,
                export_env["report_id"],
                export_env["sql_template_id"],
                ["HN"],
                [{"type": "viewer-param", "index": "p_org"}],
                50,
            )
        assert run_store == {}
        assert page_store == 1
        text = _dump(error)
        assert "ORA-12154" in text

    def test_page_of_failed_run_is_clean_error(self, export_env, operator_ctx, monkeypatch):
        from unittest.mock import patch

        import app.ui.pages.report_viewer as page
        from app.services.report_run import get_report_page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        with patch(
            "app.services.report_source.open_source_connection",
            side_effect=RuntimeError("ORA-12154: TNS:could not resolve"),
        ):
            run_store, _page_store, _error = page.handle_run_click(
                1,
                export_env["report_id"],
                export_env["sql_template_id"],
                ["HN"],
                [{"type": "viewer-param", "index": "p_org"}],
                50,
            )
        # Run đã FAILED trong DB: mở lại trang phải báo lỗi rõ, không phải
        # "Lỗi hệ thống nội bộ".
        from app.services.report_run import list_report_runs

        runs = list_report_runs(operator_ctx, page=1, page_size=50)
        assert runs.ok and runs.data["total"] == 1
        failed_id = int(runs.data["runs"][0]["id"])
        res = get_report_page(operator_ctx, failed_id, page=1, page_size=50)
        assert not res.ok
        assert "Run đã lỗi" in res.message
        assert "ORA-12154" in res.message

    def test_page_change_server_pagination(self, export_env, operator_ctx, monkeypatch):
        from unittest.mock import patch

        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        run_store = {
            "run_id": run["id"],
            "template_id": export_env["sql_template_id"],
            "report_id": export_env["report_id"],
        }
        conn, _ = _paged_conn(ALL_ROWS, total=5)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            page_no = page.handle_page_change(2, run_store)
            assert page_no == 2
            result_html, _count = page.handle_result_render(run_store, 2, [], 2)
        text = _dump(result_html)
        # Trang 2 (page_size 2) → dòng 3, 4 (3.000/HCM, 4.000/HCM).
        assert "3.000" in text
        assert "HCM" in text
        assert "1.000" not in text

    def test_result_error_keeps_old_data_and_retry(self, export_env, operator_ctx, monkeypatch):
        """Lỗi tải trang: giữ bảng cũ + nút Thử lại, không trắng trang."""
        from dash import html

        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        engine = export_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE RECON_REPORT_RUN SET STATUS='FAILED', "
                    "ERROR_MESSAGE='ORA-12154: TNS:could not resolve' "
                    "WHERE ID=:i"
                ),
                {"i": run["id"]},
            )
        run_store = {
            "run_id": run["id"],
            "template_id": export_env["sql_template_id"],
            "report_id": export_env["report_id"],
        }
        old = [html.Div("OLD-TABLE-MARKER")]
        result_html, count = page.handle_result_render(run_store, 1, [], 50, old)
        assert count == "Lỗi tải kết quả"
        dumped = _dump(result_html)
        assert "OLD-TABLE-MARKER" in dumped
        assert "Thử lại" in dumped
        assert "ORA-12154" in dumped

    def test_result_render_with_sort_applies_sort(self, export_env, operator_ctx, monkeypatch):
        """Hồi quy: thứ tự tham số handle_result_render khớp decorator.

        Trước sửa, chữ ký (run_store, page_no, page_size, sorts) nhận nhầm
        sort-store vào page_size nên sort khác rỗng làm int(list) lỗi
        TypeError trên trình duyệt thật (test cũ chỉ truyền sorts=[] nên
        không lộ). Sort AMOUNT DESC, page_size 50 → dòng 5.000 lên đầu.
        """
        from unittest.mock import patch

        import app.ui.pages.report_viewer as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: operator_ctx)
        run = _done_run(operator_ctx, export_env)
        run_store = {
            "run_id": run["id"],
            "template_id": export_env["sql_template_id"],
            "report_id": export_env["report_id"],
        }
        conn, cursor = _paged_conn(ALL_ROWS, total=5)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result_html, _count = page.handle_result_render(
                run_store,
                1,
                [{"field": "AMOUNT", "direction": "DESC"}],
                50,
            )
        text = _dump(result_html)
        assert "5.000" in text
        # Sort phải tới được câu truy vấn (mock không tự sắp xếp dữ liệu).
        executed = " ".join(str(c.args[0]) for c in cursor.execute.call_args_list)
        assert "ORDER BY" in executed and "AMOUNT" in executed
        assert "DESC" in executed

    def test_result_table_renders_total_row(self):
        from app.ui.components.report_widgets import render_result_table

        layout = {
            "columns": [
                {"field_name": "CODE", "label": "Mã", "data_type": "STRING", "is_total": False},
                {"field_name": "AMOUNT", "label": "Số tiền", "data_type": "NUMBER", "format_mask": "#,##0", "alignment": "RIGHT", "is_total": True},
            ]
        }
        rows = [
            {"CODE": "A", "AMOUNT": 1000000},
            {"CODE": "B", "AMOUNT": 2500000},
        ]
        text = _dump(render_result_table(layout, rows))
        assert "Tổng cộng" in text
        assert "3.500.000" in text
        assert "TableTfoot" in text
