"""Tests cho claim job theo bộ — Bước 6 task 18 (test viết trước).

Giới hạn song song theo Data Source + ưu tiên PRIORITY (spec 10 §5.5).
SQLite: kiểm tra 2 process riêng. Oracle: skip khi thiếu ORACLE_TEST_*.
"""

from __future__ import annotations

import multiprocessing as mp
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from app.db.dialect import DatabaseDialect
from app.db.metadata import metadata


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def claim_env(tmp_path):
    db_path = tmp_path / "claim.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    return engine, str(db_path)


def _seed_jobs(engine, max_parallel: int = 1, with_standalone: bool = True) -> dict[str, int]:
    """3 run con cùng batch + DS (ưu tiên 30/10/20), 1 run đơn lẻ tùy chọn."""
    now = _now()
    ids: dict[str, int] = {}
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
        def_id = conn.execute(
            text(
                "INSERT INTO RECON_BATCH_DEF (CODE, NAME, STATUS, MAX_PARALLEL_PER_DS, "
                "OWNER_ID, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES ('B1', 'B1', 'ACTIVE', :m, 1, 'admin', :now, 'admin', :now, 1)"
            ),
            {"m": max_parallel, "now": now},
        ).lastrowid
        run_id = conn.execute(
            text(
                "INSERT INTO RECON_BATCH_RUN (BATCH_DEF_ID, NAME, PERIOD, PERIOD_FROM, "
                "PERIOD_TO, STATUS, INCLUDE_WARN, CNT_ITEMS, CNT_DONE, CNT_FAILED, "
                "CNT_SKIPPED, CNT_NOT_RUN, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, "
                "ROW_VERSION) VALUES (:d, 'T2/2026', '2026-02', :pf, :pt, "
                "'RUNNING', 'Y', 3, 0, 0, 0, 0, 'admin', :now, 'admin', :now, 1)"
            ),
            {"d": def_id, "pf": datetime(2026, 2, 1), "pt": datetime(2026, 2, 28, 23, 59, 59), "now": now},
        ).lastrowid
        ids["batch_run_id"] = int(run_id)
        ids["ds_id"] = int(ds_id)
        for seq, priority in [(1, 30), (2, 10), (3, 20)]:
            item_id = conn.execute(
                text(
                    "INSERT INTO RECON_BATCH_RUN_ITEM (BATCH_RUN_ID, BATCH_DEF_ITEM_ID, "
                    "TEMPLATE_ID, TEMPLATE_VERSION, PROFILE_CODE, DATA_SOURCE_ID, SEQ_NO, "
                    "PRIORITY, MULTI_FILE, IS_REQUIRED, STATUS, PARAMS_RUN_OVERRIDE_JSON, "
                    "PARAMS_RESOLVED_JSON, ATTEMPT_NO, CREATED_BY, CREATED_AT, UPDATED_BY, "
                    "UPDATED_AT, ROW_VERSION) VALUES (:br, :seq, 1, 1, 'BY_INVOICE', :ds, :seq, :pri, 'Y', "
                    "'Y', 'QUEUED', '{}', '{}', 1, 'admin', :now, 'admin', :now, 1)"
                ),
                {"br": run_id, "seq": seq, "ds": ds_id, "pri": priority, "now": now},
            ).lastrowid
            child_id = conn.execute(
                text(
                    "INSERT INTO RECON_RUN (TEMPLATE_ID, TEMPLATE_VERSION, PROFILE_CODE, "
                    "FILE_ID, SHEET_NAME, DATA_SOURCE_ID, P_FROM, P_TO, PARAMS_JSON, "
                    "APPLY_RANGE_EXCEL, STATUS, PROGRESS_PCT, BATCH_RUN_ID, "
                    "BATCH_RUN_ITEM_ID, CREATED_BY, CREATED_AT) VALUES (1, 1, 'BY_INVOICE', "
                    "NULL, 'BÁO CÁO DTP', :ds, :pf, :pt, '{}', 'Y', "
                    "'QUEUED', 0, :br, :item, 'admin', :now)"
                ),
                {
                    "ds": ds_id,
                    "pf": datetime(2026, 2, 1),
                    "pt": datetime(2026, 2, 28, 23, 59, 59),
                    "br": run_id,
                    "item": item_id,
                    "now": now,
                },
            ).lastrowid
            enqueued = now - timedelta(minutes=10 - seq)
            conn.execute(
                text(
                    "INSERT INTO RECON_RUN_QUEUE (RUN_ID, STATUS, RETRY_COUNT, ENQUEUED_AT) VALUES (:r, 'READY', 0, :e)"
                ),
                {"r": child_id, "e": enqueued},
            )
            ids[f"run_p{priority}"] = int(child_id)
        if with_standalone:
            standalone_id = conn.execute(
                text(
                    "INSERT INTO RECON_RUN (TEMPLATE_ID, TEMPLATE_VERSION, PROFILE_CODE, "
                    "FILE_ID, SHEET_NAME, DATA_SOURCE_ID, P_FROM, P_TO, PARAMS_JSON, "
                    "APPLY_RANGE_EXCEL, STATUS, PROGRESS_PCT, CREATED_BY, CREATED_AT) "
                    "VALUES (1, 1, 'BY_INVOICE', NULL, 'BÁO CÁO DTP', :ds, :pf, "
                    ":pt, '{}', 'Y', 'QUEUED', 0, 'admin', :now)"
                ),
                {"ds": ds_id, "pf": datetime(2026, 2, 1), "pt": datetime(2026, 2, 28, 23, 59, 59), "now": now},
            ).lastrowid
            conn.execute(
                text(
                    "INSERT INTO RECON_RUN_QUEUE (RUN_ID, STATUS, RETRY_COUNT, ENQUEUED_AT) VALUES (:r, 'READY', 0, :e)"
                ),
                {"r": standalone_id, "e": now - timedelta(minutes=1)},
            )
            ids["standalone"] = int(standalone_id)
    return ids


