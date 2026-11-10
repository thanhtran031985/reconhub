"""Tests cho REPORT_RUN, bind/whitelist execution — Bước 1 task 25 (test viết trước).

create_report_run (T25-01), execute CUSTOM_SQL (T25-02), VIEW/TABLE (T25-03),
dry_run_version (đóng vòng T21-04).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx
from app.core.crypto import encrypt_secret
from app.db.metadata import (
    metadata,
    recon_report_template,
    recon_rpt_column,
    recon_rpt_tpl_ver,
)


@pytest.fixture()
def run_env(tmp_path, monkeypatch):
    db_path = tmp_path / "report_run.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.report",
        "app.services.report_template",
        "app.services.report_source",
        "app.services.report_param",
        "app.services.report_column",
        "app.services.report_run",
        "app.engine.catalog",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from app.services.report import create_report
    from app.services.report_param import create_param
    from app.services.report_template import create_template
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [(1, "admin"), (2, "operator"), (3, "norole")]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
        res = conn.execute(
            text(
                "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, HOST, "
                "PORT, SERVICE_NAME, USERNAME, PASSWORD_ENC, DEFAULT_SCHEMA, "
                "CALL_TIMEOUT_S, MAX_ROWS, IS_CURRENT_METADATA, IS_ACTIVE, CREATED_BY, "
                "CREATED_AT, UPDATED_AT) "
                "VALUES ('ORCL', 'DEV', 'SOURCE', 'ORACLE', '10.0.0.1', 1521, "
                "'ORCLPDB', 'RECON_RO', :pw, 'FIN', 30, 10000, 'N', 'Y', 'SEED', :now, :now)"
            ),
            {"pw": encrypt_secret("testPass"), "now": now},
        )
        ds_id = int(res.lastrowid)
    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["OPERATOR"]})
    clear_perm_cache()

    admin_ctx = Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
    res = create_report(
        admin_ctx,
        {
            "code": "FIN_REVENUE",
            "name": "Doanh thu",
            "category_code": "FIN",
            "owner": "admin",
            "is_visible": True,
        },
    )
    assert res.ok, res.message
    report_id = res.data["id"]

    def _make_template(code, **overrides):
        payload = {
            "code": code,
            "name": f"Mẫu {code}",
            "display_order": 10,
            "timeout_sec": 300,
            "preview_max_rows": 100,
            "export_max_rows": 1000000,
        }
        payload.update(overrides)
        res = create_template(admin_ctx, report_id, payload)
        assert res.ok, res.message
        data = dict(res.data)
        # create_template trả version dict (không có template_id) — tra thêm.
        with engine.connect() as conn:
            tpl_id = conn.execute(
                select(recon_report_template.c.ID).where(
                    recon_report_template.c.REPORT_ID == report_id,
                    recon_report_template.c.CODE == code,
                )
            ).scalar_one()
        data["template_id"] = int(tpl_id)
        return data

    sql_tpl = _make_template(
        "SQL1",
        data_source_id=ds_id,
        source_type="CUSTOM_SQL",
        sql_text="SELECT amount, org, txn_date FROM fin_revenue WHERE org = :p_org",
    )
    view_tpl = _make_template(
        "VIEW1",
        data_source_id=ds_id,
        source_type="VIEW",
        source_owner="FIN",
        source_object="V_REVENUE",
    )
    draft_tpl = _make_template(
        "DRAFT1",
        data_source_id=ds_id,
        source_type="CUSTOM_SQL",
        sql_text="SELECT amount, org FROM fin_revenue WHERE org = :p_org",
    )

    # Param p_org (CUSTOM_SQL + VIEW) và p_amount_min (VIEW filter >=).
    for tpl, params in (
        (
            sql_tpl,
            [
                {
                    "code": "p_org",
                    "label": "Đơn vị",
                    "data_type": "STRING",
                    "control_type": "TEXT",
                    "required": True,
                    "filter_column": "ORG",
                    "filter_operator": "=",
                }
            ],
        ),
        (
            view_tpl,
            [
                {
                    "code": "p_org",
                    "label": "Đơn vị",
                    "data_type": "STRING",
                    "control_type": "TEXT",
                    "required": True,
                    "filter_column": "ORG",
                    "filter_operator": "=",
                },
                {
                    "code": "p_amount_min",
                    "label": "Số tiền tối thiểu",
                    "data_type": "NUMBER",
                    "control_type": "NUMBER",
                    "required": False,
                    "filter_column": "AMOUNT",
                    "filter_operator": ">=",
                },
            ],
        ),
        (
            draft_tpl,
            [
                {
                    "code": "p_org",
                    "label": "Đơn vị",
                    "data_type": "STRING",
                    "control_type": "TEXT",
                    "required": True,
                    "filter_column": "ORG",
                    "filter_operator": "=",
                }
            ],
        ),
    ):
        for p in params:
            res = create_param(admin_ctx, tpl["id"], p)
            assert res.ok, res.message

    with engine.begin() as conn:
        for tpl in (sql_tpl, view_tpl, draft_tpl):
            for order, (field, dtype) in enumerate(
                [("AMOUNT", "NUMBER"), ("ORG", "STRING"), ("TXN_DATE", "DATE")]
            ):
                conn.execute(
                    recon_rpt_column.insert().values(
                        VERSION_ID=tpl["id"],
                        FIELD_NAME=field,
                        LABEL=field,
                        DATA_TYPE=dtype,
                        DISPLAY_ORDER=(order + 1) * 10,
                        WEB_VISIBLE="Y",
                        EXCEL_VISIBLE="Y",
                        ALIGNMENT="LEFT",
                        IS_TOTAL="N",
                    )
                )
        # SQL1 + VIEW1 thành ACTIVE; DRAFT1 giữ DRAFT.
        for tpl in (sql_tpl, view_tpl):
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == tpl["id"])
                .values(STATUS="ACTIVE")
            )
            conn.execute(
                recon_report_template.update()
                .where(recon_report_template.c.ID == tpl["template_id"])
                .values(ACTIVE_VERSION_ID=tpl["id"])
            )
    return {
        "engine": engine,
        "ds_id": ds_id,
        "report_id": report_id,
        "sql_template_id": sql_tpl["template_id"],
        "sql_version_id": sql_tpl["id"],
        "view_template_id": view_tpl["template_id"],
        "view_version_id": view_tpl["id"],
        "draft_version_id": draft_tpl["id"],
    }


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


@pytest.fixture()
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])


@pytest.fixture()
def norole_ctx() -> Ctx:
    return Ctx(user_id=3, username="norole", full_name="norole", roles=[])


def _mock_ora_conn(rows, total=3):
    """Mock Oracle: count → fetchone (total,), page → fetchmany rows."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = (total,)
    mock_cursor.fetchmany.return_value = rows
    mock_cursor.description = [
        ("AMOUNT", None, 0, 0, 18, 2, True),
        ("ORG", None, 0, 0, 60, 0, True),
        ("TXN_DATE", None, 0, 0, 0, 0, True),
    ]
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


