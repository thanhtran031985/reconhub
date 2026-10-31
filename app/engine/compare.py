from __future__ import annotations

import hashlib
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import polars as pl

from app.schemas.template_config import MeasureSpec, ProfileSpec

STATUS_PRIORITY = {
    "INVALID": 1,
    "DUPLICATE": 2,
    "INCONSISTENT": 3,
    "MISSING_IN_DB": 4,
    "MISSING_IN_EXCEL": 5,
    "MISMATCH": 6,
    "MATCHED": 7,
}


def _round_decimal(val: Decimal, round_places: int) -> Decimal:
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


def _is_number(val: Any) -> bool:
    return isinstance(val, (Decimal, int, float)) and not isinstance(val, bool)


def _evaluate_measure(
    m: MeasureSpec,
    x_raw: Any,
    d_raw: Any,
) -> tuple[bool, Any, Any, Any]:
    """So sánh một measure giữa 2 phía.

    Trả về: (passes, x_val, d_val, diff)
    """
    x_val = x_raw
    d_val = d_raw

    # Áp dụng null_as
    if m.null_as == "zero":
        if x_val is None:
            x_val = Decimal("0")
        if d_val is None:
            d_val = Decimal("0")
    elif m.null_as == "empty":
        if x_val is None:
            x_val = ""
        if d_val is None:
            d_val = ""

    # Tính độ lệch (diff = x - d) nếu có ít nhất một phía là số
    diff: Any = None
    x_dec = _to_decimal(x_val)
    d_dec = _to_decimal(d_val)

    if x_dec is not None and d_dec is not None:
        diff = x_dec - d_dec
    elif x_dec is not None and d_val is None:
        diff = x_dec
    elif d_dec is not None and x_val is None:
        diff = -d_dec

    # Nếu measure là display_only thì luôn pass
    if m.compare == "display_only":
        return True, x_val, d_val, diff

    # Nếu cả hai phía đều rỗng/None -> pass
    if x_val is None and d_val is None:
        return True, x_val, d_val, diff

    # Nếu một phía rỗng và một phía có giá trị -> fail
    if x_val is None or d_val is None:
        return False, x_val, d_val, diff

    # Nếu cả hai là số
    if x_dec is not None and d_dec is not None:
        if m.round is not None:
            x_dec = _round_decimal(x_dec, m.round)
            d_dec = _round_decimal(d_dec, m.round)
        abs_diff = abs(x_dec - d_dec)

        if m.compare == "exact":
            passes = abs_diff == Decimal("0")
        elif m.compare == "abs_tol":
            tol = Decimal(str(m.tolerance or 0))
            passes = abs_diff <= tol
        elif m.compare == "pct_tol":
            tol_pct = Decimal(str(m.tolerance or 0))
            max_val = max(abs(x_dec), abs(d_dec))
            if max_val == Decimal("0"):
                passes = True
            else:
                passes = abs_diff <= (tol_pct / Decimal("100")) * max_val
        else:
            passes = abs_diff == Decimal("0")

        return passes, x_val, d_val, diff

    # Nếu là chuỗi
    if isinstance(x_val, str) and isinstance(d_val, str):
        if m.ignore_case:
            passes = x_val.strip().upper() == d_val.strip().upper()
        else:
            passes = x_val.strip() == d_val.strip()
        return passes, x_val, d_val, diff

    # Các kiểu khác (ngày, v.v.)
    passes = x_val == d_val
    return passes, x_val, d_val, diff


