"""Test page Mô hình dữ liệu — bước 3: menu + route + skeleton + permission.

Viết trước (đỏ) rồi code cho xanh, theo quy tắc task.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx
from app.db.metadata import metadata, recon_user


@pytest.fixture
def dm_env(tmp_path, monkeypatch):
    db_file = tmp_path / "data_model_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res_adm = conn.execute(
            recon_user.insert().values(
                USERNAME="admin_test",
                FULL_NAME="Quản Trị Viên",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        adm_id = res_adm.inserted_primary_key[0]
        seed_perm_basics(engine, {adm_id: ["ADMIN"]}, conn=conn)

        res_op = conn.execute(
            recon_user.insert().values(
                USERNAME="op_test",
                FULL_NAME="Vận Hành Viên",
                PASSWORD_HASH=hash_password("op123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        op_id = res_op.inserted_primary_key[0]
        seed_perm_basics(engine, {op_id: ["OPERATOR"]}, conn=conn)

    return {
        "engine": engine,
        "admin_ctx": Ctx(user_id=adm_id, username="admin_test", full_name="Quản Trị Viên", roles=["ADMIN"]),
        "op_ctx": Ctx(user_id=op_id, username="op_test", full_name="Vận Hành Viên", roles=["OPERATOR"]),
    }


def _walk(node):
    """Duyệt cây component Dash theo chiều sâu."""
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


def test_menu_data_model_declared():
    """Menu data_model khai báo đúng nhóm QUẢN TRỊ, sau report_admin."""
    from app.ui.menus import MENU_BY_CODE, MENUS

    menu = MENU_BY_CODE["data_model"]
    assert menu.label == "Mô hình dữ liệu"
    assert menu.group == "QUAN_TRI"
    assert menu.path == "/data-model"
    assert menu.order == 50
    assert menu.icon == "lucide:network"
    assert menu.hideable == "Y"
    report_admin = MENU_BY_CODE["report_admin"]
    assert menu.order > report_admin.order
    assert menu in MENUS


def test_menu_visible_only_when_granted(dm_env):
    """ADMIN thấy menu; OPERATOR chưa cấp không thấy; cấp thì thấy."""
    from app.services.perm import clear_perm_cache, effective_menus

    assert "data_model" in effective_menus(dm_env["admin_ctx"], engine=dm_env["engine"])
    assert "data_model" not in effective_menus(dm_env["op_ctx"], engine=dm_env["engine"])

    # Cấp menu cho vai trò OPERATOR như ADMIN làm trên /roles.
    with dm_env["engine"].begin() as conn:
        role_id = conn.execute(text("SELECT ID FROM RECON_ROLE WHERE CODE = 'OPERATOR'")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO RECON_ROLE_MENU (ROLE_ID, MENU_CODE, GRANTED_BY, GRANTED_AT) "
                "VALUES (:rid, 'data_model', 'admin_test', :now)"
            ),
            {"rid": int(role_id), "now": datetime.now(timezone.utc).replace(tzinfo=None)},
        )
    clear_perm_cache()
    assert "data_model" in effective_menus(dm_env["op_ctx"], engine=dm_env["engine"])


def test_get_data_model_returns_manifest_and_drift(dm_env):
    """Service trả 43 bảng từ manifest đã commit + drift SYNCED trên DB test."""
    from app.services.data_model import get_data_model

    res = get_data_model(dm_env["admin_ctx"])
    assert res.ok, res.message
    assert res.data is not None
    tables = res.data["manifest"]["tables"]
    assert len(tables) == 43
    names = {t["name"] for t in tables}
    assert "RECON_RUN" in names
    assert "RECON_RPT_PARAM" in names
    assert res.data["drift"]["status"] == "SYNCED"
    assert res.data["drift"]["drifts"] == []
    assert isinstance(res.data["history"], list)
    assert len(res.data["history"]) == 58


def test_get_data_model_forbidden_without_menu(dm_env):
    """Service bị chặn khi vai trò chưa được cấp menu data_model."""
    from app.services.data_model import get_data_model

    res = get_data_model(dm_env["op_ctx"])
    assert not res.ok
    assert res.code is not None
    assert "data_model" in str(res.details or "") or "quyền" in res.message.lower()


def test_layout_gate_redirects(dm_env, monkeypatch):
    """Chưa đăng nhập -> /login; không quyền -> /forbidden."""
    import app.ui.pages.data_model as page

    monkeypatch.setattr(page, "get_current_ctx", lambda: None)
    node = page.layout()
    assert "/login" in str(node)

    monkeypatch.setattr(page, "get_current_ctx", lambda: dm_env["op_ctx"])
    node = page.layout()
    assert "/forbidden" in str(node)


def test_layout_admin_skeleton(dm_env, monkeypatch):
    """ADMIN vào được: Box cao calc(100vh - 88px), đủ 3 panel + stores."""
    import app.ui.pages.data_model as page

    monkeypatch.setattr(page, "get_current_ctx", lambda: dm_env["admin_ctx"])
    box = page.layout()
    assert box.style["height"] == "calc(100vh - 88px)"
    text = str(box)
    assert "Mô hình dữ liệu" in text
    assert "Lịch sử thay đổi" in text
    assert "Đồng bộ schema" in text
    assert "data-model-search" in text
    for store_id in (
        "data-model-manifest-store",
        "data-model-selection-store",
        "data-model-ui-store",
        "data-model-dblclick-store",
    ):
        assert store_id in text, store_id
    nodes = list(_walk(box))
    ids = {getattr(n, "id", None) for n in nodes}
    assert "data-model-explorer-container" in ids
    assert "data-model-canvas-container" in ids
    assert "data-model-detail-container" in ids
    assert "data-model-status-bar" in ids


def test_layout_accepts_query_kwargs(dm_env, monkeypatch):
    """layout(**kwargs) đọc ?table=... và preselect table đó."""
    import app.ui.pages.data_model as page

    monkeypatch.setattr(page, "get_current_ctx", lambda: dm_env["admin_ctx"])
    box = page.layout(table="RECON_RUN")
    nodes = list(_walk(box))
    store = next(n for n in nodes if getattr(n, "id", None) == "data-model-selection-store")
    assert store.data["kind"] == "table"
    assert store.data["table"] == "RECON_RUN"
    box2 = page.layout(table="RECON_RUN", domain="recon", mode="compact")
    store2 = next(n for n in _walk(box2) if getattr(n, "id", None) == "data-model-selection-store")
    assert store2.data["table"] == "RECON_RUN"


# --- Bước 4: Schema Explorer + command bar ---


@pytest.fixture
def dm_manifest():
    from app.services.data_model import load_history, load_manifest

    return {
        "manifest": load_manifest(),
        "history": load_history(),
        "drift": {"status": "SYNCED", "drifts": []},
        "counts": {"tables": 43, "columns": 515, "relationships": 53},
    }


def _manifest_tables(dm_manifest):
    return dm_manifest["manifest"]["tables"]


def test_filter_tables_by_name_column_description(dm_manifest):
    import app.ui.pages.data_model as page

    tables = _manifest_tables(dm_manifest)
    by_name = page.filter_tables(tables, "RECON_RUN", "all")
    # Khớp tên bảng + tên FK constraint (vd FK của RECON_RESULT_ROW trỏ
    # RECON_RUN) nên có thêm 3 bảng ngoài 3 bảng tên chứa RECON_RUN.
    assert {t["name"] for t in by_name} == {
        "RECON_RUN",
        "RECON_RUN_QUEUE",
        "RECON_RUN_SUMMARY",
        "RECON_INVALID_ROW",
        "RECON_RESULT_DIFF",
        "RECON_RESULT_ROW",
    }
    # Tìm theo tên cột: GRID_SPAN chỉ có ở RECON_RPT_PARAM.
    by_col = page.filter_tables(tables, "GRID_SPAN", "all")
    assert [t["name"] for t in by_col] == ["RECON_RPT_PARAM"]
    # Tìm không dấu vẫn ra mô tả có dấu.
    by_desc = page.filter_tables(tables, "bao cao", "all")
    assert "RECON_REPORT" in {t["name"] for t in by_desc}
    assert page.filter_tables(tables, "xyz-khong-co", "all") == []
    assert page.filter_tables(tables, "", "all") == tables


def test_filter_tables_by_domain(dm_manifest):
    import app.ui.pages.data_model as page

    tables = _manifest_tables(dm_manifest)
    assert len(page.filter_tables(tables, "", "report")) == 11
    assert len(page.filter_tables(tables, "", "core")) == 10
    assert len(page.filter_tables(tables, "", "recon")) == 19
    assert len(page.filter_tables(tables, "", "admin")) == 3
    assert len(page.filter_tables(tables, "", "other")) == 0
    # Domain + query kết hợp.
    assert [t["name"] for t in page.filter_tables(tables, "GRID_SPAN", "report")] == ["RECON_RPT_PARAM"]
    assert page.filter_tables(tables, "GRID_SPAN", "core") == []


def test_group_tables_order_and_counts(dm_manifest):
    import app.ui.pages.data_model as page

    groups = page.group_tables(_manifest_tables(dm_manifest))
    assert [code for code, _label, _t in groups] == ["core", "recon", "report", "admin"]
    assert [len(t) for _c, _l, t in groups] == [10, 19, 11, 3]
    assert groups[0][1] == "Core"
    assert groups[1][1] == "Đối soát"


def test_matching_columns(dm_manifest):
    import app.ui.pages.data_model as page

    tables = {t["name"]: t for t in _manifest_tables(dm_manifest)}
    assert page.matching_columns(tables["RECON_RPT_PARAM"], "GRID_SPAN") == ["GRID_SPAN"]
    assert page.matching_columns(tables["RECON_RPT_PARAM"], "grid_span") == ["GRID_SPAN"]
    assert page.matching_columns(tables["RECON_RUN"], "GRID_SPAN") == []
    assert page.matching_columns(tables["RECON_RUN"], "") == []


def test_render_explorer_groups_and_selection(dm_manifest):
    import app.ui.pages.data_model as page

    tables = _manifest_tables(dm_manifest)
    node = page.render_explorer(tables, {"kind": "table", "table": "RECON_RUN"}, {"expanded": {}}, "")
    text = str(node)
    assert "Core (10)" in text
    assert "Đối soát (19)" in text
    assert "Báo cáo (11)" in text
    assert "Quản trị (3)" in text
    assert "RECON_RUN" in text
    nodes = list(_walk(node))
    rows = [n for n in nodes if isinstance(getattr(n, "id", None), dict) and n.id.get("type") == "dm-table-item"]
    assert len(rows) == 43
    selected = [n for n in rows if n.id.get("table") == "RECON_RUN"]
    assert len(selected) == 1
    assert "active" in (selected[0].className or "")
    assert selected[0].to_plotly_json()["props"].get("aria-selected") in (True, "true")
    # Tooltip mô tả, không gọi backend: mô tả nằm trong cây.
    assert "Lần chạy đối soát" in text


def test_render_explorer_search_auto_expand_and_match(dm_manifest):
    import app.ui.pages.data_model as page

    tables = page.filter_tables(_manifest_tables(dm_manifest), "GRID_SPAN", "all")
    node = page.render_explorer(tables, {"kind": None, "table": None}, {"expanded": {}}, "GRID_SPAN")
    text = str(node)
    # Group có match tự expand dù ui-store không ghi expanded.
    assert "RECON_RPT_PARAM" in text
    assert "GRID_SPAN" in text
    assert "RECON_RUN" not in text


def test_render_explorer_empty_search(dm_manifest):
    import app.ui.pages.data_model as page

    node = page.render_explorer([], {"kind": None, "table": None}, {"expanded": {}}, "xyz")
    text = str(node)
    assert "Không tìm thấy table hoặc column phù hợp." in text
    assert "data-model-clear-filter-btn" in text


def test_handle_table_click_updates_selection_and_url(monkeypatch):
    import json

    import dash

    import app.ui.pages.data_model as page

    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(
            triggered=[
                {
                    "prop_id": json.dumps({"type": "dm-table-item", "table": "RECON_RUN"}) + ".n_clicks",
                    "value": 1,
                }
            ]
        ),
    )
    selection, href = page.handle_table_click(
        [1], {"kind": None, "table": None}, {"domain": "recon", "mode": "relations", "expanded": {}}
    )
    assert selection == {"kind": "table", "table": "RECON_RUN"}
    assert href == "/data-model?table=RECON_RUN&domain=recon&mode=relations"
    # Không có trigger thì không đổi.
    monkeypatch.setattr("dash.callback_context", SimpleNamespace(triggered=[]))
    selection2, href2 = page.handle_table_click(
        [0], {"kind": None, "table": None}, {"domain": "all", "mode": "relations", "expanded": {}}
    )
    assert selection2 == {"kind": None, "table": None}
    assert href2 == dash.no_update
    # Phát lại lúc load với n_clicks=0 cũng không đổi (hồi quy: từng tự chọn
    # RECON_APP_SETTING và đổi URL ngay khi mở page).
    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(
            triggered=[
                {
                    "prop_id": json.dumps({"type": "dm-table-item", "table": "RECON_APP_SETTING"}) + ".n_clicks",
                    "value": 0,
                }
            ]
        ),
    )
    selection3, href3 = page.handle_table_click(
        [0], {"kind": None, "table": None}, {"domain": "all", "mode": "relations", "expanded": {}}
    )
    assert selection3 == {"kind": None, "table": None}
    assert href3 == dash.no_update


def test_handle_group_toggle(monkeypatch):
    import json

    import app.ui.pages.data_model as page

    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(
            triggered=[
                {
                    "prop_id": json.dumps({"type": "dm-group-toggle", "domain": "report"}) + ".n_clicks",
                    "value": 1,
                }
            ]
        ),
    )
    ui = page.handle_group_toggle([1], {"expanded": {}, "domain": "all", "mode": "relations"})
    assert ui["expanded"] == {"report": False}
    ui2 = page.handle_group_toggle([1], {"expanded": {"report": False}, "domain": "all", "mode": "relations"})
    assert ui2["expanded"] == {"report": True}


def test_handle_context_menu_actions(monkeypatch):
    import json

    import app.ui.pages.data_model as page

    def _trigger(action, table="RECON_RUN"):
        monkeypatch.setattr(
            "dash.callback_context",
            SimpleNamespace(
                triggered=[
                    {
                        "prop_id": json.dumps({"type": "dm-table-menu", "table": table, "action": action})
                        + ".n_clicks",
                        "value": 1,
                    }
                ]
            ),
        )

    _trigger("center")
    sel, ui, hist_filter, opened, _copy = page.handle_context_menu(
        [1], {"kind": None, "table": None}, {"expanded": {}}, {"query": "", "change_type": "all", "table": None}
    )
    assert sel == {"kind": "table", "table": "RECON_RUN"}
    assert ui["center_table"] == "RECON_RUN"
    assert opened is False

    _trigger("columns")
    sel, ui, _hf, _o, _copy = page.handle_context_menu(
        [1], {"kind": None, "table": None}, {"expanded": {}}, {"query": "", "change_type": "all", "table": None}
    )
    assert sel == {"kind": "table", "table": "RECON_RUN"}
    assert ui["mode"] == "relations"

    _trigger("history")
    _sel, _ui, hist_filter, opened, _copy = page.handle_context_menu(
        [1], {"kind": None, "table": None}, {"expanded": {}}, {"query": "", "change_type": "all", "table": None}
    )
    assert hist_filter["table"] == "RECON_RUN"
    assert opened is True

    _trigger("copy")
    _sel, _ui, _hf, opened_copy, copy_store = page.handle_context_menu(
        [1], {"kind": None, "table": None}, {"expanded": {}}, {"query": "", "change_type": "all", "table": None}
    )
    assert copy_store == {"text": "RECON_RUN"}
    assert opened_copy is False


def test_handle_dblclick_centers_and_zooms(monkeypatch):
    import dash

    import app.ui.pages.data_model as page

    sel, ui, zoom = page.handle_dblclick(
        {"table": "RECON_RPT_PARAM", "ts": 123},
        {"kind": None, "table": None},
        {"expanded": {}, "mode": "compact"},
        0.55,
    )
    assert sel == {"kind": "table", "table": "RECON_RPT_PARAM"}
    assert ui["center_table"] == "RECON_RPT_PARAM"
    assert ui["mode"] == "relations"
    assert zoom == 1.0
    with pytest.raises(dash.exceptions.PreventUpdate):
        page.handle_dblclick(None, {"kind": None, "table": None}, {"expanded": {}}, 1.0)


def test_handle_clear_filter(monkeypatch):
    import dash

    import app.ui.pages.data_model as page

    assert page.handle_clear_filter(1) == ("", "all")
    with pytest.raises(dash.exceptions.PreventUpdate):
        page.handle_clear_filter(0)


def test_update_workspace_filters_and_counts(dm_manifest):
    import app.ui.pages.data_model as page

    explorer, _canvas, _detail, count_text, _status = page.update_workspace(
        dm_manifest, "", "all", "relations", {"kind": None, "table": None}, {"expanded": {}}, 1.0
    )
    assert "43 tables" in count_text
    assert "RECON_RUN" in str(explorer)
    explorer2, _c2, _d2, count2, _s2 = page.update_workspace(
        dm_manifest, "GRID_SPAN", "all", "relations", {"kind": None, "table": None}, {"expanded": {}}, 1.0
    )
    assert "1 tables" in count2
    assert "RECON_RPT_PARAM" in str(explorer2)
    explorer3, _c3, _d3, count3, _s3 = page.update_workspace(
        dm_manifest, "", "report", "relations", {"kind": None, "table": None}, {"expanded": {}}, 1.0
    )
    assert "11 tables" in count3
    # Không có manifest -> lỗi đọc metadata.
    explorer4, _c4, _d4, _ct4, _s4 = page.update_workspace(
        None, "", "all", "relations", {"kind": None, "table": None}, {"expanded": {}}, 1.0
    )
    assert "Không thể đọc metadata database." in str(explorer4)


def test_explorer_context_menu_has_no_destructive_actions(dm_manifest):
    import app.ui.pages.data_model as page

    node = page.render_explorer(_manifest_tables(dm_manifest), {"kind": None, "table": None}, {"expanded": {}}, "")
    text = str(node)
    assert "Center trong ER Diagram" in text
    assert "Xem columns" in text
    assert "Xem relationships" in text
    assert "Xem lịch sử thay đổi" in text
    assert "Copy table name" in text
    for forbidden in ("Drop table", "Alter table", "Delete column", "Run SQL"):
        assert forbidden not in text
