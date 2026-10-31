from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_issue,
    recon_result_row,
    recon_run,
    recon_template,
    recon_user,
    recon_user_role,
)
from app.ui.pages.issues import (
    handle_bulk_apply,
    open_issue_edit_drawer,
    render_bulk_action_bar,
    render_filter_bar,
    render_header,
    render_kpi_cards,
    save_issue_detail,
    update_issues_view,
)
from app.ui.pages.issues import (
    layout as issues_layout,
)
from app.ui.pages.run_result import (
    handle_run_res_bulk_apply,
    handle_save_issue_from_drawer,
    render_detail_drawer,
    render_result_grid,
    render_run_res_bulk_bar,
)


@pytest.fixture
def issues_ui_env(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "issues_ui_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-issues-test")

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

    with engine.begin() as conn:
        # Users
        u1 = conn.execute(
            recon_user.insert().values(
                ID=10,
                USERNAME="operator_tester",
                FULL_NAME="Operator Tester",
                PASSWORD_HASH=hash_password("op123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]
        conn.execute(recon_user_role.insert().values(USER_ID=u1, ROLE="OPERATOR", CREATED_AT=now))

        # Data source
        ds_id = conn.execute(
            recon_data_source.insert().values(
                NAME="Oracle DS",
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

        # Template
        tmpl_id = conn.execute(
            recon_template.insert().values(
                CODE="DTP_ISSUE_TEST",
                NAME="DTP Hóa Đơn Tác Nghiệp",
                DESCRIPTION="Template test",
                OWNER="admin",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        ).inserted_primary_key[0]

        # Run
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

        # Result row
        conn.execute(
            recon_result_row.insert().values(
                RUN_ID=run_id,
                ROW_NO=1,
                KEY_TEXT="C26TBD00100",
                KEY_HASH="hash_c26_100",
                STATUS="DIFF",
                KEY_JSON={"inv": "C26TBD00100"},
                EXCEL_JSON={"TOTAL_AMOUNT": 2000000},
                DB_JSON={"TOTAL_AMOUNT": 1800000},
                DIFF_JSON={"TOTAL_AMOUNT": 200000},
                ABS_DIFF_MAIN=200000,
                ABS_DIFF_SORT=200000.0,
            )
        )

        from app.services.issue import ensure_default_reasons
        ensure_default_reasons(conn)

        # Issue
        issue_id = conn.execute(
            recon_issue.insert().values(
                TEMPLATE_ID=tmpl_id,
                PROFILE_CODE="DEFAULT",
                KEY_TEXT="C26TBD00100",
                KEY_HASH="hash_c26_100",
                FIRST_RUN_ID=run_id,
                LAST_RUN_ID=run_id,
                STATUS="OPEN",
                REASON_CODE="ROUNDING",
                ASSIGNEE_ID=10,
                NOTE="Cần kiểm tra lại thuế",
                UPDATED_AT=now,
                UPDATED_BY="operator_tester",
                ROW_VERSION=1,
            )
        ).inserted_primary_key[0]

    return engine, operator_ctx, viewer_ctx, admin_ctx, tmpl_id, run_id, issue_id


def test_issues_page_unauthenticated(monkeypatch):
    monkeypatch.setattr("app.ui.pages.issues.get_current_ctx", lambda: None)
    res = issues_layout()
    assert res is not None


def test_issues_page_layout_authenticated(issues_ui_env, monkeypatch):
    _, operator_ctx, _, _, _, _, _ = issues_ui_env
    monkeypatch.setattr("app.ui.pages.issues.get_current_ctx", lambda: operator_ctx)

    res = issues_layout()
    assert res is not None
    # Component tree contains elements
    assert hasattr(res, "children")


def test_render_header_and_kpi_components():
    kpis = {"total": 10, "open": 4, "in_progress": 2, "resolved": 3, "accepted": 1}
    hdr = render_header(kpis)
    assert hdr is not None

    cards = render_kpi_cards(kpis)
    assert cards is not None
    assert len(cards.children) == 5


def test_render_filter_bar():
    tmpls = [{"id": 1, "code": "TMPL1", "name": "Template 1"}]
    assignees = [{"ID": 10, "USERNAME": "operator", "FULL_NAME": "Operator"}]
    bar = render_filter_bar(tmpls, assignees)
    assert bar is not None


def test_update_issues_view_callback(issues_ui_env, monkeypatch):
    _, operator_ctx, _, _, tmpl_id, _, _ = issues_ui_env
    monkeypatch.setattr("app.ui.pages.issues.get_current_ctx", lambda: operator_ctx)

    header_ui, kpi_ui, table_ui = update_issues_view(
        tmpl_val=str(tmpl_id),
        st_val="ALL",
        assignee_val="ALL",
        search_val=None,
        _refresh=1,
        _trigger=1,
        selected_ids=[],
    )

    assert header_ui is not None
    assert kpi_ui is not None
    assert table_ui is not None


def test_open_and_save_issue_drawer_callback(issues_ui_env, monkeypatch):
    _, operator_ctx, _, _, _, _, issue_id = issues_ui_env
    monkeypatch.setattr("app.ui.pages.issues.get_current_ctx", lambda: operator_ctx)
    prop_str = f'{{"index":{issue_id},"type":"issues-row-action"}}.n_clicks'
    mock_ctx = type(
        "MockCtx",
        (),
        {"triggered": [{"prop_id": prop_str}]},
    )()
    monkeypatch.setattr("dash.callback_context", mock_ctx)

    opened, hdr, st, r_code, ass_id, note_val, iss_id, feedback = open_issue_edit_drawer([1])
    assert opened is True
    assert iss_id == issue_id
    assert st == "OPEN"
    assert r_code == "ROUNDING"

    # Test lưu issue
    res_feedback, new_trigger = save_issue_detail(
        n_clicks=1,
        issue_id=issue_id,
        status_val="RESOLVED",
        reason_code="ROUNDING",
        assignee_val="10",
        note_val="Đã giải trình xong",
    )
    assert res_feedback is not None
    assert new_trigger > 0


def test_bulk_action_callbacks(issues_ui_env, monkeypatch):
    _, operator_ctx, _, _, _, _, issue_id = issues_ui_env
    monkeypatch.setattr("app.ui.pages.issues.get_current_ctx", lambda: operator_ctx)

    # Render bulk bar
    bulk_ui = render_bulk_action_bar([issue_id])
    assert bulk_ui is not None

    # Handle bulk apply
    trigger, new_selected = handle_bulk_apply(
        n_clicks=1,
        selected_ids=[issue_id],
        reason_code="TIMING",
        assignee_val="10",
        status_val="ACCEPTED",
    )
    assert trigger > 0
    assert new_selected == []


def test_run_result_issue_handling_ui(issues_ui_env, monkeypatch):
    _, operator_ctx, _, _, _, run_id, _ = issues_ui_env
    monkeypatch.setattr("app.ui.pages.run_result.get_current_ctx", lambda: operator_ctx)

    measures = [{"name": "TOTAL_AMOUNT", "label": "Tổng tiền", "type": "number"}]
    rows = [
        {
            "row_no": 1,
            "key": "C26TBD00100",
            "status": "DIFF",
            "excel": {"TOTAL_AMOUNT": 2000000},
            "db": {"TOTAL_AMOUNT": 1800000},
            "diff": {"TOTAL_AMOUNT": 200000},
            "issue_status": "OPEN",
        }
    ]

    grid_ui = render_result_grid(measures, rows, can_edit=True, selected_row_nos=[1])
    assert grid_ui is not None

    # Drawer chi tiết kèm khối Xử lý chênh lệch
    drawer_ui = render_detail_drawer(
        row_key="C26TBD00100",
        status="DIFF",
        raw_excel_rows=[{"row_no": 1, "amount": 2000000}],
        db_records=[{"inv_no": "C26TBD00100", "amount": 1800000}],
        run_id=run_id,
        row_no=1,
        issue_info={"STATUS": "OPEN", "REASON_CODE": "ROUNDING", "NOTE": "Test"},
        reasons=[{"CODE": "ROUNDING", "LABEL": "Lệch làm tròn"}],
        assignees=[{"ID": 10, "USERNAME": "operator_tester", "FULL_NAME": "Operator"}],
        can_edit=True,
    )
    assert drawer_ui is not None

    # Lưu xử lý từ Drawer kết quả run
    save_res, trig = handle_save_issue_from_drawer(
        n_clicks=1,
        meta={"run_id": run_id, "row_no": 1},
        status_val="ACCEPTED",
        reason_code="ROUNDING",
        assignee_val="10",
        note_val="Chấp nhận lệch",
    )
    assert save_res is not None
    assert trig > 0

    # Bulk action trên kết quả run
    bulk_bar = render_run_res_bulk_bar([1])
    assert bulk_bar is not None

    bulk_trig, bulk_cleared = handle_run_res_bulk_apply(
        n_clicks=1,
        data_store={"run": {"id": run_id}},
        selected_row_nos=[1],
        reason_code="POLICY_EXCEPTION",
        assignee_val="10",
        status_val="RESOLVED",
    )
    assert bulk_trig > 0
    assert bulk_cleared == []
