"""Service Report Template và Version — task 21, spec 12/12a.

Template thuộc một Report Master; mỗi template có nhiều version.
Version 1 tạo cùng template ở trạng thái DRAFT. Sửa version ACTIVE
bằng cách clone sang DRAFT mới (T21-03). Kích hoạt: DRAFT → DRY_RUN_OK
→ ACTIVE, chỉ một ACTIVE mỗi template, khóa bằng dòng
REPORT_ACTIVATE_LOCK trong RECON_APP_SETTING (mẫu MENU_SYNC_LOCK),
version cũ ACTIVE → ARCHIVED trong cùng transaction (T21-04).
Run cũ giữ VERSION_ID cũ (T21-05).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_app_setting,
    recon_report_template,
    recon_rpt_column,
    recon_rpt_param,
    recon_rpt_param_lov,
    recon_rpt_tpl_ver,
)
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.report import load_report_row
from app.services.report_param import (
    invalidate_lov_cache_for_version,
    layout_violations,
)

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,59}$")
_LOCK_KEY = "REPORT_ACTIVATE_LOCK"
_LOCK_TTL = timedelta(seconds=60)
_SOURCE_TYPES = ("CUSTOM_SQL", "VIEW", "TABLE")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TemplateCreate(BaseModel):
    """Payload tạo Template kèm version 1 DRAFT (wizard bước 1+2)."""

    code: str = Field(pattern=_CODE_RE)
    name: str = Field(min_length=1, max_length=200)
    display_order: int = Field(default=10, ge=0)
    data_source_id: int | None = None
    source_type: str | None = None
    sql_text: str | None = None
    source_owner: str | None = Field(default=None, max_length=60)
    source_object: str | None = Field(default=None, max_length=128)
    timeout_sec: int = Field(default=300, ge=1, le=600)
    preview_max_rows: int = Field(default=100, ge=1)
    export_max_rows: int = Field(default=1000000, ge=1)


class TemplateUpdate(BaseModel):
    """Payload sửa Template (không đổi CODE, không sửa version)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    display_order: int | None = Field(default=None, ge=0)


def _validate_source(dto: TemplateCreate) -> None:
    """Kiểm tra trường nguồn theo SOURCE_TYPE (spec 12a)."""
    if dto.source_type is None:
        return
    if dto.source_type not in _SOURCE_TYPES:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, f"SOURCE_TYPE phải là một trong: {', '.join(_SOURCE_TYPES)}.")
    if dto.source_type == "CUSTOM_SQL" and not (dto.sql_text or "").strip():
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "CUSTOM_SQL phải có SQL_TEXT.")
    if dto.source_type in ("VIEW", "TABLE") and not (
        (dto.source_owner or "").strip() and (dto.source_object or "").strip()
    ):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"{dto.source_type} phải có SOURCE_OWNER và SOURCE_OBJECT.",
        )


def _template_dict(row: Any, versions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "report_id": int(row["REPORT_ID"]),
        "code": str(row["CODE"]),
        "name": str(row["NAME"]),
        "display_order": int(row["DISPLAY_ORDER"]),
        "active_version_id": (int(row["ACTIVE_VERSION_ID"]) if row["ACTIVE_VERSION_ID"] is not None else None),
        "row_version": int(row["ROW_VERSION"]),
        "versions": versions or [],
    }


def _version_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "template_id": int(row["TEMPLATE_ID"]),
        "version_no": int(row["VERSION_NO"]),
        "status": str(row["STATUS"]),
        "data_source_id": row["DATA_SOURCE_ID"],
        "source_type": row["SOURCE_TYPE"],
        "sql_text": row["SQL_TEXT"],
        "source_owner": row["SOURCE_OWNER"],
        "source_object": row["SOURCE_OBJECT"],
        "timeout_sec": int(row["TIMEOUT_SEC"]),
        "preview_max_rows": int(row["PREVIEW_MAX_ROWS"]),
        "export_max_rows": int(row["EXPORT_MAX_ROWS"]),
        "sql_hash": row["SQL_HASH"],
        "activated_by": row["ACTIVATED_BY"],
        "activated_at": row["ACTIVATED_AT"],
        "row_version": int(row["ROW_VERSION"]),
    }


