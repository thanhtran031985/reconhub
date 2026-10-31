from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl
from sqlalchemy import desc, func, select

from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_app_setting,
    recon_audit_log,
    recon_data_source,
    recon_excel_row,
    recon_file,
    recon_invalid_row,
    recon_issue,
    recon_issue_reason,
    recon_result_diff,
    recon_result_row,
    recon_run,
    recon_run_queue,
    recon_run_summary,
    recon_template,
    recon_template_version,
    recon_user,
)
from app.engine.summary import build_columns_metadata
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.run import CreateRunParams, PrecheckParams, RunListFilter, RunRowsFilter
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
        setting = (
            conn.execute(select(recon_app_setting).where(recon_app_setting.c.KEY == "MAINTENANCE")).mappings().first()
        )
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
        tmpl = conn.execute(select(recon_template).where(recon_template.c.ID == params.template_id)).mappings().first()
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

        ds = conn.execute(select(recon_data_source).where(recon_data_source.c.ID == ds_id)).mappings().first()
        if not ds:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy Data Source với id {ds_id}.")

        if ds["ENV"] == "PROD" and not params.confirm_prod:
            raise ServiceError(
                ErrorCode.PROD_CONFIRM_REQUIRED,
                "Data Source đích thuộc môi trường PROD. Bạn cần xác nhận trước khi chạy.",
            )

        est_rows: int | None = None
        if params.file_id:
            f_row = conn.execute(select(recon_file).where(recon_file.c.ID == params.file_id)).mappings().first()
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
        tmpl = conn.execute(select(recon_template).where(recon_template.c.ID == params.template_id)).mappings().first()
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
        f_row = conn.execute(select(recon_file).where(recon_file.c.ID == params.file_id)).mappings().first()
        if not f_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy file với id {params.file_id}.")
        if f_row["PURGED_AT"] is not None:
            raise ServiceError(ErrorCode.TEMP_DATA_PURGED, "File Excel đã bị xóa theo yêu cầu.")

        # 4. Thêm bản ghi RECON_RUN
        run_stmt = recon_run.insert().values(
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


@service
def get_run(ctx: Ctx, run_id: int) -> dict[str, Any]:
    """Lấy thông tin chi tiết của một lần chạy (run) kèm thống kê kết quả."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        stmt = (
            select(
                recon_run,
                recon_template.c.CODE.label("TEMPLATE_CODE"),
                recon_template.c.NAME.label("TEMPLATE_NAME"),
            )
            .select_from(recon_run.outerjoin(recon_template, recon_run.c.TEMPLATE_ID == recon_template.c.ID))
            .where(recon_run.c.ID == run_id)
        )
        row = conn.execute(stmt).mappings().first()
        if not row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy run với id {run_id}.")

        # Đọc summary nếu có
        summ_row = (
            conn.execute(select(recon_run_summary).where(recon_run_summary.c.RUN_ID == run_id)).mappings().first()
        )

        summary_dict = dict(summ_row) if summ_row else None

    return {
        "id": int(row["ID"]),
        "template_id": int(row["TEMPLATE_ID"]),
        "template_code": str(row["TEMPLATE_CODE"] or ""),
        "template_name": str(row["TEMPLATE_NAME"] or ""),
        "template_version": int(row["TEMPLATE_VERSION"]),
        "profile_code": str(row["PROFILE_CODE"]),
        "status": str(row["STATUS"]),
        "stage": row["STAGE"],
        "progress_pct": int(row["PROGRESS_PCT"] or 0),
        "file_id": row["FILE_ID"],
        "data_source_id": row["DATA_SOURCE_ID"],
        "sheet_name": row["SHEET_NAME"],
        "p_from": row["P_FROM"].isoformat() if row["P_FROM"] else None,
        "p_to": row["P_TO"].isoformat() if row["P_TO"] else None,
        "apply_range_excel": row["APPLY_RANGE_EXCEL"] == "Y",
        "created_by": row["CREATED_BY"],
        "created_at": row["CREATED_AT"].isoformat() if row["CREATED_AT"] else None,
        "started_at": row["STARTED_AT"].isoformat() if row["STARTED_AT"] else None,
        "finished_at": row["FINISHED_AT"].isoformat() if row["FINISHED_AT"] else None,
        "checked_by": row["CHECKED_BY"],
        "checked_at": row["CHECKED_AT"].isoformat() if row["CHECKED_AT"] else None,
        "temp_purged_at": row["TEMP_PURGED_AT"].isoformat() if row["TEMP_PURGED_AT"] else None,
        "temp_purged_by": row["TEMP_PURGED_BY"],
        "error_code": row["ERROR_CODE"],
        "error_msg": row["ERROR_MSG"],
        "summary": summary_dict,
    }


@service
def list_runs(ctx: Ctx, filter: RunListFilter) -> dict[str, Any]:
    """Lấy danh sách các lần chạy có phân trang và bộ lọc."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        base_query = select(
            recon_run,
            recon_template.c.CODE.label("TEMPLATE_CODE"),
            recon_template.c.NAME.label("TEMPLATE_NAME"),
            recon_file.c.ORIGINAL_NAME.label("FILENAME"),
            recon_file.c.SIZE_BYTES.label("FILE_SIZE"),
            recon_run_summary.c.CNT_MATCHED.label("CNT_MATCHED"),
            recon_run_summary.c.CNT_MISMATCH.label("CNT_MISMATCH"),
            recon_run_summary.c.CNT_MISSING_IN_DB.label("CNT_MISSING_IN_DB"),
            recon_run_summary.c.CNT_MISSING_IN_EXCEL.label("CNT_MISSING_IN_EXCEL"),
            recon_run_summary.c.EXCEL_ROWS_INVALID.label("CNT_INVALID"),
        ).select_from(
            recon_run.outerjoin(recon_template, recon_run.c.TEMPLATE_ID == recon_template.c.ID)
            .outerjoin(recon_file, recon_run.c.FILE_ID == recon_file.c.ID)
            .outerjoin(recon_run_summary, recon_run.c.ID == recon_run_summary.c.RUN_ID)
        )

        if filter.template_id:
            base_query = base_query.where(recon_run.c.TEMPLATE_ID == filter.template_id)
        if filter.status:
            base_query = base_query.where(recon_run.c.STATUS == filter.status)
        if filter.created_by:
            base_query = base_query.where(recon_run.c.CREATED_BY == filter.created_by)
        if filter.from_date:
            base_query = base_query.where(recon_run.c.CREATED_AT >= filter.from_date)
        if filter.to_date:
            base_query = base_query.where(recon_run.c.CREATED_AT <= filter.to_date)
        if filter.is_checked is not None:
            if filter.is_checked:
                base_query = base_query.where(recon_run.c.CHECKED_AT.is_not(None))
            else:
                base_query = base_query.where(recon_run.c.CHECKED_AT.is_(None))
        if filter.is_temp_purged is not None:
            if filter.is_temp_purged:
                base_query = base_query.where(recon_run.c.TEMP_PURGED_AT.is_not(None))
            else:
                base_query = base_query.where(recon_run.c.TEMP_PURGED_AT.is_(None))
        if filter.filename:
            base_query = base_query.where(recon_file.c.ORIGINAL_NAME.ilike(f"%{filter.filename.strip()}%"))

        # Đếm tổng số
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = conn.execute(count_stmt).scalar() or 0

        # Phân trang và sắp xếp
        offset = (filter.page - 1) * filter.page_size
        query = base_query.order_by(desc(recon_run.c.CREATED_AT)).limit(filter.page_size).offset(offset)
        rows = conn.execute(query).mappings().fetchall()

        items = []
        for r in rows:
            cnt_matched = r["CNT_MATCHED"] or 0
            cnt_mismatch = r["CNT_MISMATCH"] or 0
            cnt_missing_db = r["CNT_MISSING_IN_DB"] or 0
            cnt_missing_excel = r["CNT_MISSING_IN_EXCEL"] or 0
            total_compared = cnt_matched + cnt_mismatch + cnt_missing_db + cnt_missing_excel
            match_pct = (
                round((cnt_matched / total_compared) * 100, 1)
                if total_compared > 0
                else (100.0 if r["STATUS"] == "DONE" and (r["CNT_INVALID"] or 0) == 0 else None)
            )
            items.append(
                {
                    "id": int(r["ID"]),
                    "template_id": int(r["TEMPLATE_ID"]),
                    "template_code": str(r["TEMPLATE_CODE"] or ""),
                    "template_name": str(r["TEMPLATE_NAME"] or ""),
                    "template_version": int(r["TEMPLATE_VERSION"]),
                    "profile_code": str(r["PROFILE_CODE"]),
                    "status": str(r["STATUS"]),
                    "progress_pct": int(r["PROGRESS_PCT"] or 0),
                    "created_by": r["CREATED_BY"],
                    "created_at": r["CREATED_AT"].isoformat() if r["CREATED_AT"] else None,
                    "finished_at": r["FINISHED_AT"].isoformat() if r["FINISHED_AT"] else None,
                    "checked_at": r["CHECKED_AT"].isoformat() if r["CHECKED_AT"] else None,
                    "checked_by": r["CHECKED_BY"],
                    "temp_purged_at": r["TEMP_PURGED_AT"].isoformat() if r["TEMP_PURGED_AT"] else None,
                    "temp_purged_by": r["TEMP_PURGED_BY"],
                    "p_from": r["P_FROM"].isoformat() if r["P_FROM"] else None,
                    "p_to": r["P_TO"].isoformat() if r["P_TO"] else None,
                    "file_id": int(r["FILE_ID"]) if r["FILE_ID"] else None,
                    "filename": str(r["FILENAME"]) if r["FILENAME"] else None,
                    "file_size": int(r["FILE_SIZE"]) if r["FILE_SIZE"] else None,
                    "cnt_matched": cnt_matched,
                    "cnt_mismatch": cnt_mismatch,
                    "cnt_missing_in_db": cnt_missing_db,
                    "cnt_missing_in_excel": cnt_missing_excel,
                    "cnt_invalid": r["CNT_INVALID"] or 0,
                    "match_pct": match_pct,
                }
            )

        total_pages = (total + filter.page_size - 1) // filter.page_size if filter.page_size > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": filter.page,
        "page_size": filter.page_size,
        "total_pages": total_pages,
    }


