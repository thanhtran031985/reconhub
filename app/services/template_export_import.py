from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import recon_template
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
        existing = conn.execute(
            select(recon_template).where(recon_template.c.CODE == code)
        ).mappings().first()

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
