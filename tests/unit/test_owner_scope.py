"""Tests cho phạm vi dữ liệu theo chủ sở hữu — Bước 4 task 19 (test viết trước).

Quy tắc: vai trò thường chỉ thấy run/issue/file của mình (CREATED_BY =
username); truy cập dữ liệu của người khác → NOT_FOUND; ADMIN thấy hết.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata, recon_result_row, recon_run_summary
from app.schemas.run import RunListFilter


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def scope_env(tmp_path, monkeypatch):
    db_path = tmp_path / "scope_test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.run_service",
        "app.services.dashboard",
        "app.services.issue",
        "app.services.file_service",
        "app.services.temp_data",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    import app.services.menu_sync as sync_mod
    import app.services.perm as perm_mod

    sync_mod.sync_from_code(engine)
    perm_mod.clear_perm_cache()
    now = _now()
    # Vai trò + user
    with engine.begin() as conn:
        role_ids: dict[str, int] = {}
        for code, is_system in [
            ("ADMIN", "Y"),
            ("TEMPLATE_OWNER", "N"),
            ("OPERATOR", "N"),
            ("VIEWER", "N"),
        ]:
            res = conn.execute(
                text(
                    "INSERT INTO RECON_ROLE (CODE, NAME, IS_SYSTEM, IS_ACTIVE, "
                    "CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:code, :code, :sys, 'Y', 'SEED', :now, 'SEED', :now, 1)"
                ),
                {"code": code, "sys": is_system, "now": now},
            )
            role_ids[code] = int(res.lastrowid)
        from app.ui.menus import ROLE_MENUS_SEED

        for role_code, menus in ROLE_MENUS_SEED.items():
            for menu in menus:
                conn.execute(
                    text(
                        "INSERT INTO RECON_ROLE_MENU (ROLE_ID, MENU_CODE, GRANTED_BY, GRANTED_AT) "
                        "VALUES (:rid, :menu, 'SEED', :now)"
                    ),
                    {"rid": role_ids[role_code], "menu": menu, "now": now},
                )
        for uid, username, role_code in [
            (1, "admin", "ADMIN"),
            (2, "owner", "TEMPLATE_OWNER"),
            (3, "operator", "OPERATOR"),
            (4, "viewer", "VIEWER"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO RECON_USER_ROLE (USER_ID, ROLE_ID, ASSIGNED_BY, ASSIGNED_AT, CREATED_AT) "
                    "VALUES (:id, :rid, 'SEED', :now, :now)"
                ),
                {"id": uid, "rid": role_ids[role_code], "now": now},
            )
        # Template + data source + file
        tmpl_id = conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE (CODE, NAME, OWNER, STATUS, CURRENT_VERSION, "
                "CREATED_AT, UPDATED_AT, ROW_VERSION) "
                "VALUES ('TPL1', 'Template 1', 'admin', 'ACTIVE', 1, :now, :now, 1)"
            ),
            {"now": now},
        ).lastrowid
        conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE_VERSION (TEMPLATE_ID, VERSION, STATUS, CONFIG_JSON, "
                "CREATED_BY, CREATED_AT) VALUES (:tid, 1, 'ACTIVE', '{}', 'admin', :now)"
            ),
            {"tid": tmpl_id, "now": now},
        )
        ds_id = conn.execute(
            text(
                "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, CALL_TIMEOUT_S, "
                "MAX_ROWS, IS_ACTIVE, IS_CURRENT_METADATA, CREATED_BY, CREATED_AT, UPDATED_AT) "
                "VALUES ('DS1', 'DEV', 'SOURCE', 'ORACLE', 600, 1000000, 'Y', 'N', 'admin', :now, :now)"
            ),
            {"now": now},
        ).lastrowid
        # File: 1 do admin upload (không gắn run nào), 2 do operator upload (file của run 3),
        # 3 là file mẫu của template (SAMPLE_FILE_ID)
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        file_ids = {}
        for fid, uploader in [(1, "admin"), (2, "operator"), (3, "admin")]:
            fpath = files_dir / f"f{fid}.xlsx"
            fpath.write_bytes(b"fake-xlsx")
            file_ids[fid] = conn.execute(
                text(
                    "INSERT INTO RECON_FILE (SHA256, ORIGINAL_NAME, SIZE_BYTES, STORAGE_PATH, "
                    "UPLOADED_BY, UPLOADED_AT) VALUES (:sha, :name, 9, :path, :u, :now)"
                ),
                {"sha": f"sha{fid}", "name": f"f{fid}.xlsx", "path": str(fpath), "u": uploader, "now": now},
            ).lastrowid
        conn.execute(
            text("UPDATE RECON_TEMPLATE_VERSION SET SAMPLE_FILE_ID=:fid WHERE TEMPLATE_ID=:tid AND VERSION=1"),
            {"fid": file_ids[3], "tid": tmpl_id},
        )
        # Run: 1,2 của admin; 3 của operator. CREATED_AT trong tháng hiện tại.
        base = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        run_ids = {}
        for rid, owner, day in [(1, "admin", 2), (2, "admin", 3), (3, "operator", 4)]:
            file_id = file_ids[2] if rid == 3 else file_ids[1]
            run_ids[rid] = conn.execute(
                text(
                    "INSERT INTO RECON_RUN (TEMPLATE_ID, TEMPLATE_VERSION, PROFILE_CODE, "
                    "FILE_ID, DATA_SOURCE_ID, P_FROM, P_TO, APPLY_RANGE_EXCEL, STATUS, PROGRESS_PCT, "
                    "CREATED_BY, CREATED_AT) "
                    "VALUES (:tid, 1, 'DEFAULT', :fid, :ds, :pf, :pt, 'N', 'DONE', 100, :owner, :ca)"
                ),
                {
                    "tid": tmpl_id,
                    "fid": file_id,
                    "ds": ds_id,
                    "pf": base,
                    "pt": base + timedelta(days=1),
                    "owner": owner,
                    "ca": base + timedelta(days=day),
                },
            ).lastrowid
            conn.execute(
                recon_run_summary.insert().values(
                    RUN_ID=run_ids[rid],
                    EXCEL_ROWS_READ=11,
                    CNT_MATCHED=10,
                    CNT_MISMATCH=1,
                    CNT_MISSING_IN_DB=0,
                    CNT_MISSING_IN_EXCEL=0,
                    COLUMNS_JSON=[{"field": "K1"}],
                )
            )
            conn.execute(
                recon_result_row.insert().values(
                    RUN_ID=run_ids[rid],
                    ROW_NO=1,
                    KEY_TEXT="K1",
                    KEY_HASH="h1",
                    STATUS="MATCHED",
                    KEY_JSON={},
                )
            )
        # Issue: 1 thuộc run 1 (admin), 2 thuộc run 3 (operator)
        for iid, run_id in [(1, 1), (2, 3)]:
            conn.execute(
                text(
                    "INSERT INTO RECON_ISSUE (TEMPLATE_ID, PROFILE_CODE, KEY_TEXT, KEY_HASH, "
                    "FIRST_RUN_ID, LAST_RUN_ID, STATUS, ROW_VERSION) "
                    "VALUES (:tid, 'DEFAULT', :key, :hash, :run, :run, 'OPEN', 1)"
                ),
                {"tid": tmpl_id, "key": f"K{iid}", "hash": f"h{iid}", "run": run_ids[run_id]},
            )
    yield engine
    engine.dispose()


def _ctx(uid: int, username: str, roles: list[str]) -> Ctx:
    return Ctx(user_id=uid, username=username, full_name=username, roles=roles)


ADMIN = _ctx(1, "admin", ["ADMIN"])
OPERATOR = _ctx(3, "operator", ["OPERATOR"])
VIEWER = _ctx(4, "viewer", ["VIEWER"])


class TestRunScope:
    def test_list_runs_scoped(self, scope_env):
        from app.services.run_service import list_runs

        res = list_runs(OPERATOR, RunListFilter())
        assert res.ok
        assert [i["id"] for i in res.data["items"]] == [3]
        assert res.data["total"] == 1
        res = list_runs(ADMIN, RunListFilter())
        assert res.data["total"] == 3
        res = list_runs(VIEWER, RunListFilter())
        assert res.data["total"] == 0

    def test_get_run_other_owner_not_found(self, scope_env):
        from app.services.run_service import get_run

        res = get_run(OPERATOR, 1)
        assert not res.ok and res.code == "NOT_FOUND"
        assert get_run(OPERATOR, 3).ok
        assert get_run(ADMIN, 1).ok

    def test_run_rows_and_detail_scoped(self, scope_env):
        from app.schemas.run import RunRowsFilter
        from app.services.run_service import get_row_detail, get_run_columns, get_run_rows

        assert not get_run_columns(OPERATOR, 1).ok
        assert get_run_columns(OPERATOR, 3).ok
        assert not get_run_rows(OPERATOR, 1, RunRowsFilter()).ok
        assert get_run_rows(OPERATOR, 3, RunRowsFilter()).ok
        assert not get_row_detail(OPERATOR, 1, 1).ok
        assert get_row_detail(OPERATOR, 3, 1).ok

    def test_export_other_run_not_found(self, scope_env):
        from app.services.run_service import export_run

        res = export_run(OPERATOR, 1)
        assert not res.ok and res.code == "NOT_FOUND"


class TestDashboardScope:
    def test_dashboard_totals_scoped(self, scope_env):
        from app.services.dashboard import get_dashboard_summary

        res = get_dashboard_summary(OPERATOR)
        assert res.ok
        assert res.data["total_runs"] == 1
        assert [r["id"] for r in res.data["recent_runs"]] == [3]
        res = get_dashboard_summary(ADMIN)
        assert res.data["total_runs"] == 3
        res = get_dashboard_summary(VIEWER)
        assert res.data["total_runs"] == 0

    def test_compare_runs_other_owner_not_found(self, scope_env):
        from app.services.dashboard import compare_runs

        res = compare_runs(OPERATOR, 1, 2)
        assert not res.ok and res.code == "NOT_FOUND"
        # So sánh run của mình với chính nó thì được
        assert compare_runs(OPERATOR, 3, 3).ok

    def test_previous_run_only_own(self, scope_env):
        from app.services.dashboard import get_previous_run

        # Run 3 của operator không có run DONE nào trước đó của chính mình
        assert get_previous_run(OPERATOR, 3).data is None
        # Admin xem run 2 thì run trước là run 1 (của admin)
        prev = get_previous_run(ADMIN, 2)
        assert prev.data is not None and prev.data["id"] == 1


class TestIssueScope:
    def test_list_issues_scoped(self, scope_env):
        from app.services.issue import get_issue, list_issues

        res = list_issues(OPERATOR)
        assert res.ok
        assert [i["ID"] for i in res.data["items"]] == [2]
        assert list_issues(ADMIN).data["total"] == 2
        assert not get_issue(OPERATOR, 1).ok
        assert get_issue(OPERATOR, 2).ok

    def test_update_other_issue_not_found(self, scope_env):
        from app.services.issue import update_issue_by_id

        res = update_issue_by_id(OPERATOR, 1, status="RESOLVED")
        assert not res.ok and res.code == "NOT_FOUND"


class TestFileScope:
    def test_get_file_own_upload(self, scope_env):
        from app.services.file_service import get_file

        assert get_file(OPERATOR, 2).ok  # file do operator upload
        assert not get_file(OPERATOR, 1).ok  # file của admin, không gắn run nào

    def test_get_file_own_run_file(self, scope_env):
        from app.services.file_service import get_file

        # File 1 là FILE_ID của run 1 (admin) và run 2 (admin), không phải run của operator
        assert not get_file(OPERATOR, 1).ok
        assert get_file(ADMIN, 1).ok

    def test_get_file_template_sample(self, scope_env):
        from app.services.file_service import get_file

        # File 3 là file mẫu của template: viewer có menu template nên được tải
        assert get_file(VIEWER, 3).ok
        # Operator không có menu template nên không được tải file mẫu
        assert not get_file(OPERATOR, 3).ok


class TestPurgeScope:
    def test_purge_single_own_run(self, scope_env):
        from app.services.temp_data import purge_runs

        res = purge_runs(OPERATOR, [3])
        assert res.ok, res.message
        res = purge_runs(OPERATOR, [1])
        assert not res.ok and res.code == "NOT_FOUND"

    def test_purge_bulk_requires_admin(self, scope_env):
        from app.services.temp_data import purge_runs

        res = purge_runs(OPERATOR, [1, 3])
        assert not res.ok and res.code == "FORBIDDEN"

    def test_mark_checked_other_run_not_found(self, scope_env):
        from app.services.temp_data import mark_checked

        res = mark_checked(OPERATOR, 1, purge=False)
        assert not res.ok and res.code == "NOT_FOUND"
        assert mark_checked(OPERATOR, 3, purge=False).ok
