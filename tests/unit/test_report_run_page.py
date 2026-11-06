"""Tests cho Server-side count/page/filter/sort — Bước 2 task 25 (test viết trước).

get_report_page (T25-04/05) + helper thuần build_paged_query/build_count_query.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

from tests.unit.test_report_run_execute import (
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


def _paged_conn(all_rows, total):
    """Mock Oracle trả đúng lát cắt theo OFFSET/FETCH trong SQL."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = (total,)
    mock_cursor.description = [
        ("AMOUNT", None, 0, 0, 18, 2, True),
        ("ORG", None, 0, 0, 60, 0, True),
        ("TXN_DATE", None, 0, 0, 0, 0, True),
    ]

    def _execute(sql, binds=None):
        m = re.search(r"OFFSET (\d+) ROWS FETCH NEXT (\d+) ROWS ONLY", str(sql))
        if m:
            off, lim = int(m.group(1)), int(m.group(2))
            mock_cursor.fetchmany.return_value = all_rows[off : off + lim]

    mock_cursor.execute.side_effect = _execute
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


ALL_ROWS = [
    (1000, "HN", "2026-02-01"),
    (2000, "HN", "2026-02-02"),
    (3000, "HCM", "2026-02-03"),
    (4000, "HCM", "2026-02-04"),
    (5000, "HN", "2026-02-05"),
]


def _make_run(operator_ctx, run_env, template_key="sql_template_id"):
    from app.services.report_run import create_report_run

    res = create_report_run(
        operator_ctx,
        run_env["report_id"],
        template_id=run_env[template_key],
        values={"p_org": "HN"},
    )
    assert res.ok, res.message
    return res.data


class TestStablePagination:
    def test_pages_no_overlap_no_gap(self, run_env, operator_ctx):
        from app.services.report_run import get_report_page

        run = _make_run(operator_ctx, run_env)
        conn, _ = _paged_conn(ALL_ROWS, total=5)
        seen = []
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            for page in (1, 2, 3):
                res = get_report_page(operator_ctx, run["id"], page=page, page_size=2)
                assert res.ok, res.message
                assert res.data["total"] == 5
                seen.extend(r["AMOUNT"] for r in res.data["rows"])
        assert seen == [1000, 2000, 3000, 4000, 5000]

    def test_page_beyond_total_empty(self, run_env, operator_ctx):
        from app.services.report_run import get_report_page

        run = _make_run(operator_ctx, run_env)
        conn, _ = _paged_conn(ALL_ROWS, total=5)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = get_report_page(operator_ctx, run["id"], page=4, page_size=2)
        assert res.ok, res.message
        assert res.data["rows"] == []

    def test_page_validation(self, run_env, operator_ctx):
        from app.services.report_run import get_report_page

        run = _make_run(operator_ctx, run_env)
        for bad in ({"page": 0}, {"page_size": 0}, {"page_size": 201}):
            res = get_report_page(operator_ctx, run["id"], **bad)
            assert not res.ok and res.code == "VALIDATION_ERROR"


class TestSortFilterWhitelist:
    def test_sort_by_known_field(self, run_env, operator_ctx):
        from app.services.report_run import get_report_page

        run = _make_run(operator_ctx, run_env)
        conn, cursor = _paged_conn(ALL_ROWS, total=5)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = get_report_page(
                operator_ctx,
                run["id"],
                page=1,
                page_size=2,
                sorts=[{"field": "ORG", "direction": "DESC"}],
            )
        assert res.ok, res.message
        page_sql = next(
            str(c.args[0])
            for c in cursor.execute.call_args_list
            if "OFFSET" in str(c.args[0])
        )
        assert '"ORG" DESC' in page_sql
        # Tiebreaker cột đầu tiên (AMOUNT) vẫn có sau sort người dùng
        assert '"AMOUNT" ASC' in page_sql

    def test_sort_unknown_field_rejected(self, run_env, operator_ctx):
        from app.services.report_run import get_report_page

        run = _make_run(operator_ctx, run_env)
        res = get_report_page(
            operator_ctx,
            run["id"],
            page=1,
            page_size=2,
            sorts=[{"field": "HACK", "direction": "ASC"}],
        )
        assert not res.ok and res.code == "SQL_NOT_ALLOWED"

    def test_sort_bad_direction_rejected(self, run_env, operator_ctx):
        from app.services.report_run import get_report_page

        run = _make_run(operator_ctx, run_env)
        res = get_report_page(
            operator_ctx,
            run["id"],
            page=1,
            page_size=2,
            sorts=[{"field": "ORG", "direction": "SIDEWAYS"}],
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_view_filter_through_builder(self, run_env, operator_ctx):
        from app.services.report_run import create_report_run, get_report_page

        res = create_report_run(
            operator_ctx,
            run_env["report_id"],
            template_id=run_env["view_template_id"],
            values={"p_org": "HN", "p_amount_min": 1000},
        )
        assert res.ok, res.message
        run = res.data
        conn, cursor = _paged_conn(ALL_ROWS, total=5)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = get_report_page(operator_ctx, run["id"], page=1, page_size=2)
        assert res.ok, res.message
        count_sql = next(
            str(c.args[0])
            for c in cursor.execute.call_args_list
            if "COUNT(*)" in str(c.args[0])
        )
        assert '"FIN"."V_REVENUE"' in count_sql
        assert "HN" not in count_sql
        count_call = next(
            c
            for c in cursor.execute.call_args_list
            if "COUNT(*)" in str(c.args[0])
        )
        assert count_call.args[1] == {"p_org": "HN", "p_amount_min": 1000}


class TestPagedQueryHelpers:
    def test_build_helpers(self):
        from app.services.report_run import build_count_query, build_paged_query

        sql = "SELECT a FROM t WHERE x = :p_org"
        assert build_count_query(sql) == "SELECT COUNT(*) AS total FROM (\nSELECT a FROM t WHERE x = :p_org\n)"
        paged = build_paged_query(sql, 2, 50, '"ORG" DESC, "AMOUNT" ASC')
        assert paged.endswith("OFFSET 50 ROWS FETCH NEXT 50 ROWS ONLY")
        assert '"ORG" DESC' in paged
