"""Tests cho task 67 — sửa lỗi wizard chạy bộ + switch chạy ngay/chạy ngầm.

Tests-first: các test này phải đỏ trước khi code.
- A: upload lại file đã bỏ (IGNORED) không còn báo "đã tồn tại".
- B: sang bước 3 không tự đặt lại tham số (guard n_clicks ở _reset_param).
- C1: lỗi thật của run con hiện ở bước 5 + trang /runs/<id>.
- C2: run lỗi vẫn lưu được câu SQL đã thử.
- C3: precheck probe SQL bắt lỗi SQL trước khi thực thi.
- D: switch chạy ngay (mặc định) / chạy ngầm ở bước Thực thi.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def batch_env(tmp_path, monkeypatch):
    db_path = tmp_path / "batch67.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.batch_def",
        "app.services.batch_run",
        "app.services.file_service",
        "app.services.excel_load",
        "app.services.run_executor",
        "app.services.report_source",
        "app.services.source_conn",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [
            (1, "admin"),
            (2, "owner"),
            (3, "operator"),
            (4, "viewer"),
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
    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["TEMPLATE_OWNER"], 3: ["OPERATOR"], 4: ["VIEWER"]})
    clear_perm_cache()
    return engine


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


class FakeConn:
    def close(self) -> None:
        pass


@pytest.fixture()
def mock_ds_ok(monkeypatch):
    monkeypatch.setattr("app.services.batch_run.open_source_connection", lambda ds_id: FakeConn())


def _sample_config(params: list[dict], table: str | None = None) -> dict:
    data = json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
    data["db_source"]["params"] = params
    if table is not None:
        data["db_source"]["table"] = table
    return data


def _default_params() -> list[dict]:
    return [
        {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
        {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
        {"name": "p_ky", "type": "text", "source": "user", "label": "Kỳ", "required": True},
        {"name": "p_org", "type": "text", "source": "default", "default": "BDP", "label": "Đơn vị", "required": True},
        {"name": "p_so", "type": "number", "source": "user", "label": "Số", "required": False},
    ]


def _make_data_source(engine, env: str = "DEV", name: str = "ORACLE_TEST", db_type: str = "ORACLE") -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        ds_id = conn.execute(
            text(
                "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, HOST, "
                "PORT, SERVICE_NAME, CALL_TIMEOUT_S, MAX_ROWS, IS_ACTIVE, "
                "IS_CURRENT_METADATA, CREATED_BY, CREATED_AT, UPDATED_AT) VALUES "
                "(:name, :env, 'SOURCE', :dbt, 'localhost', 1521, 'XE', "
                "600, 1000000, 'Y', 'N', 'admin', :now, :now)"
            ),
            {"name": name, "env": env, "dbt": db_type, "now": now},
        ).lastrowid
    return int(ds_id)


def _make_template(engine, code: str, ds_id: int, table: str | None = None) -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        tmpl_id = conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE (CODE, NAME, OWNER, STATUS, CURRENT_VERSION, "
                "CREATED_AT, UPDATED_AT, ROW_VERSION) VALUES (:c, :n, 'admin', 'ACTIVE', 1, :now, :now, 1)"
            ),
            {"c": code, "n": code, "now": now},
        ).lastrowid
        conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE_VERSION (TEMPLATE_ID, VERSION, STATUS, "
                "CONFIG_JSON, DATA_SOURCE_ID, CREATED_BY, CREATED_AT) VALUES (:t, 1, "
                "'ACTIVE', :cfg, :ds, 'admin', :now)"
            ),
            {
                "t": tmpl_id,
                "cfg": json.dumps(_sample_config(_default_params(), table), ensure_ascii=False),
                "ds": ds_id,
                "now": now,
            },
        )
    return int(tmpl_id)


def _make_run(batch_env, admin_ctx, env: str = "DEV", items: list[dict] | None = None, ds_id: int | None = None):
    from app.services.batch_def import activate_batch_def, add_batch_def_items, create_batch_def
    from app.services.batch_run import create_batch_run

    if items is None:
        if ds_id is None:
            ds_id = _make_data_source(batch_env, env)
        tmpl = _make_template(batch_env, "DTP_TMPL", ds_id)
        items = [
            {
                "template_id": tmpl,
                "file_pattern": "*DTP*",
                "multi_file": True,
                "is_required": True,
                "priority": 100,
                "params_override": {"p_ky": "{ky.thang}"},
            }
        ]
    res = create_batch_def(admin_ctx, {"code": "DOANH_THU", "name": "DOANH_THU", "max_parallel_per_ds": 2})
    assert res.ok is True
    d = res.data
    added = add_batch_def_items(admin_ctx, d["id"], items)
    assert added.ok is True
    assert activate_batch_def(admin_ctx, d["id"]).ok is True
    run = create_batch_run(admin_ctx, d["id"], "2026-02")
    assert run.ok is True
    return d, run.data


def _add_sample_file(batch_env, admin_ctx, run_id: int, filename: str = "dtp_2026-02.xlsx"):
    from app.services.batch_run import add_files

    content = Path("samples/dtp_sample_200.xlsx").read_bytes()
    res = add_files(admin_ctx, run_id, [{"filename": filename, "content": content}])
    assert res.ok is True, res.message
    return res.data["added"][0]


def _check_level(precheck: dict, key: str) -> str | None:
    for c in precheck.get("checks", []):
        if c["key"] == key:
            return c["level"]
    return None


def _texts(comp) -> list[str]:
    out: list[str] = []
    if isinstance(comp, str):
        out.append(comp)
    elif isinstance(comp, (list, tuple)):
        for c in comp:
            out.extend(_texts(c))
    elif hasattr(comp, "children"):
        out.extend(_texts(comp.children))
    return out


def _find_all(comp, typ) -> list:
    found: list = []
    if isinstance(comp, typ):
        found.append(comp)
    children = getattr(comp, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            found.extend(_find_all(c, typ))
    elif children is not None:
        found.extend(_find_all(children, typ))
    return found


def _sample_content() -> bytes:
    return Path("samples/dtp_sample_200.xlsx").read_bytes()


class TestReuploadAfterIgnore:
    """A — upload lại file đã bỏ không còn báo 'đã tồn tại'."""

    def test_reupload_same_name_after_ignore(self, batch_env, admin_ctx):
        from app.services.batch_run import add_files, ignore_file

        _d, run = _make_run(batch_env, admin_ctx)
        added = _add_sample_file(batch_env, admin_ctx, run["id"])
        res_ignore = ignore_file(admin_ctx, added["id"])
        assert res_ignore.ok is True
        res = add_files(admin_ctx, run["id"], [{"filename": "dtp_2026-02.xlsx", "content": _sample_content()}])
        assert res.ok is True
        assert res.data["skipped"] == []
        assert len(res.data["added"]) == 1
        # Tái dùng đúng dòng IGNORED cũ (UNIQUE cấm INSERT dòng mới cùng tên).
        assert res.data["added"][0]["id"] == added["id"]
        assert res.data["added"][0]["match_state"] != "IGNORED"

    def test_reupload_same_content_new_name_after_ignore_no_warning(self, batch_env, admin_ctx):
        from app.services.batch_run import add_files, ignore_file

        _d, run = _make_run(batch_env, admin_ctx)
        added = _add_sample_file(batch_env, admin_ctx, run["id"], "dtp_a.xlsx")
        assert ignore_file(admin_ctx, added["id"]).ok is True
        res = add_files(admin_ctx, run["id"], [{"filename": "dtp_b.xlsx", "content": _sample_content()}])
        assert res.ok is True
        assert res.data["skipped"] == []
        assert res.data["warnings"] == []
        assert len(res.data["added"]) == 1


class TestResetParamGuard:
    """B — callback đặt lại tham số chỉ chạy khi nút được bấm thật."""

    def _mock_trigger(self, monkeypatch, triggered_id):
        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered_id=triggered_id, triggered=[{"prop_id": "x", "value": 1}]),
        )

    def _store(self, run_id: int, item_id: int) -> dict:
        return {
            "id": run_id,
            "items": [{"id": item_id, "params_run_override": {"p_org": "XXX"}}],
        }

    def test_layout_insert_does_not_reset(self, batch_env, admin_ctx, monkeypatch):
        import dash

        import app.ui.pages.batch_run_wizard as page
        from app.services.batch_run import set_param_override

        _d, run = _make_run(batch_env, admin_ctx)
        item_id = run["items"][0]["id"]
        assert set_param_override(admin_ctx, item_id, "p_org", "XXX").ok is True
        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        # Mô phỏng Dash kích hoạt callback khi layout bước 3 chèn nút reset:
        # mọi n_clicks đều None, triggered_id là nút reset.
        self._mock_trigger(monkeypatch, {"type": "brw-param-reset-btn", "index": f"{item_id}:p_org"})
        out_store, out_notif = page._reset_param([None, None], self._store(run["id"], item_id))
        assert out_store is dash.no_update
        assert out_notif is dash.no_update
        from app.services.batch_run import get_batch_run

        item = get_batch_run(admin_ctx, run["id"]).data["items"][0]
        assert item["params_run_override"].get("p_org") == "XXX"

    def test_real_click_still_resets(self, batch_env, admin_ctx, monkeypatch):
        import app.ui.pages.batch_run_wizard as page
        from app.services.batch_run import get_batch_run, set_param_override

        _d, run = _make_run(batch_env, admin_ctx)
        item_id = run["items"][0]["id"]
        assert set_param_override(admin_ctx, item_id, "p_org", "XXX").ok is True
        monkeypatch.setattr(page, "get_current_ctx", lambda: admin_ctx)
        self._mock_trigger(monkeypatch, {"type": "brw-param-reset-btn", "index": f"{item_id}:p_org"})
        out_store, out_notif = page._reset_param([1], self._store(run["id"], item_id))
        assert out_store is not None
        item = get_batch_run(admin_ctx, run["id"]).data["items"][0]
        assert "p_org" not in (item["params_run_override"] or {})


class TestSyncChildError:
    """C1 — sync_batch_status copy lỗi thật từ run con sang mục."""

    def test_sync_copies_error_msg_and_code(self, batch_env, admin_ctx):
        from app.db.metadata import recon_batch_run_item, recon_run
        from app.services.batch_run import get_batch_run, sync_batch_status

        _d, run = _make_run(batch_env, admin_ctx)
        run_id = run["id"]
        item_id = run["items"][0]["id"]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with batch_env.begin() as conn:
            child_id = conn.execute(
                recon_run.insert().values(
                    TEMPLATE_ID=run["items"][0]["template_id"],
                    TEMPLATE_VERSION=1,
                    PROFILE_CODE="BY_INVOICE",
                    DATA_SOURCE_ID=run["items"][0]["data_source_id"],
                    P_FROM=datetime(2026, 2, 1),
                    P_TO=datetime(2026, 2, 28, 23, 59, 59),
                    STATUS="FAILED",
                    ERROR_CODE="SOURCE_QUERY_FAILED",
                    ERROR_MSG="Lỗi thực thi truy vấn nguồn Oracle: ORA-00942: table or view does not exist",
                    BATCH_RUN_ID=run_id,
                    BATCH_RUN_ITEM_ID=item_id,
                    CREATED_BY="admin",
                    CREATED_AT=now,
                )
            ).inserted_primary_key[0]
            conn.execute(
                recon_batch_run_item.update()
                .where(recon_batch_run_item.c.ID == item_id)
                .values(STATUS="QUEUED", CURRENT_RUN_ID=int(child_id))
            )
            conn.execute(
                text("UPDATE RECON_BATCH_RUN SET STATUS='RUNNING' WHERE ID=:r"), {"r": run_id}
            )
        res = sync_batch_status(batch_env, run_id)
        assert res["status"] == "PARTIAL"
        item = get_batch_run(admin_ctx, run_id).data["items"][0]
        assert item["status"] == "FAILED"
        assert item["error_code"] == "SOURCE_QUERY_FAILED"
        assert "ORA-00942" in (item["error_msg"] or "")


class TestErrorCards:
    """C1 — card lỗi hiện lỗi thật ở bước 5 và trang /runs/<id>."""

    def _failed_item(self) -> dict:
        return {
            "id": 1,
            "template_code": "BILL_SMART_PORT_BDP",
            "template_name": "Doanh thu smartport BDP",
            "status": "FAILED",
            "source_sql": "SELECT * FROM FACT_BILL WHERE APPLICATION = 'SMP'",
            "source_binds": {"p_org": "BDP"},
            "data_source_name": "GMD_DEV",
            "data_source_id": 2,
            "data_source_env": "DEV",
            "error_msg": "Lỗi thực thi truy vấn nguồn Oracle: ORA-00942: table or view does not exist",
            "error_code": "SOURCE_QUERY_FAILED",
            "current_run_id": 1033,
            "seq_no": 1,
            "progress_pct": 100,
        }

    def test_step5_failed_item_shows_error_card(self):
        import dash_mantine_components as dmc

        from app.ui.pages.batch_run_wizard import render_step5

        run = {
            "status": "PARTIAL",
            "max_parallel_per_ds": 2,
            "data_source_name": "GMD_DEV",
            "items": [self._failed_item()],
        }
        comp = render_step5(run)
        alerts = _find_all(comp, dmc.Alert)
        assert any("ORA-00942" in t for a in alerts for t in _texts(a)), "thiếu card lỗi bên cạnh câu SQL"
        # Bảng tiến độ hiện lỗi thật thay cho chữ chung "Lỗi khi chạy".
        assert "Lỗi khi chạy" not in _texts(comp)

    def test_step5_done_item_has_no_error_card(self):
        from app.ui.pages.batch_run_wizard import render_step5

        item = self._failed_item()
        item["status"] = "DONE"
        item["error_msg"] = None
        run = {"status": "DONE", "max_parallel_per_ds": 2, "data_source_name": "GMD_DEV", "items": [item]}
        comp = render_step5(run)
        assert not any("ORA-00942" in t for t in _texts(comp))

    def test_run_result_failed_run_shows_error_card(self):
        from app.ui.pages.run_result import render_sql_tab_content

        run_info = {
            "status": "FAILED",
            "error_msg": "Lỗi thực thi truy vấn nguồn Oracle: ORA-00942: table or view does not exist",
            "data_source_id": 2,
            "params_json": {"p_org": "BDP"},
            "p_from": "2026-07-01 00:00:00",
            "p_to": "2026-07-31 23:59:59",
        }
        summary = {"SOURCE_SQL": "SELECT * FROM FACT_BILL", "DB_ROWS": 0, "DURATION_MS": 0}
        comp = render_sql_tab_content(run_info, summary)
        assert any("ORA-00942" in t for t in _texts(comp))

    def test_run_result_done_run_has_no_error_card(self):
        from app.ui.pages.run_result import render_sql_tab_content

        run_info = {
            "status": "DONE",
            "error_msg": None,
            "data_source_id": 2,
            "params_json": {},
            "p_from": "2026-07-01 00:00:00",
            "p_to": "2026-07-31 23:59:59",
        }
        comp = render_sql_tab_content(run_info, {"SOURCE_SQL": "SELECT 1", "DB_ROWS": 1, "DURATION_MS": 5})
        assert not any("ORA-00942" in t for t in _texts(comp))


class TestFailedRunKeepsSql:
    """C2 — run lỗi vẫn lưu được câu SQL đã thử (executor)."""

    @pytest.fixture()
    def exec_db(self, tmp_path, monkeypatch):
        db_file = tmp_path / "recon_test67.db"
        db_url = f"sqlite:///{db_file.as_posix()}"
        monkeypatch.setenv("RECON_DB_URL", db_url)
        from app.core.config import get_settings

        get_settings.cache_clear()
        engine = create_engine(db_url, connect_args={"timeout": 30})
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            conn.exec_driver_sql("PRAGMA busy_timeout=30000")
        metadata.create_all(engine)
        yield engine
        get_settings.cache_clear()

    def test_failed_run_summary_keeps_source_sql(self, exec_db, admin_ctx):
        from sqlalchemy import select

        from app.db.metadata import recon_run_summary
        from app.schemas.run import CreateRunParams
        from app.services.run_executor import execute_run
        from app.services.run_service import create_run

        def _sample_cfg() -> dict:
            return json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))

        # Seed giống test_worker_executor.seed_data nhưng dùng fixture exec_db.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with exec_db.begin() as conn:
            from app.db.metadata import recon_data_source, recon_file, recon_template, recon_template_version

            ds_id = conn.execute(
                recon_data_source.insert().values(
                    NAME="ORACLE_DEV", ENV="DEV", PURPOSE="SOURCE", DB_TYPE="ORACLE",
                    HOST="localhost", PORT=1521, SERVICE_NAME="orcl", USERNAME="RECON_SRC_RO",
                    PASSWORD_ENC="dummy", DEFAULT_SCHEMA="RECON_SRC", IS_ACTIVE="Y",
                    CREATED_BY="admin", CREATED_AT=now, UPDATED_AT=now,
                )
            ).inserted_primary_key[0]
            f_id = conn.execute(
                recon_file.insert().values(
                    SHA256="dummy_sha256", ORIGINAL_NAME="dtp_sample_200.xlsx", SIZE_BYTES=1024,
                    STORAGE_PATH="samples/dtp_sample_200.xlsx", SHEETS_JSON=["BÁO CÁO DTP"],
                    UPLOADED_BY="admin", UPLOADED_AT=now,
                )
            ).inserted_primary_key[0]
            tmpl_id = conn.execute(
                recon_template.insert().values(
                    CODE="DTP_HOA_DON", NAME="DTP Hóa đơn", OWNER="admin", STATUS="ACTIVE",
                    CURRENT_VERSION=1, CREATED_AT=now, UPDATED_AT=now,
                )
            ).inserted_primary_key[0]
            conn.execute(
                recon_template_version.insert().values(
                    TEMPLATE_ID=tmpl_id, VERSION=1, STATUS="ACTIVE", CONFIG_JSON=_sample_cfg(),
                    DATA_SOURCE_ID=ds_id, DRY_RUN_OK="Y", CREATED_BY="admin", CREATED_AT=now, ACTIVATED_AT=now,
                )
            )
        res = create_run(
            admin_ctx,
            CreateRunParams(
                template_id=int(tmpl_id), file_id=int(f_id), profile_code="BY_INVOICE",
                p_from=datetime(2026, 2, 1, 0, 0, 0), p_to=datetime(2026, 2, 5, 23, 59, 59),
            ),
        )
        assert res.ok
        run_id = res.data["run_id"]

        def failing_fetcher(config, profile, p_from, p_to, max_rows, timeout):
            raise RuntimeError("Lỗi mô phỏng mất kết nối DB nguồn!")

        exec_res = execute_run(run_id, mock_fetcher=failing_fetcher)
        assert exec_res["status"] == "FAILED"
        with exec_db.connect() as conn:
            summ = conn.execute(
                select(recon_run_summary).where(recon_run_summary.c.RUN_ID == run_id)
            ).mappings().first()
            assert summ is not None
            assert summ["SOURCE_SQL"] is not None
            assert "SRC_FACT_INVOICE_DTP" in summ["SOURCE_SQL"]


def _create_src_table(engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE SRC_FACT (COLLECT_POINT TEXT, TXN_ID TEXT, INVOICE_NO TEXT, "
            "INVOICE_STATUS TEXT, INVOICE_DATE TEXT, PIN_NO TEXT, SERVICE_CODE TEXT, "
            "QUANTITY REAL, AMOUNT REAL, ORG_CODE TEXT)"
        )


class TestPrecheckSqlProbe:
    """C3 — precheck probe SQL bắt lỗi SQL trước khi thực thi."""

    def test_probe_ok_for_valid_sql(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import precheck

        ds_id = _make_data_source(batch_env, db_type="SQLITE", name="SQLITE_SRC")
        _create_src_table(batch_env)
        _d, run = _make_run(batch_env, admin_ctx, ds_id=ds_id)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        # Template của _make_run dùng bảng mặc định RECON_SRC... -> đổi sang bảng thật.
        from sqlalchemy import text as _text

        with batch_env.begin() as conn:
            tmpl_id = run["items"][0]["template_id"]
            row = conn.execute(
                _text("SELECT CONFIG_JSON FROM RECON_TEMPLATE_VERSION WHERE TEMPLATE_ID=:t AND VERSION=1"),
                {"t": tmpl_id},
            ).first()
            cfg = json.loads(row[0])
            cfg["db_source"]["table"] = "SRC_FACT"
            conn.execute(
                _text("UPDATE RECON_TEMPLATE_VERSION SET CONFIG_JSON=:c WHERE TEMPLATE_ID=:t AND VERSION=1"),
                {"c": json.dumps(cfg, ensure_ascii=False), "t": tmpl_id},
            )
        res = precheck(admin_ctx, run["id"])
        assert res.ok is True
        item = res.data["items"][0]
        assert item["status"] == "READY"
        assert _check_level(item["precheck"], "source_sql") == "ok"

    def test_probe_error_for_bad_table(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import precheck

        ds_id = _make_data_source(batch_env, db_type="SQLITE", name="SQLITE_SRC")
        _create_src_table(batch_env)
        _d, run = _make_run(batch_env, admin_ctx, ds_id=ds_id)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        from sqlalchemy import text as _text

        with batch_env.begin() as conn:
            tmpl_id = run["items"][0]["template_id"]
            row = conn.execute(
                _text("SELECT CONFIG_JSON FROM RECON_TEMPLATE_VERSION WHERE TEMPLATE_ID=:t AND VERSION=1"),
                {"t": tmpl_id},
            ).first()
            cfg = json.loads(row[0])
            cfg["db_source"]["table"] = "NO_SUCH_TABLE_XYZ"
            conn.execute(
                _text("UPDATE RECON_TEMPLATE_VERSION SET CONFIG_JSON=:c WHERE TEMPLATE_ID=:t AND VERSION=1"),
                {"c": json.dumps(cfg, ensure_ascii=False), "t": tmpl_id},
            )
        res = precheck(admin_ctx, run["id"])
        assert res.ok is True
        item = res.data["items"][0]
        assert item["status"] == "ERROR"
        assert _check_level(item["precheck"], "source_sql") == "error"


class TestRunModeSwitch:
    """D — switch chạy ngay (mặc định) / chạy ngầm ở bước Thực thi."""

    def _mock_ctx(self, monkeypatch, triggered_id):
        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(triggered_id=triggered_id, triggered=[{"prop_id": "x", "value": 1}]),
        )

    def _mock_nav(self, monkeypatch):
        import app.ui.pages.batch_run_wizard as page

        monkeypatch.setattr(page, "get_current_ctx", lambda: SimpleNamespace(username="admin"))
        monkeypatch.setattr(page, "start", lambda ctx, run_id, include_warn=True, confirm_prod=False: SimpleNamespace(ok=True, code=None, details=None, message="", data={}))
        monkeypatch.setattr(page, "_load_run_data", lambda run_id: {"id": run_id, "status": "RUNNING"})
        return page

    def test_navigate_background_redirects_to_history(self, monkeypatch):
        page = self._mock_nav(monkeypatch)
        self._mock_ctx(monkeypatch, "brw-next-btn")
        store = {"id": 1, "status": "DRAFT"}
        out = page._navigate(None, 1, 5, store, 1, True, True)
        # outputs: store, step, notif, redirect, interval_disabled, modal, modal_body
        assert out[3] == "/batch-runs"
        assert out[4] is True

    def test_navigate_run_now_stays_on_step5(self, monkeypatch):
        import dash

        page = self._mock_nav(monkeypatch)
        self._mock_ctx(monkeypatch, "brw-next-btn")
        store = {"id": 1, "status": "DRAFT"}
        out = page._navigate(None, 1, 5, store, 1, True, False)
        assert out[3] is dash.no_update
        assert out[4] is False

    def test_confirm_prod_background_redirects(self, monkeypatch):
        page = self._mock_nav(monkeypatch)
        self._mock_ctx(monkeypatch, "brw-prod-confirm")
        out = page._confirm_prod_start(1, None, True, 1, True)
        # outputs: store, step, modal_opened, notif, interval_disabled, redirect
        assert out[5] == "/batch-runs"
        assert out[4] is True

    def test_confirm_prod_run_now_stays(self, monkeypatch):
        import dash

        page = self._mock_nav(monkeypatch)
        self._mock_ctx(monkeypatch, "brw-prod-confirm")
        out = page._confirm_prod_start(1, None, True, 1, False)
        assert out[5] is dash.no_update
        assert out[4] is False
