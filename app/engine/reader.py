from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fastexcel
import polars as pl

from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import FileSpec


def list_sheets(path: Path | str) -> list[str]:
    """Liệt kê danh sách tên sheet trong file Excel hoặc trả về ['Sheet1'] nếu là CSV."""
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return ["Sheet1"]

    try:
        wb = fastexcel.read_excel(p)
        return list(wb.sheet_names)
    except Exception as exc:
        raise ServiceError(ErrorCode.SHEET_NOT_FOUND, f"Không thể đọc danh sách sheet từ file: {exc}") from exc


def _detect_csv_delimiter(path: Path) -> str:
    """Tự động nhận diện ký tự phân cách CSV (',', ';', '\\t')."""
    with open(path, "rb") as f:
        first_chunk = f.read(4096).decode("utf-8-sig", errors="replace")
    first_line = first_chunk.splitlines()[0] if first_chunk.splitlines() else ""

    counts = {
        ",": first_line.count(","),
        ";": first_line.count(";"),
        "\t": first_line.count("\t"),
    }
    delim = max(counts, key=lambda k: counts[k])
    return delim if counts[delim] > 0 else ","


def read_sheets(
    paths: list[Path | str],
    file_spec: FileSpec,
    names: list[str] | None = None,
) -> list[tuple[str, pl.DataFrame]]:
    """Đọc nhiều file theo cùng FileSpec, trả về [(tên hiển thị, raw_df)].

    Mỗi DataFrame giữ __row_no theo từng file. Tên hiển thị mặc định là
    basename; caller (gộp file theo bộ) truyền tên gốc trong .zip để
    __source_file không trùng khi hai file cùng tên.
    """
    out: list[tuple[str, pl.DataFrame]] = []
    for i, path in enumerate(paths):
        name = names[i] if names is not None else Path(path).name
        raw_df, _ = read_sheet(path, file_spec)
        out.append((name, raw_df))
    return out


def read_sheet(
    path: Path | str,
    file_spec: FileSpec,
) -> tuple[pl.DataFrame, list[str]]:
    """Đọc dữ liệu sheet theo FileSpec, giữ mọi ô dạng chuỗi, đánh chỉ số __row_no."""
    p = Path(path)
    warnings: list[str] = []

    # 1. Đọc dữ liệu thô (has_header=False, mọi cột String)
    if p.suffix.lower() == ".csv":
        delim = _detect_csv_delimiter(p)
        raw_df = pl.read_csv(
            p,
            has_header=False,
            separator=delim,
            infer_schema_length=0,
            truncate_ragged_lines=True,
        )
    else:
        sheets = list_sheets(p)
        target_sheet = file_spec.sheet
        if target_sheet not in sheets:
            if file_spec.sheet_pattern:
                pat = re.compile(file_spec.sheet_pattern)
                matched = next((s for s in sheets if pat.search(s)), None)
                if matched:
                    target_sheet = matched
                else:
                    raise ServiceError(
                        ErrorCode.SHEET_NOT_FOUND,
                        f"Không tìm thấy sheet '{file_spec.sheet}' hoặc khớp mẫu '{file_spec.sheet_pattern}' (có các sheet: {', '.join(sheets)})",
                    )
            else:
                raise ServiceError(
                    ErrorCode.SHEET_NOT_FOUND,
                    f"Không tìm thấy sheet '{file_spec.sheet}' trong file (có các sheet: {', '.join(sheets)})",
                )

        raw_df = pl.read_excel(
            source=p,
            sheet_name=target_sheet,
            engine="calamine",
            has_header=False,
            infer_schema_length=0,
        )

    total_rows = raw_df.height
    header_idx = file_spec.header_row - 1
    data_start_idx = file_spec.data_start_row - 1

    if header_idx >= total_rows:
        raise ServiceError(
            ErrorCode.SHEET_NOT_FOUND,
            f"File chỉ có {total_rows} dòng, không đủ tới header_row ({file_spec.header_row})",
        )

    # 2. Xử lý header row và giải quyết trùng lặp
    header_row_vals = [str(x).strip().lstrip("\ufeff") if x is not None else "" for x in raw_df.row(header_idx)]
    seen_headers: dict[str, int] = {}
    unique_headers: list[str] = []

    for i, col_name in enumerate(header_row_vals):
        clean_name = col_name if col_name else f"_COL_{i + 1}"
        if clean_name in seen_headers:
            seen_headers[clean_name] += 1
            new_name = f"{clean_name}__{seen_headers[clean_name]}"
            unique_headers.append(new_name)
            warnings.append(f"Cột '{clean_name}' bị trùng lặp ở vị trí {i + 1}, tự động đổi thành '{new_name}'")
        else:
            seen_headers[clean_name] = 1
            unique_headers.append(clean_name)

    # 3. Cắt dữ liệu từ data_start_row
    if data_start_idx >= total_rows:
        empty_schema: dict[str, Any] = {h: pl.Utf8 for h in unique_headers}
        empty_schema["__row_no"] = pl.Int64
        return pl.DataFrame(schema=empty_schema), warnings

    data_slice = raw_df.slice(data_start_idx)
    if file_spec.skip_footer_rows > 0:
        slice_len = data_slice.height - file_spec.skip_footer_rows
        if slice_len > 0:
            data_slice = data_slice.slice(0, slice_len)
        else:
            data_slice = data_slice.slice(0, 0)

    # Đổi tên cột sang unique_headers
    data_slice.columns = unique_headers

    # 4. Thêm cột __row_no (1-based physical row number)
    row_count = data_slice.height
    row_numbers = [file_spec.data_start_row + i for i in range(row_count)]
    data_slice = data_slice.with_columns(pl.Series("__row_no", row_numbers, dtype=pl.Int64))

    # Đảm bảo tất cả cột dữ liệu (trừ __row_no) là Utf8
    cast_exprs = [pl.col(col).cast(pl.Utf8) for col in unique_headers]
    data_slice = data_slice.with_columns(cast_exprs)

    return data_slice, warnings
