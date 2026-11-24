from __future__ import annotations

import hmac
import secrets
import time
from typing import Any
from urllib.parse import quote, urlparse

import jwt
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from sso_server.config import (
    ALLOWED_REDIRECT_HOSTS,
    SSO_CLIENT_SECRET,
    SSO_CODE_TTL_SECONDS,
    SSO_COOKIE_NAME,
    SSO_JWT_SECRET,
    SSO_SESSION_HOURS,
)
from sso_server.users import get_sso_user, verify_sso_user

app = FastAPI(title="FastAPI SSO Server", version="1.0.0")

# Bộ lưu trữ mã xác thực tạm thời trong RAM (code -> record)
# Record: {"username": str, "redirect_uri": str, "expires_at": float}
_AUTH_CODES: dict[str, dict[str, Any]] = {}


def is_allowed_redirect(redirect_uri: str) -> bool:
    """Kiểm tra xem redirect_uri có thuộc danh sách host cho phép không."""
    if not redirect_uri:
        return False
    try:
        parsed = urlparse(redirect_uri)
        host = parsed.netloc or parsed.path.split("/")[0]
        return any(host == allowed or host.startswith(f"{allowed}:") for allowed in ALLOWED_REDIRECT_HOSTS)
    except Exception:
        return False


def get_current_sso_user(request: Request) -> str | None:
    """Đọc và giải mã cookie SSO của trình duyệt."""
    token = request.cookies.get(SSO_COOKIE_NAME)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SSO_JWT_SECRET, algorithms=["HS256"])
        username = payload.get("sub")
        if username and get_sso_user(username):
            return str(username)
    except Exception:
        pass
    return None


def issue_code_and_redirect(
    username: str, redirect_uri: str, state: str | None = None
) -> RedirectResponse:
    """Sinh mã code dùng 1 lần và chuyển hướng về ứng dụng gọi."""
    code = secrets.token_urlsafe(32)
    _AUTH_CODES[code] = {
        "username": username,
        "redirect_uri": redirect_uri,
        "expires_at": time.time() + SSO_CODE_TTL_SECONDS,
    }
    delimiter = "&" if "?" in redirect_uri else "?"
    target_url = f"{redirect_uri}{delimiter}code={code}"
    if state:
        target_url += f"&state={quote(state)}"
    return RedirectResponse(url=target_url, status_code=302)


def render_login_html(
    redirect_uri: str, error_msg: str | None = None, state: str | None = None
) -> str:
    """Render giao diện HTML đăng nhập SSO."""
    error_html = ""
    if error_msg:
        error_html = f"""
        <div style="background-color: #fee2e2; border: 1px solid #ef4444; color: #b91c1c; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 16px;">
            {error_msg}
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Đăng nhập SSO Doanh nghiệp</title>
    <style>
        :root {{
            --primary: #106ebe;
            --primary-hover: #005a9e;
            --bg: #f3f4f6;
            --card-bg: #ffffff;
            --text: #1f2937;
            --text-dim: #6b7280;
            --border: #e5e7eb;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 16px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
            width: 100%;
            max-width: 400px;
            padding: 32px;
        }}
        .logo-row {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 8px;
        }}
        .logo-badge {{
            background: var(--primary);
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 18px;
        }}
        h2 {{ font-size: 20px; font-weight: 700; color: #111827; }}
        .subtitle {{ font-size: 13px; color: var(--text-dim); margin-bottom: 24px; }}
        .form-group {{ margin-bottom: 18px; }}
        label {{ display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; }}
        input[type="text"], input[type="password"] {{
            width: 100%;
            padding: 10px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.15s;
        }}
        input:focus {{ border-color: var(--primary); ring: 2px solid rgba(16, 110, 190, 0.2); }}
        button.btn-submit {{
            width: 100%;
            padding: 11px 16px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.15s;
            margin-top: 6px;
        }}
        button.btn-submit:hover {{ background: var(--primary-hover); }}
        .footer-note {{
            margin-top: 24px;
            text-align: center;
            font-size: 12px;
            color: var(--text-dim);
            line-height: 1.5;
        }}
        .badge-secure {{
            display: inline-block;
            background: #ecfdf5;
            color: #065f46;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo-row">
            <div class="logo-badge">SSO</div>
            <div>
                <h2>Xác thực Tập trung</h2>
                <span class="badge-secure">Cổng đăng nhập an toàn</span>
            </div>
        </div>
        <p class="subtitle">Đăng nhập một lần cho ReconHub và hệ thống nội bộ</p>

        {error_html}

        <form method="POST" action="/login">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <input type="hidden" name="state" value="{state or ''}">
            <div class="form-group">
                <label for="username">Tên đăng nhập</label>
                <input type="text" id="username" name="username" placeholder="ví dụ: admin, thanh.tran" required autofocus autocomplete="username">
            </div>
            <div class="form-group">
                <label for="password">Mật khẩu</label>
                <input type="password" id="password" name="password" placeholder="••••••••" required autocomplete="current-password">
            </div>
            <button type="submit" class="btn-submit">Đăng nhập tiếp tục</button>
        </form>

        <div class="footer-note">
            Tài khoản mẫu: <code>admin / admin123</code> hoặc <code>thanh.tran / password123</code><br>
            Hệ thống nội bộ — Chỉ truy cập khi được phân quyền.
        </div>
    </div>
</body>
</html>
"""


