from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from app.engine.mapping import detect_template, resolve_columns
from app.engine.reader import read_sheet
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import FieldSpec, TemplateConfig

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
SAMPLE_XLSX = Path("samples/dtp_sample_200.xlsx")


def get_sample_config() -> TemplateConfig:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TemplateConfig.model_validate(data)


def test_resolve_columns_sample_dtp() -> None:
    cfg = get_sample_config()
    df, _ = read_sheet(SAMPLE_XLSX, cfg.file)

    mapped_df, rename_map = resolve_columns(df, cfg.fields)

    # Các cột logic phải xuất hiện trong dataframe
    assert "INVOICE_NO" in mapped_df.columns
    assert "INV_DATETIME" in mapped_df.columns
    assert "AMOUNT" in mapped_df.columns
    assert "__row_no" in mapped_df.columns

    # Kiểm tra map ngược lại cột gốc
    assert rename_map["INVOICE_NO"] == "Số hóa đơn"
    assert rename_map["AMOUNT"] == "Thành tiền"


def test_resolve_columns_with_alias_and_case_insensitivity() -> None:
    # Header viết hoa/thường khác nhau và dùng alias
    df = pl.DataFrame(
        {
            "số  hóa  đơn": ["C26TBD001"],  # dư khoảng trắng
            "MÃ GIAO DỊCH ALIAS": ["TXN_01"],
            "Thành tiền": ["100000"],
            "__row_no": [2],
        }
    )

    fields = [
        FieldSpec(
            name="INVOICE_NO",
            label="Số hóa đơn",
            excel="Số hóa đơn",
            type="text",
            required=True,
        ),
        FieldSpec(
            name="TXN_ID",
            label="Mã giao dịch",
            excel="Mã giao dịch",
            excel_aliases=["Mã giao dịch alias"],
            type="text",
        ),
        FieldSpec(
            name="AMOUNT",
            label="Thành tiền",
            excel="Thành tiền",
            type="number",
        ),
    ]

    mapped_df, rename_map = resolve_columns(df, fields)
    assert "INVOICE_NO" in mapped_df.columns
    assert "TXN_ID" in mapped_df.columns
    assert "AMOUNT" in mapped_df.columns
    assert mapped_df["TXN_ID"][0] == "TXN_01"


def test_resolve_columns_missing_required_column_raises_error() -> None:
    df = pl.DataFrame(
        {
            "Thành tiền": ["100000"],
            "__row_no": [2],
        }
    )

    fields = [
        FieldSpec(
            name="INVOICE_NO",
            label="Số hóa đơn",
            excel="Số hóa đơn",
            type="text",
            required=True,
        ),
    ]

    with pytest.raises(ServiceError) as exc:
        resolve_columns(df, fields)
    assert exc.value.code == ErrorCode.EXCEL_COLUMN_MISSING
    assert "Số hóa đơn" in exc.value.message


def test_detect_template_dtp_sample() -> None:
    cfg = get_sample_config()
    template_item = {
        "id": 1,
        "code": "DTP_HOA_DON_TAC_NGHIEP",
        "name": "Template DTP",
        "config": cfg.model_dump(),
    }

    matched = detect_template(SAMPLE_XLSX, [template_item])
    assert matched is not None
    assert matched["code"] == "DTP_HOA_DON_TAC_NGHIEP"


def test_detect_template_no_match(tmp_path) -> None:
    # File CSV có header không khớp bất kỳ template nào
    csv_file = tmp_path / "unknown.csv"
    csv_file.write_text("COL_A,COL_B,COL_C\n1,2,3\n", encoding="utf-8")

    cfg = get_sample_config()
    template_item = {
        "id": 1,
        "code": "DTP_HOA_DON_TAC_NGHIEP",
        "config": cfg.model_dump(),
    }

    matched = detect_template(csv_file, [template_item])
    assert matched is None


def test_resolve_columns_no_match_raises_error() -> None:
    """Khi file không khớp bất kỳ cột nào của template (ví dụ sai dòng header_row)."""
    df = pl.DataFrame(
        {
            "_COL_1": ["Title banner"],
            "_COL_2": ["None"],
            "__row_no": [1],
        }
    )
    fields = [
        FieldSpec(
            name="INVOICE_NO",
            label="Số hóa đơn",
            excel="Số HĐ",
            type="text",
            required=False,
        ),
        FieldSpec(
            name="TOTAL_AMOUNT",
            label="Tổng tiền",
            excel="Tổng Tiền",
            type="number",
            required=False,
        ),
    ]

    with pytest.raises(ServiceError) as exc:
        resolve_columns(df, fields)
    assert exc.value.code == ErrorCode.EXCEL_COLUMN_MISSING
    assert "header_row" in exc.value.message

