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
    sel, ui, hist_filter, opened, _copy, _s, _t = page.handle_context_menu(
        [1], {"kind": None, "table": None}, {"expanded": {}}, {"query": "", "change_type": "all", "table": None}
    )
    assert sel == {"kind": "table", "table": "RECON_RUN"}
    assert ui["center_table"] == "RECON_RUN"
    assert opened is False

    _trigger("columns")
    sel, ui, _hf, _o, _copy, _s, _t = page.handle_context_menu(
        [1], {"kind": None, "table": None}, {"expanded": {}}, {"query": "", "change_type": "all", "table": None}
    )
    assert sel == {"kind": "table", "table": "RECON_RUN"}
    assert ui["mode"] == "relations"

    _trigger("history")
    _sel, _ui, hist_filter, opened, _copy, _s, _t = page.handle_context_menu(
        [1], {"kind": None, "table": None}, {"expanded": {}}, {"query": "", "change_type": "all", "table": None}
    )
    assert hist_filter["table"] == "RECON_RUN"
    assert opened is True
    assert _s == "" and _t == "all"

    _trigger("copy")
    _sel, _ui, _hf, opened_copy, copy_store, _s, _t = page.handle_context_menu(
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

    explorer, _canvas, _detail, count_text, _status, _zoom = page.update_workspace(
        dm_manifest, "", "all", "relations", {"kind": None, "table": None}, {"expanded": {}}, 1.0
    )
    assert "43 tables" in count_text
    assert "RECON_RUN" in str(explorer)
    # Nhãn zoom theo zoom-store (fit đổi zoom thì nhãn cũng đổi theo).
    assert _zoom == "100%"
    _e, _c, _d, _ct, _st, zoom_label = page.update_workspace(
        dm_manifest, "", "all", "relations", {"kind": None, "table": None}, {"expanded": {}}, 0.55
    )
    assert zoom_label == "55%"
    explorer2, _c2, _d2, count2, _s2, _z2 = page.update_workspace(
        dm_manifest, "GRID_SPAN", "all", "relations", {"kind": None, "table": None}, {"expanded": {}}, 1.0
    )
    assert "1 tables" in count2
    assert "RECON_RPT_PARAM" in str(explorer2)
    explorer3, _c3, _d3, count3, _s3, _z3 = page.update_workspace(
        dm_manifest, "", "report", "relations", {"kind": None, "table": None}, {"expanded": {}}, 1.0
    )
    assert "11 tables" in count3
    # Không có manifest -> lỗi đọc metadata.
    explorer4, _c4, _d4, _ct4, _s4, _z4 = page.update_workspace(
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


# --- Bước 5: ER Canvas ---


def test_layout_entities_deterministic(dm_manifest):
    import app.ui.pages.data_model as page

    tables = _manifest_tables(dm_manifest)
    first = page.layout_entities(tables, "relations")
    second = page.layout_entities(tables, "relations")
    assert first == second
    assert len(first) == 43
    # Cột theo domain, thứ tự Core, Đối soát, Báo cáo, Quản trị.
    assert first["RECON_USER"]["x"] == 0
    assert first["RECON_RUN"]["x"] == 205 + 40
    assert first["RECON_REPORT"]["x"] == 2 * (205 + 40)
    assert first["RECON_DATA_SOURCE"]["x"] == 3 * (205 + 40)
    # Trong domain xếp theo tên bảng alphabet: y tăng dần theo tên.
    core_names = sorted(t["name"] for t in tables if t["domain"] == "core")
    core_ys = [first[n]["y"] for n in core_names]
    assert core_ys == sorted(core_ys)
    # Chiều cao relations = 34 + 24 * số cột.
    run_table = next(t for t in tables if t["name"] == "RECON_RUN")
    assert first["RECON_RUN"]["h"] == 34 + 24 * len(run_table["columns"])
    assert first["RECON_RUN"]["w"] == 205
    # Canvas đủ chứa mọi entity.
    w, h = page.canvas_size(first)
    assert w == 4 * 205 + 3 * 40
    assert h >= max(v["y"] + v["h"] for v in first.values())


def test_layout_entities_compact_fixed_height(dm_manifest):
    import app.ui.pages.data_model as page

    layout = page.layout_entities(_manifest_tables(dm_manifest), "compact")
    assert {v["h"] for v in layout.values()} == {40}
    assert len(layout) == 43


def test_relationship_lines_match_manifest_fk(dm_manifest):
    import app.ui.pages.data_model as page

    tables = _manifest_tables(dm_manifest)
    layout = page.layout_entities(tables, "relations")
    lines = page.relationship_lines(tables, layout)
    total_fk = sum(len(t.get("foreign_keys", [])) for t in tables)
    assert len(lines) == total_fk == 53
    assert all(line["length"] > 0 for line in lines)
    assert all(isinstance(line["angle_deg"], float) for line in lines)
    user_role_line = next(line for line in lines if line["source"] == "RECON_USER_ROLE" and line["column"] == "USER_ID")
    assert user_role_line["target"] == "RECON_USER"
    assert user_role_line["references_column"] == "ID"


def test_render_canvas_entities_and_markers(dm_manifest):
    import app.ui.pages.data_model as page

    tables = _manifest_tables(dm_manifest)
    node = page.render_canvas(tables, {"kind": None, "table": None}, {}, 1.0, "")
    text = str(node)
    assert "data-model-canvas-inner" in text
    assert "data-model-canvas-inner" in text
    nodes = list(_walk(node))
    entities = [n for n in nodes if isinstance(getattr(n, "id", None), dict) and n.id.get("type") == "dm-entity"]
    assert len(entities) == 43
    lines = [n for n in nodes if isinstance(getattr(n, "id", None), dict) and n.id.get("type") == "dm-rel-line"]
    assert len(lines) == 53
    # Marker PK/FK bằng ký tự, không chỉ bằng màu.
    assert "◆" in text
    assert "↗" in text
    # Compact: chỉ header, không liệt kê cột.
    compact = page.render_canvas(tables, {"kind": None, "table": None}, {}, 1.0, "")
    _ = compact
    compact_node = page.render_canvas(tables, {"kind": None, "table": None}, {}, 1.0, "")
    assert "RECON_RUN" in str(compact_node)


def test_render_canvas_compact_hides_columns(dm_manifest):
    import app.ui.pages.data_model as page

    tables = _manifest_tables(dm_manifest)
    # render_canvas nhận mode qua ui-store.
    relations = page.render_canvas(tables, {"kind": None, "table": None}, {"mode": "relations"}, 1.0, "")
    compact = page.render_canvas(tables, {"kind": None, "table": None}, {"mode": "compact"}, 1.0, "")
    assert "CREATED_AT" in str(relations)
    assert "CREATED_AT" not in str(compact)


def test_render_canvas_selection_highlight(dm_manifest):
    import app.ui.pages.data_model as page

    tables = _manifest_tables(dm_manifest)
    node = page.render_canvas(tables, {"kind": "table", "table": "RECON_RUN"}, {"mode": "relations"}, 1.0, "")
    nodes = list(_walk(node))
    entities = {
        n.id["table"]: n for n in nodes if isinstance(getattr(n, "id", None), dict) and n.id.get("type") == "dm-entity"
    }
    assert "selected" in (entities["RECON_RUN"].className or "")
    # Bảng liên quan (RECON_RESULT_ROW trỏ RECON_RUN) được accent, bảng không
    # liên quan (RECON_USER) mờ đi.
    assert "related" in (entities["RECON_RESULT_ROW"].className or "")
    assert "dimmed" in (entities["RECON_USER"].className or "")


def test_render_canvas_query_highlights_column(dm_manifest):
    import app.ui.pages.data_model as page

    tables = page.filter_tables(_manifest_tables(dm_manifest), "GRID_SPAN", "all")
    node = page.render_canvas(tables, {"kind": None, "table": None}, {"mode": "relations"}, 1.0, "GRID_SPAN")
    assert "RECON_RPT_PARAM" in str(node)
    assert "dm-match" in str(node)


def test_handle_zoom_clamps(monkeypatch):
    import dash

    import app.ui.pages.data_model as page

    # Phóng to từ 1.0 -> 1.1; tới max 1.35 thì kẹp.
    assert page.handle_zoom_in(1, 1.0) == 1.1
    assert page.handle_zoom_in(1, 1.35) == 1.35
    assert page.handle_zoom_in(1, 1.3) == 1.35
    # Thu nhỏ từ 1.0 -> 0.9; tới min 0.55 thì kẹp.
    assert page.handle_zoom_out(1, 1.0) == 0.9
    assert page.handle_zoom_out(1, 0.55) == 0.55
    assert page.handle_zoom_out(1, 0.6) == 0.55
    with pytest.raises(dash.exceptions.PreventUpdate):
        page.handle_zoom_in(0, 1.0)
    with pytest.raises(dash.exceptions.PreventUpdate):
        page.handle_zoom_out(None, 1.0)


def test_handle_entity_click(monkeypatch):
    import json

    import app.ui.pages.data_model as page

    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(
            triggered=[
                {
                    "prop_id": json.dumps({"type": "dm-entity", "table": "RECON_RUN"}) + ".n_clicks",
                    "value": 1,
                }
            ]
        ),
    )
    selection, href = page.handle_entity_click(
        [1], {"kind": None, "table": None}, {"domain": "all", "mode": "relations"}
    )
    assert selection == {"kind": "table", "table": "RECON_RUN"}
    assert href == "/data-model?table=RECON_RUN&domain=all&mode=relations"


def test_handle_rel_click_selects_relationship(dm_manifest, monkeypatch):
    import json

    import app.ui.pages.data_model as page

    tables = _manifest_tables(dm_manifest)
    layout = page.layout_entities(tables, "relations")
    lines = page.relationship_lines(tables, layout)
    idx = next(i for i, line in enumerate(lines) if line["source"] == "RECON_USER_ROLE" and line["column"] == "USER_ID")
    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(
            triggered=[{"prop_id": json.dumps({"type": "dm-rel-line", "index": idx}) + ".n_clicks", "value": 1}]
        ),
    )
    selection = page.handle_rel_click([1] * len(lines), dm_manifest, {"kind": None, "table": None})
    assert selection["kind"] == "relationship"
    assert selection["source"] == "RECON_USER_ROLE"
    assert selection["target"] == "RECON_USER"
    assert selection["column"] == "USER_ID"
    assert selection["references_column"] == "ID"