def _load_template_row(conn: Connection, template_id: int, admin: bool) -> Any:
    """Đọc template; người thường chỉ thấy template của report hiển thị."""
    stmt = select(recon_report_template).where(recon_report_template.c.ID == template_id)
    row = conn.execute(stmt).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy template.")
    if not admin:
        load_report_row(conn, int(row["REPORT_ID"]), admin=False)
    return row


def _load_version_row(conn: Connection, version_id: int, admin: bool) -> Any:
    row = conn.execute(select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)).mappings().first()
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy version.")
    _load_template_row(conn, int(row["TEMPLATE_ID"]), admin)
    return row


def _versions_of(conn: Connection, template_id: int) -> list[dict[str, Any]]:
    rows = (
        conn.execute(
            select(recon_rpt_tpl_ver)
            .where(recon_rpt_tpl_ver.c.TEMPLATE_ID == template_id)
            .order_by(recon_rpt_tpl_ver.c.VERSION_NO)
        )
        .mappings()
        .all()
    )
    return [_version_dict(row) for row in rows]


def _version_detail(conn: Connection, version_row: Any) -> dict[str, Any]:
    """Version kèm params (có LOV) và columns — snapshot đầy đủ."""
    data = _version_dict(version_row)
    params = (
        conn.execute(
            select(recon_rpt_param)
            .where(recon_rpt_param.c.VERSION_ID == version_row["ID"])
            .order_by(recon_rpt_param.c.DISPLAY_ORDER, recon_rpt_param.c.CODE)
        )
        .mappings()
        .all()
    )
    param_list = []
    for param in params:
        lov = (
            conn.execute(select(recon_rpt_param_lov).where(recon_rpt_param_lov.c.PARAM_ID == param["ID"]))
            .mappings()
            .first()
        )
        param_list.append(
            {
                "id": int(param["ID"]),
                "code": str(param["CODE"]),
                "label": str(param["LABEL"]),
                "data_type": str(param["DATA_TYPE"]),
                "control_type": str(param["CONTROL_TYPE"]),
                "required": param["REQUIRED"] == "Y",
                "default_type": param["DEFAULT_TYPE"],
                "default_value": param["DEFAULT_VALUE"],
                "display_row": int(param["DISPLAY_ROW"]),
                "display_order": int(param["DISPLAY_ORDER"]),
                "grid_span": int(param["GRID_SPAN"]),
                "filter_column": param["FILTER_COLUMN"],
                "filter_operator": param["FILTER_OPERATOR"],
                "is_visible": param["IS_VISIBLE"] == "Y",
                "lov": (
                    {
                        "lov_type": str(lov["LOV_TYPE"]),
                        "data_source_id": lov["DATA_SOURCE_ID"],
                        "sql_text": lov["SQL_TEXT"],
                        "lookup_type": lov["LOOKUP_TYPE"],
                        "static_json": lov["STATIC_JSON"],
                        "cache_seconds": int(lov["CACHE_SECONDS"]),
                        "max_rows": int(lov["MAX_ROWS"]),
                    }
                    if lov is not None
                    else None
                ),
            }
        )
    columns = (
        conn.execute(
            select(recon_rpt_column)
            .where(recon_rpt_column.c.VERSION_ID == version_row["ID"])
            .order_by(recon_rpt_column.c.DISPLAY_ORDER, recon_rpt_column.c.FIELD_NAME)
        )
        .mappings()
        .all()
    )
    data["params"] = param_list
    data["columns"] = [
        {
            "id": int(col["ID"]),
            "field_name": str(col["FIELD_NAME"]),
            "label": str(col["LABEL"]),
            "data_type": str(col["DATA_TYPE"]),
            "display_order": int(col["DISPLAY_ORDER"]),
            "web_visible": col["WEB_VISIBLE"] == "Y",
            "excel_visible": col["EXCEL_VISIBLE"] == "Y",
            "format_mask": col["FORMAT_MASK"],
            "alignment": str(col["ALIGNMENT"]),
            "width": col["WIDTH"],
            "is_total": col["IS_TOTAL"] == "Y",
        }
        for col in columns
    ]
    return data


