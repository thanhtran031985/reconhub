"""Service Report Studio — task 109 Bước 2.

Báo cáo Studio tái dùng RECON_REPORT + RECON_REPORT_TEMPLATE +
RECON_RPT_TPL_VER với SOURCE_TYPE='SEMANTIC_MODEL'; mỗi version pin một
MODEL_VERSION_ID (phiên bản model ACTIVE lúc tạo/phát hành). Visual lưu
chuẩn hóa ở RECON_RPT_VISUAL / RECON_RPT_VISUAL_FIELD.

Luồng version giống wizard cổ điển: DRAFT -> DRY_RUN_OK (validate) ->
ACTIVE (publish, khóa REPORT_ACTIVATE_LOCK); bản ACTIVE cũ -> ARCHIVED.
Phiên bản model bị ARCHIVED (model đã phát hành v2) thì preview/validate
chặn theo quy tắc fail-closed của planner task 108 (MODEL_VERSION_LOCKED);
nâng cấp báo cáo sang model version mới là việc riêng, xem decisions.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Connection, func, select

from app.core.audit import write_audit_log
from app.core.context import Ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_report,
    recon_report_template,
    recon_rpt_model,
    recon_rpt_model_ver,
    recon_rpt_param,
    recon_rpt_param_lov,
    recon_rpt_tpl_ver,
    recon_rpt_visual,
    recon_rpt_visual_field,
)
from app.engine.semantic_planner import resolve_semantic_plan
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.report_studio import (
    StudioCloneDTO,
    StudioDraftSaveDTO,
    StudioPublishDTO,
    StudioReportCreateDTO,
    StudioVisualDTO,
)
from app.schemas.semantic_query import SemanticQueryIntent
from app.services import service
from app.services.perm import is_admin, requires_menu
from app.services.report import load_report_row
from app.services.report_param import (
    LovPayload,
    ParamCreate,
    _auto_place,
    _insert_lov,
    _load_params_with_lov,
    _validate_param,
    invalidate_lov_cache_for_version,
)
from app.services.report_template import (
    _acquire_activate_lock,
    _release_activate_lock,
    _version_dict,
)
from app.services.semantic_model import _pk_from_insert, load_version_bundle
from app.services.semantic_query import execute_semantic_preview

# Giới hạn pivot Matrix ở server (hàng x cột) — vượt thì cắt + báo truncated.
_MATRIX_MAX_ROWS = 50
_MATRIX_MAX_COLS = 20

_DIMENSION_WELLS = ("X", "ROWS", "COLUMNS", "SERIES")
_MEASURE_WELLS = ("Y", "VALUES", "VALUE")
_VISUAL_WELLS: dict[str, tuple[str, ...]] = {
    "TABLE": ("X", "Y"),
    "MATRIX": ("ROWS", "COLUMNS", "VALUES"),
    "KPI": ("VALUE",),
    "BAR": ("X", "Y", "SERIES"),
    "LINE": ("X", "Y", "SERIES"),
}
_EDITABLE_STATUSES = ("DRAFT", "DRY_RUN_OK")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Loader nội bộ
# ---------------------------------------------------------------------------


def _load_template_of_report(conn: Connection, report_id: int) -> Any:
    row = (
        conn.execute(
            select(recon_report_template)
            .where(recon_report_template.c.REPORT_ID == report_id)
            .order_by(recon_report_template.c.ID)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy template của báo cáo.")
    return row


def _load_studio_version(conn: Connection, version_id: int) -> Any:
    row = (
        conn.execute(select(recon_rpt_tpl_ver).where(recon_rpt_tpl_ver.c.ID == version_id))
        .mappings()
        .first()
    )
    if row is None:
        raise ServiceError(ErrorCode.NOT_FOUND, "Không tìm thấy phiên bản báo cáo.")
    if row["SOURCE_TYPE"] != "SEMANTIC_MODEL" or row["MODEL_VERSION_ID"] is None:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR, "Phiên bản này không phải báo cáo Studio."
        )
    return row


def _report_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "code": str(row["CODE"]),
        "name": str(row["NAME"]),
        "category_code": row["CATEGORY_CODE"],
        "owner": str(row["OWNER"]),
        "description": row["DESCRIPTION"],
        "is_visible": row["IS_VISIBLE"] == "Y",
        "is_active": row["IS_ACTIVE"] == "Y",
        "row_version": int(row["ROW_VERSION"]),
    }


def _field_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["ID"]),
        "well_role": str(row["WELL_ROLE"]),
        "field_id": int(row["FIELD_ID"]) if row["FIELD_ID"] is not None else None,
        "measure_id": int(row["MEASURE_ID"]) if row["MEASURE_ID"] is not None else None,
        "aggregation": str(row["AGGREGATION"]),
        "date_part": row["DATE_PART"],
        "alias": row["ALIAS"],
        "label_override": row["LABEL_OVERRIDE"],
        "format_mask": row["FORMAT_MASK"],
        "sort_direction": row["SORT_DIRECTION"],
        "display_order": int(row["DISPLAY_ORDER"]),
    }


def _visual_dict(vis: Any, fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": int(vis["ID"]),
        "code": str(vis["CODE"]),
        "title": str(vis["TITLE"]),
        "visual_type": str(vis["VISUAL_TYPE"]),
        "display_order": int(vis["DISPLAY_ORDER"]),
        "grid_span": int(vis["GRID_SPAN"]),
        "height_size": str(vis["HEIGHT_SIZE"]),
        "config": json.loads(vis["CONFIG_JSON"]) if vis["CONFIG_JSON"] else {},
        "fields": fields,
    }


def load_visual_by_id(conn: Connection, visual_id: int) -> dict[str, Any]:
    """Đọc 1 visual + fields theo ID (dùng cho run/export của Viewer).

    Trả thêm ``version_id`` để caller kiểm tra visual thuộc đúng version.
    """
    vis = (
        conn.execute(select(recon_rpt_visual).where(recon_rpt_visual.c.ID == int(visual_id)))
        .mappings()
        .first()
    )
    if vis is None:
        raise ServiceError(ErrorCode.NOT_FOUND, f"Không tìm thấy visual #{visual_id}.")
    field_rows = (
        conn.execute(
            select(recon_rpt_visual_field)
            .where(recon_rpt_visual_field.c.VISUAL_ID == int(visual_id))
            .order_by(
                recon_rpt_visual_field.c.DISPLAY_ORDER,
                recon_rpt_visual_field.c.ID,
            )
        )
        .mappings()
        .all()
    )
    visual = _visual_dict(vis, [_field_dict(fr) for fr in field_rows])
    visual["version_id"] = int(vis["VERSION_ID"])
    return visual


def _load_visuals(conn: Connection, version_id: int) -> list[dict[str, Any]]:
    vis_rows = (
        conn.execute(
            select(recon_rpt_visual)
            .where(recon_rpt_visual.c.VERSION_ID == version_id)
            .order_by(recon_rpt_visual.c.DISPLAY_ORDER, recon_rpt_visual.c.ID)
        )
        .mappings()
        .all()
    )
    if not vis_rows:
        return []
    vis_ids = [int(v["ID"]) for v in vis_rows]
    field_rows = (
        conn.execute(
            select(recon_rpt_visual_field)
            .where(recon_rpt_visual_field.c.VISUAL_ID.in_(vis_ids))
            .order_by(
                recon_rpt_visual_field.c.VISUAL_ID,
                recon_rpt_visual_field.c.DISPLAY_ORDER,
                recon_rpt_visual_field.c.ID,
            )
        )
        .mappings()
        .all()
    )
    by_visual: dict[int, list[dict[str, Any]]] = {vid: [] for vid in vis_ids}
    for fr in field_rows:
        by_visual[int(fr["VISUAL_ID"])].append(_field_dict(fr))
    return [_visual_dict(v, by_visual[int(v["ID"])]) for v in vis_rows]


def _draft_detail(
    conn: Connection, report_row: Any, template_row: Any, version_row: Any
) -> dict[str, Any]:
    bundle = load_version_bundle(conn, int(version_row["MODEL_VERSION_ID"]))
    return {
        "report": _report_dict(report_row),
        "template": {
            "id": int(template_row["ID"]),
            "code": str(template_row["CODE"]),
            "name": str(template_row["NAME"]),
        },
        "version": _version_dict(version_row),
        "model": bundle,
        "visuals": _load_visuals(conn, int(version_row["ID"])),
        "params": _load_params_with_lov(conn, int(version_row["ID"])),
    }


# ---------------------------------------------------------------------------
# Kiểm tra visual gắn đúng phiên bản model đã pin
# ---------------------------------------------------------------------------


def _validate_visuals_against_bundle(
    visuals: list[StudioVisualDTO], bundle: dict[str, Any]
) -> None:
    """Mọi field/measure phải thuộc bundle, đang hiển thị, đúng vai trò well."""
    fields_by_id: dict[int, dict[str, Any]] = {}
    field_table: dict[int, str] = {}
    for table in bundle.get("tables") or []:
        for f in table.get("fields") or []:
            fields_by_id[int(f["id"])] = f
            field_table[int(f["id"])] = str(table["alias"])
    measures_by_id = {int(m["id"]): m for m in (bundle.get("measures") or [])}

    seen_codes: set[str] = set()
    for vis in visuals:
        if vis.code in seen_codes:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR, f"Mã visual {vis.code} bị trùng trong bản nháp."
            )
        seen_codes.add(vis.code)
        allowed = _VISUAL_WELLS[vis.visual_type]
        by_role: dict[str, list[Any]] = {}
        for f in vis.fields:
            if f.well_role not in allowed:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Visual {vis.visual_type} không dùng well {f.well_role}.",
                )
            by_role.setdefault(f.well_role, []).append(f)
        if vis.visual_type == "MATRIX":
            for role in ("ROWS", "COLUMNS", "VALUES"):
                if len(by_role.get(role, [])) != 1:
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        "Visual MATRIX cần đúng một trường ở mỗi well ROWS, COLUMNS, VALUES.",
                    )
        elif vis.visual_type == "KPI":
            if len(by_role.get("VALUE", [])) != 1:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR, "Visual KPI cần đúng một measure ở well VALUE."
                )
        elif vis.visual_type in ("BAR", "LINE"):
            if not by_role.get("X") or not by_role.get("Y"):
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Visual {vis.visual_type} cần ít nhất một trường X và một measure Y.",
                )
        for f in vis.fields:
            if f.field_id is not None:
                field = fields_by_id.get(int(f.field_id))
                if field is None:
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Trường #{f.field_id} không thuộc phiên bản mô hình đã pin.",
                    )
                if not field.get("is_visible") or str(field.get("field_role") or "").upper() == "HIDDEN":
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Trường {field_table[int(f.field_id)]}.{field['field_code']} đã ẩn, "
                        "không dùng được trong visual.",
                    )
                if f.well_role in _MEASURE_WELLS and f.aggregation == "NONE":
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Trường {field['field_code']} ở well {f.well_role} cần chọn Aggregation.",
                    )
                if f.well_role in _DIMENSION_WELLS and f.aggregation != "NONE":
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Trường {field['field_code']} ở well {f.well_role} không dùng Aggregation.",
                    )
                if f.date_part is not None and str(field.get("data_type") or "").upper() not in (
                    "DATE",
                    "DATETIME",
                ):
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Trường {field['field_code']} không phải kiểu ngày nên không dùng Date Part.",
                    )
            else:
                measure = measures_by_id.get(int(f.measure_id or 0))
                if measure is None:
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Measure #{f.measure_id} không thuộc phiên bản mô hình đã pin.",
                    )
                if f.well_role in _DIMENSION_WELLS:
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Measure {measure['code']} không đặt được ở well {f.well_role}.",
                    )
                if f.aggregation != "NONE":
                    raise ServiceError(
                        ErrorCode.VALIDATION_ERROR,
                        f"Measure {measure['code']} đã có Aggregation riêng, không chọn thêm.",
                    )


def _insert_visuals(
    conn: Connection, version_id: int, visuals: list[StudioVisualDTO], now: datetime
) -> None:
    for vis in visuals:
        res = conn.execute(
            recon_rpt_visual.insert().values(
                VERSION_ID=version_id,
                CODE=vis.code,
                TITLE=vis.title,
                VISUAL_TYPE=vis.visual_type,
                DISPLAY_ORDER=vis.display_order,
                GRID_SPAN=vis.grid_span,
                HEIGHT_SIZE=vis.height_size,
                CONFIG_JSON=json.dumps(vis.config, ensure_ascii=False) if vis.config else None,
                CREATED_AT=now,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        vis_id = _pk_from_insert(res)
        for f in vis.fields:
            conn.execute(
                recon_rpt_visual_field.insert().values(
                    VISUAL_ID=vis_id,
                    WELL_ROLE=f.well_role,
                    FIELD_ID=f.field_id,
                    MEASURE_ID=f.measure_id,
                    AGGREGATION=f.aggregation,
                    DATE_PART=f.date_part,
                    ALIAS=f.alias,
                    LABEL_OVERRIDE=f.label_override,
                    FORMAT_MASK=f.format_mask,
                    SORT_DIRECTION=f.sort_direction,
                    DISPLAY_ORDER=f.display_order,
                )
            )


def _delete_visuals(conn: Connection, version_id: int) -> None:
    vis_ids = [
        int(r[0])
        for r in conn.execute(
            select(recon_rpt_visual.c.ID).where(recon_rpt_visual.c.VERSION_ID == version_id)
        ).all()
    ]
    if vis_ids:
        conn.execute(
            recon_rpt_visual_field.delete().where(
                recon_rpt_visual_field.c.VISUAL_ID.in_(vis_ids)
            )
        )
        conn.execute(
            recon_rpt_visual.delete().where(recon_rpt_visual.c.VERSION_ID == version_id)
        )


def _clone_visuals(conn: Connection, src_version_id: int, dst_version_id: int, now: datetime) -> None:
    for vis in _load_visuals(conn, src_version_id):
        res = conn.execute(
            recon_rpt_visual.insert().values(
                VERSION_ID=dst_version_id,
                CODE=vis["code"],
                TITLE=vis["title"],
                VISUAL_TYPE=vis["visual_type"],
                DISPLAY_ORDER=vis["display_order"],
                GRID_SPAN=vis["grid_span"],
                HEIGHT_SIZE=vis["height_size"],
                CONFIG_JSON=json.dumps(vis["config"], ensure_ascii=False) if vis["config"] else None,
                CREATED_AT=now,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        vis_id = _pk_from_insert(res)
        for f in vis["fields"]:
            conn.execute(
                recon_rpt_visual_field.insert().values(
                    VISUAL_ID=vis_id,
                    WELL_ROLE=f["well_role"],
                    FIELD_ID=f["field_id"],
                    MEASURE_ID=f["measure_id"],
                    AGGREGATION=f["aggregation"],
                    DATE_PART=f["date_part"],
                    ALIAS=f["alias"],
                    LABEL_OVERRIDE=f["label_override"],
                    FORMAT_MASK=f["format_mask"],
                    SORT_DIRECTION=f["sort_direction"],
                    DISPLAY_ORDER=f["display_order"],
                )
            )


def _clone_params(conn: Connection, src_version_id: int, dst_version_id: int) -> None:
    param_rows = (
        conn.execute(
            select(recon_rpt_param)
            .where(recon_rpt_param.c.VERSION_ID == src_version_id)
            .order_by(recon_rpt_param.c.DISPLAY_ROW, recon_rpt_param.c.DISPLAY_ORDER)
        )
        .mappings()
        .all()
    )
    for param in param_rows:
        lov = (
            conn.execute(
                select(recon_rpt_param_lov).where(
                    recon_rpt_param_lov.c.PARAM_ID == int(param["ID"])
                )
            )
            .mappings()
            .first()
        )
        res = conn.execute(
            recon_rpt_param.insert().values(
                VERSION_ID=dst_version_id,
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
        new_param_id = _pk_from_insert(res)
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


def _replace_params(
    conn: Connection,
    version_id: int,
    params_payload: list[dict[str, Any]],
    actor: str,
    now: datetime,
) -> None:
    """Thay toàn bộ params của version (kèm LOV), tái dùng validation wizard."""
    param_ids = [
        int(r[0])
        for r in conn.execute(
            select(recon_rpt_param.c.ID).where(recon_rpt_param.c.VERSION_ID == version_id)
        ).all()
    ]
    if param_ids:
        conn.execute(
            recon_rpt_param_lov.delete().where(
                recon_rpt_param_lov.c.PARAM_ID.in_(param_ids)
            )
        )
        conn.execute(
            recon_rpt_param.delete().where(recon_rpt_param.c.VERSION_ID == version_id)
        )
    seen_codes: set[str] = set()
    for raw in params_payload:
        dto = ParamCreate(**raw)
        if dto.code in seen_codes:
            raise ServiceError(
                ErrorCode.CONFLICT, f"Mã tham số {dto.code} bị trùng trong version."
            )
        seen_codes.add(dto.code)
        _validate_param(dto, conn)
        if dto.display_row is None or dto.display_order is None:
            auto_row, auto_order = _auto_place(conn, version_id, dto.grid_span)
            display_row = dto.display_row if dto.display_row is not None else auto_row
            display_order = dto.display_order if dto.display_order is not None else auto_order
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
        param_id = _pk_from_insert(res)
        _insert_lov(conn, param_id, dto.lov or LovPayload())
    write_audit_log(
        conn,
        "RECON_RPT_PARAM",
        version_id,
        "SAVE_STUDIO_PARAMS",
        actor,
        new_data={"version_id": version_id, "param_count": len(params_payload)},
        now=now,
    )
    invalidate_lov_cache_for_version(conn, version_id)


# ---------------------------------------------------------------------------
# Intent + validate từng visual
# ---------------------------------------------------------------------------


def build_visual_intent(
    visual: dict[str, Any],
    bundle: dict[str, Any],
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Chuyển một visual (dict đã lưu) thành SemanticQueryIntent.

    MATRIX chạy như TABLE ở tầng planner; pivot dựng ở server khi preview.
    """
    vtype = str(visual["visual_type"])
    dimensions: list[dict[str, Any]] = []
    measures: list[dict[str, Any]] = []
    sorts: list[dict[str, Any]] = []
    for f in visual.get("fields") or []:
        role = str(f["well_role"])
        if role in _DIMENSION_WELLS:
            dim: dict[str, Any] = {"field_id": int(f["field_id"])}
            if f.get("date_part"):
                dim["date_part"] = str(f["date_part"])
            if f.get("alias"):
                dim["alias"] = str(f["alias"])
            dimensions.append(dim)
        elif role in _MEASURE_WELLS:
            if f.get("measure_id"):
                meas: dict[str, Any] = {"measure_id": int(f["measure_id"])}
            else:
                meas = {
                    "field_id": int(f["field_id"]),
                    "aggregation": str(f["aggregation"]),
                }
            if f.get("alias"):
                meas["alias"] = str(f["alias"])
            measures.append(meas)
        if f.get("sort_direction"):
            sorts.append(
                {
                    "target_type": "MEASURE" if f.get("measure_id") else "FIELD",
                    "id": int(f.get("measure_id") or f["field_id"]),
                    "direction": str(f["sort_direction"]),
                }
            )
    return {
        "model_version_id": int(bundle["version"]["id"]),
        "dimensions": dimensions,
        "measures": measures,
        "filters": list(filters or []),
        "sorts": sorts,
        "visual_type": "TABLE" if vtype == "MATRIX" else vtype,
        "limit": 500,
        "offset": 0,
    }


