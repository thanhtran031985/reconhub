"""Service Parameter báo cáo — task 23, spec 12/12a.

Parameter CRUD (chỉ version DRAFT), validation, default resolution.
LOV resolve + layout ở cùng module (bước 2–4).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field
from sqlalchemy import Connection, func, select

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_lookup_code,
    recon_lookup_type,
    recon_report,
    recon_report_template,
    recon_rpt_lov_cache,
    recon_rpt_param,
    recon_rpt_param_lov,
    recon_rpt_tpl_ver,
)
from app.engine.sql_guard import check_report_sql, discover_binds
from app.schemas.errors import ErrorCode, ServiceError
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.report_source import describe_report_sql, open_checked_connection

_CODE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,59}$")
_DATA_TYPES = ("STRING", "NUMBER", "DATE", "DATETIME", "BOOLEAN")
_CONTROL_TYPES = ("TEXT", "NUMBER", "DATE", "SELECT", "MULTI_SELECT", "DATE_RANGE")
_DEFAULT_TYPES = ("NONE", "STATIC", "TODAY", "FIRST_LOV")
_LOV_TYPES = ("NONE", "STATIC", "SQL", "LOOKUP")
_FILTER_OPERATORS = ("=", ">=", "<=", "BETWEEN", "IN", "LIKE_PREFIX", "IS_NULL")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LovPayload(BaseModel):
    """Payload LOV của một param."""

    lov_type: str = "NONE"
    data_source_id: int | None = None
    sql_text: str | None = None
    lookup_type: str | None = None
    static_json: list[dict[str, Any]] | None = None
    cache_seconds: int = Field(default=300, ge=0, le=3600)
    max_rows: int = Field(default=5000, ge=1, le=5000)


class ParamCreate(BaseModel):
    """Payload tạo param (wizard bước 3)."""

    code: str = Field(pattern=_CODE_RE)
    label: str = Field(min_length=1, max_length=200)
    data_type: Literal["STRING", "NUMBER", "DATE", "DATETIME", "BOOLEAN"] = "STRING"
    control_type: Literal["TEXT", "NUMBER", "DATE", "SELECT", "MULTI_SELECT", "DATE_RANGE"] = "TEXT"
    required: bool = False
    default_type: Literal["NONE", "STATIC", "TODAY", "FIRST_LOV"] = "NONE"
    default_value: str | None = None
    display_row: int | None = Field(default=None, ge=1)
    display_order: int | None = Field(default=None, ge=0)
    grid_span: int = Field(default=6, ge=1, le=12)
    filter_column: str | None = Field(default=None, max_length=128)
    filter_operator: str | None = None
    is_visible: bool = True
    lov: LovPayload | None = None


class ParamUpdate(BaseModel):
    """Payload sửa param (không đổi CODE — CODE là khóa bind)."""

    code: str | None = Field(default=None, pattern=_CODE_RE)
    label: str | None = Field(default=None, min_length=1, max_length=200)
    data_type: Literal["STRING", "NUMBER", "DATE", "DATETIME", "BOOLEAN"] | None = None
    control_type: Literal["TEXT", "NUMBER", "DATE", "SELECT", "MULTI_SELECT", "DATE_RANGE"] | None = None
    required: bool | None = None
    default_type: Literal["NONE", "STATIC", "TODAY", "FIRST_LOV"] | None = None
    default_value: str | None = None
    display_row: int | None = Field(default=None, ge=1)
    display_order: int | None = Field(default=None, ge=0)
    grid_span: int | None = Field(default=None, ge=1, le=12)
    filter_column: str | None = Field(default=None, max_length=128)
    filter_operator: str | None = None
    is_visible: bool | None = None
    lov: LovPayload | None = None


def _coerce_value(data_type: str, value: Any) -> Any:
    """Ép giá trị theo DATA_TYPE; lỗi → VALIDATION_ERROR.

    Trả về: STRING → str, NUMBER → int/float, DATE/DATETIME → chuỗi ISO,
    BOOLEAN → bool.
    """
    if value is None:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Giá trị không được để trống.")
    if data_type == "STRING":
        return str(value)
    if data_type == "NUMBER":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, f"Giá trị {value!r} không phải số."
            )
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, f"Giá trị {value!r} không phải số."
            ) from None
        return int(num) if num.is_integer() else num
    if data_type == "DATE":
        try:
            parsed = datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Giá trị {value!r} không đúng định dạng ngày YYYY-MM-DD.",
            ) from None
        return parsed.strftime("%Y-%m-%d")
    if data_type == "DATETIME":
        text = str(value).strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"Giá trị {value!r} không đúng định dạng ngày giờ.",
        )
    if data_type == "BOOLEAN":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.strip().upper() in ("Y", "N", "TRUE", "FALSE", "1", "0"):
            return value.strip().upper() in ("Y", "TRUE", "1")
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, f"Giá trị {value!r} không phải đúng/sai."
        )
    raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Kiểu dữ liệu không hỗ trợ: {data_type}.")


def _validate_lov(lov: LovPayload, conn: Connection) -> None:
    """Kiểm tra LOV (bước 1: cấu trúc; SQL describe/test ở resolve_lov bước 2)."""
    if lov.lov_type not in _LOV_TYPES:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, f"LOV_TYPE phải là một trong: {', '.join(_LOV_TYPES)}."
        )
    if lov.lov_type == "STATIC":
        items = lov.static_json
        if not items:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, "LOV STATIC cần ít nhất một mục Value/Label."
            )
        seen: set[str] = set()
        for item in items:
            if "value" not in item or "label" not in item:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR, "Mỗi mục STATIC cần có value và label."
                )
            key = str(item["value"])
            if key in seen:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR, f"Giá trị STATIC trùng: {key!r}."
                )
            seen.add(key)
    elif lov.lov_type == "SQL":
        if lov.data_source_id is None or not (lov.sql_text or "").strip():
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, "LOV SQL cần Data Source và SQL_TEXT."
            )
        ds = conn.execute(
            select(recon_data_source.c.ID).where(
                recon_data_source.c.ID == lov.data_source_id
            )
        ).first()
        if ds is None:
            raise ServiceError(
                ErrorCode.NOT_FOUND,
                f"Nguồn dữ liệu ID={lov.data_source_id} không tồn tại",
            )
        ok, reason, _binds = check_report_sql(lov.sql_text)
        if not ok:
            raise ServiceError(
                ErrorCode.SQL_NOT_ALLOWED, reason or "SQL LOV không hợp lệ."
            )
    elif lov.lov_type == "LOOKUP":
        if not (lov.lookup_type or "").strip():
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, "LOV LOOKUP cần chọn lookup type."
            )
        row = conn.execute(
            select(recon_lookup_type.c.IS_ACTIVE).where(
                recon_lookup_type.c.LOOKUP_TYPE == lov.lookup_type
            )
        ).mappings().first()
        if row is None:
            raise ServiceError(
                ErrorCode.NOT_FOUND, f"Lookup type {lov.lookup_type!r} không tồn tại."
            )
        if row["IS_ACTIVE"] != "Y":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Lookup type {lov.lookup_type!r} đã ngừng dùng.",
            )


def _validate_param(dto: ParamCreate, conn: Connection) -> None:
    """Kiểm tra tương thích data/control type, default và LOV."""
    if dto.control_type in ("SELECT", "MULTI_SELECT"):
        lov_type = (dto.lov.lov_type if dto.lov else "NONE")
        if lov_type == "NONE":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Control {dto.control_type} bắt buộc phải có LOV khác NONE.",
            )
    if dto.control_type == "DATE_RANGE" and dto.data_type not in ("DATE", "DATETIME"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Control DATE_RANGE chỉ dùng với DATA_TYPE DATE/DATETIME.",
        )
    if dto.default_type == "TODAY" and dto.data_type not in ("DATE", "DATETIME"):
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Default TODAY chỉ dùng với DATA_TYPE DATE/DATETIME.",
        )
    if dto.default_type == "FIRST_LOV":
        lov_type = (dto.lov.lov_type if dto.lov else "NONE")
        if lov_type == "NONE":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Default FIRST_LOV chỉ dùng khi param có LOV khác NONE.",
            )
    if dto.default_type == "STATIC":
        if dto.default_value is None or str(dto.default_value).strip() == "":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Default STATIC cần có DEFAULT_VALUE.",
            )
        _coerce_value(dto.data_type, dto.default_value)
    if dto.filter_operator is not None and dto.filter_operator not in _FILTER_OPERATORS:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            f"FILTER_OPERATOR phải là một trong: {', '.join(_FILTER_OPERATORS)}.",
        )
    if dto.lov is not None:
        _validate_lov(dto.lov, conn)


def _load_version_draft(conn: Connection, version_id: int) -> Any:
    """Đọc version; chỉ DRAFT mới sửa được param/layout."""
    row = (
        conn.execute(
            select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy version.")
    if row["STATUS"] != "DRAFT":
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            "Chỉ version DRAFT mới sửa được tham số; version đã khóa cần clone mới.",
        )
    return row


def _load_version_for_resolve(conn: Connection, version_id: int, admin: bool) -> Any:
    """Đọc version cho resolve/preview: người thường chỉ thấy report hiển thị."""
    row = (
        conn.execute(
            select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy version.")
    if not admin:
        report_row = (
            conn.execute(
                select(recon_report)
                .join(
                    recon_report_template,
                    recon_report_template.c.REPORT_ID == recon_report.c.ID,
                )
                .where(recon_report_template.c.ID == int(row["TEMPLATE_ID"]))
            )
            .mappings()
            .first()
        )
        if (
            report_row is None
            or report_row["IS_VISIBLE"] != "Y"
            or report_row["IS_ACTIVE"] != "Y"
        ):
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy version.")
    return row


def _lov_dict(lov_row: Any) -> dict[str, Any] | None:
    if lov_row is None:
        return None
    return {
        "lov_type": str(lov_row["LOV_TYPE"]),
        "data_source_id": lov_row["DATA_SOURCE_ID"],
        "sql_text": lov_row["SQL_TEXT"],
        "lookup_type": lov_row["LOOKUP_TYPE"],
        "static_json": lov_row["STATIC_JSON"],
        "cache_seconds": int(lov_row["CACHE_SECONDS"]),
        "max_rows": int(lov_row["MAX_ROWS"]),
    }


def _param_dict(conn: Connection, param_row: Any) -> dict[str, Any]:
    lov_row = (
        conn.execute(
            select(recon_rpt_param_lov).where(
                recon_rpt_param_lov.c.PARAM_ID == param_row["ID"]
            )
        )
        .mappings()
        .first()
    )
    return {
        "id": int(param_row["ID"]),
        "version_id": int(param_row["VERSION_ID"]),
        "code": str(param_row["CODE"]),
        "label": str(param_row["LABEL"]),
        "data_type": str(param_row["DATA_TYPE"]),
        "control_type": str(param_row["CONTROL_TYPE"]),
        "required": param_row["REQUIRED"] == "Y",
        "default_type": param_row["DEFAULT_TYPE"],
        "default_value": param_row["DEFAULT_VALUE"],
        "display_row": int(param_row["DISPLAY_ROW"]),
        "display_order": int(param_row["DISPLAY_ORDER"]),
        "grid_span": int(param_row["GRID_SPAN"]),
        "filter_column": param_row["FILTER_COLUMN"],
        "filter_operator": param_row["FILTER_OPERATOR"],
        "is_visible": param_row["IS_VISIBLE"] == "Y",
        "lov": _lov_dict(lov_row),
    }


def _auto_place(conn: Connection, version_id: int, span: int) -> tuple[int, int]:
    """Xếp param mới vào cuối layout: hàng cuối còn chỗ, không thì hàng mới."""
    rows = (
        conn.execute(
            select(
                recon_rpt_param.c.DISPLAY_ROW,
                func.sum(recon_rpt_param.c.GRID_SPAN).label("total"),
                func.max(recon_rpt_param.c.DISPLAY_ORDER).label("max_order"),
            )
            .where(
                recon_rpt_param.c.VERSION_ID == version_id,
                recon_rpt_param.c.IS_VISIBLE == "Y",
            )
            .group_by(recon_rpt_param.c.DISPLAY_ROW)
            .order_by(recon_rpt_param.c.DISPLAY_ROW)
        )
        .mappings()
        .all()
    )
    if not rows:
        return 1, 10
    last = rows[-1]
    if int(last["total"] or 0) + span <= 12:
        return int(last["DISPLAY_ROW"]), int(last["max_order"] or 0) + 10
    return int(last["DISPLAY_ROW"]) + 1, 10


def _insert_lov(conn: Connection, param_id: int, lov: LovPayload) -> None:
    conn.execute(
        recon_rpt_param_lov.insert().values(
            PARAM_ID=param_id,
            LOV_TYPE=lov.lov_type,
            DATA_SOURCE_ID=lov.data_source_id,
            SQL_TEXT=lov.sql_text,
            LOOKUP_TYPE=lov.lookup_type,
            STATIC_JSON=lov.static_json,
            CACHE_SECONDS=lov.cache_seconds,
            MAX_ROWS=lov.max_rows,
        )
    )


@service
@requires_menu("report_admin")
def create_param(ctx: Ctx, version_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Tạo param cho version DRAFT kèm LOV (một transaction + audit)."""
    dto = ParamCreate(**payload)
    engine = get_recon_engine()
    with engine.begin() as conn:
        _load_version_draft(conn, version_id)
        _validate_param(dto, conn)
        exists = conn.execute(
            select(recon_rpt_param.c.ID).where(
                recon_rpt_param.c.VERSION_ID == version_id,
                recon_rpt_param.c.CODE == dto.code,
            )
        ).first()
        if exists is not None:
            raise ServiceError(
                ErrorCode.CONFLICT, f"Mã tham số {dto.code} đã tồn tại trong version."
            )
        if dto.display_row is None or dto.display_order is None:
            auto_row, auto_order = _auto_place(conn, version_id, dto.grid_span)
            display_row = dto.display_row if dto.display_row is not None else auto_row
            display_order = (
                dto.display_order if dto.display_order is not None else auto_order
            )
        else:
            display_row, display_order = dto.display_row, dto.display_order
        res = conn.execute(
            recon_rpt_param.insert().values(
                VERSION_ID=version_id,
                CODE=dto.code,
                LABEL=dto.label,
                DATA_TYPE=dto.data_type,
                CONTROL_TYPE=dto.control_type,
                REQUIRED="Y" if dto.required else "N",
                DEFAULT_TYPE=dto.default_type,
                DEFAULT_VALUE=dto.default_value,
                DISPLAY_ROW=display_row,
                DISPLAY_ORDER=display_order,
                GRID_SPAN=dto.grid_span,
                FILTER_COLUMN=dto.filter_column,
                FILTER_OPERATOR=dto.filter_operator,
                IS_VISIBLE="Y" if dto.is_visible else "N",
            )
        )
        pk = res.inserted_primary_key
        if pk is None:
            raise ServiceError(ErrorCode.INTERNAL_ERROR, "Không tạo được tham số.")
        param_id = int(pk[0])
        _insert_lov(conn, param_id, dto.lov or LovPayload())
        write_audit_log(
            conn,
            "RECON_RPT_PARAM",
            param_id,
            "CREATE_PARAM",
            ctx.username,
            new_data={"version_id": version_id, "code": dto.code},
        )
        row = (
            conn.execute(
                select(recon_rpt_param).where(recon_rpt_param.c.ID == param_id)
            )
            .mappings()
            .first()
        )
        assert row is not None
        return _param_dict(conn, row)