ROWS = [
    (1000, "HN", "2026-02-01"),
    (2000, "HN", "2026-02-02"),
    (3000, "HN", "2026-02-03"),
]


class TestCreateReportRun:
    def test_snapshot_params_and_version(self, run_env, operator_ctx):
        from app.services.report_run import create_report_run

        res = create_report_run(
            operator_ctx,
            run_env["report_id"],
            template_id=run_env["sql_template_id"],
            values={"p_org": "HN"},
        )
        assert res.ok, res.message
        assert res.data["status"] == "QUEUED"
        assert res.data["version_id"] == run_env["sql_version_id"]
        assert res.data["params"] == {"p_org": "HN"}
        assert res.data["created_by"] == "operator"

    def test_create_without_template_picks_active(self, run_env, operator_ctx):
        from app.services.report_run import create_report_run

        res = create_report_run(
            operator_ctx, run_env["report_id"], values={"p_org": "HN"}
        )
        assert res.ok, res.message
        # Template đầu tiên theo display order có ACTIVE version
        assert res.data["version_id"] in (
            run_env["sql_version_id"],
            run_env["view_version_id"],
        )

    def test_create_missing_required_param(self, run_env, operator_ctx):
        from app.services.report_run import create_report_run

        res = create_report_run(
            operator_ctx,
            run_env["report_id"],
            template_id=run_env["sql_template_id"],
            values={},
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_create_forbidden_without_menu(self, run_env, norole_ctx):
        from app.services.report_run import create_report_run

        res = create_report_run(
            norole_ctx,
            run_env["report_id"],
            template_id=run_env["sql_template_id"],
            values={"p_org": "HN"},
        )
        assert not res.ok and res.code == "FORBIDDEN"


class TestExecuteReportRun:
    def test_execute_custom_sql(self, run_env, operator_ctx):
        from app.services.report_run import create_report_run, execute_report_run

        run = create_report_run(
            operator_ctx,
            run_env["report_id"],
            template_id=run_env["sql_template_id"],
            values={"p_org": "HN"},
        ).data
        conn, cursor = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = execute_report_run(operator_ctx, run["id"])
        assert res.ok, res.message
        assert res.data["run"]["status"] == "DONE"
        assert res.data["run"]["row_count"] == 3
        assert res.data["run"]["query_ms"] is not None
        assert res.data["total"] == 3
        assert res.data["rows"] == [
            {"AMOUNT": 1000, "ORG": "HN", "TXN_DATE": "2026-02-01"},
            {"AMOUNT": 2000, "ORG": "HN", "TXN_DATE": "2026-02-02"},
            {"AMOUNT": 3000, "ORG": "HN", "TXN_DATE": "2026-02-03"},
        ]
        executed = [str(c.args[0]) for c in cursor.execute.call_args_list]
        assert any("COUNT(*)" in s for s in executed)
        assert any("OFFSET 0 ROWS FETCH NEXT 50 ROWS ONLY" in s for s in executed)
        # Bind đúng giá trị, không nối chuỗi
        count_call = next(c for c in cursor.execute.call_args_list if "COUNT(*)" in str(c.args[0]))
        assert count_call.args[1] == {"p_org": "HN"}

    def test_execute_view_table_whitelist(self, run_env, operator_ctx):
        from app.services.report_run import create_report_run, execute_report_run

        run = create_report_run(
            operator_ctx,
            run_env["report_id"],
            template_id=run_env["view_template_id"],
            values={"p_org": "HN", "p_amount_min": 1000},
        ).data
        conn, cursor = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = execute_report_run(operator_ctx, run["id"])
        assert res.ok, res.message
        assert res.data["run"]["status"] == "DONE"
        executed = [str(c.args[0]) for c in cursor.execute.call_args_list]
        sql = next(s for s in executed if "COUNT(*)" in s)
        assert '"FIN"."V_REVENUE"' in sql
        assert "HN" not in sql  # giá trị chỉ đi qua bind
        count_call = next(c for c in cursor.execute.call_args_list if "COUNT(*)" in str(c.args[0]))
        assert count_call.args[1] == {"p_org": "HN", "p_amount_min": 1000}

    def test_execute_twice_rejected(self, run_env, operator_ctx):
        from app.services.report_run import create_report_run, execute_report_run

        run = create_report_run(
            operator_ctx,
            run_env["report_id"],
            template_id=run_env["sql_template_id"],
            values={"p_org": "HN"},
        ).data
        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            assert execute_report_run(operator_ctx, run["id"]).ok
            res = execute_report_run(operator_ctx, run["id"])
        assert not res.ok and res.code == "VALIDATION_ERROR"

    def test_execute_forbidden_without_menu(self, run_env, operator_ctx):
        from app.services.report_run import create_report_run, execute_report_run

        run = create_report_run(
            operator_ctx,
            run_env["report_id"],
            template_id=run_env["sql_template_id"],
            values={"p_org": "HN"},
        ).data
        # Người không có menu report_center bị chặn ngay ở cổng menu
        other = Ctx(user_id=3, username="norole", full_name="norole", roles=[])
        res = execute_report_run(other, run["id"])
        assert not res.ok and res.code == "FORBIDDEN"

    def test_execute_oracle_timeout_marks_failed(self, run_env, operator_ctx):
        from app.services.report_run import create_report_run, execute_report_run

        run = create_report_run(
            operator_ctx,
            run_env["report_id"],
            template_id=run_env["sql_template_id"],
            values={"p_org": "HN"},
        ).data
        conn, cursor = _mock_ora_conn(ROWS)
        cursor.execute.side_effect = Exception("ORA-01013: user requested cancel")
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = execute_report_run(operator_ctx, run["id"])
        assert res.ok, res.message  # execute trả run FAILED, không raise
        assert res.data["run"]["status"] == "FAILED"
        assert res.data["run"]["error_code"] == "SOURCE_TIMEOUT"


class TestDryRunVersion:
    def test_dry_run_activates_draft(self, run_env, admin_ctx):
        from app.services.report_run import dry_run_version

        conn, cursor = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = dry_run_version(
                admin_ctx, run_env["draft_version_id"], {"p_org": "HN"}
            )
        assert res.ok, res.message
        # Task 36: không chạy COUNT nữa nên không biết tổng; chỉ lấy trang xem trước.
        assert res.data["total"] is None
        assert len(res.data["rows"]) == 3
        assert all("COUNT(" not in str(c.args[0]) for c in cursor.execute.call_args_list)
        engine = run_env["engine"]
        with engine.connect() as db:
            row = db.execute(
                select(recon_rpt_tpl_ver.c.STATUS).where(
                    recon_rpt_tpl_ver.c.ID == run_env["draft_version_id"]
                )
            ).scalar_one()
        assert row == "DRY_RUN_OK"

    def test_dry_run_caps_rows_at_10(self, run_env, admin_ctx):
        """Hồi quy task 36: version lưu preview_max_rows=500 thì dry-run vẫn tối đa 10 dòng, không COUNT."""
        from app.services.report_run import dry_run_version

        engine = run_env["engine"]
        with engine.begin() as db:
            db.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == run_env["draft_version_id"])
                .values(PREVIEW_MAX_ROWS=500)
            )
        rows = [(i, "HN", "2026-02-01") for i in range(500)]
        conn, cursor = _mock_ora_conn(rows, total=500)
        cursor.fetchmany.side_effect = lambda n: rows[:n]
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = dry_run_version(
                admin_ctx, run_env["draft_version_id"], {"p_org": "HN"}
            )
        assert res.ok, res.message
        assert res.data["total"] is None
        assert len(res.data["rows"]) == 10
        assert all("COUNT(" not in str(c.args[0]) for c in cursor.execute.call_args_list)
        paged_sql = next(
            str(c.args[0])
            for c in cursor.execute.call_args_list
            if "FETCH NEXT" in str(c.args[0])
        )
        assert "FETCH NEXT 10 ROWS ONLY" in paged_sql

    def test_dry_run_failure_keeps_draft(self, run_env, admin_ctx):
        from app.services.report_run import dry_run_version

        conn, cursor = _mock_ora_conn(ROWS)
        cursor.execute.side_effect = Exception("ORA-00942: table or view does not exist")
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = dry_run_version(
                admin_ctx, run_env["draft_version_id"], {"p_org": "HN"}
            )
        assert not res.ok and res.code == "SOURCE_QUERY_FAILED"
        engine = run_env["engine"]
        with engine.connect() as db:
            row = db.execute(
                select(recon_rpt_tpl_ver.c.STATUS).where(
                    recon_rpt_tpl_ver.c.ID == run_env["draft_version_id"]
                )
            ).scalar_one()
        assert row == "DRAFT"

    def test_dry_run_forbidden_for_operator(self, run_env, operator_ctx):
        from app.services.report_run import dry_run_version

        res = dry_run_version(
            operator_ctx, run_env["draft_version_id"], {"p_org": "HN"}
        )
        assert not res.ok and res.code == "FORBIDDEN"

    def test_dry_run_active_is_preview_only(self, run_env, admin_ctx):
        """Task 34: dry-run version ACTIVE chỉ xem trước, giữ nguyên ACTIVE."""
        from app.services.report_run import dry_run_version

        conn, _ = _mock_ora_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection", return_value=conn
        ):
            res = dry_run_version(
                admin_ctx, run_env["sql_version_id"], {"p_org": "HN"}
            )
        assert res.ok, res.message
        assert res.data["total"] is None
        assert res.data["status"] == "ACTIVE"
        engine = run_env["engine"]
        with engine.connect() as db:
            row = db.execute(
                select(recon_rpt_tpl_ver.c.STATUS).where(
                    recon_rpt_tpl_ver.c.ID == run_env["sql_version_id"]
                )
            ).scalar_one()
        assert row == "ACTIVE"
        with engine.connect() as db:
            tpl = db.execute(
                select(recon_report_template.c.ACTIVE_VERSION_ID).where(
                    recon_report_template.c.ID == run_env["sql_template_id"]
                )
            ).scalar_one()
        assert tpl == run_env["sql_version_id"]

    def test_dry_run_archived_rejected(self, run_env, admin_ctx):
        """Task 34: version đã lưu trữ không dry-run được."""
        from app.services.report_run import dry_run_version

        engine = run_env["engine"]
        with engine.begin() as db:
            db.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == run_env["draft_version_id"])
                .values(STATUS="ARCHIVED")
            )
        res = dry_run_version(
            admin_ctx, run_env["draft_version_id"], {"p_org": "HN"}
        )
        assert not res.ok and res.code == "VALIDATION_ERROR"
