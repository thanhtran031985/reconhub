from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import dash
import pytest
from sqlalchemy import create_engine, func, select, update

from app.core.context import Ctx
from app.db.metadata import metadata, recon_audit_log, recon_data_source, recon_user
from app.ui.pages.data_sources import (
    layout,
    render_data_sources_table,
    render_storage_tab,
)


@pytest.fixture
def ds_perm_env(tmp_path, monkeypatch):
    """DB tạm có admin/operator + phân quyền (task 19) cho test layout.

    layout() kiểm tra admin từ DB (is_admin) nên không được dựa vào
    DB ambient hay cache settings của test chạy trước.
    """
    from tests.conftest import seed_perm_basics

    db_path = tmp_path / "ds_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        for uid, username in [(1, "admin"), (2, "operator")]:
            conn.execute(
                recon_user.insert().values(
                    ID=uid,
                    USERNAME=username,
                    FULL_NAME=username,
                    PASSWORD_HASH="hash",
                    IS_ACTIVE="Y",
                    MUST_CHANGE_PW="N",
                    SESSION_VERSION=1,
                    CREATED_BY="system",
                    CREATED_AT=now,
                    UPDATED_AT=now,
                )
            )
    seed_perm_basics(engine, {1: ["ADMIN"], 2: ["OPERATOR"]})
    for mod in [
        "app.services.perm",
        "app.services.data_source",
        "app.services.temp_data",
        "app.ui.pages.data_sources",
        "app.db.engine",
    ]:
        monkeypatch.setattr(f"{mod}.get_recon_engine", lambda: engine)
    yield engine


def test_data_sources_layout_renders_for_admin(ds_perm_env) -> None:
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    with patch("app.ui.pages.data_sources.get_current_ctx", return_value=admin_ctx):
        page = layout()
        assert page is not None
        page_str = str(page)
        assert "Nguồn đối soát" in page_str
        assert "Lưu trữ RECON_APP" in page_str


def test_data_sources_forbidden_for_non_admin(ds_perm_env) -> None:
    op_ctx = Ctx(user_id=2, username="operator", full_name="Operator", roles=["OPERATOR"])
    with patch("app.ui.pages.data_sources.get_current_ctx", return_value=op_ctx):
        page = layout()
        assert page is not None
        page_str = str(page)
        assert "chỉ dành cho Quản trị viên" in page_str or "forbidden" in page_str.lower() or "quyền" in page_str


def test_render_data_sources_table() -> None:
    mock_sources = [
        {
            "id": 1,
            "name": "Oracle ERP Billing",
            "environment": "PROD",
            "host": "10.0.1.50",
            "port": 1521,
            "service_name": "ORCLPDB1",
            "username": "RECON_RO",
            "default_schema": "BILLING",
            "last_check_status": "RO_OK",
            "last_check_ms": 45,
            "template_count": 3,
        }
    ]
    content = render_data_sources_table(mock_sources, loading=False, error=None)
    content_str = str(content)
    assert "Oracle ERP Billing" in content_str
    assert "PROD" in content_str
    assert "10.0.1.50" in content_str
    assert "BILLING" in content_str
    assert "Kích hoạt" in content_str
    assert "ds-active-switch" in content_str


def test_render_storage_tab(ds_perm_env) -> None:
    mock_usage = {
        "temp_bytes": 3355443,  # 3.2 MB
        "warning_gb": 2.0,
        "warning_days": 30,
        "is_warning": False,
        "uncheck_count": 5,
        "stale_count": 2,
    }
    content = render_storage_tab(mock_usage, purge_logs=[])
    content_str = str(content)
    assert "3,2 MB" in content_str
    assert "Xóa dữ liệu tạm theo điều kiện" in content_str

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    with patch("app.ui.pages.data_sources.get_current_ctx", return_value=admin_ctx):
        page_str = str(layout())
        assert "XOA" in page_str


