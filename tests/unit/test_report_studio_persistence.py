"""Tests cho schema Report Studio, migration 0019 và menu report_studio (Bước 1 task 109).

Viết trước theo plan: migration 0019 upgrade/downgrade, constraint
VISUAL_TYPE/SOURCE_TYPE, tương thích ngược report CUSTOM_SQL/VIEW/TABLE,
menu report_studio + schema-inspector/metadata-migration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.context import Ctx, Role
from app.core.crypto import encrypt_secret
from app.db.metadata import metadata, recon_data_source, recon_user
from app.engine.catalog import invalidate_catalog_cache
from app.schemas.errors import ErrorCode

ROOT = Path(__file__).resolve().parent.parent.parent


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _report_id(conn, code: str = "SALES_STUDIO") -> int:
    from app.db.metadata import recon_report

    now = _now()
    res = conn.execute(
        recon_report.insert().values(
            CODE=code,
            NAME="Báo cáo Studio",
            CATEGORY_CODE="SALES",
            OWNER="admin",
            DESCRIPTION="Báo cáo thiết kế từ Report Studio",
            DEFAULT_FAVORITE="N",
            IS_VISIBLE="Y",
            IS_ACTIVE="Y",
            CREATED_BY="admin",
            CREATED_AT=now,
            UPDATED_BY="admin",
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
    )
    return int(res.inserted_primary_key[0])


def _template_id(conn, report_id: int, code: str = "MAIN") -> int:
    from app.db.metadata import recon_report_template

    now = _now()
    res = conn.execute(
        recon_report_template.insert().values(
            REPORT_ID=report_id,
            CODE=code,
            NAME="Mẫu chính",
            DISPLAY_ORDER=10,
            ACTIVE_VERSION_ID=None,
            CREATED_BY="admin",
            CREATED_AT=now,
            UPDATED_BY="admin",
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
    )
    return int(res.inserted_primary_key[0])


def _version_id(conn, template_id: int, version_no: int = 1, source_type: str | None = None) -> int:
    from app.db.metadata import recon_rpt_tpl_ver

    now = _now()
    res = conn.execute(
        recon_rpt_tpl_ver.insert().values(
            TEMPLATE_ID=template_id,
            VERSION_NO=version_no,
            STATUS="DRAFT",
            DATA_SOURCE_ID=None,
            SOURCE_TYPE=source_type,
            SQL_TEXT=None,
            SOURCE_OWNER=None,
            SOURCE_OBJECT=None,
            TIMEOUT_SEC=300,
            PREVIEW_MAX_ROWS=100,
            EXPORT_MAX_ROWS=1000000,
            SQL_HASH=None,
            ACTIVATED_BY=None,
            ACTIVATED_AT=None,
            CREATED_BY="admin",
            CREATED_AT=now,
            UPDATED_BY="admin",
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
    )
    return int(res.inserted_primary_key[0])


def _visual_id(conn, version_id: int, code: str = "V_TABLE", visual_type: str = "TABLE") -> int:
    from app.db.metadata import recon_rpt_visual

    now = _now()
    res = conn.execute(
        recon_rpt_visual.insert().values(
            VERSION_ID=version_id,
            CODE=code,
            TITLE="Bảng doanh thu",
            VISUAL_TYPE=visual_type,
            DISPLAY_ORDER=10,
            GRID_SPAN=12,
            HEIGHT_SIZE="M",
            CONFIG_JSON=None,
            CREATED_AT=now,
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
    )
    return int(res.inserted_primary_key[0])


@pytest.fixture()
def schema_engine(tmp_path, monkeypatch):
    from app.db.engine import get_sqlite_engine

    db_file = tmp_path / "report_studio_schema.db"
    engine = get_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_report_studio_tables_in_metadata() -> None:
    assert {"RECON_RPT_VISUAL", "RECON_RPT_VISUAL_FIELD"} <= set(metadata.tables.keys())
    tpl_ver_cols = {c.name for c in metadata.tables["RECON_RPT_TPL_VER"].columns}
    assert "MODEL_VERSION_ID" in tpl_ver_cols
    run_cols = {c.name for c in metadata.tables["RECON_REPORT_RUN"].columns}
    assert {"VISUAL_ID", "QUERY_SPEC_JSON"} <= run_cols
    visual_cols = {c.name for c in metadata.tables["RECON_RPT_VISUAL"].columns}
    assert {
        "ID",
        "VERSION_ID",
        "CODE",
        "TITLE",
        "VISUAL_TYPE",
        "DISPLAY_ORDER",
        "GRID_SPAN",
        "HEIGHT_SIZE",
        "CONFIG_JSON",
        "ROW_VERSION",
        "CREATED_AT",
        "UPDATED_AT",
    } <= visual_cols
    field_cols = {c.name for c in metadata.tables["RECON_RPT_VISUAL_FIELD"].columns}
    assert {
        "ID",
        "VISUAL_ID",
        "WELL_ROLE",
        "FIELD_ID",
        "MEASURE_ID",
        "AGGREGATION",
        "DATE_PART",
        "ALIAS",
        "LABEL_OVERRIDE",
        "FORMAT_MASK",
        "SORT_DIRECTION",
        "DISPLAY_ORDER",
    } <= field_cols


def test_alembic_0019_upgrade_and_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "mig0019.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "test-secret-key-1234567890")
    from app.core.config import get_settings

    get_settings.cache_clear()
    cfg = _alembic_cfg(db_url)
    command.upgrade(cfg, "0018_semantic_model")

    engine = create_engine(db_url)
    try:
        before_tables = set(inspect(engine).get_table_names())
        assert "RECON_RPT_VISUAL" not in before_tables
        assert "RECON_RPT_VISUAL_FIELD" not in before_tables
        assert "MODEL_VERSION_ID" not in {c["name"] for c in inspect(engine).get_columns("RECON_RPT_TPL_VER")}
        assert "VISUAL_ID" not in {c["name"] for c in inspect(engine).get_columns("RECON_REPORT_RUN")}

        # Gieo vai trò TEMPLATE_OWNER nếu chưa có, để kiểm chứng seed quyền menu.
        with engine.begin() as conn:
            role_exists = conn.execute(
                text("SELECT 1 FROM RECON_ROLE WHERE CODE = 'TEMPLATE_OWNER'")
            ).scalar_one_or_none()
            if role_exists is None:
                conn.execute(
                    text("INSERT INTO RECON_ROLE (CODE, NAME, IS_SYSTEM, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                         "VALUES ('TEMPLATE_OWNER', 'Template Owner', 'N', 'SEED', :now, 'SEED', :now, 1)"),
                    {"now": _now()},
                )

        command.upgrade(cfg, "0019_report_studio")
        after_tables = set(inspect(engine).get_table_names())
        assert {"RECON_RPT_VISUAL", "RECON_RPT_VISUAL_FIELD"} <= after_tables
        assert "MODEL_VERSION_ID" in {c["name"] for c in inspect(engine).get_columns("RECON_RPT_TPL_VER")}
        run_cols = {c["name"] for c in inspect(engine).get_columns("RECON_REPORT_RUN")}
        assert {"VISUAL_ID", "QUERY_SPEC_JSON"} <= run_cols

        with engine.connect() as conn:
            menu = conn.execute(
                text("SELECT CODE, PATH, SOURCE_GROUP, SOURCE_ORDER FROM RECON_MENU WHERE CODE = 'report_studio'")
            ).mappings().one_or_none()
            assert menu is not None
            assert menu["PATH"] == "/report-studio"
            assert menu["SOURCE_GROUP"] == "CAU_HINH"
            assert int(menu["SOURCE_ORDER"]) == 47
            grant = conn.execute(
                text(
                    "SELECT 1 FROM RECON_ROLE_MENU rm JOIN RECON_ROLE r ON r.ID = rm.ROLE_ID "
                    "WHERE r.CODE = 'TEMPLATE_OWNER' AND rm.MENU_CODE = 'report_studio'"
                )
            ).scalar_one_or_none()
            assert grant == 1
            # Chạy lại upgrade phải idempotent (không nhân đôi menu/quyền).
            command.upgrade(cfg, "0019_report_studio")
            menu_count = conn.execute(
                text("SELECT COUNT(*) FROM RECON_MENU WHERE CODE = 'report_studio'")
            ).scalar_one()
            assert menu_count == 1

        command.downgrade(cfg, "0018_semantic_model")
        downgraded_tables = set(inspect(engine).get_table_names())
        assert "RECON_RPT_VISUAL" not in downgraded_tables
        assert "RECON_RPT_VISUAL_FIELD" not in downgraded_tables
        assert "MODEL_VERSION_ID" not in {c["name"] for c in inspect(engine).get_columns("RECON_RPT_TPL_VER")}
        assert "VISUAL_ID" not in {c["name"] for c in inspect(engine).get_columns("RECON_REPORT_RUN")}
        with engine.connect() as conn:
            grant_after = conn.execute(
                text(
                    "SELECT 1 FROM RECON_ROLE_MENU rm JOIN RECON_ROLE r ON r.ID = rm.ROLE_ID "
                    "WHERE r.CODE = 'TEMPLATE_OWNER' AND rm.MENU_CODE = 'report_studio'"
                )
            ).scalar_one_or_none()
            assert grant_after is None
    finally:
        engine.dispose()


def test_alembic_0019_downgrade_blocked_when_visuals_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "mig0019_blocked.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "test-secret-key-1234567890")
    from app.core.config import get_settings

    get_settings.cache_clear()
    cfg = _alembic_cfg(db_url)
    command.upgrade(cfg, "0019_report_studio")
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            vid = _version_id(conn, _template_id(conn, _report_id(conn)), source_type="SEMANTIC_MODEL")
            _visual_id(conn, vid)
        with pytest.raises(RuntimeError, match="visual"):
            command.downgrade(cfg, "0018_semantic_model")
    finally:
        engine.dispose()


def test_visual_check_constraints(schema_engine) -> None:
    from app.db.metadata import recon_rpt_tpl_ver, recon_rpt_visual

    with schema_engine.begin() as conn:
        vid = _version_id(conn, _template_id(conn, _report_id(conn)), source_type="SEMANTIC_MODEL")
        # SOURCE_TYPE SEMANTIC_MODEL được chấp nhận; loại lạ vẫn bị chặn.
        with pytest.raises(IntegrityError):
            conn.execute(
                recon_rpt_tpl_ver.update().where(recon_rpt_tpl_ver.c.ID == vid).values(SOURCE_TYPE="PROCEDURE")
            )
        # Report cũ CUSTOM_SQL/VIEW/TABLE vẫn chạy bình thường.
        old_vid = _version_id(conn, _template_id(conn, _report_id(conn, "OLD_RPT")), source_type="CUSTOM_SQL")
        assert old_vid
        with pytest.raises(IntegrityError):
            _visual_id(conn, vid, code="V_BAD_TYPE", visual_type="PIE")
        with pytest.raises(IntegrityError):
            conn.execute(
                recon_rpt_visual.insert().values(
                    VERSION_ID=vid,
                    CODE="V_BAD_SPAN",
                    TITLE="Sai span",
                    VISUAL_TYPE="TABLE",
                    DISPLAY_ORDER=10,
                    GRID_SPAN=5,
                    HEIGHT_SIZE="M",
                    CONFIG_JSON=None,
                    CREATED_AT=_now(),
                    UPDATED_AT=_now(),
                    ROW_VERSION=1,
                )
            )
        with pytest.raises(IntegrityError):
            conn.execute(
                recon_rpt_visual.insert().values(
                    VERSION_ID=vid,
                    CODE="V_BAD_HEIGHT",
                    TITLE="Sai height",
                    VISUAL_TYPE="TABLE",
                    DISPLAY_ORDER=10,
                    GRID_SPAN=6,
                    HEIGHT_SIZE="XL",
                    CONFIG_JSON=None,
                    CREATED_AT=_now(),
                    UPDATED_AT=_now(),
                    ROW_VERSION=1,
                )
            )


def test_visual_field_check_constraints(schema_engine) -> None:
    from app.db.metadata import recon_rpt_visual_field

    with schema_engine.begin() as conn:
        vid = _version_id(conn, _template_id(conn, _report_id(conn)), source_type="SEMANTIC_MODEL")
        vis_id = _visual_id(conn, vid)
        with pytest.raises(IntegrityError):
            conn.execute(
                recon_rpt_visual_field.insert().values(
                    VISUAL_ID=vis_id,
                    WELL_ROLE="Y",
                    FIELD_ID=None,
                    MEASURE_ID=None,
                    AGGREGATION="SUMX",
                    DATE_PART=None,
                    ALIAS="BAD_AGG",
                    LABEL_OVERRIDE=None,
                    FORMAT_MASK=None,
                    SORT_DIRECTION=None,
                    DISPLAY_ORDER=10,
                )
            )
        with pytest.raises(IntegrityError):
            conn.execute(
                recon_rpt_visual_field.insert().values(
                    VISUAL_ID=vis_id,
                    WELL_ROLE="X",
                    FIELD_ID=None,
                    MEASURE_ID=None,
                    AGGREGATION="SUM",
                    DATE_PART="DECADE",
                    ALIAS="BAD_PART",
                    LABEL_OVERRIDE=None,
                    FORMAT_MASK=None,
                    SORT_DIRECTION=None,
                    DISPLAY_ORDER=10,
                )
            )
        row = conn.execute(
            recon_rpt_visual_field.insert().values(
                VISUAL_ID=vis_id,
                WELL_ROLE="Y",
                FIELD_ID=None,
                MEASURE_ID=None,
                AGGREGATION="SUM",
                DATE_PART=None,
                ALIAS="GOOD",
                LABEL_OVERRIDE=None,
                FORMAT_MASK=None,
                SORT_DIRECTION="DESC",
                DISPLAY_ORDER=10,
            )
        )
        assert row.inserted_primary_key[0]


def test_menu_report_studio_registered_and_seeded() -> None:
    from app.ui.menus import MENU_BY_CODE, ROLE_MENUS_SEED

    assert "report_studio" in MENU_BY_CODE
    m = MENU_BY_CODE["report_studio"]
    assert m.group == "CAU_HINH"
    assert m.path == "/report-studio"
    assert m.order == 47
    assert "report_studio" in ROLE_MENUS_SEED["TEMPLATE_OWNER"]
    assert "report_studio" not in ROLE_MENUS_SEED["OPERATOR"]
    assert "report_studio" not in ROLE_MENUS_SEED["VIEWER"]


def test_schema_inspector_and_metadata_migration_include_studio_tables() -> None:
    from app.services.metadata_migration import CONFIG_ONLY_TABLES, RECON_TABLES_ORDER
    from app.services.schema_inspector import TABLE_DESCRIPTIONS, domain_for_table

    for name in ("RECON_RPT_VISUAL", "RECON_RPT_VISUAL_FIELD"):
        assert domain_for_table(name) == ("report", "Báo cáo")
        assert TABLE_DESCRIPTIONS.get(name)
        assert name in RECON_TABLES_ORDER
        assert name in CONFIG_ONLY_TABLES
    order = RECON_TABLES_ORDER
    assert order.index("RECON_RPT_MODEL") < order.index("RECON_RPT_TPL_VER")
    assert order.index("RECON_RPT_MODEL_RLS") < order.index("RECON_RPT_TPL_VER")
    assert order.index("RECON_RPT_TPL_VER") < order.index("RECON_RPT_VISUAL") < order.index("RECON_REPORT_RUN")
    assert order.index("RECON_RPT_VISUAL") < order.index("RECON_RPT_VISUAL_FIELD") < order.index("RECON_REPORT_RUN")

# ---------------------------------------------------------------------------
# Bước 2 — Service layer Report Studio (test viết trước, xem plan Bước 2)
# ---------------------------------------------------------------------------


@pytest.fixture()
def studio_svc_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """DB app + source star schema + model service, phục vụ test service studio."""
    invalidate_catalog_cache()
    db_file = tmp_path / "studio_svc.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    src_db = tmp_path / "studio_src.db"

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
                    SEGMENT TEXT NOT NULL,
                    ORG_CODE TEXT NOT NULL,
                    ROLE_COL TEXT NOT NULL
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
                "(1, 'Cong ty A', 'VIP', 'BDP', 'admin'), "
                "(2, 'Cong ty B', 'STD', 'HCM', 'admin')"
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
    now = _now()
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

    ctxs = {
        "admin": Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN]),
        "owner": Ctx(user_id=2, username="owner", full_name="Owner", roles=[Role.TEMPLATE_OWNER]),
        "viewer": Ctx(user_id=3, username="viewer", full_name="Viewer", roles=[Role.VIEWER]),
    }
    yield engine, ds_id, ctxs
    src_engine.dispose()
    engine.dispose()


def _build_published_model(owner_ctx, ds_id, code="M_SALES", hide_field=None):
    """Dựng model star schema qua service 106 rồi publish ACTIVE. Trả (ver_id, bundle)."""
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
    if hide_field is not None:
        alias, col = hide_field
        fld = next(f for f in tables[alias]["fields"] if f["source_column"] == col)
        assert update_field_props(owner_ctx, fld["id"], {"is_visible": False}).ok
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


def _create_studio_report(owner_ctx, ver_id, code="RPT_SALES"):
    from app.services.report_studio import create_studio_report

    res = create_studio_report(
        owner_ctx,
        {
            "code": code,
            "name": "Báo cáo doanh thu",
            "model_version_id": ver_id,
            "description": "Báo cáo Studio",
            "category_code": "SALES",
        },
    )
    assert res.ok, res.message
    return res.data


def test_create_studio_report_requires_active_model(studio_svc_env) -> None:
    from app.services.report_studio import create_studio_report
    from app.services.semantic_model import create_model

    _, ds_id, ctxs = studio_svc_env
    # Model mới chỉ có DRAFT -> tạo báo cáo Studio bị chặn.
    draft = create_model(
        ctxs["owner"], {"code": "M_DRAFT", "name": "Nháp", "data_source_id": ds_id}
    )
    assert draft.ok
    draft_ver = draft.data["draft_version"]["id"]
    blocked = create_studio_report(
        ctxs["owner"],
        {"code": "RPT_X", "name": "X", "model_version_id": draft_ver},
    )
    assert not blocked.ok and blocked.code == ErrorCode.MODEL_VERSION_LOCKED

    # Model ACTIVE -> tạo được, version 1 DRAFT, SOURCE_TYPE SEMANTIC_MODEL.
    ver_id, _ = _build_published_model(ctxs["owner"], ds_id)
    res = create_studio_report(
        ctxs["owner"],
        {"code": "RPT_SALES", "name": "Báo cáo doanh thu", "model_version_id": ver_id},
    )
    assert res.ok, res.message
    data = res.data
    assert data["version"]["status"] == "DRAFT"
    assert data["version"]["source_type"] == "SEMANTIC_MODEL"
    assert data["version"]["model_version_id"] == ver_id
    assert data["version"]["version_no"] == 1


def test_create_studio_report_viewer_forbidden_and_duplicate_code(studio_svc_env) -> None:
    from app.services.report_studio import create_studio_report

    _, ds_id, ctxs = studio_svc_env
    ver_id, _ = _build_published_model(ctxs["owner"], ds_id)
    denied = create_studio_report(
        ctxs["viewer"],
        {"code": "RPT_V", "name": "Viewer", "model_version_id": ver_id},
    )
    assert not denied.ok and denied.code == ErrorCode.FORBIDDEN
    _create_studio_report(ctxs["owner"], ver_id, "RPT_SALES")
    dup = create_studio_report(
        ctxs["owner"],
        {"code": "RPT_SALES", "name": "Trùng", "model_version_id": ver_id},
    )
    assert not dup.ok and dup.code == ErrorCode.CONFLICT


def test_list_studio_reports_only_semantic(studio_svc_env) -> None:
    from app.services.report_studio import list_studio_reports

    engine, ds_id, ctxs = studio_svc_env
    ver_id, _ = _build_published_model(ctxs["owner"], ds_id)
    _create_studio_report(ctxs["owner"], ver_id, "RPT_SALES")
    # Báo cáo cổ điển (CUSTOM_SQL) không được liệt kê ở Center Studio.
    with engine.begin() as conn:
        rid = _report_id(conn, "RPT_CLASSIC")
        tid = _template_id(conn, rid, "MAIN")
        _version_id(conn, tid, 1)
    listed = list_studio_reports(ctxs["owner"])
    assert listed.ok, listed.message
    codes = [r["code"] for r in listed.data]
    assert codes == ["RPT_SALES"]
    assert listed.data[0]["model_version_id"] == ver_id
    # Viewer không có menu report_studio -> bị chặn.
    denied = list_studio_reports(ctxs["viewer"])
    assert not denied.ok and denied.code == ErrorCode.FORBIDDEN


def test_open_or_create_draft_and_save_roundtrip(studio_svc_env) -> None:
    from app.services.report_studio import (
        get_studio_draft,
        open_or_create_studio_draft,
        save_studio_draft,
    )

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    report_id = created["report"]["id"]
    opened = open_or_create_studio_draft(ctxs["owner"], report_id)
    assert opened.ok, opened.message
    draft = opened.data
    assert draft["version"]["status"] == "DRAFT"
    assert draft["model"]["version"]["id"] == ver_id
    assert draft["visuals"] == []
    rv = draft["version"]["row_version"]

    saved = save_studio_draft(
        ctxs["owner"],
        draft["version"]["id"],
        {"row_version": rv, "visuals": [_table_visual(bundle)]},
    )
    assert saved.ok, saved.message
    assert saved.data["row_version"] == rv + 1
    assert saved.data["visual_count"] == 1

    again = get_studio_draft(ctxs["owner"], draft["version"]["id"])
    assert again.ok, again.message
    assert len(again.data["visuals"]) == 1
    vis = again.data["visuals"][0]
    assert vis["code"] == "V_TABLE" and vis["visual_type"] == "TABLE"
    assert vis["grid_span"] == 12 and vis["height_size"] == "M"
    assert len(vis["fields"]) == 2
    assert vis["fields"][0]["well_role"] == "X"
    assert vis["fields"][1]["measure_id"] == _measure_id(bundle, "REV_SUM")


def test_save_draft_stale_row_version_conflict(studio_svc_env) -> None:
    from app.services.report_studio import open_or_create_studio_draft, save_studio_draft

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    first = save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv, "visuals": [_table_visual(bundle)]}
    )
    assert first.ok, first.message
    # Lưu lại với row_version cũ -> STALE_DATA, không ghi đè.
    stale = save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv, "visuals": []}
    )
    assert not stale.ok and stale.code == ErrorCode.STALE_DATA
    # Lưu trên phiên bản ACTIVE -> không được sửa.
    from app.services.report_studio import publish_studio_report, validate_studio_report

    assert validate_studio_report(ctxs["owner"], vid).ok
    pub = publish_studio_report(ctxs["owner"], vid, {"change_note": "Phat hanh v1"})
    assert pub.ok, pub.message
    on_active = save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv + 1, "visuals": []}
    )
    assert not on_active.ok and on_active.code == ErrorCode.VALIDATION_ERROR


def test_save_draft_rejects_hidden_and_unknown_field(studio_svc_env) -> None:
    from app.services.report_studio import open_or_create_studio_draft, save_studio_draft

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(
        ctxs["owner"], ds_id, hide_field=("DIM_CUSTOMER", "CUSTOMER_NAME")
    )
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    hidden_id = _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")
    bad_hidden = save_studio_draft(
        ctxs["owner"],
        vid,
        {
            "row_version": rv,
            "visuals": [
                {
                    "code": "V_BAD",
                    "title": "Field ẩn",
                    "visual_type": "TABLE",
                    "fields": [{"well_role": "X", "field_id": hidden_id}],
                }
            ],
        },
    )
    assert not bad_hidden.ok and bad_hidden.code == ErrorCode.VALIDATION_ERROR
    bad_unknown = save_studio_draft(
        ctxs["owner"],
        vid,
        {
            "row_version": rv,
            "visuals": [
                {
                    "code": "V_BAD2",
                    "title": "Field lạ",
                    "visual_type": "TABLE",
                    "fields": [{"well_role": "X", "field_id": 999999}],
                }
            ],
        },
    )
    assert not bad_unknown.ok and bad_unknown.code == ErrorCode.VALIDATION_ERROR


def test_validate_and_publish_studio_report(studio_svc_env) -> None:
    from app.services.report_studio import (
        open_or_create_studio_draft,
        publish_studio_report,
        save_studio_draft,
        validate_studio_report,
    )

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    assert save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv, "visuals": [_table_visual(bundle)]}
    ).ok
    validated = validate_studio_report(ctxs["owner"], vid)
    assert validated.ok, validated.message
    assert validated.data["status"] == "DRY_RUN_OK"
    assert validated.data["errors"] == []
    # Phát hành thiếu change_note -> từ chối.
    no_note = publish_studio_report(ctxs["owner"], vid, {"change_note": "  "})
    assert not no_note.ok and no_note.code == ErrorCode.VALIDATION_ERROR
    pub = publish_studio_report(ctxs["owner"], vid, {"change_note": "Phát hành v1"})
    assert pub.ok, pub.message
    assert pub.data["version"]["status"] == "ACTIVE"
    assert pub.data["version"]["version_no"] == 1


def test_open_or_create_draft_clones_active_visuals(studio_svc_env) -> None:
    from app.services.report_studio import (
        open_or_create_studio_draft,
        publish_studio_report,
        save_studio_draft,
        validate_studio_report,
    )

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    report_id = created["report"]["id"]
    opened = open_or_create_studio_draft(ctxs["owner"], report_id)
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    assert save_studio_draft(
        ctxs["owner"],
        vid,
        {"row_version": rv, "visuals": [_table_visual(bundle), _table_visual(bundle, code="V_KPI", visual_type="KPI", fields=[{"well_role": "VALUE", "measure_id": _measure_id(bundle, "REV_SUM")}])]},
    ).ok
    assert validate_studio_report(ctxs["owner"], vid).ok
    assert publish_studio_report(ctxs["owner"], vid, {"change_note": "v1"}).ok
    # Mở draft sau khi phát hành -> clone ACTIVE thành DRAFT v2, giữ visuals.
    reopened = open_or_create_studio_draft(ctxs["owner"], report_id)
    assert reopened.ok, reopened.message
    assert reopened.data["version"]["version_no"] == 2
    assert reopened.data["version"]["status"] == "DRAFT"
    assert [v["code"] for v in reopened.data["visuals"]] == ["V_TABLE", "V_KPI"]
    kpi = reopened.data["visuals"][1]
    assert kpi["visual_type"] == "KPI"
    assert kpi["fields"][0]["well_role"] == "VALUE"


def test_preview_studio_visual_table(studio_svc_env) -> None:
    from app.services.report_studio import (
        open_or_create_studio_draft,
        preview_studio_visual,
        save_studio_draft,
    )

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    assert save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv, "visuals": [_table_visual(bundle)]}
    ).ok
    prev = preview_studio_visual(ctxs["owner"], vid, "V_TABLE", {})
    assert prev.ok, prev.message
    data = prev.data
    assert data["visual_code"] == "V_TABLE"
    assert data["row_count"] == 2
    assert data["truncated"] is False
    by_name = {r["CUSTOMER_NAME"]: r for r in data["rows"]}
    assert by_name["Cong ty A"]["REV_SUM"] == 800000
    assert by_name["Cong ty B"]["REV_SUM"] == 200000
    # Viewer không có quyền xem trước.
    denied = preview_studio_visual(ctxs["viewer"], vid, "V_TABLE", {})
    assert not denied.ok and denied.code == ErrorCode.FORBIDDEN


def test_preview_studio_visual_matrix_pivot_and_truncation(studio_svc_env) -> None:
    import app.services.report_studio as studio_mod
    from app.services.report_studio import (
        open_or_create_studio_draft,
        preview_studio_visual,
        save_studio_draft,
    )

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    matrix = {
        "code": "V_MATRIX",
        "title": "Ma trận doanh thu",
        "visual_type": "MATRIX",
        "display_order": 10,
        "grid_span": 12,
        "height_size": "M",
        "fields": [
            {"well_role": "ROWS", "field_id": _field_id(bundle, "DIM_CUSTOMER", "CUSTOMER_NAME")},
            {"well_role": "COLUMNS", "field_id": _field_id(bundle, "DIM_DATE", "MONTH_LABEL")},
            {"well_role": "VALUES", "measure_id": _measure_id(bundle, "REV_SUM")},
        ],
    }
    assert save_studio_draft(ctxs["owner"], vid, {"row_version": rv, "visuals": [matrix]}).ok
    prev = preview_studio_visual(ctxs["owner"], vid, "V_MATRIX", {})
    assert prev.ok, prev.message
    data = prev.data
    assert data["visual_type"] == "MATRIX"
    assert data["pivot"]["row_headers"] == ["Cong ty A", "Cong ty B"]
    assert data["pivot"]["col_headers"] == ["2026-01", "2026-02"]
    assert data["pivot"]["cells"] == [[500000, 300000], [200000, None]]
    assert data["truncated"] is False
    # Ép trần pivot nhỏ -> phải báo truncated, không trả toàn bộ bảng.
    old_rows, old_cols = studio_mod._MATRIX_MAX_ROWS, studio_mod._MATRIX_MAX_COLS
    studio_mod._MATRIX_MAX_ROWS = 1
    try:
        capped = preview_studio_visual(ctxs["owner"], vid, "V_MATRIX", {})
    finally:
        studio_mod._MATRIX_MAX_ROWS, studio_mod._MATRIX_MAX_COLS = old_rows, old_cols
    assert capped.ok, capped.message
    assert capped.data["truncated"] is True
    assert len(capped.data["pivot"]["row_headers"]) == 1


def test_preview_studio_visual_override_unsaved_draft_and_request_seq(studio_svc_env) -> None:
    """Bước 4: preview chấp nhận visual chưa lưu (từ Store) + echo request_seq."""
    from app.services.report_studio import (
        open_or_create_studio_draft,
        preview_studio_visual,
        save_studio_draft,
    )

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    assert save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv, "visuals": [_table_visual(bundle)]}
    ).ok

    # Visual chưa lưu: đổi X sang SEGMENT — preview phải chạy theo override, không theo DB.
    override = _table_visual(bundle)
    override["fields"] = [
        {"well_role": "X", "field_id": _field_id(bundle, "DIM_CUSTOMER", "SEGMENT")},
        {"well_role": "Y", "measure_id": _measure_id(bundle, "REV_SUM")},
    ]
    prev = preview_studio_visual(
        ctxs["owner"], vid, "V_TABLE", {"request_seq": 7}, visual=override
    )
    assert prev.ok, prev.message
    assert prev.data["request_seq"] == 7
    by_seg = {r["SEGMENT"]: r for r in prev.data["rows"]}
    assert by_seg["VIP"]["REV_SUM"] == 800000
    assert by_seg["STD"]["REV_SUM"] == 200000

    # Override sai mã visual -> NOT_FOUND, không chạy query.
    bad = preview_studio_visual(
        ctxs["owner"], vid, "V_OTHER", {"request_seq": 8}, visual=override
    )
    assert not bad.ok and bad.code == ErrorCode.NOT_FOUND

    # Override không hợp lệ (field không thuộc model) -> VALIDATION_ERROR, fail-closed.
    invalid = _table_visual(bundle)
    invalid["fields"] = [
        {"well_role": "X", "field_id": 999999},
        {"well_role": "Y", "measure_id": _measure_id(bundle, "REV_SUM")},
    ]
    denied = preview_studio_visual(ctxs["owner"], vid, "V_TABLE", {}, visual=invalid)
    assert not denied.ok and denied.code == ErrorCode.VALIDATION_ERROR


def test_impact_analysis_lists_affected_visuals_field_level(studio_svc_env) -> None:
    from app.services.report_studio import open_or_create_studio_draft, save_studio_draft
    from app.services.semantic_model import (
        get_model_version_detail,
        impact_analysis,
        open_or_create_draft,
        update_field_props,
    )

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    assert save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv, "visuals": [_table_visual(bundle)]}
    ).ok
    # Mở draft v2 của model, ẩn CUSTOMER_NAME -> visual dùng field đó phải bị nêu.
    model_id = int(bundle["model"]["id"])
    draft2 = open_or_create_draft(ctxs["owner"], model_id)
    assert draft2.ok, draft2.message
    draft2_id = draft2.data["version"]["id"]
    detail2 = get_model_version_detail(ctxs["owner"], draft2_id)
    assert detail2.ok
    fid2 = _field_id(detail2.data, "DIM_CUSTOMER", "CUSTOMER_NAME")
    assert update_field_props(ctxs["owner"], fid2, {"is_visible": False}).ok
    impact = impact_analysis(ctxs["owner"], model_id, target_version_id=draft2_id)
    assert impact.ok, impact.message
    assert any(r["report_code"] == "RPT_SALES" for r in impact.data["reports"])
    assert any(v["code"] == "V_TABLE" for v in impact.data["visuals"])


def test_impact_analysis_lists_affected_visuals_table_level(studio_svc_env) -> None:
    from app.services.report_studio import open_or_create_studio_draft, save_studio_draft
    from app.services.semantic_model import (
        get_model_version_detail,
        impact_analysis,
        open_or_create_draft,
        update_table_props,
    )

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    assert save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv, "visuals": [_table_visual(bundle)]}
    ).ok
    # Mở draft v2 của model, ẩn cả bảng DIM_CUSTOMER -> visual phải bị nêu
    # (breaking change mức bảng, không có field_id).
    model_id = int(bundle["model"]["id"])
    draft2 = open_or_create_draft(ctxs["owner"], model_id)
    assert draft2.ok, draft2.message
    draft2_id = draft2.data["version"]["id"]
    detail2 = get_model_version_detail(ctxs["owner"], draft2_id)
    assert detail2.ok
    tbl2 = next(t for t in detail2.data["tables"] if t["alias"] == "DIM_CUSTOMER")
    assert update_table_props(ctxs["owner"], tbl2["id"], {"is_hidden": True}).ok
    impact = impact_analysis(ctxs["owner"], model_id, target_version_id=draft2_id)
    assert impact.ok, impact.message
    assert any(v["code"] == "V_TABLE" for v in impact.data["visuals"])


def test_clone_and_archive_studio_report(studio_svc_env) -> None:
    from app.services.report_studio import (
        archive_studio_report,
        clone_studio_report,
        list_studio_reports,
        open_or_create_studio_draft,
        save_studio_draft,
    )

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    assert save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv, "visuals": [_table_visual(bundle)]}
    ).ok
    cloned = clone_studio_report(
        ctxs["owner"],
        created["report"]["id"],
        {"code": "RPT_SALES_COPY", "name": "Bản sao doanh thu"},
    )
    assert cloned.ok, cloned.message
    assert cloned.data["report"]["code"] == "RPT_SALES_COPY"
    draft2 = open_or_create_studio_draft(ctxs["owner"], cloned.data["report"]["id"])
    assert draft2.ok
    assert [v["code"] for v in draft2.data["visuals"]] == ["V_TABLE"]
    archived = archive_studio_report(ctxs["owner"], created["report"]["id"])
    assert archived.ok, archived.message
    listed = list_studio_reports(ctxs["owner"])
    assert listed.ok
    assert [r["code"] for r in listed.data] == ["RPT_SALES_COPY"]


def test_version_dict_includes_model_version_id(studio_svc_env) -> None:
    from sqlalchemy import select

    from app.db.metadata import recon_rpt_tpl_ver
    from app.services.report_template import _version_dict

    engine, ds_id, ctxs = studio_svc_env
    ver_id, _ = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    with engine.connect() as conn:
        row = conn.execute(
            select(recon_rpt_tpl_ver).where(
                recon_rpt_tpl_ver.c.ID == created["version"]["id"]
            )
        ).mappings().first()
        assert row is not None
        assert _version_dict(row)["model_version_id"] == ver_id
        # Version cổ điển không gắn model -> None.
        rid = _report_id(conn, "RPT_CLASSIC2")
        tid = _template_id(conn, rid, "MAIN")
        classic_vid = _version_id(conn, tid, 1)
        row2 = conn.execute(
            select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == classic_vid)
        ).mappings().first()
        assert row2 is not None
        assert _version_dict(row2)["model_version_id"] is None

def test_validate_reports_per_visual_error_when_model_archived(studio_svc_env) -> None:
    from app.services.report_studio import (
        open_or_create_studio_draft,
        save_studio_draft,
        validate_studio_report,
    )
    from app.services.semantic_model import open_or_create_draft
    from app.services.semantic_model_validate import publish_model_version

    _, ds_id, ctxs = studio_svc_env
    ver_id, bundle = _build_published_model(ctxs["owner"], ds_id)
    created = _create_studio_report(ctxs["owner"], ver_id)
    opened = open_or_create_studio_draft(ctxs["owner"], created["report"]["id"])
    assert opened.ok
    vid = opened.data["version"]["id"]
    rv = opened.data["version"]["row_version"]
    assert save_studio_draft(
        ctxs["owner"], vid, {"row_version": rv, "visuals": [_table_visual(bundle)]}
    ).ok
    # Model phát hành v2 -> v1 thành ARCHIVED, visual pin v1 không resolve được.
    model_id = int(bundle["model"]["id"])
    draft2 = open_or_create_draft(ctxs["owner"], model_id)
    assert draft2.ok
    pub2 = publish_model_version(
        ctxs["owner"], draft2.data["version"]["id"], {"change_note": "Phat hanh v2"}
    )
    assert pub2.ok, pub2.message
    validated = validate_studio_report(ctxs["owner"], vid)
    assert validated.ok, validated.message
    assert validated.data["status"] == "DRAFT"
    assert len(validated.data["errors"]) == 1
    assert validated.data["errors"][0]["visual_code"] == "V_TABLE"
    assert validated.data["errors"][0]["code"] == "MODEL_VERSION_LOCKED"
    # Publish cũng bị chặn vì validate lỗi.
    from app.services.report_studio import publish_studio_report

    blocked = publish_studio_report(ctxs["owner"], vid, {"change_note": "v1"})
    assert not blocked.ok and blocked.code == ErrorCode.VALIDATION_ERROR
