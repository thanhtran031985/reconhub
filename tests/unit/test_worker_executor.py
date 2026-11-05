from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from app.core.context import Ctx, Role
from app.db.dialect import get_dialect
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_file,
    recon_issue,
    recon_result_row,
    recon_run,
    recon_run_queue,
    recon_run_summary,
    recon_template,
    recon_template_version,
)
from app.schemas.run import CreateRunParams
from app.services.run_executor import _update_issues_last_run, execute_run
from app.services.run_service import create_run
from worker.runner import ReconWorker

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")


def get_sample_config() -> dict:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "recon_test_worker.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(
        db_url,
        connect_args={"timeout": 30},
    )
    # Kích hoạt WAL mode
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA busy_timeout=30000")

    metadata.create_all(engine)
    return engine


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])


@pytest.fixture
def seed_data(test_db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with test_db.begin() as conn:
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="ORACLE_DEV",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="orcl",
                USERNAME="RECON_SRC_RO",
                PASSWORD_ENC="dummy",
                DEFAULT_SCHEMA="RECON_SRC",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        f_id = conn.execute(
            recon_file.insert().values(
                SHA256="dummy_sha256",
                ORIGINAL_NAME="dtp_sample_200.xlsx",
                SIZE_BYTES=1024,
                STORAGE_PATH="samples/dtp_sample_200.xlsx",
                SHEETS_JSON=["BÁO CÁO DTP"],
                UPLOADED_BY="admin",
                UPLOADED_AT=now,
            )
        ).inserted_primary_key[0]

        tmpl_id = conn.execute(
            recon_template.insert().values(
                CODE="DTP_HOA_DON",
                NAME="DTP Hóa đơn",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        cfg = get_sample_config()
        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=tmpl_id,
                VERSION=1,
                STATUS="ACTIVE",
                CONFIG_JSON=cfg,
                DATA_SOURCE_ID=ds_id,
                DRY_RUN_OK="Y",
                CREATED_BY="admin",
                CREATED_AT=now,
                ACTIVATED_AT=now,
            )
        )

    return {
        "ds_id": ds_id,
        "file_id": f_id,
        "template_id": tmpl_id,
    }


def test_claim_next_queued_job_concurrency(test_db, seed_data, admin_ctx):
    """Kiểm tra 2 worker claim job đồng thời không bao giờ lấy trùng nhau."""
    dialect = get_dialect(test_db)

    # Tạo 5 jobs trong hàng đợi
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with test_db.begin() as conn:
        for _ in range(1, 6):
            r_id = conn.execute(
                recon_run.insert().values(
                    TEMPLATE_ID=seed_data["template_id"],
                    TEMPLATE_VERSION=1,
                    PROFILE_CODE="BY_INVOICE",
                    FILE_ID=seed_data["file_id"],
                    DATA_SOURCE_ID=seed_data["ds_id"],
                    P_FROM=datetime(2026, 1, 1),
                    P_TO=datetime(2026, 1, 10),
                    STATUS="QUEUED",
                    CREATED_BY="admin",
                    CREATED_AT=now,
                )
            ).inserted_primary_key[0]
            conn.execute(
                recon_run_queue.insert().values(
                    RUN_ID=r_id,
                    STATUS="READY",
                    ENQUEUED_AT=now,
                )
            )

    claimed_jobs: list[int] = []

    def claim_job(worker_name: str) -> None:
        for _ in range(3):
            job = dialect.claim_next_queued_job(locked_by=worker_name)
            if job is not None:
                claimed_jobs.append(job)

    with ThreadPoolExecutor(max_workers=4) as executor:
        f1 = executor.submit(claim_job, "worker-1")
        f2 = executor.submit(claim_job, "worker-2")
        f1.result()
        f2.result()

    # Xác minh không có job nào bị claim trùng
    assert len(claimed_jobs) == len(set(claimed_jobs))
    assert len(claimed_jobs) == 5


def test_execute_run_success(test_db, seed_data, admin_ctx):
    """Kiểm tra execute_run chạy trọn vẹn và lưu đầy đủ kết quả."""
    # Tạo run
    res = create_run(
        admin_ctx,
        CreateRunParams(
            template_id=seed_data["template_id"],
            file_id=seed_data["file_id"],
            profile_code="BY_INVOICE",
            p_from=datetime(2026, 2, 1, 0, 0, 0),
            p_to=datetime(2026, 2, 5, 23, 59, 59),
        ),
    )
    assert res.ok
    run_id = res.data["run_id"]

    # Đọc mock fetcher từ parquet golden
    import polars as pl

    golden_db_path = Path("tests/golden/G01_dtp_by_invoice/db.parquet")
    db_df = pl.read_parquet(golden_db_path)

    def mock_fetcher(config, profile, p_from, p_to, max_rows, timeout):
        return db_df

    # Thực thi run
    exec_res = execute_run(run_id, mock_fetcher=mock_fetcher)
    assert exec_res["status"] == "DONE"

    # Kiểm tra RECON_RUN trạng thái DONE
    with test_db.connect() as conn:
        r = conn.execute(select(recon_run).where(recon_run.c.ID == run_id)).mappings().first()
        assert r is not None
        assert r["STATUS"] == "DONE"
        assert r["PROGRESS_PCT"] == 100
        assert r["FINISHED_AT"] is not None

        # Kiểm tra RECON_RUN_SUMMARY
        summ = conn.execute(select(recon_run_summary).where(recon_run_summary.c.RUN_ID == run_id)).mappings().first()
        assert summ is not None
        assert summ["CNT_MATCHED"] == 184
        assert summ["CNT_MISMATCH"] == 4
        assert summ["CNT_MISSING_IN_DB"] == 2
        assert summ["CNT_MISSING_IN_EXCEL"] == 2

        # Kiểm tra RECON_RESULT_ROW có đủ dòng
        total_rows = conn.execute(select(recon_result_row).where(recon_result_row.c.RUN_ID == run_id)).all()
        assert len(total_rows) == 192  # 184 + 4 + 2 + 2


def test_execute_run_failure_cleans_up(test_db, seed_data, admin_ctx):
    """Khi có lỗi ngoại lệ trong lúc chạy, chuyển trạng thái FAILED và không để lại kết quả dở dang."""
    res = create_run(
        admin_ctx,
        CreateRunParams(
            template_id=seed_data["template_id"],
            file_id=seed_data["file_id"],
            profile_code="BY_INVOICE",
            p_from=datetime(2026, 2, 1, 0, 0, 0),
            p_to=datetime(2026, 2, 5, 23, 59, 59),
        ),
    )
    run_id = res.data["run_id"]

    def failing_fetcher(config, profile, p_from, p_to, max_rows, timeout):
        raise RuntimeError("Lỗi mô phỏng mất kết nối DB nguồn!")

    exec_res = execute_run(run_id, mock_fetcher=failing_fetcher)
    assert exec_res["status"] == "FAILED"

    with test_db.connect() as conn:
        r = conn.execute(select(recon_run).where(recon_run.c.ID == run_id)).mappings().first()
        assert r is not None
        assert r["STATUS"] == "FAILED"
        assert r["ERROR_MSG"] is not None
        assert "Lỗi mô phỏng mất kết nối" in r["ERROR_MSG"]

        # Không có bản ghi dở trong RECON_RESULT_ROW
        res_rows = conn.execute(select(recon_result_row).where(recon_result_row.c.RUN_ID == run_id)).all()
        assert len(res_rows) == 0


def test_update_issues_last_run_chunks_over_sqlite_variable_limit(test_db, seed_data):
    """Danh sách key_hash lớn không được đưa vào một mệnh đề IN duy nhất.

    Tái hiện môi trường của người dùng: giới hạn biến SQLite hạ xuống 999
    (mức thường gặp trên Windows). Với 1200 issue, câu UPDATE một lần duy
    nhất sẽ lỗi "too many SQL variables"; helper chia lô 500 phải cập nhật
    đủ 1200 issue và không chạm vào issue của profile khác.
    """
    import sqlite3

    from sqlalchemy import event, update

    template_id = seed_data["template_id"]
    hashes = [f"hash-{i:05d}" for i in range(1200)]
    with test_db.begin() as conn:
        conn.execute(
            recon_issue.insert(),
            [
                {
                    "TEMPLATE_ID": template_id,
                    "PROFILE_CODE": "BY_INVOICE",
                    "KEY_TEXT": f"key-{h}",
                    "KEY_HASH": h,
                    "FIRST_RUN_ID": 1,
                    "LAST_RUN_ID": 0,
                    "STATUS": "OPEN",
                }
                for h in hashes
            ],
        )
        conn.execute(
            recon_issue.insert().values(
                TEMPLATE_ID=template_id,
                PROFILE_CODE="OTHER_PROFILE",
                KEY_TEXT="key-other",
                KEY_HASH=hashes[0],
                FIRST_RUN_ID=1,
                LAST_RUN_ID=0,
                STATUS="OPEN",
            )
        )

    # Hạ giới hạn biến của mọi kết nối mới xuống 999 rồi mở lại pool.
    def _limit_999(dbapi_conn, _record):
        dbapi_conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 999)

    event.listen(test_db, "connect", _limit_999)
    test_db.dispose()

    # Đối chứng: một câu IN với 1200 biến phải lỗi ở giới hạn 999.
    with test_db.connect() as conn:
        with pytest.raises(Exception, match="too many SQL variables"):
            conn.execute(update(recon_issue).where(recon_issue.c.KEY_HASH.in_(hashes)).values(LAST_RUN_ID=9999))

    # Sửa: truyền cả danh sách kèm trùng lặp, helper tự dedupe và chia lô.
    with test_db.begin() as conn:
        _update_issues_last_run(conn, template_id, "BY_INVOICE", hashes + hashes[:10], 1011)

    with test_db.connect() as conn:
        updated = conn.execute(
            select(recon_issue.c.KEY_HASH).where(
                recon_issue.c.TEMPLATE_ID == template_id,
                recon_issue.c.PROFILE_CODE == "BY_INVOICE",
                recon_issue.c.LAST_RUN_ID == 1011,
            )
        ).all()
        assert len(updated) == 1200
        other = conn.execute(
            select(recon_issue.c.LAST_RUN_ID).where(
                recon_issue.c.TEMPLATE_ID == template_id,
                recon_issue.c.PROFILE_CODE == "OTHER_PROFILE",
            )
        ).scalar_one()
        assert other == 0


