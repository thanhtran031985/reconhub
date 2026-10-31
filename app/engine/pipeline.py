from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl
from pydantic import BaseModel, ConfigDict

from app.engine.aggregate import aggregate
from app.engine.compare import compare
from app.engine.control_total import ControlTotalResult, check_control_total
from app.engine.filters import apply_profile_filters, apply_row_filters, apply_time_filter
from app.engine.mapping import resolve_columns
from app.engine.normalize import derive, normalize
from app.engine.reader import read_sheet
from app.engine.sql_builder import build_source_sql
from app.engine.sql_guard import check_sql
from app.engine.summary import build_summary
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import ProfileSpec, TemplateConfig


class PipelineResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    result_df: pl.DataFrame
    invalid_df: pl.DataFrame
    summary: dict[str, Any]
    profile: ProfileSpec
    control_total: ControlTotalResult | None


def _parse_datetime(val: Any) -> datetime | None:
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    if isinstance(val, str):
        cleaned = val.strip()
        try:
            return datetime.fromisoformat(cleaned)
        except Exception:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(cleaned, fmt)
                except Exception:
                    pass
    return None


def run_pipeline(
    excel_path: str | Path,
    config: TemplateConfig,
    profile_code: str | None = None,
    params: dict[str, Any] | None = None,
    fetcher: Any = None,
) -> PipelineResult:
    """Chạy trọn vẹn đối soát theo Spec 04 mục 0."""
    start_time = time.perf_counter()
    params_dict = params or {}

    # 1. Chọn Profile phù hợp
    target_profile: ProfileSpec | None = None
    if profile_code:
        for p in config.profiles:
            if p.code == profile_code:
                target_profile = p
                break
        if target_profile is None:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"Không tìm thấy profile '{profile_code}'.")
    else:
        for p in config.profiles:
            if p.is_default:
                target_profile = p
                break
        if target_profile is None:
            target_profile = config.profiles[0]

    profile = target_profile

    # 2. Đọc file Excel
    raw_df, _ = read_sheet(excel_path, config.file)
    excel_rows_read = len(raw_df)

    # 3. Lọc dòng Excel thô (drop_if, keep_if, loại bỏ footer v.v.)
    filtered_raw = apply_row_filters(raw_df, config.file.row_filters)

    # 4. Kiểm tra Control total (Spec 04 mục 3: trên dữ liệu sau row_filters, trước lọc thời gian)
    ct_res: ControlTotalResult | None = None
    if config.control_total:
        ct_res = check_control_total(
            raw_df,
            filtered_raw,
            config.control_total,
            config.fields,
            thousand_sep=config.file.thousand_sep or ",",
            decimal_sep=config.file.decimal_sep or ".",
        )

    # 5. Mapping cột
    mapped_df, _ = resolve_columns(filtered_raw, config.fields)

    # 6. Chuẩn hóa & Dẫn xuất (Excel)
    norm_excel, invalid_df = normalize(mapped_df, config.fields, side="excel")
    excel_rows_invalid = len(invalid_df)
    derived_excel = derive(norm_excel, config.derived)

    # 7. Lọc theo thời gian (Excel)
    p_from = _parse_datetime(params_dict.get("p_from"))
    p_to = _parse_datetime(params_dict.get("p_to"))

    excel_rows_out_of_range = 0
    if config.time_filter and p_from and p_to:
        tf_res = apply_time_filter(derived_excel, config.time_filter, p_from, p_to)
        derived_excel = tf_res.df
        excel_rows_out_of_range = tf_res.out_of_range_count

    # 8. Lọc theo Profile (Excel)
    if profile.filters:
        derived_excel = apply_profile_filters(derived_excel, profile.filters)

    # 9. Gộp dữ liệu Excel
    excel_agg = aggregate(derived_excel, profile)
    excel_groups = len(excel_agg)

    # 10. Lấy dữ liệu DB
    if isinstance(fetcher, pl.DataFrame):
        db_raw = fetcher
    elif callable(fetcher):
        db_raw = fetcher(config, profile, p_from, p_to, 1_000_000, 600)
    elif hasattr(fetcher, "fetch_df"):
        sql, binds = build_source_sql(config, profile, params_dict)
        ok, err_msg = check_sql(sql, list(binds.keys()))
        if not ok:
            raise ServiceError(ErrorCode.SQL_NOT_ALLOWED, err_msg or "SQL không hợp lệ.")
        db_raw = fetcher.fetch_df(None, sql, binds)
    else:
        db_raw = pl.DataFrame()

    db_rows = len(db_raw)

    # Đổi tên cột từ DB sang tên trường logic
    db_col_to_field: dict[str, str] = {}
    for f in config.fields:
        if f.db:
            db_col_to_field[f.db] = f.name
            db_col_to_field[f.db.upper()] = f.name
    rename_db = {c: db_col_to_field[c] for c in db_raw.columns if c in db_col_to_field and c != db_col_to_field[c]}
    if rename_db:
        db_raw = db_raw.rename(rename_db)

    # Lọc thời gian phía DB nếu dữ liệu DB chưa lọc (ví dụ DataFrame thô)
    if config.time_filter and p_from and p_to:
        tf_field = config.time_filter.excel_field or config.time_filter.db_column
        if tf_field and tf_field in db_raw.columns:
            tf_res_db = apply_time_filter(db_raw, config.time_filter, p_from, p_to)
            db_raw = tf_res_db.df

    # Chuẩn hóa & Dẫn xuất (DB)
    norm_db, _ = normalize(db_raw, config.fields, side="db")
    derived_db = derive(norm_db, config.derived)

    # Lọc theo Profile (DB)
    if profile.filters:
        derived_db = apply_profile_filters(derived_db, profile.filters)

    # Gộp dữ liệu DB
    db_agg = aggregate(derived_db, profile)
    db_groups = len(db_agg)

    # 11. Ghép và so sánh kết quả
    result_df = compare(excel_agg, db_agg, profile)

    # 12. Tổng hợp số liệu
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    summary_dict = build_summary(
        result_df=result_df,
        profile=profile,
        excel_rows_read=excel_rows_read,
        excel_rows_out_of_range=excel_rows_out_of_range,
        excel_rows_invalid=excel_rows_invalid,
        excel_groups=excel_groups,
        db_rows=db_rows,
        db_groups=db_groups,
        control_total_res=ct_res,
        duration_ms=duration_ms,
        config=config,
    )

    return PipelineResult(
        result_df=result_df,
        invalid_df=invalid_df,
        summary=summary_dict,
        profile=profile,
        control_total=ct_res,
    )