def test_render_storage_tab_with_migration_and_sqlite() -> None:
    mock_usage = {
        "temp_bytes": 0,
        "warning_gb": 2.0,
        "warning_days": 30,
        "is_warning": False,
        "uncheck_count": 0,
        "stale_count": 0,
    }
    mock_oracle_sources = [
        {
            "ID": 10,
            "NAME": "Oracle Billing UAT",
            "ENV": "UAT",
            "USERNAME": "recon_uat",
            "HOST": "db.corp",
            "PORT": 1521,
            "SERVICE_NAME": "ORCL",
        }
    ]
    # Khi đang chạy SQLite
    content_sqlite = render_storage_tab(mock_usage, purge_logs=[], is_oracle=False, oracle_sources=mock_oracle_sources)
    c_str = str(content_sqlite)
    assert "Chuyển dữ liệu sang Oracle" in c_str
    assert "Đang chạy trên SQLite" in c_str

    # Khi đang chạy Oracle
    mock_mig = {"OLD_SQLITE_PATH": "data/recon_app.db", "OLD_SQLITE_DELETED_AT": None}
    content_oracle = render_storage_tab(
        mock_usage,
        purge_logs=[],
        is_oracle=True,
        oracle_sources=mock_oracle_sources,
        latest_migration=mock_mig,
    )
    o_str = str(content_oracle)
    assert "Chuyển dữ liệu sang Oracle" in o_str
    assert "Bản lưu SQLite cũ đang được lưu trữ an toàn" in o_str
    assert "data/recon_app.db" in o_str

# --- Task 91: mount firing trên /data-sources ---


