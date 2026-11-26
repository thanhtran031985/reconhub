"""Tests cho Bước 3 của task 104-layout-cache-perf: Asset Lazy-Load, Gzip và Cache-Control."""

from __future__ import annotations

import gzip
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_user
from app.services.perm import clear_perm_cache
from app.ui.app import create_app


@pytest.fixture
def asset_client(tmp_path, monkeypatch):
    clear_perm_cache()
    invalidate_user_session_cache()
    db_file = tmp_path / "step3_assets.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-step3-secret-key-123")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)
    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="admin",
                FULL_NAME="Admin Step3",
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
        uid = res.inserted_primary_key[0]
        seed_perm_basics(engine, {uid: ["ADMIN"]}, conn=conn)

    dash_app = create_app()
    client = dash_app.server.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["username"] = "admin"
        sess["session_version"] = 1
        sess["roles"] = ["ADMIN"]
        sess["must_change_pw"] = False
    return client


def test_non_heavy_pages_do_not_eager_load_mermaid_or_tabulator(asset_client) -> None:
    """Trang /login và /report-runs không nạp mermaid.min.js hay tabulator.min.js trong HTML."""
    for path in ("/login", "/report-runs"):
        resp = asset_client.get(path)
        assert resp.status_code == 200
        html_text = resp.get_data(as_text=True)
        assert "mermaid.min.js" not in html_text
        assert "mermaid_init.js" not in html_text
        assert "tabulator.min.js" not in html_text
        assert "tabulator.min.css" not in html_text
        assert "tabulator_fluent.css" not in html_text


def test_lazy_assets_still_served_with_cache_control(asset_client) -> None:
    """Các bundle lazy vẫn tải được khi cần với Cache-Control phù hợp."""
    for rel_path in (
        "/assets/lazy/mermaid.min.js",
        "/assets/lazy/mermaid_init.js",
        "/assets/lazy/tabulator.min.js",
        "/assets/lazy/tabulator.min.css",
        "/assets/lazy/tabulator_fluent.css",
    ):
        resp = asset_client.get(rel_path)
        assert resp.status_code == 200, rel_path
        cc = resp.headers.get("Cache-Control", "")
        assert "public" in cc
        assert "max-age=" in cc

    versioned = asset_client.get("/assets/custom.css?m=123456")
    assert versioned.status_code == 200
    assert "immutable" in versioned.headers.get("Cache-Control", "")
    assert "max-age=31536000" in versioned.headers.get("Cache-Control", "")


def test_http_gzip_compression_when_accepted(asset_client) -> None:
    """Server trả Content-Encoding: gzip và Vary: Accept-Encoding khi client hỗ trợ."""
    resp = asset_client.get(
        "/assets/lazy/tabulator.min.js",
        headers={"Accept-Encoding": "gzip, deflate"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("Content-Encoding") == "gzip"
    assert "Accept-Encoding" in resp.headers.get("Vary", "")
    decompressed = gzip.decompress(resp.data)
    assert b"Tabulator" in decompressed

    # JSON lớn từ _dash-layout cũng phải được nén
    layout_resp = asset_client.get(
        "/_dash-layout",
        headers={"Accept-Encoding": "gzip"},
    )
    assert layout_resp.status_code == 200
    assert layout_resp.headers.get("Content-Encoding") == "gzip"
    assert b"app-shell-container" in gzip.decompress(layout_resp.data)

    # Response nhỏ (/health) giữ nguyên không nén phình dung lượng
    health_resp = asset_client.get(
        "/health",
        headers={"Accept-Encoding": "gzip"},
    )
    assert health_resp.status_code == 200
    assert "Content-Encoding" not in health_resp.headers