# --- Bước 6: Detail Panel + History + Drift viewer ---


def test_render_table_detail_sections(dm_manifest):
    """Detail table: header, KPI, badges, column list, relationships, index/constraint, recent changes."""
    import app.ui.pages.data_model as page

    tables = {t["name"]: t for t in _manifest_tables(dm_manifest)}
    node = page.render_table_detail(tables["RECON_RUN"], dm_manifest["manifest"], dm_manifest["history"], "")
    text = str(node)
    assert "RECON_RUN" in text
    assert "Lần chạy đối soát" in text
    assert "28" in text  # KPI Columns
    assert "5" in text  # KPI Relationships (out)
    assert "Đối soát" in text  # badge domain
    assert "Đồng bộ" in text  # badge schema status (không drift)
    # Column list: PK, FK, type, nullable.
    assert "ID" in text and "INTEGER" in text
    assert "FILE_ID" in text and "RECON_FILE.ID" in text
    assert "NOT NULL" in text
    assert "Nullable" in text
    # Relationships out + in.
    assert "RECON_RUN.FILE_ID → RECON_FILE.ID" in text
    assert "RECON_RESULT_ROW.RUN_ID → RECON_RUN.ID" in text
    assert "fk_RECON_RUN_FILE_ID_RECON_FILE" in text
    # Index/constraint (không hide PK/FK).
    assert "Primary Key" in text
    assert "ID" in text
    # Recent changes theo table (TABLE_CREATED + 2 COLUMN_ADDED).
    assert "COLUMN_ADDED" in text
    assert "BATCH_RUN_ID" in text


