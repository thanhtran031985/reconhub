from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, update

from app.core.audit import write_audit_log
from app.core.context import Ctx, Role, require_role
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_excel_load,
    recon_excel_row,
    recon_file,
    recon_invalid_row,
    recon_issue,
    recon_result_diff,
    recon_result_row,
    recon_run,
    recon_run_queue,
    recon_run_summary,
    recon_template,
    recon_template_version,
)
from app.engine.catalog import describe_sql, list_columns
from app.engine.sql_builder import build_source_sql
from app.engine.sql_guard import check_sql
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import ProfileSpec, TemplateConfig
from app.services import service
from app.services.perm import require_admin, requires_menu
from app.services.source_conn import open_source_connection


@service
@requires_menu("template", "issue", any_of=True)
def list_templates(
    ctx: Ctx,
    q: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Liệt kê danh sách template kèm cấu hình và phiên bản hiện hành."""

    engine = get_recon_engine()

    with engine.connect() as conn:
        stmt = select(recon_template).order_by(recon_template.c.UPDATED_AT.desc())
        if status:
            stmt = stmt.where(recon_template.c.STATUS == status.upper())

        rows = conn.execute(stmt).mappings().all()

        if q and q.strip():
            term = q.strip().upper()
            rows = [r for r in rows if term in str(r["CODE"]).upper() or term in str(r["NAME"]).upper()]

        result: list[dict[str, Any]] = []
        for r in rows:
            t_id = int(r["ID"])
            c_ver = r["CURRENT_VERSION"]

            # Lấy phiên bản hiện hành (hoặc phiên bản mới nhất nếu current_version chưa set)
            ver_stmt = select(recon_template_version).where(recon_template_version.c.TEMPLATE_ID == t_id)
            if c_ver is not None:
                ver_stmt = ver_stmt.where(recon_template_version.c.VERSION == c_ver)
            else:
                ver_stmt = ver_stmt.order_by(recon_template_version.c.VERSION.desc())

            ver_row = conn.execute(ver_stmt.limit(1)).mappings().first()

            field_count = 0
            profiles_list: list[dict[str, Any]] = []
            sheet_name: str | None = None
            sheet_pattern: str | None = None
            detect_headers: list[str] = []
            sample_file_id = ver_row["SAMPLE_FILE_ID"] if ver_row else None
            data_source_id = ver_row["DATA_SOURCE_ID"] if ver_row else None
            version_val = ver_row["VERSION"] if ver_row else (c_ver or 1)

            if ver_row and ver_row["CONFIG_JSON"]:
                cfg = ver_row["CONFIG_JSON"]
                if isinstance(cfg, str):
                    try:
                        cfg = json.loads(cfg)
                    except Exception:
                        cfg = {}
                if isinstance(cfg, dict):
                    field_count = len(cfg.get("fields", []))
                    profiles_list = [
                        {
                            "code": p.get("code") or p.get("profile_id", ""),
                            "name": p.get("name") or p.get("code", ""),
                            "is_default": bool(p.get("is_default", False)),
                        }
                        for p in cfg.get("profiles", [])
                    ]
                    file_spec = cfg.get("file", {})
                    sheet_name = file_spec.get("sheet")
                    sheet_pattern = file_spec.get("sheet_pattern")
                    detect_headers = file_spec.get("detect_by_headers", [])

            # Lấy tên file mẫu upload nếu có
            sample_file_name: str | None = None
            if sample_file_id:
                sample_file_name = conn.execute(
                    select(recon_file.c.ORIGINAL_NAME).where(recon_file.c.ID == sample_file_id)
                ).scalar()

            # Nhận diện file: Ưu tiên tên file mẫu, hoặc sheet_pattern, hoặc f"Sheet: {sheet}"
            if sample_file_name:
                file_pattern_val = sample_file_name
            elif sheet_pattern:
                file_pattern_val = sheet_pattern
            elif sheet_name:
                file_pattern_val = f"Sheet: {sheet_name}"
            else:
                file_pattern_val = "—"

            # Lấy run gần nhất
            last_run = (
                conn.execute(
                    select(
                        recon_run.c.ID,
                        recon_run.c.STATUS,
                        recon_run.c.FINISHED_AT,
                        recon_run.c.CREATED_AT,
                    )
                    .where(recon_run.c.TEMPLATE_ID == t_id)
                    .order_by(recon_run.c.ID.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )

            last_run_dict: dict[str, Any] | None = None
            if last_run:
                run_dt = last_run["FINISHED_AT"] or last_run["CREATED_AT"]
                last_run_dict = {
                    "id": int(last_run["ID"]),
                    "status": str(last_run["STATUS"]),
                    "finished_at": run_dt.strftime("%d/%m/%Y %H:%M") if run_dt else "",
                }

            result.append(
                {
                    "id": t_id,
                    "code": str(r["CODE"]),
                    "name": str(r["NAME"]),
                    "description": r["DESCRIPTION"],
                    "owner": str(r["OWNER"]),
                    "status": str(r["STATUS"]),
                    "current_version": version_val,
                    "version": version_val,
                    "created_at": r["CREATED_AT"],
                    "updated_at": r["UPDATED_AT"],
                    "row_version": int(r["ROW_VERSION"]),
                    "field_count": field_count,
                    "profiles": profiles_list,
                    "sheet": sheet_name,
                    "detect_headers": detect_headers,
                    "sample_file_id": sample_file_id,
                    "sample_file_name": sample_file_name,
                    "file_pattern": file_pattern_val,
                    "data_source_id": data_source_id,
                    "last_run": last_run_dict,
                }
            )
        return result


@service
@requires_menu("template", "result", any_of=True)
def get_template(
    ctx: Ctx,
    template_id: int | str,
    version: int | None = None,
) -> dict[str, Any]:
    """Lấy thông tin chi tiết template và cấu hình CONFIG_JSON của phiên bản tương ứng."""

    engine = get_recon_engine()

    with engine.connect() as conn:
        if isinstance(template_id, int) or (isinstance(template_id, str) and str(template_id).isdigit()):
            tmpl_stmt = select(recon_template).where(recon_template.c.ID == int(template_id))
        else:
            tmpl_stmt = select(recon_template).where(recon_template.c.CODE == str(template_id).strip().upper())

        tmpl = conn.execute(tmpl_stmt).mappings().first()

        if tmpl is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template có ID hoặc mã '{template_id}'")

        t_id = int(tmpl["ID"])
        # Lấy danh sách tất cả các phiên bản
        vers_rows = (
            conn.execute(
                select(recon_template_version)
                .where(recon_template_version.c.TEMPLATE_ID == t_id)
                .order_by(recon_template_version.c.VERSION.desc())
            )
            .mappings()
            .all()
        )

        if not vers_rows:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Template {template_id} chưa có phiên bản nào")

        target_version = version if version is not None else (tmpl["CURRENT_VERSION"] or vers_rows[0]["VERSION"])
        target_ver_row = next((v for v in vers_rows if v["VERSION"] == target_version), vers_rows[0])

        config_data = target_ver_row["CONFIG_JSON"]
        if isinstance(config_data, str):
            import json

            config_data = json.loads(config_data)

        ds_id = target_ver_row["DATA_SOURCE_ID"]
        if ds_id and isinstance(config_data, dict):
            from app.db.metadata import recon_data_source

            ds_row = conn.execute(select(recon_data_source.c.NAME).where(recon_data_source.c.ID == ds_id)).scalar()
            if ds_row:
                config_data.setdefault("db_source", {})["source_id"] = str(ds_row)

        versions_list = [
            {
                "version": int(v["VERSION"]),
                "status": str(v["STATUS"]),
                "data_source_id": v["DATA_SOURCE_ID"],
                "dry_run_ok": v["DRY_RUN_OK"],
                "created_by": str(v["CREATED_BY"]),
                "created_at": v["CREATED_AT"],
                "activated_at": v["ACTIVATED_AT"],
            }
            for v in vers_rows
        ]

        return {
            "id": int(tmpl["ID"]),
            "code": str(tmpl["CODE"]),
            "name": str(tmpl["NAME"]),
            "description": tmpl["DESCRIPTION"],
            "owner": str(tmpl["OWNER"]),
            "status": str(tmpl["STATUS"]),
            "current_version": int(target_ver_row["VERSION"]),
            "row_version": int(tmpl["ROW_VERSION"]),
            "created_at": tmpl["CREATED_AT"],
            "updated_at": tmpl["UPDATED_AT"],
            "config": config_data,
            "data_source_id": target_ver_row["DATA_SOURCE_ID"],
            "sample_file_id": target_ver_row["SAMPLE_FILE_ID"],
            "version_status": str(target_ver_row["STATUS"]),
            "dry_run_ok": target_ver_row["DRY_RUN_OK"],
            "versions": versions_list,
        }


@service
@requires_menu("template")
def save_draft_template(
    ctx: Ctx,
    code: str,
    name: str,
    config: TemplateConfig,
    description: str | None = None,
    data_source_id: int | None = None,
    row_version: int | None = None,
    sample_file_id: int | None = None,
) -> dict[str, Any]:
    """Lưu bản nháp template.

    Nếu là template mới: tạo RECON_TEMPLATE + RECON_TEMPLATE_VERSION (v=1, DRAFT).
    Nếu đã có: kiểm tra row_version (STALE_DATA). Nếu phiên bản mới nhất là DRAFT và chưa có run thì ghi đè;
    nếu đã có run hoặc đã kích hoạt thì tạo phiên bản mới (v = max + 1).
    """
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    norm_code = code.strip().upper()
    config_dict = config.model_dump()

    with engine.begin() as conn:
        existing_tmpl = (
            conn.execute(select(recon_template).where(recon_template.c.CODE == norm_code)).mappings().first()
        )

        if existing_tmpl is None:
            # 1. Tạo mới template và version 1
            ins_res = conn.execute(
                recon_template.insert().values(
                    CODE=norm_code,
                    NAME=name,
                    DESCRIPTION=description,
                    OWNER=ctx.username,
                    STATUS="DRAFT",
                    CURRENT_VERSION=1,
                    CREATED_AT=now,
                    UPDATED_AT=now,
                    ROW_VERSION=1,
                )
            )
            template_id = int(ins_res.inserted_primary_key[0])  # type: ignore[index]

            conn.execute(
                recon_template_version.insert().values(
                    TEMPLATE_ID=template_id,
                    VERSION=1,
                    STATUS="DRAFT",
                    CONFIG_JSON=config_dict,
                    DATA_SOURCE_ID=data_source_id,
                    SAMPLE_FILE_ID=sample_file_id,
                    DRY_RUN_OK="N",
                    CREATED_BY=ctx.username,
                    CREATED_AT=now,
                )
            )

            write_audit_log(
                conn=conn,
                entity="TEMPLATE",
                entity_id=template_id,
                action="CREATE_TEMPLATE",
                actor=ctx.username,
                new_data={"code": norm_code, "name": name, "version": 1},
                now=now,
            )

            return {
                "id": template_id,
                "code": norm_code,
                "name": name,
                "status": "DRAFT",
                "current_version": 1,
                "row_version": 1,
            }

        # 2. Đã tồn tại: kiểm tra STALE_DATA
        template_id = int(existing_tmpl["ID"])
        current_row_ver = int(existing_tmpl["ROW_VERSION"])
        if row_version is not None and row_version != current_row_ver:
            raise ServiceError(
                ErrorCode.STALE_DATA,
                "Dữ liệu template đã bị sửa đổi bởi người dùng khác, vui lòng tải lại trang",
            )

        # Lấy version mới nhất
        latest_ver_row = (
            conn.execute(
                select(recon_template_version)
                .where(recon_template_version.c.TEMPLATE_ID == template_id)
                .order_by(recon_template_version.c.VERSION.desc())
            )
            .mappings()
            .first()
        )

        latest_version = int(latest_ver_row["VERSION"]) if latest_ver_row else 1
        is_latest_draft = latest_ver_row is not None and latest_ver_row["STATUS"] == "DRAFT"

        # Kiểm tra xem version này đã có run nào chưa
        run_count = (
            conn.execute(
                select(func.count(recon_run.c.ID))
                .where(recon_run.c.TEMPLATE_ID == template_id)
                .where(recon_run.c.TEMPLATE_VERSION == latest_version)
            ).scalar()
            or 0
        )

        next_row_version = current_row_ver + 1

        if is_latest_draft and run_count == 0:
            # Ghi đè version nháp hiện tại
            conn.execute(
                update(recon_template_version)
                .where(recon_template_version.c.TEMPLATE_ID == template_id)
                .where(recon_template_version.c.VERSION == latest_version)
                .values(
                    CONFIG_JSON=config_dict,
                    DATA_SOURCE_ID=data_source_id,
                    SAMPLE_FILE_ID=sample_file_id,
                    DRY_RUN_OK="N",
                    DRY_RUN_JSON=None,
                )
            )

            conn.execute(
                update(recon_template)
                .where(recon_template.c.ID == template_id)
                .values(
                    NAME=name,
                    DESCRIPTION=description,
                    UPDATED_AT=now,
                    ROW_VERSION=next_row_version,
                )
            )

            target_version = latest_version
            action = "UPDATE_TEMPLATE_DRAFT"

        else:
            # Tạo version mới = max + 1
            target_version = latest_version + 1
            conn.execute(
                recon_template_version.insert().values(
                    TEMPLATE_ID=template_id,
                    VERSION=target_version,
                    STATUS="DRAFT",
                    CONFIG_JSON=config_dict,
                    DATA_SOURCE_ID=data_source_id,
                    SAMPLE_FILE_ID=sample_file_id,
                    DRY_RUN_OK="N",
                    CREATED_BY=ctx.username,
                    CREATED_AT=now,
                )
            )

            conn.execute(
                update(recon_template)
                .where(recon_template.c.ID == template_id)
                .values(
                    CURRENT_VERSION=target_version,
                    STATUS="DRAFT",
                    NAME=name,
                    DESCRIPTION=description,
                    UPDATED_AT=now,
                    ROW_VERSION=next_row_version,
                )
            )

            action = "CREATE_TEMPLATE_VERSION"

        write_audit_log(
            conn=conn,
            entity="TEMPLATE",
            entity_id=template_id,
            action=action,
            actor=ctx.username,
            new_data={"code": norm_code, "name": name, "version": target_version},
            now=now,
        )

        return {
            "id": template_id,
            "code": norm_code,
            "name": name,
            "status": "DRAFT",
            "current_version": target_version,
            "row_version": next_row_version,
        }


@service
@requires_menu("template")
def activate_version(
    ctx: Ctx,
    template_id: int,
    version: int,
    dry_run_override: bool = False,
) -> dict[str, Any]:
    """Kích hoạt một phiên bản template thành ACTIVE (chuyển các version ACTIVE cũ thành RETIRED)."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        ver_row = (
            conn.execute(
                select(recon_template_version)
                .where(recon_template_version.c.TEMPLATE_ID == template_id)
                .where(recon_template_version.c.VERSION == version)
            )
            .mappings()
            .first()
        )

        if ver_row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy phiên bản {version} của template {template_id}")

        if not dry_run_override and ver_row["DRY_RUN_OK"] != "Y":
            raise ServiceError(
                ErrorCode.DRY_RUN_REQUIRED,
                "Phiên bản cần chạy thử (Dry-run) thành công trước khi kích hoạt",
            )

        # Chuyển các version ACTIVE cũ thành RETIRED
        conn.execute(
            update(recon_template_version)
            .where(recon_template_version.c.TEMPLATE_ID == template_id)
            .where(recon_template_version.c.STATUS == "ACTIVE")
            .values(STATUS="RETIRED")
        )

        # Kích hoạt phiên bản này
        conn.execute(
            update(recon_template_version)
            .where(recon_template_version.c.TEMPLATE_ID == template_id)
            .where(recon_template_version.c.VERSION == version)
            .values(
                STATUS="ACTIVE",
                ACTIVATED_AT=now,
            )
        )

        # Cập nhật template chính
        conn.execute(
            update(recon_template)
            .where(recon_template.c.ID == template_id)
            .values(
                STATUS="ACTIVE",
                CURRENT_VERSION=version,
                UPDATED_AT=now,
                ROW_VERSION=recon_template.c.ROW_VERSION + 1,
            )
        )

        write_audit_log(
            conn=conn,
            entity="TEMPLATE",
            entity_id=template_id,
            action="ACTIVATE_TEMPLATE_VERSION",
            actor=ctx.username,
            new_data={"version": version},
            now=now,
        )

        return {"ok": True, "template_id": template_id, "version": version, "status": "ACTIVE"}


