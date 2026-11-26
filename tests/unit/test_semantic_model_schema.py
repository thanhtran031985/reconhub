"""Tests cho schema Semantic Model, migration 0018 và menu report_model (Bước 1 task 106)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.metadata import metadata

ROOT = Path(__file__).resolve().parent.parent.parent


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_semantic_model_tables_in_metadata() -> None:
    expected = {
        "RECON_RPT_MODEL",
        "RECON_RPT_MODEL_VER",
        "RECON_RPT_MODEL_TABLE",
        "RECON_RPT_MODEL_REL",
        "RECON_RPT_MODEL_FIELD",
        "RECON_RPT_MODEL_MEASURE",
        "RECON_RPT_MODEL_RLS",
    }
    assert expected <= set(metadata.tables.keys())


def test_alembic_0018_upgrade_and_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "mig0018.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "test-secret-key-1234567890")
    from app.core.config import get_settings

    get_settings.cache_clear()
    cfg = _alembic_cfg(db_url)
    command.upgrade(cfg, "0017_multi_sso_oidc")

    engine = create_engine(db_url)
    try:
        before_tables = set(inspect(engine).get_table_names())
        assert "RECON_RPT_MODEL" not in before_tables

        command.upgrade(cfg, "0018_semantic_model")
        after_tables = set(inspect(engine).get_table_names())
        expected = {
            "RECON_RPT_MODEL",
            "RECON_RPT_MODEL_VER",
            "RECON_RPT_MODEL_TABLE",
            "RECON_RPT_MODEL_REL",
            "RECON_RPT_MODEL_FIELD",
            "RECON_RPT_MODEL_MEASURE",
            "RECON_RPT_MODEL_RLS",
        }
        assert expected <= after_tables

        with engine.connect() as conn:
            lock_val = conn.execute(
                text("SELECT VALUE FROM RECON_APP_SETTING WHERE KEY = 'MODEL_PUBLISH_LOCK'")
            ).scalar_one_or_none()
            assert lock_val == "N"
            menu_exists = conn.execute(
                text("SELECT 1 FROM RECON_MENU WHERE CODE = 'report_model'")
            ).scalar_one_or_none()
            assert menu_exists == 1

        command.downgrade(cfg, "0017_multi_sso_oidc")
        downgraded_tables = set(inspect(engine).get_table_names())
        for name in expected:
            assert name not in downgraded_tables
    finally:
        engine.dispose()


def test_semantic_model_check_constraints(tmp_path: Path) -> None:
    db_file = tmp_path / "constraints.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    try:
        metadata.create_all(engine)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO RECON_DATA_SOURCE "
                    "(NAME, ENV, PURPOSE, DB_TYPE, CALL_TIMEOUT_S, MAX_ROWS, IS_ACTIVE, IS_CURRENT_METADATA, CREATED_BY, CREATED_AT, UPDATED_AT) "
                    "VALUES ('SRC_1', 'DEV', 'SOURCE', 'SQLITE', 600, 1000000, 'Y', 'N', 'admin', :now, :now)"
                ),
                {"now": now},
            )
            ds_id = conn.execute(text("SELECT ID FROM RECON_DATA_SOURCE WHERE NAME='SRC_1'")).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO RECON_RPT_MODEL "
                    "(CODE, NAME, DATA_SOURCE_ID, IS_ARCHIVED, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                    "VALUES ('SALES_MODEL', 'Sales', :ds_id, 'N', 'admin', :now, 'admin', :now, 1)"
                ),
                {"ds_id": ds_id, "now": now},
            )
            model_id = conn.execute(text("SELECT ID FROM RECON_RPT_MODEL WHERE CODE='SALES_MODEL'")).scalar_one()

            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO RECON_RPT_MODEL_VER "
                        "(MODEL_ID, VERSION_NO, STATUS, CREATED_BY, CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                        "VALUES (:mid, 1, 'INVALID_STATUS', 'admin', :now, 'admin', :now, 1)"
                    ),
                    {"mid": model_id, "now": now},
                )
    finally:
        engine.dispose()


def test_menu_report_model_registered_and_seeded() -> None:
    from app.ui.menus import MENU_BY_CODE, ROLE_MENUS_SEED

    assert "report_model" in MENU_BY_CODE
    m = MENU_BY_CODE["report_model"]
    assert m.group == "CAU_HINH"
    assert m.path == "/report-models"
    assert "report_model" in ROLE_MENUS_SEED["TEMPLATE_OWNER"]
    assert "report_model" not in ROLE_MENUS_SEED["OPERATOR"]
    assert "report_model" not in ROLE_MENUS_SEED["VIEWER"]


def test_schema_inspector_and_metadata_migration_include_semantic_tables() -> None:
    from app.services.metadata_migration import CONFIG_ONLY_TABLES, RECON_TABLES_ORDER
    from app.services.schema_inspector import TABLE_DESCRIPTIONS, domain_for_table

    expected = [
        "RECON_RPT_MODEL",
        "RECON_RPT_MODEL_VER",
        "RECON_RPT_MODEL_TABLE",
        "RECON_RPT_MODEL_REL",
        "RECON_RPT_MODEL_FIELD",
        "RECON_RPT_MODEL_MEASURE",
        "RECON_RPT_MODEL_RLS",
    ]
    for name in expected:
        assert domain_for_table(name) == ("report", "Báo cáo")
        assert TABLE_DESCRIPTIONS.get(name)
        assert name in RECON_TABLES_ORDER
        assert name in CONFIG_ONLY_TABLES