def test_render_table_detail_query_highlight(dm_manifest):
    """Query khớp column thì highlight cột đó trong detail."""
    import app.ui.pages.data_model as page

    tables = {t["name"]: t for t in _manifest_tables(dm_manifest)}
    node = page.render_table_detail(
        tables["RECON_RUN"], dm_manifest["manifest"], dm_manifest["history"], "batch_run_id"
    )
    text = str(node)
    assert "BATCH_RUN_ID" in text
    assert "dm-match" in text


def test_render_table_detail_no_changes(dm_manifest):
    """Table không có history thì hiện 'Chưa ghi nhận thay đổi schema cho table này.'"""
    import app.ui.pages.data_model as page

    tables = {t["name"]: t for t in _manifest_tables(dm_manifest)}
    node = page.render_table_detail(tables["RECON_RUN"], dm_manifest["manifest"], [], "")
    assert "Chưa ghi nhận thay đổi schema cho table này." in str(node)


def test_render_table_detail_drift_badge(dm_manifest):
    """Table có drift thì badge schema status báo drift."""
    import app.ui.pages.data_model as page

    tables = {t["name"]: t for t in _manifest_tables(dm_manifest)}
    drifts = [
        {
            "type": "COLUMN_EXTRA",
            "table": "RECON_RUN",
            "column": "EXTRA_COL",
            "detail": "Cột EXTRA_COL có trong database nhưng không có trong model.",
            "db_value": "EXTRA_COL",
            "model_value": None,
        }
    ]
    node = page.render_table_detail(
        tables["RECON_RUN"], dm_manifest["manifest"], dm_manifest["history"], "", drifts=drifts
    )
    assert "Drift" in str(node)


