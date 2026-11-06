"""Tests cho nạp nhiều file theo FILE_SET_HASH — Bước 5 task 18 (test viết trước).

load_excel_files_to_temp: gộp nhiều file, header đã map phải khớp,
control total kiểm từng file, EXCEL_LOAD theo FILE_SET_HASH.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest
import xlsxwriter
from sqlalchemy import create_engine, text

from app.core.context import Ctx
from app.db.metadata import metadata

SAMPLE_XLSX = Path("samples/dtp_sample_200.xlsx")
SHEET = "BÁO CÁO DTP"


@pytest.fixture()
def fileset_env(tmp_path, monkeypatch):
    db_path = tmp_path / "fileset.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    for mod in [
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.excel_load",
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


def _make_template(engine) -> int:
    data = json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
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
        tmpl_id = conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE (CODE, NAME, OWNER, STATUS, CURRENT_VERSION, "
                "CREATED_AT, UPDATED_AT, ROW_VERSION) VALUES ('DTP_TMPL', 'DTP_TMPL', "
                "'admin', 'ACTIVE', 1, :now, :now, 1)"
            ),
            {"now": now},
        ).lastrowid
        conn.execute(
            text(
                "INSERT INTO RECON_TEMPLATE_VERSION (TEMPLATE_ID, VERSION, STATUS, "
                "CONFIG_JSON, DATA_SOURCE_ID, CREATED_BY, CREATED_AT) VALUES (:t, 1, "
                "'ACTIVE', :cfg, :ds, 'admin', :now)"
            ),
            {"t": tmpl_id, "cfg": json.dumps(data, ensure_ascii=False), "ds": ds_id, "now": now},
        )
    return int(tmpl_id)


def _sample_rows() -> tuple[list[str], list[list]]:
    """Đọc file mẫu: header + 200 dòng dữ liệu + dòng tổng."""
    df = pl.read_excel(SAMPLE_XLSX, sheet_name=SHEET, engine="calamine", has_header=False, infer_schema_length=0)
    rows = df.rows()
    header = [str(v) for v in rows[0]]
    return header, [list(r) for r in rows[1:201]]


def _total_row(header: list[str], data_rows: list[list]) -> list:
    qty_idx = header.index("Số lượng")
    amt_idx = header.index("Thành tiền")
    svc_idx = header.index("Dịch vụ")
    qty = sum(Decimal(str(r[qty_idx])) for r in data_rows if r[qty_idx] not in (None, ""))
    amt = sum(Decimal(str(r[amt_idx])) for r in data_rows if r[amt_idx] not in (None, ""))
    row: list = [None] * len(header)
    row[svc_idx] = "Tổng tiền"
    row[qty_idx] = str(qty)
    row[amt_idx] = str(amt)
    return row


def _write_dtp_xlsx(
    path: Path, header: list[str], data_rows: list[list], total_header: list[str] | None = None
) -> None:
    with xlsxwriter.Workbook(str(path)) as wb:
        ws = wb.add_worksheet(SHEET)
        ws.write_row(0, 0, header)
        for i, row in enumerate(data_rows, start=1):
            ws.write_row(i, 0, ["" if v is None else str(v) for v in row])
        ws.write_row(
            len(data_rows) + 1,
            0,
            ["" if v is None else str(v) for v in _total_row(total_header or header, data_rows)],
        )


def _insert_file(engine, path: Path, name: str) -> int:
    content = path.read_bytes()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        file_id = conn.execute(
            text(
                "INSERT INTO RECON_FILE (ORIGINAL_NAME, STORAGE_PATH, SIZE_BYTES, "
                "SHA256, SHEETS_JSON, UPLOADED_BY, UPLOADED_AT) VALUES (:n, :p, :s, "
                ":sha, :sheets, 'admin', :now)"
            ),
            {
                "n": name,
                "p": str(path),
                "s": len(content),
                "sha": hashlib.sha256(content).hexdigest(),
                "sheets": json.dumps([SHEET], ensure_ascii=False),
                "now": now,
            },
        ).lastrowid
    return int(file_id)


def _split_sample(tmp_path: Path) -> tuple[list[str], list[Path]]:
    header, data_rows = _sample_rows()
    parts = [data_rows[:70], data_rows[70:140], data_rows[140:]]
    paths: list[Path] = []
    for i, part in enumerate(parts, start=1):
        p = tmp_path / f"dtp_part{i}.xlsx"
        _write_dtp_xlsx(p, header, part)
        paths.append(p)
    return header, paths


class TestLoadFileset:
    def test_load_three_files_ok(self, fileset_env, tmp_path, admin_ctx):
        from app.services.batch_formula import compute_file_set_hash
        from app.services.excel_load import load_excel_files_to_temp

        tmpl_id = _make_template(fileset_env)
        _header, paths = _split_sample(tmp_path)
        file_ids = [_insert_file(fileset_env, p, p.name) for p in paths]
        res = load_excel_files_to_temp(admin_ctx, file_ids, tmpl_id, 1)
        assert res.ok is True
        data = res.data
        assert data["rows_read"] == 203
        assert data["rows_valid"] == 200
        assert data["rows_invalid"] == 0
        assert data["control_total_matched"] is True
        assert data["is_reused"] is False
        assert len(data["source_files"]) == 3
        assert {s["file_id"] for s in data["source_files"]} == set(file_ids)
        assert all(s["control_total_ok"] == "Y" for s in data["source_files"])
        shas = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        assert data["file_set_hash"] == compute_file_set_hash(shas, SHEET, tmpl_id, 1)

        from sqlalchemy import select

        from app.db.metadata import recon_excel_load, recon_excel_row

        with fileset_env.connect() as conn:
            load = (
                conn.execute(select(recon_excel_load).where(recon_excel_load.c.ID == data["load_id"]))
                .mappings()
                .first()
            )
            assert load is not None
            assert load["FILE_ID"] == file_ids[0]
            rows = (
                conn.execute(select(recon_excel_row).where(recon_excel_row.c.LOAD_ID == data["load_id"]))
                .mappings()
                .all()
            )
            assert len(rows) == 200
            by_file = {fid: [r for r in rows if r["SOURCE_FILE_ID"] == fid] for fid in file_ids}
            assert [len(by_file[fid]) for fid in file_ids] == [70, 70, 60]
            assert {r["EXCEL_ROW_NO"] for r in by_file[file_ids[0]]} == set(range(2, 72))

    def test_load_fileset_reuse(self, fileset_env, tmp_path, admin_ctx):
        from app.services.excel_load import load_excel_files_to_temp

        tmpl_id = _make_template(fileset_env)
        _header, paths = _split_sample(tmp_path)
        file_ids = [_insert_file(fileset_env, p, p.name) for p in paths]
        first = load_excel_files_to_temp(admin_ctx, file_ids, tmpl_id, 1)
        assert first.ok is True
        second = load_excel_files_to_temp(admin_ctx, file_ids, tmpl_id, 1)
        assert second.ok is True
        assert second.data["is_reused"] is True
        assert second.data["load_id"] == first.data["load_id"]
        assert second.data["rows_valid"] == 200

    def test_load_fileset_header_mismatch(self, fileset_env, tmp_path, admin_ctx):
        from app.services.excel_load import load_excel_files_to_temp

        tmpl_id = _make_template(fileset_env)
        header, paths = _split_sample(tmp_path)
        bad_header = ["Thanh tien" if h == "Thành tiền" else h for h in header]
        bad_path = tmp_path / "dtp_bad.xlsx"
        _write_dtp_xlsx(bad_path, bad_header, _sample_rows()[1][:10], total_header=header)
        file_ids = [_insert_file(fileset_env, p, p.name) for p in paths[:2]]
        file_ids.append(_insert_file(fileset_env, bad_path, "dtp_bad.xlsx"))
        res = load_excel_files_to_temp(admin_ctx, file_ids, tmpl_id, 1)
        assert res.ok is False
        assert res.code == "BATCH_MERGE_HEADER_MISMATCH"
        assert "dtp_bad.xlsx" in res.message

    def test_load_fileset_control_total_per_file(self, fileset_env, tmp_path, admin_ctx):
        from app.services.excel_load import load_excel_files_to_temp

        tmpl_id = _make_template(fileset_env)
        header, paths = _split_sample(tmp_path)
        data_rows = _sample_rows()[1][:10]
        bad_row = _total_row(header, data_rows)
        bad_row[header.index("Thành tiền")] = "999"
        with xlsxwriter.Workbook(str(tmp_path / "dtp_wrong_total.xlsx")) as wb:
            ws = wb.add_worksheet(SHEET)
            ws.write_row(0, 0, header)
            for i, row in enumerate(data_rows, start=1):
                ws.write_row(i, 0, ["" if v is None else str(v) for v in row])
            ws.write_row(len(data_rows) + 1, 0, ["" if v is None else str(v) for v in bad_row])
        file_ids = [_insert_file(fileset_env, paths[0], paths[0].name)]
        file_ids.append(_insert_file(fileset_env, tmp_path / "dtp_wrong_total.xlsx", "dtp_wrong_total.xlsx"))
        res = load_excel_files_to_temp(admin_ctx, file_ids, tmpl_id, 1)
        assert res.ok is True
        assert res.data["control_total_matched"] is False
        by_name = {s["file_id"]: s for s in res.data["source_files"]}
        assert by_name[file_ids[0]]["control_total_ok"] == "Y"
        assert by_name[file_ids[1]]["control_total_ok"] == "N"

    def test_load_single_file_same_as_single_load(self, fileset_env, tmp_path, admin_ctx):
        from app.services.excel_load import load_excel_files_to_temp, load_excel_to_temp

        tmpl_id = _make_template(fileset_env)
        _header, paths = _split_sample(tmp_path)
        file_id = _insert_file(fileset_env, paths[0], paths[0].name)
        via_single = load_excel_to_temp(admin_ctx, file_id=file_id, template_id=tmpl_id, template_version=1)
        assert via_single.ok is True
        via_set = load_excel_files_to_temp(admin_ctx, [file_id], tmpl_id, 1)
        assert via_set.ok is True
        assert via_set.data["is_reused"] is True
        assert via_set.data["load_id"] == via_single.data["load_id"]