def _mark_queue_done(engine, run_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE RECON_RUN_QUEUE SET STATUS = 'DONE' WHERE RUN_ID = :r"), {"r": run_id})


class TestClaimBatch:
    def test_claim_priority_order(self, claim_env):
        engine, _path = claim_env
        ids = _seed_jobs(engine, max_parallel=1)
        dialect = DatabaseDialect(engine)
        # Ưu tiên 10 chạy trước dù enqueue sau.
        assert dialect.claim_next_queued_job("w1") == ids["run_p10"]
        # Đã có 1 run PROCESSING cùng DS trong batch (giới hạn 1): run bộ
        # tiếp theo bị bỏ qua, run đơn lẻ vẫn lấy được.
        assert dialect.claim_next_queued_job("w2") == ids["standalone"]
        _mark_queue_done(engine, ids["run_p10"])
        assert dialect.claim_next_queued_job("w3") == ids["run_p20"]
        _mark_queue_done(engine, ids["run_p20"])
        assert dialect.claim_next_queued_job("w4") == ids["run_p30"]

    def test_claim_limit_two_parallel(self, claim_env):
        engine, _path = claim_env
        ids = _seed_jobs(engine, max_parallel=2, with_standalone=False)
        dialect = DatabaseDialect(engine)
        assert dialect.claim_next_queued_job("w1") == ids["run_p10"]
        assert dialect.claim_next_queued_job("w2") == ids["run_p20"]
        # Đã đủ 2 song song cùng DS: run thứ 3 bị chặn.
        assert dialect.claim_next_queued_job("w3") is None
        _mark_queue_done(engine, ids["run_p10"])
        assert dialect.claim_next_queued_job("w4") == ids["run_p30"]

    def test_claim_empty(self, claim_env):
        engine, _path = claim_env
        assert DatabaseDialect(engine).claim_next_queued_job("w1") is None


def _claim_in_child(db_path: str, worker_id: str, out: mp.Queue) -> None:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    try:
        out.put(DatabaseDialect(engine).claim_next_queued_job(worker_id))
    finally:
        engine.dispose()


class TestClaimTwoProcesses:
    def test_two_processes_respect_limit(self, claim_env):
        engine, db_path = claim_env
        ids = _seed_jobs(engine, max_parallel=1, with_standalone=False)
        engine.dispose()
        ctx = mp.get_context("fork")
        out: mp.Queue = ctx.Queue()
        p1 = ctx.Process(target=_claim_in_child, args=(db_path, "w1", out))
        p2 = ctx.Process(target=_claim_in_child, args=(db_path, "w2", out))
        p1.start()
        p2.start()
        p1.join(timeout=30)
        p2.join(timeout=30)
        assert p1.exitcode == 0
        assert p2.exitcode == 0
        results = sorted([out.get(timeout=10), out.get(timeout=10)], key=lambda v: (v is None, v))
        # Giới hạn 1: chỉ một process lấy được job, process còn lại None.
        assert results[0] == ids["run_p10"]
        assert results[1] is None


class TestClaimOracle:
    @pytest.mark.oracle
    def test_claim_oracle(self, oracle_test):
        from sqlalchemy import inspect

        engine = oracle_test
        needed = {
            "RECON_RUN_QUEUE",
            "RECON_RUN",
            "RECON_BATCH_RUN",
            "RECON_BATCH_DEF",
            "RECON_BATCH_RUN_ITEM",
        }
        existing = set(inspect(engine).get_table_names())
        if not needed.issubset(existing):
            pytest.skip("Schema Oracle test chưa có đủ bảng batch; bỏ qua kiểm tra claim trên Oracle.")
        ids = _seed_jobs(engine, max_parallel=1, with_standalone=False)
        dialect = DatabaseDialect(engine)
        assert dialect.claim_next_queued_job("w-oracle") == ids["run_p10"]
        assert dialect.claim_next_queued_job("w-oracle-2") is None
