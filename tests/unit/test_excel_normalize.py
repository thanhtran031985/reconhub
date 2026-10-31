from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl

from app.engine.mapping import resolve_columns
from app.engine.normalize import derive, normalize
from app.engine.reader import read_sheet
from app.schemas.template_config import DerivedExpr, DerivedSpec, FieldSpec, TemplateConfig

SAMPLE_PATH = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
SAMPLE_XLSX = Path("samples/dtp_sample_200.xlsx")


def test_normalize_sample_dtp() -> None:
    import json

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        cfg = TemplateConfig.model_validate(json.load(f))

    raw_df, _ = read_sheet(SAMPLE_XLSX, cfg.file)
    # Loại dòng tổng trước khi normalize (vì dòng tổng có Số hóa đơn = None)
    filtered_df = raw_df.filter(pl.col("Số hóa đơn").is_not_null())
    mapped_df, _ = resolve_columns(filtered_df, cfg.fields)

    valid_df, invalid_df = normalize(mapped_df, cfg.fields)

    # File có đúng 200 dòng hóa đơn hợp lệ
    assert valid_df.height == 200
    assert invalid_df.height == 0
    assert "__row_no" in valid_df.columns

    # Cột AMOUNT phải có kiểu Decimal
    assert isinstance(valid_df["AMOUNT"][0], Decimal)
    # Cột INV_DATETIME phải có kiểu datetime
    assert isinstance(valid_df["INV_DATETIME"][0], datetime)
    # STATUS value_map: 'HĐ Gốc' -> 'ORIGINAL'
    assert valid_df["STATUS"][0] == "ORIGINAL"


def test_golden_g04_excel_serial_date() -> None:
    # G04: Hỗ trợ ngày vừa là chuỗi dd/MM/yyyy HH:mm:ss vừa là số serial Excel (vd: 46054.375)
    df = pl.DataFrame(
        {
            "INV_DATETIME": ["01/02/2026 09:00:00", "46054.375"],
            "__row_no": [2, 3],
        }
    )

    fields = [
        FieldSpec(
            name="INV_DATETIME",
            label="Ngày lập HĐ",
            type="datetime",
            format="dd/MM/yyyy HH:mm:ss",
            required=True,
        )
    ]

    valid_df, invalid_df = normalize(df, fields)
    assert valid_df.height == 2
    assert invalid_df.height == 0
    assert valid_df["INV_DATETIME"][0] == datetime(2026, 2, 1, 9, 0, 0)
    assert isinstance(valid_df["INV_DATETIME"][1], datetime)
    assert valid_df["INV_DATETIME"][1].year == 2026


def test_golden_g09_invalid_rows_detection() -> None:
    # G09: Tiền 'abc', ngày sai định dạng, khóa bắt buộc rỗng
    df = pl.DataFrame(
        {
            "INVOICE_NO": ["C26TBD001", "C26TBD002", None],
            "INV_DATETIME": ["01/02/2026 09:00:00", "invalid_date", "01/02/2026 10:00:00"],
            "AMOUNT": ["150000", "not_a_number", "200000"],
            "__row_no": [2, 3, 4],
        }
    )

    fields = [
        FieldSpec(name="INVOICE_NO", label="Số HĐ", type="text", required=True),
        FieldSpec(name="INV_DATETIME", label="Ngày HĐ", type="datetime", format="dd/MM/yyyy HH:mm:ss", required=True),
        FieldSpec(name="AMOUNT", label="Tiền", type="number", required=True),
    ]

    valid_df, invalid_df = normalize(df, fields)
    assert valid_df.height == 1
    assert valid_df["INVOICE_NO"][0] == "C26TBD001"
    assert valid_df["__row_no"][0] == 2

    # 2 dòng vi phạm
    assert invalid_df.height == 2
    assert invalid_df["__row_no"][0] == 3
    assert "PARSE_DATE" in str(invalid_df["__invalid_reasons"][0])
    assert "PARSE_NUMBER" in str(invalid_df["__invalid_reasons"][0])

    assert invalid_df["__row_no"][1] == 4
    assert "MISSING_REQUIRED" in str(invalid_df["__invalid_reasons"][1])


def test_derive_trunc_day_and_concat() -> None:
    df = pl.DataFrame(
        {
            "INV_DATETIME": [datetime(2026, 2, 1, 14, 30, 0)],
            "CODE": ["INV"],
            "NUM": ["001"],
            "__row_no": [2],
        }
    )

    derived = [
        DerivedSpec(
            name="INV_DATE",
            label="Ngày HĐ",
            type="date",
            expr=DerivedExpr(fn="trunc_day", args=["INV_DATETIME"]),
        ),
        DerivedSpec(
            name="FULL_CODE",
            label="Mã đầy đủ",
            type="text",
            expr=DerivedExpr(fn="concat", args=["CODE", "-", "NUM"]),
        ),
    ]

    res_df = derive(df, derived)
    assert "INV_DATE" in res_df.columns
    assert res_df["INV_DATE"][0] == date(2026, 2, 1)
    assert "FULL_CODE" in res_df.columns
    assert res_df["FULL_CODE"][0] == "INV-001"
