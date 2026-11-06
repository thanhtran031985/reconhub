"""Tests cho chạy lại / thay file / hủy — Bước 7 task 18 (test viết trước).

Spec 10 mục 5.7: chạy lại run lỗi, thay file và chạy lại một mục, hủy.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def batch_env(tmp_path, monkeypatch):
    db_path = tmp_path / "batch7.db"
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
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [(1, "admin"), (3, "operator")]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": username, "now": now},
            )
    seed_perm_basics(engine, {1: ["ADMIN"], 3: ["OPERATOR"]})
    clear_perm_cache()
    return engine


@pytest.fixture()
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="admin", roles=["ADMIN"])


@pytest.fixture()
def operator_ctx() -> Ctx:
    return Ctx(user_id=3, username="operator", full_name="operator", roles=["OPERATOR"])


class FakeConn:
    def close(self) -> None:
        pass


@pytest.fixture()
def mock_ds_ok(monkeypatch):
    monkeypatch.setattr("app.services.batch_run.open_source_connection", lambda ds_id: FakeConn())


def _sample_config() -> dict:
    data = json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
    data["db_source"]["params"] = [
        {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
        {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
        {"name": "p_ky", "type": "text", "source": "user", "label": "Kỳ", "required": True},
        {"name": "p_so", "type": "number", "source": "user", "label": "Số", "required": False},
    ]
    return data


def _make_ds_template(engine, code: str = "DTP_TMPL"):
    return _make_ds_templates(engine, [code])[0]


def _make_ds_templates(engine, codes: list[str]):
    """Tạo Data Source + một template cho mỗi mã (mỗi mục trong bộ cần template riêng)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        ds_id = conn.execute(
            text(
                "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, HOST, "
                "PORT, SERVICE_NAME, CALL_TIMEOUT_S, MAX_ROWS, IS_ACTIVE, "
                "IS_CURRENT_METADATA, CREATED_BY, CREATED_AT, UPDATED_AT) VALUES "
                "('ORACLE_TEST', 'DEV', 'SOURCE', 'ORACLE', 'localhost', 1521, 'XE', "
                "600, 1000000, 'Y', 'N', 'admin', :now, :now)"
            ),
            {"now": now},
        ).lastrowid
        out = []
        for code in codes:
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
                {"t": tmpl_id, "cfg": json.dumps(_sample_config(), ensure_ascii=False), "ds": ds_id, "now": now},
            )
            out.append((int(ds_id), int(tmpl_id)))
    return out


def _make_started_run(batch_env, admin_ctx, n_items: int = 1, period: str = "2026-02"):
    """Tạo bộ + lần chạy đã start (các mục QUEUED, có run con)."""
    from app.services.batch_def import activate_batch_def, add_batch_def_items, create_batch_def
    from app.services.batch_run import add_files, create_batch_run, precheck, start

    tmpls = [t for _ds, t in _make_ds_templates(batch_env, [f"DTP_TMPL{i}" for i in range(n_items)])]
    items = [
        {
            "template_id": tmpls[i],
            "file_pattern": f"*DTP{i}*" if n_items > 1 else "*DTP*",
            "multi_file": True,
            "is_required": True,
            "priority": 10 * (i + 1),
            "params_override": {"p_ky": "{ky.thang}"},
        }
        for i in range(n_items)
    ]
    res = create_batch_def(admin_ctx, {"code": "DOANH_THU", "name": "DOANH_THU", "max_parallel_per_ds": 2})
    assert res.ok is True
    d = res.data
    assert add_batch_def_items(admin_ctx, d["id"], items).ok is True
    assert activate_batch_def(admin_ctx, d["id"]).ok is True
    run = create_batch_run(admin_ctx, d["id"], period)
    assert run.ok is True
    run = run.data
    content = Path("samples/dtp_sample_200.xlsx").read_bytes()
    for i in range(n_items):
        name = f"dtp{i}_2026-02.xlsx" if n_items > 1 else "dtp_2026-02.xlsx"
        assert add_files(admin_ctx, run["id"], [{"filename": name, "content": content}]).ok is True
    assert precheck(admin_ctx, run["id"]).ok is True
    started = start(admin_ctx, run["id"])
    assert started.ok is True, started.message
    return d, started.data


def _set_child_status(batch_env, child_run_id: int, status: str) -> None:
    with batch_env.begin() as conn:
        conn.execute(text("UPDATE RECON_RUN SET STATUS = :s WHERE ID = :r"), {"s": status, "r": child_run_id})
        conn.execute(text("UPDATE RECON_RUN_QUEUE SET STATUS = 'DONE' WHERE RUN_ID = :r"), {"r": child_run_id})


def _sync(batch_env, run_id: int):
    from app.services.batch_run import sync_batch_status

    return sync_batch_status(batch_env, run_id)


