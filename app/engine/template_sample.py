from __future__ import annotations

import io
from pathlib import Path

import xlsxwriter

from app.engine.reader import list_sheets, read_sheet
from app.schemas.template_config import FileSpec

PREVIEW_ROW_COUNT = 5


def _sanitize_sheet_name(name: str | None) -> str:
    """Tên sheet Excel tối đa 31 ký tự, các ký tự không hợp lệ được thay bằng _."""
    cleaned = "".join("_" if ch in "\\/?*[]:" else ch for ch in (name or "")).strip()
    return cleaned[:31] or "Sheet1"


def build_template_preview_excel(file_path: Path | str, file_spec: FileSpec) -> bytes:
    """Sinh file Excel từ đúng file mẫu đã tải lên của template.

    Lấy đúng header và 5 dòng dữ liệu đầu tiên như bảng "Xem trước 5 dòng"
    ở trang sửa template, giữ nguyên thứ tự cột và giá trị gốc dạng chuỗi
    (kể cả số 0 ở đầu mã), không tự sinh giá trị ví dụ.
    """
    path = Path(file_path)
    effective_spec = file_spec
    if not file_spec.sheet:
        sheets = list_sheets(path)
        if sheets:
            effective_spec = file_spec.model_copy(update={"sheet": sheets[0]})

    df, _warnings = read_sheet(path, effective_spec)
    columns = [c for c in df.columns if c != "__row_no"]
    if not columns:
        raise ValueError("File mẫu không có cột nào để tạo file tải về")

    rows = df.head(PREVIEW_ROW_COUNT).select(columns).to_dicts()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet(_sanitize_sheet_name(effective_spec.sheet))
    header_format = workbook.add_format({"bold": True})

    for col_idx, header in enumerate(columns):
        worksheet.write(0, col_idx, header, header_format)
        max_len = len(header)
        for row in rows:
            value = row.get(header)
            if value is not None:
                max_len = max(max_len, len(str(value)))
        worksheet.set_column(col_idx, col_idx, min(max(max_len + 2, 14), 40))

    for row_idx, row in enumerate(rows, start=1):
        for col_idx, header in enumerate(columns):
            value = row.get(header)
            worksheet.write(row_idx, col_idx, "" if value is None else str(value))

    worksheet.freeze_panes(1, 0)
    workbook.close()
    return output.getvalue()