@service
@requires_menu("template")
def clone_template(
    ctx: Ctx,
    template_id: int,
    new_code: str,
    new_name: str,
    version: int | None = None,
) -> dict[str, Any]:
    """Nhân bản template sang mã mới ở trạng thái DRAFT v1."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    norm_new_code = new_code.strip().upper()

    with engine.begin() as conn:
        # Kiểm tra trùng mã
        existing = conn.execute(
            select(recon_template.c.ID).where(recon_template.c.CODE == norm_new_code)
        ).scalar_one_or_none()
        if existing is not None:
            raise ServiceError(
                ErrorCode.TEMPLATE_CODE_EXISTS,
                f"Mã template '{norm_new_code}' đã tồn tại, vui lòng chọn mã khác",
            )

        # Lấy template nguồn
        src_tmpl = conn.execute(select(recon_template).where(recon_template.c.ID == template_id)).mappings().first()
        if src_tmpl is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template nguồn có ID {template_id}")

        src_ver_num = version or src_tmpl["CURRENT_VERSION"]
        src_ver_row = (
            conn.execute(
                select(recon_template_version)
                .where(recon_template_version.c.TEMPLATE_ID == template_id)
                .where(recon_template_version.c.VERSION == src_ver_num)
            )
            .mappings()
            .first()
        )

        if src_ver_row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy phiên bản nguồn {src_ver_num}")

        # Tạo template mới
        ins_res = conn.execute(
            recon_template.insert().values(
                CODE=norm_new_code,
                NAME=new_name,
                DESCRIPTION=f"Nhân bản từ {src_tmpl['CODE']}: {src_tmpl['NAME']}",
                OWNER=ctx.username,
                STATUS="DRAFT",
                CURRENT_VERSION=1,
                CREATED_AT=now,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        new_template_id = int(ins_res.inserted_primary_key[0])  # type: ignore[index]

        conn.execute(
            recon_template_version.insert().values(
                TEMPLATE_ID=new_template_id,
                VERSION=1,
                STATUS="DRAFT",
                CONFIG_JSON=src_ver_row["CONFIG_JSON"],
                DATA_SOURCE_ID=src_ver_row["DATA_SOURCE_ID"],
                DRY_RUN_OK="N",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
            )
        )

        write_audit_log(
            conn=conn,
            entity="TEMPLATE",
            entity_id=new_template_id,
            action="CLONE_TEMPLATE",
            actor=ctx.username,
            new_data={"from_template_id": template_id, "new_code": norm_new_code},
            now=now,
        )

        return {
            "id": new_template_id,
            "code": norm_new_code,
            "name": new_name,
            "status": "DRAFT",
            "current_version": 1,
            "row_version": 1,
        }


@service
@requires_menu("template")
def archive_template(
    ctx: Ctx,
    template_id: int,
) -> dict[str, Any]:
    """Lưu trữ template (chuyển sang trạng thái ARCHIVED, không thể tạo run mới)."""
    require_role(ctx, Role.ADMIN, Role.TEMPLATE_OWNER)
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        tmpl = conn.execute(select(recon_template).where(recon_template.c.ID == template_id)).mappings().first()
        if tmpl is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template có ID {template_id}")

        conn.execute(
            update(recon_template)
            .where(recon_template.c.ID == template_id)
            .values(
                STATUS="ARCHIVED",
                UPDATED_AT=now,
                ROW_VERSION=recon_template.c.ROW_VERSION + 1,
            )
        )

        write_audit_log(
            conn=conn,
            entity="TEMPLATE",
            entity_id=template_id,
            action="ARCHIVE_TEMPLATE",
            actor=ctx.username,
            new_data={"status": "ARCHIVED"},
            now=now,
        )

        return {"ok": True, "template_id": template_id, "status": "ARCHIVED"}


@service
@requires_menu("template")
def delete_template(
    ctx: Ctx,
    template_id: int | str,
) -> dict[str, Any]:
    """Xóa vĩnh viễn template và các cấu hình/dữ liệu liên quan (chỉ dành cho Quản trị viên)."""
    engine = get_recon_engine()
    require_admin(ctx, engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        if isinstance(template_id, int) or str(template_id).isdigit():
            target_int_id = int(template_id)
            tmpl = conn.execute(select(recon_template).where(recon_template.c.ID == target_int_id)).mappings().first()
        else:
            tmpl = (
                conn.execute(select(recon_template).where(recon_template.c.CODE == str(template_id).upper()))
                .mappings()
                .first()
            )

        if tmpl is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template có ID/Code {template_id}")

        resolved_id = int(tmpl["ID"])
        code = str(tmpl["CODE"])
        name = str(tmpl["NAME"])

        # 1. Tìm và xóa các run liên quan nếu có
        run_ids = conn.execute(select(recon_run.c.ID).where(recon_run.c.TEMPLATE_ID == resolved_id)).scalars().all()

        if run_ids:
            conn.execute(delete(recon_result_diff).where(recon_result_diff.c.RUN_ID.in_(run_ids)))
            conn.execute(delete(recon_result_row).where(recon_result_row.c.RUN_ID.in_(run_ids)))
            conn.execute(delete(recon_invalid_row).where(recon_invalid_row.c.RUN_ID.in_(run_ids)))
            conn.execute(delete(recon_run_summary).where(recon_run_summary.c.RUN_ID.in_(run_ids)))
            conn.execute(delete(recon_run_queue).where(recon_run_queue.c.RUN_ID.in_(run_ids)))
            conn.execute(delete(recon_run).where(recon_run.c.ID.in_(run_ids)))

        # 2. Xóa các issue liên quan
        conn.execute(delete(recon_issue).where(recon_issue.c.TEMPLATE_ID == resolved_id))

        # 3. Xóa các excel load liên quan
        load_ids = (
            conn.execute(select(recon_excel_load.c.ID).where(recon_excel_load.c.TEMPLATE_ID == resolved_id))
            .scalars()
            .all()
        )
        if load_ids:
            conn.execute(delete(recon_excel_row).where(recon_excel_row.c.LOAD_ID.in_(load_ids)))
            conn.execute(delete(recon_excel_load).where(recon_excel_load.c.ID.in_(load_ids)))

        # 4. Xóa các phiên bản template
        conn.execute(delete(recon_template_version).where(recon_template_version.c.TEMPLATE_ID == resolved_id))

        # 5. Xóa chính template
        conn.execute(delete(recon_template).where(recon_template.c.ID == resolved_id))

        # 6. Ghi nhật ký audit
        write_audit_log(
            conn=conn,
            entity="TEMPLATE",
            entity_id=resolved_id,
            action="DELETE_TEMPLATE",
            actor=ctx.username,
            old_data={"code": code, "name": name},
            now=now,
        )

        return {"ok": True, "template_id": resolved_id, "code": code, "deleted": True}


@service
@requires_menu("template")
def preview_source_sql(
    ctx: Ctx,
    template_id: int,
    version: int | None = None,
    profile_code: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Xem trước câu lệnh SQL sinh ra cho nguồn DB và danh sách bind parameters."""

    tmpl_res = get_template(ctx, template_id, version=version)
    if not tmpl_res.ok or not isinstance(tmpl_res.data, dict):
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy template có ID {template_id}")

    config = TemplateConfig.model_validate(tmpl_res.data["config"])
    target_profile: ProfileSpec | None = None
    if profile_code:
        for p in config.profiles:
            if p.code == profile_code:
                target_profile = p
                break
    elif config.profiles:
        for p in config.profiles:
            if p.is_default:
                target_profile = p
                break
        if target_profile is None:
            target_profile = config.profiles[0]

    sql, binds = build_source_sql(config, profile=target_profile, params=params)
    return {
        "template_id": template_id,
        "version": tmpl_res.data["current_version"],
        "profile_code": target_profile.code if target_profile else None,
        "sql": sql,
        "binds": binds,
    }