def test_render_relationship_detail(dm_manifest):
    """Relationship detail: source/target/constraint/N:1/delete rule + nút Source/Target."""
    import app.ui.pages.data_model as page

    rel = {
        "kind": "relationship",
        "source": "RECON_USER_ROLE",
        "target": "RECON_USER",
        "column": "USER_ID",
        "references_column": "ID",
        "constraint": "fk_RECON_USER_ROLE_USER_ID_RECON_USER",
        "on_delete": None,
    }
    node = page.render_relationship_detail(rel, dm_manifest["manifest"])
    text = str(node)
    assert "RECON_USER_ROLE.USER_ID" in text
    assert "RECON_USER.ID" in text
    assert "fk_RECON_USER_ROLE_USER_ID_RECON_USER" in text
    assert "N:1" in text
    assert "—" in text  # delete rule chưa có trong metadata
    assert "Source table" in text
    assert "Target table" in text
    nodes = list(_walk(node))
    nav_ids = [n.id for n in nodes if isinstance(getattr(n, "id", None), dict) and n.id.get("type") == "dm-rel-nav"]
    assert {"type": "dm-rel-nav", "table": "RECON_USER_ROLE"} in nav_ids
    assert {"type": "dm-rel-nav", "table": "RECON_USER"} in nav_ids


def test_render_detail_empty_and_dispatch(dm_manifest):
    """Detail trống khi chưa chọn; dispatch sang relationship detail khi chọn relationship."""
    import app.ui.pages.data_model as page

    empty = page.render_detail({"kind": None, "table": None}, dm_manifest["manifest"], [], "")
    assert "Chọn một table hoặc relationship để xem chi tiết." in str(empty)

    rel = {
        "kind": "relationship",
        "source": "RECON_USER_ROLE",
        "target": "RECON_USER",
        "column": "USER_ID",
        "references_column": "ID",
        "constraint": "fk_RECON_USER_ROLE_USER_ID_RECON_USER",
        "on_delete": None,
    }
    node = page.render_detail(rel, dm_manifest["manifest"], [], "")
    assert "RECON_USER_ROLE.USER_ID" in str(node)


def test_filter_history_by_type_table_query(dm_manifest):
    """Lọc history theo type, theo table, theo query (migration/entity)."""
    import app.ui.pages.data_model as page

    history = dm_manifest["history"]
    assert len(page.filter_history(history, "", "COLUMN_ADDED", None)) == 11
    assert len(page.filter_history(history, "", "all", "RECON_RUN")) == 3
    assert len(page.filter_history(history, "0006", "all", None)) == 12
    assert len(page.filter_history(history, "menu_permission", "all", None)) == 9
    assert len(page.filter_history(history, "xyz-khong-co", "all", None)) == 0
    # Lọc theo table không nhầm RECON_RUN_QUEUE / RECON_RUN_SUMMARY vào RECON_RUN.
    names = {e["entity"] for e in page.filter_history(history, "", "TABLE_CREATED", "RECON_RUN")}
    assert names == {"RECON_RUN"}