_QUERY_FILTER_OPERATORS = ("=", ">=", "<=", "BETWEEN", "IN", "LIKE_PREFIX", "IS_NULL", "RELATIVE_DATE")


def build_param_filters(
    resolved: dict[str, Any],
    params: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Map tham số báo cáo đã resolve thành QueryFilter cho intent semantic.

    Param chỉ thành filter khi FILTER_COLUMN (hoặc CODE khi không có
    FILTER_COLUMN) khớp FIELD_CODE của một field đang hiển thị trong
    bundle; param không khớp bị bỏ qua — giống luồng VIEW/TABLE cũ bỏ
    param không có filter_column. BETWEEN cần giá trị {from, to};
    IN cần danh sách; sai hình dạng thì lỗi rõ ràng thay vì lọc sai lặng lẽ.
    """
    by_code: dict[str, dict[str, Any]] = {}
    for table in bundle.get("tables") or []:
        for field in table.get("fields") or []:
            if field.get("is_visible", True):
                by_code[str(field["field_code"]).upper()] = field
    out: list[dict[str, Any]] = []
    for param in params:
        code = str(param.get("code") or "")
        if code not in resolved:
            continue
        value = resolved[code]
        if value is None or value == "" or value == []:
            continue
        target = str(param.get("filter_column") or code).upper()
        field = by_code.get(target)
        if field is None:
            continue
        operator = str(param.get("filter_operator") or "=").upper()
        if operator not in _QUERY_FILTER_OPERATORS:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Toán tử lọc {operator!r} của tham số {code} không hỗ trợ cho báo cáo Studio.",
            )
        if operator == "BETWEEN":
            if not isinstance(value, dict) or value.get("from") is None or value.get("to") is None:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Tham số {code} (BETWEEN) cần đủ giá trị từ và đến.",
                )
            shaped: Any = [value["from"], value["to"]]
        elif operator == "IN":
            if not isinstance(value, list) or not value:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Tham số {code} (IN) cần danh sách giá trị không rỗng.",
                )
            shaped = list(value)
        elif operator == "IS_NULL":
            shaped = None
        else:
            shaped = value
        out.append({"field_id": int(field["id"]), "operator": operator, "value": shaped})
    return out


def _map_output_sorts(
    visual: dict[str, Any],
    bundle: dict[str, Any],
    sorts: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Map sort theo tên cột output (như Viewer gửi) thành QuerySort.

    Tên cột output của dimension = alias hoặc FIELD_CODE; của measure =
    alias hoặc CODE (measure lưu) / FIELD_CODE (adhoc). Tên lạ -> lỗi
    SQL_NOT_ALLOWED giống _validate_sorts của luồng cổ điển.
    """
    fields_by_id = {
        int(f["id"]): f for t in (bundle.get("tables") or []) for f in (t.get("fields") or [])
    }
    measures_by_id = {int(m["id"]): m for m in (bundle.get("measures") or [])}
    dim_alias: dict[str, tuple[str, str]] = {}
    meas_alias: dict[str, tuple[str, str]] = {}
    for f in visual.get("fields") or []:
        role = str(f.get("well_role") or "")
        if role in _DIMENSION_WELLS:
            fld = fields_by_id.get(int(f["field_id"]))
            if fld is None:
                continue
            name = str(f.get("alias") or fld["field_code"])
            dim_alias[name.upper()] = ("FIELD", name)
        elif role in _MEASURE_WELLS:
            if f.get("measure_id"):
                meas = measures_by_id.get(int(f["measure_id"]))
                name = str(f.get("alias") or (meas["code"] if meas else ""))
            else:
                fld = fields_by_id.get(int(f["field_id"]))
                name = str(f.get("alias") or (fld["field_code"] if fld else ""))
            if name:
                meas_alias[name.upper()] = ("MEASURE", name)
    out: list[dict[str, Any]] = []
    for item in sorts or []:
        field = str(item.get("field", "")).strip().upper()
        direction = str(item.get("direction", "ASC")).strip().upper()
        if direction not in ("ASC", "DESC"):
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                f"Hướng sort phải là ASC hoặc DESC: {direction!r}.",
            )
        if field in dim_alias:
            target_type, alias = dim_alias[field]
        elif field in meas_alias:
            target_type, alias = meas_alias[field]
        else:
            raise ServiceError(
                ErrorCode.SQL_NOT_ALLOWED,
                f"Cột sort không có trong kết quả: {field!r}.",
            )
        out.append({"target_type": target_type, "alias": alias, "direction": direction})
    return out


