from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import polars as pl

from app.schemas.template_config import ProfileSpec


def format_key_value(val: Any) -> str:
    """Định dạng một giá trị thành phần khóa sang chuỗi chuẩn."""
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, Decimal):
        # Bỏ đuôi .00 vô nghĩa nếu là số nguyên
        if val == val.to_integral():
            return str(val.quantize(Decimal("1")))
        return str(val.normalize())
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    return str(val).strip()


def build_key(row: dict[str, Any], group_by: list[str]) -> tuple[str, str, dict[str, Any]]:
    """Tạo khóa nội bộ nối bởi ASCII 31 (\x1f), khóa hiển thị và dict giá trị."""
    formatted = [format_key_value(row.get(col)) for col in group_by]
    internal_key = "\x1f".join(formatted)
    key_text = " | ".join(formatted)
    key_dict = {col: row.get(col) for col in group_by}
    return internal_key, key_text, key_dict


def _round_decimal(val: Decimal, round_places: int) -> Decimal:
    """Làm tròn Decimal theo cơ chế ROUND_HALF_UP."""
    if round_places <= 0:
        target = Decimal("1")
    else:
        target = Decimal("10") ** (-round_places)
    return val.quantize(target, rounding=ROUND_HALF_UP)


def _to_decimal(val: Any) -> Decimal | None:
    if val is None or val == "":
        return None
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return None


