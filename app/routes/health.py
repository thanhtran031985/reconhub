from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify
from sqlalchemy import text

from app.core.config import get_settings
from app.db.engine import get_db_engine

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health() -> Any:
    """Kiểm tra sức khỏe hệ thống và kết nối CSDL RECON_APP."""
    settings = get_settings()
    db_status = "up"
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"down: {exc}"

    is_healthy = db_status == "up"
    return jsonify(
        {
            "status": "ok" if is_healthy else "error",
            "db": db_status,
            "env": settings.APP_ENV,
        }
    ), 200 if is_healthy else 503
