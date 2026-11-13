"""Task 85 (A): get_row_detail phải mở được dòng MISSING_IN_DB khi EXCEL_ROW_NOS
dạng gộp file [{"f": ..., "r": ...}] mà f là TÊN file (executor không map được
tên → file_id). Trước fix: int("ten-file.xlsx") ném ValueError → drawer im
lặng không mở. Sau fix: map tên qua SOURCE_FILES_JSON, fallback file duy
nhất của load, bỏ qua cặp không map được — không bao giờ ném lỗi.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_excel_load,
    recon_excel_row,
    recon_file,
    recon_result_row,
    recon_run,
    recon_template,
    recon_user,
)
from app.services.run_service import get_row_detail


def _key_hash(key_text: str) -> str:
    return hashlib.sha256(key_text.encode("utf-8")).hexdigest()


@pytest.fixture
def row_detail_env(tmp_path, monkeypatch):
    db_file = tmp_path / "row_detail_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res_u = conn.execute(
            recon_user.insert().values(
                USERNAME="admin",
                FULL_NAME="Quản trị viên",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        user_id = int(res_u.inserted_primary_key[0])
        seed_perm_basics(engine, {user_id: ["ADMIN"]}, conn=conn)

        ds_id = int(
            conn.execute(
                recon_data_source.insert().values(
                    NAME="ORACLE_TEST",
                    ENV="DEV",
                    PURPOSE="SOURCE",
                    DB_TYPE="ORACLE",
                    HOST="localhost",
                    PORT=1521,
                    SERVICE_NAME="TESTSVC",
                    USERNAME="recon_test",
                    IS_ACTIVE="Y",
                    IS_CURRENT_METADATA="N",
                    CREATED_BY="test",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                )
            ).inserted_primary_key[0]
        )
        f_id = int(
            conn.execute(
                recon_file.insert().values(
                    ORIGINAL_NAME="vtos_2026-07.xlsx",
                    SIZE_BYTES=31000,
                    SHA256="abc12345",
                    STORAGE_PATH="vtos_2026-07.xlsx",
                    UPLOADED_BY="admin",
                    UPLOADED_AT=now,
                )
            ).inserted_primary_key[0]
        )
        f2_id = int(
            conn.execute(
                recon_file.insert().values(
                    ORIGINAL_NAME="vtos_2026-07-b.xlsx",
                    SIZE_BYTES=12000,
                    SHA256="def67890",
                    STORAGE_PATH="vtos_2026-07-b.xlsx",
                    UPLOADED_BY="admin",
                    UPLOADED_AT=now,
                )
            ).inserted_primary_key[0]
        )
        tmpl_id = int(
            conn.execute(
                recon_template.insert().values(
                    CODE="BY_INVOICE_VTOS",
                    NAME="Doanh thu Vtos",
                    OWNER="admin",
                    STATUS="ACTIVE",
                    CURRENT_VERSION=1,
                    CREATED_AT=now,
                    UPDATED_AT=now,
                )
            ).inserted_primary_key[0]
        )

    return {
        "engine": engine,
        "ds_id": ds_id,
        "file_id": f_id,
        "file2_id": f2_id,
        "template_id": tmpl_id,
        "now": now,
    }


def _seed_run_with_rows(
    env: dict[str, Any], *, source_files_json: Any, excel_rows: list[tuple[int, int, str, int]]
) -> int:
    """Seed run 1040 + load + excel rows + 1 dòng MISSING_IN_DB.

    excel_rows: [(source_file_id, excel_row_no, invoice_no, amount)].
    Trả về ROW_NO của dòng MISSING_IN_DB (luôn là 2).
    """
    engine = env["engine"]
    now = env["now"]
    with engine.begin() as conn:
        load_id = int(
            conn.execute(
                recon_excel_load.insert().values(
                    FILE_ID=env["file_id"],
                    SHEET_NAME="Sheet1",
                    TEMPLATE_ID=env["template_id"],
                    TEMPLATE_VERSION=1,
                    ROWS_READ=len(excel_rows),
                    ROWS_INVALID=0,
                    BYTES_EST=1000,
                    FILE_SET_HASH="f" * 64,
                    SOURCE_FILES_JSON=source_files_json,
                    LOADED_AT=now,
                )
            ).inserted_primary_key[0]
        )
        for source_file_id, row_no, inv, amt in excel_rows:
            conn.execute(
                recon_excel_row.insert().values(
                    LOAD_ID=load_id,
                    SOURCE_FILE_ID=source_file_id,
                    EXCEL_ROW_NO=row_no,
                    DATA_JSON={"INVOICE_NO": inv, "TOTAL_AMOUNT": amt},
                    IS_VALID="Y",
                )
            )
        conn.execute(
            recon_run.insert().values(
                ID=1040,
                TEMPLATE_ID=env["template_id"],
                TEMPLATE_VERSION=1,
                PROFILE_CODE="BY_INVOICE",
                DATA_SOURCE_ID=env["ds_id"],
                FILE_ID=env["file_id"],
                EXCEL_LOAD_ID=load_id,
                SHEET_NAME="Sheet1",
                STATUS="DONE",
                STAGE=5,
                PROGRESS_PCT=100,
                P_FROM=datetime(2026, 7, 1, 0, 0, 0),
                P_TO=datetime(2026, 7, 31, 23, 59, 59),
                CREATED_BY="admin",
                CREATED_AT=now,
                STARTED_AT=now,
                FINISHED_AT=now,
                CHECKED_BY=None,
                CHECKED_AT=None,
                TEMP_PURGED_AT=None,
            )
        )
        return load_id


def _insert_result_row(env: dict[str, Any], *, row_no: int, key_text: str, status: str, excel_row_nos: str) -> None:
    engine = env["engine"]
    xl = {"x__TOTAL_AMOUNT": "66805000"} if status == "MISSING_IN_DB" else {"x__TOTAL_AMOUNT": None}
    db = {"d__TOTAL_AMOUNT": None} if status == "MISSING_IN_DB" else {"d__TOTAL_AMOUNT": "1370037884"}
    with engine.begin() as conn:
        conn.execute(
            recon_result_row.insert().values(
                RUN_ID=1040,
                ROW_NO=row_no,
                KEY_TEXT=key_text,
                KEY_HASH=_key_hash(key_text),
                STATUS=status,
                KEY_JSON={"INVOICE_NO": key_text.split(" | ")[1]},
                EXCEL_JSON=xl,
                DB_JSON=db,
                DIFF_JSON={"diff__TOTAL_AMOUNT": "66805000" if status == "MISSING_IN_DB" else "-1370037884"},
                EXCEL_ROW_NOS=excel_row_nos,
                ABS_DIFF_MAIN=None,
                ABS_DIFF_SORT=66805000.0,
            )
        )


_ADMIN = Ctx(user_id=1, username="admin", full_name="Quản trị viên", roles=[Role.ADMIN])


class TestGetRowDetailNameFileRef:
    """Task 85 (A): EXCEL_ROW_NOS dạng [{"f": tên file, "r": dòng}]."""

    def test_name_mapped_via_source_files_json(self, row_detail_env):
        env = row_detail_env
        _seed_run_with_rows(
            env,
            source_files_json=[{"name": "vtos_2026-07.xlsx", "file_id": env["file_id"]}],
            excel_rows=[(env["file_id"], 5, "C26TBD0084556", 66805000)],
        )
        _insert_result_row(
            env,
            row_no=2,
            key_text="2026-04-15 08:47:39 | C26TBD0084556",
            status="MISSING_IN_DB",
            excel_row_nos=json.dumps([{"f": "vtos_2026-07.xlsx", "r": 5}], ensure_ascii=False),
        )
        res = get_row_detail(_ADMIN, run_id=1040, row_no=2)
        assert res.ok, res.message
        assert res.data["status"] == "MISSING_IN_DB"
        raw = res.data["excel_raw_rows"]
        assert raw is not None and len(raw) == 1
        assert raw[0]["excel_row_no"] == 5
        assert raw[0]["data"]["INVOICE_NO"] == "C26TBD0084556"

    def test_name_unmapped_single_file_fallback(self, row_detail_env):
        env = row_detail_env
        _seed_run_with_rows(
            env,
            source_files_json=[],
            excel_rows=[(env["file_id"], 5, "C26TBD0084556", 66805000)],
        )
        _insert_result_row(
            env,
            row_no=2,
            key_text="2026-04-15 08:47:39 | C26TBD0084556",
            status="MISSING_IN_DB",
            excel_row_nos=json.dumps([{"f": "vtos_2026-07.xlsx", "r": 5}], ensure_ascii=False),
        )
        res = get_row_detail(_ADMIN, run_id=1040, row_no=2)
        assert res.ok, res.message
        raw = res.data["excel_raw_rows"]
        assert raw is not None and len(raw) == 1
        assert raw[0]["excel_row_no"] == 5

    def test_name_unmapped_multi_file_no_crash(self, row_detail_env):
        env = row_detail_env
        _seed_run_with_rows(
            env,
            source_files_json=[],
            excel_rows=[
                (env["file_id"], 5, "C26TBD0084556", 66805000),
                (env["file2_id"], 3, "C26TBD0011111", 1000),
            ],
        )
        _insert_result_row(
            env,
            row_no=2,
            key_text="2026-04-15 08:47:39 | C26TBD0084556",
            status="MISSING_IN_DB",
            excel_row_nos=json.dumps([{"f": "file-khong-co-trong-load.xlsx", "r": 5}], ensure_ascii=False),
        )
        res = get_row_detail(_ADMIN, run_id=1040, row_no=2)
        assert res.ok, res.message
        # Không map được và load có 2 file → bỏ qua cặp đó, drawer vẫn mở.
        assert res.data["excel_raw_rows"] in (None, [])

    def test_int_file_ref_still_works(self, row_detail_env):
        env = row_detail_env
        _seed_run_with_rows(
            env,
            source_files_json=[{"name": "vtos_2026-07.xlsx", "file_id": env["file_id"]}],
            excel_rows=[(env["file_id"], 5, "C26TBD0084556", 66805000)],
        )
        _insert_result_row(
            env,
            row_no=2,
            key_text="2026-04-15 08:47:39 | C26TBD0084556",
            status="MISSING_IN_DB",
            excel_row_nos=json.dumps([{"f": env["file_id"], "r": 5}], ensure_ascii=False),
        )
        res = get_row_detail(_ADMIN, run_id=1040, row_no=2)
        assert res.ok, res.message
        assert res.data["excel_raw_rows"] is not None and len(res.data["excel_raw_rows"]) == 1

    def test_plain_row_nos_still_works(self, row_detail_env):
        env = row_detail_env
        _seed_run_with_rows(
            env,
            source_files_json=[{"name": "vtos_2026-07.xlsx", "file_id": env["file_id"]}],
            excel_rows=[(env["file_id"], 5, "C26TBD0084556", 66805000)],
        )
        _insert_result_row(
            env,
            row_no=2,
            key_text="2026-04-15 08:47:39 | C26TBD0084556",
            status="MISSING_IN_DB",
            excel_row_nos="5",
        )
        res = get_row_detail(_ADMIN, run_id=1040, row_no=2)
        assert res.ok, res.message
        assert res.data["excel_raw_rows"] is not None and len(res.data["excel_raw_rows"]) == 1

    def test_missing_in_excel_still_ok(self, row_detail_env):
        env = row_detail_env
        _seed_run_with_rows(
            env,
            source_files_json=[{"name": "vtos_2026-07.xlsx", "file_id": env["file_id"]}],
            excel_rows=[(env["file_id"], 5, "C26TBD0084556", 66805000)],
        )
        _insert_result_row(
            env,
            row_no=3,
            key_text="2026-07-23 16:57:54 | C26TBP0003038",
            status="MISSING_IN_EXCEL",
            excel_row_nos="",
        )
        res = get_row_detail(_ADMIN, run_id=1040, row_no=3)
        assert res.ok, res.message
        assert res.data["status"] == "MISSING_IN_EXCEL"
        assert res.data["excel_raw_rows"] in (None, [])