@service
def get_run_columns(ctx: Ctx, run_id: int) -> list[dict[str, Any]]:
    """Lấy metadata danh sách cột cho màn hình hiển thị AG Grid và xuất Excel."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        summ = conn.execute(
            select(recon_run_summary.c.COLUMNS_JSON).where(recon_run_summary.c.RUN_ID == run_id)
        ).scalar()
        if summ:
            return summ if isinstance(summ, list) else []

        # Nếu chưa có summary, tính từ TemplateConfig
        run_row = conn.execute(select(recon_run).where(recon_run.c.ID == run_id)).mappings().first()
        if not run_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy run {run_id}.")

        tv = (
            conn.execute(
                select(recon_template_version.c.CONFIG_JSON).where(
                    recon_template_version.c.TEMPLATE_ID == run_row["TEMPLATE_ID"],
                    recon_template_version.c.VERSION == run_row["TEMPLATE_VERSION"],
                )
            )
            .mappings()
            .first()
        )
        if not tv:
            return []

        cfg = TemplateConfig.model_validate(tv["CONFIG_JSON"])
        profile = next((p for p in cfg.profiles if p.code == run_row["PROFILE_CODE"]), cfg.profiles[0])
        return build_columns_metadata(profile, cfg)


@service
def get_run_rows(ctx: Ctx, run_id: int, filter: RunRowsFilter) -> dict[str, Any]:
    """Lấy danh sách các dòng kết quả phân trang theo trạng thái, tìm kiếm và sắp xếp, kèm thông tin issue."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        run_row = conn.execute(
            select(recon_run.c.TEMPLATE_ID, recon_run.c.PROFILE_CODE).where(recon_run.c.ID == run_id)
        ).mappings().first()

        tmpl_id = int(run_row["TEMPLATE_ID"]) if run_row else None
        prof_code = str(run_row["PROFILE_CODE"]) if run_row else None

        base_query = (
            select(
                recon_result_row,
                recon_issue.c.ID.label("ISSUE_ID"),
                recon_issue.c.STATUS.label("ISSUE_STATUS"),
                recon_issue.c.REASON_CODE.label("ISSUE_REASON_CODE"),
                recon_issue_reason.c.LABEL.label("ISSUE_REASON_LABEL"),
                recon_user.c.FULL_NAME.label("ISSUE_ASSIGNEE_NAME"),
                recon_user.c.USERNAME.label("ISSUE_ASSIGNEE_USERNAME"),
            )
            .outerjoin(
                recon_issue,
                (recon_issue.c.TEMPLATE_ID == tmpl_id)
                & (recon_issue.c.PROFILE_CODE == prof_code)
                & (recon_issue.c.KEY_HASH == recon_result_row.c.KEY_HASH),
            )
            .outerjoin(recon_issue_reason, recon_issue.c.REASON_CODE == recon_issue_reason.c.CODE)
            .outerjoin(recon_user, recon_issue.c.ASSIGNEE_ID == recon_user.c.ID)
            .where(recon_result_row.c.RUN_ID == run_id)
        )

        if filter.status:
            base_query = base_query.where(recon_result_row.c.STATUS == filter.status)
        if filter.issue_status:
            base_query = base_query.where(recon_issue.c.STATUS == filter.issue_status)
        if filter.search:
            base_query = base_query.where(recon_result_row.c.KEY_TEXT.like(f"%{filter.search}%"))

        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = conn.execute(count_stmt).scalar() or 0

        # Sắp xếp
        if filter.sort_by == "abs_diff_sort":
            order_col = (
                desc(recon_result_row.c.ABS_DIFF_SORT)
                if filter.sort_dir == "desc"
                else recon_result_row.c.ABS_DIFF_SORT
            )
        else:
            order_col = desc(recon_result_row.c.ROW_NO) if filter.sort_dir == "desc" else recon_result_row.c.ROW_NO

        offset = (filter.page - 1) * filter.page_size
        query = base_query.order_by(order_col).limit(filter.page_size).offset(offset)
        rows = conn.execute(query).mappings().fetchall()

        items = []
        for r in rows:
            iss_st = str(r["ISSUE_STATUS"]) if r["ISSUE_STATUS"] else None
            items.append(
                {
                    "row_no": int(r["ROW_NO"]),
                    "key_text": str(r["KEY_TEXT"]),
                    "status": str(r["STATUS"]),
                    "key": r["KEY_JSON"],
                    "excel": r["EXCEL_JSON"],
                    "db": r["DB_JSON"],
                    "diff": r["DIFF_JSON"],
                    "row_nos": r["EXCEL_ROW_NOS"],
                    "abs_diff_main": str(r["ABS_DIFF_MAIN"]) if r["ABS_DIFF_MAIN"] is not None else None,
                    "abs_diff_sort": r["ABS_DIFF_SORT"],
                    "issue_id": r["ISSUE_ID"],
                    "issue_status": iss_st,
                    "is_accepted": iss_st == "ACCEPTED",
                    "reason_code": r["ISSUE_REASON_CODE"],
                    "reason_label": r["ISSUE_REASON_LABEL"],
                    "assignee_name": r["ISSUE_ASSIGNEE_NAME"] or r["ISSUE_ASSIGNEE_USERNAME"],
                }
            )

        total_pages = (total + filter.page_size - 1) // filter.page_size if filter.page_size > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": filter.page,
        "page_size": filter.page_size,
        "total_pages": total_pages,
    }