@app.get("/health")
def health_check() -> dict[str, str]:
    """Kiểm tra tình trạng hoạt động của dịch vụ SSO."""
    return {"status": "ok", "service": "fastapi-sso-server"}


@app.get("/login", response_class=HTMLResponse)
def get_login_page(request: Request, redirect_uri: str, state: str | None = None) -> Any:
    """Trang đăng nhập SSO."""
    if not is_allowed_redirect(redirect_uri):
        raise HTTPException(
            status_code=400,
            detail=f"redirect_uri '{redirect_uri}' không nằm trong danh sách an toàn",
        )

    # Nếu đã có SSO Session Cookie -> tự động cấp code và redirect ngay (Single Sign-On!)
    existing_user = get_current_sso_user(request)
    if existing_user:
        return issue_code_and_redirect(existing_user, redirect_uri, state=state)

    return HTMLResponse(content=render_login_html(redirect_uri, state=state))


@app.post("/login")
def submit_login(
    redirect_uri: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    state: str | None = Form(None),
) -> Any:
    """Xử lý gửi form đăng nhập."""
    if not is_allowed_redirect(redirect_uri):
        raise HTTPException(status_code=400, detail="redirect_uri không an toàn")

    norm_user = username.strip().lower()
    user = verify_sso_user(norm_user, password)
    if not user:
        return HTMLResponse(
            content=render_login_html(
                redirect_uri,
                error_msg="Tên đăng nhập hoặc mật khẩu không chính xác.",
                state=state,
            ),
            status_code=400,
        )

    # 1. Sinh SSO Cookie (JWT) hạn 8 giờ
    sso_token = jwt.encode(
        {"sub": norm_user, "exp": time.time() + (SSO_SESSION_HOURS * 3600)},
        SSO_JWT_SECRET,
        algorithm="HS256",
    )

    # 2. Sinh mã code và redirect
    response = issue_code_and_redirect(norm_user, redirect_uri, state=state)
    response.set_cookie(
        key=SSO_COOKIE_NAME,
        value=sso_token,
        httponly=True,
        samesite="lax",
        max_age=SSO_SESSION_HOURS * 3600,
    )
    return response


class VerifyCodeRequest(BaseModel):
    code: str
    client_secret: str | None = None


@app.post("/api/verify-code")
def verify_code(req: VerifyCodeRequest) -> JSONResponse:
    """Endpoint để ứng dụng client (ReconHub) gọi ngầm đổi mã code lấy profile."""
    # Kiểm tra tính hợp lệ của client_secret qua hmac để phòng chống Timing Attack
    if not req.client_secret or not hmac.compare_digest(req.client_secret, SSO_CLIENT_SECRET):
        return JSONResponse(
            status_code=401,
            content={"ok": False, "message": "Client secret không hợp lệ hoặc bị thiếu"},
        )

    # Lấy và xóa ngay khỏi RAM (chỉ dùng đúng 1 lần)
    record = _AUTH_CODES.pop(req.code, None)
    if not record:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": "Mã xác thực không hợp lệ hoặc đã được sử dụng"},
        )

    if record["expires_at"] < time.time():
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": "Mã xác thực đã hết hạn (quá 60 giây)"},
        )

    user = get_sso_user(record["username"])
    if not user:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "message": "Không tìm thấy thông tin người dùng"},
        )

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "username": record["username"],
            "full_name": user["full_name"],
            "email": user["email"],
            "roles": user["roles"],
        },
    )


@app.get("/logout")
def sso_logout(redirect_uri: str | None = None) -> Any:
    """Đăng xuất phiên SSO."""
    dest = (
        redirect_uri
        if redirect_uri and is_allowed_redirect(redirect_uri)
        else "/login?redirect_uri=http://localhost:8050/auth/sso/callback"
    )
    response = RedirectResponse(url=dest, status_code=302)
    response.delete_cookie(SSO_COOKIE_NAME)
    return response
