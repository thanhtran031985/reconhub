"""Tests cho Report Studio Center + Designer khung 3 panel — Bước 3 task 109 (test viết trước)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx, Role
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_data_source, recon_user
from app.engine.catalog import invalidate_catalog_cache


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
def rs_ui_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    invalidate_catalog_cache()
    db_file = tmp_path / "rs_ui.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    src_db = tmp_path / "rs_ui_src.db"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")
    from app.core.config import get_settings

    get_settings.cache_clear()
    engine = create_engine(db_url)
    metadata.create_all(engine)

    src_engine = create_engine(f"sqlite:///{src_db.as_posix()}")
    with src_engine.begin() as sconn:
        sconn.execute(
            text(
                "CREATE TABLE DIM_CUSTOMER ("
                "CUSTOMER_ID INTEGER PRIMARY KEY, CUSTOMER_NAME TEXT NOT NULL, "
                "SEGMENT TEXT NOT NULL, ORG_CODE TEXT NOT NULL)"
            )
        )
        sconn.execute(text("CREATE TABLE DIM_DATE (CAL_DATE DATE NOT NULL, MONTH_LABEL TEXT NOT NULL)"))
        sconn.execute(
            text(
                "CREATE TABLE FACT_SALES ("
                "SALE_ID INTEGER PRIMARY KEY, CUSTOMER_ID INTEGER NOT NULL, "
                "SALE_DAY DATE NOT NULL, REVENUE NUMERIC NOT NULL, QTY INTEGER NOT NULL, "
                "FOREIGN KEY (CUSTOMER_ID) REFERENCES DIM_CUSTOMER(CUSTOMER_ID))"
            )
        )
        sconn.execute(text("INSERT INTO DIM_CUSTOMER VALUES (1, 'Cong ty A', 'VIP', 'BDP'), (2, 'Cong ty B', 'STD', 'HCM')"))
        sconn.execute(text("INSERT INTO DIM_DATE VALUES ('2026-01-01', '2026-01'), ('2026-02-01', '2026-02')"))
        sconn.execute(
            text(
                "INSERT INTO FACT_SALES VALUES "
                "(1, 1, '2026-01-01', 500000, 5), (2, 2, '2026-01-01', 200000, 2), "
                "(3, 1, '2026-02-01', 300000, 3)"
            )
        )

    import app.services.report_studio  # noqa: F401
    import app.services.semantic_model  # noqa: F401

    for mod_path in (
        "app.db.engine",
        "app.services.perm",
        "app.services.menu_sync",
        "app.engine.catalog",
        "app.services.semantic_model",
        "app.services.semantic_model_validate",
        "app.services.semantic_query",
        "app.services.report_source",
        "app.services.report_studio",
        "app.services.report_template",
        "app.services.report",
        "app.services.report_param",
    ):
        monkeypatch.setattr(f"{mod_path}.get_recon_engine", lambda: engine)

    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from app.services.semantic_query import invalidate_semantic_query_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, uname in [(1, "admin"), (2, "owner"), (3, "viewer")]:
            conn.execute(
                recon_user.insert().values(
                    ID=uid,
                    USERNAME=uname,
                    FULL_NAME=uname.title(),
                    PASSWORD_HASH="hash",
                    IS_ACTIVE="Y",
                    MUST_CHANGE_PW="N",
                    FAILED_COUNT=0,
                    SESSION_VERSION=1,
                    CREATED_BY="system",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                    ROW_VERSION=1,
                )
            )
        res_ds = conn.execute(
            recon_data_source.insert().values(
                NAME="STAR_SQLITE",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="SQLITE",
                FILE_PATH=str(src_db),
                USERNAME="ro_user",
                PASSWORD_ENC=encrypt_secret("top_secret_pw"),
                CALL_TIMEOUT_S=30,
                MAX_ROWS=1000000,
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = int(res_ds.inserted_primary_key[0])

    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["TEMPLATE_OWNER"], 3: ["VIEWER"]})
    clear_perm_cache()
    invalidate_semantic_query_cache()

    ver_id, bundle = _build_published_model(_owner(), ds_id)
    created = _create_studio_report(_owner(), ver_id)
    # Một model chỉ có DRAFT (không ACTIVE) để kiểm tra modal tạo chỉ liệt kê ACTIVE.
    from app.services.semantic_model import create_model

    draft_only = create_model(_owner(), {"code": "M_DRAFT", "name": "Nháp", "data_source_id": ds_id})
    assert draft_only.ok
    try:
        yield engine, ds_id, ver_id, bundle, created
    finally:
        src_engine.dispose()
        engine.dispose()


def _build_published_model(owner_ctx, ds_id, code="M_SALES", hide_field=None):
    from app.services.semantic_model import (
        add_table_to_draft,
        create_model,
        get_model_version_detail,
        update_field_props,
        update_table_props,
        upsert_measure,
    )
    from app.services.semantic_model_validate import publish_model_version, upsert_relationship

    created = create_model(owner_ctx, {"code": code, "name": "Sales Q", "data_source_id": ds_id})
    assert created.ok, created.message
    ver_id = created.data["draft_version"]["id"]
    tables = {}
    for obj in ("FACT_SALES", "DIM_CUSTOMER", "DIM_DATE"):
        res = add_table_to_draft(owner_ctx, ver_id, {"source_object": obj})
        assert res.ok, res.message
        tables[obj] = res.data
    fact = tables["FACT_SALES"]
    assert update_table_props(
        owner_ctx,
        fact["id"],
        {"table_role": "FACT", "grain_desc": "Theo dòng bán", "grain_keys": ["SALE_ID"]},
    ).ok
    for obj in ("DIM_CUSTOMER", "DIM_DATE"):
        assert update_table_props(owner_ctx, tables[obj]["id"], {"table_role": "DIMENSION"}).ok
    for name, from_tid, from_col, to_tid, to_col in [
        ("SALES_CUSTOMER", fact["id"], "CUSTOMER_ID", tables["DIM_CUSTOMER"]["id"], "CUSTOMER_ID"),
        ("SALES_DATE", fact["id"], "SALE_DAY", tables["DIM_DATE"]["id"], "CAL_DATE"),
    ]:
        res = upsert_relationship(
            owner_ctx,
            ver_id,
            {
                "name": name,
                "from_table_id": from_tid,
                "from_column": from_col,
                "to_table_id": to_tid,
                "to_column": to_col,
                "cardinality": "MANY_TO_ONE",
                "join_type": "LEFT_OUTER",
            },
        )
        assert res.ok, res.message
    fact_cols = {f["source_column"]: f for f in fact["fields"]}
    m = upsert_measure(
        owner_ctx,
        ver_id,
        {
            "code": "REV_SUM",
            "name": "Tong doanh thu",
            "table_id": fact["id"],
            "measure_type": "SIMPLE",
            "base_field_id": fact_cols["REVENUE"]["id"],
            "aggregation": "SUM",
        },
    )
    assert m.ok, m.message
    if hide_field is not None:
        alias, col = hide_field
        fld = next(f for f in tables[alias]["fields"] if f["source_column"] == col)
        assert update_field_props(owner_ctx, fld["id"], {"is_visible": False}).ok
    pub = publish_model_version(owner_ctx, ver_id, {"change_note": "Phat hanh v1"})
    assert pub.ok, pub.message
    detail = get_model_version_detail(owner_ctx, ver_id)
    assert detail.ok, detail.message
    return ver_id, detail.data


def _create_studio_report(owner_ctx, ver_id, code="RPT_SALES"):
    from app.services.report_studio import create_studio_report

    res = create_studio_report(
        owner_ctx,
        {"code": code, "name": "Báo cáo doanh thu", "model_version_id": ver_id},
    )
    assert res.ok, res.message
    return res.data


def test_center_breadcrumbs_and_permission_gate(rs_ui_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.ui.pages.report_studio_center as page
    from app.ui.layout.shell import build_breadcrumbs

    assert page.MENU_CODE == "report_studio"

    bc = build_breadcrumbs("/report-studio")
    assert any(item["label"] == "Report Studio" for item in bc)
    bc_detail = build_breadcrumbs("/report-studio/12")
    assert any(item.get("href") == "/report-studio" for item in bc_detail)

    monkeypatch.setattr(page, "get_current_ctx", lambda: None)
    assert "/login" in _dump(page.layout())
    monkeypatch.setattr(page, "get_current_ctx", _viewer)
    assert "/forbidden" in _dump(page.layout())
    monkeypatch.setattr(page, "get_current_ctx", _owner)
    ok_dump = _dump(page.layout())
    assert "Report Studio" in ok_dump
    assert "Tạo báo cáo" in ok_dump
    assert "RPT_SALES" in ok_dump


def test_center_four_states_and_filter_helpers(rs_ui_env) -> None:
    import app.ui.pages.report_studio_center as page
    from app.services.report_studio import list_studio_reports

    reports = list_studio_reports(_owner()).data

    sk_dump = _dump(page.render_studio_reports_body(rows=[], loading=True, has_filter=False, error_msg=None))
    assert "Skeleton" in sk_dump
    empty_raw = _dump(page.render_studio_reports_body(rows=[], loading=False, has_filter=False, error_msg=None))
    assert "Chưa có báo cáo Studio" in empty_raw
    empty_flt = _dump(page.render_studio_reports_body(rows=[], loading=False, has_filter=True, error_msg=None))
    assert "Xóa bộ lọc" in empty_flt
    err_dump = _dump(
        page.render_studio_reports_body(
            rows=page.studio_reports_to_grid_rows(reports),
            loading=False,
            has_filter=False,
            error_msg="Mất kết nối tạm thời",
        )
    )
    assert "Mất kết nối tạm thời" in err_dump
    assert "Thử lại" in err_dump
    assert "RPT_SALES" in err_dump

    filtered_q = page.filter_studio_reports(reports, query="doanh thu")
    assert [r["code"] for r in filtered_q] == ["RPT_SALES"]
    filtered_none = page.filter_studio_reports(reports, query="không có")
    assert filtered_none == []
    filtered_status = page.filter_studio_reports(reports, status="ACTIVE")
    assert filtered_status == []
    filtered_draft = page.filter_studio_reports(reports, status="DRAFT")
    assert len(filtered_draft) == 1


def test_center_create_modal_lists_only_active_models(rs_ui_env) -> None:
    import app.ui.pages.report_studio_center as page

    opts = page.studio_model_options(_owner())
    codes = [o["label"] for o in opts]
    assert any("M_SALES" in c for c in codes)
    assert not any("M_DRAFT" in c for c in codes)
    # Modal tạo báo cáo chỉ liệt kê model ACTIVE.
    modal_dump = _dump(page.render_create_report_modal(_owner()))
    assert "M_SALES" in modal_dump
    assert "M_DRAFT" not in modal_dump


def test_center_submit_create_and_open_flows(rs_ui_env) -> None:
    import app.ui.pages.report_studio_center as page
    from app.services.report_studio import list_studio_reports

    _, _, ver_id, _, _ = rs_ui_env
    new_id, err, rows, toast = page.submit_create_studio_report(
        _owner(), code="RPT_NEW", name="Báo cáo mới", model_version_id=ver_id
    )
    assert err is None and new_id is not None
    assert toast is not None
    assert any(r["code"] == "RPT_NEW" for r in (rows or []))

    dup_id, dup_err, _, _ = page.submit_create_studio_report(
        _owner(), code="RPT_SALES", name="Trùng", model_version_id=ver_id
    )
    assert dup_id is None and dup_err is not None

    denied_id, denied_err, _, _ = page.submit_create_studio_report(
        _viewer(), code="RPT_V", name="Viewer", model_version_id=ver_id
    )
    assert denied_id is None and denied_err is not None

    listed = list_studio_reports(_owner()).data
    assert {r["code"] for r in listed} == {"RPT_SALES", "RPT_NEW"}


def test_designer_layout_three_panels_and_field_search(rs_ui_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.ui.pages.report_studio as studio
    from app.services.report_studio import open_or_create_studio_draft

    _, _, _, _, created = rs_ui_env
    report_id = created["report"]["id"]

    monkeypatch.setattr(studio, "get_current_ctx", lambda: None)
    assert "/login" in _dump(studio.layout(report_id=str(report_id)))
    monkeypatch.setattr(studio, "get_current_ctx", _viewer)
    assert "/forbidden" in _dump(studio.layout(report_id=str(report_id)))

    monkeypatch.setattr(studio, "get_current_ctx", _owner)
    root_dump = _dump(studio.layout(report_id=str(report_id)))
    assert "rs-fields-panel" in root_dump
    assert "rs-canvas" in root_dump
    assert "rs-settings-panel" in root_dump
    assert "rs-status-bar" in root_dump
    assert "Trường & Chỉ số" in root_dump
    assert "Xem trước" in root_dump
    assert "Kiểm tra" in root_dump
    assert "Lưu nháp" in root_dump
    assert "Phát hành" in root_dump

    # Search in-memory trên bundle đã tải, không query DB.
    opened = open_or_create_studio_draft(_owner(), report_id)
    assert opened.ok
    bundle = opened.data["model"]
    panel = studio.render_fields_panel(bundle, query="CUSTOMER_NAME")
    panel_dump = _dump(panel)
    assert "CUSTOMER_NAME" in panel_dump
    assert "REVENUE" not in panel_dump
    panel_all = studio.render_fields_panel(bundle, query="")
    assert "CUSTOMER_NAME" in _dump(panel_all)
    assert "REVENUE" in _dump(panel_all)


def test_designer_fields_panel_hides_hidden_and_groups(rs_ui_env) -> None:
    import app.ui.pages.report_studio as studio

    _, ds_id, _, _, _ = rs_ui_env
    _, bundle_hidden = _build_published_model(_owner(), ds_id, code="M_HIDDEN", hide_field=("DIM_CUSTOMER", "SEGMENT"))
    panel = studio.render_fields_panel(bundle_hidden, query="")
    panel_dump = _dump(panel)
    # Field SEGMENT đã ẩn trong model -> không hiện ở panel.
    assert "SEGMENT" not in panel_dump
    assert "CUSTOMER_NAME" in panel_dump
    # Nhóm Dimensions / Measures hiện đủ.
    assert "Dimensions" in panel_dump
    assert "Measures" in panel_dump
    assert "REV_SUM" in panel_dump
    # Search không khớp -> trạng thái trống, không lộ field ẩn.
    empty_panel = studio.render_fields_panel(bundle_hidden, query="zzz-khong-co")
    assert "Không tìm thấy trường" in _dump(empty_panel)
    assert "SEGMENT" not in _dump(empty_panel)


def test_designer_readonly_active_and_invalid_report(rs_ui_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.ui.pages.report_studio as studio
    from app.services.report_studio import (
        open_or_create_studio_draft,
        publish_studio_report,
        save_studio_draft,
        validate_studio_report,
    )

    _, _, _, bundle, created = rs_ui_env
    report_id = created["report"]["id"]
    opened = open_or_create_studio_draft(_owner(), report_id)
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    assert save_studio_draft(_owner(), vid, {"row_version": rv, "visuals": []}).ok
    assert validate_studio_report(_owner(), vid).ok
    assert publish_studio_report(_owner(), vid, {"change_note": "v1"}).ok

    monkeypatch.setattr(studio, "get_current_ctx", _owner)
    # Bản ACTIVE -> chỉ đọc, có nút tạo bản nháp mới.
    active_dump = _dump(studio.layout(report_id=str(report_id)))
    assert "chỉ đọc" in active_dump.lower() or "Chỉ đọc" in active_dump
    assert "Tạo bản nháp mới" in active_dump
    # Report không tồn tại -> trạng thái lỗi.
    bad_dump = _dump(studio.layout(report_id="999999"))
    assert "Không mở được Report Studio" in bad_dump


# ─── Bước 4: Canvas 12 cột, 5 visual types, Data Wells, Filters & Preview ───


def _ui_field_id(bundle, alias, source_column):
    for t in bundle.get("tables") or []:
        if str(t.get("alias")) == alias:
            for f in t.get("fields") or []:
                if str(f.get("source_column")) == source_column:
                    return int(f["id"])
    raise AssertionError(f"Không thấy field {alias}.{source_column}")


def _ui_measure_id(bundle, code):
    for m in bundle.get("measures") or []:
        if str(m.get("code")) == code:
            return int(m["id"])
    raise AssertionError(f"Không thấy measure {code}")


def _ui_well(role, field_id=None, measure_id=None, agg="NONE", **kw):
    d = {
        "well_role": role,
        "field_id": field_id,
        "measure_id": measure_id,
        "aggregation": agg,
        "date_part": None,
        "alias": None,
        "label_override": None,
        "format_mask": None,
        "sort_direction": None,
        "display_order": 10,
    }
    d.update(kw)
    return d


def _ui_visual(code, vtype, fields, **kw):
    d = {
        "code": code,
        "title": kw.pop("title", code),
        "visual_type": vtype,
        "display_order": kw.pop("display_order", 10),
        "grid_span": kw.pop("grid_span", 12),
        "height_size": kw.pop("height_size", "M"),
        "config": kw.pop("config", {}),
        "fields": fields,
    }
    d.update(kw)
    return d


def _ui_preview(visual_type, columns, rows, **kw):
    d = {
        "visual_code": "V_001",
        "visual_type": visual_type,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": False,
        "warning_message": None,
        "request_seq": 1,
        "elapsed_ms": 12,
    }
    d.update(kw)
    return d


def _ui_detail(bundle, created, visuals):
    return {
        "report": created["report"],
        "version": created["version"],
        "model": bundle,
        "visuals": visuals,
    }


def _ui_find_all(component, type_name):
    """Thu thập mọi component có tên lớp type_name trong cây Dash."""
    found = []
    stack = [component]
    while stack:
        node = stack.pop()
        if type(node).__name__ == type_name:
            found.append(node)
        children = getattr(node, "children", None)
        if isinstance(children, (list, tuple)):
            stack.extend(children)
        elif children is not None:
            stack.append(children)
    return found


def test_semantic_visuals_render_all_five_types(rs_ui_env) -> None:
    from app.ui.components.semantic_visuals import render_semantic_visual

    _, _, _, bundle, _ = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    seg = _ui_field_id(bundle, "DIM_CUSTOMER", "SEGMENT")
    rev = _ui_field_id(bundle, "FACT_SALES", "REVENUE")
    rev_sum = _ui_measure_id(bundle, "REV_SUM")
    cols = [
        {"name": "CUSTOMER_NAME", "label": "CUSTOMER_NAME", "data_type": "STRING"},
        {"name": "REV_SUM", "label": "REV_SUM", "data_type": "NUMBER"},
    ]
    rows = [
        {"CUSTOMER_NAME": "Cong ty A", "REV_SUM": 800000},
        {"CUSTOMER_NAME": "Cong ty B", "REV_SUM": 200000},
    ]

    table_vis = _ui_visual("V_001", "TABLE", [_ui_well("X", cust), _ui_well("Y", rev_sum)])
    table_node = render_semantic_visual(table_vis, _ui_preview("TABLE", cols, rows))
    grids = _ui_find_all(table_node, "AgGrid")
    assert len(grids) == 1
    assert [c["field"] for c in grids[0].columnDefs] == ["CUSTOMER_NAME", "REV_SUM"]
    assert grids[0].rowData == rows

    matrix_vis = _ui_visual(
        "V_002",
        "MATRIX",
        [_ui_well("ROWS", cust), _ui_well("COLUMNS", seg), _ui_well("VALUES", rev_sum)],
    )
    matrix_prev = _ui_preview(
        "MATRIX",
        cols,
        rows,
        visual_code="V_002",
        pivot={
            "row_headers": ["Cong ty A", "Cong ty B"],
            "col_headers": ["VIP", "STD"],
            "cells": [[800000, None], [None, 200000]],
            "truncated": False,
        },
    )
    matrix_node = render_semantic_visual(matrix_vis, matrix_prev)
    matrix_grids = _ui_find_all(matrix_node, "AgGrid")
    assert len(matrix_grids) == 1
    assert [c["field"] for c in matrix_grids[0].columnDefs] == ["", "VIP", "STD"]
    assert matrix_grids[0].rowData[0]["VIP"] == 800000

    kpi_vis = _ui_visual("V_003", "KPI", [_ui_well("VALUE", rev_sum)])
    kpi_prev = _ui_preview(
        "KPI",
        [{"name": "REV_SUM", "label": "REV_SUM", "data_type": "NUMBER"}],
        [{"REV_SUM": 1000000}],
        visual_code="V_003",
    )
    assert "1,000,000" in _dump(render_semantic_visual(kpi_vis, kpi_prev))

    bar_vis = _ui_visual("V_004", "BAR", [_ui_well("X", cust), _ui_well("Y", rev, agg="SUM")])
    bar_node = render_semantic_visual(bar_vis, _ui_preview("BAR", cols, rows, visual_code="V_004"))
    graphs = _ui_find_all(bar_node, "Graph")
    assert len(graphs) == 1
    fig = graphs[0].figure
    assert list(fig["data"][0]["x"]) == ["Cong ty A", "Cong ty B"]
    assert list(fig["data"][0]["y"]) == [800000, 200000]
    assert fig["data"][0]["type"] == "bar"
    assert graphs[0].config.get("displayModeBar") is False

    line_vis = _ui_visual("V_005", "LINE", [_ui_well("X", cust), _ui_well("Y", rev, agg="SUM")])
    line_node = render_semantic_visual(line_vis, _ui_preview("LINE", cols, rows, visual_code="V_005"))
    line_graphs = _ui_find_all(line_node, "Graph")
    assert len(line_graphs) == 1
    assert line_graphs[0].figure["data"][0]["type"] == "scatter"
    assert line_graphs[0].figure["data"][0]["mode"] == "lines+markers"


def test_semantic_visual_states(rs_ui_env) -> None:
    from app.ui.components.semantic_visuals import render_semantic_visual

    _, _, _, bundle, _ = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    rev_sum = _ui_measure_id(bundle, "REV_SUM")
    vis = _ui_visual("V_001", "TABLE", [_ui_well("X", cust), _ui_well("Y", rev_sum)])

    loading_dump = _dump(render_semantic_visual(vis, None, state="loading"))
    assert "Skeleton" in loading_dump

    empty_dump = _dump(render_semantic_visual(vis, _ui_preview("TABLE", [], []), state="empty"))
    assert "Chưa có dữ liệu" in empty_dump

    err_dump = _dump(
        render_semantic_visual(vis, None, state="error", error_message="Lỗi kết nối nguồn")
    )
    assert "Lỗi kết nối nguồn" in err_dump
    assert "rs-visual-retry" in err_dump

    cols = [{"name": "REV_SUM", "label": "REV_SUM", "data_type": "NUMBER"}]
    trunc_dump = _dump(
        render_semantic_visual(
            vis,
            _ui_preview("TABLE", cols, [{"REV_SUM": 1}], truncated=True),
        )
    )
    assert "chỉ hiển thị" in trunc_dump.lower()


def test_matrix_truncation_warning(rs_ui_env) -> None:
    from app.ui.components.semantic_visuals import render_semantic_visual

    _, _, _, bundle, _ = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    seg = _ui_field_id(bundle, "DIM_CUSTOMER", "SEGMENT")
    rev_sum = _ui_measure_id(bundle, "REV_SUM")
    vis = _ui_visual(
        "V_002",
        "MATRIX",
        [_ui_well("ROWS", cust), _ui_well("COLUMNS", seg), _ui_well("VALUES", rev_sum)],
    )
    prev = _ui_preview(
        "MATRIX",
        [{"name": "CUSTOMER_NAME", "label": "CUSTOMER_NAME", "data_type": "STRING"}],
        [{"CUSTOMER_NAME": "Cong ty A"}],
        visual_code="V_002",
        truncated=True,
        pivot={
            "row_headers": ["Cong ty A"],
            "col_headers": ["VIP"],
            "cells": [[800000]],
            "truncated": True,
        },
    )
    dump = _dump(render_semantic_visual(vis, prev))
    assert "giới hạn" in dump.lower() or "chỉ hiển thị" in dump.lower()


def test_invalid_drop_rejected_keeps_visual(rs_ui_env) -> None:
    import app.ui.pages.report_studio as studio

    _, _, _, bundle, created = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    seg = _ui_field_id(bundle, "DIM_CUSTOMER", "SEGMENT")
    rev = _ui_field_id(bundle, "FACT_SALES", "REVENUE")
    rev_sum = _ui_measure_id(bundle, "REV_SUM")
    table_vis = _ui_visual("V_001", "TABLE", [_ui_well("X", cust), _ui_well("Y", rev_sum)])
    matrix_vis = _ui_visual(
        "V_002",
        "MATRIX",
        [_ui_well("ROWS", cust), _ui_well("COLUMNS", seg), _ui_well("VALUES", rev_sum)],
    )
    detail = _ui_detail(bundle, created, [table_vis, matrix_vis])
    before = _dump(detail)

    # Measure không đặt được ở well dimension X.
    _, err = studio.apply_field_drop(
        detail, kind="measure", field_id=rev_sum, visual_code="V_001", well_role="X"
    )
    assert err and "Measure" in err
    assert _dump(detail) == before

    # Field không đặt được ở well không thuộc loại visual (ROWS ở TABLE).
    _, err = studio.apply_field_drop(
        detail, kind="field", field_id=seg, visual_code="V_001", well_role="ROWS"
    )
    assert err and "ROWS" in err
    assert _dump(detail) == before

    # Well đơn (MATRIX ROWS) đã có field -> từ chối field thứ hai.
    _, err = studio.apply_field_drop(
        detail, kind="field", field_id=seg, visual_code="V_002", well_role="ROWS"
    )
    assert err and "chỉ chứa một" in err
    assert _dump(detail) == before

    # Trùng field trong cùng well -> từ chối.
    _, err = studio.apply_field_drop(
        detail, kind="field", field_id=cust, visual_code="V_001", well_role="X"
    )
    assert err and "đã có" in err
    assert _dump(detail) == before

    # Visual không tồn tại -> từ chối.
    _, err = studio.apply_field_drop(
        detail, kind="field", field_id=cust, visual_code="V_999", well_role="X"
    )
    assert err
    assert _dump(detail) == before

    # Hợp lệ: measure vào Y giữ aggregation NONE.
    new_detail, err = studio.apply_field_drop(
        detail, kind="measure", field_id=rev_sum, visual_code="V_001", well_role="Y"
    )
    assert err is None
    added = [f for f in new_detail["visuals"][0]["fields"] if f.get("measure_id") == rev_sum]
    assert added and added[0]["aggregation"] == "NONE"

    # Hợp lệ: field NUMBER vào Y tự lấy aggregation SUM.
    new_detail, err = studio.apply_field_drop(
        detail, kind="field", field_id=rev, visual_code="V_001", well_role="Y"
    )
    assert err is None
    added = [f for f in new_detail["visuals"][0]["fields"] if f.get("field_id") == rev]
    assert added and added[0]["aggregation"] == "SUM"


def test_change_visual_type_confirm_lists_dropped_fields(rs_ui_env) -> None:
    import app.ui.pages.report_studio as studio

    _, _, _, bundle, _ = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    seg = _ui_field_id(bundle, "DIM_CUSTOMER", "SEGMENT")
    rev = _ui_field_id(bundle, "FACT_SALES", "REVENUE")
    rev_sum = _ui_measure_id(bundle, "REV_SUM")

    table_vis = _ui_visual(
        "V_001", "TABLE", [_ui_well("X", cust), _ui_well("Y", rev, agg="SUM")]
    )
    kept, dropped = studio.remap_visual_fields(table_vis, "KPI", bundle)
    assert [f["well_role"] for f in kept] == ["VALUE"]
    assert dropped == ["CUSTOMER_NAME"]

    kept, dropped = studio.remap_visual_fields(table_vis, "MATRIX", bundle)
    assert dropped == []
    assert [f["well_role"] for f in kept] == ["ROWS", "VALUES"]

    bar_vis = _ui_visual(
        "V_004",
        "BAR",
        [_ui_well("X", cust), _ui_well("Y", rev, agg="SUM"), _ui_well("SERIES", seg)],
    )
    kept, dropped = studio.remap_visual_fields(bar_vis, "TABLE", bundle)
    assert dropped == ["SEGMENT"]
    assert [f["well_role"] for f in kept] == ["X", "Y"]

    two_x = _ui_visual(
        "V_001",
        "TABLE",
        [_ui_well("X", cust), _ui_well("X", seg), _ui_well("Y", rev, agg="SUM")],
    )
    kept, dropped = studio.remap_visual_fields(two_x, "MATRIX", bundle)
    assert dropped == ["SEGMENT"]
    assert [f["well_role"] for f in kept] == ["ROWS", "VALUES"]

    kpi_vis = _ui_visual("V_003", "KPI", [_ui_well("VALUE", rev_sum)])
    kept, dropped = studio.remap_visual_fields(kpi_vis, "BAR", bundle)
    assert dropped == []
    assert [f["well_role"] for f in kept] == ["Y"]


def test_stale_preview_response_ignored() -> None:
    import app.ui.pages.report_studio as studio

    store: dict[str, Any] = {"seq": 5, "results": {}}
    result = {"rows": [{"REV_SUM": 1}], "row_count": 1}
    new_store, applied = studio.apply_preview_result(store, "V_001", result, request_seq=3)
    assert applied is False
    assert new_store == store

    new_store, applied = studio.apply_preview_result(store, "V_001", result, request_seq=5)
    assert applied is True
    assert new_store["results"]["V_001"] == result
    assert new_store["seq"] == 5

    new_store, applied = studio.apply_preview_result(new_store, "V_001", result, request_seq=6)
    assert applied is True
    assert new_store["seq"] == 6


def test_visual_move_duplicate_delete(rs_ui_env) -> None:
    import app.ui.pages.report_studio as studio

    _, _, _, bundle, created = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    rev_sum = _ui_measure_id(bundle, "REV_SUM")
    visuals = [
        _ui_visual("V_001", "TABLE", [_ui_well("X", cust)], display_order=10),
        _ui_visual("V_002", "BAR", [_ui_well("X", cust), _ui_well("Y", rev_sum)], display_order=20),
        _ui_visual("V_003", "KPI", [_ui_well("VALUE", rev_sum)], display_order=30),
    ]
    detail = _ui_detail(bundle, created, visuals)

    moved, ok = studio.move_visual(detail, "V_002", "up")
    assert ok is True
    assert [v["code"] for v in sorted(moved["visuals"], key=lambda v: v["display_order"])] == [
        "V_002",
        "V_001",
        "V_003",
    ]
    _, ok = studio.move_visual(detail, "V_001", "up")
    assert ok is False
    _, ok = studio.move_visual(detail, "V_003", "down")
    assert ok is False

    duped = studio.duplicate_visual(detail, "V_001")
    assert len(duped["visuals"]) == 4
    clone = next(v for v in duped["visuals"] if v["code"] == "V_004")
    assert clone["title"].endswith("(bản sao)")
    assert clone["fields"] == visuals[0]["fields"]
    assert clone["display_order"] == 40

    deleted = studio.delete_visual(detail, "V_002")
    assert [v["code"] for v in deleted["visuals"]] == ["V_001", "V_003"]


def test_settings_panel_controls(rs_ui_env) -> None:
    import app.ui.pages.report_studio as studio

    _, _, _, bundle, created = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    rev = _ui_field_id(bundle, "FACT_SALES", "REVENUE")
    vis = _ui_visual(
        "V_001",
        "TABLE",
        [_ui_well("X", cust), _ui_well("Y", rev, agg="SUM", sort_direction="DESC")],
    )
    detail = _ui_detail(bundle, created, [vis])
    dump = _dump(studio.render_settings_panel(detail, {"visual_code": "V_001"}))
    assert "rs-set-title" in dump
    assert "rs-set-type" in dump
    assert "rs-set-grid-span" in dump
    assert "rs-set-height-size" in dump
    assert "rs-well-agg" in dump
    assert "rs-well-sort" in dump
    assert "rs-well-format" in dump
    assert "SUM" in dump
    assert "Bộ lọc visual" in dump
    assert "rs-visual-delete-btn" in dump


def test_canvas_grid_spans_and_move_buttons(rs_ui_env) -> None:
    import app.ui.pages.report_studio as studio

    _, _, _, bundle, created = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    rev_sum = _ui_measure_id(bundle, "REV_SUM")
    visuals = [
        _ui_visual("V_001", "TABLE", [_ui_well("X", cust)], grid_span=6),
        _ui_visual("V_002", "KPI", [_ui_well("VALUE", rev_sum)], grid_span=6),
    ]
    detail = _ui_detail(bundle, created, visuals)
    canvas = studio.render_canvas_panel(detail)
    dump = _dump(canvas)
    assert "rs-visual-move-up" in dump
    assert "rs-visual-move-down" in dump
    assert "rs-visual-duplicate" in dump
    assert "rs-visual-delete" in dump
    assert "GridCol" in dump
    cols = _ui_find_all(canvas, "GridCol")
    assert sorted(c.span for c in cols) == [6, 6]


def _walk_components(node: Any) -> Any:
    """Đi bộ cây component Dash (children có thể là list/dict/component)."""
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk_components(child)
    elif children is not None:
        yield from _walk_components(children)


def test_canvas_action_buttons_not_inside_clickable_card(rs_ui_env) -> None:
    """Hồi quy race bubbling (Bước 6): nút lên/xuống/nhân bản/xóa KHÔNG
    được là con cháu của div clickable chọn visual.

    Trước fix, click nút Nhân bản/Xóa bubble lên n_clicks của card, bắn
    thêm handle_visual_select vẽ lại canvas từ store cũ — visual mới
    nhân bản biến mất khỏi canvas dù store đã có (status bar vẫn đếm
    đủ), xóa xong visual hiện lại.
    """
    import app.ui.pages.report_studio as studio

    _, _, _, bundle, created = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    rev_sum = _ui_measure_id(bundle, "REV_SUM")
    visuals = [
        _ui_visual("V_001", "TABLE", [_ui_well("X", cust), _ui_well("Y", rev_sum, kind="measure")]),
    ]
    detail = _ui_detail(bundle, created, visuals)
    canvas = studio.render_canvas_panel(detail)
    action_types = {"rs-visual-move-up", "rs-visual-move-down", "rs-visual-duplicate", "rs-visual-delete"}
    for node in _walk_components(canvas):
        node_id = getattr(node, "id", None)
        if isinstance(node_id, dict) and node_id.get("type") == "rs-visual-card":
            for desc in _walk_components(node):
                desc_id = getattr(desc, "id", None)
                assert not (
                    isinstance(desc_id, dict) and desc_id.get("type") in action_types
                ), f"Nút {desc_id} còn nằm trong div clickable của card"
            break
    else:
        raise AssertionError("Không tìm thấy div clickable rs-visual-card")
    # Nút action vẫn tồn tại trong canvas (chỉ tách ra ngoài div clickable).
    dump = _dump(canvas)
    for action in action_types:
        assert action in dump


def test_add_field_to_bar_line_selected(rs_ui_env) -> None:
    import app.ui.pages.report_studio as studio

    _, _, _, bundle, created = rs_ui_env
    cust = _ui_field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    seg = _ui_field_id(bundle, "DIM_CUSTOMER", "SEGMENT")
    rev = _ui_field_id(bundle, "FACT_SALES", "REVENUE")
    rev_sum = _ui_measure_id(bundle, "REV_SUM")
    bar_vis = _ui_visual("V_001", "BAR", [_ui_well("X", cust)])
    detail = _ui_detail(bundle, created, [bar_vis])
    selection = {"visual_code": "V_001"}

    new_detail, msg = studio.add_field_to_draft(detail, kind="measure", field_id=rev_sum, selection=selection)
    assert msg is not None
    assert len(new_detail["visuals"]) == 1
    assert any(f.get("measure_id") == rev_sum and f["well_role"] == "Y" for f in new_detail["visuals"][0]["fields"])

    matrix_vis = _ui_visual(
        "V_002",
        "MATRIX",
        [_ui_well("ROWS", cust), _ui_well("COLUMNS", seg), _ui_well("VALUES", rev_sum)],
    )
    detail2 = _ui_detail(bundle, created, [matrix_vis])
    new_detail2, _ = studio.add_field_to_draft(
        detail2, kind="field", field_id=rev, selection={"visual_code": "V_002"}
    )
    assert len(new_detail2["visuals"]) == 2
    assert new_detail2["visuals"][1]["visual_type"] == "TABLE"


def test_model_studio_report_studio_button_enabled() -> None:
    """Nút 'Report Studio' ở header Model Studio phải bật và mở /report-studio (task 109).

    Trước task 109 nút bị disabled với tooltip 'Khả dụng ở Task 109';
    nay Report Studio đã có nên nút phải bấm được (hồi quy: đỏ khi nút
    còn disabled hoặc không có link /report-studio).
    """
    from app.ui.pages.report_model_studio import render_studio_header

    bundle = {
        "model": {"name": "SALES_MODEL", "code": "SALES_MODEL", "active_version_no": 1},
        "version": {"version_no": 1, "status": "ACTIVE"},
    }
    # _dump() chỉ chuỗi hóa các component lồng nhau thành repr nên không
    # duyệt được cây — duyệt trực tiếp trên cây component sống.
    header = render_studio_header(bundle)

    found: dict[str, Any] = {}

    def walk(node: Any, parent_href: str | None = None) -> None:
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item, parent_href)
            return
        if not hasattr(node, "to_plotly_json"):
            return
        props = node.to_plotly_json().get("props") or {}
        href = str(props.get("href") or parent_href or "")
        if props.get("id") == "rms-open-report-studio-btn":
            found["button"] = props
            found["href"] = href
        walk(props.get("children"), href)

    walk(header)
    assert "button" in found, "Không tìm thấy nút rms-open-report-studio-btn trong header Model Studio."
    assert found["button"].get("disabled") is not True, "Nút Report Studio vẫn đang disabled."
    assert found.get("href") == "/report-studio", "Nút Report Studio phải mở /report-studio."
