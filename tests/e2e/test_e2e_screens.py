from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_user
from app.ui.app import create_app


@pytest.fixture
def e2e_client(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "e2e_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-e2e-secret-key-123")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    # Đồng bộ menu + vai trò seed (task 19) trước khi chèn user
    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

    # Thêm user admin
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="admin",
                FULL_NAME="Quản trị viên",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        user_id = res.inserted_primary_key[0]
        seed_perm_basics(engine, {user_id: ["ADMIN"]}, conn=conn)

    app = create_app()
    client = app.server.test_client()

    # Đăng nhập bằng cách set session
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = "admin"
        sess["session_version"] = 1
        sess["roles"] = ["ADMIN"]
        sess["must_change_pw"] = False

    return client


def test_e2e_templates_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/templates")
    assert resp.status_code == 200
    assert b"ReconHub" in resp.data


def test_e2e_data_sources_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/data-sources")
    assert resp.status_code == 200
    assert b"ReconHub" in resp.data
    assert b"Data Sources" in resp.data


def test_e2e_users_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/users")
    assert resp.status_code == 200
    assert b"ReconHub" in resp.data
    assert b"users-page-root" in resp.data or b"users" in resp.data


def test_e2e_template_wizard_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/templates/new")
    assert resp.status_code == 200
    assert b"ReconHub" in resp.data


def test_e2e_new_run_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/runs/new")
    assert resp.status_code == 200
    assert b"ReconHub" in resp.data


def test_e2e_run_result_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/runs/1042")
    assert resp.status_code == 200
    assert b"ReconHub" in resp.data


def test_e2e_history_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/history")
    assert resp.status_code == 200
    assert b"ReconHub" in resp.data


def test_e2e_dashboard_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/")
    assert resp.status_code == 200
    assert b"ReconHub" in resp.data


def test_e2e_issues_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/issues")
    assert resp.status_code == 200
    assert b"ReconHub" in resp.data


def test_e2e_reports_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/reports")
    assert resp.status_code == 200
    assert "Trung tâm báo cáo".encode() in resp.data


def test_e2e_report_viewer_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/reports/1")
    assert resp.status_code == 200
    assert "Xem báo cáo".encode() in resp.data


def test_e2e_report_runs_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/report-runs")
    assert resp.status_code == 200
    assert "Lịch sử báo cáo".encode() in resp.data


def test_e2e_report_admin_page_accessible(e2e_client) -> None:
    resp = e2e_client.get("/report-admin")
    assert resp.status_code == 200
    assert "Quản trị báo cáo".encode() in resp.data


def test_e2e_report_export_download_requires_login(e2e_client) -> None:
    # App guard (before_request) chuyển chưa đăng nhập về /login (302),
    # trước cả abort(401) trong route.
    with e2e_client.session_transaction() as sess:
        sess.clear()
    resp = e2e_client.get("/download/report-export/1")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_e2e_report_export_download_missing_404(e2e_client) -> None:
    resp = e2e_client.get("/download/report-export/999999")
    assert resp.status_code in (403, 404)