def test_worker_reset_stale_jobs(test_db, seed_data):
    """Worker có khả năng nhận diện và reset các job bị treo do worker khác chết đột ngột."""
    worker = ReconWorker()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Giả lập 1 job đang PROCESSING nhưng HEARTBEAT_AT cách đây 10 phút
    old_time = now - timedelta(minutes=10)
    with test_db.begin() as conn:
        r_id = conn.execute(
            recon_run.insert().values(
                TEMPLATE_ID=seed_data["template_id"],
                TEMPLATE_VERSION=1,
                PROFILE_CODE="BY_INVOICE",
                FILE_ID=seed_data["file_id"],
                DATA_SOURCE_ID=seed_data["ds_id"],
                P_FROM=datetime(2026, 1, 1),
                P_TO=datetime(2026, 1, 10),
                STATUS="RUNNING",
                CREATED_BY="admin",
                CREATED_AT=old_time,
            )
        ).inserted_primary_key[0]
        conn.execute(
            recon_run_queue.insert().values(
                RUN_ID=r_id,
                STATUS="PROCESSING",
                LOCKED_BY="crashed-worker",
                LOCKED_AT=old_time,
                HEARTBEAT_AT=old_time,
                ENQUEUED_AT=old_time,
            )
        )

    # Chạy hàm reset_stale_jobs
    reset_count = worker.reset_stale_jobs(timeout_seconds=300)
    assert reset_count == 1

    with test_db.connect() as conn:
        q = conn.execute(select(recon_run_queue).where(recon_run_queue.c.RUN_ID == r_id)).mappings().first()
        assert q is not None
        assert q["STATUS"] == "ERROR"

        r = conn.execute(select(recon_run).where(recon_run.c.ID == r_id)).mappings().first()
        assert r is not None
        assert r["STATUS"] == "FAILED"
        assert "bị ngắt đột ngột" in str(r["ERROR_MSG"])
