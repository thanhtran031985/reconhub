"""Tests tích hợp task 28 bước 1 — menu/owner_filter/PROD (T28-01..T28-04).

Dùng fixture run_env/export_env có sẵn (test_report_run_execute,
test_report_export_queue): DB SQLite tạm, DS DEV, report FIN_REVENUE,
template CUSTOM_SQL ACTIVE + DRAFT, operator/admin/norole.
"""

from __future__ import annotations

from sqlalchemy import text

from tests.unit.test_report_export_queue import _done_run, _request, export_env
from tests.unit.test_report_run_execute import (
    admin_ctx,
    norole_ctx,
    operator_ctx,
    run_env,
)

__all__ = ["export_env", "run_env", "admin_ctx", "operator_ctx", "norole_ctx"]


class TestReportMenusSeeded:
    def test_menus_in_registry(self):
        from app.ui.menus import MENU_BY_CODE, ROLE_MENUS_SEED

        for code in ("report_center", "report_history", "report_admin"):
            assert code in MENU_BY_CODE, f"thiếu menu {code}"
        assert MENU_BY_CODE["report_center"].group == "DOI_SOAT"
        assert MENU_BY_CODE["report_history"].group == "DOI_SOAT"
        assert MENU_BY_CODE["report_admin"].group == "QUAN_TRI"
        for role in ("TEMPLATE_OWNER", "OPERATOR", "VIEWER"):
            assert "report_center" in ROLE_MENUS_SEED[role]
            assert "report_history" in ROLE_MENUS_SEED[role]
            assert "report_admin" not in ROLE_MENUS_SEED[role]

    def test_sync_creates_menus_and_assigns(self, run_env):
        from app.services.menu_sync import sync_from_code
        from app.services.perm import effective_menus

        engine = run_env["engine"]
        sync_from_code(engine)
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT CODE FROM RECON_MENU WHERE CODE LIKE 'report_%'")).fetchall()
        assert {r[0] for r in rows} == {
            "report_center",
            "report_history",
            "report_admin",
        }
        # Operator có center/history, không có admin; ADMIN có tất cả.
        from app.core.context import Ctx

        op = Ctx(user_id=2, username="operator", full_name="operator", roles=["OPERATOR"])
        menus = effective_menus(op, engine)
        assert "report_center" in menus and "report_history" in menus
        assert "report_admin" not in menus
        admin = Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])
        assert "report_admin" in effective_menus(admin, engine)

    def test_pages_declare_report_menu_codes(self):
        import app.ui.pages.report_admin as admin_page
        import app.ui.pages.report_runs as runs_page
        import app.ui.pages.report_viewer as viewer_page
        import app.ui.pages.reports as center_page

        assert center_page.MENU_CODE == "report_center"
        assert viewer_page.MENU_CODE == "report_center"
        assert runs_page.MENU_CODE == "report_history"
        assert admin_page.MENU_CODE == "report_admin"


class TestOwnerScope:
    def test_operator_sees_only_own_runs(self, export_env, operator_ctx, admin_ctx, monkeypatch):
        from unittest.mock import patch

        from app.services.report_run import get_report_run, list_report_runs
        from tests.unit.test_report_run_execute import ROWS, _mock_ora_conn

        monkeypatch.setattr("app.services.report_run.get_recon_engine", lambda: export_env["engine"])
        conn, _ = _mock_ora_conn(ROWS)
        with patch("app.services.report_source.open_source_connection", return_value=conn):
            op_run = _done_run(operator_ctx, export_env)
            admin_run = _done_run(admin_ctx, export_env)
        listed = list_report_runs(operator_ctx, page=1, page_size=50)
        assert listed.ok
        ids = {r["id"] for r in listed.data["runs"]}
        assert op_run["id"] in ids
        assert admin_run["id"] not in ids
        # get run người khác → NOT_FOUND (không lộ tồn tại).
        other = get_report_run(operator_ctx, admin_run["id"])
        assert not other.ok
        assert other.code == "NOT_FOUND"
        mine = get_report_run(operator_ctx, op_run["id"])
        assert mine.ok
        # ADMIN thấy tất cả.
        listed_admin = list_report_runs(admin_ctx, page=1, page_size=50)
        ids_admin = {r["id"] for r in listed_admin.data["runs"]}
        assert op_run["id"] in ids_admin and admin_run["id"] in ids_admin

    def test_operator_cannot_download_others_export(self, export_env, operator_ctx, admin_ctx, monkeypatch):
        from unittest.mock import patch

        from app.services.report_export import download_export, execute_export, get_export
        from tests.unit.test_report_export_queue import _mock_stream_conn
        from tests.unit.test_report_run_execute import ROWS

        monkeypatch.setattr("app.services.report_export.get_recon_engine", lambda: export_env["engine"])
        monkeypatch.setattr("app.services.report_run.get_recon_engine", lambda: export_env["engine"])
        admin_run = _done_run(admin_ctx, export_env)
        exp = _request(admin_ctx, export_env, admin_run["id"], fmt="CSV").data
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(exp["id"], engine=export_env["engine"])
        assert result["status"] == "DONE", result
        export_id = exp["id"]
        # Chủ khác + không phải ADMIN → download bị chặn.
        dl = download_export(operator_ctx, export_id)
        assert not dl.ok
        assert dl.code in ("NOT_FOUND", "FORBIDDEN")
        got = get_export(operator_ctx, export_id)
        assert not got.ok
        # ADMIN tải được.
        assert download_export(admin_ctx, export_id).ok


