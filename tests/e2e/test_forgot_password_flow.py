from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from app.core.auth import authenticate_user, hash_password
from app.core.config import get_settings
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_user
from app.services.password_reset import perform_password_reset, request_password_reset
from app.ui.app import create_app


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "reset_e2e.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-reset-e2e-secret")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(
            recon_user.insert().values(
                USERNAME="e2e_user",
                FULL_NAME="E2E Test User",
                EMAIL="e2e_user@company.local",
                PASSWORD_HASH=hash_password("OldPassword123!"),
                IS_ACTIVE="Y",
                SESSION_VERSION=1,
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )

    dash_app = create_app()
    server = dash_app.server
    return server.test_client(), engine


def test_forgot_password_http_routes(app_client):
    client, _ = app_client

    # 1. Trang /forgot-password nạp thành công HTTP 200
    res_forgot = client.get("/forgot-password")
    assert res_forgot.status_code == 200
    assert "Quên mật khẩu" in res_forgot.text or "ReconHub" in res_forgot.text

    # 2. Trang /reset-password nạp thành công HTTP 200
    res_reset = client.get("/reset-password?token=invalid_dummy")
    assert res_reset.status_code == 200


def test_forgot_and_reset_routes_render_without_app_shell(app_client, monkeypatch):
    """Trang /forgot-password và /reset-password không được hiển thị AppShell (sidebar menu/header)."""
    from app.core.context import Ctx
    from app.ui.layout.shell import render_app_shell

    # Dù có hay không có session, shell cũng phải ẩn hoàn toàn trên các route auth công khai
    monkeypatch.setattr(
        "app.ui.layout.shell.get_current_ctx",
        lambda: Ctx(user_id=1, username="e2e_user", full_name="E2E User", roles=["OPERATOR"]),
    )
    for route in ("/login", "/forgot-password", "/reset-password"):
        comp = render_app_shell(route, False)
        comp_str = str(comp)
        assert "app-shell-navbar" in comp_str
        # Shell thật (dmc.AppShell) có header/navbar hiển thị và text menu/tìm kiếm; chế độ shellless chỉ có Div ẩn
        assert "Tìm kiếm menu" not in comp_str
        assert "AppShellHeader" not in comp_str
        assert "AppShellNavbar" not in comp_str


def test_forgot_password_end_to_end_flow(app_client):
    client, engine = app_client

    # 1. Thử đăng nhập mật khẩu cũ -> OK
    auth_old = authenticate_user(engine, "e2e_user", "OldPassword123!")
    assert auth_old.ok is True

    # 2. Yêu cầu đặt lại mật khẩu qua email (cần cả username và email)
    req_res = request_password_reset(engine, "e2e_user", "e2e_user@company.local")
    assert req_res.ok is True

    # 3. Lấy token mới nhất từ database
    from sqlalchemy import select

    from app.db.metadata import recon_password_reset_token

    with engine.connect() as conn:
        token_rows = conn.execute(select(recon_password_reset_token)).mappings().all()
        assert len(token_rows) == 1
        assert token_rows[0]["IS_USED"] == "N"

    # Giả lập token do người dùng nhận được qua email
    # (Trong test_password_reset_service đã test sinh raw_token và so khớp SHA-256)
    import hashlib
    raw_test_token = "e2e_manual_test_token_12345"
    token_hash = hashlib.sha256(raw_test_token.encode("utf-8")).hexdigest()

    with engine.begin() as conn:
        conn.execute(
            recon_password_reset_token.update()
            .where(recon_password_reset_token.c.ID == token_rows[0]["ID"])
            .values(TOKEN_HASH=token_hash)
        )

    # 4. Thực hiện đổi mật khẩu
    new_password = "BrandNewPassword2026@"
    reset_res = perform_password_reset(engine, raw_test_token, new_password)
    assert reset_res.ok is True

    # 5. Mật khẩu cũ không còn tác dụng
    auth_old_again = authenticate_user(engine, "e2e_user", "OldPassword123!")
    assert auth_old_again.ok is False

    # 6. Mật khẩu mới đăng nhập thành công
    auth_new = authenticate_user(engine, "e2e_user", new_password)
    assert auth_new.ok is True
    assert auth_new.data is not None
    assert auth_new.data.username == "e2e_user"
    assert auth_new.data.session_version == 2