@service
@requires_menu("report_admin")
def update_param(
    ctx: Ctx, version_id: int, param_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    """Sửa param của version DRAFT (không đổi CODE — CODE là khóa bind)."""
    dto = ParamUpdate(**payload)
    engine = get_recon_engine()
    with engine.begin() as conn:
        _load_version_draft(conn, version_id)
        row = (
            conn.execute(
                select(recon_rpt_param).where(
                    recon_rpt_param.c.ID == param_id,
                    recon_rpt_param.c.VERSION_ID == version_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy tham số.")
        if dto.code is not None and dto.code != row["CODE"]:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Không đổi được CODE tham số (CODE là khóa bind); "
                "muốn đổi mã thì xóa rồi tạo lại sau khi sửa SQL.",
            )
        merged = ParamCreate(
            code=str(row["CODE"]),
            label=dto.label if dto.label is not None else str(row["LABEL"]),
            data_type=dto.data_type or str(row["DATA_TYPE"]),  # type: ignore[arg-type]
            control_type=dto.control_type or str(row["CONTROL_TYPE"]),  # type: ignore[arg-type]
            required=dto.required if dto.required is not None else row["REQUIRED"] == "Y",
            default_type=dto.default_type or str(row["DEFAULT_TYPE"] or "NONE"),  # type: ignore[arg-type]
            default_value=dto.default_value if dto.default_value is not None else row["DEFAULT_VALUE"],
            display_row=dto.display_row if dto.display_row is not None else int(row["DISPLAY_ROW"]),
            display_order=dto.display_order if dto.display_order is not None else int(row["DISPLAY_ORDER"]),
            grid_span=dto.grid_span if dto.grid_span is not None else int(row["GRID_SPAN"]),
            filter_column=dto.filter_column if dto.filter_column is not None else row["FILTER_COLUMN"],
            filter_operator=dto.filter_operator if dto.filter_operator is not None else row["FILTER_OPERATOR"],
            is_visible=dto.is_visible if dto.is_visible is not None else row["IS_VISIBLE"] == "Y",
            lov=dto.lov,
        )
        if dto.lov is None:
            lov_row = (
                conn.execute(
                    select(recon_rpt_param_lov).where(
                        recon_rpt_param_lov.c.PARAM_ID == param_id
                    )
                )
                .mappings()
                .first()
            )
            if lov_row is not None:
                merged.lov = LovPayload(
                    lov_type=str(lov_row["LOV_TYPE"]),
                    data_source_id=lov_row["DATA_SOURCE_ID"],
                    sql_text=lov_row["SQL_TEXT"],
                    lookup_type=lov_row["LOOKUP_TYPE"],
                    static_json=lov_row["STATIC_JSON"],
                    cache_seconds=int(lov_row["CACHE_SECONDS"]),
                    max_rows=int(lov_row["MAX_ROWS"]),
                )
        _validate_param(merged, conn)
        conn.execute(
            recon_rpt_param.update()
            .where(recon_rpt_param.c.ID == param_id)
            .values(
                LABEL=merged.label,
                DATA_TYPE=merged.data_type,
                CONTROL_TYPE=merged.control_type,
                REQUIRED="Y" if merged.required else "N",
                DEFAULT_TYPE=merged.default_type,
                DEFAULT_VALUE=merged.default_value,
                DISPLAY_ROW=merged.display_row,
                DISPLAY_ORDER=merged.display_order,
                GRID_SPAN=merged.grid_span,
                FILTER_COLUMN=merged.filter_column,
                FILTER_OPERATOR=merged.filter_operator,
                IS_VISIBLE="Y" if merged.is_visible else "N",
            )
        )
        if dto.lov is not None:
            conn.execute(
                recon_rpt_param_lov.delete().where(
                    recon_rpt_param_lov.c.PARAM_ID == param_id
                )
            )
            _insert_lov(conn, param_id, dto.lov)
        write_audit_log(
            conn,
            "RECON_RPT_PARAM",
            param_id,
            "UPDATE_PARAM",
            ctx.username,
            new_data={"version_id": version_id, "code": str(row["CODE"])},
        )
        updated = (
            conn.execute(
                select(recon_rpt_param).where(recon_rpt_param.c.ID == param_id)
            )
            .mappings()
            .first()
        )
        assert updated is not None
        return _param_dict(conn, updated)


@service
@requires_menu("report_admin")
def delete_param(ctx: Ctx, version_id: int, param_id: int) -> dict[str, Any]:
    """Xóa param của version DRAFT (chặn khi CODE còn là bind trong SQL)."""
    engine = get_recon_engine()
    with engine.begin() as conn:
        ver = _load_version_draft(conn, version_id)
        row = (
            conn.execute(
                select(recon_rpt_param).where(
                    recon_rpt_param.c.ID == param_id,
                    recon_rpt_param.c.VERSION_ID == version_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy tham số.")
        code = str(row["CODE"])
        sql_texts: list[str] = []
        if ver["SOURCE_TYPE"] == "CUSTOM_SQL" and ver["SQL_TEXT"]:
            sql_texts.append(str(ver["SQL_TEXT"]))
        lov_rows = (
            conn.execute(
                select(recon_rpt_param_lov.c.SQL_TEXT)
                .join(
                    recon_rpt_param,
                    recon_rpt_param.c.ID == recon_rpt_param_lov.c.PARAM_ID,
                )
                .where(
                    recon_rpt_param.c.VERSION_ID == version_id,
                    recon_rpt_param_lov.c.LOV_TYPE == "SQL",
                )
            ).all()
        )
        sql_texts.extend(str(r[0]) for r in lov_rows if r[0])
        for sql_text in sql_texts:
            _ok, _reason, binds = check_report_sql(sql_text)
            if code in binds:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Không xóa được tham số {code} vì còn là bind trong SQL.",
                )
        conn.execute(
            recon_rpt_param_lov.delete().where(
                recon_rpt_param_lov.c.PARAM_ID == param_id
            )
        )
        conn.execute(
            recon_rpt_param.delete().where(recon_rpt_param.c.ID == param_id)
        )
        write_audit_log(
            conn,
            "RECON_RPT_PARAM",
            param_id,
            "DELETE_PARAM",
            ctx.username,
            new_data={"version_id": version_id, "code": code},
        )
        return {"deleted": True, "code": code}


def _load_params_with_lov(conn: Connection, version_id: int) -> list[dict[str, Any]]:
    """Đọc toàn bộ param của version kèm LOV, theo DISPLAY_ROW/ORDER."""
    rows = (
        conn.execute(
            select(recon_rpt_param)
            .where(recon_rpt_param.c.VERSION_ID == version_id)
            .order_by(recon_rpt_param.c.DISPLAY_ROW, recon_rpt_param.c.DISPLAY_ORDER)
        )
        .mappings()
        .all()
    )
    return [_param_dict(conn, row) for row in rows]


def _normalize_pair(value: Any) -> list[Any] | None:
    """Chuẩn hóa giá trị cặp (BETWEEN/DATE_RANGE) về [from, to]."""
    if isinstance(value, dict) and "from" in value and "to" in value:
        return [value["from"], value["to"]]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [value[0], value[1]]
    return None


def _validate_resolved_value(param: dict[str, Any], value: Any) -> Any:
    """Kiểm tra type/range của một giá trị đã resolve; trả giá trị đã ép kiểu."""
    data_type = str(param["data_type"])
    control_type = str(param["control_type"])
    op = param.get("filter_operator")
    if control_type == "DATE_RANGE" or op == "BETWEEN":
        pair = _normalize_pair(value)
        if pair is None:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Tham số {param['code']} cần đúng 2 giá trị (từ – đến).",
            )
        lo = _coerce_value(data_type, pair[0])
        hi = _coerce_value(data_type, pair[1])
        if lo > hi:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Tham số {param['code']}: giá trị đầu phải ≤ giá trị cuối.",
            )
        return [lo, hi]
    if op == "IN" or control_type == "MULTI_SELECT":
        if not isinstance(value, (list, tuple)):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Tham số {param['code']} cần danh sách giá trị.",
            )
        return [_coerce_value(data_type, item) for item in value]
    return _coerce_value(data_type, value)


@service
@requires_menu("report_center")
def resolve_param_values(
    ctx: Ctx,
    version_id: int,
    values: dict[str, Any],
    lov_resolver: Callable[[int, int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Điền default và kiểm tra giá trị tham số cho một lần chạy (T23-05).

    values: giá trị người dùng nhập {code: value}. lov_resolver: hàm lấy
    options LOV (version_id, param_id) -> [{value, label}] — dùng cho
    default FIRST_LOV; mặc định dùng resolver thật (bước 2), truyền vào
    để test hoặc ghi đè. Trả {code: giá trị đã ép kiểu}; param không bắt
    buộc và không có giá trị thì vắng mặt.
    """
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        ver = _load_version_for_resolve(conn, version_id, admin)
        params = _load_params_with_lov(conn, version_id)
        by_id = {int(p["id"]): p for p in params}
        resolved: dict[str, Any] = {}
        for param in params:
            code = str(param["code"])
            raw = values.get(code)
            has_value = raw is not None and raw != "" and raw != []
            if not has_value:
                default_type = param.get("default_type") or "NONE"
                if default_type == "STATIC":
                    raw = param.get("default_value")
                    has_value = raw is not None and str(raw).strip() != ""
                elif default_type == "TODAY":
                    today = _now().date().isoformat()
                    raw = (
                        today
                        if param["data_type"] == "DATE"
                        else f"{today}T00:00:00"
                    )
                    has_value = True
                elif default_type == "FIRST_LOV":
                    resolver = lov_resolver or (
                        lambda vid, pid: _resolve_lov_options(
                            engine, ver, by_id[pid], resolved
                        )
                    )
                    options = resolver(version_id, int(param["id"]))
                    if options:
                        raw = options[0]["value"]
                        has_value = True
            if not has_value:
                if param["required"]:
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Tham số {param['label']} ({code}) là bắt buộc.",
                    )
                continue
            resolved[code] = _validate_resolved_value(param, raw)
    return resolved


# ─── LOV (bước 2) ──────────────────────────────────────────────────────────


def _lov_cache_key(
    data_source_id: int, sql_text: str, dep_values: dict[str, Any]
) -> str:
    """Key cache SQL LOV: sha256(Data Source + SQL) : sha256(dep params).

    Phần đầu (base) dùng để xóa cache theo LOV khi activate (Q7).
    """
    base = hashlib.sha256(f"{data_source_id}|{sql_text}".encode()).hexdigest()
    dep_hash = hashlib.sha256(
        json.dumps(dep_values or {}, sort_keys=True, default=str).encode()
    ).hexdigest()
    return f"{base}:{dep_hash}"


def _read_lov_cache(conn: Connection, cache_key: str) -> list[dict[str, Any]] | None:
    row = (
        conn.execute(
            select(recon_rpt_lov_cache).where(
                recon_rpt_lov_cache.c.CACHE_KEY == cache_key
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    if row["EXPIRES_AT"] <= _now():
        return None
    payload = row["PAYLOAD_JSON"]
    return list(payload) if isinstance(payload, list) else None


def _write_lov_cache(
    conn: Connection,
    cache_key: str,
    options: list[dict[str, Any]],
    cache_seconds: int,
) -> None:
    now = _now()
    conn.execute(
        recon_rpt_lov_cache.delete().where(
            recon_rpt_lov_cache.c.CACHE_KEY == cache_key
        )
    )
    conn.execute(
        recon_rpt_lov_cache.insert().values(
            CACHE_KEY=cache_key,
            PAYLOAD_JSON=options,
            ROW_COUNT=len(options),
            EXPIRES_AT=now + timedelta(seconds=cache_seconds),
            CREATED_AT=now,
        )
    )


def invalidate_lov_cache_for_version(conn: Connection, version_id: int) -> int:
    """Xóa cache LOV SQL của version (dùng khi activate — dataflow F, Q7)."""
    lov_rows = (
        conn.execute(
            select(recon_rpt_param_lov.c.DATA_SOURCE_ID, recon_rpt_param_lov.c.SQL_TEXT)
            .join(
                recon_rpt_param,
                recon_rpt_param.c.ID == recon_rpt_param_lov.c.PARAM_ID,
            )
            .where(
                recon_rpt_param.c.VERSION_ID == version_id,
                recon_rpt_param_lov.c.LOV_TYPE == "SQL",
            )
        ).all()
    )
    total = 0
    for ds_id, sql_text in lov_rows:
        if not sql_text:
            continue
        base = hashlib.sha256(f"{ds_id}|{sql_text}".encode()).hexdigest()
        res = conn.execute(
            recon_rpt_lov_cache.delete().where(
                recon_rpt_lov_cache.c.CACHE_KEY.like(f"{base}:%")
            )
        )
        total += res.rowcount or 0
    return total


def _execute_lov_sql(
    data_source_id: int,
    sql_text: str,
    binds: dict[str, Any],
    timeout_sec: int,
    max_rows: int,
) -> list[dict[str, Any]]:
    """Chạy SQL LOV read-only, lấy tối đa max_rows (fetchmany, T23-03)."""
    with open_checked_connection(data_source_id, timeout_sec) as ora_conn:
        cursor = ora_conn.cursor()
        try:
            cursor.execute(sql_text, binds)
            desc = cursor.description or []
            names = [str(d[0]).upper() for d in desc]
            if "VALUE" not in names or "LABEL" not in names:
                raise ServiceError(
                    ErrorCode.SQL_DESCRIBE_FAILED,
                    "SQL LOV phải trả về 2 cột VALUE và LABEL.",
                )
            value_idx = names.index("VALUE")
            label_idx = names.index("LABEL")
            # fetchmany đã giới hạn ở cursor; cắt lại để chắc chắn với mọi driver.
            rows = (cursor.fetchmany(max_rows) or [])[:max_rows]
            return [
                {"value": r[value_idx], "label": r[label_idx]} for r in rows
            ]
        finally:
            try:
                cursor.close()
            except Exception:
                pass


def _resolve_lov_options(
    engine,
    version_row: Any,
    param: dict[str, Any],
    dep_values: dict[str, Any],
) -> list[dict[str, Any]]:
    """Lấy options LOV của một param (hàm lõi dùng cho resolve_lov và default FIRST_LOV)."""
    lov = param.get("lov") or {}
    lov_type = str(lov.get("lov_type") or "NONE")
    if lov_type == "NONE":
        return []
    if lov_type == "STATIC":
        items = lov.get("static_json") or []
        return [{"value": i["value"], "label": i["label"]} for i in items]
    if lov_type == "LOOKUP":
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    select(recon_lookup_code)
                    .where(
                        recon_lookup_code.c.LOOKUP_TYPE == lov.get("lookup_type"),
                        recon_lookup_code.c.IS_ACTIVE == "Y",
                    )
                    .order_by(
                        recon_lookup_code.c.DISPLAY_ORDER,
                        recon_lookup_code.c.LOOKUP_CODE,
                    )
                )
                .mappings()
                .all()
            )
        return [
            {"value": str(r["LOOKUP_CODE"]), "label": str(r["MEANING"])} for r in rows
        ]
    if lov_type == "SQL":
        ds_id = lov.get("data_source_id")
        sql_text = str(lov.get("sql_text") or "")
        cache_seconds = int(lov.get("cache_seconds") or 0)
        max_rows = int(lov.get("max_rows") or 5000)
        timeout = int(version_row["TIMEOUT_SEC"] or 300)
        cache_key = _lov_cache_key(ds_id, sql_text, dep_values)
        if cache_seconds > 0:
            with engine.connect() as conn:
                cached = _read_lov_cache(conn, cache_key)
            if cached is not None:
                return cached
        described = describe_report_sql(ds_id, sql_text, timeout)
        names = [str(c["name"]).upper() for c in described["columns"]]
        if "VALUE" not in names or "LABEL" not in names:
            raise ServiceError(
                ErrorCode.SQL_DESCRIBE_FAILED,
                "SQL LOV phải trả về 2 cột VALUE và LABEL.",
            )
        _ok, _reason, binds = check_report_sql(sql_text)
        missing = [b for b in binds if b not in (dep_values or {})]
        if missing:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"SQL LOV cần giá trị cho bind :{missing[0]}.",
            )
        options = _execute_lov_sql(
            ds_id,
            sql_text,
            {b: dep_values[b] for b in binds},
            timeout,
            max_rows,
        )
        if cache_seconds > 0:
            with engine.begin() as conn:
                _write_lov_cache(conn, cache_key, options, cache_seconds)
        return options
    raise ServiceError(
        ErrorCode.VALIDATION_ERROR, f"LOV_TYPE không hỗ trợ: {lov_type}."
    )


@service
@requires_menu("report_center")
def resolve_lov(
    ctx: Ctx,
    version_id: int,
    param_id: int,
    dep_values: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Lấy options LOV của một param (T23-02, T23-03, T23-04).

    NONE → []; STATIC → từ STATIC_JSON; SQL → cache rồi execute read-only
    với binds (dataflow D); LOOKUP → chỉ mã active.
    """
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        ver = _load_version_for_resolve(conn, version_id, admin)
        params = _load_params_with_lov(conn, version_id)
        param = next((p for p in params if int(p["id"]) == param_id), None)
        if param is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy tham số.")
    return _resolve_lov_options(engine, ver, param, dep_values or {})
