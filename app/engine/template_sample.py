from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import xlsxwriter

from app.schemas.template_config import FieldSpec, TemplateConfig

SAMPLE_ROW_COUNT = 5


def _sanitize_sheet_name(name: str | None) -> str:
    """Tên sheet Excel tối đa 31 ký tự, các ký tự không hợp lệ được thay bằng _."""
    cleaned = "".join("_" if ch in "\\/?*[]:" else ch for ch in (name or "")).strip()
    return cleaned[:31] or "Sheet1"


def _excel_columns(config: TemplateConfig) -> list[tuple[str, FieldSpec]]:
    """Chỉ lấy các trường có nguồn Excel, theo đúng thứ tự khai báo trong template."""
    columns: list[tuple[str, FieldSpec]] = []
    for field in config.fields:
        header = field.excel or (field.excel_aliases[0] if field.excel_aliases else None)
        if header:
            columns.append((header, field))
    return columns


def _sample_value(field: FieldSpec, row_number: int) -> Any:
    """Giá trị ví dụ cho một dòng, chỉ để minh họa định dạng, không phải dữ liệu thật."""
    if field.type == "number":
        return 1000 * row_number
    if field.type == "date":
        return datetime(2026, 2, row_number)
    if field.type == "datetime":
        return datetime(2026, 2, row_number, 9, 0, 0)
    return f"Ví dụ {row_number}"


def build_template_sample_excel(config: TemplateConfig) -> bytes:
    """Sinh file Excel mẫu: header cột Excel + 5 dòng ví dụ theo kiểu trường.

    Vị trí header và dòng dữ liệu tuân theo file.header_row / file.data_start_row
    của template, để file mẫu đọc được đúng bằng cùng cấu hình đó.
    """
    columns = _excel_columns(config)
    if not columns:
        raise ValueError("Template không có cột Excel nào để tạo file mẫu")

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet(_sanitize_sheet_name(config.file.sheet))
    header_format = workbook.add_format({"bold": True})
    date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
    datetime_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm:ss"})

    header_row_idx = config.file.header_row - 1
    data_start_idx = config.file.data_start_row - 1

    for col_idx, (header, _field) in enumerate(columns):
        worksheet.write(header_row_idx, col_idx, header, header_format)
        width = max(len(header) + 2, 14)
        worksheet.set_column(col_idx, col_idx, min(width, 40))

    for offset in range(SAMPLE_ROW_COUNT):
        row_number = offset + 1
        row_idx = data_start_idx + offset
        for col_idx, (_header, field) in enumerate(columns):
            value = _sample_value(field, row_number)
            if field.type == "date":
                worksheet.write_datetime(row_idx, col_idx, value, date_format)
            elif field.type == "datetime":
                worksheet.write_datetime(row_idx, col_idx, value, datetime_format)
            else:
                worksheet.write(row_idx, col_idx, value)

    worksheet.freeze_panes(header_row_idx + 1, 0)
    workbook.close()
    return output.getvalue()
