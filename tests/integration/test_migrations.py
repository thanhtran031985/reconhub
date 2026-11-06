from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_recon.db"


@pytest.fixture
def temp_db_url(temp_db_path: Path) -> str:
    return f"sqlite:///{temp_db_path.as_posix()}"


def run_alembic_upgrade(db_url: str, revision: str = "head") -> None:
    root = Path(__file__).resolve().parent.parent.parent
    ini_path = root / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, revision)


def run_alembic_downgrade(db_url: str, revision: str = "base") -> None:
    root = Path(__file__).resolve().parent.parent.parent
    ini_path = root / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.downgrade(alembic_cfg, revision)


def test_migration_lifecycle(temp_db_url: str) -> None:
    # 1. Upgrade head lần 1
    run_alembic_upgrade(temp_db_url, "head")

    # 2. Upgrade head lần 2 (idempotent)
    run_alembic_upgrade(temp_db_url, "head")

    # 3. Downgrade base rồi upgrade head lại
    run_alembic_downgrade(temp_db_url, "base")
    run_alembic_upgrade(temp_db_url, "head")


def test_sqlite_pragmas_and_data_types(temp_db_url: str) -> None:
    from app.db.engine import get_sqlite_engine
    from app.db.metadata import (
        recon_run,
        recon_run_summary,
        recon_template,
        recon_template_version,
    )

    run_alembic_upgrade(temp_db_url, "head")
    engine = get_sqlite_engine(temp_db_url)

    with engine.connect() as conn:
        # Kiểm tra pragma foreign_keys
        fk_result = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert fk_result == 1

        # Kiểm tra pragma journal_mode (khi có file thật)
        jm_result = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert str(jm_result).lower() == "wal"

        # Tạo Data Source trước để thỏa mãn FK của RECON_RUN
        from app.db.metadata import recon_data_source

        now = datetime.now(timezone.utc)
        ins_ds = recon_data_source.insert().values(
            NAME="ORACLE_TEST",
            ENV="DEV",
            PURPOSE="SOURCE",
            DB_TYPE="ORACLE",
            HOST="localhost",
            PORT=1521,
            SERVICE_NAME="XE",
            CALL_TIMEOUT_S=600,
            MAX_ROWS=1000000,
            IS_ACTIVE="Y",
            CREATED_BY="admin",
            CREATED_AT=now,
            UPDATED_AT=now,
        )
        ds_res = conn.execute(ins_ds)
        ds_id = ds_res.inserted_primary_key[0]

        ins_tmpl = recon_template.insert().values(
            CODE="TEST_TMPL",
            NAME="Template Test",
            OWNER="admin",
            STATUS="ACTIVE",
            CREATED_AT=now,
            UPDATED_AT=now,
            ROW_VERSION=1,
        )
        res = conn.execute(ins_tmpl)
        tmpl_id = res.inserted_primary_key[0]

        config_data = {"version": 1, "fields": ["ID", "AMOUNT"], "nested": {"active": True}}
        ins_ver = recon_template_version.insert().values(
            TEMPLATE_ID=tmpl_id,
            VERSION=1,
            STATUS="ACTIVE",
            CONFIG_JSON=config_data,
            CREATED_BY="admin",
            CREATED_AT=now,
        )
        conn.execute(ins_ver)

        # Decimal chính xác 0.1 + 0.2
        d1 = Decimal("0.1")
        d2 = Decimal("0.2")
        d_sum = d1 + d2  # Decimal('0.3')

        ins_run = recon_run.insert().values(
            TEMPLATE_ID=tmpl_id,
            TEMPLATE_VERSION=1,
            PROFILE_CODE="DEFAULT",
            DATA_SOURCE_ID=ds_id,
            P_FROM=now,
            P_TO=now,
            STATUS="QUEUED",
            CREATED_BY="admin",
            CREATED_AT=now,
        )
        run_res = conn.execute(ins_run)
        run_id = run_res.inserted_primary_key[0]

        ins_sum = recon_run_summary.insert().values(
            RUN_ID=run_id,
            EXCEL_ROWS_READ=100,
            CONTROL_TOTAL_FILE=d_sum,
            DURATION_MS=125,
        )
        conn.execute(ins_sum)
        conn.commit()

        # Đọc lại và kiểm tra kiểu
        sel_ver = conn.execute(
            select(recon_template_version.c.CONFIG_JSON).where(recon_template_version.c.TEMPLATE_ID == tmpl_id)
        ).scalar_one()
        assert isinstance(sel_ver, dict)
        assert sel_ver["nested"]["active"] is True

        sel_sum = conn.execute(
            select(recon_run_summary.c.CONTROL_TOTAL_FILE).where(recon_run_summary.c.RUN_ID == run_id)
        ).scalar_one()
        assert isinstance(sel_sum, Decimal)
        assert sel_sum == Decimal("0.3")

        # Kiểm tra trong SQLite thực tế lưu dạng TEXT
        raw_text = conn.execute(
            text(
                f"SELECT typeof(CONTROL_TOTAL_FILE), CONTROL_TOTAL_FILE FROM RECON_RUN_SUMMARY WHERE RUN_ID = {run_id}"
            )
        ).fetchone()
        assert raw_text is not None
        assert raw_text[0] == "text"
        assert raw_text[1] == "0.3"


