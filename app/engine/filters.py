from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any

import polars as pl
from pydantic import BaseModel, ConfigDict

from app.schemas.template_config import RowFilter, RowFilters, TimeFilterSpec


class TimeFilterResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    df: pl.DataFrame
    out_of_range_count: int
    out_of_range_row_nos: list[int]


def _match_row_filter(row: dict[str, Any], flt: RowFilter, col_map: dict[str, str]) -> bool:
    target_key = flt.field or flt.excel_col or ""
    norm_key = unicodedata.normalize("NFC", target_key).strip().lower()
    actual_col = col_map.get(norm_key)

    val = row.get(actual_col) if actual_col else None

    # Check is_null / not_null
    is_null_val = val is None or str(val).strip() == "" or str(val).strip().lower() == "none"

    if flt.op == "is_null":
        return is_null_val
    if flt.op == "not_null":
        return not is_null_val

    if is_null_val:
        return False

    val_str = str(val).strip()

    if flt.op == "equals":
        return val_str == str(flt.value).strip()
    if flt.op == "not_equals":
        return val_str != str(flt.value).strip()
    if flt.op == "in":
        candidates = [str(x).strip() for x in (flt.value if isinstance(flt.value, list) else [flt.value])]
        return val_str in candidates
    if flt.op == "regex":
        return bool(re.search(str(flt.value), val_str))

    return False


def apply_row_filters(df: pl.DataFrame, row_filters: RowFilters) -> pl.DataFrame:
    """Áp dụng các bộ lọc dòng (drop_if và keep_if) trên DataFrame."""
    if df.is_empty():
        return df

    if not row_filters.drop_if and not row_filters.keep_if:
        return df

    # Tạo map tên cột chuẩn hóa -> tên cột thật
    col_map = {unicodedata.normalize("NFC", col).strip().lower(): col for col in df.columns}

    rows = df.to_dicts()
    kept_rows: list[dict[str, Any]] = []

    for r in rows:
        # Kiểm tra drop_if: nếu thỏa mãn bất kỳ điều kiện nào thì bỏ dòng
        should_drop = False
        for flt in row_filters.drop_if:
            if _match_row_filter(r, flt, col_map):
                should_drop = True
                break
        if should_drop:
            continue

        # Kiểm tra keep_if: nếu có keep_if thì mọi điều kiện đều phải thỏa mãn
        should_keep = True
        for flt in row_filters.keep_if:
            if not _match_row_filter(r, flt, col_map):
                should_keep = False
                break
        if not should_keep:
            continue

        kept_rows.append(r)

    if not kept_rows:
        return pl.DataFrame(schema=df.schema)

    return pl.from_dicts(kept_rows, schema=df.schema)


def apply_time_filter(
    df: pl.DataFrame,
    time_filter: TimeFilterSpec | None,
    p_from: datetime,
    p_to: datetime,
) -> TimeFilterResult:
    """Lọc dữ liệu theo khoảng thời gian p_from và p_to (giờ Việt Nam, gồm cả 2 đầu)."""
    if df.is_empty() or time_filter is None or not time_filter.excel_field:
        return TimeFilterResult(df=df, out_of_range_count=0, out_of_range_row_nos=[])

    target_field = time_filter.excel_field
    if target_field not in df.columns:
        # Thử tìm theo Unicode NFC
        norm_target = unicodedata.normalize("NFC", target_field).strip().lower()
        found = False
        for col in df.columns:
            if unicodedata.normalize("NFC", col).strip().lower() == norm_target:
                target_field = col
                found = True
                break
        if not found:
            return TimeFilterResult(df=df, out_of_range_count=0, out_of_range_row_nos=[])

    # Thiết lập mốc thời gian từ - đến
    if time_filter.granularity == "date":
        from_dt = datetime(p_from.year, p_from.month, p_from.day, 0, 0, 0)
        to_dt = datetime(p_to.year, p_to.month, p_to.day, 23, 59, 59, 999999)
    else:
        from_dt = p_from
        to_dt = p_to

    rows = df.to_dicts()
    in_range_rows: list[dict[str, Any]] = []
    out_of_range_row_nos: list[int] = []

    for r in rows:
        val = r.get(target_field)
        row_dt: datetime | None = None
        if isinstance(val, datetime):
            row_dt = val
        elif isinstance(val, date):
            row_dt = datetime(val.year, val.month, val.day)
        elif isinstance(val, str) and val.strip():
            try:
                row_dt = datetime.fromisoformat(val.strip())
            except Exception:
                pass

        if row_dt is not None and from_dt <= row_dt <= to_dt:
            in_range_rows.append(r)
        else:
            row_no = r.get("__row_no")
            if isinstance(row_no, int) and len(out_of_range_row_nos) < 1000:
                out_of_range_row_nos.append(row_no)

    out_of_range_count = len(rows) - len(in_range_rows)

    if not in_range_rows:
        filtered_df = pl.DataFrame(schema=df.schema)
    else:
        filtered_df = pl.from_dicts(in_range_rows, schema=df.schema)

    return TimeFilterResult(
        df=filtered_df,
        out_of_range_count=out_of_range_count,
        out_of_range_row_nos=out_of_range_row_nos,
    )
