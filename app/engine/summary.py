from __future__ import annotations

from decimal import Decimal
from typing import Any

import polars as pl

from app.engine.control_total import ControlTotalResult
from app.schemas.template_config import ProfileSpec, TemplateConfig


def build_columns_metadata(
    profile: ProfileSpec,
    config: TemplateConfig | None = None,
) -> list[dict[str, Any]]:
    """Tạo metadata cột phục vụ hiển thị AG Grid và xuất Excel (Spec 04 mục 10)."""
    # Lấy nhãn của các trường từ TemplateConfig nếu có
    field_labels: dict[str, str] = {}
    if config:
        for f in config.fields:
            field_labels[f.name] = f.label or f.name
        for d in config.derived:
            field_labels[d.name] = d.label or d.name

    cols: list[dict[str, Any]] = []

    # 1. Các cột khóa
    for g in profile.group_by:
        label = field_labels.get(g, g)
        cols.append(
            {
                "field": g,
                "headerName": label,
                "type": "key",
                "side": "key",
            }
        )

    # 2. Cột trạng thái
    cols.append(
        {
            "field": "STATUS",
            "headerName": "Trạng thái",
            "type": "status",
            "side": "status",
        }
    )

    # 3. Các cột measures: Excel, DB, Chênh lệch
    for m in profile.measures:
        m_label = m.label or m.name
        cols.append(
            {
                "field": f"x__{m.name}",
                "headerName": f"{m_label} (Excel)",
                "type": "number" if m.agg in ("sum", "count", "count_distinct") else "text",
                "side": "excel",
                "measure": m.name,
            }
        )
        cols.append(
            {
                "field": f"d__{m.name}",
                "headerName": f"{m_label} (DB)",
                "type": "number" if m.agg in ("sum", "count", "count_distinct") else "text",
                "side": "db",
                "measure": m.name,
            }
        )
        cols.append(
            {
                "field": f"diff__{m.name}",
                "headerName": f"Chênh {m_label}",
                "type": "number" if m.agg in ("sum", "count", "count_distinct") else "text",
                "side": "diff",
                "measure": m.name,
            }
        )

    # 4. Cột số dòng Excel
    cols.append(
        {
            "field": "__row_nos",
            "headerName": "Dòng Excel",
            "type": "list",
            "side": "system",
        }
    )

    return cols


def _sum_decimal_series(series: list[Any]) -> Decimal:
    total = Decimal("0")
    for v in series:
        if v is not None and isinstance(v, Decimal):
            total += v
        elif v is not None and isinstance(v, (int, float)):
            total += Decimal(str(v))
    return total


def build_summary(
    result_df: pl.DataFrame,
    profile: ProfileSpec,
    excel_rows_read: int = 0,
    excel_rows_out_of_range: int = 0,
    excel_rows_invalid: int = 0,
    excel_groups: int = 0,
    db_rows: int = 0,
    db_groups: int = 0,
    control_total_res: ControlTotalResult | None = None,
    duration_ms: int = 0,
    config: TemplateConfig | None = None,
    source_sql: str | None = None,
) -> dict[str, Any]:
    """Tổng hợp số liệu thống kê cho lần chạy (RECON_RUN_SUMMARY theo Spec 04 mục 10)."""
    rows = result_df.to_dicts() if not result_df.is_empty() else []

    # Đếm số lượng theo trạng thái
    cnt_matched = 0
    cnt_mismatch = 0
    cnt_missing_in_db = 0
    cnt_missing_in_excel = 0
    cnt_inconsistent = 0
    cnt_duplicate = 0

    for r in rows:
        st = r.get("STATUS")
        if st == "MATCHED":
            cnt_matched += 1
        elif st == "MISMATCH":
            cnt_mismatch += 1
        elif st == "MISSING_IN_DB":
            cnt_missing_in_db += 1
        elif st == "MISSING_IN_EXCEL":
            cnt_missing_in_excel += 1
        elif st == "INCONSISTENT":
            cnt_inconsistent += 1
        elif st == "DUPLICATE":
            cnt_duplicate += 1

    # Tổng hợp Measures (MEASURE_TOTALS_JSON)
    measure_totals: dict[str, dict[str, str]] = {}
    for m in profile.measures:
        x_vals = [r.get(f"x__{m.name}") for r in rows]
        d_vals = [r.get(f"d__{m.name}") for r in rows]
        diff_vals = [r.get(f"diff__{m.name}") for r in rows]

        x_sum = _sum_decimal_series(x_vals)
        d_sum = _sum_decimal_series(d_vals)
        diff_sum = _sum_decimal_series(diff_vals)

        measure_totals[m.name] = {
            "excel": str(x_sum),
            "db": str(d_sum),
            "diff": str(diff_sum),
        }

    # Tổng tiền theo trạng thái (STATUS_AMOUNTS_JSON)
    status_amounts: dict[str, dict[str, str]] = {}
    main_m = profile.main_measure
    if main_m:
        statuses = ["MATCHED", "MISMATCH", "MISSING_IN_DB", "MISSING_IN_EXCEL", "INCONSISTENT", "DUPLICATE"]
        for st in statuses:
            st_rows = [r for r in rows if r.get("STATUS") == st]
            x_vals = [r.get(f"x__{main_m}") for r in st_rows]
            d_vals = [r.get(f"d__{main_m}") for r in st_rows]
            diff_vals = [r.get(f"diff__{main_m}") for r in st_rows]

            status_amounts[st] = {
                "excel": str(_sum_decimal_series(x_vals)),
                "db": str(_sum_decimal_series(d_vals)),
                "diff": str(_sum_decimal_series(diff_vals)),
            }

    # Metadata cột
    columns_json = build_columns_metadata(profile, config)

    # Control total
    ct_file = control_total_res.file_total if control_total_res else None
    ct_calc = control_total_res.calc_total if control_total_res else None
    ct_ok = ("Y" if control_total_res.is_matched else "N") if control_total_res else None

    return {
        "EXCEL_ROWS_READ": excel_rows_read,
        "EXCEL_ROWS_OUT_OF_RANGE": excel_rows_out_of_range,
        "EXCEL_ROWS_INVALID": excel_rows_invalid,
        "EXCEL_GROUPS": excel_groups,
        "DB_ROWS": db_rows,
        "DB_GROUPS": db_groups,
        "CNT_MATCHED": cnt_matched,
        "CNT_MISMATCH": cnt_mismatch,
        "CNT_MISSING_IN_DB": cnt_missing_in_db,
        "CNT_MISSING_IN_EXCEL": cnt_missing_in_excel,
        "CNT_INCONSISTENT": cnt_inconsistent,
        "CNT_DUPLICATE": cnt_duplicate,
        "CONTROL_TOTAL_FILE": ct_file,
        "CONTROL_TOTAL_CALC": ct_calc,
        "CONTROL_TOTAL_OK": ct_ok,
        "MEASURE_TOTALS_JSON": measure_totals,
        "STATUS_AMOUNTS_JSON": status_amounts,
        "COLUMNS_JSON": columns_json,
        "SOURCE_SQL": source_sql,
        "DURATION_MS": duration_ms,
    }