@service
@requires_menu("report_center")
def list_templates(ctx: Ctx, report_id: int) -> list[dict[str, Any]]:
    """Danh sách template của một report (kèm version ACTIVE)."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        load_report_row(conn, report_id, admin)
        rows = (
            conn.execute(
                select(recon_report_template)
                .where(recon_report_template.c.REPORT_ID == report_id)
                .order_by(recon_report_template.c.DISPLAY_ORDER, recon_report_template.c.CODE)
            )
            .mappings()
            .all()
        )
        return [_template_dict(row) for row in rows]


@service
@requires_menu("report_center")
def get_template(ctx: Ctx, template_id: int) -> dict[str, Any]:
    """Chi tiết template kèm mọi version."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        row = _load_template_row(conn, template_id, admin)
        return _template_dict(row, _versions_of(conn, template_id))


@service
@requires_menu("report_admin")
def create_template(ctx: Ctx, report_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Tạo template kèm version 1 DRAFT (chỉ Admin)."""
    dto = TemplateCreate(**payload)
    _validate_source(dto)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        load_report_row(conn, report_id, admin=True)
        exists = conn.execute(
            select(recon_report_template.c.ID).where(
                recon_report_template.c.REPORT_ID == report_id,
                recon_report_template.c.CODE == dto.code,
            )
        ).first()
        if exists is not None:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã template {dto.code} đã tồn tại trong báo cáo.")
        res = conn.execute(
            recon_report_template.insert().values(
                REPORT_ID=report_id,
                CODE=dto.code,
                NAME=dto.name,
                DISPLAY_ORDER=dto.display_order,
                ACTIVE_VERSION_ID=None,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        tpl_pk = res.inserted_primary_key
        if tpl_pk is None:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không tạo được template.")
        template_id = int(tpl_pk[0])
        write_audit_log(
            conn=conn,
            entity="RECON_REPORT_TEMPLATE",
            entity_id=template_id,
            action="CREATE_TEMPLATE",
            actor=ctx.username,
            new_data={"report_id": report_id, "code": dto.code, "name": dto.name},
            now=now,
        )
        conn.execute(
            recon_rpt_tpl_ver.insert().values(
                TEMPLATE_ID=template_id,
                VERSION_NO=1,
                STATUS="DRAFT",
                DATA_SOURCE_ID=dto.data_source_id,
                SOURCE_TYPE=dto.source_type,
                SQL_TEXT=dto.sql_text,
                SOURCE_OWNER=dto.source_owner,
                SOURCE_OBJECT=dto.source_object,
                TIMEOUT_SEC=dto.timeout_sec,
                PREVIEW_MAX_ROWS=dto.preview_max_rows,
                EXPORT_MAX_ROWS=dto.export_max_rows,
                SQL_HASH=None,
                ACTIVATED_BY=None,
                ACTIVATED_AT=None,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        row = (
            conn.execute(select(recon_report_template).where(recon_report_template.c.ID == template_id))
            .mappings()
            .first()
        )
        assert row is not None
        return _template_dict(row, _versions_of(conn, template_id))


@service
@requires_menu("report_admin")
def update_template(
    ctx: Ctx, template_id: int, payload: dict[str, Any], row_version: int | None = None
) -> dict[str, Any]:
    """Sửa tên/thứ tự template; khóa lạc quan ROW_VERSION (chỉ kiểm khi truyền)."""
    dto = TemplateUpdate(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = _load_template_row(conn, template_id, admin=True)
        if row_version is not None and int(row["ROW_VERSION"]) != row_version:
            raise ServiceError(ErrorCode.STALE_DATA, "Template đã bị thay đổi, tải lại rồi sửa tiếp.")
        values: dict[str, Any] = {
            "UPDATED_BY": ctx.username,
            "UPDATED_AT": now,
            "ROW_VERSION": int(row["ROW_VERSION"]) + 1,
        }
        if dto.name is not None:
            values["NAME"] = dto.name
        if dto.display_order is not None:
            values["DISPLAY_ORDER"] = dto.display_order
        conn.execute(recon_report_template.update().where(recon_report_template.c.ID == template_id).values(**values))
        write_audit_log(
            conn=conn,
            entity="RECON_REPORT_TEMPLATE",
            entity_id=template_id,
            action="UPDATE_TEMPLATE",
            actor=ctx.username,
            old_data={"code": str(row["CODE"]), "name": str(row["NAME"])},
            new_data={"code": str(row["CODE"]), "name": dto.name or str(row["NAME"])},
            now=now,
        )
        updated = (
            conn.execute(select(recon_report_template).where(recon_report_template.c.ID == template_id))
            .mappings()
            .first()
        )
        assert updated is not None
        return _template_dict(updated, _versions_of(conn, template_id))


class VersionSourceUpdate(BaseModel):
    """Payload sửa nguồn dữ liệu của version DRAFT (wizard bước 2, task 27)."""

    data_source_id: int | None = None
    source_type: str | None = None
    sql_text: str | None = None
    source_owner: str | None = Field(default=None, max_length=60)
    source_object: str | None = Field(default=None, max_length=128)
    timeout_sec: int | None = Field(default=None, ge=1, le=600)
    preview_max_rows: int | None = Field(default=None, ge=1)
    export_max_rows: int | None = Field(default=None, ge=1)


@service
@requires_menu("report_admin")
def update_version_source(ctx: Ctx, version_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Sửa nguồn dữ liệu của version DRAFT (wizard bước 2, task 27).

    Task 21/22 không có service này: create_template chỉ nhận nguồn lúc
    tạo, update_template chỉ sửa tên/thứ tự. Đổi nguồn reset SQL_HASH.
    Chỉ DRAFT được sửa; kiểm tra cấu trúc (CUSTOM_SQL cần sql_text,
    VIEW/TABLE cần owner + object). Kiểm tra SQL sâu (guard + describe)
    do wizard gọi validate_version_sql trước.
    """
    dto = VersionSourceUpdate(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = _load_version_row(conn, version_id, admin=True)
        if str(row["STATUS"]) != "DRAFT":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ sửa được nguồn dữ liệu của version DRAFT.",
            )
        source_type = dto.source_type or str(row["SOURCE_TYPE"] or "")
        sql_text = dto.sql_text if dto.sql_text is not None else row["SQL_TEXT"]
        owner = dto.source_owner if dto.source_owner is not None else row["SOURCE_OWNER"]
        obj = dto.source_object if dto.source_object is not None else row["SOURCE_OBJECT"]
        if source_type and source_type not in _SOURCE_TYPES:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Loại nguồn không hỗ trợ: {source_type}.")
        if source_type == "CUSTOM_SQL" and not (sql_text or "").strip():
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "CUSTOM_SQL cần câu lệnh SQL.")
        if source_type in ("VIEW", "TABLE"):
            if not (owner or "").strip():
                from app.engine.catalog import _resolve_schema
                ds_val = dto.data_source_id or row["DATA_SOURCE_ID"]
                if ds_val:
                    owner = _resolve_schema(int(ds_val), None) or "main"
                else:
                    owner = "main"
            if not ((owner or "").strip() and (obj or "").strip()):
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    "VIEW/TABLE cần chọn schema và đối tượng.",
                )
        values: dict[str, Any] = {
            "UPDATED_BY": ctx.username,
            "UPDATED_AT": now,
            "ROW_VERSION": int(row["ROW_VERSION"]) + 1,
            "SQL_HASH": None,
        }
        if dto.data_source_id is not None:
            values["DATA_SOURCE_ID"] = dto.data_source_id
        if dto.source_type is not None:
            values["SOURCE_TYPE"] = dto.source_type
        if dto.sql_text is not None:
            values["SQL_TEXT"] = dto.sql_text
        if dto.source_owner is not None:
            values["SOURCE_OWNER"] = dto.source_owner
        if dto.source_object is not None:
            values["SOURCE_OBJECT"] = dto.source_object
        if dto.timeout_sec is not None:
            values["TIMEOUT_SEC"] = dto.timeout_sec
        if dto.preview_max_rows is not None:
            values["PREVIEW_MAX_ROWS"] = dto.preview_max_rows
        if dto.export_max_rows is not None:
            values["EXPORT_MAX_ROWS"] = dto.export_max_rows
        conn.execute(recon_rpt_tpl_ver.update().where(recon_rpt_tpl_ver.c.ID == version_id).values(**values))
        write_audit_log(
            conn=conn,
            entity="RECON_RPT_TPL_VER",
            entity_id=version_id,
            action="UPDATE_VERSION_SOURCE",
            actor=ctx.username,
            old_data={"source_type": str(row["SOURCE_TYPE"] or "")},
            new_data={"source_type": source_type},
            now=now,
        )
        updated = conn.execute(select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)).mappings().first()
        assert updated is not None
        return _version_dict(updated)


