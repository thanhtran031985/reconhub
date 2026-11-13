from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

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
)
from app.ui.pages.issues import (
    DEFAULT_ISSUE_STATUS_OPTIONS,
    _lookup_status_options,
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

    # Đồng bộ menu + vai trò seed (task 19) trước khi chèn user
    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

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
        seed_perm_basics(engine, {u1: ["OPERATOR"]}, conn=conn)

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


# ─── Task 87: lọc "Chưa giao" / trạng thái từ lookup / lọc theo lần chạy ───


def _find_by_id(comp, target_id):
    """Tìm component theo id trong cây Dash (đệ quy qua .children)."""
    if getattr(comp, "id", None) == target_id:
        return comp
    children = getattr(comp, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            found = _find_by_id(c, target_id)
            if found is not None:
                return found
    elif children is not None:
        return _find_by_id(children, target_id)
    return None


def _collect_texts(comp, out):
    """Gom mọi chuỗi lá trong cây Dash (để assert nội dung bảng đã render)."""
    if isinstance(comp, str):
        out.append(comp)
        return
    children = getattr(comp, "children", None)
    if isinstance(children, (list, tuple)):
        for c in children:
            _collect_texts(c, out)
    elif children is not None:
        _collect_texts(children, out)


def _seed_unassigned_issue_87(engine, tmpl_id, run_id):
    """Thêm 1 issue chưa giao (KEY_TEXT INV_87_UNASSIGNED) vào run đã có."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        return conn.execute(
            recon_issue.insert().values(
                TEMPLATE_ID=tmpl_id,
                PROFILE_CODE="DEFAULT",
                KEY_TEXT="INV_87_UNASSIGNED",
                KEY_HASH="hash_inv_87_unassigned",
                FIRST_RUN_ID=run_id,
                LAST_RUN_ID=run_id,
                STATUS="OPEN",
                REASON_CODE="ROUNDING",
                ASSIGNEE_ID=None,
                NOTE=None,
                UPDATED_AT=now,
                UPDATED_BY="operator_tester",
                ROW_VERSION=1,
            )
        ).inserted_primary_key[0]


def test_render_filter_bar_with_runs87():
    tmpls = [{"id": 1, "code": "TMPL1", "name": "Template 1"}]
    assignees = [{"ID": 10, "USERNAME": "operator", "FULL_NAME": "Operator"}]
    runs = [{"id": 5, "template_code": "TMPL1", "created_at": "2026-11-13T10:30:00"}]
    status_options = [{"value": "ON_HOLD", "label": "Tạm giữ"}]
    bar = render_filter_bar(tmpls, assignees, status_options=status_options, runs=runs)

    run_sel = _find_by_id(bar, "issues-filter-run")
    assert run_sel is not None
    assert {"value": "ALL", "label": "Tất cả lần chạy"} in run_sel.data
    assert {"value": "5", "label": "Run #5 · TMPL1 · 13/11/2026 10:30"} in run_sel.data

    st_sel = _find_by_id(bar, "issues-filter-status")
    assert st_sel is not None
    assert {"value": "ALL", "label": "Tất cả trạng thái"} in st_sel.data
    assert {"value": "ON_HOLD", "label": "Tạm giữ"} in st_sel.data


def test_lookup_status_options87(issues_ui_env):
    engine, operator_ctx, _, admin_ctx, _, _, _ = issues_ui_env
    from app.services.lookup import create_lookup_code, ensure_default_lookup_data

    with engine.begin() as conn:
        ensure_default_lookup_data(conn)
    # Lookup có seed mặc định → 4 mã, nhãn lấy từ lookup.
    opts = _lookup_status_options(operator_ctx)
    assert {o["value"] for o in opts} == {"OPEN", "IN_PROGRESS", "ACCEPTED", "RESOLVED"}

    created = create_lookup_code(
        admin_ctx,
        lookup_type="ISSUE_STATUS",
        lookup_code="ON_HOLD",
        meaning="Tạm giữ",
        display_order=50,
    )
    assert created.ok, created.message
    opts = _lookup_status_options(operator_ctx)
    assert {"value": "ON_HOLD", "label": "Tạm giữ"} in opts

    # Vô hiệu hóa toàn bộ mã → fallback 4 trạng thái mặc định.
    with engine.begin() as conn:
        conn.execute(text("UPDATE RECON_LOOKUP_CODE SET IS_ACTIVE='N' WHERE LOOKUP_TYPE='ISSUE_STATUS'"))
    opts = _lookup_status_options(operator_ctx)
    assert opts == list(DEFAULT_ISSUE_STATUS_OPTIONS)


def test_update_issues_view_run_and_unassigned87(issues_ui_env, monkeypatch):
    _, operator_ctx, _, _, _, run_id, _ = issues_ui_env
    monkeypatch.setattr("app.ui.pages.issues.get_current_ctx", lambda: operator_ctx)
    from app.services.issue import list_issues as real_list_issues

    captured = {}

    def fake_list_issues(ctx, **kwargs):
        captured.update(kwargs)
        return real_list_issues(ctx, **kwargs)

    monkeypatch.setattr("app.ui.pages.issues.list_issues", fake_list_issues)
    update_issues_view(
        tmpl_val="ALL",
        st_val="ALL",
        assignee_val="UNASSIGNED",
        search_val=None,
        run_val=str(run_id),
        _refresh=1,
        _trigger=1,
        selected_ids=[],
    )
    assert captured.get("unassigned_only") is True
    assert captured.get("run_id") == run_id
    assert captured.get("assignee_id") is None


def test_update_issues_view_unassigned_filters_rows87(issues_ui_env, monkeypatch):
    engine, operator_ctx, _, _, tmpl_id, run_id, _ = issues_ui_env
    monkeypatch.setattr("app.ui.pages.issues.get_current_ctx", lambda: operator_ctx)
    _seed_unassigned_issue_87(engine, tmpl_id, run_id)

    _, _, table_ui = update_issues_view(
        tmpl_val="ALL",
        st_val="ALL",
        assignee_val="UNASSIGNED",
        search_val=None,
        run_val="ALL",
        _refresh=1,
        _trigger=1,
        selected_ids=[],
    )
    texts: list[str] = []
    _collect_texts(table_ui, texts)
    assert "INV_87_UNASSIGNED" in texts
    # Issue đã giao của fixture (C26TBD00100) phải bị lọc ra.
    assert "C26TBD00100" not in texts


def test_update_issues_view_run_filters_rows87(issues_ui_env, monkeypatch):
    engine, operator_ctx, _, _, tmpl_id, run_id, _ = issues_ui_env
    monkeypatch.setattr("app.ui.pages.issues.get_current_ctx", lambda: operator_ctx)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        ds_id = conn.execute(text("SELECT DATA_SOURCE_ID FROM RECON_RUN WHERE ID=:r"), {"r": run_id}).scalar()
        run2_id = conn.execute(
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
            recon_issue.insert().values(
                TEMPLATE_ID=tmpl_id,
                PROFILE_CODE="DEFAULT",
                KEY_TEXT="INV_87_RUN2",
                KEY_HASH="hash_inv_87_run2",
                FIRST_RUN_ID=run2_id,
                LAST_RUN_ID=run2_id,
                STATUS="OPEN",
                REASON_CODE="ROUNDING",
                ASSIGNEE_ID=None,
                NOTE=None,
                UPDATED_AT=now,
                UPDATED_BY="operator_tester",
                ROW_VERSION=1,
            )
        )

    _, _, table_ui = update_issues_view(
        tmpl_val="ALL",
        st_val="ALL",
        assignee_val="ALL",
        search_val=None,
        run_val=str(run2_id),
        _refresh=1,
        _trigger=1,
        selected_ids=[],
    )
    texts: list[str] = []
    _collect_texts(table_ui, texts)
    assert "INV_87_RUN2" in texts
    assert "C26TBD00100" not in texts


def test_issues_layout_has_run_filter87(issues_ui_env, monkeypatch):
    _, operator_ctx, _, _, _, run_id, _ = issues_ui_env
    monkeypatch.setattr("app.ui.pages.issues.get_current_ctx", lambda: operator_ctx)
    res = issues_layout()
    run_sel = _find_by_id(res, "issues-filter-run")
    assert run_sel is not None
    assert any(str(o.get("value")) == str(run_id) for o in run_sel.data)
    st_sel = _find_by_id(res, "issues-filter-status")
    assert st_sel is not None
    # Lookup seed mặc định (85f) → nhãn trạng thái lấy từ lookup.
    assert {"value": "OPEN", "label": "Chưa đối soát (Chờ xử lý)"} in st_sel.data
