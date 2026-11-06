from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, BinaryIO

import polars as pl
import xlsxwriter

from app.engine.export_styles import get_export_formats
from app.schemas.template_config import ProfileSpec, TemplateConfig

STATUS_SHEET_MAP = {
    "MISMATCH": "Lệch giá trị",
    "MISSING_IN_DB": "Thiếu trong DB",
    "MISSING_IN_EXCEL": "Thiếu trong Excel",
    "INCONSISTENT": "Không nhất quán",
    "DUPLICATE": "Trùng khóa",
    "MATCHED": "Khớp",
}


def _write_summary_sheet(
    ws: xlsxwriter.workbook.Worksheet,
    formats: dict[str, Any],
    summary: dict[str, Any],
    profile: ProfileSpec,
    config: TemplateConfig | None = None,
    run_params: dict[str, Any] | None = None,
) -> None:
    ws.set_column(0, 0, 25)
    ws.set_column(1, 1, 25)
    ws.set_column(2, 2, 20)
    ws.set_column(3, 3, 20)
    ws.set_column(4, 4, 20)

    # 1. Tiêu đề
    ws.write(0, 0, "BÁO CÁO TỔNG HỢP KẾT QUẢ ĐỐI SOÁT", formats["title"])
    ws.write(2, 0, "THÔNG TIN CHUNG", formats["section_header"])
    ws.write(2, 1, "", formats["section_header"])

    # 2. Thông tin chung
    curr_row = 3
    params = run_params or {}
    general_info = [
        ("Profile đối soát:", profile.name),
        ("Từ ngày giờ:", str(params.get("p_from", "—"))),
        ("Đến ngày giờ:", str(params.get("p_to", "—"))),
        ("Đơn vị:", str(params.get("p_org", "—"))),
        ("Số dòng Excel đọc được:", summary.get("EXCEL_ROWS_READ", 0)),
        ("Số dòng Excel ngoài khoảng:", summary.get("EXCEL_ROWS_OUT_OF_RANGE", 0)),
        ("Số dòng Excel không hợp lệ:", summary.get("EXCEL_ROWS_INVALID", 0)),
        ("Số nhóm Excel:", summary.get("EXCEL_GROUPS", 0)),
        ("Số dòng DB:", summary.get("DB_ROWS", 0)),
        ("Số nhóm DB:", summary.get("DB_GROUPS", 0)),
    ]
    for lbl, val in general_info:
        ws.write(curr_row, 0, lbl, formats["text"])
        if isinstance(val, int):
            ws.write(curr_row, 1, val, formats["number_integer"])
        else:
            ws.write(curr_row, 1, str(val), formats["text"])
        curr_row += 1

    # 3. Control Total
    curr_row += 1
    ws.write(curr_row, 0, "KIỂM TRA DÒNG TỔNG (CONTROL TOTAL)", formats["section_header"])
    ws.write(curr_row, 1, "", formats["section_header"])
    curr_row += 1

    ct_file = summary.get("CONTROL_TOTAL_FILE")
    ct_calc = summary.get("CONTROL_TOTAL_CALC")
    ct_ok = summary.get("CONTROL_TOTAL_OK")

    ws.write(curr_row, 0, "Tổng trong file Excel:", formats["text"])
    if ct_file is not None:
        ws.write(curr_row, 1, float(ct_file), formats["number_integer"])
    else:
        ws.write(curr_row, 1, "—", formats["text"])
    curr_row += 1

    ws.write(curr_row, 0, "Tổng tính toán:", formats["text"])
    if ct_calc is not None:
        ws.write(curr_row, 1, float(ct_calc), formats["number_integer"])
    else:
        ws.write(curr_row, 1, "—", formats["text"])
    curr_row += 1

    ws.write(curr_row, 0, "Trạng thái Control Total:", formats["text"])
    ct_status_str = "Khớp" if ct_ok == "Y" else ("Lệch" if ct_ok == "N" else "Không có")
    ws.write(curr_row, 1, ct_status_str, formats["status_matched"] if ct_ok == "Y" else formats["status_mismatch"])
    curr_row += 2

    # 4. Thống kê theo trạng thái
    ws.write(curr_row, 0, "THỐNG KÊ THEO TRẠNG THÁI KẾT QUẢ", formats["section_header"])
    ws.write(curr_row, 1, "", formats["section_header"])
    ws.write(curr_row, 2, "", formats["section_header"])
    ws.write(curr_row, 3, "", formats["section_header"])
    ws.write(curr_row, 4, "", formats["section_header"])
    curr_row += 1

    st_headers = ["Trạng thái", "Số lượng", "Tiền Excel", "Tiền DB", "Chênh lệch"]
    for c_idx, h in enumerate(st_headers):
        ws.write(curr_row, c_idx, h, formats["table_header"])
    curr_row += 1

    status_data = [
        ("Khớp (MATCHED)", summary.get("CNT_MATCHED", 0), "MATCHED"),
        ("Lệch giá trị (MISMATCH)", summary.get("CNT_MISMATCH", 0), "MISMATCH"),
        ("Thiếu trong DB", summary.get("CNT_MISSING_IN_DB", 0), "MISSING_IN_DB"),
        ("Thiếu trong Excel", summary.get("CNT_MISSING_IN_EXCEL", 0), "MISSING_IN_EXCEL"),
        ("Không nhất quán", summary.get("CNT_INCONSISTENT", 0), "INCONSISTENT"),
        ("Trùng khóa", summary.get("CNT_DUPLICATE", 0), "DUPLICATE"),
    ]

    status_amounts = summary.get("STATUS_AMOUNTS_JSON", {})

    for lbl, cnt, code in status_data:
        ws.write(curr_row, 0, lbl, formats["text"])
        ws.write(curr_row, 1, cnt, formats["number_integer"])
        amt_info = status_amounts.get(code, {})
        ex_amt = amt_info.get("excel", "0")
        db_amt = amt_info.get("db", "0")
        diff_amt = amt_info.get("diff", "0")

        ws.write(curr_row, 2, float(ex_amt), formats["number_integer"])
        ws.write(curr_row, 3, float(db_amt), formats["number_integer"])
        ws.write(curr_row, 4, float(diff_amt), formats["number_integer"])
        curr_row += 1