@service
@requires_menu("report_admin")
def archive_template(ctx: Ctx, template_id: int) -> dict[str, Any]:
    """Lưu trữ template: mọi version → ARCHIVED, bỏ ACTIVE_VERSION_ID."""
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = _load_template_row(conn, template_id, admin=True)
        conn.execute(
            recon_rpt_tpl_ver.update()
            .where(
                recon_rpt_tpl_ver.c.TEMPLATE_ID == template_id,
                recon_rpt_tpl_ver.c.STATUS != "ARCHIVED",
            )
            .values(STATUS="ARCHIVED", UPDATED_BY=ctx.username, UPDATED_AT=now)
        )
        conn.execute(
            recon_report_template.update()
            .where(recon_report_template.c.ID == template_id)
            .values(
                ACTIVE_VERSION_ID=None,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=int(row["ROW_VERSION"]) + 1,
            )
        )
        write_audit_log(
            conn=conn,
            entity="RECON_REPORT_TEMPLATE",
            entity_id=template_id,
            action="ARCHIVE_TEMPLATE",
            actor=ctx.username,
            old_data={"code": str(row["CODE"])},
            new_data={"code": str(row["CODE"]), "active_version_id": None},
            now=now,
        )
        updated = (
            conn.execute(select(recon_report_template).where(recon_report_template.c.ID == template_id))
            .mappings()
            .first()
        )
        assert updated is not None
        return _template_dict(updated, _versions_of(conn, template_id))


