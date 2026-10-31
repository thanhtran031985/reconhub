from __future__ import annotations

from unittest.mock import patch

from app.core.context import Ctx
from app.ui.pages.data_sources import (
    layout,
    render_data_sources_table,
    render_storage_tab,
)


def test_data_sources_layout_renders_for_admin() -> None:
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    with patch("app.ui.pages.data_sources.get_current_ctx", return_value=admin_ctx):
        page = layout()
        assert page is not None
        page_str = str(page)
        assert "Nguồn đối soát" in page_str
        assert "Lưu trữ RECON_APP" in page_str


def test_data_sources_forbidden_for_non_admin() -> None:
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


def test_render_storage_tab() -> None:
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
