from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import dash_mantine_components as dmc
from dash import Dash
from flask import redirect, request, session

from app.core.config import get_settings
from app.core.session import get_user_session_state
from app.db.engine import get_recon_engine
from app.routes.auth_routes import auth_bp
from app.routes.file_routes import file_bp
from app.routes.health import health_bp
from app.services.data_source import sync_current_metadata_source
from app.ui.layout import create_shell_layout
from app.ui.theme import THEME

UI_DIR = Path(__file__).resolve().parent


def create_app() -> Dash:
    """Tạo và cấu hình ứng dụng Dash & Flask server."""
    settings = get_settings()

    import dash._pages as _pages

    _pages.PAGE_REGISTRY.clear()

    dash_app = Dash(
        __name__,
        use_pages=True,
        pages_folder=str(UI_DIR / "pages"),
        assets_folder=str(UI_DIR / "assets"),
        title="ReconHub",
        update_title="",
        suppress_callback_exceptions=True,
    )

    flask_server = dash_app.server
    flask_server.secret_key = settings.FLASK_SECRET_KEY
    flask_server.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=settings.SESSION_HOURS)
    flask_server.config["SESSION_COOKIE_HTTPONLY"] = True
    flask_server.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    flask_server.config["SESSION_COOKIE_SECURE"] = not (settings.APP_ENV == "dev" or settings.DASH_DEBUG)

    flask_server.register_blueprint(health_bp)
    flask_server.register_blueprint(auth_bp)
    flask_server.register_blueprint(file_bp)

    try:
        sync_current_metadata_source()
    except Exception:
        pass

    @flask_server.before_request  # type: ignore[untyped-decorator]
    def auth_and_security_guard() -> Any:
        path = request.path

        # 1. Kiểm tra Origin đối với AJAX / Dash component update
        if path == "/_dash-update-component":
            origin = request.headers.get("Origin")
            if origin:
                parsed_origin = urlparse(origin)
                origin_host = parsed_origin.netloc or parsed_origin.path
                if origin_host and origin_host != request.host:
                    return "Origin không hợp lệ", 403

        # 2. Danh sách đường dẫn mở công khai
        public_prefixes = (
            "/health",
            "/assets",
            "/_dash-component-suites",
            "/_dash-layout",
            "/_dash-dependencies",
            "/favicon.ico",
        )
        if path == "/login" or path.startswith(public_prefixes):
            return None

        # 3. Với Dash component update khi chưa đăng nhập
        if "user_id" not in session:
            if path == "/_dash-update-component":
                # Cho phép callback nếu người dùng đang ở trang login
                referer = request.headers.get("Referer", "")
                if "/login" in referer:
                    return None
                return {"error": "UNAUTHENTICATED"}, 401
            return redirect("/login")

        # 4. Người dùng đã đăng nhập: xác thực trạng thái phiên qua DB
        user_id = int(session["user_id"])
        engine = get_recon_engine()
        state = get_user_session_state(engine, user_id)

        # Mismatch session_version hoặc user bị vô hiệu hóa
        if state is None:
            session.clear()
            return redirect("/login")

        session_ver, is_active, must_change = state
        if is_active != "Y" or session_ver != int(session.get("session_version", -1)):
            session.clear()
            return redirect("/login")

        # Cập nhật cờ bắt buộc đổi mật khẩu
        must_change_pw = must_change == "Y"
        session["must_change_pw"] = must_change_pw

        # Nếu bắt buộc đổi mật khẩu, chỉ cho phép trang đổi mật khẩu hoặc đăng xuất
        if must_change_pw:
            allowed_pw_paths = ("/login", "/account", "/logout")
            if not any(path.startswith(p) for p in allowed_pw_paths):
                if path == "/_dash-update-component":
                    return None  # Cho phép các callback UI chạy
                return redirect("/login?step=change")

        return None

    dash_app.layout = dmc.MantineProvider(
        children=create_shell_layout(),
        theme=THEME,
    )

    return dash_app


app = create_app()
server = app.server

if __name__ == "__main__":
    _settings = get_settings()
    app.run(port=_settings.DASH_PORT, debug=_settings.DASH_DEBUG)