@service
@requires_menu("report_center")
def get_version(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Chi tiết version kèm params (có LOV) và columns."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        row = _load_version_row(conn, version_id, admin)
        return _version_detail(conn, row)


@service
@requires_menu("report_admin")
def clone_version(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Clone một version (bất kỳ trạng thái) sang DRAFT mới, VERSION_NO+1.

    Sao chép sâu nguồn + params + LOV + columns (T21-03).
    """
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        src = _load_version_row(conn, version_id, admin=True)
        max_no = conn.execute(
            select(func.max(recon_rpt_tpl_ver.c.VERSION_NO)).where(
                recon_rpt_tpl_ver.c.TEMPLATE_ID == src["TEMPLATE_ID"]
            )
        ).scalar_one()
        new_no = int(max_no or 0) + 1
        res = conn.execute(
            recon_rpt_tpl_ver.insert().values(
                TEMPLATE_ID=src["TEMPLATE_ID"],
                VERSION_NO=new_no,
                STATUS="DRAFT",
                DATA_SOURCE_ID=src["DATA_SOURCE_ID"],
                SOURCE_TYPE=src["SOURCE_TYPE"],
                SQL_TEXT=src["SQL_TEXT"],
                SOURCE_OWNER=src["SOURCE_OWNER"],
                SOURCE_OBJECT=src["SOURCE_OBJECT"],
                TIMEOUT_SEC=src["TIMEOUT_SEC"],
                PREVIEW_MAX_ROWS=src["PREVIEW_MAX_ROWS"],
                EXPORT_MAX_ROWS=src["EXPORT_MAX_ROWS"],
                SQL_HASH=src["SQL_HASH"],
                ACTIVATED_BY=None,
                ACTIVATED_AT=None,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        ver_pk = res.inserted_primary_key
        if ver_pk is None:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không clone được version.")
        new_id = int(ver_pk[0])
        params = (
            conn.execute(select(recon_rpt_param).where(recon_rpt_param.c.VERSION_ID == version_id)).mappings().all()
        )
        for param in params:
            pres = conn.execute(
                recon_rpt_param.insert().values(
                    VERSION_ID=new_id,
                    CODE=param["CODE"],
                    LABEL=param["LABEL"],
                    DATA_TYPE=param["DATA_TYPE"],
                    CONTROL_TYPE=param["CONTROL_TYPE"],
                    REQUIRED=param["REQUIRED"],
                    DEFAULT_TYPE=param["DEFAULT_TYPE"],
                    DEFAULT_VALUE=param["DEFAULT_VALUE"],
                    DISPLAY_ROW=param["DISPLAY_ROW"],
                    DISPLAY_ORDER=param["DISPLAY_ORDER"],
                    GRID_SPAN=param["GRID_SPAN"],
                    FILTER_COLUMN=param["FILTER_COLUMN"],
                    FILTER_OPERATOR=param["FILTER_OPERATOR"],
                    IS_VISIBLE=param["IS_VISIBLE"],
                )
            )
            param_pk = pres.inserted_primary_key
            if param_pk is None:
                raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không clone được tham số.")
            new_param_id = int(param_pk[0])
            lov = (
                conn.execute(select(recon_rpt_param_lov).where(recon_rpt_param_lov.c.PARAM_ID == param["ID"]))
                .mappings()
                .first()
            )
            if lov is not None:
                conn.execute(
                    recon_rpt_param_lov.insert().values(
                        PARAM_ID=new_param_id,
                        LOV_TYPE=lov["LOV_TYPE"],
                        DATA_SOURCE_ID=lov["DATA_SOURCE_ID"],
                        SQL_TEXT=lov["SQL_TEXT"],
                        LOOKUP_TYPE=lov["LOOKUP_TYPE"],
                        STATIC_JSON=lov["STATIC_JSON"],
                        CACHE_SECONDS=lov["CACHE_SECONDS"],
                        MAX_ROWS=lov["MAX_ROWS"],
                    )
                )
        columns = (
            conn.execute(select(recon_rpt_column).where(recon_rpt_column.c.VERSION_ID == version_id)).mappings().all()
        )
        for col in columns:
            conn.execute(
                recon_rpt_column.insert().values(
                    VERSION_ID=new_id,
                    FIELD_NAME=col["FIELD_NAME"],
                    LABEL=col["LABEL"],
                    DATA_TYPE=col["DATA_TYPE"],
                    DISPLAY_ORDER=col["DISPLAY_ORDER"],
                    WEB_VISIBLE=col["WEB_VISIBLE"],
                    EXCEL_VISIBLE=col["EXCEL_VISIBLE"],
                    FORMAT_MASK=col["FORMAT_MASK"],
                    ALIGNMENT=col["ALIGNMENT"],
                    WIDTH=col["WIDTH"],
                    IS_TOTAL=col["IS_TOTAL"],
                )
            )
        new_row = conn.execute(select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == new_id)).mappings().first()
        assert new_row is not None
        write_audit_log(
            conn=conn,
            entity="RECON_RPT_TPL_VER",
            entity_id=new_id,
            action="CLONE_VERSION",
            actor=ctx.username,
            new_data={
                "template_id": int(src["TEMPLATE_ID"]),
                "from_version_id": version_id,
                "version_no": new_no,
            },
            now=now,
        )
        return _version_dict(new_row)


def _parse_lock(value: str | None) -> datetime | None:
    if not value or value == "N":
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _acquire_activate_lock(engine: Engine) -> bool:
    """Giữ khóa kích hoạt (mẫu MENU_SYNC_LOCK); False nếu đang có người giữ."""
    now = _now()
    try:
        with engine.begin() as conn:
            lock_row = conn.execute(
                select(recon_app_setting.c.VALUE).where(recon_app_setting.c.KEY == _LOCK_KEY)
            ).scalar_one_or_none()
            held_at = _parse_lock(lock_row)
            if held_at is not None and now - held_at < _LOCK_TTL:
                return False
            if lock_row is None:
                conn.execute(
                    recon_app_setting.insert().values(
                        KEY=_LOCK_KEY, VALUE=now.isoformat(), UPDATED_BY="system", UPDATED_AT=now
                    )
                )
            else:
                conn.execute(
                    recon_app_setting.update()
                    .where(recon_app_setting.c.KEY == _LOCK_KEY)
                    .values(VALUE=now.isoformat(), UPDATED_BY="system", UPDATED_AT=now)
                )
    except SQLAlchemyError:
        return False
    return True


def _release_activate_lock(engine: Engine) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                recon_app_setting.update()
                .where(recon_app_setting.c.KEY == _LOCK_KEY)
                .values(VALUE="N", UPDATED_BY="system", UPDATED_AT=_now())
            )
    except SQLAlchemyError:
        pass


@service
@requires_menu("report_admin")
def activate_version(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Kích hoạt version DRY_RUN_OK → ACTIVE (chỉ một ACTIVE/template).

    Version cũ ACTIVE → ARCHIVED, ACTIVE_VERSION_ID cập nhật, cùng một
    transaction (T21-04). Khóa chống kích hoạt đồng thời.
    """
    engine = get_recon_engine()
    if not _acquire_activate_lock(engine):
        raise ServiceError(ErrorCode.CONFLICT, "Đang có thao tác kích hoạt khác, thử lại sau.")
    try:
        now = _now()
        with engine.begin() as conn:
            row = _load_version_row(conn, version_id, admin=True)
            if row["STATUS"] != "DRY_RUN_OK":
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    "Chỉ version DRY_RUN_OK mới được kích hoạt.",
                )
            # Layout tham số vượt 12 cột thì chặn kích hoạt (task 23 Q5).
            violations = layout_violations(conn, version_id)
            if violations:
                rows_txt = ", ".join(f"hàng {v['row']} (tổng {v['total']})" for v in violations)
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Layout tham số vượt 12 cột ở {rows_txt}; sửa layout trước khi kích hoạt.",
                )
            template_id = int(row["TEMPLATE_ID"])
            old_active_id = conn.execute(
                select(recon_rpt_tpl_ver.c.ID).where(
                    recon_rpt_tpl_ver.c.TEMPLATE_ID == template_id,
                    recon_rpt_tpl_ver.c.STATUS == "ACTIVE",
                )
            ).scalar_one_or_none()
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(
                    recon_rpt_tpl_ver.c.TEMPLATE_ID == template_id,
                    recon_rpt_tpl_ver.c.STATUS == "ACTIVE",
                )
                .values(STATUS="ARCHIVED", UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == version_id)
                .values(
                    STATUS="ACTIVE",
                    ACTIVATED_BY=ctx.username,
                    ACTIVATED_AT=now,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=int(row["ROW_VERSION"]) + 1,
                )
            )
            conn.execute(
                recon_report_template.update()
                .where(recon_report_template.c.ID == template_id)
                .values(ACTIVE_VERSION_ID=version_id, UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
            # Xóa cache LOV SQL của version mới và version cũ (dataflow F, task 23 Q7).
            invalidate_lov_cache_for_version(conn, version_id)
            if old_active_id is not None:
                invalidate_lov_cache_for_version(conn, int(old_active_id))
            write_audit_log(
                conn=conn,
                entity="RECON_RPT_TPL_VER",
                entity_id=version_id,
                action="ACTIVATE_VERSION",
                actor=ctx.username,
                old_data={"status": "DRY_RUN_OK"},
                new_data={"status": "ACTIVE", "template_id": template_id},
                now=now,
            )
            if old_active_id is not None:
                write_audit_log(
                    conn=conn,
                    entity="RECON_RPT_TPL_VER",
                    entity_id=int(old_active_id),
                    action="ARCHIVE_VERSION",
                    actor=ctx.username,
                    old_data={"status": "ACTIVE"},
                    new_data={"status": "ARCHIVED"},
                    now=now,
                )
            updated = (
                conn.execute(select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)).mappings().first()
            )
            assert updated is not None
            return _version_dict(updated)
    finally:
        _release_activate_lock(engine)


@service
@requires_menu("report_admin")
def reopen_version(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Mở lại version ACTIVE/DRY_RUN_OK về DRAFT để sửa lại bảng cũ (task 34).

    Chỉ ADMIN (cổng menu report_admin). Một transaction: version ACTIVE thì
    gỡ ACTIVE_VERSION_ID của template (template tạm không có version ACTIVE
    cho tới khi kích hoạt lại); DRY_RUN_OK thì chỉ đổi trạng thái. Ghi audit
    REOPEN_VERSION. DRAFT đã là DRAFT và ARCHIVED không mở lại.
    """
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = _load_version_row(conn, version_id, admin=True)
        status = str(row["STATUS"])
        if status not in ("ACTIVE", "DRY_RUN_OK"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ version ACTIVE hoặc DRY_RUN_OK mới mở lại được bản nháp.",
            )
        template_id = int(row["TEMPLATE_ID"])
        if status == "ACTIVE":
            conn.execute(
                recon_report_template.update()
                .where(recon_report_template.c.ID == template_id)
                .values(ACTIVE_VERSION_ID=None, UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
        conn.execute(
            recon_rpt_tpl_ver.update()
            .where(recon_rpt_tpl_ver.c.ID == version_id)
            .values(
                STATUS="DRAFT",
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=int(row["ROW_VERSION"]) + 1,
            )
        )
        write_audit_log(
            conn=conn,
            entity="RECON_RPT_TPL_VER",
            entity_id=version_id,
            action="REOPEN_VERSION",
            actor=ctx.username,
            old_data={"status": status},
            new_data={"status": "DRAFT", "template_id": template_id},
            now=now,
        )
        updated = conn.execute(select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)).mappings().first()
        assert updated is not None
        return _version_dict(updated)


@service
@requires_menu("report_admin")
def archive_version(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Lưu trữ version DRAFT/DRY_RUN_OK. Version ACTIVE không lưu trữ
    trực tiếp — kích hoạt version khác hoặc lưu trữ cả template."""
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        row = _load_version_row(conn, version_id, admin=True)
        if row["STATUS"] == "ACTIVE":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Không thể lưu trữ version đang ACTIVE.",
            )
        if row["STATUS"] != "ARCHIVED":
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == version_id)
                .values(
                    STATUS="ARCHIVED",
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=int(row["ROW_VERSION"]) + 1,
                )
            )
            write_audit_log(
                conn=conn,
                entity="RECON_RPT_TPL_VER",
                entity_id=version_id,
                action="ARCHIVE_VERSION",
                actor=ctx.username,
                old_data={"status": str(row["STATUS"])},
                new_data={"status": "ARCHIVED"},
                now=now,
            )
        updated = conn.execute(select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)).mappings().first()
        assert updated is not None
        return _version_dict(updated)
