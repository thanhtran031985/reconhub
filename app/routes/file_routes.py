from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, abort, send_file

from app.core.session import get_current_ctx
from app.schemas.errors import ErrorCode
from app.services.file_service import get_file

file_bp = Blueprint("file_routes", __name__)


@file_bp.route("/download/file/<int:file_id>", methods=["GET"])
def download_file(file_id: int) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        abort(401)

    res = get_file(ctx, file_id)
    if not res.ok or not isinstance(res.data, dict):
        if res.code == ErrorCode.TEMP_DATA_PURGED:
            return "File Excel gốc đã bị xóa theo yêu cầu.", 410
        if res.code == ErrorCode.NOT_FOUND:
            abort(404)
        abort(403)

    f_info: dict[str, Any] = res.data
    storage_path = Path(str(f_info["storage_path"]))
    if not storage_path.exists():
        return "File Excel gốc không còn trên máy chủ.", 410

    return send_file(
        storage_path,
        as_attachment=True,
        download_name=f_info["original_name"],
    )
