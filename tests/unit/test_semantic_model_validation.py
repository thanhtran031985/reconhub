"""Tests cho Relationship Validation 2 tầng, Model Validate, Diff, Impact & Publish (Bước 5 task 106)."""

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
def val_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    invalidate_catalog_cache()
    db_file = tmp_path / "val_meta.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    src_db = tmp_path / "val_star.db"

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
                    CUSTOMER_ID INTEGER NOT NULL,
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
                    MONTH_NUM INTEGER NOT NULL
                )
                """
            )
        )
        sconn.execute(
            text(
                """
                CREATE TABLE DIM_REGION (
                    REGION_ID INTEGER PRIMARY KEY,
                    REGION_NAME TEXT NOT NULL
                )
                """
            )
        )
        sconn.execute(
            text(
                """
                CREATE TABLE FACT_SALES (
                    SALES_ID INTEGER PRIMARY KEY,
                    CUSTOMER_ID INTEGER,
                    ALT_CUSTOMER_ID INTEGER,
                    DATE_ID INTEGER NOT NULL,
                    REGION_ID INTEGER NOT NULL,
                    REVENUE NUMERIC NOT NULL
                )
                """
            )
        )
        # DIM_CUSTOMER cố ý chèn 1 key sạch (1, 2) và sau này test có thể chèn trùng để kiểm tra profiling
        sconn.execute(text("INSERT INTO DIM_CUSTOMER VALUES (1, 'Cong ty A', 'BDP'), (2, 'Cong ty B', 'HCM')"))
        sconn.execute(text("INSERT INTO DIM_DATE VALUES (20260101, 1)"))
        sconn.execute(text("INSERT INTO DIM_REGION VALUES (10, 'Mien Bac')"))
        # Có 1 orphan CUSTOMER_ID = 999 và 1 NULL để kiểm tra profiling WARNING
        sconn.execute(
            text(
                "INSERT INTO FACT_SALES VALUES "
                "(1, 1, 1, 20260101, 10, 1000), "
                "(2, 2, 2, 20260101, 10, 2000), "
                "(3, 999, 1, 20260101, 10, 500), "
                "(4, NULL, 1, 20260101, 10, 300)"
            )
        )

    import app.services.semantic_model  # noqa: F401
    import app.services.semantic_model_validate  # noqa: F401

    for mod_path in (
        "app.db.engine",
        "app.services.perm",
        "app.services.menu_sync",
        "app.engine.catalog",
        "app.services.semantic_model",
        "app.services.semantic_model_validate",
    ):
        monkeypatch.setattr(f"{mod_path}.get_recon_engine", lambda: engine)

    from app.services.menu_sync import sync_from_code
    from app.services.perm import clear_perm_cache
    from tests.conftest import seed_perm_basics

    sync_from_code(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, uname in [(1, "admin"), (2, "owner")]:
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
                NAME="VAL_SQLITE",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="SQLITE",
                FILE_PATH=str(src_db),
                USERNAME="ro",
                PASSWORD_ENC=encrypt_secret("pw"),
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

    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["TEMPLATE_OWNER"]})
    clear_perm_cache()
    owner = Ctx(user_id=2, username="owner", full_name="Owner", roles=[Role.TEMPLATE_OWNER])
    admin = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])
    yield engine, src_engine, ds_id, owner, admin
    src_engine.dispose()
    engine.dispose()


def test_relationship_tier1_datatype_loop_and_ambiguity(val_env) -> None:
    from app.services.semantic_model import add_table_to_draft, create_model
    from app.services.semantic_model_validate import (
        delete_relationship,
        upsert_relationship,
        validate_model,
    )

    _, _, ds_id, owner, _ = val_env
    ver_id = create_model(owner, {"code": "M_REL", "name": "Rel Test", "data_source_id": ds_id}).data[
        "draft_version"
    ]["id"]

    fact = add_table_to_draft(owner, ver_id, {"source_object": "FACT_SALES", "table_role": "FACT"}).data
    dim_cust = add_table_to_draft(owner, ver_id, {"source_object": "DIM_CUSTOMER", "table_role": "DIMENSION"}).data
    dim_date = add_table_to_draft(owner, ver_id, {"source_object": "DIM_DATE", "table_role": "DIMENSION"}).data

    # 1. Sai kiểu dữ liệu (NUMBER vs STRING) -> ERROR
    bad_dtype = upsert_relationship(
        owner,
        ver_id,
        {
            "name": "Bad Dtype",
            "from_table_id": fact["id"],
            "from_column": "CUSTOMER_ID",
            "to_table_id": dim_cust["id"],
            "to_column": "CUSTOMER_NAME",
        },
    )
    assert not bad_dtype.ok and bad_dtype.code == ErrorCode.VALIDATION_ERROR

    # 2. Quan hệ hợp lệ FACT_SALES -> DIM_CUSTOMER
    r1 = upsert_relationship(
        owner,
        ver_id,
        {
            "name": "Sales to Customer",
            "from_table_id": fact["id"],
            "from_column": "CUSTOMER_ID",
            "to_table_id": dim_cust["id"],
            "to_column": "CUSTOMER_ID",
        },
    )
    assert r1.ok, r1.message

    # 3. Hai quan hệ active giữa cùng 2 bảng -> ambiguous active path
    r2_active = upsert_relationship(
        owner,
        ver_id,
        {
            "name": "Sales Alt Customer",
            "from_table_id": fact["id"],
            "from_column": "ALT_CUSTOMER_ID",
            "to_table_id": dim_cust["id"],
            "to_column": "CUSTOMER_ID",
            "is_active": True,
        },
    )
    assert r2_active.ok
    v_amb = validate_model(owner, ver_id, check_physical=False)
    assert v_amb.ok
    assert v_amb.data["status"] == "INVALID"
    assert any(i["code"] == ErrorCode.AMBIGUOUS_PATH for i in v_amb.data["issues"])

    # Tắt is_active quan hệ thứ 2 thì hết ambiguous
    r2_inactive = upsert_relationship(
        owner,
        ver_id,
        {
            "id": r2_active.data["id"],
            "name": "Sales Alt Customer",
            "from_table_id": fact["id"],
            "from_column": "ALT_CUSTOMER_ID",
            "to_table_id": dim_cust["id"],
            "to_column": "CUSTOMER_ID",
            "is_active": False,
        },
    )
    assert r2_inactive.ok
    assert delete_relationship(owner, r2_active.data["id"]).ok

    # 4. Vòng lặp quan hệ (A -> B -> C -> A)
    r_fd = upsert_relationship(
        owner,
        ver_id,
        {
            "name": "Fact to Date",
            "from_table_id": fact["id"],
            "from_column": "DATE_ID",
            "to_table_id": dim_date["id"],
            "to_column": "DATE_ID",
        },
    )
    r_cd = upsert_relationship(
        owner,
        ver_id,
        {
            "name": "Cust to Date",
            "from_table_id": dim_cust["id"],
            "from_column": "CUSTOMER_ID",
            "to_table_id": dim_date["id"],
            "to_column": "DATE_ID",
        },
    )
    assert r_fd.ok and r_cd.ok
    v_loop = validate_model(owner, ver_id, check_physical=False)
    assert v_loop.ok
    assert v_loop.data["status"] == "INVALID"
    assert any(i["code"] == ErrorCode.RELATIONSHIP_LOOP for i in v_loop.data["issues"])


def test_relationship_tier2_data_profiling(val_env) -> None:
    from app.services.semantic_model import add_table_to_draft, create_model
    from app.services.semantic_model_validate import profile_relationship_data, upsert_relationship

    _, src_engine, ds_id, owner, _ = val_env
    ver_id = create_model(owner, {"code": "M_PROF", "name": "Profile", "data_source_id": ds_id}).data[
        "draft_version"
    ]["id"]
    fact = add_table_to_draft(owner, ver_id, {"source_object": "FACT_SALES", "table_role": "FACT"}).data
    dim_cust = add_table_to_draft(owner, ver_id, {"source_object": "DIM_CUSTOMER", "table_role": "DIMENSION"}).data

    rel = upsert_relationship(
        owner,
        ver_id,
        {
            "name": "Sales to Customer",
            "from_table_id": fact["id"],
            "from_column": "CUSTOMER_ID",
            "to_table_id": dim_cust["id"],
            "to_column": "CUSTOMER_ID",
        },
    ).data

    prof = profile_relationship_data(owner, rel["id"])
    assert prof.ok, prof.message
    checks = {c["key"]: c for c in prof.data["checks"]}
    assert checks["datatype_compat"]["status"] == "PASS"
    assert checks["target_uniqueness"]["status"] == "PASS"
    assert checks["null_rate"]["status"] == "WARNING"
    assert checks["orphan_fact_keys"]["status"] == "WARNING"
    assert prof.data["metrics"]["orphan_count"] == 1
    assert prof.data["metrics"]["null_count"] == 1

    # Thêm key trùng vào DIM_CUSTOMER -> target_uniqueness ERROR
    with src_engine.begin() as sconn:
        sconn.execute(text("INSERT INTO DIM_CUSTOMER VALUES (1, 'Cong ty A dup', 'BDP')"))

    prof_dup = profile_relationship_data(owner, rel["id"])
    assert prof_dup.ok
    checks2 = {c["key"]: c for c in prof_dup.data["checks"]}
    assert checks2["target_uniqueness"]["status"] == "ERROR"


def test_validate_publish_diff_impact_and_reopen_draft(val_env) -> None:
    from app.services.semantic_model import (
        add_table_to_draft,
        create_model,
        diff_model_versions,
        impact_analysis,
        open_or_create_draft,
        update_field_props,
        update_table_props,
        upsert_measure,
    )
    from app.services.semantic_model_validate import (
        publish_model_version,
        upsert_relationship,
        validate_model,
    )

    engine, _, ds_id, owner, _ = val_env
    created = create_model(owner, {"code": "M_PUB", "name": "Publish Test", "data_source_id": ds_id}).data
    model_id = created["id"]
    v1_id = created["draft_version"]["id"]

    fact = add_table_to_draft(owner, v1_id, {"source_object": "FACT_SALES", "table_role": "FACT"}).data
    dim_date = add_table_to_draft(owner, v1_id, {"source_object": "DIM_DATE", "table_role": "DIMENSION"}).data
    upsert_relationship(
        owner,
        v1_id,
        {
            "name": "Sales to Date",
            "from_table_id": fact["id"],
            "from_column": "DATE_ID",
            "to_table_id": dim_date["id"],
            "to_column": "DATE_ID",
        },
    )
    f_rev = next(f for f in fact["fields"] if f["source_column"] == "REVENUE")
    upsert_measure(
        owner,
        v1_id,
        {
            "code": "SUM_REV",
            "name": "Tổng doanh thu",
            "table_id": fact["id"],
            "measure_type": "SIMPLE",
            "base_field_id": f_rev["id"],
            "aggregation": "SUM",
        },
    )

    # Fact chưa có Grain -> validate INVALID và publish bị chặn
    v_missing_grain = validate_model(owner, v1_id)
    assert v_missing_grain.ok and v_missing_grain.data["status"] == "INVALID"
    assert any(i["code"] == ErrorCode.GRAIN_REQUIRED for i in v_missing_grain.data["issues"])

    pub_fail = publish_model_version(owner, v1_id, {"change_note": "v1"})
    assert not pub_fail.ok and pub_fail.code == ErrorCode.GRAIN_REQUIRED

    # Bổ sung Grain -> validate VALID -> Publish thành công
    update_table_props(
        owner,
        fact["id"],
        {"grain_desc": "Một dòng bán hàng", "grain_keys": ["SALES_ID"]},
    )
    v_ok = validate_model(owner, v1_id)
    assert v_ok.ok and v_ok.data["status"] == "VALID"

    pub_empty_note = publish_model_version(owner, v1_id, {"change_note": ""})
    assert not pub_empty_note.ok and pub_empty_note.code == ErrorCode.VALIDATION_ERROR

    pub_ok = publish_model_version(owner, v1_id, {"change_note": "Phát hành v1 chuẩn"})
    assert pub_ok.ok, pub_ok.message
    assert pub_ok.data["active_version_id"] == v1_id

    # Không thể sửa version ACTIVE
    locked = update_table_props(owner, fact["id"], {"display_name": "Sửa trực tiếp"})
    assert not locked.ok and locked.code == ErrorCode.MODEL_VERSION_LOCKED

    # Mở lại Draft v2 từ v1 ACTIVE
    v2_bundle = open_or_create_draft(owner, model_id)
    assert v2_bundle.ok
    v2_id = v2_bundle.data["version"]["id"]
    assert v2_id != v1_id
    assert v2_bundle.data["version"]["version_no"] == 2
    assert v2_bundle.data["version"]["status"] == "DRAFT"

    # Ẩn trường REVENUE ở v2 -> diff phát hiện breaking change
    v2_fact = next(t for t in v2_bundle.data["tables"] if t["source_object"] == "FACT_SALES")
    v2_rev = next(f for f in v2_fact["fields"] if f["source_column"] == "REVENUE")
    update_field_props(owner, v2_rev["id"], {"field_role": "HIDDEN"})

    diff = diff_model_versions(owner, v2_id, v1_id)
    assert diff.ok
    assert any(c["change_type"] == "FIELD_HIDDEN_OR_REMOVED" for c in diff.data["breaking_changes"])

    # Impact Analysis an toàn khi chưa có RECON_RPT_VISUAL (trước Task 109)
    imp = impact_analysis(owner, model_id, v2_id)
    assert imp.ok
    assert imp.data["reports"] == []
    assert len(imp.data["breaking_changes"]) >= 1

    # Mô phỏng có bảng RECON_RPT_VISUAL + RECON_RPT_VISUAL_FIELD (như sau Task 109) -> trả dependency
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE RECON_RPT_VISUAL (
                    ID INTEGER PRIMARY KEY,
                    VERSION_ID INTEGER NOT NULL,
                    TITLE TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE RECON_RPT_VISUAL_FIELD (
                    ID INTEGER PRIMARY KEY,
                    VISUAL_ID INTEGER NOT NULL,
                    FIELD_ID INTEGER,
                    MEASURE_ID INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO RECON_REPORT (CODE, NAME, OWNER, DEFAULT_FAVORITE, IS_VISIBLE, IS_ACTIVE, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES ('RPT_1', 'Bao cao doanh thu', 'owner', 'N', 'Y', 'Y', 'owner', '2026-11-26 00:00:00', 'owner', '2026-11-26 00:00:00', 1)"
            )
        )
        rpt_id = conn.execute(text("SELECT ID FROM RECON_REPORT WHERE CODE='RPT_1'")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO RECON_REPORT_TEMPLATE (REPORT_ID, CODE, NAME, DISPLAY_ORDER, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES (:rid, 'T1', 'Mac dinh', 10, 'owner', '2026-11-26 00:00:00', 'owner', '2026-11-26 00:00:00', 1)"
            ),
            {"rid": rpt_id},
        )
        tpl_id = conn.execute(text("SELECT ID FROM RECON_REPORT_TEMPLATE WHERE REPORT_ID=:rid"), {"rid": rpt_id}).scalar_one()
        conn.execute(
            text(
                "INSERT INTO RECON_RPT_TPL_VER (TEMPLATE_ID, VERSION_NO, STATUS, TIMEOUT_SEC, PREVIEW_MAX_ROWS, EXPORT_MAX_ROWS, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES (:tid, 1, 'ACTIVE', 300, 100, 1000000, 'owner', '2026-11-26 00:00:00', 'owner', '2026-11-26 00:00:00', 1)"
            ),
            {"tid": tpl_id},
        )
        tver_id = conn.execute(text("SELECT ID FROM RECON_RPT_TPL_VER WHERE TEMPLATE_ID=:tid"), {"tid": tpl_id}).scalar_one()
        # Gắn thêm cột MODEL_VERSION_ID như Task 109 sẽ tạo
        conn.execute(text("ALTER TABLE RECON_RPT_TPL_VER ADD COLUMN MODEL_VERSION_ID INTEGER"))
        conn.execute(
            text("UPDATE RECON_RPT_TPL_VER SET MODEL_VERSION_ID = :mvid WHERE ID = :tver"),
            {"mvid": v1_id, "tver": tver_id},
        )
        conn.execute(
            text("INSERT INTO RECON_RPT_VISUAL (ID, VERSION_ID, TITLE) VALUES (1, :tver, 'Bieu do doanh thu')"),
            {"tver": tver_id},
        )
        conn.execute(
            text("INSERT INTO RECON_RPT_VISUAL_FIELD (ID, VISUAL_ID, FIELD_ID, MEASURE_ID) VALUES (1, 1, :fid, NULL)"),
            {"fid": f_rev["id"]},
        )

    imp2 = impact_analysis(owner, model_id, v2_id)
    assert imp2.ok
    assert len(imp2.data["reports"]) == 1
    assert imp2.data["reports"][0]["report_code"] == "RPT_1"
    assert len(imp2.data["visuals"]) == 1
    assert imp2.data["visuals"][0]["visual_title"] == "Bieu do doanh thu"

    # Publish v2 -> v1 chuyển sang ARCHIVED, v2 thành ACTIVE
    v2_valid = validate_model(owner, v2_id)
    assert v2_valid.ok and v2_valid.data["status"] in ("VALID", "WARNING")
    pub2 = publish_model_version(owner, v2_id, {"change_note": "Ẩn cột REVENUE"})
    assert pub2.ok and pub2.data["active_version_id"] == v2_id

    with engine.connect() as conn:
        v1_status = conn.execute(
            text("SELECT STATUS FROM RECON_RPT_MODEL_VER WHERE ID = :id"), {"id": v1_id}
        ).scalar_one()
    assert v1_status == "ARCHIVED"
