"""E2E cho màn /menus — Bước 4 task 20 (test viết trước).

Dash chỉ trả khung shell ở mức HTTP (nội dung trang dựng ở client),
nên ở đây chỉ kiểm tra: app khởi động được với trang đã đăng ký,
GET /menus trả 200 và có tiêu đề trang. Nội dung bảng, cảnh báo,
quyền truy cập và thanh bên kiểm tra ở tests/unit/test_menus_page.py
(gọi trực tiếp layout() và get_nav_items_for_menus).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_user
from app.ui.app import create_app


@pytest.fixture()
def menus_clients(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "menus_e2e.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-menus-e2e-secret")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user_ids: dict[str, int] = {}
    with engine.begin() as conn:
        for username, role in [("admin", "ADMIN"), ("operator", "OPERATOR")]:
            res = conn.execute(
                recon_user.insert().values(
                    USERNAME=username,
                    FULL_NAME=username,
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
            uid = int(res.inserted_primary_key[0])
            user_ids[username] = uid
            seed_perm_basics(engine, {uid: [role]}, conn=conn)

    app = create_app()

    def _client(username: str, role: str):
        client = app.server.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_ids[username]
            sess["username"] = username
            sess["session_version"] = 1
            sess["roles"] = [role]
            sess["must_change_pw"] = False
        return client

    return {"admin": _client("admin", "ADMIN"), "operator": _client("operator", "OPERATOR")}


class TestMenusPageAccess:
    def test_admin_opens_menus_page(self, menus_clients):
        resp = menus_clients["admin"].get("/menus")
        assert resp.status_code == 200
        assert "Danh sách menu" in resp.text

    def test_operator_page_serves_shell(self, menus_clients):
        # Trang bị chặn ở phía client (layout trả redirect /forbidden);
        # mức HTTP chỉ xác nhận shell trả 200 với đúng tiêu đề trang.
        resp = menus_clients["operator"].get("/menus")
        assert resp.status_code == 200
        assert "Danh sách menu" in resp.text
