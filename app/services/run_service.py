from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_app_setting,
    recon_audit_log,
    recon_data_source,
    recon_file,
    recon_run,
    recon_run_queue,
    recon_template,
    recon_template_version,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.run import CreateRunParams, PrecheckParams
from app.schemas.template_config import TemplateConfig
from app.services import service


@service
def precheck(
    ctx: Ctx,
    params: PrecheckParams,
) -> dict[str, Any]:
    """Kiểm tra điều kiện trước khi tạo run: thời gian, dung lượng, PROD confirm, trạng thái hệ thống."""
    engine = get_recon_engine()

    # 1. Kiểm tra chế độ bảo trì MAINTENANCE
    with engine.connect() as conn:
        setting = conn.execute(
            select(recon_app_setting).where(recon_app_setting.c.KEY == "MAINTENANCE")
        ).mappings().first()
        if setting and setting["VALUE"] == "Y" and Role.ADMIN not in ctx.roles:
            raise ServiceError(
                ErrorCode.MAINTENANCE_MODE,
                "Hệ thống đang trong chế độ bảo trì. Chỉ quản trị viên mới có thể thực hiện thao tác này.",
            )

    # 2. Kiểm tra khoảng thời gian
    if params.p_from > params.p_to:
        raise ServiceError(
            ErrorCode.INVALID_RANGE,
            "Khoảng thời gian không hợp lệ: 'Từ ngày' phải trước hoặc bằng 'Đến ngày'.",
        )

    # 3. Đọc template version và cấu hình
    with engine.connect() as conn:
        tmpl = conn.execute(
            select(recon_template).where(recon_template.c.ID == params.template_id)
        ).mappings().first()
        if not tmpl:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template với id {params.template_id}.")

        tv_stmt = select(recon_template_version).where(recon_template_version.c.TEMPLATE_ID == params.template_id)
        if params.template_version is not None:
            tv_stmt = tv_stmt.where(recon_template_version.c.VERSION == params.template_version)
        else:
            tv_stmt = tv_stmt.where(recon_template_version.c.STATUS == "ACTIVE")

        tv = conn.execute(tv_stmt).mappings().first()
        if not tv:
            raise ServiceError(
                ErrorCode.TEMPLATE_NOT_ACTIVE,
                "Template chưa có phiên bản kích hoạt (ACTIVE) để thực hiện đối soát.",
            )

        cfg_dict = tv["CONFIG_JSON"]
        cfg = TemplateConfig.model_validate(cfg_dict)

        # Kiểm tra max_range_days từ time_filter (mặc định 93 ngày)
        max_days = cfg.time_filter.max_range_days if cfg.time_filter and cfg.time_filter.max_range_days else 93
        delta_seconds = (params.p_to - params.p_from).total_seconds()
        if delta_seconds > max_days * 86400:
            raise ServiceError(
                ErrorCode.RANGE_TOO_LARGE,
                f"Khoảng thời gian ({int(delta_seconds / 86400)} ngày) vượt quá giới hạn tối đa cho phép của template ({max_days} ngày).",
            )

        # 4. Kiểm tra Data Source và xác nhận PROD
        ds_id = params.data_source_id or tv["DATA_SOURCE_ID"]
        if not ds_id:
            raise ServiceError(ErrorCode.NOT_FOUND, "Template chưa được cấu hình Data Source nguồn.")

        ds = conn.execute(
            select(recon_data_source).where(recon_data_source.c.ID == ds_id)
        ).mappings().first()
        if not ds:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy Data Source với id {ds_id}.")

        if ds["ENV"] == "PROD" and not params.confirm_prod:
            raise ServiceError(
                ErrorCode.PROD_CONFIRM_REQUIRED,
                "Data Source đích thuộc môi trường PROD. Bạn cần xác nhận trước khi chạy.",
            )

        est_rows: int | None = None
        if params.file_id:
            f_row = conn.execute(
                select(recon_file).where(recon_file.c.ID == params.file_id)
            ).mappings().first()
            if f_row:
                # Ước lượng số dòng thô từ dung lượng file
                size = f_row["SIZE_BYTES"] or 0
                est_rows = max(1, int(size // 150))

    return {
        "valid": True,
        "data_source_env": str(ds["ENV"]),
        "est_excel_rows": est_rows,
        "warnings": [],
    }


@service
def create_run(
    ctx: Ctx,
    params: CreateRunParams,
) -> dict[str, Any]:
    """Tạo run đối soát mới và đẩy vào hàng đợi RECON_RUN_QUEUE."""
    require_role(ctx, Role.OPERATOR, Role.TEMPLATE_OWNER, Role.ADMIN)

    # 1. Thực hiện precheck
    pre_res = precheck(
        ctx,
        PrecheckParams(
            template_id=params.template_id,
            template_version=params.template_version,
            data_source_id=params.data_source_id,
            p_from=params.p_from,
            p_to=params.p_to,
            confirm_prod=params.confirm_prod,
            file_id=params.file_id,
        ),
    )
    if not pre_res.ok:
        err_msg = pre_res.message or "Lỗi xác thực tham số precheck."
        raise ServiceError(pre_res.code or ErrorCode.VALIDATION_ERROR, err_msg, pre_res.details)

    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        # 2. Lấy template và template_version
        tmpl = conn.execute(
            select(recon_template).where(recon_template.c.ID == params.template_id)
        ).mappings().first()
        if not tmpl:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template với id {params.template_id}.")

        tv_stmt = select(recon_template_version).where(recon_template_version.c.TEMPLATE_ID == params.template_id)
        if params.template_version is not None:
            tv_stmt = tv_stmt.where(recon_template_version.c.VERSION == params.template_version)
        else:
            tv_stmt = tv_stmt.where(recon_template_version.c.STATUS == "ACTIVE")

        tv = conn.execute(tv_stmt).mappings().first()
        if not tv:
            raise ServiceError(ErrorCode.TEMPLATE_NOT_ACTIVE, "Template chưa có phiên bản ACTIVE.")

        version = int(tv["VERSION"])
        cfg = TemplateConfig.model_validate(tv["CONFIG_JSON"])

        # 3. Xác định profile, data source, sheet name
        profile_code = params.profile_code or cfg.profiles[0].code
        # Kiểm tra profile_code có tồn tại trong config
        valid_profiles = [p.code for p in cfg.profiles]
        if profile_code not in valid_profiles:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Mã Profile '{profile_code}' không tồn tại trong template. Hợp lệ: {valid_profiles}.",
            )

        data_source_id = params.data_source_id or tv["DATA_SOURCE_ID"]
        sheet_name = params.sheet_name or cfg.file.sheet

        # Kiểm tra file_id
        f_row = conn.execute(
            select(recon_file).where(recon_file.c.ID == params.file_id)
        ).mappings().first()
        if not f_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy file với id {params.file_id}.")
        if f_row["PURGED_AT"] is not None:
            raise ServiceError(ErrorCode.TEMP_DATA_PURGED, "File Excel đã bị xóa theo yêu cầu.")

        # 4. Thêm bản ghi RECON_RUN
        run_stmt = (
            recon_run.insert()
            .values(
                TEMPLATE_ID=params.template_id,
                TEMPLATE_VERSION=version,
                PROFILE_CODE=profile_code,
                PROFILE_OVERRIDE=params.profile_override,
                FILE_ID=params.file_id,
                EXCEL_LOAD_ID=None,
                SHEET_NAME=sheet_name,
                DATA_SOURCE_ID=data_source_id,
                P_FROM=params.p_from,
                P_TO=params.p_to,
                PARAMS_JSON=params.params,
                APPLY_RANGE_EXCEL="Y" if params.apply_range_excel else "N",
                STATUS="QUEUED",
                PROGRESS_PCT=0,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
            )
        )
        res = conn.execute(run_stmt)
        pk = res.inserted_primary_key
        if not pk:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không thể tạo bản ghi RECON_RUN.")
        run_id = int(pk[0])

        # 5. Thêm bản ghi RECON_RUN_QUEUE
        queue_stmt = recon_run_queue.insert().values(
            RUN_ID=run_id,
            STATUS="READY",
            RETRY_COUNT=0,
            ENQUEUED_AT=now,
        )
        conn.execute(queue_stmt)

        # 6. Ghi audit log
        audit_stmt = recon_audit_log.insert().values(
            ENTITY="RECON_RUN",
            ENTITY_ID=str(run_id),
            ACTION="CREATE_RUN",
            OLD_JSON=None,
            NEW_JSON={
                "run_id": run_id,
                "template_id": params.template_id,
                "template_version": version,
                "profile_code": profile_code,
                "file_id": params.file_id,
                "data_source_id": data_source_id,
                "p_from": params.p_from.isoformat(),
                "p_to": params.p_to.isoformat(),
            },
            ACTOR=ctx.username,
            CREATED_AT=now,
        )
        conn.execute(audit_stmt)

    return {
        "run_id": run_id,
        "status": "QUEUED",
        "created_at": now.isoformat(),
    }