def compare(
    excel_agg: pl.DataFrame,
    db_agg: pl.DataFrame,
    profile: ProfileSpec,
) -> pl.DataFrame:
    """Ghép Full Outer Join theo __key và so sánh measures theo Spec 04 mục 6–7.

    Phân loại 7 trạng thái chuẩn:
    MATCHED, MISMATCH, MISSING_IN_DB, MISSING_IN_EXCEL, INCONSISTENT, DUPLICATE, INVALID.
    """
    excel_rows = excel_agg.to_dicts() if not excel_agg.is_empty() else []
    db_rows = db_agg.to_dicts() if not db_agg.is_empty() else []

    excel_by_key: dict[str, list[dict[str, Any]]] = {}
    for r in excel_rows:
        k = str(r["__key"])
        if k not in excel_by_key:
            excel_by_key[k] = []
        excel_by_key[k].append(r)

    db_by_key: dict[str, list[dict[str, Any]]] = {}
    for r in db_rows:
        k = str(r["__key"])
        if k not in db_by_key:
            db_by_key[k] = []
        db_by_key[k].append(r)

    all_keys = list(dict.fromkeys(list(excel_by_key.keys()) + list(db_by_key.keys())))

    result_rows: list[dict[str, Any]] = []

    for k in all_keys:
        x_list = excel_by_key.get(k, [])
        d_list = db_by_key.get(k, [])

        # Kiểm tra trùng lặp (DUPLICATE) khi aggregate = False hoặc có cờ lặp
        has_dup = (
            len(x_list) > 1
            or len(d_list) > 1
            or any(xr.get("__is_duplicate") for xr in x_list)
            or any(dr.get("__is_duplicate") for dr in d_list)
        )

        # Số dòng cặp cần sinh
        max_len = max(len(x_list), len(d_list))
        for idx in range(max_len):
            xr = x_list[idx] if idx < len(x_list) else None
            dr = d_list[idx] if idx < len(d_list) else None

            # Xác định các giá trị cơ bản
            primary_r = xr if xr is not None else dr
            assert primary_r is not None
            key_text = primary_r["KEY_TEXT"]
            key_hash = hashlib.sha256(k.encode("utf-8")).hexdigest()

            row_out: dict[str, Any] = {
                "KEY_TEXT": key_text,
                "KEY_HASH": key_hash,
                "__key": k,
            }

            # Group by columns
            for g in profile.group_by:
                row_out[g] = primary_r.get(g)

            # Excel row nos
            row_out["__row_nos"] = xr.get("__row_nos", []) if xr is not None else []

            # Measures so sánh
            all_measures_pass = True
            diff_dict: dict[str, Any] = {}

            for m in profile.measures:
                x_m_val = xr.get(m.name) if xr is not None else None
                d_m_val = dr.get(m.name) if dr is not None else None

                passes, x_val, d_val, diff = _evaluate_measure(m, x_m_val, d_m_val)
                row_out[f"x__{m.name}"] = x_val
                row_out[f"d__{m.name}"] = d_val
                row_out[f"diff__{m.name}"] = diff
                diff_dict[m.name] = diff

                if not passes:
                    all_measures_pass = False

            # Phân loại trạng thái (State classification theo thứ tự ưu tiên)
            is_inc = (xr is not None and xr.get("__is_inconsistent")) or (
                dr is not None and dr.get("__is_inconsistent")
            )

            if has_dup:
                status = "DUPLICATE"
            elif is_inc:
                status = "INCONSISTENT"
            elif xr is not None and dr is None:
                status = "MISSING_IN_DB"
            elif xr is None and dr is not None:
                status = "MISSING_IN_EXCEL"
            elif not all_measures_pass:
                status = "MISMATCH"
            else:
                status = "MATCHED"

            row_out["STATUS"] = status

            # ABS_DIFF_MAIN cho main_measure
            abs_diff_main: Decimal | None = None
            abs_diff_sort: float = 0.0

            if profile.main_measure and profile.main_measure in diff_dict:
                m_diff = diff_dict[profile.main_measure]
                if isinstance(m_diff, Decimal):
                    abs_diff_main = abs(m_diff)
                    abs_diff_sort = float(abs_diff_main)

            row_out["ABS_DIFF_MAIN"] = abs_diff_main
            row_out["ABS_DIFF_SORT"] = abs_diff_sort

            result_rows.append(row_out)

    if not result_rows:
        # Schema rỗng
        schema: dict[str, Any] = {
            "KEY_TEXT": pl.Utf8,
            "KEY_HASH": pl.Utf8,
            "__key": pl.Utf8,
            "STATUS": pl.Utf8,
        }
        for g in profile.group_by:
            schema[g] = pl.Utf8
        for m in profile.measures:
            schema[f"x__{m.name}"] = pl.Decimal(38, 4) if "AMOUNT" in m.name else pl.Utf8
            schema[f"d__{m.name}"] = pl.Decimal(38, 4) if "AMOUNT" in m.name else pl.Utf8
            schema[f"diff__{m.name}"] = pl.Decimal(38, 4) if "AMOUNT" in m.name else pl.Utf8
        schema["__row_nos"] = pl.List(pl.Int64)
        schema["ABS_DIFF_MAIN"] = pl.Decimal(38, 4)
        schema["ABS_DIFF_SORT"] = pl.Float64
        return pl.DataFrame(schema=schema)

    # Sắp xếp kết quả theo Spec 04: trạng thái, |diff main| giảm dần, KEY_TEXT
    result_rows.sort(
        key=lambda r: (
            STATUS_PRIORITY.get(r["STATUS"], 99),
            -r["ABS_DIFF_SORT"],
            r["KEY_TEXT"],
        )
    )

    return pl.from_dicts(result_rows)
