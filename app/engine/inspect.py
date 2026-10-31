from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.engine.reader import list_sheets, read_sheet
from app.schemas.template_config import FileSpec

_VIETNAMESE_ACCENTS_MAP = {
    "à": "a",
    "á": "a",
    "ả": "a",
    "ã": "a",
    "ạ": "a",
    "ă": "a",
    "ằ": "a",
    "ắ": "a",
    "ẳ": "a",
    "ẵ": "a",
    "ặ": "a",
    "â": "a",
    "ầ": "a",
    "ấ": "a",
    "ẩ": "a",
    "ẫ": "a",
    "ậ": "a",
    "è": "e",
    "é": "e",
    "ẻ": "e",
    "ẽ": "e",
    "ẹ": "e",
    "ê": "e",
    "ề": "e",
    "ế": "e",
    "ể": "e",
    "ễ": "e",
    "ệ": "e",
    "ì": "i",
    "í": "i",
    "ỉ": "i",
    "ĩ": "i",
    "ị": "i",
    "ò": "o",
    "ó": "o",
    "ỏ": "o",
    "õ": "o",
    "ọ": "o",
    "ô": "o",
    "ồ": "o",
    "ố": "o",
    "ổ": "o",
    "ỗ": "o",
    "ộ": "o",
    "ơ": "o",
    "ờ": "o",
    "ớ": "o",
    "ở": "o",
    "ỡ": "o",
    "ợ": "o",
    "ù": "u",
    "ú": "u",
    "ủ": "u",
    "ũ": "u",
    "ụ": "u",
    "ư": "u",
    "ừ": "u",
    "ứ": "u",
    "ử": "u",
    "ữ": "u",
    "ự": "u",
    "ỳ": "y",
    "ý": "y",
    "ỷ": "y",
    "ỹ": "y",
    "ỵ": "y",
    "đ": "d",
    "À": "A",
    "Á": "A",
    "Ả": "A",
    "Ã": "A",
    "Ạ": "A",
    "Ă": "A",
    "Ằ": "A",
    "Ắ": "A",
    "Ẳ": "A",
    "Ẵ": "A",
    "Ặ": "A",
    "Â": "A",
    "Ầ": "A",
    "Ấ": "A",
    "Ẩ": "A",
    "Ẫ": "A",
    "Ậ": "A",
    "È": "E",
    "É": "E",
    "Ẻ": "E",
    "Ẽ": "E",
    "Ẹ": "E",
    "Ê": "E",
    "Ề": "E",
    "Ế": "E",
    "Ể": "E",
    "Ễ": "E",
    "Ệ": "E",
    "Ì": "I",
    "Í": "I",
    "Ỉ": "I",
    "Ĩ": "I",
    "Ị": "I",
    "Ò": "O",
    "Ó": "O",
    "Ỏ": "O",
    "Õ": "O",
    "Ọ": "O",
    "Ô": "O",
    "Ồ": "O",
    "Ố": "O",
    "Ổ": "O",
    "Ỗ": "O",
    "Ộ": "O",
    "Ơ": "O",
    "Ờ": "O",
    "Ớ": "O",
    "Ở": "O",
    "Ỡ": "O",
    "Ợ": "O",
    "Ù": "U",
    "Ú": "U",
    "Ủ": "U",
    "Ũ": "U",
    "Ụ": "U",
    "Ư": "U",
    "Ừ": "U",
    "Ứ": "U",
    "Ử": "U",
    "Ữ": "U",
    "Ự": "U",
    "Ỳ": "Y",
    "Ý": "Y",
    "Ỷ": "Y",
    "Ỹ": "Y",
    "Ỵ": "Y",
    "Đ": "D",
}


