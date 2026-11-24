from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from sso_server.config import SSO_COOKIE_NAME
from sso_server.main import _AUTH_CODES, app

client = TestClient(app)


def test_sso_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_sso_login_whitelist_check() -> None:
    # 1. Host không nằm trong whitelist -> 400
    res = client.get("/login?redirect_uri=https://evil.com/steal-token")
    assert res.status_code == 400
    assert "không nằm trong danh sách an toàn" in res.text

    # 2. Host hợp lệ -> 200 HTML
    res_ok = client.get("/login?redirect_uri=http://localhost:8050/auth/sso/callback")
    assert res_ok.status_code == 200
    assert "Đăng nhập SSO Doanh nghiệp" in res_ok.text


def test_sso_login_flow_and_verify() -> None:
    redirect_uri = "http://localhost:8050/auth/sso/callback"

    # 1. Đăng nhập sai pass -> 400
    res_wrong = client.post(
        "/login",
        data={
            "username": "admin",
            "password": "wrongpassword",
            "redirect_uri": redirect_uri,
        },
    )
    assert res_wrong.status_code == 400
    assert "không chính xác" in res_wrong.text

    # 2. Đăng nhập đúng pass -> 302 redirect kèm cookie và code
    res_correct = client.post(
        "/login",
        data={
            "username": "admin",
            "password": "admin123",
            "redirect_uri": redirect_uri,
        },
        follow_redirects=False,
    )
    assert res_correct.status_code == 302
    assert SSO_COOKIE_NAME in res_correct.cookies

    location = res_correct.headers["location"]
    assert "code=" in location

    parsed = urlparse(location)
    query_params = parse_qs(parsed.query)
    auth_code = query_params["code"][0]
    assert auth_code is not None

    # 3. Gọi verify-code qua API
    verify_res = client.post(
        "/api/verify-code",
        json={"code": auth_code},
    )
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert data["ok"] is True
    assert data["username"] == "admin"
    assert data["full_name"] == "Quản trị viên Hệ thống"
    assert "Admin" in data["roles"]

    # 4. Kiểm tra mã dùng 1 lần (gọi lại cùng code -> 400)
    verify_again = client.post(
        "/api/verify-code",
        json={"code": auth_code},
    )
    assert verify_again.status_code == 400
    assert "đã được sử dụng" in verify_again.json()["message"]


def test_sso_cookie_auto_login() -> None:
    redirect_uri = "http://localhost:8050/auth/sso/callback"

    # Đăng nhập lấy cookie
    login_res = client.post(
        "/login",
        data={
            "username": "thanh.tran",
            "password": "password123",
            "redirect_uri": redirect_uri,
        },
        follow_redirects=False,
    )
    sso_cookie = login_res.cookies[SSO_COOKIE_NAME]

    # Bây giờ truy cập /login mà kèm SSO Cookie -> Phải tự động redirect kèm code mới
    auto_res = client.get(
        f"/login?redirect_uri={redirect_uri}",
        cookies={SSO_COOKIE_NAME: sso_cookie},
        follow_redirects=False,
    )
    assert auto_res.status_code == 302
    assert "code=" in auto_res.headers["location"]


def test_sso_expired_code() -> None:
    # Giả lập mã hết hạn
    fake_code = "expired_test_code_123"
    _AUTH_CODES[fake_code] = {
        "username": "admin",
        "redirect_uri": "http://localhost:8050/auth/sso/callback",
        "expires_at": time.time() - 10,  # Đã hết hạn 10s trước
    }

    res = client.post(
        "/api/verify-code",
        json={"code": fake_code},
    )
    assert res.status_code == 400
    assert "đã hết hạn" in res.json()["message"]