def aggregate(
    df: pl.DataFrame,
    profile: ProfileSpec,
    is_db_pushdown: bool = False,
) -> pl.DataFrame:
    """Gộp dữ liệu theo Profile (Spec 04 mục 5).

    Hỗ trợ:
    - profile.aggregate = True (gộp nhiều dòng thành 1 nhóm)
    - profile.aggregate = False (giữ nguyên từng dòng, phát hiện khóa lặp gán __is_duplicate=True)
    - Xử lý is_db_pushdown khi phía DB đã GROUP BY sẵn từ Oracle.
    """
    if df.is_empty():
        # Trả DataFrame rỗng với schema chuẩn
        schema: dict[str, Any] = {
            "__key": pl.Utf8,
            "KEY_TEXT": pl.Utf8,
        }
        for g in profile.group_by:
            schema[g] = pl.Utf8
        for m in profile.measures:
            if m.agg in ("sum", "min", "max") and m.field and "AMOUNT" in m.field.upper():
                schema[m.name] = pl.Decimal(38, 4)
            elif m.agg in ("count", "count_distinct"):
                schema[m.name] = pl.Int64
            else:
                schema[m.name] = pl.Utf8
        schema["__row_nos"] = pl.List(pl.Int64)
        schema["__rows"] = pl.Int64
        schema["__is_inconsistent"] = pl.Boolean
        schema["__is_duplicate"] = pl.Boolean
        return pl.DataFrame(schema=schema)

    rows = df.to_dicts()

    # Trường hợp 1: Dữ liệu Oracle đã pushdown GROUP BY sẵn
    if is_db_pushdown:
        out_rows: list[dict[str, Any]] = []
        for r in rows:
            int_key, key_text, key_dict = build_key(r, profile.group_by)
            out_r: dict[str, Any] = {
                "__key": int_key,
                "KEY_TEXT": key_text,
                **key_dict,
            }
            is_inconsistent = False
            for m in profile.measures:
                m_val = r.get(m.name)
                # Kiểm tra cờ inconsistent từ pushdown
                dist_col = f"{m.name}__CNT_DIST"
                if dist_col in r:
                    cnt_dist = r.get(dist_col)
                    if cnt_dist is not None and int(cnt_dist) > 1:
                        is_inconsistent = True
                out_r[m.name] = m_val

            out_r["__row_nos"] = []
            out_r["__rows"] = int(r.get("LINE_CNT", 1))
            out_r["__is_inconsistent"] = is_inconsistent
            out_r["__is_duplicate"] = False
            out_rows.append(out_r)

        return pl.from_dicts(out_rows)

    # Trường hợp 2: Profile không gộp (aggregate = False)
    if not profile.aggregate:
        key_counts: dict[str, int] = {}
        for r in rows:
            int_key, _, _ = build_key(r, profile.group_by)
            key_counts[int_key] = key_counts.get(int_key, 0) + 1

        out_rows = []
        for r in rows:
            int_key, key_text, key_dict = build_key(r, profile.group_by)
            row_no = r.get("__row_no")
            single_row_nos = [int(row_no)] if isinstance(row_no, int) else []

            out_r = {
                "__key": int_key,
                "KEY_TEXT": key_text,
                **key_dict,
            }

            for m in profile.measures:
                target_field = m.field or m.name
                val = r.get(target_field)
                if m.round is not None and isinstance(val, (Decimal, int, float)):
                    d_val = _to_decimal(val)
                    if d_val is not None:
                        val = _round_decimal(d_val, m.round)
                out_r[m.name] = val

            out_r["__row_nos"] = single_row_nos
            out_r["__rows"] = 1
            out_r["__is_inconsistent"] = False
            out_r["__is_duplicate"] = key_counts[int_key] > 1
            out_rows.append(out_r)

        return pl.from_dicts(out_rows)

    # Trường hợp 3: profile.aggregate = True (nhóm theo khóa)
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        int_key, _, _ = build_key(r, profile.group_by)
        if int_key not in groups:
            groups[int_key] = []
        groups[int_key].append(r)

    out_rows = []
    for int_key, group_rows in groups.items():
        first_r = group_rows[0]
        _, key_text, key_dict = build_key(first_r, profile.group_by)

        row_nos: list[int] = []
        for gr in group_rows:
            rno = gr.get("__row_no")
            if isinstance(rno, int):
                row_nos.append(rno)
        row_nos.sort()

        out_r = {
            "__key": int_key,
            "KEY_TEXT": key_text,
            **key_dict,
        }

        is_inconsistent = False

        for m in profile.measures:
            target_field = m.field or m.name

            if m.agg == "sum":
                dec_vals: list[Decimal] = []
                for gr in group_rows:
                    dv = _to_decimal(gr.get(target_field))
                    if dv is not None:
                        dec_vals.append(dv)
                if not dec_vals:
                    sum_val = Decimal("0") if m.null_as == "zero" else Decimal("0")
                else:
                    sum_val = sum(dec_vals, Decimal("0"))
                if m.round is not None:
                    sum_val = _round_decimal(sum_val, m.round)
                out_r[m.name] = sum_val

            elif m.agg == "count":
                if m.field:
                    cnt = sum(1 for gr in group_rows if gr.get(target_field) is not None)
                else:
                    cnt = len(group_rows)
                out_r[m.name] = cnt

            elif m.agg == "count_distinct":
                unique_vals = {gr.get(target_field) for gr in group_rows if gr.get(target_field) is not None}
                out_r[m.name] = len(unique_vals)

            elif m.agg == "min":
                vals: list[Any] = [gr.get(target_field) for gr in group_rows if gr.get(target_field) is not None]
                out_r[m.name] = min(vals) if vals else None

            elif m.agg == "max":
                vals = [gr.get(target_field) for gr in group_rows if gr.get(target_field) is not None]
                out_r[m.name] = max(vals) if vals else None

            elif m.agg == "first_distinct":
                unique_list: list[Any] = []
                for gr in group_rows:
                    v = gr.get(target_field)
                    if v is not None and v not in unique_list:
                        unique_list.append(v)
                if len(unique_list) >= 2:
                    is_inconsistent = True
                    out_r[m.name] = unique_list[0]
                elif len(unique_list) == 1:
                    out_r[m.name] = unique_list[0]
                else:
                    out_r[m.name] = None

            elif m.agg == "value":
                out_r[m.name] = first_r.get(target_field)

        out_r["__row_nos"] = row_nos
        out_r["__rows"] = len(group_rows)
        out_r["__is_inconsistent"] = is_inconsistent
        out_r["__is_duplicate"] = False
        out_rows.append(out_r)

    return pl.from_dicts(out_rows)
