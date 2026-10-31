from __future__ import annotations

from typing import Any

from flask import Blueprint, redirect

from app.core.session import logout_session

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout() -> Any:
    """Đăng xuất người dùng và chuyển về trang đăng nhập."""
    logout_session()
    return redirect("/login")