class TestProdAdminOnly:
    def _set_ds_env(self, export_env, env: str) -> None:
        engine = export_env["engine"]
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE RECON_DATA_SOURCE SET ENV=:e WHERE ID=:i"),
                {"e": env, "i": export_env["ds_id"]},
            )

    def test_operator_blocked_on_prod_run(self, export_env, operator_ctx, admin_ctx, monkeypatch):
        from unittest.mock import patch

        from app.services.report_run import create_report_run
        from tests.unit.test_report_run_execute import ROWS, _mock_ora_conn

        monkeypatch.setattr("app.services.report_run.get_recon_engine", lambda: export_env["engine"])
        self._set_ds_env(export_env, "PROD")
        conn, _ = _mock_ora_conn(ROWS)
        with patch("app.services.report_source.open_source_connection", return_value=conn):
            denied = create_report_run(operator_ctx, export_env["report_id"], values={"p_org": "HN"})
            assert not denied.ok
            assert denied.code == "FORBIDDEN"
            allowed = create_report_run(admin_ctx, export_env["report_id"], values={"p_org": "HN"})
            assert allowed.ok, allowed.message

    def test_operator_blocked_on_prod_execute_and_page(self, export_env, operator_ctx, admin_ctx, monkeypatch):
        """Chạy trên DS PROD chỉ ADMIN (spec 11 D4).

        Dry-run/activate đã report_admin-only nên không cần rào thêm;
        rào chắn đặt ở các điểm thực thi truy vấn mà operator gọi được:
        create, execute, get_report_page.
        """
        from unittest.mock import patch

        from app.services.report_run import (
            create_report_run,
            execute_report_run,
            get_report_page,
        )
        from tests.unit.test_report_run_execute import ROWS, _mock_ora_conn

        monkeypatch.setattr("app.services.report_run.get_recon_engine", lambda: export_env["engine"])
        # Tạo run khi DS còn DEV (hợp lệ), rồi chuyển DS sang PROD.
        created = create_report_run(operator_ctx, export_env["report_id"], values={"p_org": "HN"})
        assert created.ok, created.message
        run_id = created.data["id"]
        self._set_ds_env(export_env, "PROD")
        conn, _ = _mock_ora_conn(ROWS)
        with patch("app.services.report_source.open_source_connection", return_value=conn):
            denied = execute_report_run(operator_ctx, run_id)
            assert not denied.ok
            assert denied.code == "FORBIDDEN"
            # ADMIN vẫn chạy được trên PROD.
            admin_created = create_report_run(admin_ctx, export_env["report_id"], values={"p_org": "HN"})
            assert admin_created.ok, admin_created.message
            admin_run = execute_report_run(admin_ctx, admin_created.data["id"])
            assert admin_run.ok, admin_run.message
            # Paging lại kết quả = chạy lại truy vấn → operator cũng bị chặn
            # (dùng run QUEUED của chính operator để qua được owner scope).
            page_denied = get_report_page(operator_ctx, run_id)
            assert not page_denied.ok
            assert page_denied.code == "FORBIDDEN"
            page_ok = get_report_page(admin_ctx, admin_created.data["id"])
            assert page_ok.ok, page_ok.message


