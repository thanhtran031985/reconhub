"""Tests cho ma trận kết quả + tải .zip — Bước 7 task 18 (test viết trước).

Spec 10 mục 6: ma trận từ RECON_RUN_SUMMARY của CURRENT_RUN_ID, so với
lần chạy DONE gần nhất kỳ trước; .zip gồm file tổng hợp + file riêng
từng mục, cache theo danh sách CURRENT_RUN_ID.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata


@pytest.fixture()
def batch_env(tmp_path, monkeypatch):
    db_path = tmp_path / "batch7z.db"
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
        "app.services.run_service",
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


def _make_def(batch_env, admin_ctx, code: str = "DOANH_THU", n_items: int = 2):
    from app.services.batch_def import activate_batch_def, add_batch_def_items, create_batch_def

    tmpls = [t for _ds, t in _make_ds_templates(batch_env, [f"DTP_TMPL{i}" for i in range(n_items)])]
    items = [
        {
            "template_id": tmpls[i],
            "file_pattern": f"*DTP{i}*",
            "multi_file": True,
            "is_required": True,
            "priority": 10 * (i + 1),
            "params_override": {"p_ky": "{ky.thang}"},
        }
        for i in range(n_items)
    ]
    res = create_batch_def(admin_ctx, {"code": code, "name": code, "max_parallel_per_ds": 2})
    d = res.data
    assert add_batch_def_items(admin_ctx, d["id"], items).ok is True
    assert activate_batch_def(admin_ctx, d["id"]).ok is True
    return d


def _shift_sample_to_january(tmp_path: Path) -> tuple[bytes, object]:
    """Dời dữ liệu mẫu (Excel + DB parquet) từ tháng 2 sang tháng 1."""

    from decimal import Decimal

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
    data_rows = [list(r) for r in rows[1:201]]
    for r in data_rows:
        if isinstance(r[5], str):
            r[5] = r[5].replace("/02/2026", "/01/2026")
    qty_idx = header.index("Số lượng")
    amt_idx = header.index("Thành tiền")
    svc_idx = header.index("Dịch vụ")
    total_row: list = [None] * len(header)
    total_row[svc_idx] = "Tổng tiền"
    total_row[qty_idx] = str(sum(Decimal(str(r[qty_idx])) for r in data_rows))
    total_row[amt_idx] = str(sum(Decimal(str(r[amt_idx])) for r in data_rows))
    p = tmp_path / "dtp_jan.xlsx"
    with xlsxwriter.Workbook(str(p)) as wb:
        ws = wb.add_worksheet("BÁO CÁO DTP")
        ws.write_row(0, 0, header)
        for i, row in enumerate(data_rows, start=1):
            ws.write_row(i, 0, ["" if v is None else str(v) for v in row])
        ws.write_row(len(data_rows) + 1, 0, ["" if v is None else str(v) for v in total_row])
    db_df = pl.read_parquet("tests/golden/G01_dtp_by_invoice/db.parquet")
    db_df = db_df.with_columns((pl.col("INVOICE_DATE") - pl.duration(days=31)).alias("INVOICE_DATE"))
    return p.read_bytes(), db_df


def _make_done_run(
    batch_env,
    admin_ctx,
    period: str = "2026-02",
    n_items: int = 2,
    d: dict | None = None,
    excel_content: bytes | None = None,
    db_df=None,
):
    """Tạo lần chạy bộ đã chạy xong (2 mục DONE) bằng execute_run thật."""
    import polars as pl

    from app.services.batch_run import add_files, create_batch_run, precheck, start
    from app.services.run_executor import execute_run

    if d is None:
        d = _make_def(batch_env, admin_ctx, n_items=n_items)
    run = create_batch_run(admin_ctx, d["id"], period).data
    content = excel_content or Path("samples/dtp_sample_200.xlsx").read_bytes()
    for i in range(n_items):
        assert add_files(admin_ctx, run["id"], [{"filename": f"dtp{i}_2026-02.xlsx", "content": content}]).ok is True
    assert precheck(admin_ctx, run["id"]).ok is True
    started = start(admin_ctx, run["id"])
    assert started.ok is True
    if db_df is None:
        db_df = pl.read_parquet("tests/golden/G01_dtp_by_invoice/db.parquet")

    def mock_fetcher(config, profile, p_from, p_to, max_rows, timeout):
        return db_df

    for item in started.data["items"]:
        exec_res = execute_run(item["current_run_id"], mock_fetcher=mock_fetcher)
        assert exec_res["status"] == "DONE", exec_res
    return d, started.data


class TestMatrix:
    def test_matrix_done_run(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import matrix

        _d, run = _make_done_run(batch_env, admin_ctx)
        res = matrix(admin_ctx, run["id"])
        assert res.ok is True
        assert res.data["run"]["status"] == "DONE"
        assert res.data["kpis"]["items_with_results"] == 2
        rows = res.data["rows"]
        assert len(rows) == 2
        for row in rows:
            assert row["status"] == "DONE"
            assert row["cnt_matched"] == 184
            assert row["cnt_mismatch"] == 4
            assert row["file_count"] == 1
            assert row["excel_total"] is not None
            assert row["prev_match_rate"] is None
            assert row["match_rate"] is not None

    def test_matrix_prev_period_delta(self, batch_env, tmp_path, admin_ctx, mock_ds_ok):
        from app.services.batch_run import matrix

        jan_content, jan_db = _shift_sample_to_january(tmp_path)
        d = _make_def(batch_env, admin_ctx)
        _d2, _prev = _make_done_run(
            batch_env, admin_ctx, period="2026-01", d=d, excel_content=jan_content, db_df=jan_db
        )
        _d3, run = _make_done_run(batch_env, admin_ctx, period="2026-02", d=d)
        res = matrix(admin_ctx, run["id"])
        assert res.ok is True
        for row in res.data["rows"]:
            assert row["prev_match_rate"] is not None
            assert row["match_rate_delta"] == pytest.approx(0.0, abs=1e-9)

    def test_matrix_draft_run(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_def import activate_batch_def, add_batch_def_items, create_batch_def
        from app.services.batch_run import create_batch_run, matrix

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
        res = matrix(admin_ctx, run["id"])
        assert res.ok is True
        assert res.data["rows"][0]["status"] == "PENDING"
        assert res.data["rows"][0]["cnt_matched"] is None

    def test_matrix_forbidden_for_non_creator(self, batch_env, admin_ctx, operator_ctx, mock_ds_ok):
        from app.services.batch_run import matrix

        _d, run = _make_done_run(batch_env, admin_ctx)
        assert matrix(operator_ctx, run["id"]).code == "NOT_FOUND"


class TestBuildZip:
    def test_build_zip_contents_and_cache(self, batch_env, admin_ctx, mock_ds_ok):
        from app.services.batch_run import build_zip

        _d, run = _make_done_run(batch_env, admin_ctx)
        first = build_zip(admin_ctx, run["id"])
        assert first.ok is True
        assert first.data["cached"] is False
        zip_path = Path(first.data["zip_path"])
        assert zip_path.exists()
        assert first.data["file_name"] == f"DOANH_THU_202602_{run['id']}.zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "00_TONG_HOP_202602.xlsx" in names
            assert "01_DTP_TMPL0_202602.xlsx" in names
            assert "02_DTP_TMPL1_202602.xlsx" in names
        second = build_zip(admin_ctx, run["id"])
        assert second.ok is True
        assert second.data["cached"] is True
        assert second.data["zip_path"] == first.data["zip_path"]

    def test_build_zip_regenerates_after_rerun(self, batch_env, admin_ctx, mock_ds_ok):
        import polars as pl

        from app.services.batch_run import build_zip, rerun_item
        from app.services.run_executor import execute_run

        _d, run = _make_done_run(batch_env, admin_ctx)
        first = build_zip(admin_ctx, run["id"])
        assert first.ok is True
        item = run["items"][0]
        rerun = rerun_item(admin_ctx, item["id"])
        assert rerun.ok is True
        db_df = pl.read_parquet("tests/golden/G01_dtp_by_invoice/db.parquet")

        def mock_fetcher(config, profile, p_from, p_to, max_rows, timeout):
            return db_df

        exec_res = execute_run(rerun.data["current_run_id"], mock_fetcher=mock_fetcher)
        assert exec_res["status"] == "DONE"
        third = build_zip(admin_ctx, run["id"])
        assert third.ok is True
        assert third.data["cached"] is False

    def test_build_zip_forbidden_for_non_creator(self, batch_env, admin_ctx, operator_ctx, mock_ds_ok):
        from app.services.batch_run import build_zip

        _d, run = _make_done_run(batch_env, admin_ctx)
        assert build_zip(operator_ctx, run["id"]).code == "NOT_FOUND"