def build_visual_run_intent(
    conn: Connection,
    version_id: int,
    visual_id: int,
    resolved_params: dict[str, Any],
    query_spec: dict[str, Any] | None = None,
    sorts: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], int]:
    """Dựng intent cho 1 lần chạy/xuất của visual (dùng chung run + export).

    Visual đã lưu + filter trong config + tham số báo cáo đã resolve +
    filter trong query_spec của run. Sort của người dùng (theo tên cột
    output) thay thế sort mặc định của visual. Trả (intent_dict, model_version_id).
    """
    version_row = _load_studio_version(conn, version_id)
    model_version_id = int(version_row["MODEL_VERSION_ID"])
    bundle = load_version_bundle(conn, model_version_id)
    visual = load_visual_by_id(conn, visual_id)
    if int(visual["version_id"]) != int(version_id):
        raise ServiceError(
            ErrorCode.NOT_FOUND,
            f"Visual #{visual_id} không thuộc phiên bản báo cáo này.",
        )
    param_rows = (
        conn.execute(
            select(recon_rpt_param).where(recon_rpt_param.c.VERSION_ID == int(version_id))
        )
        .mappings()
        .all()
    )
    params = [
        {
            "code": str(p["CODE"]),
            "filter_column": p["FILTER_COLUMN"],
            "filter_operator": p["FILTER_OPERATOR"],
        }
        for p in param_rows
    ]
    filters = list((visual.get("config") or {}).get("filters") or [])
    filters += build_param_filters(resolved_params, params, bundle)
    filters += list((query_spec or {}).get("filters") or [])
    intent = build_visual_intent(visual, bundle, filters=filters)
    if sorts:
        intent["sorts"] = _map_output_sorts(visual, bundle, sorts)
    return intent, model_version_id


