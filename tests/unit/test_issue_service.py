from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_audit_log,
    recon_data_source,
    recon_issue,
    recon_result_row,
    recon_run,
    recon_template,
    recon_user,
)
from app.schemas.errors import ErrorCode
from app.services.issue import (
    bulk_upsert_issues,
    get_issue,
    get_issue_for_row,
    list_issues,
    list_reasons,
    upsert_issue_for_row,
)


@pytest.fixture
def issue_env(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "issue_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")

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
    admin_ctx = Ctx(
        user_id=1,
        username="admin_tester",
        roles=[Role.ADMIN],
        full_name="Admin Tester",
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Seed data: template, data source, run, user
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
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        tmpl_id = conn.execute(
            recon_template.insert().values(
                CODE="TMPL_ISSUE_TEST",
                NAME="Template Issue Test",
                DESCRIPTION="Test",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        run_id = conn.execute(
            recon_run.insert().values(
                TEMPLATE_ID=tmpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="DEFAULT",
                DATA_SOURCE_ID=ds_id,
                STATUS="DONE",
                P_FROM=now,
                P_TO=now,
                CREATED_BY="operator_tester",
                CREATED_AT=now,
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
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

        # Chèn 1 dòng kết quả lệch
        conn.execute(
            recon_result_row.insert().values(
                RUN_ID=run_id,
                ROW_NO=1,
                KEY_TEXT="INV_99999",
                KEY_HASH="hash_inv_99999",
                STATUS="DIFF",
                KEY_JSON={"invoice_no": "INV_99999"},
                EXCEL_JSON={"amount": 1000},
                DB_JSON={"amount": 950},
                DIFF_JSON={"amount": 50},
                ABS_DIFF_MAIN=50,
                ABS_DIFF_SORT=50.0,
            )
        )

    return engine, operator_ctx, viewer_ctx, admin_ctx, tmpl_id, run_id


def test_list_reasons(issue_env):
    _, _, viewer_ctx, _, _, _ = issue_env

    res = list_reasons(viewer_ctx)
    assert res.ok is True
    reasons = res.data
    assert len(reasons) >= 6
    codes = {r["CODE"] for r in reasons}
    assert "ROUNDING" in codes
    assert "TIMING" in codes
    assert "SYSTEM_BUG" in codes
    assert "POLICY_EXCEPTION" in codes


def test_permissions_viewer_cannot_update(issue_env):
    _, _, viewer_ctx, _, _, run_id = issue_env

    # Viewer không được phép cập nhật issue
    r1 = upsert_issue_for_row(
        viewer_ctx,
        run_id=run_id,
        row_no=1,
        reason_code="ROUNDING",
        status="IN_PROGRESS",
    )
    assert r1.ok is False
    assert r1.code == ErrorCode.FORBIDDEN

    r2 = bulk_upsert_issues(
        viewer_ctx,
        run_id=run_id,
        row_nos=[1],
        reason_code="ROUNDING",
        status="RESOLVED",
    )
    assert r2.ok is False
    assert r2.code == ErrorCode.FORBIDDEN


def test_upsert_issue_for_row(issue_env):
    engine, operator_ctx, _, _, tmpl_id, run_id = issue_env

    # 1. Tạo issue mới cho dòng kết quả số 1
    res = upsert_issue_for_row(
        operator_ctx,
        run_id=run_id,
        row_no=1,
        reason_code="ROUNDING",
        assignee_id=10,
        status="IN_PROGRESS",
        note="Đang kiểm tra lệch làm tròn tiền thuế",
    )
    assert res.ok is True
    issue_id = res.data["issue_id"]
    assert res.data["action"] == "CREATE_ISSUE"
    assert res.data["status"] == "IN_PROGRESS"

    # 2. Đọc lại thông tin issue
    iss = get_issue(operator_ctx, issue_id=issue_id)
    assert iss.ok is True
    assert iss.data["STATUS"] == "IN_PROGRESS"
    assert iss.data["REASON_CODE"] == "ROUNDING"
    assert iss.data["REASON_LABEL"] == "Lệch làm tròn số thập phân"
    assert iss.data["ASSIGNEE_USERNAME"] == "operator_tester"
    assert iss.data["KEY_TEXT"] == "INV_99999"

    # 3. Lấy issue theo dòng của run
    row_iss = get_issue_for_row(operator_ctx, run_id=run_id, row_no=1)
    assert row_iss.ok is True
    assert row_iss.data is not None
    assert row_iss.data["ID"] == issue_id

    # 4. Cập nhật issue sang ACCEPTED (chấp nhận lệch)
    res_upd = upsert_issue_for_row(
        operator_ctx,
        run_id=run_id,
        row_no=1,
        reason_code="POLICY_EXCEPTION",
        assignee_id=10,
        status="ACCEPTED",
        note="Chấp nhận lệch theo công văn phê duyệt",
    )
    assert res_upd.ok is True
    assert res_upd.data["action"] == "UPDATE_ISSUE"
    assert res_upd.data["status"] == "ACCEPTED"

    # Kiểm tra audit log
    with engine.connect() as conn:
        audits = conn.execute(
            select(recon_audit_log).where(
                recon_audit_log.c.ENTITY == "ISSUE",
                recon_audit_log.c.ENTITY_ID == str(issue_id),
            )
        ).mappings().all()
        assert len(audits) >= 2


def test_bulk_upsert_issues_performance(issue_env):
    """Kiểm tra xử lý hàng loạt 100 dòng thỏa tiêu chí nghiệm thu < 2 giây."""
    engine, operator_ctx, _, _, tmpl_id, run_id = issue_env

    # Tạo 100 dòng kết quả
    rows = []
    for i in range(10, 110):
        rows.append(
            {
                "RUN_ID": run_id,
                "ROW_NO": i,
                "KEY_TEXT": f"INV_BULK_{i}",
                "KEY_HASH": f"hash_bulk_{i}",
                "STATUS": "DIFF",
                "KEY_JSON": {"inv": f"INV_BULK_{i}"},
                "EXCEL_JSON": {"val": 100},
                "DB_JSON": {"val": 90},
                "DIFF_JSON": {"val": 10},
            }
        )

    with engine.begin() as conn:
        conn.execute(recon_result_row.insert(), rows)

    row_nos = list(range(10, 110))
    assert len(row_nos) == 100

    # Đo thời gian xử lý hàng loạt
    start_time = time.perf_counter()
    bulk_res = bulk_upsert_issues(
        operator_ctx,
        run_id=run_id,
        row_nos=row_nos,
        reason_code="TIMING",
        assignee_id=10,
        status="RESOLVED",
        note="Đã đối chiếu bù vào kỳ sau",
    )
    duration_s = time.perf_counter() - start_time

    assert bulk_res.ok is True
    assert bulk_res.data["count"] == 100
    # Tiêu chí chấp nhận: < 2 giây
    assert duration_s < 2.0, f"Xử lý hàng loạt 100 dòng mất {duration_s:.3f}s (vượt quá 2 giây)!"

    # Kiểm tra trong DB có đủ 100 issue
    with engine.connect() as conn:
        cnt = conn.execute(
            select(recon_issue).where(
                recon_issue.c.TEMPLATE_ID == tmpl_id,
                recon_issue.c.REASON_CODE == "TIMING",
            )
        ).fetchall()
        assert len(cnt) == 100


def test_list_issues_filters_and_kpis(issue_env):
    engine, operator_ctx, viewer_ctx, _, tmpl_id, run_id = issue_env

    # Tạo thêm 2 issue với các trạng thái khác nhau
    upsert_issue_for_row(
        operator_ctx,
        run_id=run_id,
        row_no=1,
        reason_code="ROUNDING",
        status="OPEN",
        note="Lệch tiền lẻ",
    )

    # Chèn dòng thứ 2
    with engine.begin() as conn:
        conn.execute(
            recon_result_row.insert().values(
                RUN_ID=run_id,
                ROW_NO=2,
                KEY_TEXT="INV_CUSTOMER_X",
                KEY_HASH="hash_customer_x",
                STATUS="MISSING_DB",
                KEY_JSON={"inv": "INV_CUSTOMER_X"},
            )
        )

    upsert_issue_for_row(
        operator_ctx,
        run_id=run_id,
        row_no=2,
        reason_code="SYSTEM_BUG",
        status="RESOLVED",
        note="Lỗi đồng bộ API",
    )

    # 1. List tất cả
    lst = list_issues(viewer_ctx, template_id=tmpl_id)
    assert lst.ok is True
    assert lst.data["total"] >= 2
    assert lst.data["kpis"]["open"] >= 1
    assert lst.data["kpis"]["resolved"] >= 1

    # 2. Lọc theo trạng thái
    lst_open = list_issues(viewer_ctx, status="OPEN")
    assert lst_open.ok is True
    assert all(it["STATUS"] == "OPEN" for it in lst_open.data["items"])

    # 3. Tìm kiếm theo từ khóa
    lst_search = list_issues(viewer_ctx, search="CUSTOMER_X")
    assert lst_search.ok is True
    assert len(lst_search.data["items"]) == 1
    assert lst_search.data["items"][0]["KEY_TEXT"] == "INV_CUSTOMER_X"
