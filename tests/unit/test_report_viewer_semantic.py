"""Tests Bước 5 task 109 — Report Run/Viewer cho báo cáo Studio (SEMANTIC_MODEL).

Viết trước theo plan: create_report_run hỗ trợ visual_id + query_spec,
execute/get_report_page/get_run_sql chạy semantic qua Query Planner 108,
hồi quy report CUSTOM_SQL cũ, layout Viewer nhận biết SEMANTIC_MODEL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text

from app.core.context import Ctx, Role
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_data_source, recon_rpt_visual, recon_user
from app.engine.catalog import invalidate_catalog_cache
from app.schemas.errors import ErrorCode, ServiceError

ROOT = Path(__file__).resolve().parent.parent.parent


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def viewer_sem_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """DB app + source star schema + model/report Studio, phục vụ test Bước 5."""
    invalidate_catalog_cache()
    db_file = tmp_path / "viewer_sem.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    src_db = tmp_path / "viewer_sem_src.db"

    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "super-secret-key-123456789")
    monkeypatch.setenv("RECON_STORAGE_DIR", str(tmp_path / "storage"))
    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    src_engine = create_engine(f"sqlite:///{src_db.as_posix()}")
    with src_engine.begin() as sconn:
        sconn.execute(
            text(
                """
                CREATE TABLE DIM_CUSTOMER (
                    CUSTOMER_ID INTEGER PRIMARY KEY,
                    CUSTOMER_NAME TEXT NOT NULL,
                    SEGMENT TEXT NOT NULL,
                    ORG_CODE TEXT NOT NULL,
                    ROLE_COL TEXT NOT NULL,
                    OWNER_USER TEXT NOT NULL
                )
                """
            )
        )
        sconn.execute(
            text(
                """
                CREATE TABLE DIM_DATE (
                    CAL_DATE DATE NOT NULL,
                    MONTH_LABEL TEXT NOT NULL
                )
                """
            )
        )
        sconn.execute(
            text(
                """
                CREATE TABLE DIM_SERVICE (
                    SERVICE_ID INTEGER PRIMARY KEY,
                    SERVICE_NAME TEXT NOT NULL
                )
                """
            )
        )
        sconn.execute(
            text(
                """
                CREATE TABLE FACT_SALES (
                    SALE_ID INTEGER PRIMARY KEY,
                    CUSTOMER_ID INTEGER NOT NULL,
                    SERVICE_ID INTEGER NOT NULL,
                    SALE_DAY DATE NOT NULL,
                    SALE_DATE DATETIME NOT NULL,
                    REVENUE NUMERIC NOT NULL,
                    COST NUMERIC NOT NULL,
                    QTY INTEGER NOT NULL,
                    OWNER_COL TEXT NOT NULL,
                    ORG_CODE TEXT NOT NULL,
                    FOREIGN KEY (CUSTOMER_ID) REFERENCES DIM_CUSTOMER(CUSTOMER_ID),
                    FOREIGN KEY (SERVICE_ID) REFERENCES DIM_SERVICE(SERVICE_ID)
                )
                """
            )
        )
        sconn.execute(
            text(
                "INSERT INTO DIM_CUSTOMER VALUES "
                "(1, 'Cong ty A', 'VIP', 'BDP', 'admin', 'owner'), "
                "(2, 'Cong ty B', 'STD', 'HCM', 'admin', 'viewer')"
            )
        )
        sconn.execute(text("INSERT INTO DIM_DATE VALUES ('2026-01-01', '2026-01'), ('2026-02-01', '2026-02')"))
        sconn.execute(text("INSERT INTO DIM_SERVICE VALUES (1, 'Dich vu 1'), (2, 'Dich vu 2')"))
        sconn.execute(
            text(
                "INSERT INTO FACT_SALES VALUES "
                "(1, 1, 1, '2026-01-01', '2026-01-01 10:00:00', 500000, 300000, 5, 'admin', 'BDP'), "
                "(2, 2, 1, '2026-01-01', '2026-01-01 11:00:00', 200000, 120000, 2, 'admin', 'HCM'), "
                "(3, 1, 2, '2026-02-01', '2026-02-01 09:00:00', 300000, 180000, 3, 'admin', 'BDP')"
            )
        )

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
        "app.services.report_column",
        "app.services.report_run",
        "app.services.report_export",
        "app.services.report_timeouts",
        "app.services.export_retention",
        "app.services.notification",
    ):
        monkeypatch.setattr(f"{mod_path}.get_recon_engine", lambda: engine)

    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from app.services.semantic_query import invalidate_semantic_query_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = _now()
    with engine.begin() as conn:
        for uid, uname in [(1, "admin"), (2, "owner"), (3, "viewer"), (4, "operator")]:
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

    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["TEMPLATE_OWNER"], 3: ["VIEWER"], 4: ["OPERATOR"]})
    clear_perm_cache()
    invalidate_semantic_query_cache()

    ctxs = {
        "admin": Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN]),
        "owner": Ctx(user_id=2, username="owner", full_name="Owner", roles=[Role.TEMPLATE_OWNER]),
        "viewer": Ctx(user_id=3, username="viewer", full_name="Viewer", roles=[Role.VIEWER]),
        "operator": Ctx(user_id=4, username="operator", full_name="Operator", roles=[Role.OPERATOR]),
    }
    yield engine, ds_id, ctxs
    src_engine.dispose()
    engine.dispose()


def _build_published_model(owner_ctx, ds_id, code="M_SALES", rls_owner_username=False):
    """Dựng model star schema qua service 106 rồi publish ACTIVE."""
    from app.services.semantic_model import (
        add_table_to_draft,
        create_model,
        get_model_version_detail,
        update_table_props,
        upsert_measure,
        upsert_rls_policy,
    )
    from app.services.semantic_model_validate import publish_model_version, upsert_relationship

    created = create_model(owner_ctx, {"code": code, "name": "Sales Q", "data_source_id": ds_id})
    assert created.ok, created.message
    ver_id = created.data["draft_version"]["id"]
    tables = {}
    for obj in ("FACT_SALES", "DIM_CUSTOMER", "DIM_DATE", "DIM_SERVICE"):
        res = add_table_to_draft(owner_ctx, ver_id, {"source_object": obj})
        assert res.ok, res.message
        tables[obj] = res.data
    fact = tables["FACT_SALES"]
    assert update_table_props(
        owner_ctx,
        fact["id"],
        {"table_role": "FACT", "grain_desc": "Theo dòng bán", "grain_keys": ["SALE_ID"]},
    ).ok
    for obj in ("DIM_CUSTOMER", "DIM_DATE", "DIM_SERVICE"):
        assert update_table_props(owner_ctx, tables[obj]["id"], {"table_role": "DIMENSION"}).ok
    rels = [
        ("SALES_CUSTOMER", fact["id"], "CUSTOMER_ID", tables["DIM_CUSTOMER"]["id"], "CUSTOMER_ID"),
        ("SALES_DATE", fact["id"], "SALE_DAY", tables["DIM_DATE"]["id"], "CAL_DATE"),
        ("SALES_SERVICE", fact["id"], "SERVICE_ID", tables["DIM_SERVICE"]["id"], "SERVICE_ID"),
    ]
    for name, from_tid, from_col, to_tid, to_col in rels:
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
    for mcode, base_col in (("REV_SUM", "REVENUE"), ("QTY_SUM", "QTY")):
        m = upsert_measure(
            owner_ctx,
            ver_id,
            {
                "code": mcode,
                "name": f"Measure {mcode}",
                "table_id": fact["id"],
                "measure_type": "SIMPLE",
                "base_field_id": fact_cols[base_col]["id"],
                "aggregation": "SUM",
            },
        )
        assert m.ok, m.message
    if rls_owner_username:
        res = upsert_rls_policy(
            owner_ctx,
            ver_id,
            {
                "table_id": tables["DIM_CUSTOMER"]["id"],
                "column_name": "OWNER_USER",
                "policy_type": "OWNER_USERNAME",
                "admin_bypass": True,
                "is_active": True,
            },
        )
        assert res.ok, res.message
    pub = publish_model_version(owner_ctx, ver_id, {"change_note": "Phat hanh v1"})
    assert pub.ok, pub.message
    detail = get_model_version_detail(owner_ctx, ver_id)
    assert detail.ok, detail.message
    return ver_id, detail.data


def _field_id(bundle, alias, source_column):
    for t in bundle["tables"]:
        if t["alias"] == alias:
            for f in t["fields"]:
                if f["source_column"] == source_column:
                    return int(f["id"])
    raise AssertionError(f"Không thấy field {alias}.{source_column}")


def _measure_id(bundle, code):
    for m in bundle["measures"]:
        if m["code"] == code:
            return int(m["id"])
    raise AssertionError(f"Không thấy measure {code}")


def _table_visual(bundle, code="V_TABLE", **overrides):
    payload = {
        "code": code,
        "title": "Bảng doanh thu",
        "visual_type": "TABLE",
        "display_order": 10,
        "grid_span": 12,
        "height_size": "M",
        "fields": [
            {"well_role": "X", "field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")},
            {"well_role": "Y", "measure_id": _measure_id(bundle, "REV_SUM")},
        ],
    }
    payload.update(overrides)
    return payload


def _bar_visual(bundle, code="V_BAR", **overrides):
    payload = {
        "code": code,
        "title": "Biểu đồ doanh thu",
        "visual_type": "BAR",
        "display_order": 20,
        "grid_span": 6,
        "height_size": "M",
        "fields": [
            {"well_role": "X", "field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")},
            {"well_role": "Y", "measure_id": _measure_id(bundle, "REV_SUM")},
            {"well_role": "SERIES", "field_id": _field_id(bundle, "DIM_CUSTOMER", "SEGMENT")},
        ],
    }
    payload.update(overrides)
    return payload


def _publish_studio_report(owner_ctx, ver_id, bundle, visuals, params=None, code="RPT_SALES"):
    """Tạo báo cáo Studio + lưu visuals (+ params) + validate + publish.

    Trả (report_id, version_id, {visual_code: visual_db_id}).
    """
    from app.services.report_studio import (
        create_studio_report,
        open_or_create_studio_draft,
        publish_studio_report,
        save_studio_draft,
        validate_studio_report,
    )

    res = create_studio_report(
        owner_ctx,
        {"code": code, "name": "Báo cáo doanh thu", "model_version_id": ver_id},
    )
    assert res.ok, res.message
    report_id = res.data["report"]["id"]
    opened = open_or_create_studio_draft(owner_ctx, report_id)
    assert opened.ok, opened.message
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    payload = {"row_version": rv, "visuals": visuals}
    if params is not None:
        payload["params"] = params
    saved = save_studio_draft(owner_ctx, vid, payload)
    assert saved.ok, saved.message
    assert validate_studio_report(owner_ctx, vid).ok
    pub = publish_studio_report(owner_ctx, vid, {"change_note": "Phat hanh v1"})
    assert pub.ok, pub.message
    return report_id, vid, _visual_db_ids(vid)


def _visual_db_ids(version_id):
    from app.db.engine import get_recon_engine

    engine = get_recon_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(select(recon_rpt_visual).where(recon_rpt_visual.c.VERSION_ID == version_id))
            .mappings()
            .all()
        )
    return {str(r["CODE"]): int(r["ID"]) for r in rows}


def _run_visual(ctx, report_id, visual_id, values=None, query_spec=None):
    """Tạo + chạy 1 run cho 1 visual; trả dict run đã DONE (hoặc FAILED)."""
    from app.services.report_run import create_report_run, execute_report_run

    created = create_report_run(ctx, report_id, values=values or {}, visual_id=visual_id, query_spec=query_spec)
    assert created.ok, created.message
    run_id = int(created.data["id"])
    executed = execute_report_run(ctx, run_id)
    assert executed.ok, executed.message
    return executed.data


def _make_classic_report(admin_ctx, ds_id, engine):
    """Báo cáo CUSTOM_SQL cổ điển trên cùng source SQLite + ACTIVE."""
    from sqlalchemy import select

    from app.db.metadata import recon_report_template, recon_rpt_column
    from app.services.report import create_report
    from app.services.report_param import create_param
    from app.services.report_run import dry_run_version
    from app.services.report_template import activate_version, create_template

    res = create_report(
        admin_ctx,
        {"code": "RPT_CLASSIC", "name": "Báo cáo cổ điển", "category_code": "FIN", "owner": "admin"},
    )
    assert res.ok, res.message
    report_id = res.data["id"]
    tpl = create_template(
        admin_ctx,
        report_id,
        {
            "code": "SQL1",
            "name": "Mẫu SQL1",
            "display_order": 10,
            "timeout_sec": 300,
            "preview_max_rows": 100,
            "export_max_rows": 1000000,
            "data_source_id": ds_id,
            "source_type": "CUSTOM_SQL",
            # Lưu ý: classic + SQLITE chạy trên chính RECON_APP DB
            # (open_checked_connection trả raw_connection của app engine),
            # nên SQL mẫu truy vấn RECON_REPORT thay vì bảng nguồn star.
            "sql_text": (
                "SELECT CODE, NAME FROM RECON_REPORT "
                "WHERE (:P_SEG IS NULL OR CATEGORY_CODE = :P_SEG) ORDER BY CODE"
            ),
        },
    )
    assert tpl.ok, tpl.message
    version_id = int(tpl.data["id"])
    param = create_param(
        admin_ctx,
        version_id,
        {
            "code": "P_SEG",
            "label": "Nhóm",
            "data_type": "STRING",
            "control_type": "TEXT",
            "required": False,
            "filter_column": "CATEGORY_CODE",
            "filter_operator": "=",
        },
    )
    assert param.ok, param.message
    with engine.begin() as conn:
        for order, field in enumerate(["CODE", "NAME"]):
            conn.execute(
                recon_rpt_column.insert().values(
                    VERSION_ID=version_id,
                    FIELD_NAME=field,
                    LABEL="Mã" if field == "CODE" else "Tên",
                    DATA_TYPE="STRING",
                    DISPLAY_ORDER=(order + 1) * 10,
                    WEB_VISIBLE="Y",
                    EXCEL_VISIBLE="Y",
                    ALIGNMENT="LEFT",
                    IS_TOTAL="N",
                )
            )
    dry = dry_run_version(admin_ctx, version_id, {"P_SEG": "FIN"})
    assert dry.ok, dry.message
    assert dry.data["status"] == "DRY_RUN_OK"
    act = activate_version(admin_ctx, version_id)
    assert act.ok, act.message
    with engine.connect() as conn:
        template_id = conn.execute(
            select(recon_report_template.c.ID).where(
                recon_report_template.c.REPORT_ID == report_id,
                recon_report_template.c.CODE == "SQL1",
            )
        ).scalar_one()
    return report_id, int(template_id), version_id


# ---------------------------------------------------------------------------
# create_report_run với visual_id + query_spec
# ---------------------------------------------------------------------------


def test_create_run_for_visual_stores_visual_id_and_query_spec(viewer_sem_env) -> None:
    from app.services.report_run import create_report_run, get_report_run

    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle)]
    )
    spec = {"filters": [{"field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME"), "operator": "LIKE_PREFIX", "value": "Cong ty A"}]}
    created = create_report_run(
        ctxs["viewer"], report_id, values={}, visual_id=vis_ids["V_TABLE"], query_spec=spec
    )
    assert created.ok, created.message
    data = created.data
    assert data["status"] == "QUEUED"
    assert data["visual_id"] == vis_ids["V_TABLE"]
    assert data["query_spec"] == spec
    got = get_report_run(ctxs["viewer"], int(data["id"]))
    assert got.ok
    assert got.data["visual_id"] == vis_ids["V_TABLE"]


def test_create_run_visual_from_other_version_rejected(viewer_sem_env) -> None:
    from app.services.report_run import create_report_run

    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, _vis = _publish_studio_report(ctxs["owner"], ver_id, bundle, [_table_visual(bundle)])
    # Báo cáo thứ hai, visual của nó không thuộc version của báo cáo đầu.
    ver2, bundle2 = _build_published_model(ctxs["owner"], ds_id, code="M_SALES2")
    _rid2, _vid2, vis2 = _publish_studio_report(
        ctxs["owner"], ver2, bundle2, [_table_visual(bundle2, code="V_OTHER")], code="RPT_SALES2"
    )
    blocked = create_report_run(ctxs["viewer"], report_id, values={}, visual_id=vis2["V_OTHER"])
    assert not blocked.ok
    assert blocked.code in (ErrorCode.NOT_FOUND, ErrorCode.VALIDATION_ERROR)


def test_create_run_semantic_requires_visual_id(viewer_sem_env) -> None:
    """Báo cáo Studio không có visual_id thì từ chối rõ ràng (không chạy cả báo cáo)."""
    from app.services.report_run import create_report_run

    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, _vis = _publish_studio_report(ctxs["owner"], ver_id, bundle, [_table_visual(bundle)])
    blocked = create_report_run(ctxs["viewer"], report_id, values={})
    assert not blocked.ok
    assert blocked.code == ErrorCode.VALIDATION_ERROR


# ---------------------------------------------------------------------------
# execute_report_run cho SEMANTIC_MODEL
# ---------------------------------------------------------------------------


def test_execute_semantic_run_returns_rows(viewer_sem_env) -> None:
    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle), _bar_visual(bundle)]
    )
    data = _run_visual(ctxs["viewer"], report_id, vis_ids["V_TABLE"])
    run = data["run"]
    assert run["status"] == "DONE"
    assert data["total"] == 2
    # Semantic trả columns dạng meta {name, label, data_type} (khác classic list[str]).
    assert {c["name"] for c in data["columns"]} == {"CUSTOMER_NAME", "REV_SUM"}
    assert {c["data_type"] for c in data["columns"]} == {"STRING", "NUMBER"}
    by_name = {r["CUSTOMER_NAME"]: r["REV_SUM"] for r in data["rows"]}
    assert by_name == {"Cong ty A": 800000, "Cong ty B": 200000}


def test_execute_semantic_run_applies_rls_for_viewer(viewer_sem_env) -> None:
    """RLS OWNER_USERNAME: viewer chỉ thấy khách của mình; admin (bypass) thấy hết."""
    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id, rls_owner_username=True)
    report_id, _vid, vis_ids = _publish_studio_report(ctxs["owner"], ver_id, bundle, [_table_visual(bundle)])
    viewer_data = _run_visual(ctxs["viewer"], report_id, vis_ids["V_TABLE"])
    assert viewer_data["run"]["status"] == "DONE"
    assert viewer_data["total"] == 1
    assert [r["CUSTOMER_NAME"] for r in viewer_data["rows"]] == ["Cong ty B"]
    admin_data = _run_visual(ctxs["admin"], report_id, vis_ids["V_TABLE"])
    assert admin_data["total"] == 2


def test_execute_semantic_run_param_filter_like_prefix(viewer_sem_env) -> None:
    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    param = {
        "code": "P_CUST",
        "label": "Khách hàng",
        "data_type": "STRING",
        "control_type": "TEXT",
        "required": False,
        "filter_column": "CUSTOMER_NAME",
        "filter_operator": "LIKE_PREFIX",
    }
    report_id, _vid, vis_ids = _publish_studio_report(
        ctxs["owner"], ver_id, bundle, [_table_visual(bundle)], params=[param]
    )
    data = _run_visual(ctxs["viewer"], report_id, vis_ids["V_TABLE"], values={"P_CUST": "Cong ty A"})
    assert data["run"]["status"] == "DONE"
    assert data["total"] == 1
    assert data["rows"][0]["CUSTOMER_NAME"] == "Cong ty A"
    # Không truyền param -> không lọc, đủ 2 dòng.
    data2 = _run_visual(ctxs["viewer"], report_id, vis_ids["V_TABLE"], values={})
    assert data2["total"] == 2


def test_execute_semantic_run_query_spec_filter(viewer_sem_env) -> None:
    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(ctxs["owner"], ver_id, bundle, [_table_visual(bundle)])
    spec = {
        "filters": [
            {
                "field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME"),
                "operator": "=",
                "value": "Cong ty B",
            }
        ]
    }
    data = _run_visual(ctxs["viewer"], report_id, vis_ids["V_TABLE"], query_spec=spec)
    assert data["run"]["status"] == "DONE"
    assert data["total"] == 1
    assert data["rows"][0]["CUSTOMER_NAME"] == "Cong ty B"


def test_get_report_page_semantic_paging_and_sort(viewer_sem_env) -> None:
    from app.services.report_run import get_report_page

    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(ctxs["owner"], ver_id, bundle, [_table_visual(bundle)])
    data = _run_visual(ctxs["viewer"], report_id, vis_ids["V_TABLE"])
    run_id = int(data["run"]["id"])
    page2 = get_report_page(ctxs["viewer"], run_id, page=2, page_size=1)
    assert page2.ok, page2.message
    assert page2.data["total"] == 2
    assert len(page2.data["rows"]) == 1
    sorted_page = get_report_page(
        ctxs["viewer"], run_id, page=1, page_size=2, sorts=[{"field": "REV_SUM", "direction": "DESC"}]
    )
    assert sorted_page.ok, sorted_page.message
    assert sorted_page.data["rows"][0]["CUSTOMER_NAME"] == "Cong ty A"
    assert sorted_page.data["rows"][1]["CUSTOMER_NAME"] == "Cong ty B"


def test_get_run_sql_semantic_admin_only_and_no_bind_values(viewer_sem_env) -> None:
    import json

    from app.services.report_run import get_run_sql

    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, vis_ids = _publish_studio_report(ctxs["owner"], ver_id, bundle, [_table_visual(bundle)])
    spec = {
        "filters": [
            {
                "field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME"),
                "operator": "LIKE_PREFIX",
                "value": "Cong ty",
            }
        ]
    }
    data = _run_visual(ctxs["viewer"], report_id, vis_ids["V_TABLE"], query_spec=spec)
    run_id = int(data["run"]["id"])
    denied = get_run_sql(ctxs["viewer"], run_id)
    assert not denied.ok and denied.code == ErrorCode.FORBIDDEN
    res = get_run_sql(ctxs["admin"], run_id)
    assert res.ok, res.message
    payload = res.data
    assert payload["source_type"] == "SEMANTIC_MODEL"
    assert "SELECT" in str(payload["sql_text"]).upper()
    assert payload["bind_names"]  # chỉ tên bind, không lộ giá trị
    dump = json.dumps(payload, ensure_ascii=False, default=str)
    assert "Cong ty A" not in dump
    assert "800000" not in dump


# ---------------------------------------------------------------------------
# Hồi quy report cổ điển
# ---------------------------------------------------------------------------


def test_classic_custom_sql_run_regression(viewer_sem_env) -> None:
    from app.services.report_run import create_report_run, execute_report_run, get_run_sql

    engine, ds_id, ctxs = viewer_sem_env
    report_id, _tpl_id, _ver_id = _make_classic_report(ctxs["admin"], ds_id, engine)
    created = create_report_run(ctxs["viewer"], report_id, values={"P_SEG": "FIN"})
    assert created.ok, created.message
    executed = execute_report_run(ctxs["viewer"], int(created.data["id"]))
    assert executed.ok, executed.message
    assert executed.data["run"]["status"] == "DONE"
    assert executed.data["total"] == 1
    assert executed.data["rows"][0]["CODE"] == "RPT_CLASSIC"
    sql = get_run_sql(ctxs["admin"], int(created.data["id"]))
    assert sql.ok, sql.message
    assert sql.data["source_type"] == "CUSTOM_SQL"
    assert sql.data["binds"].get("P_SEG") == "FIN"


# ---------------------------------------------------------------------------
# build_param_filters (helper thuần)
# ---------------------------------------------------------------------------


def test_build_param_filters_mapping(viewer_sem_env) -> None:
    from app.services.report_studio import build_param_filters

    _, ds_id, ctxs = viewer_sem_env
    _ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    params = [
        {"code": "P_CUST", "filter_column": "CUSTOMER_NAME", "filter_operator": "LIKE_PREFIX"},
        {"code": "P_SEG", "filter_column": "SEGMENT", "filter_operator": "="},
        {"code": "P_BETWEEN", "filter_column": "CUSTOMER_NAME", "filter_operator": "BETWEEN"},
        {"code": "P_GHOST", "filter_column": "KHONG_CO", "filter_operator": "="},
        {"code": "P_NOFILTER", "filter_column": None, "filter_operator": "="},
    ]
    resolved = {
        "P_CUST": "Cong ty A",
        "P_SEG": "VIP",
        "P_BETWEEN": {"from": "A", "to": "Z"},
        "P_GHOST": "x",
    }
    filters = build_param_filters(resolved, params, bundle)
    by_field_op = {(f["field_id"], f["operator"]): f for f in filters}
    cust_id = _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    seg_id = _field_id(bundle, "DIM_CUSTOMER", "SEGMENT")
    assert by_field_op[(cust_id, "LIKE_PREFIX")]["value"] == "Cong ty A"
    assert by_field_op[(seg_id, "=")]["value"] == "VIP"
    assert by_field_op[(cust_id, "BETWEEN")]["value"] == ["A", "Z"]
    # Param trỏ field không có + param không có filter_column đều bị bỏ qua.
    assert len(filters) == 3
    # BETWEEN thiếu đầu mút -> lỗi rõ ràng thay vì lọc sai lặng lẽ.
    with pytest.raises(ServiceError):
        build_param_filters({"P_BETWEEN": {"from": "A"}}, params, bundle)


# ---------------------------------------------------------------------------
# Layout Viewer
# ---------------------------------------------------------------------------


def _dump(component) -> str:
    import json

    def conv(obj):
        if hasattr(obj, "to_plotly_json"):
            return obj.to_plotly_json()
        if isinstance(obj, (list, tuple)):
            return [conv(o) for o in obj]
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        return obj

    return json.dumps(conv(component), ensure_ascii=False, default=str)


def _find_by_id(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            found = _find_by_id(child, target_id)
            if found is not None:
                return found
    elif children is not None:
        return _find_by_id(children, target_id)
    return None


def test_viewer_layout_semantic_hides_classic_export(viewer_sem_env, monkeypatch) -> None:
    import app.ui.pages.report_viewer as page

    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, _vis = _publish_studio_report(ctxs["owner"], ver_id, bundle, [_table_visual(bundle)])
    monkeypatch.setattr(page, "get_current_ctx", lambda: ctxs["viewer"])
    comp = page.layout(report_id=report_id)
    controls = _find_by_id(comp, "viewer-export-controls")
    assert controls is not None
    assert (controls.style or {}).get("display") == "none"
    text = _dump(comp)
    assert "Xem báo cáo" in text
    assert "Nhập tham số và bấm Xem báo cáo." in text


def test_viewer_layout_semantic_sql_tab_admin_only(viewer_sem_env, monkeypatch) -> None:
    import app.ui.pages.report_viewer as page

    _, ds_id, ctxs = viewer_sem_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    report_id, _vid, _vis = _publish_studio_report(ctxs["owner"], ver_id, bundle, [_table_visual(bundle)])
    monkeypatch.setattr(page, "get_current_ctx", lambda: ctxs["admin"])
    assert "SQL thực hiện" in _dump(page.layout(report_id=report_id))
    monkeypatch.setattr(page, "get_current_ctx", lambda: ctxs["viewer"])
    assert "SQL thực hiện" not in _dump(page.layout(report_id=report_id))


def test_viewer_layout_classic_shows_export(viewer_sem_env, monkeypatch) -> None:
    import app.ui.pages.report_viewer as page

    engine, ds_id, ctxs = viewer_sem_env
    report_id, _tpl_id, _ver_id = _make_classic_report(ctxs["admin"], ds_id, engine)
    monkeypatch.setattr(page, "get_current_ctx", lambda: ctxs["viewer"])
    comp = page.layout(report_id=report_id)
    controls = _find_by_id(comp, "viewer-export-controls")
    assert controls is not None
    assert (controls.style or {}).get("display") != "none"


def test_sql_tab_callback_registered_on_handle_sql_tab_render() -> None:
    """Hồi quy (Bước 6, e2e): decorator @callback của tab SQL phải gắn đúng
    handle_sql_tab_render, không gắn nhầm helper _render_sql_field.

    Khi helper nằm giữa decorator và hàm thật, Dash gọi helper với 1 arg
    (run_store) -> TypeError 'missing text' -> 500 mỗi lần mở tab SQL.
    Kiểm tra tĩnh bằng AST (không dựa vào GLOBAL_CALLBACK_LIST).
    """
    import ast

    src = Path("app/ui/pages/report_viewer.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    sql_cb_funcs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and getattr(dec.func, "id", "") == "callback":
                for arg in dec.args:
                    if (
                        isinstance(arg, ast.Call)
                        and getattr(arg.func, "id", "") == "Output"
                        and len(arg.args) >= 1
                        and isinstance(arg.args[0], ast.Constant)
                        and arg.args[0].value == "viewer-sql-container"
                    ):
                        sql_cb_funcs.append(node.name)
    assert sql_cb_funcs == ["handle_sql_tab_render"], sql_cb_funcs
    # Helper không được mang decorator callback nào.
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_render_sql_field":
            assert node.decorator_list == [], "helper _render_sql_field bị gắn decorator"
