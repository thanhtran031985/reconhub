from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import recon_file
from app.engine.reader import list_sheets
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service


def _validate_magic_bytes(ext: str, content: bytes) -> None:
    """Xác thực magic bytes của file để ngăn chặn đổi phần mở rộng trái phép."""
    if ext in (".xlsx", ".xlsm", ".xltx"):
        if not content.startswith(b"PK\x03\x04"):
            raise ServiceError(
                ErrorCode.FILE_TYPE_NOT_ALLOWED,
                "Nội dung file không khớp với định dạng Excel (.xlsx/.xlsm). File có thể đã bị đổi phần mở rộng hoặc bị hỏng.",
            )
    elif ext == ".xls":
        if not content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            raise ServiceError(
                ErrorCode.FILE_TYPE_NOT_ALLOWED,
                "Nội dung file không khớp với định dạng Excel 97-2003 (.xls). File có thể đã bị đổi phần mở rộng.",
            )
    elif ext == ".csv":
        sample = content[:8192]
        if b"\x00" in sample:
            raise ServiceError(
                ErrorCode.FILE_TYPE_NOT_ALLOWED,
                "File CSV chứa ký tự nhị phân không hợp lệ.",
            )
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            try:
                sample.decode("latin-1")
            except Exception:
                raise ServiceError(
                    ErrorCode.FILE_TYPE_NOT_ALLOWED,
                    "Không thể giải mã nội dung file CSV dạng văn bản.",
                ) from None
    else:
        raise ServiceError(
            ErrorCode.FILE_TYPE_NOT_ALLOWED,
            f"Phần mở rộng '{ext}' không được hỗ trợ. Chỉ chấp nhận .xlsx, .xls, .csv.",
        )


@service
def upload_file(
    ctx: Ctx,
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    """Tải lên file dữ liệu Excel/CSV, kiểm tra magic bytes, lưu kho và ghi nhận RECON_FILE."""
    require_role(ctx, Role.OPERATOR, Role.TEMPLATE_OWNER, Role.ADMIN)

    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise ServiceError(
            ErrorCode.FILE_TOO_LARGE,
            f"Dung lượng file ({len(content) // (1024 * 1024)}MB) vượt quá giới hạn tối đa cho phép ({settings.MAX_UPLOAD_SIZE_MB}MB).",
        )

    ext = Path(filename).suffix.lower()
    _validate_magic_bytes(ext, content)

    sha = hashlib.sha256(content).hexdigest()

    storage_base = Path(settings.RECON_STORAGE_DIR) / "files"
    storage_base.mkdir(parents=True, exist_ok=True)
    storage_path = storage_base / f"{sha}{ext}"

    if not storage_path.exists():
        storage_path.write_bytes(content)

    sheets = list_sheets(storage_path)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    engine = get_recon_engine()

    with engine.begin() as conn:
        stmt = (
            recon_file.insert()
            .values(
                SHA256=sha,
                ORIGINAL_NAME=filename,
                SIZE_BYTES=len(content),
                STORAGE_PATH=str(storage_path),
                SHEETS_JSON=sheets,
                UPLOADED_BY=ctx.username,
                UPLOADED_AT=now,
                PURGED_AT=None,
            )
            .returning(recon_file.c.ID)
        )
        file_id = conn.scalar(stmt)

    return {
        "id": int(file_id) if file_id else 0,
        "sha256": sha,
        "original_name": filename,
        "size_bytes": len(content),
        "sheets": sheets,
        "storage_path": str(storage_path),
        "uploaded_by": ctx.username,
        "uploaded_at": now.isoformat(),
    }


@service
def get_file(ctx: Ctx, file_id: int) -> dict[str, Any]:
    """Lấy thông tin file tải lên. Báo lỗi TEMP_DATA_PURGED nếu file đã bị xóa."""
    require_role(ctx)

    engine = get_recon_engine()
    with engine.connect() as conn:
        rec = conn.execute(select(recon_file).where(recon_file.c.ID == file_id)).mappings().first()

    if not rec:
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy file với id {file_id}.")

    storage_path_str = rec["STORAGE_PATH"]
    purged_at = rec["PURGED_AT"]

    if purged_at is not None or not storage_path_str or not Path(str(storage_path_str)).exists():
        raise ServiceError(
            ErrorCode.TEMP_DATA_PURGED,
            f"File Excel gốc '{rec['ORIGINAL_NAME']}' đã bị xóa theo yêu cầu.",
        )

    return {
        "id": int(rec["ID"]),
        "sha256": str(rec["SHA256"]),
        "original_name": str(rec["ORIGINAL_NAME"]),
        "size_bytes": int(rec["SIZE_BYTES"]),
        "storage_path": str(storage_path_str),
        "sheets": rec["SHEETS_JSON"] if isinstance(rec["SHEETS_JSON"], list) else [],
        "uploaded_by": str(rec["UPLOADED_BY"]),
        "uploaded_at": rec["UPLOADED_AT"],
    }
