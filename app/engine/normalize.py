from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import polars as pl

from app.schemas.template_config import DerivedSpec, FieldSpec

EXCEL_DATE_EPOCH = datetime(1899, 12, 30)


def _to_python_strftime(fmt: str) -> str:
    """Chuyển đổi chuỗi định dạng (dd/MM/yyyy HH:mm:ss...) sang cú pháp strptime Python."""
    res = fmt
    res = res.replace("yyyy", "%Y")
    res = res.replace("yy", "%y")
    res = res.replace("MM", "%m")
    res = res.replace("dd", "%d")
    res = res.replace("HH", "%H")
    res = res.replace("mm", "%M")
    res = res.replace("ss", "%S")
    return res


def _apply_norm_ops(val: str, norm_list: list[str | dict[str, Any]]) -> str:
    """Áp dụng các thao tác chuẩn hóa chuỗi (trim, upper, lower, value_map, lpad, strip_chars)."""
    curr = val
    for op in norm_list:
        if isinstance(op, str):
            if op == "trim":
                curr = curr.strip()
            elif op == "upper":
                curr = curr.upper()
            elif op == "lower":
                curr = curr.lower()
        elif isinstance(op, dict):
            if "value_map" in op and isinstance(op["value_map"], dict):
                vmap = op["value_map"]
                if curr in vmap:
                    curr = str(vmap[curr])
            elif "lpad" in op and isinstance(op["lpad"], (list, tuple)) and len(op["lpad"]) >= 2:
                pad_len = int(op["lpad"][0])
                pad_char = str(op["lpad"][1])
                curr = curr.rjust(pad_len, pad_char)
            elif "strip_chars" in op:
                chars = str(op["strip_chars"])
                curr = curr.strip(chars)
    return curr


def normalize_value(
    raw_val: Any,
    field: FieldSpec,
    thousand_sep: str = ",",
    decimal_sep: str = ".",
) -> tuple[Any, str | None]:
    """Chuẩn hóa một giá trị ô đơn lẻ theo cấu hình FieldSpec.

    Trả về (giá trị đã chuẩn hóa, mã lỗi nếu có).
    Mã lỗi: 'MISSING_REQUIRED', 'PARSE_NUMBER', 'PARSE_DATE'.
    """
    if raw_val is None or str(raw_val).strip() == "":
        if field.required:
            return None, "MISSING_REQUIRED"
        return None, None

    str_val = str(raw_val).strip()

    # 1. Áp dụng norm operations trước (nếu có)
    if field.norm:
        str_val = _apply_norm_ops(str_val, field.norm)

    # 2. Xử lý theo kiểu dữ liệu
    if field.type == "text":
        return str_val, None

    elif field.type == "number":
        try:
            # Loại bỏ ký tự phân cách nghìn và chuẩn hóa phân cách thập phân
            clean_str = str_val.replace(thousand_sep, "").replace(decimal_sep, ".").strip()
            num = Decimal(clean_str)

            # Kiểm tra multiply trong norm nếu có
            for op in field.norm:
                if isinstance(op, dict) and "multiply" in op:
                    mult = Decimal(str(op["multiply"]))
                    num = num * mult

            return num, None
        except Exception:
            return None, "PARSE_NUMBER"

    elif field.type in ("date", "datetime"):
        # A. Thử parse Excel serial date nếu là chuỗi số
        try:
            serial_num = float(str_val)
            dt = EXCEL_DATE_EPOCH + timedelta(days=serial_num)
            return (dt.date() if field.type == "date" else dt), None
        except (ValueError, OverflowError):
            pass

        # B. Thử parse theo field.format
        if field.format:
            py_fmt = _to_python_strftime(field.format)
            try:
                dt = datetime.strptime(str_val, py_fmt)
                return (dt.date() if field.type == "date" else dt), None
            except ValueError:
                pass

        # C. Thử parse ISO format
        try:
            dt = datetime.fromisoformat(str_val)
            return (dt.date() if field.type == "date" else dt), None
        except ValueError:
            pass

        # D. Thử các định dạng phổ biến
        fallback_formats = [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y",
        ]
        for fb_fmt in fallback_formats:
            try:
                dt = datetime.strptime(str_val, fb_fmt)
                return (dt.date() if field.type == "date" else dt), None
            except ValueError:
                continue

        return None, "PARSE_DATE"

    return str_val, None


