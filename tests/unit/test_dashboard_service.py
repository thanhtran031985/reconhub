from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_result_row,
    recon_run,
    recon_run_summary,
    recon_template,
    recon_user,
)
from app.schemas.errors import ErrorCode
from app.services.dashboard import compare_runs, get_dashboard_summary, get_previous_run


@pytest.fixture
def dashboard_env(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "dashboard_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-dashboard-test")

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    operator_ctx = Ctx(
        user_id=10,
        username="operator_tester",
        roles=[Role.OPERATOR],
        full_name="Operator Tester",
    )
    viewer_ctx = Ctx(
        user_id=20,
        username="viewer_tester",
        roles=[Role.VIEWER],
        full_name="Viewer Tester",
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_of_month = datetime(now.year, now.month, 1, 0, 0, 0)

    from datetime import timedelta

    t1 = start_of_month + timedelta(minutes=5)
    t2 = start_of_month + timedelta(minutes=10)

    with engine.begin() as conn:
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="DS Test",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                USERNAME="test",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=t1,
                UPDATED_AT=t1,
            )
        ).inserted_primary_key[0]

        tmpl_id = conn.execute(
            recon_template.insert().values(
                CODE="DTP_DASHBOARD_TEST",
                NAME="DTP Hóa Đơn Dashboard",
                DESCRIPTION="Test",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=t1,
                UPDATED_AT=t1,
            )
        ).inserted_primary_key[0]

        conn.execute(
            recon_user.insert().values(
                ID=10,
                USERNAME="operator_tester",
                FULL_NAME="Operator Tester",
                PASSWORD_HASH="hash",
                IS_ACTIVE="Y",
                CREATED_BY="admin",
                CREATED_AT=t1,
                UPDATED_AT=t1,
            )
        )

        # Run 1 (cũ hơn, trạng thái DONE)
        run_1_id = conn.execute(
            recon_run.insert().values(
                TEMPLATE_ID=tmpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="DEFAULT",
                DATA_SOURCE_ID=ds_id,
                STATUS="DONE",
                P_FROM=t1,
                P_TO=t1,
                CREATED_BY="operator_tester",
                CREATED_AT=t1,
            )
        ).inserted_primary_key[0]

        conn.execute(
            recon_run_summary.insert().values(
                RUN_ID=run_1_id,
                CNT_MATCHED=180,
                CNT_MISMATCH=10,
                CNT_MISSING_IN_DB=5,
                CNT_MISSING_IN_EXCEL=5,
            )
        )

        # Run 2 (mới hơn, trạng thái DONE)
        run_2_id = conn.execute(
            recon_run.insert().values(
                TEMPLATE_ID=tmpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="DEFAULT",
                DATA_SOURCE_ID=ds_id,
                STATUS="DONE",
                P_FROM=t2,
                P_TO=t2,
                CREATED_BY="operator_tester",
                CREATED_AT=t2,
            )
        ).inserted_primary_key[0]

        conn.execute(
            recon_run_summary.insert().values(
                RUN_ID=run_2_id,
                CNT_MATCHED=190,
                CNT_MISMATCH=5,
                CNT_MISSING_IN_DB=3,
                CNT_MISSING_IN_EXCEL=2,
            )
        )

    return engine, operator_ctx, viewer_ctx, tmpl_id, run_1_id, run_2_id


def test_get_dashboard_summary(dashboard_env):
    _, operator_ctx, viewer_ctx, tmpl_id, _, _ = dashboard_env

    # 1. Gọi summary với Viewer
    res = get_dashboard_summary(viewer_ctx)
    assert res.ok is True
    data = res.data
    assert data["total_runs"] >= 2
    assert data["done_count"] >= 2
    assert data["unchecked_count"] >= 2
    assert data["avg_match_pct"] is not None
    assert data["avg_match_pct"] > 80.0

    # 2. Thống kê theo template
    diff_tmpls = data["diff_rate_by_template"]
    assert len(diff_tmpls) >= 1
    t0 = diff_tmpls[0]
    assert t0["template_id"] == tmpl_id
    assert t0["run_count"] >= 2
    assert t0["total_compared"] > 0
    assert "diff_pct" in t0

    # 3. Danh sách run gần đây
    recent = data["recent_runs"]
    assert len(recent) >= 2
    assert recent[0]["id"] is not None