class TestRetryFailed:
    def test_retry_failed(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import get_batch_run, retry_failed

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=2)
        items = run["items"]
        _set_child_status(batch_env, items[0]["current_run_id"], "FAILED")
        _set_child_status(batch_env, items[1]["current_run_id"], "DONE")
        synced = _sync(batch_env, run["id"])
        assert synced["status"] == "PARTIAL"
        old_child = items[0]["current_run_id"]
        res = retry_failed(admin_ctx, run["id"])
        assert res.ok is True
        assert res.data["status"] == "RUNNING"
        assert res.data["started"] == 1
        got = get_batch_run(admin_ctx, run["id"])
        item0 = got.data["items"][0]
        assert item0["status"] == "QUEUED"
        assert item0["current_run_id"] != old_child
        assert item0["attempt_no"] == 2
        assert got.data["items"][1]["status"] == "DONE"
        assert got.data["items"][1]["current_run_id"] == items[1]["current_run_id"]

        from sqlalchemy import select

        from app.db.metadata import recon_run

        with batch_env.connect() as conn:
            old = conn.execute(select(recon_run).where(recon_run.c.ID == old_child)).mappings().first()
            assert old["STATUS"] == "FAILED"
            new = conn.execute(select(recon_run).where(recon_run.c.ID == item0["current_run_id"])).mappings().first()
            assert new["STATUS"] == "QUEUED"
            assert new["BATCH_RUN_ID"] == run["id"]
            assert new["FILE_ID"] == old["FILE_ID"]
            assert str(new["P_FROM"]).startswith("2026-02-01")

    def test_retry_failed_nothing_to_run(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import retry_failed

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=1)
        _set_child_status(batch_env, run["items"][0]["current_run_id"], "DONE")
        _sync(batch_env, run["id"])
        res = retry_failed(admin_ctx, run["id"])
        assert res.ok is False
        assert res.code == "BATCH_NOTHING_TO_RUN"

    def test_retry_failed_forbidden_for_non_creator(self, batch_env, admin_ctx, operator_ctx, mock_ds_ok):
        from app.services.batch_run import retry_failed

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=1)
        _set_child_status(batch_env, run["items"][0]["current_run_id"], "FAILED")
        _sync(batch_env, run["id"])
        assert retry_failed(operator_ctx, run["id"]).code == "FORBIDDEN"


class TestRerunItem:
    def test_rerun_done_item(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import get_batch_run, rerun_item

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=1)
        item = run["items"][0]
        _set_child_status(batch_env, item["current_run_id"], "DONE")
        _sync(batch_env, run["id"])
        assert get_batch_run(admin_ctx, run["id"]).data["status"] == "DONE"
        old_child = item["current_run_id"]
        res = rerun_item(admin_ctx, item["id"])
        assert res.ok is True
        assert res.data["status"] == "QUEUED"
        assert res.data["current_run_id"] != old_child
        assert res.data["attempt_no"] == 2
        assert get_batch_run(admin_ctx, run["id"]).data["status"] == "RUNNING"

    def test_rerun_queued_item_busy(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import rerun_item

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=1)
        res = rerun_item(admin_ctx, run["items"][0]["id"])
        assert res.ok is False
        assert res.code == "BATCH_RUN_BUSY"


class TestReplaceFiles:
    def test_replace_files_rechecks_item(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import get_batch_run, replace_files

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=1)
        item = run["items"][0]
        _set_child_status(batch_env, item["current_run_id"], "DONE")
        _sync(batch_env, run["id"])
        import polars as pl

        df = pl.read_excel(
            "samples/dtp_sample_200.xlsx",
            sheet_name="BÁO CÁO DTP",
            engine="calamine",
            has_header=False,
            infer_schema_length=0,
        )
        data_rows = [list(r) for r in df.rows()[1:11]]
        # File thay thế: 10 dòng đầu, tên khác nhưng khớp mẫu *DTP*.
        from decimal import Decimal

        import xlsxwriter

        tmp_path = Path("/tmp")
        p = tmp_path / "dtp_replacement.xlsx"
        header = [str(v) for v in df.rows()[0]]
        qty_idx = header.index("Số lượng")
        amt_idx = header.index("Thành tiền")
        svc_idx = header.index("Dịch vụ")
        total_row: list = [None] * len(header)
        total_row[svc_idx] = "Tổng tiền"
        total_row[qty_idx] = str(sum(Decimal(str(r[qty_idx])) for r in data_rows))
        total_row[amt_idx] = str(sum(Decimal(str(r[amt_idx])) for r in data_rows))
        with xlsxwriter.Workbook(str(p)) as wb:
            ws = wb.add_worksheet("BÁO CÁO DTP")
            ws.write_row(0, 0, header)
            for i, row in enumerate(data_rows, start=1):
                ws.write_row(i, 0, ["" if v is None else str(v) for v in row])
            ws.write_row(len(data_rows) + 1, 0, ["" if v is None else str(v) for v in total_row])
        res = replace_files(admin_ctx, item["id"], [{"filename": "dtp_moi.xlsx", "content": p.read_bytes()}])
        assert res.ok is True
        assert res.data["status"] == "READY"
        assert res.data["precheck"]["rows_valid"] == 10
        got = get_batch_run(admin_ctx, run["id"])
        files = got.data["files"]
        old = [f for f in files if f["original_name"] == "dtp_2026-02.xlsx"]
        assert old and old[0]["match_state"] == "REPLACED"
        new = [f for f in files if f["original_name"] == "dtp_moi.xlsx"]
        assert new and new[0]["match_state"] == "MATCHED"
        assert got.data["items"][0]["status"] == "READY"

    def test_replace_files_busy_item(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import replace_files

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=1)
        content = Path("samples/dtp_sample_200.xlsx").read_bytes()
        res = replace_files(admin_ctx, run["items"][0]["id"], [{"filename": "dtp_moi.xlsx", "content": content}])
        assert res.ok is False
        assert res.code == "BATCH_RUN_BUSY"


