"""Tests cho Semantic Model Service — Bước 3 & Bước 4 task 106 (test viết trước)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.context import Ctx, Role
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_data_source, recon_user
from app.engine.catalog import invalidate_catalog_cache
from app.schemas.errors import ErrorCode


@pytest.fixture
def sm_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    invalidate_catalog_cache()
    db_file = tmp_path / "sm_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    src_db = tmp_path / "star_src.db"

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
                """
                CREATE TABLE DIM_CUSTOMER (
                    CUSTOMER_ID INTEGER PRIMARY KEY,
                    CUSTOMER_NAME TEXT NOT NULL,
                    ORG_CODE TEXT NOT NULL
                )
                """
            )
        )
        sconn.execute(
            text(
                """
                CREATE TABLE DIM_DATE (
                    DATE_ID INTEGER PRIMARY KEY,
                    CAL_DATE DATE NOT NULL,
                    MONTH_NUM INTEGER NOT NULL
                )
                """
            )
        )
        sconn.execute(
            text(
                """
                CREATE TABLE FACT_SALES (
                    SALES_ID INTEGER PRIMARY KEY,
                    CUSTOMER_ID INTEGER NOT NULL,
                    DATE_ID INTEGER NOT NULL,
                    TX_DATE DATETIME NOT NULL,
                    QUANTITY INTEGER NOT NULL,
                    REVENUE NUMERIC NOT NULL,
                    FOREIGN KEY (CUSTOMER_ID) REFERENCES DIM_CUSTOMER(CUSTOMER_ID),
                    FOREIGN KEY (DATE_ID) REFERENCES DIM_DATE(DATE_ID)
                )
                """
            )
        )
        sconn.execute(
            text(
                "INSERT INTO DIM_CUSTOMER VALUES (1, 'Cong ty A', 'BDP'), (2, 'Cong ty B', 'HCM')"
            )
        )
        sconn.execute(text("INSERT INTO DIM_DATE VALUES (20260101, '2026-01-01', 1)"))
        sconn.execute(
            text(
                "INSERT INTO FACT_SALES VALUES "
                "(100, 1, 20260101, '2026-01-01 10:00:00', 5, 500000), "
                "(101, 2, 20260101, '2026-01-01 11:00:00', 2, 200000)"
            )
        )

    import app.services.semantic_model  # noqa: F401

    for mod_path in (
        "app.db.engine",
        "app.services.perm",
        "app.services.menu_sync",
        "app.engine.catalog",
        "app.services.semantic_model",
    ):
        monkeypatch.setattr(f"{mod_path}.get_recon_engine", lambda: engine)

    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
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

    ctxs = {
        "admin": Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN]),
        "owner": Ctx(user_id=2, username="owner", full_name="Owner", roles=[Role.TEMPLATE_OWNER]),
        "viewer": Ctx(user_id=3, username="viewer", full_name="Viewer", roles=[Role.VIEWER]),
    }
    yield engine, ds_id, ctxs
    src_engine.dispose()
    engine.dispose()


def test_permissions_and_create_model_no_secret_leak(sm_env) -> None:
    from app.services.semantic_model import create_model, get_model, list_models

    engine, ds_id, ctxs = sm_env

    # Unauthenticated & Viewer bị chặn
    res_unauth = list_models(None)  # type: ignore[arg-type]
    assert not res_unauth.ok and res_unauth.code == ErrorCode.UNAUTHENTICATED

    res_viewer = create_model(
        ctxs["viewer"],
        {"code": "M_SALES", "name": "Sales Model", "data_source_id": ds_id},
    )
    assert not res_viewer.ok and res_viewer.code == ErrorCode.FORBIDDEN

    # Owner tạo model thành công
    res = create_model(
        ctxs["owner"],
        {
            "code": "M_SALES",
            "name": "Mô hình doanh thu",
            "description": "Star schema bán hàng",
            "data_source_id": ds_id,
        },
    )
    assert res.ok, res.message
    data = res.data
    assert data["code"] == "M_SALES"
    assert data["active_version_id"] is None
    assert data["draft_version"]["version_no"] == 1
    assert data["draft_version"]["status"] == "DRAFT"
    assert "top_secret_pw" not in str(data)

    # Trùng code bị từ chối
    dup = create_model(
        ctxs["owner"],
        {"code": "M_SALES", "name": "Trùng", "data_source_id": ds_id},
    )
    assert not dup.ok and dup.code == ErrorCode.CONFLICT

    # Audit log được ghi
    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT COUNT(*) FROM RECON_AUDIT_LOG WHERE ENTITY = 'RECON_RPT_MODEL'")
        ).scalar_one()
        assert cnt == 1

    fetched = get_model(ctxs["owner"], data["id"])
    assert fetched.ok and fetched.data["code"] == "M_SALES"


def test_optimistic_concurrency_and_immutable_code(sm_env) -> None:
    from app.services.semantic_model import create_model, save_draft_state

    _, ds_id, ctxs = sm_env
    created = create_model(
        ctxs["owner"],
        {"code": "M_CONC", "name": "Ban đầu", "data_source_id": ds_id},
    )
    assert created.ok
    ver_id = created.data["draft_version"]["id"]
    ver_rv = created.data["draft_version"]["row_version"]

    # Đổi code bị từ chối
    bad = save_draft_state(
        ctxs["owner"],
        ver_id,
        {"code": "M_OTHER", "name": "Đổi tên", "expected_row_version": ver_rv},
    )
    assert not bad.ok and bad.code == ErrorCode.VALIDATION_ERROR

    # Lưu hợp lệ tăng row_version
    ok1 = save_draft_state(
        ctxs["owner"],
        ver_id,
        {"name": "Tên mới v1", "expected_row_version": ver_rv},
    )
    assert ok1.ok
    assert ok1.data["draft_version"]["row_version"] == ver_rv + 1

    # Lưu lại với row_version cũ -> STALE_DATA, không ghi đè
    stale = save_draft_state(
        ctxs["owner"],
        ver_id,
        {"name": "Ghi đè cũ", "expected_row_version": ver_rv},
    )
    assert not stale.ok and stale.code == ErrorCode.STALE_DATA


def test_clone_and_archive_model(sm_env) -> None:
    from app.services.semantic_model import archive_model, clone_model, create_model, list_models

    _, ds_id, ctxs = sm_env
    created = create_model(
        ctxs["admin"],
        {"code": "M_ORIG", "name": "Gốc", "data_source_id": ds_id},
    )
    assert created.ok
    orig_id = created.data["id"]

    cloned = clone_model(
        ctxs["owner"],
        orig_id,
        {"code": "M_CLONE", "name": "Bản sao"},
    )
    assert cloned.ok, cloned.message
    assert cloned.data["code"] == "M_CLONE"
    assert cloned.data["active_version_id"] is None
    assert cloned.data["draft_version"]["status"] == "DRAFT"

    archived = archive_model(ctxs["admin"], orig_id)
    assert archived.ok
    assert archived.data["is_archived"] is True

    active_only = list_models(ctxs["owner"], include_archived=False)
    assert active_only.ok
    assert [m["code"] for m in active_only.data] == ["M_CLONE"]


def test_add_remove_table_with_lookup_labels_and_grain(sm_env) -> None:
    from app.db.metadata import recon_lookup_code, recon_lookup_type
    from app.services.lookup import _col_mapping_cache
    from app.services.semantic_model import (
        add_table_to_draft,
        create_model,
        get_model_version_detail,
        remove_table_from_draft,
        update_table_props,
    )

    _col_mapping_cache.clear()
    engine, ds_id, ctxs = sm_env
    with engine.begin() as conn:
        conn.execute(
            recon_lookup_type.insert().values(
                LOOKUP_TYPE="DB_COLUMN_MAPPING",
                TYPE_NAME="Mapping cột DB",
                IS_SYSTEM="N",
                IS_ACTIVE="Y",
            )
        )
        conn.execute(
            recon_lookup_code.insert().values(
                LOOKUP_TYPE="DB_COLUMN_MAPPING",
                LOOKUP_CODE="REVENUE",
                MEANING="Doanh thu hóa đơn",
                DISPLAY_ORDER=1,
                IS_DEFAULT="N",
                IS_SYSTEM="N",
                IS_ACTIVE="Y",
            )
        )

    created = create_model(ctxs["owner"], {"code": "M_TBL", "name": "Table Test", "data_source_id": ds_id})
    ver_id = created.data["draft_version"]["id"]

    add_fact = add_table_to_draft(ctxs["owner"], ver_id, {"source_object": "FACT_SALES"})
    assert add_fact.ok, add_fact.message
    fact = add_fact.data
    assert fact["table_role"] == "FACT"
    assert fact["row_estimate"] == 2
    by_col = {f["source_column"]: f for f in fact["fields"]}
    assert by_col["SALES_ID"]["is_pk"] is True
    assert by_col["CUSTOMER_ID"]["is_fk"] is True
    assert by_col["REVENUE"]["display_name"] == "Doanh thu hóa đơn"
    assert by_col["REVENUE"]["data_type"] == "NUMBER"

    # Thêm trùng bị từ chối
    dup = add_table_to_draft(ctxs["owner"], ver_id, {"source_object": "FACT_SALES"})
    assert not dup.ok and dup.code == ErrorCode.CONFLICT

    # Cập nhật Grain hợp lệ & không hợp lệ
    bad_grain = update_table_props(
        ctxs["owner"],
        fact["id"],
        {"grain_desc": "Một dòng bán hàng", "grain_keys": ["NO_SUCH_COL"]},
    )
    assert not bad_grain.ok and bad_grain.code == ErrorCode.VALIDATION_ERROR

    ok_grain = update_table_props(
        ctxs["owner"],
        fact["id"],
        {
            "table_role": "FACT",
            "grain_desc": "Một dòng là một giao dịch bán hàng",
            "grain_keys": ["SALES_ID"],
            "default_date_field": "TX_DATE",
        },
    )
    assert ok_grain.ok and ok_grain.data["grain_keys"] == ["SALES_ID"]

    rem = remove_table_from_draft(ctxs["owner"], fact["id"])
    assert rem.ok
    detail = get_model_version_detail(ctxs["owner"], ver_id)
    assert detail.data["tables"] == []


def test_field_aggregation_rules_virtual_date_and_sort_by(sm_env) -> None:
    from app.services.semantic_model import add_table_to_draft, create_model, update_field_props

    _, ds_id, ctxs = sm_env
    ver_id = create_model(ctxs["owner"], {"code": "M_FLD", "name": "Field Test", "data_source_id": ds_id}).data[
        "draft_version"
    ]["id"]
    fact = add_table_to_draft(ctxs["owner"], ver_id, {"source_object": "FACT_SALES"}).data
    dim = add_table_to_draft(ctxs["owner"], ver_id, {"source_object": "DIM_CUSTOMER"}).data

    f_fields = {f["source_column"]: f for f in fact["fields"]}
    d_fields = {f["source_column"]: f for f in dim["fields"]}

    # SUM bị khóa với STRING
    bad_sum = update_field_props(ctxs["owner"], d_fields["CUSTOMER_NAME"]["id"], {"default_agg": "SUM"})
    assert not bad_sum.ok and bad_sum.code == ErrorCode.VALIDATION_ERROR

    # Virtual Date Hierarchy chỉ hợp lệ cho DATE/DATETIME
    bad_dh = update_field_props(ctxs["owner"], d_fields["CUSTOMER_NAME"]["id"], {"enable_date_hierarchy": True})
    assert not bad_dh.ok and bad_dh.code == ErrorCode.VALIDATION_ERROR

    ok_dh = update_field_props(ctxs["owner"], f_fields["TX_DATE"]["id"], {"enable_date_hierarchy": True})
    assert ok_dh.ok and ok_dh.data["enable_date_hierarchy"] is True

    # Sort By Field hợp lệ vs tự trỏ chính mình
    self_sort = update_field_props(
        ctxs["owner"],
        d_fields["CUSTOMER_NAME"]["id"],
        {"sort_by_field_id": d_fields["CUSTOMER_NAME"]["id"]},
    )
    assert not self_sort.ok and self_sort.code == ErrorCode.VALIDATION_ERROR

    ok_sort = update_field_props(
        ctxs["owner"],
        d_fields["CUSTOMER_NAME"]["id"],
        {"sort_by_field_id": d_fields["CUSTOMER_ID"]["id"], "folder": "Khách hàng"},
    )
    assert ok_sort.ok and ok_sort.data["sort_by_field_id"] == d_fields["CUSTOMER_ID"]["id"]


def test_measures_and_rls_metadata(sm_env) -> None:
    from app.services.semantic_model import (
        add_table_to_draft,
        create_model,
        delete_measure,
        delete_rls_policy,
        upsert_measure,
        upsert_rls_policy,
    )

    _, ds_id, ctxs = sm_env
    ver_id = create_model(ctxs["owner"], {"code": "M_MEAS", "name": "Measure Test", "data_source_id": ds_id}).data[
        "draft_version"
    ]["id"]
    fact = add_table_to_draft(ctxs["owner"], ver_id, {"source_object": "FACT_SALES"}).data
    dim = add_table_to_draft(ctxs["owner"], ver_id, {"source_object": "DIM_CUSTOMER"}).data
    f_cols = {f["source_column"]: f for f in fact["fields"]}
    d_cols = {f["source_column"]: f for f in dim["fields"]}

    # Simple Measure SUM trên STRING -> chặn
    bad_m = upsert_measure(
        ctxs["owner"],
        ver_id,
        {
            "code": "SUM_NAME",
            "name": "Sum Name",
            "measure_type": "SIMPLE",
            "base_field_id": d_cols["CUSTOMER_NAME"]["id"],
            "aggregation": "SUM",
        },
    )
    assert not bad_m.ok and bad_m.code == ErrorCode.VALIDATION_ERROR

    m_rev = upsert_measure(
        ctxs["owner"],
        ver_id,
        {
            "code": "TOTAL_REVENUE",
            "name": "Tổng doanh thu",
            "table_id": fact["id"],
            "measure_type": "SIMPLE",
            "base_field_id": f_cols["REVENUE"]["id"],
            "aggregation": "SUM",
            "format_mask": "#,##0",
        },
    )
    assert m_rev.ok, m_rev.message

    m_qty = upsert_measure(
        ctxs["owner"],
        ver_id,
        {
            "code": "TOTAL_QTY",
            "name": "Tổng số lượng",
            "table_id": fact["id"],
            "measure_type": "SIMPLE",
            "base_field_id": f_cols["QUANTITY"]["id"],
            "aggregation": "SUM",
        },
    )
    assert m_qty.ok

    # Calculated AST Measure hợp lệ
    m_avg_price = upsert_measure(
        ctxs["owner"],
        ver_id,
        {
            "code": "AVG_PRICE",
            "name": "Đơn giá bình quân",
            "table_id": fact["id"],
            "measure_type": "CALCULATED",
            "expr_json": {
                "op": "DIVIDE",
                "left": {"op": "MEASURE", "measure_id": m_rev.data["id"]},
                "right": {"op": "MEASURE", "measure_id": m_qty.data["id"]},
            },
        },
    )
    assert m_avg_price.ok, m_avg_price.message

    # AST toán tử cấm / SQL injection -> chặn
    bad_ast = upsert_measure(
        ctxs["owner"],
        ver_id,
        {
            "code": "BAD_SQL",
            "name": "Bad SQL",
            "measure_type": "CALCULATED",
            "expr_json": {"op": "RAW_SQL", "sql": "SELECT 1 FROM DUAL"},
        },
    )
    assert not bad_ast.ok and bad_ast.code == ErrorCode.SQL_NOT_ALLOWED

    # Vòng lặp phụ thuộc Calculated Measure -> chặn
    m1 = upsert_measure(
        ctxs["owner"],
        ver_id,
        {
            "code": "CALC_1",
            "name": "Calc 1",
            "measure_type": "CALCULATED",
            "expr_json": {"op": "MEASURE", "measure_id": m_avg_price.data["id"]},
        },
    )
    assert m1.ok
    loop_upd = upsert_measure(
        ctxs["owner"],
        ver_id,
        {
            "id": m_avg_price.data["id"],
            "code": "AVG_PRICE",
            "name": "Đơn giá bình quân",
            "table_id": fact["id"],
            "measure_type": "CALCULATED",
            "expr_json": {"op": "MEASURE", "measure_id": m1.data["id"]},
        },
    )
    assert not loop_upd.ok and loop_upd.code == ErrorCode.VALIDATION_ERROR

    assert delete_measure(ctxs["owner"], m1.data["id"]).ok

    # RLS Metadata Scaffold V1
    bad_rls = upsert_rls_policy(
        ctxs["owner"],
        ver_id,
        {"table_id": dim["id"], "column_name": "MISSING_COL", "policy_type": "ORG_SCOPE_HOOK"},
    )
    assert not bad_rls.ok and bad_rls.code == ErrorCode.COLUMN_NOT_FOUND

    ok_rls = upsert_rls_policy(
        ctxs["owner"],
        ver_id,
        {
            "table_id": dim["id"],
            "column_name": "ORG_CODE",
            "policy_type": "ORG_SCOPE_HOOK",
            "scope_attr": "allowed_orgs",
            "admin_bypass": True,
        },
    )
    assert ok_rls.ok and ok_rls.data["column_name"] == "ORG_CODE"
    assert delete_rls_policy(ctxs["owner"], ok_rls.data["id"]).ok
