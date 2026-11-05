from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import recon_file, recon_template
from app.engine.template_sample import build_template_preview_excel
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import TemplateConfig
from app.services import service
from app.services.template import get_template, save_draft_template


@service
def export_template(
    ctx: Ctx,
    template_id: int,
    version: int | None = None,
) -> dict[str, Any]:
    """Xuất thông tin template và cấu hình CONFIG_JSON ra định dạng JSON."""
    require_role(ctx)
    tmpl_res = get_template(ctx, template_id=template_id, version=version)
    if not tmpl_res.ok or tmpl_res.data is None:
        raise ServiceError(tmpl_res.code or ErrorCode.NOT_FOUND, tmpl_res.message or "Không tìm thấy template")

    tmpl_data = dict(tmpl_res.data)
    return {
        "code": tmpl_data["code"],
        "name": tmpl_data["name"],
        "description": tmpl_data["description"],
        "version": tmpl_data["current_version"],
        "config": tmpl_data["config"],
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": ctx.username,
    }


@service
def export_template_sample_excel(
    ctx: Ctx,
    template_id: int,
    version: int | None = None,
) -> dict[str, Any]:
    """Xuất file Excel mẫu của template từ đúng file mẫu đã tải lên.

    Nội dung là header và 5 dòng dữ liệu đầu tiên như bảng "Xem trước 5 dòng"
    ở trang sửa template, không tự sinh giá trị ví dụ. Template chưa có file
    mẫu hoặc file mẫu đã mất thì báo lỗi rõ, không trả file ví dụ thay thế.
    """
    require_role(ctx)
    tmpl_res = get_template(ctx, template_id=template_id, version=version)
    if not tmpl_res.ok or tmpl_res.data is None:
        raise ServiceError(tmpl_res.code or ErrorCode.NOT_FOUND, tmpl_res.message or "Không tìm thấy template")

    tmpl_data = dict(tmpl_res.data)
    try:
        config = TemplateConfig.model_validate(tmpl_data["config"])
    except Exception as exc:
        raise ServiceError(ErrorCode.TEMPLATE_INVALID, f"Cấu hình template không hợp lệ: {exc}") from exc

    sample_file_id = tmpl_data.get("sample_file_id")
    if not sample_file_id:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Template chưa có file mẫu tải lên. Hãy mở trang sửa template và tải file mẫu ở bước 1.",
        )

    engine = get_recon_engine()
    with engine.connect() as conn:
        file_row = conn.execute(select(recon_file).where(recon_file.c.ID == int(sample_file_id))).mappings().first()
    storage_path_str = str(file_row["STORAGE_PATH"]) if file_row else ""
    if (
        not file_row
        or file_row.get("PURGED_AT") is not None
        or not storage_path_str
        or not Path(storage_path_str).exists()
    ):
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            "Không tìm thấy file mẫu đã tải lên của template (file có thể đã bị xóa). "
            "Hãy tải lại file mẫu ở trang sửa template.",
        )

    try:
        content = build_template_preview_excel(Path(storage_path_str), config.file)
    except ValueError as exc:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, str(exc)) from exc

    code_val = str(tmpl_data["code"] or "template")
    return {
        "code": code_val,
        "filename": f"{code_val}_mau.xlsx",
        "content": content,
    }


@service
def import_template(
    ctx: Ctx,
    data: dict[str, Any],
    overwrite: bool = False,
) -> dict[str, Any]:
    """Nhập template từ dictionary/file JSON và xác thực cấu hình chặt chẽ."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)

    code = str(data.get("code") or "").strip().upper()
    if not code:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Dữ liệu nhập thiếu 'code' template")

    name = str(data.get("name") or code).strip()
    description = data.get("description")

    raw_config = data.get("config")
    if not raw_config:
        # Trường hợp file JSON chỉ chứa trực tiếp TemplateConfig
        raw_config = data

    try:
        validated_config = TemplateConfig.model_validate(raw_config)
    except Exception as exc:
        raise ServiceError(ErrorCode.TEMPLATE_INVALID, f"Cấu hình template không hợp lệ: {exc}") from exc

    engine = get_recon_engine()
    with engine.connect() as conn:
        existing = conn.execute(select(recon_template).where(recon_template.c.CODE == code)).mappings().first()

    if existing is not None:
        if not overwrite:
            raise ServiceError(
                ErrorCode.TEMPLATE_CODE_EXISTS,
                f"Template với mã '{code}' đã tồn tại. Đặt overwrite=True để ghi đè.",
            )
        row_version = int(existing["ROW_VERSION"])
    else:
        row_version = None

    save_res = save_draft_template(
        ctx=ctx,
        code=code,
        name=name,
        config=validated_config,
        description=description,
        row_version=row_version,
    )
    if not save_res.ok or save_res.data is None:
        raise ServiceError(save_res.code or ErrorCode.VALIDATION_ERROR, save_res.message or "Lưu template thất bại")

    return dict(save_res.data)