def _write_data_sheet(
    ws: xlsxwriter.workbook.Worksheet,
    formats: dict[str, Any],
    rows: list[dict[str, Any]],
    profile: ProfileSpec,
    status_code: str,
    field_labels: dict[str, str],
) -> None:
    # 1. Xác định danh sách cột
    headers: list[str] = []
    col_keys: list[str] = []

    # Khóa Group by
    for g in profile.group_by:
        headers.append(field_labels.get(g, g))
        col_keys.append(g)

    # Trạng thái
    headers.append("Trạng thái")
    col_keys.append("STATUS")

    # Measures
    for m in profile.measures:
        m_lbl = m.label or m.name
        headers.append(f"{m_lbl} (Excel)")
        col_keys.append(f"x__{m.name}")
        headers.append(f"{m_lbl} (DB)")
        col_keys.append(f"d__{m.name}")
        headers.append(f"Chênh {m_lbl}")
        col_keys.append(f"diff__{m.name}")

    # Cột dòng Excel
    headers.append("Dòng Excel")
    col_keys.append("__row_nos")

    # Ghi header
    for c_idx, h in enumerate(headers):
        ws.write(0, c_idx, h, formats["table_header"])

    # Freeze top row
    ws.freeze_panes(1, 0)

    # 2. Ghi từng dòng dữ liệu
    for r_idx, r in enumerate(rows, start=1):
        for c_idx, col_name in enumerate(col_keys):
            val = r.get(col_name)

            # Cột khóa
            if col_name in profile.group_by:
                val_str = "" if val is None else str(val)
                # Dùng write_string và num_format="@" để giữ số 0 ở đầu
                ws.write_string(r_idx, c_idx, val_str, formats["key_text"])

            # Cột trạng thái
            elif col_name == "STATUS":
                st = str(val or "")
                if st == "MATCHED":
                    fmt = formats["status_matched"]
                elif st == "MISMATCH":
                    fmt = formats["status_mismatch"]
                else:
                    fmt = formats["status_missing"]
                ws.write(r_idx, c_idx, st, fmt)

            # Cột dòng Excel: run gộp nhiều file hiện "file · dòng r"
            elif col_name == "__row_nos":
                if isinstance(val, list):
                    parts = []
                    for x in val:
                        if isinstance(x, dict):
                            parts.append(f"{x.get('f')} · dòng {x.get('r')}")
                        else:
                            parts.append(str(x))
                    row_nos_str = ", ".join(parts)
                else:
                    row_nos_str = str(val or "")
                ws.write(r_idx, c_idx, row_nos_str, formats["text_center"])

            # Cột Measures
            else:
                is_diff_col = col_name.startswith("diff__")
                has_diff = is_diff_col and val is not None and val != 0 and val != Decimal("0")

                if isinstance(val, (Decimal, int, float)) and not isinstance(val, bool):
                    num_val = float(val)
                    if num_val.is_integer():
                        fmt = formats["diff_number_integer"] if has_diff else formats["number_integer"]
                    else:
                        fmt = formats["diff_number_decimal"] if has_diff else formats["number_decimal"]
                    ws.write(r_idx, c_idx, num_val, fmt)
                elif val is None:
                    ws.write(r_idx, c_idx, "", formats["diff_text"] if has_diff else formats["text"])
                else:
                    ws.write(r_idx, c_idx, str(val), formats["diff_text"] if has_diff else formats["text"])

    # Auto-adjust column widths
    for c_idx, h in enumerate(headers):
        max_len = max(len(h), 12)
        ws.set_column(c_idx, c_idx, max_len + 3)