@service
def get_row_detail(ctx: Ctx, run_id: int, row_no: int) -> dict[str, Any]:
    """Lấy chi tiết dòng đối soát, các measures lệch và các dòng Excel gốc tương ứng."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        r_stmt = select(recon_result_row).where(
            recon_result_row.c.RUN_ID == run_id,
            recon_result_row.c.ROW_NO == row_no,
        )
        row = conn.execute(r_stmt).mappings().first()
        if not row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy dòng {row_no} của run {run_id}.")

        # Đọc thông tin run để xem dữ liệu tạm đã xóa chưa và thông tin template/profile
        run_row = (
            conn.execute(
                select(
                    recon_run.c.TEMPLATE_ID,
                    recon_run.c.PROFILE_CODE,
                    recon_run.c.TEMP_PURGED_AT,
                    recon_run.c.EXCEL_LOAD_ID,
                ).where(recon_run.c.ID == run_id)
            )
            .mappings()
            .first()
        )

        # Đọc diffs
        diffs = (
            conn.execute(
                select(recon_result_diff).where(
                    recon_result_diff.c.RUN_ID == run_id,
                    recon_result_diff.c.ROW_NO == row_no,
                )
            )
            .mappings()
            .fetchall()
        )

        # Đọc thông tin issue (nếu có)
        issue_info = None
        if run_row and row:
            iss_stmt = (
                select(
                    recon_issue,
                    recon_issue_reason.c.LABEL.label("REASON_LABEL"),
                    recon_user.c.FULL_NAME.label("ASSIGNEE_NAME"),
                    recon_user.c.USERNAME.label("ASSIGNEE_USERNAME"),
                )
                .outerjoin(recon_issue_reason, recon_issue.c.REASON_CODE == recon_issue_reason.c.CODE)
                .outerjoin(recon_user, recon_issue.c.ASSIGNEE_ID == recon_user.c.ID)
                .where(
                    recon_issue.c.TEMPLATE_ID == run_row["TEMPLATE_ID"],
                    recon_issue.c.PROFILE_CODE == run_row["PROFILE_CODE"],
                    recon_issue.c.KEY_HASH == row["KEY_HASH"],
                )
            )
            iss_row = conn.execute(iss_stmt).mappings().first()
            if iss_row:
                issue_info = dict(iss_row)

        # Đọc dòng thô từ Excel nếu chưa bị xóa
        raw_rows = None
        is_purged = run_row and run_row["TEMP_PURGED_AT"] is not None
        if not is_purged and run_row and run_row["EXCEL_LOAD_ID"]:
            row_nos_str = row["EXCEL_ROW_NOS"] or ""
            row_nos = [int(n.strip()) for n in row_nos_str.split(",") if n.strip().isdigit()]
            if row_nos:
                excel_rows_stmt = (
                    select(recon_excel_row)
                    .where(
                        recon_excel_row.c.LOAD_ID == run_row["EXCEL_LOAD_ID"],
                        recon_excel_row.c.EXCEL_ROW_NO.in_(row_nos),
                    )
                    .order_by(recon_excel_row.c.EXCEL_ROW_NO)
                )
                raw_rows = [
                    {"excel_row_no": int(er["EXCEL_ROW_NO"]), "data": er["DATA_JSON"]}
                    for er in conn.execute(excel_rows_stmt).mappings().fetchall()
                ]

    return {
        "run_id": run_id,
        "row_no": row_no,
        "key_text": str(row["KEY_TEXT"]),
        "status": str(row["STATUS"]),
        "key": row["KEY_JSON"],
        "excel": row["EXCEL_JSON"],
        "db": row["DB_JSON"],
        "diff": row["DIFF_JSON"],
        "diff_items": [dict(d) for d in diffs],
        "excel_raw_rows": raw_rows,
        "issue": issue_info,
        "purged_at": run_row["TEMP_PURGED_AT"].isoformat() if (run_row and run_row["TEMP_PURGED_AT"]) else None,
    }


@service
def get_invalid_rows(ctx: Ctx, run_id: int, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    """Lấy danh sách các dòng Excel không hợp lệ (INVALID) khi nạp file."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        base_query = select(recon_invalid_row).where(recon_invalid_row.c.RUN_ID == run_id)
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = conn.execute(count_stmt).scalar() or 0

        offset = (page - 1) * page_size
        query = base_query.order_by(recon_invalid_row.c.EXCEL_ROW_NO).limit(page_size).offset(offset)
        rows = conn.execute(query).mappings().fetchall()

        items = [dict(r) for r in rows]
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@service
def export_run(
    ctx: Ctx,
    run_id: int,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Xuất file Excel báo cáo đối soát từ các bảng kết quả lưu trong RECON_APP."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        run_row = conn.execute(select(recon_run).where(recon_run.c.ID == run_id)).mappings().first()
        if not run_row:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy run {run_id}.")

        tv = (
            conn.execute(
                select(recon_template_version.c.CONFIG_JSON).where(
                    recon_template_version.c.TEMPLATE_ID == run_row["TEMPLATE_ID"],
                    recon_template_version.c.VERSION == run_row["TEMPLATE_VERSION"],
                )
            )
            .mappings()
            .first()
        )
        if not tv:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy cấu hình template.")

        cfg = TemplateConfig.model_validate(tv["CONFIG_JSON"])
        profile = next((p for p in cfg.profiles if p.code == run_row["PROFILE_CODE"]), cfg.profiles[0])

        summ_row = (
            conn.execute(select(recon_run_summary).where(recon_run_summary.c.RUN_ID == run_id)).mappings().first()
        )
        summary_dict = dict(summ_row) if summ_row else {}

        # Lấy tất cả dòng kết quả
        rows = (
            conn.execute(
                select(recon_result_row).where(recon_result_row.c.RUN_ID == run_id).order_by(recon_result_row.c.ROW_NO)
            )
            .mappings()
            .fetchall()
        )

        # Lấy dòng invalid
        inv_rows = (
            conn.execute(select(recon_invalid_row).where(recon_invalid_row.c.RUN_ID == run_id)).mappings().fetchall()
        )

    # Dựng result_df cho hàm write_export
    dict_list: list[dict[str, Any]] = []
    for r in rows:
        row_dict: dict[str, Any] = {
            "KEY_TEXT": r["KEY_TEXT"],
            "STATUS": r["STATUS"],
            "ABS_DIFF_MAIN": r["ABS_DIFF_MAIN"],
            "ABS_DIFF_SORT": r["ABS_DIFF_SORT"],
            "__row_nos": [int(n) for n in str(r["EXCEL_ROW_NOS"]).split(",") if n.strip().isdigit()],
        }
        if r["KEY_JSON"]:
            row_dict.update(r["KEY_JSON"])
        if r["EXCEL_JSON"]:
            row_dict.update(r["EXCEL_JSON"])
        if r["DB_JSON"]:
            row_dict.update(r["DB_JSON"])
        if r["DIFF_JSON"]:
            row_dict.update(r["DIFF_JSON"])
        dict_list.append(row_dict)

    result_df = pl.DataFrame(dict_list) if dict_list else pl.DataFrame()
    invalid_df = pl.DataFrame([dict(ir) for ir in inv_rows]) if inv_rows else pl.DataFrame()

    from app.core.config import get_settings

    settings = get_settings()

    if output_path is None:
        target_dir = Path(settings.RECON_STORAGE_DIR) / "runs" / str(run_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_dest = target_dir / "export.xlsx"
    else:
        file_dest = Path(output_path)
        file_dest.parent.mkdir(parents=True, exist_ok=True)

    from app.engine.export import write_export

    write_export(
        output_path=file_dest,
        result_df=result_df,
        invalid_df=invalid_df,
        summary=summary_dict,
        profile=profile,
        config=cfg,
        run_params=dict(run_row["PARAMS_JSON"] or {}),
    )

    return {
        "run_id": run_id,
        "export_path": str(file_dest),
        "file_name": file_dest.name,
    }


@service
def dry_run(
    ctx: Ctx,
    template_id: int,
    version: int,
    file_id: int,
    p_from: datetime,
    p_to: datetime,
    profile_code: str | None = None,
    mock_fetcher: Any = None,
) -> dict[str, Any]:
    """Chạy thử nghiệm (Dry-run) một phiên bản template trên file mẫu không lưu kết quả vào DB."""
    require_role(ctx, Role.OPERATOR, Role.TEMPLATE_OWNER, Role.ADMIN)

    # 1. Tạo run với tham số đã chỉ định
    create_res = create_run(
        ctx,
        CreateRunParams(
            template_id=template_id,
            template_version=version,
            file_id=file_id,
            profile_code=profile_code,
            p_from=p_from,
            p_to=p_to,
        ),
    )
    if not create_res.ok:
        err_msg = create_res.message or "Lỗi khi tạo run thử nghiệm."
        raise ServiceError(create_res.code or ErrorCode.VALIDATION_ERROR, err_msg, create_res.details)

    if not create_res.data:
        raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không thể lấy thông tin run đã tạo.")
    run_id = int(create_res.data["run_id"])

    # 2. Thực thi run với cờ persist=False
    from app.services.run_executor import execute_run

    exec_res = execute_run(run_id=run_id, mock_fetcher=mock_fetcher, persist=False)
    if exec_res.get("status") != "DONE":
        raise ServiceError(
            exec_res.get("error_code") or ErrorCode.INTERNAL_ERROR,
            exec_res.get("error_msg") or "Lỗi xảy ra trong quá trình Dry-run.",
        )

    summary_dict = exec_res.get("summary") or {}

    engine = get_recon_engine()
    # 3. Cập nhật SAMPLE_FILE_ID vào template version và dọn dẹp run tạm
    with engine.begin() as conn:
        conn.execute(
            recon_template_version.update()
            .where(
                recon_template_version.c.TEMPLATE_ID == template_id,
                recon_template_version.c.VERSION == version,
            )
            .values(SAMPLE_FILE_ID=file_id)
        )
        # Dọn dẹp run tạm khỏi hàng đợi và bảng run vì dry-run không lưu kết quả
        conn.execute(recon_run_queue.delete().where(recon_run_queue.c.RUN_ID == run_id))
        conn.execute(recon_run.delete().where(recon_run.c.ID == run_id))

    # 4. Kiểm tra và phân tích Grain cảnh báo
    grain_warnings: list[str] = []
    cnt_dup = summary_dict.get("CNT_DUPLICATE", 0)
    if cnt_dup > 0:
        grain_warnings.append(
            f"Phát hiện {cnt_dup} nhóm bị trùng khóa (DUPLICATE). Cần rà soát lại các trường Group by của Profile."
        )

    excel_groups = summary_dict.get("EXCEL_GROUPS", 0)
    excel_rows = summary_dict.get("EXCEL_ROWS_READ", 0)
    if excel_groups == 1 and excel_rows > 10:
        grain_warnings.append(
            f"Độ chi tiết (Grain) quá thô: Toàn bộ {excel_rows} dòng dữ liệu gộp thành đúng 1 nhóm duy nhất."
        )

    return {
        "run_id": run_id,
        "dry_run_ok": True,
        "summary": summary_dict,
        "grain_warnings": grain_warnings,
    }