def _audit_actions(engine, entity: str, entity_id: int) -> list[tuple[str, str]]:
    """Danh sách (ACTION, ACTOR) trong RECON_AUDIT_LOG cho một entity."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT ACTION, ACTOR FROM RECON_AUDIT_LOG WHERE ENTITY=:e AND ENTITY_ID=:i ORDER BY ID"),
            {"e": entity, "i": str(entity_id)},
        ).fetchall()
    return [(str(r[0]), str(r[1])) for r in rows]


class TestAudit:
    def test_run_audit_trail(self, export_env, operator_ctx, admin_ctx, monkeypatch):
        from unittest.mock import patch

        from app.services.report_run import (
            cancel_report_run,
            create_report_run,
            dry_run_version,
            execute_report_run,
        )
        from tests.unit.test_report_run_execute import ROWS, _mock_ora_conn

        monkeypatch.setattr("app.services.report_run.get_recon_engine", lambda: export_env["engine"])
        engine = export_env["engine"]
        conn, _ = _mock_ora_conn(ROWS)
        with patch("app.services.report_source.open_source_connection", return_value=conn):
            created = create_report_run(operator_ctx, export_env["report_id"], values={"p_org": "HN"})
            assert created.ok, created.message
            run_id = created.data["id"]
            assert ("CREATE_REPORT_RUN", "operator") in _audit_actions(engine, "RECON_REPORT_RUN", run_id)
            executed = execute_report_run(operator_ctx, run_id)
            assert executed.ok, executed.message
            assert ("EXECUTE_REPORT_RUN", "operator") in _audit_actions(engine, "RECON_REPORT_RUN", run_id)
            # Dry-run (admin) + cancel run thứ hai.
            dry = dry_run_version(admin_ctx, export_env["draft_version_id"], values={"p_org": "HN"})
            assert dry.ok, dry.message
            assert ("DRY_RUN_VERSION", "admin") in _audit_actions(
                engine, "RECON_RPT_TPL_VER", export_env["draft_version_id"]
            )
            created2 = create_report_run(operator_ctx, export_env["report_id"], values={"p_org": "HN"})
            cancelled = cancel_report_run(operator_ctx, created2.data["id"])
            assert cancelled.ok, cancelled.message
            assert ("CANCEL_REPORT_RUN", "operator") in _audit_actions(engine, "RECON_REPORT_RUN", created2.data["id"])

    def test_failed_run_audited(self, export_env, operator_ctx, monkeypatch):
        from unittest.mock import patch

        from app.services.report_run import create_report_run, execute_report_run

        monkeypatch.setattr("app.services.report_run.get_recon_engine", lambda: export_env["engine"])
        engine = export_env["engine"]
        created = create_report_run(operator_ctx, export_env["report_id"], values={"p_org": "HN"})
        run_id = created.data["id"]
        with patch(
            "app.services.report_source.open_source_connection",
            side_effect=RuntimeError("ORA-12154: TNS:could not resolve"),
        ):
            executed = execute_report_run(operator_ctx, run_id)
        # execute trả ok=True kể cả FAILED (hợp đồng task 25) nhưng audit vẫn ghi.
        assert executed.ok
        assert executed.data["run"]["status"] == "FAILED"
        actions = _audit_actions(engine, "RECON_REPORT_RUN", run_id)
        assert ("EXECUTE_REPORT_RUN", "operator") in actions

    def test_preset_audit(self, export_env, operator_ctx, monkeypatch):
        from app.services.report_run import create_preset, delete_preset

        monkeypatch.setattr("app.services.report_run.get_recon_engine", lambda: export_env["engine"])
        engine = export_env["engine"]
        preset = create_preset(
            operator_ctx,
            export_env["report_id"],
            export_env["sql_template_id"],
            "Preset kiểm thử",
            values={"p_org": "HN"},
        )
        assert preset.ok, preset.message
        preset_id = preset.data["id"]
        assert ("CREATE_PRESET", "operator") in _audit_actions(engine, "RECON_RPT_PRESET", preset_id)
        deleted = delete_preset(operator_ctx, preset_id)
        assert deleted.ok, deleted.message
        assert ("DELETE_PRESET", "operator") in _audit_actions(engine, "RECON_RPT_PRESET", preset_id)

    def test_export_audit_trail(self, export_env, operator_ctx, monkeypatch):
        from unittest.mock import patch

        from app.services.report_export import (
            cancel_export,
            download_export,
            execute_export,
            request_export,
            retry_export,
        )
        from tests.unit.test_report_export_queue import _mock_stream_conn
        from tests.unit.test_report_run_execute import ROWS

        monkeypatch.setattr("app.services.report_export.get_recon_engine", lambda: export_env["engine"])
        monkeypatch.setattr("app.services.report_run.get_recon_engine", lambda: export_env["engine"])
        engine = export_env["engine"]
        run = _done_run(operator_ctx, export_env)
        requested = request_export(operator_ctx, run["id"], "CSV")
        assert requested.ok, requested.message
        export_id = requested.data["id"]
        assert ("REQUEST_EXPORT", "operator") in _audit_actions(engine, "RECON_RPT_EXPORT", export_id)
        conn, _ = _mock_stream_conn(ROWS)
        with patch(
            "app.services.report_source.open_source_connection",
            return_value=conn,
        ):
            result = execute_export(export_id, engine=engine)
        assert result["status"] == "DONE", result
        assert ("EXECUTE_EXPORT", "operator") in _audit_actions(engine, "RECON_RPT_EXPORT", export_id)
        downloaded = download_export(operator_ctx, export_id)
        assert downloaded.ok, downloaded.message
        assert ("DOWNLOAD_EXPORT", "operator") in _audit_actions(engine, "RECON_RPT_EXPORT", export_id)
        # Retry + cancel trên export thứ hai.
        requested2 = request_export(operator_ctx, run["id"], "CSV", force=True)
        export2_id = requested2.data["id"]
        with engine.begin() as conn2:
            conn2.execute(
                text("UPDATE RECON_RPT_EXPORT SET STATUS='FAILED' WHERE ID=:i"),
                {"i": export2_id},
            )
        retried = retry_export(operator_ctx, export2_id)
        assert retried.ok, retried.message
        assert ("RETRY_EXPORT", "operator") in _audit_actions(engine, "RECON_RPT_EXPORT", export2_id)
        cancelled = cancel_export(operator_ctx, export2_id)
        assert cancelled.ok, cancelled.message
        assert ("CANCEL_EXPORT", "operator") in _audit_actions(engine, "RECON_RPT_EXPORT", export2_id)
