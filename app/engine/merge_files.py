"""Gộp nhiều file Excel vào một mục (task 18, bước 5, spec 10 §5.6).

Mọi file đọc bằng cùng FileSpec của template. Header đã map phải khớp
giữa các file (khác → BATCH_MERGE_HEADER_MISMATCH, chỉ rõ file nào
thiếu/thừa cột). Control total kiểm từng file (mỗi file có dòng tổng
riêng). Kết quả giữ cột kỹ thuật __source_file (tên hiển thị của file)
và __row_no theo từng file.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import polars as pl

from app.engine.control_total import ControlTotalResult, check_control_total
from app.engine.filters import apply_row_filters
from app.engine.mapping import resolve_columns
from app.engine.normalize import derive, normalize
from app.engine.reader import read_sheets
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import TemplateConfig


@dataclass
class MergedFile:
    """Kết quả xử lý của một file trong tập gộp."""

    name: str
    path: Path
    rows_read: int
    rows_valid: int
    rows_invalid: int
    valid_df: pl.DataFrame
    invalid_df: pl.DataFrame
    control_total: ControlTotalResult | None

    @property
    def control_total_ok(self) -> bool | None:
        if self.control_total is None:
            return None
        return self.control_total.is_matched


def _mapped_field_set(mapped_df: pl.DataFrame) -> set[str]:
    return {c for c in mapped_df.columns if c not in ("__row_no", "__source_file")}


def merge_excel_files(
    files: list[tuple[Path | str, str]],
    config: TemplateConfig,
) -> list[MergedFile]:
    """Đọc và xử lý từng file, trả về danh sách kết quả theo từng file.

    files: [(đường dẫn, tên hiển thị)]. Tên hiển thị đưa vào cột
    __source_file và dùng trong thông báo lỗi.
    """
    if not files:
        raise ServiceError(ErrorCode.VALIDATION_ERROR, "Cần ít nhất một file để gộp.")
    paths = [p for p, _ in files]
    names = [n for _, n in files]
    raw_list = read_sheets(paths, config.file, names)

    expected_fields: set[str] | None = None
    results: list[MergedFile] = []
    for idx, (name, raw_df) in enumerate(raw_list):
        raw_df = raw_df.with_columns(pl.lit(name).alias("__source_file"))
        filtered_df = apply_row_filters(raw_df, config.file.row_filters)
        try:
            mapped_df, _ = resolve_columns(filtered_df, config.fields)
        except ServiceError as exc:
            if exc.code == ErrorCode.EXCEL_COLUMN_MISSING:
                raise ServiceError(
                    ErrorCode.BATCH_MERGE_HEADER_MISMATCH,
                    f"File '{name}' thiếu cột bắt buộc khi gộp: {exc.message}",
                ) from exc
            raise
        field_set = _mapped_field_set(mapped_df)
        if expected_fields is None:
            expected_fields = field_set
        elif field_set != expected_fields:
            missing = sorted(expected_fields - field_set)
            extra = sorted(field_set - expected_fields)
            details: list[str] = []
            if missing:
                details.append(f"thiếu cột: {', '.join(missing)}")
            if extra:
                details.append(f"thừa cột: {', '.join(extra)}")
            raise ServiceError(
                ErrorCode.BATCH_MERGE_HEADER_MISMATCH,
                f"File '{name}' lệch header khi gộp ({'; '.join(details)}).",
            )
        valid_df, invalid_df = normalize(
            mapped_df,
            config.fields,
            side="excel",
            thousand_sep=config.file.thousand_sep or ",",
            decimal_sep=config.file.decimal_sep or ".",
        )
        if config.derived:
            valid_df = derive(valid_df, config.derived)
        ct_res: ControlTotalResult | None = None
        if config.control_total:
            ct_res = check_control_total(
                raw_df,
                valid_df,
                config.control_total,
                config.fields,
                thousand_sep=config.file.thousand_sep or ",",
                decimal_sep=config.file.decimal_sep or ".",
            )
        results.append(
            MergedFile(
                name=name,
                path=Path(paths[idx]),
                rows_read=len(raw_df),
                rows_valid=len(valid_df),
                rows_invalid=len(invalid_df),
                valid_df=valid_df,
                invalid_df=invalid_df,
                control_total=ct_res,
            )
        )
    return results


def sum_control_totals(results: list[MergedFile]) -> ControlTotalResult | None:
    """Cộng dồn control total từng file thành một kết quả chung."""
    totals = [r.control_total for r in results if r.control_total is not None]
    if not totals:
        return None
    file_total = None
    calc_total = sum((t.calc_total for t in totals), start=Decimal("0"))
    if all(t.file_total is not None for t in totals):
        file_total = sum((t.file_total for t in totals if t.file_total is not None), start=Decimal("0"))
    matched = all(t.is_matched for t in totals) and file_total is not None
    warning = None
    if file_total is None:
        warning = "CONTROL_TOTAL_NOT_FOUND"
    return ControlTotalResult(
        file_total=file_total,
        calc_total=calc_total,
        diff=abs(calc_total - file_total) if file_total is not None else None,
        is_matched=matched,
        warning=warning,
    )
