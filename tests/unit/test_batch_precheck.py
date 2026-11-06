"""Tests cho precheck + start lần chạy bộ — Bước 6 task 18 (test viết trước).

Spec 10 mục 5.4 (precheck) và 5.5 (thực thi): kiểm tra trước theo từng
mục, tạo run con QUEUED, xác nhận PROD một lần, mục WARN/ERROR.
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
    db_path = tmp_path / "batch6.db"
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


@pytest.fixture()
def operator_ctx() -> Ctx:
    return Ctx(user_id=3, username="operator", full_name="operator", roles=["OPERATOR"])


class FakeConn:
    def close(self) -> None:
        pass


@pytest.fixture()
def mock_ds_ok(monkeypatch):
    monkeypatch.setattr("app.services.batch_run.open_source_connection", lambda ds_id: FakeConn())


def _sample_config(params: list[dict]) -> dict:
    data = json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
    data["db_source"]["params"] = params
    return data


def _default_params() -> list[dict]:
    return [
        {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
        {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
        {"name": "p_ky", "type": "text", "source": "user", "label": "Kỳ", "required": True},
        {"name": "p_so", "type": "number", "source": "user", "label": "Số", "required": False},
    ]


def _make_data_source(engine, env: str = "DEV", name: str = "ORACLE_TEST") -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        ds_id = conn.execute(
            text(
                "INSERT INTO RECON_DATA_SOURCE (NAME, ENV, PURPOSE, DB_TYPE, HOST, "
                "PORT, SERVICE_NAME, CALL_TIMEOUT_S, MAX_ROWS, IS_ACTIVE, "
                "IS_CURRENT_METADATA, CREATED_BY, CREATED_AT, UPDATED_AT) VALUES "
                "(:name, :env, 'SOURCE', 'ORACLE', 'localhost', 1521, 'XE', "
                "600, 1000000, 'Y', 'N', 'admin', :now, :now)"
            ),
            {"name": name, "env": env, "now": now},
        ).lastrowid
    return int(ds_id)


def _make_template(engine, code: str, ds_id: int) -> int:
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
                "cfg": json.dumps(_sample_config(_default_params()), ensure_ascii=False),
                "ds": ds_id,
                "now": now,
            },
        )
    return int(tmpl_id)


def _make_run(batch_env, admin_ctx, env: str = "DEV", items: list[dict] | None = None):
    from app.services.batch_def import activate_batch_def, add_batch_def_items, create_batch_def
    from app.services.batch_run import create_batch_run

    if items is None:
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


def _write_custom_xlsx(tmp_path: Path, name: str, data_rows: list[list]) -> Path:
    import polars as pl
    import xlsxwriter

    df = pl.read_excel(
        "samples/dtp_sample_200.xlsx",
        sheet_name="BÁO CÁO DTP",
        engine="calamine",
        has_header=False,
        infer_schema_length=0,
    )
    rows = df.rows()
    header = [str(v) for v in rows[0]]
    from decimal import Decimal

    qty_idx = header.index("Số lượng")
    amt_idx = header.index("Thành tiền")
    svc_idx = header.index("Dịch vụ")
    qty = sum(Decimal(str(r[qty_idx])) for r in data_rows if r[qty_idx] not in (None, ""))
    amt = sum(Decimal(str(r[amt_idx])) for r in data_rows if r[amt_idx] not in (None, ""))
    total_row: list = [None] * len(header)
    total_row[svc_idx] = "Tổng tiền"
    total_row[qty_idx] = str(qty)
    total_row[amt_idx] = str(amt)
    p = tmp_path / name
    with xlsxwriter.Workbook(str(p)) as wb:
        ws = wb.add_worksheet("BÁO CÁO DTP")
        ws.write_row(0, 0, header)
        for i, row in enumerate(data_rows, start=1):
            ws.write_row(i, 0, ["" if v is None else str(v) for v in row])
        ws.write_row(len(data_rows) + 1, 0, ["" if v is None else str(v) for v in total_row])
    return p


def _check_level(precheck: dict, key: str) -> str | None:
    for c in precheck.get("checks", []):
        if c["key"] == key:
            return c["level"]
    return None


class TestPrecheck:
    def test_precheck_ready(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import get_batch_run, precheck

        _d, run = _make_run(batch_env, admin_ctx)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        res = precheck(admin_ctx, run["id"])
        assert res.ok is True
        item = res.data["items"][0]
        assert item["status"] == "READY"
        assert item["precheck"]["rows_read"] == 201
        assert item["precheck"]["rows_valid"] == 200
        assert item["precheck"]["rows_invalid"] == 0
        assert item["precheck"]["rows_out_of_range"] == 0
        assert item["precheck"]["control_total"]["matched"] is True
        assert _check_level(item["precheck"], "template") == "ok"
        assert _check_level(item["precheck"], "data_source") == "ok"
        assert get_batch_run(admin_ctx, run["id"]).data["status"] == "DRAFT"

    def test_precheck_warn_control_total(self, batch_env, tmp_path, admin_ctx, mock_ds_ok):
        from app.services.batch_run import add_files, precheck

        _d, run = _make_run(batch_env, admin_ctx)
        import polars as pl

        df = pl.read_excel(
            "samples/dtp_sample_200.xlsx",
            sheet_name="BÁO CÁO DTP",
            engine="calamine",
            has_header=False,
            infer_schema_length=0,
        )
        data_rows = [list(r) for r in df.rows()[1:11]]
        # File có dòng tổng sai (999 thay vì tổng thật).
        import xlsxwriter

        with xlsxwriter.Workbook(str(tmp_path / "dtp_wrong2.xlsx")) as wb:
            ws = wb.add_worksheet("BÁO CÁO DTP")
            header = [str(v) for v in df.rows()[0]]
            ws.write_row(0, 0, header)
            for i, row in enumerate(data_rows, start=1):
                ws.write_row(i, 0, ["" if v is None else str(v) for v in row])
            total_row: list = [None] * len(header)
            total_row[header.index("Dịch vụ")] = "Tổng tiền"
            total_row[header.index("Số lượng")] = "999"
            total_row[header.index("Thành tiền")] = "999"
            ws.write_row(len(data_rows) + 1, 0, ["" if v is None else str(v) for v in total_row])
        res = add_files(
            admin_ctx,
            run["id"],
            [{"filename": "dtp_wrong2.xlsx", "content": (tmp_path / "dtp_wrong2.xlsx").read_bytes()}],
        )
        assert res.ok is True
        out = precheck(admin_ctx, run["id"])
        assert out.ok is True
        item = out.data["items"][0]
        assert item["status"] == "WARN"
        assert _check_level(item["precheck"], "control_total") == "warn"
        assert item["precheck"]["control_total"]["matched"] is False

    def test_precheck_warn_out_of_range(self, batch_env, tmp_path, admin_ctx, mock_ds_ok):
        from app.services.batch_run import add_files, precheck

        _d, run = _make_run(batch_env, admin_ctx)
        import polars as pl

        df = pl.read_excel(
            "samples/dtp_sample_200.xlsx",
            sheet_name="BÁO CÁO DTP",
            engine="calamine",
            has_header=False,
            infer_schema_length=0,
        )
        data_rows = [list(r) for r in df.rows()[1:11]]
        march_row = list(data_rows[0])
        march_row[5] = "01/03/2026 00:00:00"
        data_rows.append(march_row)
        p = _write_custom_xlsx(tmp_path, "dtp_march.xlsx", data_rows)
        res = add_files(admin_ctx, run["id"], [{"filename": "dtp_march.xlsx", "content": p.read_bytes()}])
        assert res.ok is True
        out = precheck(admin_ctx, run["id"])
        assert out.ok is True
        item = out.data["items"][0]
        assert item["status"] == "WARN"
        assert item["precheck"]["rows_out_of_range"] == 1
        assert _check_level(item["precheck"], "out_of_range") == "warn"

    def test_precheck_error_ds_unreachable(self, batch_env, admin_ctx):
        from app.services.batch_run import precheck

        _d, run = _make_run(batch_env, admin_ctx)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        out = precheck(admin_ctx, run["id"])
        assert out.ok is True
        item = out.data["items"][0]
        assert item["status"] == "ERROR"
        assert _check_level(item["precheck"], "data_source") == "error"

    def test_precheck_error_template_archived(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import precheck

        _d, run = _make_run(batch_env, admin_ctx)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        with batch_env.begin() as conn:
            conn.execute(text("UPDATE RECON_TEMPLATE SET STATUS = 'ARCHIVED'"))
        out = precheck(admin_ctx, run["id"])
        assert out.ok is True
        assert out.data["items"][0]["status"] == "ERROR"
        assert _check_level(out.data["items"][0]["precheck"], "template") == "error"

    def test_precheck_single_item(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import precheck

        ds_id = _make_data_source(batch_env, name="ORACLE_TEST2")
        t1 = _make_template(batch_env, "DTP_A", ds_id)
        t2 = _make_template(batch_env, "DTP_B", ds_id)
        _d, run = _make_run(
            batch_env,
            admin_ctx,
            items=[
                {
                    "template_id": t1,
                    "file_pattern": "*A*",
                    "multi_file": True,
                    "is_required": True,
                    "priority": 10,
                    "params_override": {"p_ky": "{ky.thang}"},
                },
                {
                    "template_id": t2,
                    "file_pattern": "*B*",
                    "multi_file": True,
                    "is_required": True,
                    "priority": 20,
                    "params_override": {"p_ky": "{ky.thang}"},
                },
            ],
        )
        from app.services.batch_run import add_files

        content = Path("samples/dtp_sample_200.xlsx").read_bytes()
        add_files(admin_ctx, run["id"], [{"filename": "a_file.xlsx", "content": content}])
        add_files(admin_ctx, run["id"], [{"filename": "b_file.xlsx", "content": content}])
        first_item = run["items"][0]
        out = precheck(admin_ctx, run["id"], item_ids=[first_item["id"]])
        assert out.ok is True
        assert len(out.data["items"]) == 1
        assert out.data["items"][0]["status"] == "READY"

    def test_precheck_forbidden_for_non_creator(self, batch_env, admin_ctx, operator_ctx, mock_ds_ok):
        from app.services.batch_run import precheck

        _d, run = _make_run(batch_env, admin_ctx)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        assert precheck(operator_ctx, run["id"]).code == "FORBIDDEN"

    def test_precheck_not_draft_after_start(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import precheck, start

        _d, run = _make_run(batch_env, admin_ctx)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        assert precheck(admin_ctx, run["id"]).ok is True
        assert start(admin_ctx, run["id"]).ok is True
        assert precheck(admin_ctx, run["id"]).code == "BATCH_RUN_NOT_DRAFT"


class TestStart:
    def test_start_ok(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import get_batch_run, precheck, start

        _d, run = _make_run(batch_env, admin_ctx)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        assert precheck(admin_ctx, run["id"]).ok is True
        res = start(admin_ctx, run["id"])
        assert res.ok is True
        assert res.data["status"] == "RUNNING"
        assert res.data["started"] == 1
        assert res.data["not_run"] == 0
        got = get_batch_run(admin_ctx, run["id"])
        item = got.data["items"][0]
        assert item["status"] == "QUEUED"
        assert item["current_run_id"] is not None
        assert item["attempt_no"] == 1

        from sqlalchemy import select

        from app.db.metadata import recon_run, recon_run_queue

        with batch_env.connect() as conn:
            child = conn.execute(select(recon_run).where(recon_run.c.ID == item["current_run_id"])).mappings().first()
            assert child is not None
            assert child["STATUS"] == "QUEUED"
            assert child["BATCH_RUN_ID"] == run["id"]
            assert child["BATCH_RUN_ITEM_ID"] == item["id"]
            assert child["TEMPLATE_VERSION"] == 1
            assert child["PROFILE_CODE"] == "BY_INVOICE"
            assert str(child["P_FROM"]).startswith("2026-02-01")
            assert str(child["P_TO"]).startswith("2026-02-28")
            queue = (
                conn.execute(select(recon_run_queue).where(recon_run_queue.c.RUN_ID == item["current_run_id"]))
                .mappings()
                .first()
            )
            assert queue is not None
            assert queue["STATUS"] == "READY"

    def test_start_prod_requires_confirm(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import precheck, start

        _d, run = _make_run(batch_env, admin_ctx, env="PROD")
        _add_sample_file(batch_env, admin_ctx, run["id"])
        assert precheck(admin_ctx, run["id"]).ok is True
        res = start(admin_ctx, run["id"])
        assert res.ok is False
        assert res.code == "PROD_CONFIRM_REQUIRED"
        ok = start(admin_ctx, run["id"], confirm_prod=True)
        assert ok.ok is True
        assert ok.data["prod_confirmed_by"] == "admin"
        assert "ORACLE_TEST" in str(ok.data.get("prod_data_sources") or "")

    def test_start_warn_excluded_when_flag_off(self, batch_env, tmp_path, admin_ctx, mock_ds_ok):
        from app.services.batch_run import add_files, get_batch_run, precheck, start

        _d, run = _make_run(batch_env, admin_ctx)
        import polars as pl
        import xlsxwriter

        df = pl.read_excel(
            "samples/dtp_sample_200.xlsx",
            sheet_name="BÁO CÁO DTP",
            engine="calamine",
            has_header=False,
            infer_schema_length=0,
        )
        data_rows = [list(r) for r in df.rows()[1:11]]
        header = [str(v) for v in df.rows()[0]]
        bad = tmp_path / "dtp_bad_total.xlsx"
        with xlsxwriter.Workbook(str(bad)) as wb:
            ws = wb.add_worksheet("BÁO CÁO DTP")
            ws.write_row(0, 0, header)
            for i, row in enumerate(data_rows, start=1):
                ws.write_row(i, 0, ["" if v is None else str(v) for v in row])
            total_row: list = [None] * len(header)
            total_row[header.index("Dịch vụ")] = "Tổng tiền"
            total_row[header.index("Số lượng")] = "999"
            total_row[header.index("Thành tiền")] = "999"
            ws.write_row(len(data_rows) + 1, 0, ["" if v is None else str(v) for v in total_row])
        add_files(admin_ctx, run["id"], [{"filename": "dtp_bad_total.xlsx", "content": bad.read_bytes()}])
        assert precheck(admin_ctx, run["id"]).data["items"][0]["status"] == "WARN"
        res = start(admin_ctx, run["id"], include_warn=False)
        assert res.ok is True
        assert res.data["started"] == 0
        assert res.data["not_run"] == 1
        assert res.data["status"] == "PARTIAL"
        got = get_batch_run(admin_ctx, run["id"])
        assert got.data["items"][0]["status"] == "NOT_RUN"

    def test_start_pending_item_not_run(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import get_batch_run, start

        _d, run = _make_run(batch_env, admin_ctx)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        res = start(admin_ctx, run["id"])
        assert res.ok is True
        assert res.data["started"] == 0
        assert get_batch_run(admin_ctx, run["id"]).data["items"][0]["status"] == "NOT_RUN"

    def test_start_optional_no_file_skipped(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import get_batch_run, start

        ds_id = _make_data_source(batch_env, name="ORACLE_TEST2")
        tmpl = _make_template(batch_env, "DTP_TMPL", ds_id)
        _d, run = _make_run(
            batch_env,
            admin_ctx,
            items=[
                {
                    "template_id": tmpl,
                    "file_pattern": "*DTP*",
                    "multi_file": True,
                    "is_required": False,
                    "priority": 100,
                    "params_override": {"p_ky": "{ky.thang}"},
                }
            ],
        )
        res = start(admin_ctx, run["id"])
        assert res.ok is True
        item = get_batch_run(admin_ctx, run["id"]).data["items"][0]
        assert item["status"] == "SKIPPED"
        assert item["skip_reason"] == "NO_FILE"

    def test_start_twice_blocked(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import precheck, start

        _d, run = _make_run(batch_env, admin_ctx)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        assert precheck(admin_ctx, run["id"]).ok is True
        assert start(admin_ctx, run["id"]).ok is True
        assert start(admin_ctx, run["id"]).code == "BATCH_RUN_NOT_DRAFT"


class TestBatchChildExecution:
    def _started_run(self, batch_env, admin_ctx):
        from app.services.batch_run import get_batch_run, precheck, start

        _d, run = _make_run(batch_env, admin_ctx)
        _add_sample_file(batch_env, admin_ctx, run["id"])
        assert precheck(admin_ctx, run["id"]).ok is True
        started = start(admin_ctx, run["id"])
        assert started.ok is True
        item = get_batch_run(admin_ctx, run["id"]).data["items"][0]
        return run["id"], item["current_run_id"]

    def test_execute_child_run_completes_batch(self, batch_env, admin_ctx, mock_ds_ok):
        import polars as pl

        from app.services.run_executor import execute_run

        run_id, child_id = self._started_run(batch_env, admin_ctx)
        db_df = pl.read_parquet("tests/golden/G01_dtp_by_invoice/db.parquet")

        def mock_fetcher(config, profile, p_from, p_to, max_rows, timeout):
            return db_df

        exec_res = execute_run(child_id, mock_fetcher=mock_fetcher)
        assert exec_res["status"] == "DONE"

        from sqlalchemy import select

        from app.db.metadata import recon_batch_run, recon_batch_run_item, recon_run, recon_run_summary

        with batch_env.connect() as conn:
            child = conn.execute(select(recon_run).where(recon_run.c.ID == child_id)).mappings().first()
            assert child["STATUS"] == "DONE"
            item = (
                conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.CURRENT_RUN_ID == child_id))
                .mappings()
                .first()
            )
            assert item["STATUS"] == "DONE"
            batch = conn.execute(select(recon_batch_run).where(recon_batch_run.c.ID == run_id)).mappings().first()
            assert batch["STATUS"] == "DONE"
            summ = (
                conn.execute(select(recon_run_summary).where(recon_run_summary.c.RUN_ID == child_id)).mappings().first()
            )
            assert summ["CNT_MATCHED"] == 184
            assert summ["CNT_MISMATCH"] == 4

    def test_execute_child_run_failure_marks_partial(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.run_executor import execute_run

        run_id, child_id = self._started_run(batch_env, admin_ctx)

        def failing_fetcher(config, profile, p_from, p_to, max_rows, timeout):
            raise RuntimeError("Oracle ngắt kết nối")

        exec_res = execute_run(child_id, mock_fetcher=failing_fetcher)
        assert exec_res["status"] == "FAILED"

        from sqlalchemy import select

        from app.db.metadata import recon_batch_run, recon_batch_run_item, recon_run

        with batch_env.connect() as conn:
            child = conn.execute(select(recon_run).where(recon_run.c.ID == child_id)).mappings().first()
            assert child["STATUS"] == "FAILED"
            item = (
                conn.execute(select(recon_batch_run_item).where(recon_batch_run_item.c.CURRENT_RUN_ID == child_id))
                .mappings()
                .first()
            )
            assert item["STATUS"] == "FAILED"
            batch = conn.execute(select(recon_batch_run).where(recon_batch_run.c.ID == run_id)).mappings().first()
            assert batch["STATUS"] == "PARTIAL"