def _validate_visual_intents(
    visuals: list[dict[str, Any]], bundle: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve plan từng visual; lỗi ghi theo visual, warning gom chung."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for vis in visuals:
        try:
            intent = SemanticQueryIntent(**build_visual_intent(vis, bundle))
            resolved = resolve_semantic_plan(intent, bundle)
            for w in resolved.warnings or []:
                warnings.append({"visual_code": vis["code"], "message": str(w)})
        except ServiceError as exc:
            errors.append(
                {
                    "visual_code": vis["code"],
                    "visual_title": vis["title"],
                    "code": str(exc.code),
                    "message": exc.message,
                }
            )
        except ValidationError as exc:
            errors.append(
                {
                    "visual_code": vis["code"],
                    "visual_title": vis["title"],
                    "code": str(ErrorCode.VALIDATION_ERROR),
                    "message": f"Intent của visual {vis['code']} không hợp lệ: "
                    f"{'; '.join(e.get('msg', '') for e in exc.errors())}",
                }
            )
    return errors, warnings


def _pivot_matrix(
    rows: list[dict[str, Any]],
    row_field: str,
    col_field: str,
    value_field: str,
) -> dict[str, Any]:
    """Pivot kết quả preview thành ma trận; cắt theo giới hạn an toàn."""
    row_headers: list[Any] = []
    col_headers: list[Any] = []
    seen_rows: set[Any] = set()
    seen_cols: set[Any] = set()
    cells_map: dict[tuple[Any, Any], Any] = {}
    for r in rows:
        rk, ck = r.get(row_field), r.get(col_field)
        if rk not in seen_rows:
            seen_rows.add(rk)
            row_headers.append(rk)
        if ck not in seen_cols:
            seen_cols.add(ck)
            col_headers.append(ck)
        cells_map[(rk, ck)] = r.get(value_field)
    truncated = len(row_headers) > _MATRIX_MAX_ROWS or len(col_headers) > _MATRIX_MAX_COLS
    row_headers = row_headers[:_MATRIX_MAX_ROWS]
    col_headers = col_headers[:_MATRIX_MAX_COLS]
    cells = [
        [cells_map.get((rk, ck)) for ck in col_headers] for rk in row_headers
    ]
    return {
        "row_headers": row_headers,
        "col_headers": col_headers,
        "cells": cells,
        "truncated": truncated,
    }


# ---------------------------------------------------------------------------
# Service công khai
# ---------------------------------------------------------------------------


@service
@requires_menu("report_studio")
def list_studio_reports(ctx: Ctx) -> list[dict[str, Any]]:
    """Danh sách báo cáo Studio (một dòng/báo cáo, version mới nhất)."""
    engine = get_recon_engine()
    admin = is_admin(ctx, engine)
    with engine.connect() as conn:
        stmt = (
            select(
                recon_report,
                recon_report_template.c.ID.label("template_id"),
                recon_rpt_tpl_ver.c.ID.label("version_id"),
                recon_rpt_tpl_ver.c.VERSION_NO,
                recon_rpt_tpl_ver.c.STATUS,
                recon_rpt_tpl_ver.c.MODEL_VERSION_ID,
            )
            .join(
                recon_report_template,
                recon_report_template.c.REPORT_ID == recon_report.c.ID,
            )
            .join(
                recon_rpt_tpl_ver,
                recon_rpt_tpl_ver.c.TEMPLATE_ID == recon_report_template.c.ID,
            )
            .where(recon_rpt_tpl_ver.c.SOURCE_TYPE == "SEMANTIC_MODEL")
            .order_by(recon_report.c.CODE, recon_rpt_tpl_ver.c.VERSION_NO.desc())
        )
        if not admin:
            stmt = stmt.where(
                recon_report.c.IS_VISIBLE == "Y", recon_report.c.IS_ACTIVE == "Y"
            )
        rows = conn.execute(stmt).mappings().all()
        by_report: dict[int, dict[str, Any]] = {}
        for row in rows:
            rid = int(row["ID"])
            if rid in by_report:
                continue
            by_report[rid] = {
                "id": rid,
                "code": str(row["CODE"]),
                "name": str(row["NAME"]),
                "category_code": row["CATEGORY_CODE"],
                "owner": str(row["OWNER"]),
                "description": row["DESCRIPTION"],
                "is_visible": row["IS_VISIBLE"] == "Y",
                "is_active": row["IS_ACTIVE"] == "Y",
                "template_id": int(row["template_id"]),
                "version_id": int(row["version_id"]),
                "version_no": int(row["VERSION_NO"]),
                "version_status": str(row["STATUS"]),
                "model_version_id": int(row["MODEL_VERSION_ID"]),
            }
        if not by_report:
            return []
        model_ids = {r["model_version_id"] for r in by_report.values()}
        model_rows = (
            conn.execute(
                select(
                    recon_rpt_model_ver.c.ID,
                    recon_rpt_model.c.CODE,
                )
                .join(
                    recon_rpt_model,
                    recon_rpt_model.c.ID == recon_rpt_model_ver.c.MODEL_ID,
                )
                .where(recon_rpt_model_ver.c.ID.in_(model_ids))
            )
            .mappings()
            .all()
        )
        model_codes = {int(r["ID"]): str(r["CODE"]) for r in model_rows}
        version_ids = [r["version_id"] for r in by_report.values()]
        counts = {
            int(r[0]): int(r[1])
            for r in conn.execute(
                select(
                    recon_rpt_visual.c.VERSION_ID,
                    func.count(recon_rpt_visual.c.ID),
                )
                .where(recon_rpt_visual.c.VERSION_ID.in_(version_ids))
                .group_by(recon_rpt_visual.c.VERSION_ID)
            ).all()
        }
        out = []
        for r in by_report.values():
            r["model_code"] = model_codes.get(r["model_version_id"])
            r["visual_count"] = counts.get(r["version_id"], 0)
            out.append(r)
        return out


@service
@requires_menu("report_studio")
def create_studio_report(ctx: Ctx, payload: dict[str, Any]) -> dict[str, Any]:
    """Tạo báo cáo Studio: report + template MAIN + version 1 DRAFT.

    Model version phải ACTIVE; nếu không -> MODEL_VERSION_LOCKED.
    """
    dto = StudioReportCreateDTO(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        bundle = load_version_bundle(conn, dto.model_version_id)
        if str(bundle["version"]["status"]).upper() != "ACTIVE":
            raise ServiceError(
                ErrorCode.MODEL_VERSION_LOCKED,
                "Phiên bản mô hình chưa được phát hành (ACTIVE) nên không thể tạo báo cáo Studio.",
            )
        exists = conn.execute(
            select(recon_report.c.ID).where(recon_report.c.CODE == dto.code)
        ).first()
        if exists is not None:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã báo cáo {dto.code} đã tồn tại.")
        res = conn.execute(
            recon_report.insert().values(
                CODE=dto.code,
                NAME=dto.name,
                CATEGORY_CODE=dto.category_code,
                OWNER=ctx.username,
                DESCRIPTION=dto.description,
                DEFAULT_FAVORITE="N",
                IS_VISIBLE="Y",
                IS_ACTIVE="Y",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        report_id = _pk_from_insert(res)
        res_t = conn.execute(
            recon_report_template.insert().values(
                REPORT_ID=report_id,
                CODE="MAIN",
                NAME=dto.name,
                DISPLAY_ORDER=10,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        template_id = _pk_from_insert(res_t)
        res_v = conn.execute(
            recon_rpt_tpl_ver.insert().values(
                TEMPLATE_ID=template_id,
                VERSION_NO=1,
                STATUS="DRAFT",
                DATA_SOURCE_ID=int(bundle["model"]["data_source_id"]),
                MODEL_VERSION_ID=dto.model_version_id,
                SOURCE_TYPE="SEMANTIC_MODEL",
                SQL_TEXT=None,
                SOURCE_OWNER=None,
                SOURCE_OBJECT=None,
                TIMEOUT_SEC=300,
                PREVIEW_MAX_ROWS=100,
                EXPORT_MAX_ROWS=1000000,
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
        version_id = _pk_from_insert(res_v)
        if dto.visuals:
            _validate_visuals_against_bundle(dto.visuals, bundle)
            _insert_visuals(conn, version_id, dto.visuals, now)
        write_audit_log(
            conn,
            "RECON_REPORT",
            report_id,
            "CREATE_STUDIO_REPORT",
            ctx.username,
            new_data={"code": dto.code, "model_version_id": dto.model_version_id},
            now=now,
        )
        report_row = load_report_row(conn, report_id, admin=True)
        template_row = _load_template_of_report(conn, report_id)
        version_row = _load_studio_version(conn, version_id)
        return _draft_detail(conn, report_row, template_row, version_row)


@service
@requires_menu("report_studio")
def get_studio_draft(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Chi tiết bản nháp: version + model bundle + visuals + params."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        version_row = _load_studio_version(conn, version_id)
        template_row = (
            conn.execute(
                select(recon_report_template).where(
                    recon_report_template.c.ID == int(version_row["TEMPLATE_ID"])
                )
            )
            .mappings()
            .first()
        )
        assert template_row is not None
        report_row = load_report_row(
            conn, int(template_row["REPORT_ID"]), admin=is_admin(ctx, engine)
        )
        return _draft_detail(conn, report_row, template_row, version_row)


@service
@requires_menu("report_center")
def list_version_visuals(ctx: Ctx, version_id: int) -> list[dict[str, Any]]:
    """Danh sách visual của một version Studio đã ACTIVE (Viewer chỉ đọc).

    Viewer (/reports) cần danh sách này để chạy từng visual; không dùng
    get_studio_draft vì hàm đó yêu cầu menu report_studio (thiết kế).
    Version chưa ACTIVE thì từ chối (chưa phát hành, không xem được).
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        version_row = _load_studio_version(conn, version_id)
        if str(version_row["STATUS"]) != "ACTIVE":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ xem được visual của phiên bản báo cáo đã phát hành (ACTIVE).",
            )
        return _load_visuals(conn, version_id)


@service
@requires_menu("report_studio")
def open_or_create_studio_draft(ctx: Ctx, report_id: int) -> dict[str, Any]:
    """Mở bản nháp hiện có, hoặc clone version cao nhất sang DRAFT mới.

    Clone mang theo toàn bộ visuals + params; version mới pin cùng
    MODEL_VERSION_ID với bản gốc.
    """
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        report_row = load_report_row(conn, report_id, admin=is_admin(ctx, engine))
        template_row = _load_template_of_report(conn, report_id)
        template_id = int(template_row["ID"])
        versions = (
            conn.execute(
                select(recon_rpt_tpl_ver)
                .where(recon_rpt_tpl_ver.c.TEMPLATE_ID == template_id)
                .order_by(recon_rpt_tpl_ver.c.VERSION_NO.desc())
            )
            .mappings()
            .all()
        )
        if not versions:
            raise ServiceError(ErrorCode.NOT_FOUND, "Báo cáo chưa có phiên bản nào.")
        draft = next((v for v in versions if str(v["STATUS"]) in _EDITABLE_STATUSES), None)
        if draft is not None:
            return _draft_detail(conn, report_row, template_row, draft)
        src = versions[0]
        new_no = int(src["VERSION_NO"]) + 1
        res_v = conn.execute(
            recon_rpt_tpl_ver.insert().values(
                TEMPLATE_ID=template_id,
                VERSION_NO=new_no,
                STATUS="DRAFT",
                DATA_SOURCE_ID=src["DATA_SOURCE_ID"],
                MODEL_VERSION_ID=src["MODEL_VERSION_ID"],
                SOURCE_TYPE="SEMANTIC_MODEL",
                SQL_TEXT=None,
                SOURCE_OWNER=None,
                SOURCE_OBJECT=None,
                TIMEOUT_SEC=src["TIMEOUT_SEC"],
                PREVIEW_MAX_ROWS=src["PREVIEW_MAX_ROWS"],
                EXPORT_MAX_ROWS=src["EXPORT_MAX_ROWS"],
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
        new_vid = _pk_from_insert(res_v)
        _clone_visuals(conn, int(src["ID"]), new_vid, now)
        _clone_params(conn, int(src["ID"]), new_vid)
        write_audit_log(
            conn,
            "RECON_RPT_TPL_VER",
            new_vid,
            "CLONE_VERSION",
            ctx.username,
            new_data={
                "template_id": template_id,
                "from_version_no": int(src["VERSION_NO"]),
                "version_no": new_no,
            },
            now=now,
        )
        new_row = _load_studio_version(conn, new_vid)
        return _draft_detail(conn, report_row, template_row, new_row)


@service
@requires_menu("report_studio")
def save_studio_draft(ctx: Ctx, version_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Lưu nháp: kiểm tra ROW_VERSION, thay toàn bộ visuals (+ params).

    Lưu trên bản DRY_RUN_OK đưa về DRAFT (phải kiểm tra lại trước khi phát hành).
    """
    dto = StudioDraftSaveDTO(**payload)
    engine = get_recon_engine()
    with engine.begin() as conn:
        version_row = _load_studio_version(conn, version_id)
        if str(version_row["STATUS"]) not in _EDITABLE_STATUSES:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ lưu được bản nháp (DRAFT/DRY_RUN_OK); phiên bản đã phát hành không được sửa.",
            )
        if int(version_row["ROW_VERSION"]) != dto.row_version:
            raise ServiceError(
                ErrorCode.STALE_DATA,
                "Bản nháp đã bị thay đổi bởi người khác. Tải lại trước khi lưu.",
            )
        bundle = load_version_bundle(conn, int(version_row["MODEL_VERSION_ID"]))
        _validate_visuals_against_bundle(dto.visuals, bundle)
        now = _now()
        _delete_visuals(conn, version_id)
        _insert_visuals(conn, version_id, dto.visuals, now)
        if dto.params is not None:
            _replace_params(conn, version_id, dto.params, ctx.username, now)
        new_rv = int(version_row["ROW_VERSION"]) + 1
        conn.execute(
            recon_rpt_tpl_ver.update()
            .where(recon_rpt_tpl_ver.c.ID == version_id)
            .values(STATUS="DRAFT", UPDATED_BY=ctx.username, UPDATED_AT=now, ROW_VERSION=new_rv)
        )
        write_audit_log(
            conn,
            "RECON_RPT_TPL_VER",
            version_id,
            "SAVE_STUDIO_DRAFT",
            ctx.username,
            new_data={
                "version_no": int(version_row["VERSION_NO"]),
                "visual_count": len(dto.visuals),
            },
            now=now,
        )
        return {
            "version_id": version_id,
            "version_no": int(version_row["VERSION_NO"]),
            "status": "DRAFT",
            "row_version": new_rv,
            "visual_count": len(dto.visuals),
        }


@service
@requires_menu("report_studio")
def validate_studio_report(ctx: Ctx, version_id: int) -> dict[str, Any]:
    """Kiểm tra từng visual bằng resolve_semantic_plan trên model đã pin.

    0 lỗi -> chuyển DRAFT thành DRY_RUN_OK; có lỗi -> giữ nguyên trạng thái.
    """
    engine = get_recon_engine()
    with engine.begin() as conn:
        version_row = _load_studio_version(conn, version_id)
        if str(version_row["STATUS"]) not in _EDITABLE_STATUSES:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Chỉ kiểm tra được bản nháp (DRAFT/DRY_RUN_OK).",
            )
        bundle = load_version_bundle(conn, int(version_row["MODEL_VERSION_ID"]))
        visuals = _load_visuals(conn, version_id)
        errors, warnings = _validate_visual_intents(visuals, bundle)
        now = _now()
        status = str(version_row["STATUS"])
        new_rv = int(version_row["ROW_VERSION"])
        if not errors and status == "DRAFT":
            status = "DRY_RUN_OK"
            new_rv += 1
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == version_id)
                .values(
                    STATUS="DRY_RUN_OK",
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=new_rv,
                )
            )
        elif errors and status == "DRY_RUN_OK":
            # Bản đã kiểm tra nay lại lỗi (model/visual đổi) -> hạ về DRAFT.
            status = "DRAFT"
            new_rv += 1
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == version_id)
                .values(
                    STATUS="DRAFT",
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=new_rv,
                )
            )
        return {
            "version_id": version_id,
            "version_no": int(version_row["VERSION_NO"]),
            "status": status,
            "row_version": new_rv,
            "errors": errors,
            "warnings": warnings,
        }


@service
@requires_menu("report_studio")
def publish_studio_report(
    ctx: Ctx, version_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    """Phát hành bản nháp: re-validate, khóa, ACTIVE bản này, archive bản cũ."""
    dto = StudioPublishDTO(**payload)
    engine = get_recon_engine()
    if not _acquire_activate_lock(engine):
        raise ServiceError(
            ErrorCode.CONFLICT, "Đang có thao tác kích hoạt khác, thử lại sau."
        )
    try:
        now = _now()
        with engine.begin() as conn:
            version_row = _load_studio_version(conn, version_id)
            if str(version_row["STATUS"]) != "DRY_RUN_OK":
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    "Chỉ phát hành được bản nháp đã kiểm tra (DRY_RUN_OK). "
                    "Hãy bấm Kiểm tra trước.",
                )
            bundle = load_version_bundle(conn, int(version_row["MODEL_VERSION_ID"]))
            visuals = _load_visuals(conn, version_id)
            errors, _warnings = _validate_visual_intents(visuals, bundle)
            if errors:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Bản nháp còn {len(errors)} lỗi, không thể phát hành: "
                    f"{errors[0]['message']}",
                    details={"errors": errors},
                )
            template_id = int(version_row["TEMPLATE_ID"])
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(
                    recon_rpt_tpl_ver.c.TEMPLATE_ID == template_id,
                    recon_rpt_tpl_ver.c.STATUS == "ACTIVE",
                )
                .values(STATUS="ARCHIVED", UPDATED_BY=ctx.username, UPDATED_AT=now)
            )
            new_rv = int(version_row["ROW_VERSION"]) + 1
            conn.execute(
                recon_rpt_tpl_ver.update()
                .where(recon_rpt_tpl_ver.c.ID == version_id)
                .values(
                    STATUS="ACTIVE",
                    ACTIVATED_BY=ctx.username,
                    ACTIVATED_AT=now,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                    ROW_VERSION=new_rv,
                )
            )
            conn.execute(
                recon_report_template.update()
                .where(recon_report_template.c.ID == template_id)
                .values(
                    ACTIVE_VERSION_ID=version_id,
                    UPDATED_BY=ctx.username,
                    UPDATED_AT=now,
                )
            )
            write_audit_log(
                conn,
                "RECON_RPT_TPL_VER",
                version_id,
                "ACTIVATE_VERSION",
                ctx.username,
                new_data={
                    "version_no": int(version_row["VERSION_NO"]),
                    "change_note": dto.change_note.strip(),
                },
                now=now,
            )
            template_row = (
                conn.execute(
                    select(recon_report_template).where(
                        recon_report_template.c.ID == template_id
                    )
                )
                .mappings()
                .first()
            )
            assert template_row is not None
            report_row = load_report_row(
                conn, int(template_row["REPORT_ID"]), admin=True
            )
            version_row2 = _load_studio_version(conn, version_id)
            return _draft_detail(conn, report_row, template_row, version_row2)
    finally:
        _release_activate_lock(engine)


@service
@requires_menu("report_studio")
def clone_studio_report(
    ctx: Ctx, report_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    """Nhân bản báo cáo Studio sang mã mới (version 1 DRAFT, giữ visuals)."""
    dto = StudioCloneDTO(**payload)
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        src_report = load_report_row(conn, report_id, admin=is_admin(ctx, engine))
        template_row = _load_template_of_report(conn, report_id)
        template_id = int(template_row["ID"])
        src_versions = (
            conn.execute(
                select(recon_rpt_tpl_ver)
                .where(recon_rpt_tpl_ver.c.TEMPLATE_ID == template_id)
                .order_by(recon_rpt_tpl_ver.c.VERSION_NO.desc())
            )
            .mappings()
            .all()
        )
        if not src_versions:
            raise ServiceError(ErrorCode.NOT_FOUND, "Báo cáo chưa có phiên bản nào.")
        src_version = next(
            (v for v in src_versions if str(v["STATUS"]) == "ACTIVE"), src_versions[0]
        )
        exists = conn.execute(
            select(recon_report.c.ID).where(recon_report.c.CODE == dto.code)
        ).first()
        if exists is not None:
            raise ServiceError(ErrorCode.CONFLICT, f"Mã báo cáo {dto.code} đã tồn tại.")
        res = conn.execute(
            recon_report.insert().values(
                CODE=dto.code,
                NAME=dto.name,
                CATEGORY_CODE=src_report["CATEGORY_CODE"],
                OWNER=ctx.username,
                DESCRIPTION=src_report["DESCRIPTION"],
                DEFAULT_FAVORITE="N",
                IS_VISIBLE="Y",
                IS_ACTIVE="Y",
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        new_report_id = _pk_from_insert(res)
        res_t = conn.execute(
            recon_report_template.insert().values(
                REPORT_ID=new_report_id,
                CODE="MAIN",
                NAME=dto.name,
                DISPLAY_ORDER=10,
                CREATED_BY=ctx.username,
                CREATED_AT=now,
                UPDATED_BY=ctx.username,
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        new_template_id = _pk_from_insert(res_t)
        res_v = conn.execute(
            recon_rpt_tpl_ver.insert().values(
                TEMPLATE_ID=new_template_id,
                VERSION_NO=1,
                STATUS="DRAFT",
                DATA_SOURCE_ID=src_version["DATA_SOURCE_ID"],
                MODEL_VERSION_ID=src_version["MODEL_VERSION_ID"],
                SOURCE_TYPE="SEMANTIC_MODEL",
                SQL_TEXT=None,
                SOURCE_OWNER=None,
                SOURCE_OBJECT=None,
                TIMEOUT_SEC=src_version["TIMEOUT_SEC"],
                PREVIEW_MAX_ROWS=src_version["PREVIEW_MAX_ROWS"],
                EXPORT_MAX_ROWS=src_version["EXPORT_MAX_ROWS"],
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
        new_vid = _pk_from_insert(res_v)
        _clone_visuals(conn, int(src_version["ID"]), new_vid, now)
        _clone_params(conn, int(src_version["ID"]), new_vid)
        write_audit_log(
            conn,
            "RECON_REPORT",
            new_report_id,
            "CLONE_STUDIO_REPORT",
            ctx.username,
            new_data={"from_report_id": report_id, "code": dto.code},
            now=now,
        )
        report_row = load_report_row(conn, new_report_id, admin=True)
        new_template_row = _load_template_of_report(conn, new_report_id)
        version_row = _load_studio_version(conn, new_vid)
        return _draft_detail(conn, report_row, new_template_row, version_row)


@service
@requires_menu("report_studio")
def archive_studio_report(ctx: Ctx, report_id: int) -> dict[str, Any]:
    """Lưu trữ báo cáo Studio (ẩn khỏi danh sách, giữ dữ liệu)."""
    engine = get_recon_engine()
    now = _now()
    with engine.begin() as conn:
        report_row = load_report_row(conn, report_id, admin=is_admin(ctx, engine))
        conn.execute(
            recon_report.update()
            .where(recon_report.c.ID == report_id)
            .values(IS_ACTIVE="N", UPDATED_BY=ctx.username, UPDATED_AT=now)
        )
        write_audit_log(
            conn,
            "RECON_REPORT",
            report_id,
            "ARCHIVE_REPORT",
            ctx.username,
            new_data={"code": str(report_row["CODE"])},
            now=now,
        )
        return {"report_id": report_id, "code": str(report_row["CODE"]), "is_active": False}


@service
@requires_menu("report_studio")
def preview_studio_visual(
    ctx: Ctx,
    version_id: int,
    visual_code: str,
    payload: dict[str, Any],
    visual: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Xem trước một visual: chạy preview semantic, MATRIX pivot ở server.

    payload: {"filters": [QueryFilter...], "request_seq": int} — tùy chọn.
    visual: visual chưa lưu từ Store (designer preview trước khi Lưu nháp).
        Khi có, visual phải qua validate DTO + bundle (không tin payload
        Store), và bộ lọc trong config của visual được cộng thêm vào filters.
    """
    engine = get_recon_engine()
    with engine.connect() as conn:
        version_row = _load_studio_version(conn, version_id)
        bundle = load_version_bundle(conn, int(version_row["MODEL_VERSION_ID"]))
        if visual is not None:
            try:
                dto = StudioVisualDTO(**visual)
            except ValidationError as exc:
                raise ServiceError(
                    ErrorCode.VALIDATION_ERROR,
                    "Visual xem trước không hợp lệ.",
                    details={"errors": [str(e) for e in exc.errors()]},
                ) from exc
            if dto.code != visual_code:
                raise ServiceError(
                    ErrorCode.NOT_FOUND, f"Không tìm thấy visual {visual_code}."
                )
            _validate_visuals_against_bundle([dto], bundle)
            visual_dict = dto.model_dump()
        else:
            visuals = _load_visuals(conn, version_id)
            matches = [v for v in visuals if v["code"] == visual_code]
            if not matches:
                raise ServiceError(
                    ErrorCode.NOT_FOUND, f"Không tìm thấy visual {visual_code}."
                )
            visual_dict = matches[0]
    filters = list((visual_dict.get("config") or {}).get("filters") or []) + list(
        payload.get("filters") or []
    )
    intent = build_visual_intent(visual_dict, bundle, filters=filters)
    request_seq = payload.get("request_seq")
    preview = execute_semantic_preview(ctx, intent, request_seq=request_seq)
    if not preview.ok:
        raise ServiceError(
            preview.code or ErrorCode.INTERNAL_ERROR,
            preview.message or "Không xem trước được visual.",
            details=preview.details,
        )
    data = preview.data or {}
    out: dict[str, Any] = {
        "visual_code": visual_dict["code"],
        "visual_type": visual_dict["visual_type"],
        "columns": data.get("columns") or [],
        "rows": data.get("rows") or [],
        "row_count": int(data.get("row_count") or 0),
        "truncated": bool(data.get("truncated")),
        "warning_message": data.get("warning_message"),
        "request_seq": data.get("request_seq"),
        "elapsed_ms": data.get("elapsed_ms"),
    }
    if visual_dict["visual_type"] == "MATRIX":
        row_well = next(
            (f for f in visual_dict["fields"] if f["well_role"] == "ROWS"), None
        )
        col_well = next(
            (f for f in visual_dict["fields"] if f["well_role"] == "COLUMNS"), None
        )
        val_well = next(
            (f for f in visual_dict["fields"] if f["well_role"] == "VALUES"), None
        )
        if row_well is None or col_well is None or val_well is None:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "Visual MATRIX cần đủ 3 well ROWS, COLUMNS, VALUES.",
            )
        columns = [str(c.get("name")) for c in out["columns"]]
        row_field = columns[0]
        col_field = columns[1] if len(columns) > 1 else columns[0]
        value_field = columns[-1]
        pivot = _pivot_matrix(out["rows"], row_field, col_field, value_field)
        out["pivot"] = pivot
        out["truncated"] = bool(out["truncated"] or pivot["truncated"])
    return out