@pytest.fixture
def ds_source_env(ds_perm_env):
    """DB tạm + 1 nguồn SOURCE đang active (id=1, ENV DEV)."""
    engine = ds_perm_env
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            recon_data_source.insert().values(
                ID=1,
                NAME="Oracle Test",
                ENV="DEV",
                PURPOSE="SOURCE",
                DB_TYPE="ORACLE",
                HOST="db.test",
                PORT=1521,
                SERVICE_NAME="ORCL",
                USERNAME="recon_ro",
                DEFAULT_SCHEMA="BILLING",
                CALL_TIMEOUT_S=600,
                IS_ACTIVE="Y",
                IS_CURRENT_METADATA="N",
                CREATED_BY="admin",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
    yield engine


def _audit_count(engine) -> int:
    """Chỉ đếm audit kích hoạt/vô hiệu hóa nguồn (seed_perm_basics tự ghi 1 dòng MENU_SYNC)."""
    with engine.connect() as conn:
        return int(
            conn.execute(
                select(func.count())
                .select_from(recon_audit_log)
                .where(recon_audit_log.c.ACTION.in_(["ACTIVATE_DATA_SOURCE", "DEACTIVATE_DATA_SOURCE"]))
            ).scalar()
            or 0
        )


def _ds_row(engine, ds_id=1):
    with engine.connect() as conn:
        return conn.execute(
            select(recon_data_source).where(recon_data_source.c.ID == ds_id)
        ).mappings().first()


def _mock_toggle_ctx(monkeypatch, checked_value, ds_id=1):
    """Giả callback_context như thể Switch vừa mount (chưa có click thật)."""
    fake = SimpleNamespace(
        triggered=[
            {
                "prop_id": '{"index": %d, "type": "ds-active-switch"}.checked' % ds_id,
                "value": checked_value,
            }
        ],
        triggered_id={"type": "ds-active-switch", "index": ds_id},
    )
    monkeypatch.setattr("dash.callback_context", fake)
    monkeypatch.setattr("dash.ctx", fake)


def test_active_toggle_mount_same_state_no_write(ds_source_env, monkeypatch) -> None:
    """Task 91 D1: Switch mount với đúng trạng thái hiện tại -> không ghi gì."""
    from app.ui.pages.data_sources import handle_ds_active_toggle

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    monkeypatch.setattr("app.ui.pages.data_sources.get_current_ctx", lambda: admin_ctx)
    _mock_toggle_ctx(monkeypatch, checked_value=True, ds_id=1)
    before = _ds_row(ds_source_env, 1)

    with pytest.raises(dash.exceptions.PreventUpdate):
        handle_ds_active_toggle([True], [{"type": "ds-active-switch", "index": 1}])

    after = _ds_row(ds_source_env, 1)
    assert _audit_count(ds_source_env) == 0
    assert after["IS_ACTIVE"] == before["IS_ACTIVE"] == "Y"
    assert after["UPDATED_AT"] == before["UPDATED_AT"]


def test_active_toggle_real_click_off(ds_source_env, monkeypatch) -> None:
    """Task 91 D1: user tắt Switch thật -> deactivate + audit + trigger bump."""
    from app.ui.pages.data_sources import handle_ds_active_toggle

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    monkeypatch.setattr("app.ui.pages.data_sources.get_current_ctx", lambda: admin_ctx)
    _mock_toggle_ctx(monkeypatch, checked_value=False, ds_id=1)

    env, color, trigger_ts, alert = handle_ds_active_toggle(
        [False], [{"type": "ds-active-switch", "index": 1}]
    )

    assert _ds_row(ds_source_env, 1)["IS_ACTIVE"] == "N"
    assert _audit_count(ds_source_env) == 1
    assert isinstance(trigger_ts, float) and trigger_ts > 0
    assert "vô hiệu hóa" in str(alert)


def test_active_toggle_real_click_on(ds_source_env, monkeypatch) -> None:
    """Task 91 D1: user bật Switch thật (nguồn đang tắt) -> activate + audit."""
    from app.ui.pages.data_sources import handle_ds_active_toggle

    with ds_source_env.begin() as conn:
        conn.execute(
            update(recon_data_source).where(recon_data_source.c.ID == 1).values(IS_ACTIVE="N")
        )
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    monkeypatch.setattr("app.ui.pages.data_sources.get_current_ctx", lambda: admin_ctx)
    _mock_toggle_ctx(monkeypatch, checked_value=True, ds_id=1)

    env, color, trigger_ts, alert = handle_ds_active_toggle(
        [True], [{"type": "ds-active-switch", "index": 1}]
    )

    assert _ds_row(ds_source_env, 1)["IS_ACTIVE"] == "Y"
    assert _audit_count(ds_source_env) == 1
    assert isinstance(trigger_ts, float) and trigger_ts > 0
    assert "kích hoạt" in str(alert)


def test_load_storage_data_sources_tab_no_update(ds_perm_env, monkeypatch) -> None:
    """Task 91 D2: mở trang (tab sources) -> không tải dữ liệu tab Lưu trữ."""
    from app.ui.pages.data_sources import load_storage_data

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    monkeypatch.setattr("app.ui.pages.data_sources.get_current_ctx", lambda: admin_ctx)

    assert load_storage_data(None, None, None, None, "sources") is dash.no_update


def test_load_storage_data_storage_tab_loads(ds_perm_env, monkeypatch) -> None:
    """Task 91 D2: mở tab Lưu trữ -> tải dữ liệu (usage + purge + migration)."""
    from app.ui.pages.data_sources import load_storage_data

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    monkeypatch.setattr("app.ui.pages.data_sources.get_current_ctx", lambda: admin_ctx)
    monkeypatch.setattr(
        "app.ui.pages.data_sources.usage",
        lambda ctx: SimpleNamespace(ok=True, data={"temp_bytes": 0}),
    )

    data = load_storage_data(None, None, None, None, "storage")

    assert isinstance(data, dict)
    assert set(data.keys()) == {"usage", "purge_logs", "is_oracle", "oracle_sources", "latest_migration"}


def test_purge_preview_no_click_prevent_update(monkeypatch) -> None:
    """Task 91 D3: nút Xem trước mount (chưa bấm) -> không chạy preview."""
    from app.ui.pages.data_sources import handle_purge_preview

    with pytest.raises(dash.exceptions.PreventUpdate):
        handle_purge_preview(None, None, None, None, None)


def test_drawer_open_mount_no_update(ds_source_env, monkeypatch) -> None:
    """Task 91 D4: nút Sửa mount lại (bảng vẽ lại) -> không động vào drawer."""
    from app.ui.pages.data_sources import handle_drawer_open

    fake = SimpleNamespace(
        triggered=[
            {
                "prop_id": '{"index": 1, "type": "ds-edit-btn"}.n_clicks',
                "value": None,
            }
        ],
        triggered_id={"type": "ds-edit-btn", "index": 1},
    )
    monkeypatch.setattr("dash.callback_context", fake)
    monkeypatch.setattr("dash.ctx", fake)

    result = handle_drawer_open(None, [None], None, False)

    assert len(result) == 12
    assert all(v is dash.no_update for v in result)


def test_drawer_open_add_click(ds_source_env, monkeypatch) -> None:
    """Task 91 D4: bấm Thêm thật -> mở drawer với form trống (không đổi)."""
    from app.ui.pages.data_sources import handle_drawer_open

    fake = SimpleNamespace(
        triggered=[{"prop_id": "ds-add-btn.n_clicks", "value": 1}],
        triggered_id="ds-add-btn",
    )
    monkeypatch.setattr("dash.callback_context", fake)
    monkeypatch.setattr("dash.ctx", fake)

    result = handle_drawer_open(1, [None], None, False)

    assert result[0] is True
    assert result[1] is None
    assert result[3] == "DEV"
    assert result[5] == 1521