def test_render_history_timeline(dm_manifest):
    """Timeline history: timestamp giờ VN, type, entity, migration, before/after."""
    import app.ui.pages.data_model as page

    events = page.filter_history(dm_manifest["history"], "", "COLUMN_ADDED", "RECON_USER_ROLE")
    assert len(events) == 3
    node = page.render_history_timeline(events)
    text = str(node)
    assert "05/11/2026 07:00" in text  # 00:00 UTC -> 07:00 giờ VN
    assert "COLUMN_ADDED" in text
    assert "RECON_USER_ROLE.ROLE_ID" in text
    assert "0003_menu_permission" in text
    assert "BIGINT, nullable=True" in text
    assert "3 thay đổi" in text

    empty = page.render_history_timeline([])
    assert "Không có thay đổi nào phù hợp." in str(empty)


def test_drift_group_and_filter():
    """Map 10 drift type về 5 nhóm filter; filter theo nhóm."""
    import app.ui.pages.data_model as page

    assert page.drift_group("TABLE_MISSING") == "table"
    assert page.drift_group("TABLE_EXTRA") == "table"
    assert page.drift_group("COLUMN_MISSING") == "column"
    assert page.drift_group("TYPE_CHANGED") == "column"
    assert page.drift_group("NULLABILITY_CHANGED") == "column"
    assert page.drift_group("FK_CHANGED") == "relationship"
    assert page.drift_group("INDEX_CHANGED") == "index"
    assert page.drift_group("PK_CHANGED") == "constraint"
    assert page.drift_group("CONSTRAINT_CHANGED") == "constraint"

    drifts = [
        {"type": "TABLE_MISSING", "table": "A", "column": None, "detail": "d1", "db_value": None, "model_value": "A"},
        {"type": "COLUMN_EXTRA", "table": "B", "column": "C", "detail": "d2", "db_value": "C", "model_value": None},
        {"type": "FK_CHANGED", "table": "B", "column": "C", "detail": "d3", "db_value": "x", "model_value": "y"},
    ]
    assert len(page.filter_drifts(drifts, "all")) == 3
    assert len(page.filter_drifts(drifts, "table")) == 1
    assert len(page.filter_drifts(drifts, "column")) == 1
    assert len(page.filter_drifts(drifts, "relationship")) == 1
    assert page.filter_drifts(drifts, "index") == []


def test_drift_report_text():
    """Report text: từng drift kèm DB vs Model, đủ để gửi cho AI/task."""
    import app.ui.pages.data_model as page

    drifts = [
        {
            "type": "COLUMN_EXTRA",
            "table": "RECON_RUN",
            "column": "EXTRA_COL",
            "detail": "Cột EXTRA_COL có trong database nhưng không có trong model.",
            "db_value": "EXTRA_COL",
            "model_value": None,
        },
        {
            "type": "TYPE_CHANGED",
            "table": "RECON_RUN",
            "column": "ID",
            "detail": "Kiểu dữ liệu khác.",
            "db_value": "BIGINT",
            "model_value": "INTEGER",
        },
    ]
    text = page.drift_report_text(drifts)
    assert "Schema drift" in text
    assert "COLUMN_EXTRA" in text and "RECON_RUN.EXTRA_COL" in text
    assert "DB: EXTRA_COL" in text
    assert "Model: —" in text
    assert "TYPE_CHANGED" in text
    assert "DB: BIGINT" in text and "Model: INTEGER" in text
    assert page.drift_report_text([]) == "Schema đồng bộ, không có drift."


def test_render_drift_list():
    """Drift list: marker theo loại, DB vs Model, empty khi đồng bộ."""
    import app.ui.pages.data_model as page

    drifts = [
        {
            "type": "COLUMN_EXTRA",
            "table": "RECON_RUN",
            "column": "EXTRA_COL",
            "detail": "d",
            "db_value": "EXTRA_COL",
            "model_value": None,
        },
        {
            "type": "TYPE_CHANGED",
            "table": "RECON_RUN",
            "column": "ID",
            "detail": "d",
            "db_value": "BIGINT",
            "model_value": "INTEGER",
        },
        {
            "type": "FK_CHANGED",
            "table": "RECON_RUN",
            "column": "FILE_ID",
            "detail": "d",
            "db_value": "a",
            "model_value": "b",
        },
    ]
    node = page.render_drift_list(drifts)
    text = str(node)
    assert "RECON_RUN.EXTRA_COL" in text
    assert "DB: EXTRA_COL" in text
    assert "Model: INTEGER" in text
    assert "3 drift" in text
    assert "Schema đồng bộ, không có drift." in str(page.render_drift_list([]))


