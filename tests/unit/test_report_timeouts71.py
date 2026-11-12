"""Tests task 71 — timeout truy vấn báo cáo cấu hình trên /settings.

- Setting REPORT_COUNT_TIMEOUT_SEC / REPORT_DATA_TIMEOUT_SEC: mặc định 300,
  giá trị lưu thắng, giá trị sai/vượt khoảng → 300; chỉ ADMIN đổi được.
- _execute_count_page tôn trọng setting: count dùng count timeout, data
  dùng data timeout (bỏ chặn cứng min(..., 30)); lỗi timeout hiện đúng
  số giây của setting.
- _execute_preview (dry-run) dùng data timeout.
- Trang /settings có 2 ô nhập timeout, mặc định 300.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.db.metadata import recon_app_setting
from tests.unit.test_report_run_execute import admin_ctx, operator_ctx, run_env

__all__ = ["run_env", "admin_ctx", "operator_ctx"]


def _set_raw(engine, key, value):
    with engine.begin() as conn:
        conn.execute(
            recon_app_setting.insert().values(
                KEY=key,
                VALUE=value,
                UPDATED_BY="admin",
                UPDATED_AT=datetime(2026, 11, 12),
            )
        )


def _fake_checked_connection(calls, fail_count_with=None):
    """Fake open_checked_connection: ghi lại timeout_sec, trả mock Oracle."""

    @contextmanager
    def _open(ds_id, timeout_sec):
        calls.append(int(timeout_sec))
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("AMOUNT", None, 0, 0, 18, 2, True),
            ("ORG", None, 0, 0, 60, 0, True),
            ("TXN_DATE", None, 0, 0, 0, 0, True),
        ]
        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.fetchmany.return_value = [(1000, "HN", "2026-02-01")]

        def _execute(sql, binds=None):
            if fail_count_with and "COUNT(*)" in str(sql):
                raise Exception(fail_count_with)

        mock_cursor.execute.side_effect = _execute
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    return _open


def _make_run(operator_ctx, run_env):
    from app.services.report_run import create_report_run

    res = create_report_run(
        operator_ctx,
        run_env["report_id"],
        template_id=run_env["sql_template_id"],
        values={"p_org": "HN"},
    )
    assert res.ok, res.message
    return res.data


class TestReportTimeoutSettings:
    def test_defaults_are_300(self, run_env):
        from app.services.report_timeouts import get_report_timeouts

        assert get_report_timeouts(run_env["engine"]) == {
            "count_timeout_sec": 300,
            "data_timeout_sec": 300,
        }

    def test_set_wins(self, run_env, admin_ctx):
        from app.services.report_timeouts import (
            get_report_timeout_settings,
            get_report_timeouts,
            set_report_timeouts,
        )

        assert set_report_timeouts(admin_ctx, 60, 120).ok
        assert get_report_timeouts(run_env["engine"]) == {
            "count_timeout_sec": 60,
            "data_timeout_sec": 120,
        }
        assert get_report_timeout_settings(admin_ctx).data == {
            "count_timeout_sec": 60,
            "data_timeout_sec": 120,
        }

    def test_invalid_stored_value_falls_back_to_300(self, run_env):
        from app.services.report_timeouts import get_report_timeouts

        _set_raw(run_env["engine"], "REPORT_COUNT_TIMEOUT_SEC", "abc")
        _set_raw(run_env["engine"], "REPORT_DATA_TIMEOUT_SEC", "0")
        assert get_report_timeouts(run_env["engine"]) == {
            "count_timeout_sec": 300,
            "data_timeout_sec": 300,
        }

    def test_out_of_range_stored_value_falls_back_to_300(self, run_env):
        from app.services.report_timeouts import get_report_timeouts

        _set_raw(run_env["engine"], "REPORT_COUNT_TIMEOUT_SEC", "9999")
        _set_raw(run_env["engine"], "REPORT_DATA_TIMEOUT_SEC", "-5")
        assert get_report_timeouts(run_env["engine"]) == {
            "count_timeout_sec": 300,
            "data_timeout_sec": 300,
        }

    def test_set_invalid_rejected(self, run_env, admin_ctx):
        from app.services.report_timeouts import set_report_timeouts

        assert not set_report_timeouts(admin_ctx, 0, 300).ok
        assert not set_report_timeouts(admin_ctx, 300, 3601).ok
        assert not set_report_timeouts(admin_ctx, "x", 300).ok
        assert not set_report_timeouts(admin_ctx, 300, "y").ok

    def test_operator_cannot_manage(self, run_env, operator_ctx):
        from app.services.report_timeouts import (
            get_report_timeout_settings,
            set_report_timeouts,
        )

        assert not set_report_timeouts(operator_ctx, 60, 120).ok
        assert not get_report_timeout_settings(operator_ctx).ok


class TestCountPageUsesSettings:
    def test_count_and_data_use_settings(self, run_env, operator_ctx, admin_ctx):
        from app.services.report_run import get_report_page
        from app.services.report_timeouts import set_report_timeouts

        assert set_report_timeouts(admin_ctx, 60, 120).ok
        run = _make_run(operator_ctx, run_env)
        calls: list[int] = []
        with patch(
            "app.services.report_run.open_checked_connection",
            side_effect=_fake_checked_connection(calls),
        ):
            res = get_report_page(operator_ctx, run["id"], page=1, page_size=2)
        assert res.ok, res.message
        assert res.data["total"] == 5
        assert calls == [60, 120]

    def test_defaults_no_30s_cap(self, run_env, operator_ctx):
        # Không setting → count 300, data 300 (trước fix count bị chặn 30).
        from app.services.report_run import get_report_page

        run = _make_run(operator_ctx, run_env)
        calls: list[int] = []
        with patch(
            "app.services.report_run.open_checked_connection",
            side_effect=_fake_checked_connection(calls),
        ):
            res = get_report_page(operator_ctx, run["id"], page=1, page_size=2)
        assert res.ok, res.message
        assert calls == [300, 300]

    def test_count_timeout_error_message_uses_setting(self, run_env, operator_ctx, admin_ctx):
        from app.services.report_run import get_report_page
        from app.services.report_timeouts import set_report_timeouts

        assert set_report_timeouts(admin_ctx, 1, 300).ok
        run = _make_run(operator_ctx, run_env)
        calls: list[int] = []
        with patch(
            "app.services.report_run.open_checked_connection",
            side_effect=_fake_checked_connection(
                calls,
                fail_count_with="ORA-01013: user requested cancel of current operation",
            ),
        ):
            res = get_report_page(operator_ctx, run["id"], page=1, page_size=2)
        assert not res.ok
        assert "(1 giây)" in (res.message or "")
        assert calls == [1]

    def test_preview_uses_data_setting(self, run_env, admin_ctx):
        from app.services.report_run import dry_run_version
        from app.services.report_timeouts import set_report_timeouts

        assert set_report_timeouts(admin_ctx, 60, 90).ok
        calls: list[int] = []
        with patch(
            "app.services.report_run.open_checked_connection",
            side_effect=_fake_checked_connection(calls),
        ):
            res = dry_run_version(admin_ctx, run_env["sql_version_id"], {"p_org": "HN"})
        assert res.ok, res.message
        assert calls == [90]


class TestSettingsPageTimeouts:
    def test_layout_has_timeout_inputs(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.settings as page
        from tests.unit.test_report_viewer_fixes40 import _find_by_id

        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        tree = page.layout()
        count_input = _find_by_id(tree, "settings-count-timeout-input")
        data_input = _find_by_id(tree, "settings-data-timeout-input")
        assert count_input is not None
        assert data_input is not None
        assert count_input.value == 300
        assert data_input.value == 300

    def test_layout_shows_saved_values(self, run_env, admin_ctx, monkeypatch):
        import app.ui.pages.settings as page
        from app.services.report_timeouts import set_report_timeouts
        from tests.unit.test_report_viewer_fixes40 import _find_by_id

        assert set_report_timeouts(admin_ctx, 60, 120).ok
        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        tree = page.layout()
        assert _find_by_id(tree, "settings-count-timeout-input").value == 60
        assert _find_by_id(tree, "settings-data-timeout-input").value == 120