def normalize(
    df: pl.DataFrame,
    fields: list[FieldSpec],
    side: str = "excel",
    thousand_sep: str = ",",
    decimal_sep: str = ".",
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Chuẩn hóa dữ liệu toàn bộ DataFrame theo danh sách FieldSpec.

    Tách riêng thành hai DataFrame:
    - valid_df: các dòng hợp lệ với kiểu dữ liệu chuẩn (Decimal, datetime/date, text)
    - invalid_df: các dòng lỗi gồm (__row_no, __raw_data, __invalid_reasons)
    """
    field_map = {f.name: f for f in fields if f.name in df.columns}
    cols_to_process = [f.name for f in fields if f.name in df.columns]

    valid_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []

    # Duyệt từng dòng bằng iter_rows(named=True)
    for row in df.iter_rows(named=True):
        row_no = row.get("__row_no", 0)
        row_valid = True
        norm_row: dict[str, Any] = {"__row_no": row_no}
        reasons: dict[str, str] = {}

        for col_name in cols_to_process:
            f = field_map[col_name]
            raw_val = row.get(col_name)
            val, err = normalize_value(raw_val, f, thousand_sep, decimal_sep)
            if err is not None:
                row_valid = False
                reasons[col_name] = err
            else:
                norm_row[col_name] = val

        if row_valid:
            # Giữ lại các cột khác nếu có trong df
            for k, v in row.items():
                if k not in norm_row:
                    norm_row[k] = v
            valid_records.append(norm_row)
        else:
            invalid_records.append(
                {
                    "__row_no": row_no,
                    "__raw_data": row,
                    "__invalid_reasons": reasons,
                }
            )

    valid_df = pl.DataFrame(valid_records, strict=False) if valid_records else pl.DataFrame()
    invalid_df = (
        pl.DataFrame(invalid_records)
        if invalid_records
        else pl.DataFrame(schema={"__row_no": pl.Int64, "__raw_data": pl.Object, "__invalid_reasons": pl.Object})
    )

    return valid_df, invalid_df


def derive(
    df: pl.DataFrame,
    derived: list[DerivedSpec],
) -> pl.DataFrame:
    """Tính toán các trường phái sinh theo cấu hình DerivedSpec (trunc_day, trunc_month, concat, substr, coalesce)."""
    if df.is_empty() or not derived:
        return df

    curr_df = df
    for d in derived:
        fn = d.expr.fn
        args = d.expr.args

        if fn == "trunc_day":
            source_col = args[0]
            if source_col in curr_df.columns:
                series = curr_df[source_col]
                # Nếu là datetime -> cắt lấy date
                date_vals = [(v.date() if isinstance(v, datetime) else v) if v is not None else None for v in series]
                curr_df = curr_df.with_columns(pl.Series(d.name, date_vals))

        elif fn == "trunc_month":
            source_col = args[0]
            if source_col in curr_df.columns:
                series = curr_df[source_col]
                month_vals = [(date(v.year, v.month, 1) if isinstance(v, (datetime, date)) else None) for v in series]
                curr_df = curr_df.with_columns(pl.Series(d.name, month_vals))

        elif fn == "concat":
            # Nối các tham số (chuỗi hoặc cột)
            concat_vals: list[str] = []
            for row in curr_df.iter_rows(named=True):
                parts = []
                for a in args:
                    if str(a) in row:
                        val = row[str(a)]
                        parts.append(str(val) if val is not None else "")
                    else:
                        parts.append(str(a))
                concat_vals.append("".join(parts))
            curr_df = curr_df.with_columns(pl.Series(d.name, concat_vals))

        elif fn == "substr":
            source_col = args[0]
            start_pos = int(args[1])  # 1-based index
            length = int(args[2]) if len(args) > 2 else None
            if source_col in curr_df.columns:
                substr_vals: list[str | None] = []
                for v in curr_df[source_col]:
                    if v is None:
                        substr_vals.append(None)
                    else:
                        s = str(v)
                        start_idx = max(0, start_pos - 1)
                        sub = s[start_idx : start_idx + length] if length else s[start_idx:]
                        substr_vals.append(sub)
                curr_df = curr_df.with_columns(pl.Series(d.name, substr_vals))

        elif fn == "coalesce":
            coalesce_vals: list[Any] = []
            for row in curr_df.iter_rows(named=True):
                found_val = None
                for a in args:
                    if str(a) in row and row[str(a)] is not None:
                        found_val = row[str(a)]
                        break
                    elif str(a) not in row:
                        found_val = a
                        break
                coalesce_vals.append(found_val)
            curr_df = curr_df.with_columns(pl.Series(d.name, coalesce_vals))

    return curr_df
