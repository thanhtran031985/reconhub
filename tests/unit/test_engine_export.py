from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import openpyxl
import polars as pl

from app.engine.aggregate import aggregate
from app.engine.compare import compare
from app.engine.export import write_export
from app.engine.export_styles import COLOR_DIFF_BG
from app.engine.summary import build_summary
from app.schemas.template_config import MeasureSpec, ProfileSpec


def test_export_excel_format_and_styles() -> None:
    profile = ProfileSpec(
        code="BY_INVOICE",
        name="Theo số hóa đơn",
        aggregate=True,
        group_by=["INVOICE_NO"],
        main_measure="TOTAL_AMOUNT",
        measures=[
            MeasureSpec(
                name="TOTAL_AMOUNT",
                label="Tổng tiền",
                agg="sum",
                field="AMOUNT",
                compare="abs_tol",
                tolerance=Decimal("1.0"),
                round=0,
            ),
            MeasureSpec(name="TOTAL_QTY", label="Số lượng", agg="sum", field="QTY", compare="exact", round=0),
            MeasureSpec(name="LINE_CNT", label="Số dòng", agg="count", compare="display_only"),
        ],
    )

    # 1 Khớp, 1 Lệch (có số 0 ở đầu khóa "0334"), 1 Thiếu DB, 1 Thiếu Excel
    excel_raw = pl.DataFrame(
        [
            {"INVOICE_NO": "INV-MATCH", "AMOUNT": Decimal("100"), "QTY": Decimal("1"), "__row_no": 2},
            {"INVOICE_NO": "0334", "AMOUNT": Decimal("150"), "QTY": Decimal("1"), "__row_no": 3},
            {"INVOICE_NO": "INV-MISS-DB", "AMOUNT": Decimal("50"), "QTY": Decimal("1"), "__row_no": 4},
        ]
    )
    excel_agg = aggregate(excel_raw, profile)

    db_raw = pl.DataFrame(
        [
            {"INVOICE_NO": "INV-MATCH", "AMOUNT": Decimal("100"), "QTY": Decimal("1")},
            {"INVOICE_NO": "0334", "AMOUNT": Decimal("200"), "QTY": Decimal("1")},
            {"INVOICE_NO": "INV-MISS-EXCEL", "AMOUNT": Decimal("80"), "QTY": Decimal("2")},
        ]
    )
    db_agg = aggregate(db_raw, profile)

    res_df = compare(excel_agg, db_agg, profile)

    invalid_df = pl.DataFrame(
        [{"__row_no": 10, "__raw_data": '{"INVOICE_NO": ""}', "__invalid_reasons": '["MISSING_KEY"]'}]
    )

    summary = build_summary(
        result_df=res_df,
        profile=profile,
        excel_rows_read=3,
        excel_rows_invalid=1,
    )

    with NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        tmp_export_path = f.name

    write_export(
        output_path=tmp_export_path,
        result_df=res_df,
        invalid_df=invalid_df,
        summary=summary,
        profile=profile,
        run_params={"p_from": "2026-02-01", "p_to": "2026-02-05"},
    )

    # Đọc lại bằng openpyxl để kiểm tra cấu trúc
    wb = openpyxl.load_workbook(tmp_export_path, data_only=False)
    sheet_names = wb.sheetnames

    # Kiểm tra các sheet có mặt
    assert "Tổng hợp" in sheet_names
    assert "Lệch giá trị" in sheet_names
    assert "Thiếu trong DB" in sheet_names
    assert "Thiếu trong Excel" in sheet_names
    assert "Khớp" in sheet_names
    assert "Không hợp lệ" in sheet_names

    # Kiểm tra sheet "Lệch giá trị"
    mismatch_sheet = wb["Lệch giá trị"]
    # Hàng 1 là header
    headers = [cell.value for cell in mismatch_sheet[1]]
    assert (
        "INVOICE_NO" in headers
        or "Số hóa đơn" in headers
        or "Khóa" in headers
        or any("INVOICE" in str(h) for h in headers)
    )

    # Kiểm tra giá trị khóa giữ nguyên số 0 ở đầu ("0334") dạng text
    row_2_key_cell = mismatch_sheet.cell(row=2, column=1)
    assert row_2_key_cell.value == "0334"
    assert row_2_key_cell.data_type == "s"  # string type

    # Kiểm tra ô chênh lệch có fill màu nền #FDECEC
    # Tìm cột diff__TOTAL_AMOUNT
    diff_col_idx = None
    for idx, h in enumerate(headers, start=1):
        if "Chênh" in str(h) or "diff__" in str(h):
            diff_col_idx = idx
            break
    assert diff_col_idx is not None
    diff_cell = mismatch_sheet.cell(row=2, column=diff_col_idx)
    # Background fill của openpyxl
    fill = diff_cell.fill
    assert fill is not None
    # Mã màu FDECEC (bỏ #)
    expected_hex = COLOR_DIFF_BG.lstrip("#").upper()
    if fill.start_color and fill.start_color.rgb:
        assert expected_hex in str(fill.start_color.rgb).upper()

    # Kiểm tra sheet "Không hợp lệ"
    invalid_sheet = wb["Không hợp lệ"]
    assert invalid_sheet.cell(row=2, column=1).value == 10

    Path(tmp_export_path).unlink(missing_ok=True)
