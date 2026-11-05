from __future__ import annotations

from typing import Any

from app.core.context import Ctx
from app.engine.catalog import list_columns, list_tables
from app.schemas.errors import ErrorCode
from app.schemas.template_config import TemplateConfig
from app.services import service
from app.services.perm import requires_menu


@service
@requires_menu("template")
def validate_template_connected(
    ctx: Ctx,
    config: TemplateConfig,
    data_source_id: int | None,
) -> dict[str, Any]:
    """Xác thực cấu hình template với catalog CSDL thực tế.

    Kiểm tra bảng tồn tại, các cột DB được tham chiếu có trong bảng,
    và cột dùng cho p_from/p_to có kiểu DATE/TIMESTAMP.
    Nếu không kết nối được CSDL, trả cảnh báo (warning) chứ không chặn việc lưu nháp.
    """

    if not data_source_id:
        return {
            "is_valid": True,
            "errors": [],
            "warnings": ["Chưa cấu hình Data Source, bỏ qua kiểm tra CSDL"],
        }

    if config.db_source.kind != "table" or not config.db_source.table:
        return {
            "is_valid": True,
            "errors": [],
            "warnings": [],
        }

    table_full = config.db_source.table.strip()
    if "." in table_full:
        schema_part, table_part = table_full.split(".", 1)
        schema = schema_part.strip().upper()
        table_name = table_part.strip().upper()
    else:
        schema = ""
        table_name = table_full.strip().upper()

    try:
        tables_list = list_tables(data_source_id, schema=schema)
        table_names = [t["name"].upper() for t in tables_list]
    except Exception as exc:
        return {
            "is_valid": True,
            "errors": [],
            "warnings": [f"Không thể kết nối tới Data Source: {exc}. Cảnh báo: Cấu hình chưa được xác thực với CSDL."],
        }

    if table_name not in table_names:
        return {
            "is_valid": False,
            "errors": [
                {
                    "path": "db_source.table",
                    "code": ErrorCode.TABLE_NOT_FOUND,
                    "message": f"Bảng/view '{table_full}' không tồn tại trong Data Source đã chọn",
                }
            ],
            "warnings": [],
        }

    try:
        cols_list = list_columns(data_source_id, schema=schema, table_name=table_name)
        columns_map = {c["name"].upper(): c for c in cols_list}
    except Exception as exc:
        return {
            "is_valid": True,
            "errors": [],
            "warnings": [
                f"Không thể đọc danh sách cột của bảng '{table_name}': {exc}. Cảnh báo: Chưa xác thực được cột."
            ],
        }

    errors: list[dict[str, Any]] = []
    warnings: list[str] = []

    # 1. Kiểm tra các cột trong fields[].db
    for idx, f in enumerate(config.fields):
        if f.db:
            col_upper = f.db.strip().upper()
            if col_upper not in columns_map:
                errors.append(
                    {
                        "path": f"fields[{idx}].db",
                        "code": ErrorCode.COLUMN_NOT_FOUND,
                        "message": f"Cột DB '{f.db}' của trường '{f.name}' không tồn tại trong bảng '{table_name}'",
                    }
                )

    # 2. Kiểm tra các cột trong db_source.filters
    for idx, flt in enumerate(config.db_source.filters):
        col_upper = flt.column.strip().upper()
        if col_upper not in columns_map:
            errors.append(
                {
                    "path": f"db_source.filters[{idx}].column",
                    "code": ErrorCode.COLUMN_NOT_FOUND,
                    "message": f"Cột lọc '{flt.column}' không tồn tại trong bảng '{table_name}'",
                }
            )
        else:
            if flt.param in ("p_from", "p_to"):
                col_type = str(columns_map[col_upper].get("data_type", "")).upper()
                if not any(t in col_type for t in ("DATE", "TIME", "TIMESTAMP")):
                    errors.append(
                        {
                            "path": f"db_source.filters[{idx}].column",
                            "code": ErrorCode.TEMPLATE_INVALID,
                            "message": f"Cột '{flt.column}' dùng cho mốc thời gian '{flt.param}' phải có kiểu DATE hoặc TIMESTAMP (hiện là {col_type})",
                        }
                    )

    # 3. Kiểm tra các cột trong db_source.static_where
    for idx, sw in enumerate(config.db_source.static_where):
        col_upper = sw.column.strip().upper()
        if col_upper not in columns_map:
            errors.append(
                {
                    "path": f"db_source.static_where[{idx}].column",
                    "code": ErrorCode.COLUMN_NOT_FOUND,
                    "message": f"Cột lọc cố định '{sw.column}' không tồn tại trong bảng '{table_name}'",
                }
            )

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