def _write_invalid_sheet(
    ws: xlsxwriter.workbook.Worksheet,
    formats: dict[str, Any],
    invalid_df: pl.DataFrame,
) -> None:
    headers = ["Số dòng Excel", "Dữ liệu dòng", "Lý do không hợp lệ"]
    for c_idx, h in enumerate(headers):
        ws.write(0, c_idx, h, formats["table_header"])

    ws.freeze_panes(1, 0)
    ws.set_column(0, 0, 15)
    ws.set_column(1, 1, 50)
    ws.set_column(2, 2, 35)

    rows = invalid_df.to_dicts()
    for r_idx, r in enumerate(rows, start=1):
        ws.write(r_idx, 0, r.get("__row_no", 0), formats["number_integer"])
        ws.write(r_idx, 1, str(r.get("__raw_data", "")), formats["text"])
        ws.write(r_idx, 2, str(r.get("__invalid_reasons", "")), formats["text"])


def write_export(
    output_path: str | Path | BinaryIO,
    result_df: pl.DataFrame,
    invalid_df: pl.DataFrame,
    summary: dict[str, Any],
    profile: ProfileSpec,
    config: TemplateConfig | None = None,
    run_params: dict[str, Any] | None = None,
) -> None:
    """Xuất file Excel báo cáo đối soát theo chuẩn Spec 04 mục 10."""
    field_labels: dict[str, str] = {}
    if config:
        for f in config.fields:
            field_labels[f.name] = f.label or f.name
        for d in config.derived:
            field_labels[d.name] = d.label or d.name

    wb = xlsxwriter.Workbook(output_path, {"constant_memory": False})
    formats = get_export_formats(wb)

    # 1. Sheet Tổng hợp
    ws_summary = wb.add_worksheet("Tổng hợp")
    _write_summary_sheet(ws_summary, formats, summary, profile, config, run_params)

    # 2. Các sheet theo từng trạng thái
    rows = result_df.to_dicts() if not result_df.is_empty() else []

    # Danh sách trạng thái cần sinh sheet
    status_order = ["MISMATCH", "MISSING_IN_DB", "MISSING_IN_EXCEL", "INCONSISTENT", "DUPLICATE", "MATCHED"]
    for st_code in status_order:
        sheet_title = STATUS_SHEET_MAP.get(st_code, st_code)
        st_rows = [r for r in rows if r.get("STATUS") == st_code]
        if st_rows:
            ws = wb.add_worksheet(sheet_title)
            _write_data_sheet(ws, formats, st_rows, profile, st_code, field_labels)

    # 3. Sheet Không hợp lệ (nếu có dòng lỗi)
    if not invalid_df.is_empty():
        ws_inv = wb.add_worksheet("Không hợp lệ")
        _write_invalid_sheet(ws_inv, formats, invalid_df)

    wb.close()
