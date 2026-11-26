"""Tests cho Model Studio (/report-models/<model_id>) — Bước 2 task 107 (test viết trước)."""

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
def studio_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "studio_test.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", echo=False)
    metadata.create_all(engine)
    for mod in (
        "app.engine.catalog",
        "app.services.menu_sync",
        "app.services.perm",
        "app.services.data_source",
        "app.services.semantic_model",
        "app.services.semantic_model_validate",
    ):
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)

    from app.engine.catalog import invalidate_catalog_cache
    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from app.services.semantic_model import add_table_to_draft, create_model

    invalidate_catalog_cache()
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
        conn.execute(
            text(
                "CREATE TABLE DIM_CUSTOMER ("
                "CUSTOMER_ID INTEGER PRIMARY KEY, "
                "CUSTOMER_NAME TEXT NOT NULL, "
                "REGION TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE FACT_SALES ("
                "SALES_ID INTEGER PRIMARY KEY, "
                "CUSTOMER_ID INTEGER NOT NULL REFERENCES DIM_CUSTOMER(CUSTOMER_ID), "
                "TRANS_DATE DATE NOT NULL, "
                "NOTE_TXT TEXT, "
                "AMOUNT NUMERIC NOT NULL)"
            )
        )
        conn.execute(text("CREATE VIEW V_CUSTOMER_ACTIVE AS SELECT CUSTOMER_ID, CUSTOMER_NAME FROM DIM_CUSTOMER"))
        conn.execute(text("INSERT INTO DIM_CUSTOMER VALUES (1, 'Cong ty A', 'HN'), (2, 'Cong ty B', 'HCM')"))
        conn.execute(
            text(
                "INSERT INTO FACT_SALES VALUES "
                "(101, 1, '2026-11-01', 'Note 1', 150000), "
                "(102, 2, '2026-11-02', 'Note 2', 250000)"
            )
        )
        ds_res = conn.execute(
            recon_data_source.insert().values(
                NAME="SRC_SQLITE",
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

    model_res = create_model(
        _owner(),
        {"code": "DTP_SALES", "name": "Mô hình doanh thu", "data_source_id": ds_id},
    )
    assert model_res.ok, model_res.message
    model_id = int(model_res.data["id"])
    ver_id = int(model_res.data["draft_version"]["id"])

    t_fact = add_table_to_draft(
        _owner(),
        ver_id,
        {"source_owner": "main", "source_object": "FACT_SALES", "object_type": "TABLE", "pos_x": 360, "pos_y": 80},
    )
    assert t_fact.ok, t_fact.message

    try:
        yield engine, ds_id, model_id, ver_id
    finally:
        invalidate_catalog_cache()
        clear_perm_cache()
        engine.dispose()


def test_discover_source_objects_and_picker_exclusion(studio_env) -> None:
    import app.ui.pages.report_model_studio as studio
    from app.services.semantic_model import discover_source_objects, get_model_version_detail

    _, ds_id, _, ver_id = studio_env
    # Viewer bị chặn
    deny = discover_source_objects(_viewer(), ds_id)
    assert not deny.ok

    res = discover_source_objects(_owner(), ds_id, enrich=True)
    assert res.ok, res.message
    items = res.data["objects"]
    fact_item = next(x for x in items if x["name"] == "FACT_SALES")
    assert fact_item["type"] == "TABLE"
    assert fact_item["pk_count"] >= 1
    assert fact_item["fk_count"] >= 1
    assert fact_item["row_estimate"] == 2

    view_res = discover_source_objects(_owner(), ds_id, object_type="VIEW", enrich=True)
    assert view_res.ok
    assert [x["name"] for x in view_res.data["objects"]] == ["V_CUSTOMER_ACTIVE"]
    assert view_res.data["objects"][0]["row_estimate"] is None

    bundle = get_model_version_detail(_owner(), ver_id).data
    picker_comp = studio.render_source_picker_list(
        objects=items,
        existing_objects={t["source_object"].upper() for t in bundle["tables"]},
        query="",
        object_type="ALL",
    )
    picker_text = _dump(picker_comp)
    assert "Đã thêm" in picker_text
    assert "DIM_CUSTOMER" in picker_text


def test_studio_layout_three_panels_and_explorer_search(studio_env, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.ui.pages.report_model_studio as studio
    from app.services.semantic_model import get_model_version_detail

    _, _, model_id, ver_id = studio_env

    # Gate phân quyền
    monkeypatch.setattr(studio, "get_current_ctx", lambda: None)
    assert "/login" in _dump(studio.layout(model_id=str(model_id)))
    monkeypatch.setattr(studio, "get_current_ctx", _viewer)
    assert "/forbidden" in _dump(studio.layout(model_id=str(model_id)))

    # Owner mở được Studio đủ 3 panel + status bar
    monkeypatch.setattr(studio, "get_current_ctx", _owner)
    root_dump = _dump(studio.layout(model_id=str(model_id)))
    assert "rms-explorer" in root_dump
    assert "rm-canvas-container" in root_dump
    assert "rms-properties" in root_dump
    assert "rms-status-bar" in root_dump
    assert "Thêm bảng" in root_dump
    assert "Kiểm tra model" in root_dump
    assert "Lưu nháp" in root_dump
    assert "Phát hành" in root_dump
    assert "Khả dụng ở Task 109" in root_dump

    # Search theo cột -> tự mở bảng & highlight match
    bundle = get_model_version_detail(_owner(), ver_id).data
    explorer = studio.render_explorer_panel(bundle, selection=None, query="AMOUNT")
    exp_dump = _dump(explorer)
    assert "FACT_SALES" in exp_dump
    assert "AMOUNT" in exp_dump
    assert "rms-match" in exp_dump


def test_star_schema_auto_layout_deterministic_and_no_overlap(studio_env) -> None:
    import app.ui.pages.report_model_studio as studio

    fake_tables = [
        {"id": 1, "alias": "F_SALES", "table_role": "FACT", "pos_x": 0, "pos_y": 0, "fields": [{"id": i} for i in range(6)]},
        {"id": 2, "alias": "D_CUST", "table_role": "DIMENSION", "pos_x": 0, "pos_y": 0, "fields": [{"id": i} for i in range(4)]},
        {"id": 3, "alias": "D_DATE", "table_role": "DIMENSION", "pos_x": 0, "pos_y": 0, "fields": [{"id": i} for i in range(5)]},
        {"id": 4, "alias": "D_PROD", "table_role": "DIMENSION", "pos_x": 0, "pos_y": 0, "fields": [{"id": i} for i in range(4)]},
        {"id": 5, "alias": "D_ORG", "table_role": "DIMENSION", "pos_x": 0, "pos_y": 0, "fields": [{"id": i} for i in range(3)]},
        {"id": 6, "alias": "B_ALLOC", "table_role": "BRIDGE", "pos_x": 0, "pos_y": 0, "fields": [{"id": i} for i in range(3)]},
    ]
    fake_rels = [
        {"id": 10, "from_table_id": 1, "to_table_id": 2, "from_column": "A", "to_column": "A", "is_active": True},
        {"id": 11, "from_table_id": 1, "to_table_id": 3, "from_column": "B", "to_column": "B", "is_active": True},
        {"id": 12, "from_table_id": 1, "to_table_id": 4, "from_column": "C", "to_column": "C", "is_active": True},
        {"id": 13, "from_table_id": 1, "to_table_id": 5, "from_column": "D", "to_column": "D", "is_active": True},
    ]
    pos_a = studio.auto_layout_star_schema(fake_tables, fake_rels)
    pos_b = studio.auto_layout_star_schema(fake_tables, fake_rels)
    assert pos_a == pos_b
    assert set(pos_a.keys()) == {1, 2, 3, 4, 5, 6}

    # Fact ở giữa theo trục X so với dim hai bên, và không có box nào chồng lấn
    laid_out = [{**t, "pos_x": pos_a[t["id"]][0], "pos_y": pos_a[t["id"]][1]} for t in fake_tables]
    boxes = [studio.table_box(t) for t in laid_out]
    for idx, b1 in enumerate(boxes):
        assert b1["x"] >= 32 and b1["y"] >= 32
        for b2 in boxes[idx + 1 :]:
            overlap_x = b1["x"] < b2["x"] + b2["w"] and b1["x"] + b1["w"] > b2["x"]
            overlap_y = b1["y"] < b2["y"] + b2["h"] and b1["y"] + b1["h"] > b2["y"]
            assert not (overlap_x and overlap_y), f"Card chồng lấn: {b1} vs {b2}"


def test_canvas_fit_and_dynamic_svg_connectors(studio_env) -> None:
    import app.ui.pages.report_model_studio as studio
    from app.services.semantic_model import add_table_to_draft, get_model_version_detail
    from app.services.semantic_model_validate import upsert_relationship

    _, _, _, ver_id = studio_env
    t_dim = add_table_to_draft(
        _owner(),
        ver_id,
        {"source_owner": "main", "source_object": "DIM_CUSTOMER", "object_type": "TABLE", "pos_x": 760, "pos_y": 100},
    )
    assert t_dim.ok, t_dim.message
    bundle_before = get_model_version_detail(_owner(), ver_id).data
    fact_t = next(t for t in bundle_before["tables"] if t["source_object"] == "FACT_SALES")
    dim_t = next(t for t in bundle_before["tables"] if t["source_object"] == "DIM_CUSTOMER")

    rel_res = upsert_relationship(
        _owner(),
        ver_id,
        {
            "name": "REL_SALES_CUST",
            "from_table_id": fact_t["id"],
            "from_column": "CUSTOMER_ID",
            "to_table_id": dim_t["id"],
            "to_column": "CUSTOMER_ID",
            "cardinality": "MANY_TO_ONE",
            "join_type": "LEFT_OUTER",
            "is_active": True,
        },
    )
    assert rel_res.ok, rel_res.message
    bundle = get_model_version_detail(_owner(), ver_id).data

    fit_zoom = studio.compute_canvas_fit(bundle["tables"], viewport_w=720, viewport_h=480)
    assert 0.4 <= fit_zoom <= 1.25

    conns = studio.build_relationship_connectors(
        bundle["tables"],
        bundle["relationships"],
        selection={"kind": "relationship", "id": rel_res.data["id"]},
    )
    assert len(conns) == 1
    c0 = conns[0]
    assert c0["path_d"].startswith("M ") and " C " in c0["path_d"]
    assert c0["state_cls"] == "selected"
    assert c0["label"] == "*:1"

    canvas_dump = _dump(
        studio.render_canvas_panel(
            bundle,
            selection={"kind": "relationship", "id": rel_res.data["id"]},
            zoom=fit_zoom,
        )
    )
    assert "rms-rel-svg-layer" in canvas_dump
    assert "*:1" in canvas_dump
    assert "DIM_CUSTOMER" in canvas_dump
    assert "PK" in canvas_dump
    assert "FK" in canvas_dump


def test_table_field_properties_sum_lock_and_rls_render(studio_env) -> None:
    import app.ui.pages.report_model_studio as studio
    from app.services.semantic_model import get_model_version_detail

    _, _, _, ver_id = studio_env
    bundle = get_model_version_detail(_owner(), ver_id).data
    fact_t = next(t for t in bundle["tables"] if t["source_object"] == "FACT_SALES")

    # Render Table Properties (gồm Grain & RLS V1)
    tbl_dump = _dump(studio.render_properties_panel(bundle, selection={"kind": "table", "id": fact_t["id"]}))
    assert "Grain" in tbl_dump
    assert "OWNER_USERNAME" in tbl_dump

    # Lưu Grain cho Fact + RLS metadata V1
    ok_bundle, err_msg, _ = studio.save_table_properties(
        _owner(),
        bundle=bundle,
        table_id=fact_t["id"],
        alias="FACT_SALES",
        display_name="Doanh thu bán hàng",
        table_role="FACT",
        grain_desc="1 dòng / SALES_ID",
        grain_keys=["SALES_ID"],
        default_date_field="TRANS_DATE",
        is_hidden=False,
    )
    assert err_msg is None and ok_bundle is not None

    rls_bundle, rls_err, _ = studio.save_rls_policy_from_studio(
        _owner(),
        bundle=ok_bundle,
        table_id=fact_t["id"],
        column_name="CUSTOMER_ID",
        policy_type="OWNER_USERNAME",
        scope_attr="username",
        admin_bypass=True,
        is_active=True,
    )
    assert rls_err is None and rls_bundle is not None
    assert len(rls_bundle["rls_policies"]) == 1

    # Field Properties: khóa SUM trên non-numeric (NOTE_TXT là STRING, TRANS_DATE là DATE)
    note_fld = next(f for f in fact_t["fields"] if f["source_column"] == "NOTE_TXT")
    date_fld = next(f for f in fact_t["fields"] if f["source_column"] == "TRANS_DATE")
    amt_fld = next(f for f in fact_t["fields"] if f["source_column"] == "AMOUNT")
    text_agg_opts = studio.agg_options_for_field(note_fld)
    date_agg_opts = studio.agg_options_for_field(date_fld)
    num_agg_opts = studio.agg_options_for_field(amt_fld)
    assert "SUM" not in [o["value"] for o in text_agg_opts]
    assert "SUM" not in [o["value"] for o in date_agg_opts]
    assert "SUM" in [o["value"] for o in num_agg_opts]

    fld_panel_dump = _dump(
        studio.render_properties_panel(
            rls_bundle,
            selection={"kind": "field", "id": amt_fld["id"], "table_id": fact_t["id"]},
        )
    )
    assert "Độ nhạy" in fld_panel_dump
    assert "Phép tổng hợp mặc định" in fld_panel_dump

    upd_bundle, f_err, _ = studio.save_field_properties(
        _owner(),
        bundle=rls_bundle,
        field_id=amt_fld["id"],
        display_name="Doanh thu thuần",
        field_role="MEASURE_CANDIDATE",
        default_agg="SUM",
        format_mask="#,##0",
        is_visible=True,
        is_filterable=True,
        sort_by_field_id=None,
        folder="Doanh số",
        enable_date_hierarchy=False,
        sensitivity="NORMAL",
    )
    assert f_err is None and upd_bundle is not None


def test_relationship_tier2_validation_and_measure_studio_ast(studio_env) -> None:
    import app.ui.pages.report_model_studio as studio
    from app.services.semantic_model import add_table_to_draft, get_model_version_detail
    from app.services.semantic_model_validate import upsert_relationship

    _, _, _, ver_id = studio_env
    add_table_to_draft(
        _owner(),
        ver_id,
        {"source_owner": "main", "source_object": "DIM_CUSTOMER", "object_type": "TABLE", "pos_x": 760, "pos_y": 100},
    )
    bundle = get_model_version_detail(_owner(), ver_id).data
    fact_t = next(t for t in bundle["tables"] if t["source_object"] == "FACT_SALES")
    dim_t = next(t for t in bundle["tables"] if t["source_object"] == "DIM_CUSTOMER")
    rel_res = upsert_relationship(
        _owner(),
        ver_id,
        {
            "name": "REL_SALES_CUST",
            "from_table_id": fact_t["id"],
            "from_column": "CUSTOMER_ID",
            "to_table_id": dim_t["id"],
            "to_column": "CUSTOMER_ID",
            "cardinality": "MANY_TO_ONE",
            "join_type": "LEFT_OUTER",
            "is_active": True,
        },
    )
    assert rel_res.ok
    bundle = get_model_version_detail(_owner(), ver_id).data
    rel_id = int(rel_res.data["id"])

    # Relationship panel + Tier 1/2
    rel_dump = _dump(studio.render_properties_panel(bundle, selection={"kind": "relationship", "id": rel_id}))
    assert "Kiểm tra quan hệ" in rel_dump
    assert "Kiểm tra dữ liệu mẫu" in rel_dump
    prof_res = studio.run_relationship_tier2_profile(_owner(), rel_id)
    assert prof_res.ok and prof_res.data["status"] == "PASS"

    # Measure Studio: Simple + Structured AST Calculated Measure
    amt_fld = next(f for f in fact_t["fields"] if f["source_column"] == "AMOUNT")
    sales_pk = next(f for f in fact_t["fields"] if f["source_column"] == "SALES_ID")
    m1_bundle, m1_err, _ = studio.save_measure_from_studio(
        _owner(),
        bundle=bundle,
        measure_id=None,
        code="TOTAL_REV",
        name="Tổng doanh thu",
        measure_type="SIMPLE",
        table_id=fact_t["id"],
        base_field_id=amt_fld["id"],
        aggregation="SUM",
        ast_expr=None,
        format_mask="#,##0",
        folder="Doanh thu",
    )
    assert m1_err is None and m1_bundle is not None

    ast_expr = studio.build_calculated_ast_from_form(
        op="DIVIDE",
        left_kind="FIELD_AGG",
        left_field_id=amt_fld["id"],
        left_agg="SUM",
        left_measure_id=None,
        left_const=None,
        right_kind="FIELD_AGG",
        right_field_id=sales_pk["id"],
        right_agg="COUNT",
        right_measure_id=None,
        right_const=None,
    )
    m2_bundle, m2_err, _ = studio.save_measure_from_studio(
        _owner(),
        bundle=m1_bundle,
        measure_id=None,
        code="AVG_ORDER_REV",
        name="Doanh thu TB/Đơn",
        measure_type="CALCULATED",
        table_id=fact_t["id"],
        base_field_id=None,
        aggregation=None,
        ast_expr=ast_expr,
        format_mask="#,##0",
        folder="Doanh thu",
    )
    assert m2_err is None and m2_bundle is not None
    assert len(m2_bundle["measures"]) == 2


def test_validation_drawer_and_issue_navigation(studio_env) -> None:
    import app.ui.pages.report_model_studio as studio
    from app.services.semantic_model import add_table_to_draft, get_model_version_detail

    eng, _, _, ver_id = studio_env
    # FACT_SALES chưa khai báo Grain -> validate_model báo lỗi GRAIN_REQUIRED
    t_dim = add_table_to_draft(
        _owner(),
        ver_id,
        {"source_owner": "main", "source_object": "DIM_CUSTOMER", "object_type": "TABLE", "pos_x": 40, "pos_y": 80},
    )
    assert t_dim.ok
    bundle = get_model_version_detail(_owner(), ver_id).data
    assert bundle is not None

    # Ép FACT_SALES thành FACT nhưng bỏ trống grain để phát sinh ERROR
    fact_t = next(t for t in bundle["tables"] if t["source_object"] == "FACT_SALES")
    from sqlalchemy import update

    from app.db.metadata import recon_rpt_model_table

    with eng.begin() as conn:
        conn.execute(
            update(recon_rpt_model_table)
            .where(recon_rpt_model_table.c.ID == fact_t["id"])
            .values(TABLE_ROLE="FACT", GRAIN_DESC=None, GRAIN_KEYS_JSON=None)
        )
    bundle = get_model_version_detail(_owner(), ver_id).data
    assert bundle is not None

    refreshed_bundle, val_data, val_err = studio.run_full_model_validation(_owner(), bundle)
    assert val_err is None and refreshed_bundle is not None and val_data is not None
    assert val_data["summary"]["error_count"] >= 1

    drawer_html = _dump(studio.render_validation_drawer_body(refreshed_bundle, val_data))
    assert "polite" in drawer_html  # aria-live="polite"
    assert "GRAIN_REQUIRED" in drawer_html

    issues = list(val_data.get("issues") or [])
    tbl_issue = next(i for i in issues if i.get("target_type") == "table")
    sel = studio.resolve_validation_issue_selection(refreshed_bundle, tbl_issue)
    assert sel == {"kind": "table", "id": fact_t["id"]}

    # Kiểm tra resolve cho các target_type khác (field, rls, measure, relationship)
    sample_fld = fact_t["fields"][0]
    assert studio.resolve_validation_issue_selection(
        refreshed_bundle, {"target_type": "field", "target_id": sample_fld["id"]}
    ) == {"kind": "field", "id": sample_fld["id"], "table_id": fact_t["id"]}

    # Khắc phục Grain -> validate lại sạch lỗi ERROR
    ok_bundle, err_msg, _ = studio.save_table_properties(
        _owner(),
        bundle=refreshed_bundle,
        table_id=fact_t["id"],
        alias="FACT_SALES",
        display_name="Bảng doanh thu",
        table_role="FACT",
        grain_desc="1 dòng / SALES_ID",
        grain_keys=["SALES_ID"],
        default_date_field="TRANS_DATE",
        is_hidden=False,
    )
    assert err_msg is None and ok_bundle is not None
    ok_bundle2, val_ok, err2 = studio.run_full_model_validation(_owner(), ok_bundle)
    assert err2 is None and val_ok is not None and ok_bundle2 is not None
    assert val_ok["summary"]["error_count"] == 0


def test_save_draft_optimistic_concurrency_stale_data(studio_env) -> None:
    import copy

    import app.ui.pages.report_model_studio as studio
    from app.schemas.errors import ErrorCode
    from app.services.semantic_model import get_model_version_detail, save_draft_state

    _, _, model_id, ver_id = studio_env
    bundle_a = get_model_version_detail(_owner(), ver_id).data
    assert bundle_a is not None
    ver_a_before = int(bundle_a["version"]["row_version"])

    # Phiên B lưu trước làm tăng ROW_VERSION trong DB
    res_b = save_draft_state(_owner(), ver_id, {"expected_row_version": ver_a_before, "positions": []})
    assert res_b.ok, res_b.message

    # Phiên A kéo vị trí card trên bản cũ (với row_version cũ) và bấm Lưu nháp
    stale_bundle = copy.deepcopy(bundle_a)
    stale_bundle["tables"][0]["pos_x"] = 510
    stale_bundle["tables"][0]["pos_y"] = 220

    saved_bundle, save_res = studio.save_studio_draft(_owner(), stale_bundle)
    assert saved_bundle is None
    assert not save_res.ok
    assert save_res.code == ErrorCode.STALE_DATA

    stale_dump = _dump(studio.render_stale_conflict_body(save_res.message or ""))
    assert "Tải lại bản mới" in stale_dump or "bản nháp" in stale_dump

    # Tải lại bản mới và lưu tiếp thành công
    fresh_bundle, load_err = studio.load_studio_bundle(_owner(), model_id)
    assert load_err is None and fresh_bundle is not None
    fresh_bundle["tables"][0]["pos_x"] = 510
    fresh_bundle["tables"][0]["pos_y"] = 220
    saved_ok, ok_res = studio.save_studio_draft(_owner(), fresh_bundle)
    assert ok_res.ok and saved_ok is not None
    saved_fact = next(t for t in saved_ok["tables"] if t["source_object"] == "FACT_SALES")
    assert saved_fact["pos_x"] == 510 and saved_fact["pos_y"] == 220


def test_publish_modal_preview_diff_impact_and_readonly_active(studio_env) -> None:
    import app.ui.pages.report_model_studio as studio
    from app.services.semantic_model import add_table_to_draft, get_model_version_detail, open_or_create_draft
    from app.services.semantic_model_validate import upsert_relationship

    _, _, model_id, ver_id = studio_env
    t_dim = add_table_to_draft(
        _owner(),
        ver_id,
        {"source_owner": "main", "source_object": "DIM_CUSTOMER", "object_type": "TABLE", "pos_x": 40, "pos_y": 80},
    )
    assert t_dim.ok
    bundle = get_model_version_detail(_owner(), ver_id).data
    assert bundle is not None

    fact_t = next(t for t in bundle["tables"] if t["source_object"] == "FACT_SALES")
    dim_t = next(t for t in bundle["tables"] if t["source_object"] == "DIM_CUSTOMER")
    amt_fld = next(f for f in fact_t["fields"] if f["source_column"] == "AMOUNT")

    bundle, err_t, _ = studio.save_table_properties(
        _owner(),
        bundle=bundle,
        table_id=fact_t["id"],
        alias="FACT_SALES",
        display_name="Bảng doanh thu",
        table_role="FACT",
        grain_desc="1 dòng / SALES_ID",
        grain_keys=["SALES_ID"],
        default_date_field="TRANS_DATE",
        is_hidden=False,
    )
    assert err_t is None and bundle is not None

    bundle, err_d, _ = studio.save_table_properties(
        _owner(),
        bundle=bundle,
        table_id=dim_t["id"],
        alias="DIM_CUSTOMER",
        display_name="Khách hàng",
        table_role="DIMENSION",
        grain_desc=None,
        grain_keys=[],
        default_date_field=None,
        is_hidden=False,
    )
    assert err_d is None and bundle is not None

    rel_res = upsert_relationship(
        _owner(),
        ver_id,
        {
            "name": "REL_SALES_CUST",
            "from_table_id": fact_t["id"],
            "from_column": "CUSTOMER_ID",
            "to_table_id": dim_t["id"],
            "to_column": "CUSTOMER_ID",
            "cardinality": "MANY_TO_ONE",
            "join_type": "LEFT_OUTER",
            "cross_filter": "SINGLE",
            "is_active": True,
        },
    )
    assert rel_res.ok, rel_res.message
    bundle = get_model_version_detail(_owner(), ver_id).data
    assert bundle is not None

    bundle, m_err, _ = studio.save_measure_from_studio(
        _owner(),
        bundle=bundle,
        measure_id=None,
        code="TOTAL_REV",
        name="Tổng doanh thu",
        measure_type="SIMPLE",
        table_id=fact_t["id"],
        base_field_id=amt_fld["id"],
        aggregation="SUM",
        ast_expr=None,
        format_mask="#,##0",
        folder="Doanh thu",
    )
    assert m_err is None and bundle is not None

    preview, prev_err = studio.build_publish_preview(_owner(), bundle)
    assert prev_err is None and preview is not None
    assert preview["can_publish"] is True
    assert "reports" in preview["impact"]
    modal_dump = _dump(studio.render_publish_modal_body(bundle, preview))
    assert "Ghi chú phát hành" in modal_dump

    # Thiếu change_note bị chặn
    bad_pub, bad_err = studio.publish_from_studio(_owner(), bundle, change_note="   ")
    assert bad_pub is None and bad_err is not None

    # Phát hành thành công -> Studio chuyển sang chế độ ACTIVE chỉ đọc + có nút Tạo bản nháp mới
    active_bundle, pub_err = studio.publish_from_studio(_owner(), bundle, change_note="Phát hành v1 chuẩn")
    assert pub_err is None and active_bundle is not None
    assert active_bundle["version"]["status"] == "ACTIVE"

    hdr_dump = _dump(studio.render_studio_header(active_bundle, dirty=False))
    assert "ACTIVE" in hdr_dump
    assert "Tạo bản nháp mới" in hdr_dump

    prop_ro_dump = _dump(studio.render_properties_panel(active_bundle, selection={"kind": "table", "id": fact_t["id"]}))
    assert "Phiên bản chỉ đọc" in prop_ro_dump

    # Tạo bản nháp v2 -> thêm view -> xem diff trước khi phát hành
    v2_res = open_or_create_draft(_owner(), model_id)
    assert v2_res.ok and v2_res.data is not None
    add_v = add_table_to_draft(
        _owner(),
        v2_res.data["version"]["id"],
        {"source_owner": "main", "source_object": "V_CUSTOMER_ACTIVE", "object_type": "VIEW", "pos_x": 660, "pos_y": 80},
    )
    assert add_v.ok
    v2_bundle = get_model_version_detail(_owner(), v2_res.data["version"]["id"]).data
    assert v2_bundle is not None
    v2_prev, v2_err = studio.build_publish_preview(_owner(), v2_bundle)
    assert v2_err is None and v2_prev is not None and v2_prev["diff"] is not None
    v2_dump = _dump(studio.render_publish_modal_body(v2_bundle, v2_prev))
    assert "V_CUSTOMER_ACTIVE" in v2_dump
