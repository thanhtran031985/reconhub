"""Tests cho trang Model Center (/report-models) — Bước 1 task 107 (test viết trước)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx, Role
from app.db.metadata import metadata, recon_data_source
from tests.conftest import seed_perm_basics


def _admin() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])


def _owner() -> Ctx:
    return Ctx(user_id=2, username="owner", full_name="Owner", roles=[Role.TEMPLATE_OWNER])


def _viewer() -> Ctx:
    return Ctx(user_id=3, username="viewer", full_name="Viewer", roles=[Role.VIEWER])


def _dump(component: Any) -> str:
    def conv(obj: Any) -> Any:
        if hasattr(obj, "to_plotly_json"):
            return obj.to_plotly_json()
        if isinstance(obj, (list, tuple)):
            return [conv(o) for o in obj]
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        return obj

    return json.dumps(conv(component), ensure_ascii=False, default=str)


@pytest.fixture()
def rm_center_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "rm_center.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", echo=False)
    metadata.create_all(engine)
    for mod in (
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.data_source",
        "app.services.semantic_model",
        "app.services.semantic_model_validate",
    ):
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)

    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from app.services.semantic_model import create_model

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, uname in [(1, "admin"), (2, "owner"), (3, "viewer")]:
            conn.execute(
                text(
                    "INSERT INTO RECON_USER (ID, USERNAME, FULL_NAME, PASSWORD_HASH, "
                    "IS_ACTIVE, MUST_CHANGE_PW, FAILED_COUNT, SESSION_VERSION, "
                    "CREATED_BY, CREATED_AT, UPDATED_AT, ROW_VERSION) "
                    "VALUES (:id, :u, :u, 'hash', 'Y', 'N', 0, 1, 'SEED', :now, :now, 1)"
                ),
                {"id": uid, "u": uname, "now": now},
            )
        ds_res = conn.execute(
            recon_data_source.insert().values(
                NAME="ORACLE_FIN_DEV",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="SQLITE",
                FILE_PATH=str(db_path),
                DEFAULT_SCHEMA="main",
                CALL_TIMEOUT_S=60,
                MAX_ROWS=10000,
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        assert ds_res.inserted_primary_key is not None
        ds_id = int(ds_res.inserted_primary_key[0])

    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["TEMPLATE_OWNER"], 3: ["VIEWER"]})
    clear_perm_cache()

    m1 = create_model(
        _owner(),
        {
            "code": "FIN_SALES",
            "name": "Mô hình doanh thu",
            "description": "Phân tích doanh thu theo khách hàng",
            "data_source_id": ds_id,
        },
    )
    assert m1.ok, m1.message
    m2 = create_model(
        _owner(),
        {
            "code": "ACC_INV",
            "name": "Mô hình hóa đơn",
            "description": "Đối chiếu hóa đơn tác nghiệp",
            "data_source_id": ds_id,
        },
    )
    assert m2.ok, m2.message

    try:
        yield engine, ds_id, {"FIN_SALES": m1.data, "ACC_INV": m2.data}
    finally:
        clear_perm_cache()
        engine.dispose()


def test_breadcrumbs_and_permission_gate(rm_center_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.ui.pages.report_models as page
    from app.services.data_source import options_data_sources
    from app.ui.layout.shell import build_breadcrumbs

    assert page.MENU_CODE == "report_model"

    bc_list = build_breadcrumbs("/report-models")
    assert any(item["label"] == "Mô hình báo cáo" for item in bc_list)
    bc_detail = build_breadcrumbs("/report-models/12")
    assert any(item.get("href") == "/report-models" for item in bc_detail)

    # TEMPLATE_OWNER được phép gọi options_data_sources nhờ menu report_model
    ds_res = options_data_sources(_owner(), purpose="SOURCE")
    assert ds_res.ok and len(ds_res.data) == 1
    assert ds_res.data[0].name == "ORACLE_FIN_DEV"

    # Gate chưa đăng nhập -> /login
    monkeypatch.setattr(page, "get_current_ctx", lambda: None)
    unauth = _dump(page.layout())
    assert "/login" in unauth

    # Viewer không có menu report_model -> /forbidden
    monkeypatch.setattr(page, "get_current_ctx", _viewer)
    forbid = _dump(page.layout())
    assert "/forbidden" in forbid

    # Owner có menu report_model -> thấy header + nút Tạo mô hình
    monkeypatch.setattr(page, "get_current_ctx", _owner)
    ok_dump = _dump(page.layout())
    assert "Mô hình báo cáo" in ok_dump
    assert "Tạo mô hình" in ok_dump


def test_four_states_and_filter_helpers(rm_center_env) -> None:
    import app.ui.pages.report_models as page
    from app.services.semantic_model import list_models

    _, ds_id, _ = rm_center_env
    models = list_models(_owner(), include_archived=True).data

    # 1. Loading -> Skeleton
    sk_dump = _dump(page.render_models_body(rows=[], loading=True, has_filter=False, error_msg=None))
    assert "Skeleton" in sk_dump

    # 2. Empty (chưa có model vs do lọc)
    empty_raw = _dump(page.render_models_body(rows=[], loading=False, has_filter=False, error_msg=None))
    assert "Chưa có mô hình báo cáo" in empty_raw
    empty_flt = _dump(page.render_models_body(rows=[], loading=False, has_filter=True, error_msg=None))
    assert "Xóa bộ lọc" in empty_flt

    # 3. Lỗi nhưng giữ lại dữ liệu cũ + nút Thử lại
    err_dump = _dump(
        page.render_models_body(
            rows=page.models_to_grid_rows(models),
            loading=False,
            has_filter=False,
            error_msg="Mất kết nối tạm thời",
        )
    )
    assert "Mất kết nối tạm thời" in err_dump
    assert "Thử lại" in err_dump
    assert "FIN_SALES" in err_dump

    # 4. Data + filter
    filtered_q = page.filter_models(models, query="hóa đơn", data_source_id=None, status="ALL")
    assert [m["code"] for m in filtered_q] == ["ACC_INV"]
    filtered_ds = page.filter_models(models, query="", data_source_id=str(ds_id), status="DRAFT")
    assert len(filtered_ds) == 2

    grid_comp = page.render_models_body(
        rows=page.models_to_grid_rows(filtered_ds),
        loading=False,
        has_filter=False,
        error_msg=None,
    )
    grid_dump = _dump(grid_comp)
    assert grid_comp.children.dashGridOptions["rowHeight"] == 32
    assert grid_comp.children.dashGridOptions["headerHeight"] == 34
    assert "FIN_SALES" in grid_dump


def test_create_clone_impact_and_archive_flows(rm_center_env) -> None:
    import app.ui.pages.report_models as page
    from app.services.semantic_model import list_models

    _, ds_id, models_map = rm_center_env
    fin_id = int(models_map["FIN_SALES"]["id"])

    # Tạo model thiếu thông tin -> lỗi inline
    bad_id, bad_err, bad_rows, bad_toast = page.submit_create_model(
        _owner(),
        code="bad code!",
        name="",
        ds_id=str(ds_id),
        description="",
    )
    assert bad_id is None
    assert bad_err is not None
    assert bad_rows is None

    # Tạo model hợp lệ
    new_id, ok_err, ok_rows, ok_toast = page.submit_create_model(
        _owner(),
        code="OPS_BI",
        name="Vận hành BI",
        ds_id=str(ds_id),
        description="Mô hình mới",
    )
    assert isinstance(new_id, int) and new_id > 0
    assert ok_err is None
    assert ok_rows is not None and any(r["code"] == "OPS_BI" for r in ok_rows)

    # Clone model
    clone_err, clone_rows, _ = page.submit_clone_model(
        _owner(),
        source_model_id=fin_id,
        code="FIN_SALES_V2",
        name="Doanh thu V2",
        description="Bản sao độc lập",
    )
    assert clone_err is None
    assert clone_rows is not None and any(r["code"] == "FIN_SALES_V2" for r in clone_rows)

    # Impact Analysis Drawer
    drawer_content = page.build_impact_drawer_content(_owner(), fin_id)
    drawer_dump = _dump(drawer_content)
    assert "FIN_SALES" in drawer_dump
    assert "Chưa có báo cáo" in drawer_dump or "Báo cáo bị ảnh hưởng" in drawer_dump

    # Archive model (xác nhận an toàn, không xóa dữ liệu DB vật lý)
    arch_rows, arch_toast, arch_err = page.confirm_archive_model(_owner(), fin_id)
    assert arch_err is None
    assert arch_rows is not None
    all_rows = list_models(_owner(), include_archived=True).data
    fin_after = next(m for m in all_rows if int(m["id"]) == fin_id)
    assert fin_after["is_archived"] is True


def test_pattern_matching_callbacks_prevent_mount_trigger_and_actions(rm_center_env, monkeypatch) -> None:
    """Đảm bảo nút động trong body không gây ReferenceError và bỏ qua mount trigger n_clicks=None."""
    import dash
    from dash.exceptions import PreventUpdate

    import app.ui.pages.report_models as page
    from app.services.semantic_model import list_models

    _, _, models_map = rm_center_env
    fin_id = int(models_map["FIN_SALES"]["id"])
    models = list_models(_owner(), include_archived=True).data or []

    monkeypatch.setattr(page, "get_current_ctx", lambda: _owner())

    class _FakeCtx:
        def __init__(self, triggered_id):
            self.triggered_id = triggered_id

    # 1. Clear-filter button mount (n_clicks=None) -> PreventUpdate; click (n_clicks=1) -> reset bộ lọc
    monkeypatch.setattr(dash, "callback_context", _FakeCtx({"type": "rm-center-clear-filter-btn", "k": "empty"}))
    with pytest.raises(PreventUpdate):
        page.handle_center_filter_or_refresh("abc", "DRAFT", None, None, [None], models)

    res = page.handle_center_filter_or_refresh("abc", "DRAFT", None, None, [1], models)
    assert res[2:] == ("", "ALL")

    # 2. Retry button mount (n_clicks=None) -> PreventUpdate
    monkeypatch.setattr(dash, "callback_context", _FakeCtx({"type": "rm-center-retry-btn", "k": "full"}))
    with pytest.raises(PreventUpdate):
        page.handle_center_filter_or_refresh("", "ALL", None, [None], None, models)

    # 3. Empty create button mount vs click
    monkeypatch.setattr(dash, "callback_context", _FakeCtx({"type": "rm-center-empty-create-btn", "k": "empty"}))
    with pytest.raises(PreventUpdate):
        page.handle_create_modal_toggle(None, [None], None)
    assert page.handle_create_modal_toggle(None, [1], None)[0] is True

    # 4. Grid pattern-matching ALL input
    with pytest.raises(PreventUpdate):
        page.handle_grid_action([None], models)
    action_res = page.handle_grid_action([{"value": {"action": "open", "id": fin_id}}], models)
    assert action_res[0] == f"/report-models/{fin_id}"