class TestCancel:
    def test_cancel_draft(self, batch_env, admin_ctx):
        from app.services.batch_def import activate_batch_def, add_batch_def_items, create_batch_def
        from app.services.batch_run import cancel, create_batch_run

        ds_id, tmpl = _make_ds_template(batch_env)
        res = create_batch_def(admin_ctx, {"code": "DOANH_THU", "name": "DOANH_THU", "max_parallel_per_ds": 2})
        d = res.data
        add_batch_def_items(
            admin_ctx,
            d["id"],
            [
                {
                    "template_id": tmpl,
                    "file_pattern": "*DTP*",
                    "multi_file": True,
                    "is_required": True,
                    "priority": 10,
                    "params_override": {"p_ky": "{ky.thang}"},
                }
            ],
        )
        activate_batch_def(admin_ctx, d["id"])
        run = create_batch_run(admin_ctx, d["id"], "2026-02").data
        res = cancel(admin_ctx, run["id"])
        assert res.ok is True
        assert res.data["status"] == "CANCELLED"

    def test_cancel_running_cancels_queued_children(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import cancel, get_batch_run

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=2)
        res = cancel(admin_ctx, run["id"])
        assert res.ok is True
        assert res.data["status"] == "CANCELLED"
        got = get_batch_run(admin_ctx, run["id"])
        assert all(i["status"] == "NOT_RUN" for i in got.data["items"])

        from sqlalchemy import select

        from app.db.metadata import recon_run, recon_run_queue

        with batch_env.connect() as conn:
            for item in run["items"]:
                child = (
                    conn.execute(select(recon_run).where(recon_run.c.ID == item["current_run_id"])).mappings().first()
                )
                assert child["STATUS"] == "CANCELLED"
                queue = (
                    conn.execute(select(recon_run_queue).where(recon_run_queue.c.RUN_ID == item["current_run_id"]))
                    .mappings()
                    .first()
                )
                assert queue is None

    def test_cancel_done_blocked(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import cancel

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=1)
        _set_child_status(batch_env, run["items"][0]["current_run_id"], "DONE")
        _sync(batch_env, run["id"])
        res = cancel(admin_ctx, run["id"])
        assert res.ok is False
        assert res.code == "VALIDATION_ERROR"

    def test_cancel_forbidden_for_non_creator(self, batch_env, admin_ctx, operator_ctx, mock_ds_ok):
        from app.services.batch_run import cancel

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=1)
        assert cancel(operator_ctx, run["id"]).code == "FORBIDDEN"


class TestCancelExecutor:
    def test_execute_cancelled_child_aborts(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import cancel
        from app.services.run_executor import execute_run

        _d, run = _make_started_run(batch_env, admin_ctx, n_items=1)
        item = run["items"][0]
        child_id = item["current_run_id"]
        # Worker đã claim job (queue PROCESSING) rồi người dùng hủy batch.
        with batch_env.begin() as conn:
            conn.execute(
                text("UPDATE RECON_RUN_QUEUE SET STATUS = 'PROCESSING' WHERE RUN_ID = :r"),
                {"r": child_id},
            )
        assert cancel(admin_ctx, run["id"]).ok is True
        import polars as pl

        db_df = pl.read_parquet("tests/golden/G01_dtp_by_invoice/db.parquet")

        def mock_fetcher(config, profile, p_from, p_to, max_rows, timeout):
            return db_df

        exec_res = execute_run(child_id, mock_fetcher=mock_fetcher)
        assert exec_res["status"] == "CANCELLED"

        from sqlalchemy import select

        from app.db.metadata import recon_batch_run, recon_batch_run_item, recon_run, recon_run_queue

        with batch_env.connect() as conn:
            child = conn.execute(select(recon_run).where(recon_run.c.ID == child_id)).mappings().first()
            assert child["STATUS"] == "CANCELLED"
            queue = conn.execute(select(recon_run_queue).where(recon_run_queue.c.RUN_ID == child_id)).mappings().first()
            assert queue is None
            item_row = (
                conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.ID == item["id"]))
                .mappings()
                .first()
            )
            assert item_row["STATUS"] == "NOT_RUN"
            batch = conn.execute(select(recon_batch_run).where(recon_batch_run.c.ID == run["id"])).mappings().first()
            assert batch["STATUS"] == "CANCELLED"