def test_compare_runs_three_groups(dashboard_env):
    """Test nghiệp vụ cốt lõi so sánh 2 run phân loại chuẩn 3 nhóm."""
    engine, operator_ctx, _, _, run_1_id, run_2_id = dashboard_env

    # Nạp dữ liệu dòng kết quả cho Run 1:
    # KEY_1: DIFF
    # KEY_2: DIFF
    # KEY_3: MATCHED
    with engine.begin() as conn:
        conn.execute(
            recon_result_row.insert(),
            [
                {
                    "RUN_ID": run_1_id,
                    "ROW_NO": 1,
                    "KEY_TEXT": "INV_001",
                    "KEY_JSON": "{}",
                    "KEY_HASH": "hash_001",
                    "STATUS": "DIFF",
                    "ABS_DIFF_MAIN": 100,
                },
                {
                    "RUN_ID": run_1_id,
                    "ROW_NO": 2,
                    "KEY_TEXT": "INV_002",
                    "KEY_JSON": "{}",
                    "KEY_HASH": "hash_002",
                    "STATUS": "DIFF",
                    "ABS_DIFF_MAIN": 50,
                },
                {
                    "RUN_ID": run_1_id,
                    "ROW_NO": 3,
                    "KEY_TEXT": "INV_003",
                    "KEY_JSON": "{}",
                    "KEY_HASH": "hash_003",
                    "STATUS": "MATCHED",
                    "ABS_DIFF_MAIN": 0,
                },
            ],
        )

        # Nạp dữ liệu dòng kết quả cho Run 2:
        # KEY_2: MATCHED (in both, status changed!)
        # KEY_3: MATCHED (in both, same status)
        # KEY_4: MISSING_DB (only in Run 2!)
        conn.execute(
            recon_result_row.insert(),
            [
                {
                    "RUN_ID": run_2_id,
                    "ROW_NO": 1,
                    "KEY_TEXT": "INV_002",
                    "KEY_JSON": "{}",
                    "KEY_HASH": "hash_002",
                    "STATUS": "MATCHED",
                    "ABS_DIFF_MAIN": 0,
                },
                {
                    "RUN_ID": run_2_id,
                    "ROW_NO": 2,
                    "KEY_TEXT": "INV_003",
                    "KEY_JSON": "{}",
                    "KEY_HASH": "hash_003",
                    "STATUS": "MATCHED",
                    "ABS_DIFF_MAIN": 0,
                },
                {
                    "RUN_ID": run_2_id,
                    "ROW_NO": 3,
                    "KEY_TEXT": "INV_004",
                    "KEY_JSON": "{}",
                    "KEY_HASH": "hash_004",
                    "STATUS": "MISSING_DB",
                    "ABS_DIFF_MAIN": 200,
                },
            ],
        )

    # Thực hiện so sánh Run 1 và Run 2
    res = compare_runs(operator_ctx, run_id_a=run_1_id, run_id_b=run_2_id)
    assert res.ok is True
    data = res.data

    summary = data["summary"]
    # 3 nhóm chính:
    # 1. ONLY_IN_A: KEY_1 (có ở Run 1, không có ở Run 2)
    assert summary["count_only_a"] == 1
    # 2. ONLY_IN_B: KEY_4 (có ở Run 2, không có ở Run 1)
    assert summary["count_only_b"] == 1
    # 3. IN_BOTH: KEY_2 và KEY_3 (có ở cả 2 run)
    assert summary["count_both"] == 2
    # Trong nhóm IN_BOTH:
    # KEY_2 đổi từ DIFF -> MATCHED: 1 đổi trạng thái
    assert summary["count_status_changed"] == 1
    # KEY_3 giữ nguyên MATCHED: 1 giữ nguyên trạng thái
    assert summary["count_same_status"] == 1
    # Tổng số khóa phân biệt: 4
    assert summary["total_keys"] == 4

    # Kiểm tra chi tiết items
    items_by_key = {it["key_text"]: it for it in data["items"]}
    assert items_by_key["INV_001"]["category"] == "ONLY_IN_A"
    assert items_by_key["INV_004"]["category"] == "ONLY_IN_B"
    assert items_by_key["INV_002"]["category"] == "IN_BOTH"
    assert items_by_key["INV_002"]["status_changed"] is True
    assert items_by_key["INV_003"]["category"] == "IN_BOTH"
    assert items_by_key["INV_003"]["status_changed"] is False


def test_compare_runs_validation(dashboard_env):
    _, operator_ctx, _, _, run_1_id, _ = dashboard_env

    # 1. Run không tồn tại
    r_not_found = compare_runs(operator_ctx, run_id_a=run_1_id, run_id_b=99999)
    assert r_not_found.ok is False
    assert r_not_found.code == ErrorCode.NOT_FOUND


def test_get_previous_run(dashboard_env):
    _, operator_ctx, _, _, run_1_id, run_2_id = dashboard_env

    # Run 2 có run trước là Run 1
    prev = get_previous_run(operator_ctx, run_id=run_2_id)
    assert prev.ok is True
    assert prev.data is not None
    assert prev.data["id"] == run_1_id

    # Run 1 là run đầu tiên, không có run trước
    prev_none = get_previous_run(operator_ctx, run_id=run_1_id)
    assert prev_none.ok is True
    assert prev_none.data is None
