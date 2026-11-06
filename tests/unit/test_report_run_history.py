"""Tests cho History, preset, favorite, owner scope — Bước 4 task 25 (test viết trước).

list/get_report_run (T25-09/10), preset + favorite (T25-08).
"""

from __future__ import annotations

from unittest.mock import patch

from tests.unit.test_report_run_cancel import _add_operator2, _make_run
from tests.unit.test_report_run_execute import (
    ROWS,
    _mock_ora_conn,
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


class TestOwnerScope:
    def test_user_b_open_run_a_not_found(self, run_env, operator_ctx):
        from app.services.report_run import get_report_run, list_report_runs

        run = _make_run(operator_ctx, run_env)
        other = _add_operator2(run_env["engine"])
        res = get_report_run(other, run["id"])
        assert not res.ok and res.code == "NOT_FOUND"
        res = list_report_runs(other)
        assert res.ok, res.message
        assert res.data["total"] == 0
        assert res.data["runs"] == []

    def test_admin_sees_all(self, run_env, operator_ctx, admin_ctx):
        from app.services.report_run import get_report_run, list_report_runs

        run = _make_run(operator_ctx, run_env)
        res = get_report_run(admin_ctx, run["id"])
        assert res.ok, res.message
        assert res.data["created_by"] == "operator"
        res = list_report_runs(admin_ctx)
        assert res.ok, res.message
        assert res.data["total"] == 1

    def test_history_filters(self, run_env, operator_ctx):
        from app.services.report_run import (
            execute_report_run,
            list_report_runs,
        )

        run1 = _make_run(operator_ctx, run_env)
        run2 = _make_run(operator_ctx, run_env)
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            assert execute_report_run(operator_ctx, run1["id"]).ok
        res = list_report_runs(operator_ctx, status="DONE")
        assert res.ok, res.message
        assert res.data["total"] == 1
        assert res.data["runs"][0]["id"] == run1["id"]
        res = list_report_runs(operator_ctx, status="QUEUED")
        assert res.data["total"] == 1
        assert res.data["runs"][0]["id"] == run2["id"]
        res = list_report_runs(operator_ctx, report_id=run_env["report_id"])
        assert res.data["total"] == 2
        res = list_report_runs(operator_ctx, report_id=99999)
        assert res.data["total"] == 0


class TestPresetFavorite:
    def test_favorite_toggle(self, run_env, operator_ctx):
        from app.services.report import list_reports, set_report_favorite

        res = set_report_favorite(operator_ctx, run_env["report_id"], True)
        assert res.ok, res.message
        assert res.data["is_favorite"] is True
        reports = list_reports(operator_ctx).data
        mine = next(r for r in reports if r["id"] == run_env["report_id"])
        assert mine["is_favorite"] is True
        res = set_report_favorite(operator_ctx, run_env["report_id"], False)
        assert res.ok, res.message
        assert res.data["is_favorite"] is False

    def test_preset_crud(self, run_env, operator_ctx):
        from app.services.report_run import (
            apply_preset,
            create_preset,
            delete_preset,
            list_presets,
        )

        res = create_preset(
            operator_ctx,
            run_env["report_id"],
            run_env["sql_template_id"],
            "Hà Nội",
            {"p_org": "HN"},
        )
        assert res.ok, res.message
        assert res.data["name"] == "Hà Nội"
        assert res.data["params"] == {"p_org": "HN"}
        assert res.data["is_default"] is False
        preset_id = res.data["id"]
        res = list_presets(
            operator_ctx, run_env["report_id"], run_env["sql_template_id"]
        )
        assert res.ok, res.message
        assert len(res.data) == 1
        res = apply_preset(operator_ctx, preset_id)
        assert res.ok, res.message
        assert res.data["values"] == {"p_org": "HN"}
        res = delete_preset(operator_ctx, preset_id)
        assert res.ok, res.message
        assert list_presets(
            operator_ctx, run_env["report_id"], run_env["sql_template_id"]
        ).data == []

    def test_preset_default_unique(self, run_env, operator_ctx):
        from app.services.report_run import create_preset, list_presets

        res_a = create_preset(
            operator_ctx,
            run_env["report_id"],
            run_env["sql_template_id"],
            "A",
            {"p_org": "HN"},
            is_default=True,
        )
        assert res_a.ok, res_a.message
        res_b = create_preset(
            operator_ctx,
            run_env["report_id"],
            run_env["sql_template_id"],
            "B",
            {"p_org": "HCM"},
            is_default=True,
        )
        assert res_b.ok, res_b.message
        presets = list_presets(
            operator_ctx, run_env["report_id"], run_env["sql_template_id"]
        ).data
        by_name = {p["name"]: p for p in presets}
        assert by_name["A"]["is_default"] is False
        assert by_name["B"]["is_default"] is True

    def test_preset_validation(self, run_env, operator_ctx):
        from app.services.report_run import create_preset, delete_preset

        res = create_preset(
            operator_ctx,
            run_env["report_id"],
            run_env["sql_template_id"],
            "Thiếu param",
            {},
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        res = create_preset(
            operator_ctx,
            run_env["report_id"],
            run_env["sql_template_id"],
            "   ",
            {"p_org": "HN"},
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
        res = create_preset(
            operator_ctx,
            run_env["report_id"],
            run_env["sql_template_id"],
            "X",
            {"p_org": "HN"},
        )
        assert res.ok, res.message
        other = _add_operator2(run_env["engine"])
        res = delete_preset(other, res.data["id"])
        assert not res.ok and res.code == "NOT_FOUND"