def test_handle_history_open(monkeypatch):
    """Nút Lịch sử thay đổi mở drawer + reset filter về mặc định."""
    import dash

    import app.ui.pages.data_model as page

    opened, search, change_type, hist = page.handle_history_open(
        1, {"query": "x", "change_type": "COLUMN_ADDED", "table": "RECON_RUN"}
    )
    assert opened is True
    assert search == ""
    assert change_type == "all"
    assert hist == {"query": "", "change_type": "all", "table": None}

    with pytest.raises(dash.exceptions.PreventUpdate):
        page.handle_history_open(0, None)


def test_handle_history_timeline(dm_manifest):
    """Timeline render theo store + search/type trong drawer."""
    import app.ui.pages.data_model as page

    node = page.handle_history_timeline(
        dm_manifest,
        {"query": "", "change_type": "COLUMN_ADDED", "table": "RECON_USER_ROLE"},
        "",
        "COLUMN_ADDED",
    )
    assert "RECON_USER_ROLE.ROLE_ID" in str(node)
    node2 = page.handle_history_timeline(dm_manifest, None, "0006", "all")
    assert "RECON_RUN.BATCH_RUN_ID" in str(node2)
    assert page.handle_history_timeline(None, None, "", "all") is not None


def test_handle_drift_open(monkeypatch):
    """Nút Xem khác biệt mở drift drawer; không bấm thì PreventUpdate."""
    import dash

    import app.ui.pages.data_model as page

    assert page.handle_drift_open(1) is True
    with pytest.raises(dash.exceptions.PreventUpdate):
        page.handle_drift_open(0)


def test_handle_drift_list_and_copy(dm_manifest):
    """Drift list theo filter; copy report trả đúng text theo filter."""
    import app.ui.pages.data_model as page

    manifest_data = dict(dm_manifest)
    manifest_data["drift"] = {
        "status": "DRIFT",
        "drifts": [
            {
                "type": "COLUMN_EXTRA",
                "table": "RECON_RUN",
                "column": "EXTRA_COL",
                "detail": "d",
                "db_value": "EXTRA_COL",
                "model_value": None,
            },
            {
                "type": "TABLE_MISSING",
                "table": "RECON_X",
                "column": None,
                "detail": "d",
                "db_value": None,
                "model_value": "RECON_X",
            },
        ],
    }
    node = page.handle_drift_list(manifest_data, "column")
    assert "RECON_RUN.EXTRA_COL" in str(node)
    assert "RECON_X" not in str(node)
    assert page.handle_drift_list(None, "all") is not None

    text = page.handle_drift_copy(manifest_data, "all")
    assert "COLUMN_EXTRA" in text and "TABLE_MISSING" in text
    text_col = page.handle_drift_copy(manifest_data, "column")
    assert "COLUMN_EXTRA" in text_col and "TABLE_MISSING" not in text_col
    assert page.handle_drift_copy(None, "all") == "Schema đồng bộ, không có drift."


def test_handle_rel_nav(monkeypatch):
    """Nút Source/Target table trong relationship detail chọn table đó + URL."""
    import json

    import dash

    import app.ui.pages.data_model as page

    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(
            triggered=[
                {
                    "prop_id": json.dumps({"type": "dm-rel-nav", "table": "RECON_USER"}) + ".n_clicks",
                    "value": 1,
                }
            ]
        ),
    )
    selection, href = page.handle_rel_nav([1], {"kind": "relationship"}, {"mode": "relations"})
    assert selection == {"kind": "table", "table": "RECON_USER"}
    assert href == "/data-model?table=RECON_USER&domain=all&mode=relations"

    monkeypatch.setattr(
        "dash.callback_context",
        SimpleNamespace(triggered=[{"prop_id": "x.n_clicks", "value": 0}]),
    )
    selection2, href2 = page.handle_rel_nav([0], {"kind": None, "table": None}, {})
    assert selection2 == {"kind": None, "table": None}
    assert href2 is dash.no_update
