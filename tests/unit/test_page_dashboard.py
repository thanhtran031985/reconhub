from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.db.metadata import (
    metadata,
    recon_data_source,
    recon_file,
    recon_run,
    recon_run_summary,
    recon_template,
    recon_user,
    recon_user_role,
)
from app.ui.pages.dashboard import (
    fetch_dashboard_stats,
    format_date_range,
    format_short_dt,
    render_dashboard,
    render_diff_rate_by_template,
    render_header,
    render_kpi_grid,
    render_recent_runs_card,
)


@pytest.fixture
def dashboard_env(tmp_path, monkeypatch):
    db_file = tmp_path / "dashboard_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        # User
        res_u = conn.execute(
            recon_user.insert().values(
                USERNAME="operator_user",
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
        u_id = res_u.inserted_primary_key[0]
        conn.execute(recon_user_role.insert().values(USER_ID=u_id, ROLE=Role.OPERATOR.value, CREATED_AT=now))

        # Data source
        res_ds = conn.execute(
            recon_data_source.insert().values(
                NAME="ORCL_TEST",
                ENV="TEST",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="localhost",
                PORT=1521,
                SERVICE_NAME="XEPDB1",
                USERNAME="recon_test",
                PASSWORD_ENC="dummy",
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="operator_user",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        ds_id = res_ds.inserted_primary_key[0]

        # File
        res_file = conn.execute(
            recon_file.insert().values(
                ORIGINAL_NAME="sample.xlsx",
                SIZE_BYTES=1024 * 500,
                SHA256="dummy_hash_1",
                STORAGE_PATH="files/sample.xlsx",
                UPLOADED_BY="operator_user",
                UPLOADED_AT=now,
            )
        )
        file_id = res_file.inserted_primary_key[0]

        # Template
        res_tpl = conn.execute(
            recon_template.insert().values(
                CODE="DTP",
                NAME="DTP – Hóa đơn tác nghiệp",
                OWNER="operator_user",
                STATUS="ACTIVE",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        tpl_id = res_tpl.inserted_primary_key[0]

        # Run 1: DONE, unchecked
        conn.execute(
            recon_run.insert().values(
                ID=201,
                TEMPLATE_ID=tpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="DEFAULT",
                FILE_ID=file_id,
                DATA_SOURCE_ID=ds_id,
                P_FROM=datetime(now.year, now.month, 1, 0, 0, 0),
                P_TO=datetime(now.year, now.month, 2, 23, 59, 59),
                STATUS="DONE",
                STAGE=5,
                PROGRESS_PCT=100,
                CREATED_BY="operator_user",
                CREATED_AT=now,
                FINISHED_AT=now,
            )
        )
        conn.execute(
            recon_run_summary.insert().values(
                RUN_ID=201,
                EXCEL_ROWS_READ=100,
                DB_ROWS=100,
                EXCEL_GROUPS=10,
                DB_GROUPS=10,
                CNT_MATCHED=10,
                CNT_MISMATCH=0,
                CNT_MISSING_IN_DB=0,
                CNT_MISSING_IN_EXCEL=0,
                EXCEL_ROWS_INVALID=0,
            )
        )

        # Run 2: FAILED
        conn.execute(
            recon_run.insert().values(
                ID=202,
                TEMPLATE_ID=tpl_id,
                TEMPLATE_VERSION=1,
                PROFILE_CODE="BY_DATE",
                FILE_ID=file_id,
                DATA_SOURCE_ID=ds_id,
                P_FROM=datetime(now.year, now.month, 1, 0, 0, 0),
                P_TO=datetime(now.year, now.month, 2, 23, 59, 59),
                STATUS="FAILED",
                STAGE=2,
                PROGRESS_PCT=30,
                CREATED_BY="operator_user",
                CREATED_AT=now,
                FINISHED_AT=now,
            )
        )

    return {
        "engine": engine,
        "ctx": Ctx(user_id=u_id, username="operator_user", full_name="Vận Hành Viên", roles=[Role.OPERATOR]),
    }


def test_dashboard_helpers():
    assert format_short_dt(None) == "—"
    assert format_short_dt("2026-10-31T18:20:05") == "31/10 18:20"
    rng = format_date_range("2026-10-01T00:00:00", "2026-10-31T23:59:59")
    assert "01/10 00:00 → 31/10 23:59" in rng


def test_render_header():
    hd = render_header(total=38, unchecked=9, last_run_time="31/10/2026 18:20:05")
    assert hd is not None
    assert "38 run, 9 chưa kiểm tra" in str(hd)
    assert "31/10/2026 18:20:05" in str(hd)


def test_render_kpi_grid():
    stats = {
        "total_runs": 38,
        "done_count": 35,
        "failed_count": 2,
        "running_count": 1,
        "unchecked_count": 9,
        "my_work": 4,
        "my_unchecked": 3,
        "my_failed": 1,
        "avg_match_pct": 98.6,
        "temp_bytes": 1024 * 1024 * 1024 * 5,  # 5 GB
    }
    grid = render_kpi_grid(stats)
    assert grid is not None
    grid_str = str(grid)
    assert "Run trong kỳ" in grid_str
    assert "38" in grid_str
    assert "98,6%" in grid_str
    assert "Chưa kiểm tra" in grid_str
    assert "Việc của tôi" in grid_str
    assert "4" in grid_str


def test_render_recent_runs_card():
    # Trường hợp rỗng
    empty_card = render_recent_runs_card([])
    assert "Chưa có run nào" in str(empty_card)

    # Trường hợp có dữ liệu
    items = [
        {
            "id": 201,
            "template_name": "DTP – HĐ tác nghiệp",
            "profile_code": "DEFAULT",
            "status": "DONE",
            "progress_pct": 100,
            "created_at": "2026-10-31T18:20:00",
            "checked_at": None,
            "p_from": "2026-10-01T00:00:00",
            "p_to": "2026-10-05T23:59:59",
            "cnt_mismatch": 0,
            "cnt_missing_in_db": 0,
            "cnt_missing_in_excel": 0,
            "match_pct": 100.0,
        }
    ]
    card = render_recent_runs_card(items)
    card_str = str(card)
    assert "#201" in card_str
    assert "DTP – HĐ tác nghiệp" in card_str
    assert "Khớp" in card_str
    assert "100,0%" in card_str
    assert "Chưa kiểm tra" in card_str


def test_fetch_dashboard_stats(dashboard_env):
    stats = fetch_dashboard_stats(dashboard_env["ctx"])
    assert stats["total_runs"] == 2
    assert stats["done_count"] == 1
    assert stats["failed_count"] == 1
    assert stats["unchecked_count"] == 1
    assert stats["my_work"] == 2
    assert stats["avg_match_pct"] == 100.0
    assert len(stats["recent_runs"]) == 2


def test_render_dashboard_callback(dashboard_env, monkeypatch):
    # Khi chưa đăng nhập
    monkeypatch.setattr("app.ui.pages.dashboard.get_current_ctx", lambda: None)
    res_no_login = render_dashboard(0)
    assert "Bạn cần đăng nhập" in str(res_no_login)

    # Khi đã đăng nhập
    monkeypatch.setattr("app.ui.pages.dashboard.get_current_ctx", lambda: dashboard_env["ctx"])
    res_logged_in = render_dashboard(0)
    res_str = str(res_logged_in)
    assert "Run trong kỳ" in res_str
    assert "#201" in res_str
    assert "#202" in res_str
    assert "Tỉ lệ lệch theo template" in res_str


def test_render_diff_rate_by_template():
    empty_card = render_diff_rate_by_template([])
    assert "Chưa có dữ liệu theo template" in str(empty_card)

    items = [
        {
            "template_id": 1,
            "template_code": "DTP",
            "template_name": "DTP Hóa Đơn",
            "run_count": 5,
            "total_compared": 1000,
            "total_diff": 25,
            "diff_pct": 2.5,
        }
    ]
    card = render_diff_rate_by_template(items)
    card_str = str(card)
    assert "DTP Hóa Đơn" in card_str
    assert "DTP" in card_str
    assert "2,5%" in card_str
