from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine

from app.core.context import Ctx
from app.db.metadata import metadata, recon_user
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