@service
@requires_menu("template")
def describe_source(
    ctx: Ctx,
    data_source_id: int,
    table_name: str | None = None,
    sql: str | None = None,
    schema: str | None = None,
    allowed_params: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Phân tích cấu trúc cột của bảng nguồn hoặc câu lệnh SQL tùy biến."""

    if not table_name and not sql:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Cần cung cấp table_name hoặc sql để phân tích cấu trúc cột.")

    if sql:
        effective_allowed = list(allowed_params) if allowed_params is not None else ["p_from", "p_to", "p_org"]
        for default_p in ["p_from", "p_to", "p_org"]:
            if default_p not in effective_allowed:
                effective_allowed.append(default_p)

        is_safe, err_msg = check_sql(sql, allowed_params=effective_allowed)
        if not is_safe:
            raise ServiceError(ErrorCode.SQL_NOT_ALLOWED, err_msg or "Câu lệnh SQL không an toàn.")
        conn = open_source_connection(data_source_id)
        try:
            return describe_sql(conn, sql)
        finally:
            conn.close()

    assert table_name is not None
    parts = table_name.split(".")
    target_schema = parts[0] if len(parts) > 1 else (schema or "")
    target_table = parts[1] if len(parts) > 1 else parts[0]

    return list_columns(data_source_id, schema=target_schema, table_name=target_table)
