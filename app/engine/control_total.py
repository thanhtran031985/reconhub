from __future__ import annotations

import unicodedata
from decimal import Decimal

import polars as pl
from pydantic import BaseModel

from app.engine.normalize import normalize_value
from app.schemas.template_config import ControlTotalSpec, FieldSpec


class ControlTotalResult(BaseModel):
    file_total: Decimal | None
    calc_total: Decimal
    diff: Decimal | None
    is_matched: bool
    warning: str | None = None
    located_row_no: int | None = None


def _find_column(columns: list[str], target: str) -> str | None:
    norm_target = unicodedata.normalize("NFC", target).strip().lower()
    for col in columns:
        if unicodedata.normalize("NFC", col).strip().lower() == norm_target:
            return col
    return None


def check_control_total(
    raw_df: pl.DataFrame,
    valid_df: pl.DataFrame,
    spec: ControlTotalSpec,
    fields: list[FieldSpec] | None = None,
    thousand_sep: str = ",",
    decimal_sep: str = ".",
) -> ControlTotalResult:
    """Kiểm tra control total giữa giá trị trong file Excel và tổng tính toán."""
    locate_col = _find_column(raw_df.columns, spec.locate.excel_col)
    val_col = _find_column(raw_df.columns, spec.value_col)

    file_total: Decimal | None = None
    located_row_no: int | None = None
    warning: str | None = None

    if locate_col and val_col:
        locate_expected = unicodedata.normalize("NFC", str(spec.locate.equals)).strip().lower()
        rows = raw_df.to_dicts()
        for r in rows:
            cell_val = unicodedata.normalize("NFC", str(r.get(locate_col) or "")).strip().lower()
            if cell_val == locate_expected:
                raw_val = r.get(val_col)
                dummy_spec = FieldSpec(name="TMP_TOTAL", label="TMP_TOTAL", type="number")
                try:
                    norm_val, _ = normalize_value(raw_val, dummy_spec, thousand_sep, decimal_sep)
                    if isinstance(norm_val, Decimal):
                        file_total = norm_val
                        located_row_no = r.get("__row_no")
                        break
                except Exception:
                    pass

    if file_total is None:
        warning = "CONTROL_TOTAL_NOT_FOUND"

    # Tính calc_total từ valid_df
    target_data_col: str | None = None
    if spec.value_col in valid_df.columns:
        target_data_col = spec.value_col
    elif fields:
        norm_spec_val = unicodedata.normalize("NFC", spec.value_col).strip().lower()
        for f in fields:
            f_names = [f.name, f.excel or ""] + list(f.excel_aliases)
            if any(unicodedata.normalize("NFC", fn).strip().lower() == norm_spec_val for fn in f_names if fn):
                if f.name in valid_df.columns:
                    target_data_col = f.name
                    break

    # Nếu vẫn chưa tìm thấy và valid_df chỉ có 1 cột dữ liệu (ngoài __row_no), dùng cột đó
    if target_data_col is None:
        candidate_cols = [c for c in valid_df.columns if c != "__row_no"]
        if len(candidate_cols) == 1:
            target_data_col = candidate_cols[0]

    calc_total = Decimal("0")
    if target_data_col and target_data_col in valid_df.columns:
        for val in valid_df[target_data_col].to_list():
            if isinstance(val, Decimal):
                calc_total += val
            elif val is not None and str(val).strip():
                try:
                    calc_total += Decimal(str(val))
                except Exception:
                    pass

    diff: Decimal | None = None
    is_matched = False
    if file_total is not None:
        diff = abs(calc_total - file_total)
        is_matched = diff <= Decimal(str(spec.tolerance))

    return ControlTotalResult(
        file_total=file_total,
        calc_total=calc_total,
        diff=diff,
        is_matched=is_matched,
        warning=warning,
        located_row_no=located_row_no,
    )