def remove_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt khỏi chuỗi ký tự."""
    res = "".join(_VIETNAMESE_ACCENTS_MAP.get(c, c) for c in text)
    # Khử thêm các ký tự kết hợp nếu còn
    return "".join(c for c in unicodedata.normalize("NFD", res) if unicodedata.category(c) != "Mn")


def to_upper_snake(text: str) -> str:
    """Chuyển đổi tiêu đề thành tên trường chuẩn UPPER_SNAKE_CASE (tối đa 30 ký tự)."""
    unaccented = remove_accents(text)
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", unaccented).strip("_").upper()
    if not cleaned:
        return "FIELD_1"
    if cleaned[0].isdigit():
        cleaned = f"F_{cleaned}"
    # Đảm bảo tối đa 30 ký tự
    return cleaned[:30]


class ColumnInspection(BaseModel):
    name: str
    suggested_field_name: str
    suggested_type: Literal["text", "number", "date", "datetime"]
    sample_values: list[str]
    has_leading_zero: bool
    has_mixed_types: bool
    is_date: bool
    unique_count: int
    total_non_null: int
    unique_ratio: float
    is_candidate_key: bool


class CandidateTotalRow(BaseModel):
    row_no: int
    label_col: str
    label_val: str
    values: dict[str, str]


class FileInspectionResult(BaseModel):
    sheet: str
    sheets: list[str]
    total_rows: int
    total_cols: int
    candidate_total_rows: list[CandidateTotalRow]
    columns: list[ColumnInspection]


_DATE_REGEX = re.compile(
    r"^\s*(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}(\s+\d{1,2}:\d{2}(:\d{2})?)?|\d{4}-\d{2}-\d{2}[T ]\d{1,2}:\d{2}(:\d{2})?)\s*$"
)
_TOTAL_KEYWORD_REGEX = re.compile(r"(t[oổ]ng|total|grand\s*total|sum)", re.IGNORECASE)


def _is_number_like(s: str) -> bool:
    s_clean = s.replace(",", "").replace(".", "").replace(" ", "").replace("-", "")
    return s_clean.isdigit()


def _is_date_like(s: str) -> tuple[bool, bool]:
    """Kiểm tra có phải ngày tháng không, trả về (is_date, is_datetime)."""
    s_str = s.strip()
    if _DATE_REGEX.match(s_str):
        has_time = ":" in s_str
        return True, has_time
    # Kiểm tra serial date
    try:
        f = float(s_str)
        if 20000 <= f <= 75000:
            has_time = (f % 1) > 0
            return True, has_time
    except Exception:
        pass
    return False, False


def inspect_sample(file_path: Path | str, sheet_name: str | None = None) -> FileInspectionResult:
    """Phân tích cấu trúc file Excel/CSV để gợi ý cấu hình trong Wizard."""
    path = Path(file_path)
    sheets = list_sheets(path)
    selected_sheet = sheet_name or (sheets[0] if sheets else "Sheet1")

    spec = FileSpec(sheet=selected_sheet, header_row=1, data_start_row=2)
    raw_df, _ = read_sheet(path, spec)

    total_rows = len(raw_df)
    cols = [c for c in raw_df.columns if c != "__row_no"]
    total_cols = len(cols)

    # 1. Tìm các dòng tổng ứng viên (thường ở cuối file)
    candidate_total_rows: list[CandidateTotalRow] = []
    rows_dicts = raw_df.to_dicts()

    for r in reversed(rows_dicts[-15:]):  # Quét 15 dòng cuối
        for c in cols:
            val_str = str(r.get(c) or "").strip()
            if _TOTAL_KEYWORD_REGEX.search(remove_accents(val_str)):
                # Tìm thấy từ khóa tổng
                row_no = int(r.get("__row_no") or 0)
                values: dict[str, str] = {}
                for other_col in cols:
                    if other_col != c:
                        other_val = str(r.get(other_col) or "").strip()
                        if other_val and other_val.lower() != "none":
                            values[other_col] = other_val
                candidate_total_rows.append(
                    CandidateTotalRow(
                        row_no=row_no,
                        label_col=c,
                        label_val=val_str,
                        values=values,
                    )
                )
                break

    # 2. Phân tích từng cột
    column_inspections: list[ColumnInspection] = []
    # Lấy các dòng dữ liệu thông thường (bỏ qua dòng tổng ứng viên nếu có)
    total_row_nos = {tr.row_no for tr in candidate_total_rows}
    data_rows = [r for r in rows_dicts if int(r.get("__row_no") or 0) not in total_row_nos]

    for col in cols:
        suggested_name = to_upper_snake(col)

        raw_values = [str(r.get(col) or "").strip() for r in data_rows]
        non_null_values = [v for v in raw_values if v and v.lower() != "none"]

        total_non_null = len(non_null_values)
        unique_vals = set(non_null_values)
        unique_count = len(unique_vals)
        unique_ratio = (unique_count / total_non_null) if total_non_null > 0 else 0.0

        sample_values = non_null_values[:5]

        # Đếm số lượng dạng số, ngày, chữ
        num_count = 0
        date_count = 0
        datetime_count = 0
        text_count = 0

        for v in non_null_values:
            is_dt, is_time = _is_date_like(v)
            if is_dt:
                date_count += 1
                if is_time:
                    datetime_count += 1
            elif _is_number_like(v):
                num_count += 1
            else:
                text_count += 1

        is_date = (date_count / total_non_null) >= 0.7 if total_non_null > 0 else False

        # Kiểm tra số 0 ở đầu (e.g. "0334", "0123", loại trừ ngày tháng có chứa '/' hoặc ':')
        has_leading_zero = False
        if not is_date:
            for v in non_null_values:
                if any(sep in v for sep in ["/", ":"]):
                    continue
                if len(v) > 1 and v.startswith("0") and v[1].isdigit() and not v.startswith("0."):
                    has_leading_zero = True
                    break

        has_mixed_types = (num_count > 0 and text_count > 0) or (date_count > 0 and text_count > 0)

        # Xác định suggested_type
        suggested_type: Literal["text", "number", "date", "datetime"]
        if is_date:
            suggested_type = "datetime" if datetime_count > 0 else "date"
        elif has_leading_zero or has_mixed_types:
            suggested_type = "text"
        elif total_non_null > 0 and (num_count / total_non_null) >= 0.8:
            suggested_type = "number"
        else:
            suggested_type = "text"

        # Ứng viên làm khóa chính: tỷ lệ duy nhất cao hoặc có từ khóa định danh
        is_candidate_key = False
        if total_non_null >= 5:
            col_lower = col.lower()
            has_id_keyword = any(k in col_lower for k in ["hóa đơn", "hoa don", "mã", "ma", "id", "code", "no", "key"])
            if has_id_keyword and unique_ratio >= 0.8:
                is_candidate_key = True
            elif unique_ratio >= 0.99 and suggested_type in ("text", "number"):
                is_candidate_key = True

        column_inspections.append(
            ColumnInspection(
                name=col,
                suggested_field_name=suggested_name,
                suggested_type=suggested_type,
                sample_values=sample_values,
                has_leading_zero=has_leading_zero,
                has_mixed_types=has_mixed_types,
                is_date=is_date,
                unique_count=unique_count,
                total_non_null=total_non_null,
                unique_ratio=round(unique_ratio, 4),
                is_candidate_key=is_candidate_key,
            )
        )

    return FileInspectionResult(
        sheet=selected_sheet,
        sheets=sheets,
        total_rows=total_rows,
        total_cols=total_cols,
        candidate_total_rows=candidate_total_rows,
        columns=column_inspections,
    )
