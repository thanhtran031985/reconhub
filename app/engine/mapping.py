from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import polars as pl

from app.engine.reader import list_sheets, read_sheet
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import FieldSpec, FileSpec


def _normalize_header(name: str) -> str:
    """Chuẩn hóa header: NFC, loại bỏ khoảng trắng thừa, chữ thường."""
    nfc = unicodedata.normalize("NFC", str(name))
    collapsed = re.sub(r"\s+", " ", nfc.strip())
    return collapsed.lower()


def resolve_columns(
    df: pl.DataFrame,
    fields: list[FieldSpec],
) -> tuple[pl.DataFrame, dict[str, str]]:
    """Ánh xạ các cột thực tế của file sang trường logic FieldSpec.

    So khớp không phân biệt hoa thường, NFC, gộp khoảng trắng thừa.
    Ưu tiên field.excel rồi đến field.excel_aliases.
    Báo lỗi EXCEL_COLUMN_MISSING nếu thiếu cột bắt buộc (required=True).
    Trả về (mapped_df, rename_map: {field_name: original_col_name}).
    """
    col_map: dict[str, str] = {}
    for col in df.columns:
        if col == "__row_no":
            continue
        norm_key = _normalize_header(col)
        if norm_key not in col_map:
            col_map[norm_key] = col

    rename_map: dict[str, str] = {}
    rename_for_df: dict[str, str] = {}

    for f in fields:
        if not f.excel and not f.excel_aliases:
            continue

        candidates: list[str] = []
        if f.excel:
            candidates.append(f.excel)
        candidates.extend(f.excel_aliases)
        candidates.append(f.name)

        matched_original: str | None = None
        for cand in candidates:
            norm_cand = _normalize_header(cand)
            if norm_cand in col_map:
                matched_original = col_map[norm_cand]
                break

        if matched_original is not None:
            rename_map[f.name] = matched_original
            rename_for_df[matched_original] = f.name
        else:
            if f.required:
                raise ServiceError(
                    ErrorCode.EXCEL_COLUMN_MISSING,
                    f"Không tìm thấy cột bắt buộc '{f.excel or f.name}' trong file Excel",
                )

    mapped_df = df.rename(rename_for_df)
    return mapped_df, rename_map


def detect_template(
    file_path: Path | str,
    templates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Tự động nhận diện template phù hợp dựa trên các header detect_by_headers."""
    p = Path(file_path)
    sheets = list_sheets(p)
    if not sheets:
        return None

    for sheet_name in sheets:
        try:
            df, _ = read_sheet(p, FileSpec(sheet=sheet_name, header_row=1, data_start_row=2))
            headers = set(_normalize_header(col) for col in df.columns if col != "__row_no")
        except Exception:
            continue

        for tmpl in templates:
            cfg = tmpl.get("config", {})
            file_cfg = cfg.get("file", {})
            detect_headers = file_cfg.get("detect_by_headers", [])
            if not detect_headers:
                continue

            norm_detect = [_normalize_header(h) for h in detect_headers]
            if all(h in headers for h in norm_detect):
                return tmpl

    return None