def test_reporting_migration_creates_tables_and_lock(temp_db_url: str) -> None:
    """Task 21 bước 1 (T21-01 phía SQLite): migration 0004 tạo 11 bảng
    report và seed dòng khóa REPORT_ACTIVATE_LOCK."""
    from sqlalchemy import create_engine, inspect

    run_alembic_upgrade(temp_db_url, "head")
    engine = create_engine(temp_db_url)
    names = set(inspect(engine).get_table_names())
    for table in [
        "RECON_REPORT",
        "RECON_REPORT_TEMPLATE",
        "RECON_RPT_TPL_VER",
        "RECON_RPT_PARAM",
        "RECON_RPT_PARAM_LOV",
        "RECON_RPT_COLUMN",
        "RECON_REPORT_RUN",
        "RECON_RPT_EXPORT",
        "RECON_RPT_FAVORITE",
        "RECON_RPT_PRESET",
        "RECON_RPT_LOV_CACHE",
    ]:
        assert table in names
    with engine.connect() as conn:
        lock = conn.execute(
            text("SELECT VALUE FROM RECON_APP_SETTING WHERE KEY = 'REPORT_ACTIVATE_LOCK'")
        ).scalar_one_or_none()
        assert lock == "N"


def test_reporting_downgrade_refused_with_data(temp_db_url: str) -> None:
    """Task 21 bước 1 (Q9): downgrade 0004 từ chối khi đã có dữ liệu
    report; dữ liệu và bảng còn nguyên."""
    from datetime import datetime, timezone

    from sqlalchemy import create_engine

    run_alembic_upgrade(temp_db_url, "head")
    engine = create_engine(temp_db_url)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO RECON_REPORT (CODE, NAME, CATEGORY_CODE, OWNER, "
                "DESCRIPTION, DEFAULT_FAVORITE, IS_VISIBLE, IS_ACTIVE, CREATED_BY, "
                "CREATED_AT, UPDATED_BY, UPDATED_AT, ROW_VERSION) "
                "VALUES ('FIN_REVENUE', 'Doanh thu', 'FIN', 'admin', NULL, 'N', "
                "'Y', 'Y', 'admin', :now, 'admin', :now, 1)"
            ),
            {"now": now},
        )
    with pytest.raises(RuntimeError, match="Không downgrade được"):
        run_alembic_downgrade(temp_db_url, "0003_menu_permission")
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM RECON_REPORT")).scalar()
        assert count == 1


def test_export_claim_migration_columns(temp_db_url: str) -> None:
    """Task 26 bước 1 (Q2): migration 0005 thêm LOCKED_BY/LOCKED_AT/
    HEARTBEAT_AT vào RECON_RPT_EXPORT; downgrade về 0004 bỏ 3 cột."""
    from sqlalchemy import create_engine, inspect

    run_alembic_upgrade(temp_db_url, "head")
    engine = create_engine(temp_db_url)
    cols = {
        c["name"] for c in inspect(engine).get_columns("RECON_RPT_EXPORT")
    }
    assert {"LOCKED_BY", "LOCKED_AT", "HEARTBEAT_AT"} <= cols
    run_alembic_downgrade(temp_db_url, "0004_reporting_core")
    cols = {
        c["name"] for c in inspect(engine).get_columns("RECON_RPT_EXPORT")
    }
    assert not ({"LOCKED_BY", "LOCKED_AT", "HEARTBEAT_AT"} & cols)
