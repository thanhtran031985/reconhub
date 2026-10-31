from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import polars as pl
import pytest

from app.engine.pipeline import run_pipeline
from app.schemas.template_config import (
    DbSourceSpec,
    FieldSpec,
    FileSpec,
    MeasureSpec,
    ParamSpec,
    ProfileSpec,
    SourceFilter,
    TemplateConfig,
)


@pytest.fixture(scope="session")
def dtp_config() -> TemplateConfig:
    cfg_path = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return TemplateConfig.model_validate(data)


@pytest.fixture(scope="session")
def dtp_db_parquet() -> pl.DataFrame:
    parquet_path = Path("tests/golden/G01_dtp_by_invoice/db.parquet")
    return pl.read_parquet(parquet_path)


def make_test_config(
    fields: list[FieldSpec],
    profiles: list[ProfileSpec],
    sheet: str = "Sheet1",
    date_col: str = "CREATED_AT",
) -> TemplateConfig:
    if not any(p.is_default for p in profiles):
        profiles[0].is_default = True

    return TemplateConfig(
        file=FileSpec(sheet=sheet, header_row=1, data_start_row=2),
        fields=fields,
        db_source=DbSourceSpec(
            table="SRC_TABLE",
            filters=[
                SourceFilter(param="p_from", column=date_col, op=">="),
                SourceFilter(param="p_to", column=date_col, op="<="),
            ],
            params=[
                ParamSpec(name="p_from", type="datetime", source="user", label="Từ ngày", required=True),
                ParamSpec(name="p_to", type="datetime", source="user", label="Đến ngày", required=True),
            ],
        ),
        profiles=profiles,
    )


def test_golden_g01_dtp_by_invoice(dtp_config: TemplateConfig, dtp_db_parquet: pl.DataFrame) -> None:
    excel_path = Path("samples/dtp_sample_200.xlsx")
    params = {
        "p_from": "2026-02-01 00:00:00",
        "p_to": "2026-02-05 23:59:59",
        "p_org": "BDP",
    }

    res = run_pipeline(
        excel_path=excel_path,
        config=dtp_config,
        profile_code="BY_INVOICE",
        params=params,
        fetcher=dtp_db_parquet,
    )

    summary = res.summary
    assert res.control_total is not None
    assert res.control_total.is_matched is True
    assert res.control_total.file_total == Decimal("366732000")
    assert res.control_total.calc_total == Decimal("366732000")

    assert summary["CNT_MATCHED"] == 184
    assert summary["CNT_MISMATCH"] == 4
    assert summary["CNT_MISSING_IN_DB"] == 2
    assert summary["CNT_MISSING_IN_EXCEL"] == 2
    assert summary["CNT_INCONSISTENT"] == 0
    assert summary["CNT_DUPLICATE"] == 0

    mismatch_rows = res.result_df.filter(pl.col("STATUS") == "MISMATCH").to_dicts()
    mismatch_invs = {r["INVOICE_NO"] for r in mismatch_rows}
    assert mismatch_invs == {
        "C26TBD0031338",
        "C26TBD0031375",
        "C26TBD0031412",
        "C26TBD0031350",
    }

    missing_db_rows = res.result_df.filter(pl.col("STATUS") == "MISSING_IN_DB").to_dicts()
    missing_db_invs = {r["INVOICE_NO"] for r in missing_db_rows}
    assert missing_db_invs == {"C26TBD0031435", "C26TBD0031485"}

    missing_ex_rows = res.result_df.filter(pl.col("STATUS") == "MISSING_IN_EXCEL").to_dicts()
    missing_ex_invs = {r["INVOICE_NO"] for r in missing_ex_rows}
    assert missing_ex_invs == {"C26TBD0099901", "C26TBD0099902"}


def test_golden_g02_dtp_by_day_point(dtp_config: TemplateConfig, dtp_db_parquet: pl.DataFrame) -> None:
    excel_path = Path("samples/dtp_sample_200.xlsx")
    params = {
        "p_from": "2026-02-01 00:00:00",
        "p_to": "2026-02-05 23:59:59",
        "p_org": "BDP",
    }

    res = run_pipeline(
        excel_path=excel_path,
        config=dtp_config,
        profile_code="BY_DAY_POINT",
        params=params,
        fetcher=dtp_db_parquet,
    )

    summary = res.summary
    assert summary["EXCEL_GROUPS"] > 0
    assert summary["DB_GROUPS"] > 0
    total_classified = (
        summary["CNT_MATCHED"]
        + summary["CNT_MISMATCH"]
        + summary["CNT_MISSING_IN_DB"]
        + summary["CNT_MISSING_IN_EXCEL"]
    )
    assert total_classified == len(res.result_df)


def test_golden_g03_leading_zero() -> None:
    # G03: Cột mã số / mã thuế có số 0 ở đầu ("0334", "0304422444-021") không bị mất số 0
    with NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8", delete=False) as f:
        f.write("TAX_CODE,AMOUNT\n")
        f.write("0334,1000\n")
        f.write("0304422444-021,2000\n")
        tmp_csv = f.name

    fields = [
        FieldSpec(
            name="TAX_CODE",
            label="Mã số thuế",
            excel="TAX_CODE",
            db="TAX_CODE",
            type="text",
            norm=["trim"],
            required=True,
        ),
        FieldSpec(name="AMOUNT", label="Số tiền", excel="AMOUNT", db="AMOUNT", type="number"),
    ]
    profiles = [
        ProfileSpec(
            code="BY_TAX",
            name="Theo MST",
            group_by=["TAX_CODE"],
            measures=[MeasureSpec(name="AMOUNT", label="Số tiền", agg="sum", field="AMOUNT", compare="exact")],
        )
    ]
    cfg = make_test_config(fields, profiles, date_col="TAX_CODE")

    db_df = pl.DataFrame(
        [
            {"TAX_CODE": "0334", "AMOUNT": Decimal("1000")},
            {"TAX_CODE": "0304422444-021", "AMOUNT": Decimal("2000")},
        ]
    )

    res = run_pipeline(excel_path=tmp_csv, config=cfg, fetcher=db_df)
    assert res.summary["CNT_MATCHED"] == 2
    keys = res.result_df["KEY_TEXT"].to_list()
    assert "0334" in keys
    assert "0304422444-021" in keys


def test_golden_g04_excel_serial_date() -> None:
    # G04: Ngày serial và chuỗi lẫn nhau đều parse chính xác
    with NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8", delete=False) as f:
        f.write("INV_NO,INV_DATE,AMOUNT\n")
        f.write("INV-1,46054.5,100\n")  # Excel serial 46054.5
        f.write("INV-2,01/02/2026 12:00:00,200\n")  # String date
        tmp_csv = f.name

    fields = [
        FieldSpec(name="INV_NO", label="Số HĐ", excel="INV_NO", db="INV_NO", type="text", required=True),
        FieldSpec(
            name="INV_DATE",
            label="Ngày HĐ",
            excel="INV_DATE",
            db="INV_DATE",
            type="datetime",
            format="dd/MM/yyyy HH:mm:ss",
            required=True,
        ),
        FieldSpec(name="AMOUNT", label="Số tiền", excel="AMOUNT", db="AMOUNT", type="number"),
    ]
    profiles = [
        ProfileSpec(
            code="BY_INV",
            name="Theo HĐ",
            group_by=["INV_NO"],
            measures=[
                MeasureSpec(name="AMOUNT", label="Số tiền", agg="sum", field="AMOUNT", compare="exact"),
            ],
        )
    ]
    cfg = make_test_config(fields, profiles, date_col="INV_DATE")

    db_df = pl.DataFrame(
        [
            {"INV_NO": "INV-1", "AMOUNT": Decimal("100"), "INV_DATE": datetime(2026, 2, 1, 12, 0, 0)},
            {"INV_NO": "INV-2", "AMOUNT": Decimal("200"), "INV_DATE": datetime(2026, 2, 1, 12, 0, 0)},
        ]
    )

    res = run_pipeline(excel_path=tmp_csv, config=cfg, fetcher=db_df)
    assert res.summary["CNT_MATCHED"] == 2
    assert len(res.invalid_df) == 0


def test_golden_g05_footer_total(dtp_config: TemplateConfig, dtp_db_parquet: pl.DataFrame) -> None:
    # G05: Dòng footer tổng được nhận diện bởi control_total và loại khỏi data rows
    excel_path = Path("samples/dtp_sample_200.xlsx")
    params = {"p_from": "2026-02-01 00:00:00", "p_to": "2026-02-05 23:59:59", "p_org": "BDP"}
    res = run_pipeline(excel_path=excel_path, config=dtp_config, params=params, fetcher=dtp_db_parquet)

    assert res.control_total is not None
    assert res.control_total.is_matched is True
    assert res.control_total.located_row_no == 202


def test_golden_g06_time_range(dtp_config: TemplateConfig, dtp_db_parquet: pl.DataFrame) -> None:
    # G06: Lọc theo khoảng thời gian nhỏ hơn (chỉ ngày 01/02/2026) -> các dòng ngoài khoảng được đếm
    excel_path = Path("samples/dtp_sample_200.xlsx")
    params = {
        "p_from": "2026-02-01 00:00:00",
        "p_to": "2026-02-01 23:59:59",
        "p_org": "BDP",
    }
    res = run_pipeline(excel_path=excel_path, config=dtp_config, params=params, fetcher=dtp_db_parquet)
    assert res.summary["EXCEL_ROWS_OUT_OF_RANGE"] > 0


def test_golden_g07_inconsistent() -> None:
    # G07: 1 HĐ 2 ngày khác nhau -> trạng thái INCONSISTENT
    with NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8", delete=False) as f:
        f.write("INVOICE_NO,INV_DATE,AMOUNT\n")
        f.write("INV-INC,2026-02-01,100\n")
        f.write("INV-INC,2026-02-02,100\n")
        tmp_csv = f.name

    fields = [
        FieldSpec(name="INVOICE_NO", label="Số HĐ", excel="INVOICE_NO", db="INVOICE_NO", type="text", required=True),
        FieldSpec(name="INV_DATE", label="Ngày HĐ", excel="INV_DATE", db="INV_DATE", type="date", required=True),
        FieldSpec(name="AMOUNT", label="Số tiền", excel="AMOUNT", db="AMOUNT", type="number"),
    ]
    profiles = [
        ProfileSpec(
            code="BY_INV",
            name="Theo HĐ",
            group_by=["INVOICE_NO"],
            measures=[
                MeasureSpec(name="INV_DATE", label="Ngày HĐ", agg="first_distinct", field="INV_DATE", compare="exact"),
                MeasureSpec(name="AMOUNT", label="Số tiền", agg="sum", field="AMOUNT", compare="exact"),
            ],
        )
    ]
    cfg = make_test_config(fields, profiles, date_col="INV_DATE")

    db_df = pl.DataFrame(
        [
            {"INVOICE_NO": "INV-INC", "INV_DATE": "2026-02-01", "AMOUNT": Decimal("200")},
        ]
    )

    res = run_pipeline(excel_path=tmp_csv, config=cfg, fetcher=db_df)
    assert res.summary["CNT_INCONSISTENT"] == 1
    row = res.result_df.to_dicts()[0]
    assert row["STATUS"] == "INCONSISTENT"


def test_golden_g08_duplicate() -> None:
    # G08: profile.aggregate = False, khóa lặp -> DUPLICATE
    with NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8", delete=False) as f:
        f.write("INVOICE_NO,AMOUNT\n")
        f.write("INV-DUP,100\n")
        f.write("INV-DUP,100\n")
        tmp_csv = f.name

    fields = [
        FieldSpec(name="INVOICE_NO", label="Số HĐ", excel="INVOICE_NO", db="INVOICE_NO", type="text", required=True),
        FieldSpec(name="AMOUNT", label="Số tiền", excel="AMOUNT", db="AMOUNT", type="number"),
    ]
    profiles = [
        ProfileSpec(
            code="NO_AGG",
            name="Không gộp",
            aggregate=False,
            group_by=["INVOICE_NO"],
            measures=[
                MeasureSpec(name="AMOUNT", label="Số tiền", agg="value", field="AMOUNT", compare="exact"),
            ],
        )
    ]
    cfg = make_test_config(fields, profiles, date_col="INVOICE_NO")

    db_df = pl.DataFrame(
        [
            {"INVOICE_NO": "INV-DUP", "AMOUNT": Decimal("100")},
        ]
    )

    res = run_pipeline(excel_path=tmp_csv, config=cfg, fetcher=db_df)
    assert res.summary["CNT_DUPLICATE"] >= 1
    assert all(r["STATUS"] == "DUPLICATE" for r in res.result_df.to_dicts())


def test_golden_g09_invalid() -> None:
    # G09: Tiền "abc", ngày sai, khóa trống -> INVALID kèm số dòng
    with NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8", delete=False) as f:
        f.write("INVOICE_NO,INV_DATE,AMOUNT\n")
        f.write(",2026-02-01,100\n")  # Thiếu khóa required
        f.write("INV-OK,not_a_date,100\n")  # Ngày sai format
        f.write("INV-OK2,2026-02-01,abc\n")  # Tiền không phải số
        tmp_csv = f.name

    fields = [
        FieldSpec(name="INVOICE_NO", label="Số HĐ", excel="INVOICE_NO", db="INVOICE_NO", type="text", required=True),
        FieldSpec(name="INV_DATE", label="Ngày HĐ", excel="INV_DATE", db="INV_DATE", type="date", required=True),
        FieldSpec(name="AMOUNT", label="Số tiền", excel="AMOUNT", db="AMOUNT", type="number"),
    ]
    profiles = [
        ProfileSpec(
            code="BY_INV",
            name="Theo HĐ",
            group_by=["INVOICE_NO"],
            measures=[MeasureSpec(name="AMOUNT", label="Số tiền", agg="sum", field="AMOUNT", compare="exact")],
        )
    ]
    cfg = make_test_config(fields, profiles, date_col="INV_DATE")

    res = run_pipeline(excel_path=tmp_csv, config=cfg, fetcher=pl.DataFrame())
    assert res.summary["EXCEL_ROWS_INVALID"] == 3
    assert len(res.invalid_df) == 3


def test_golden_g10_tolerance() -> None:
    # G10: abs_tol, pct_tol, round, null_as
    with NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8", delete=False) as f:
        f.write("KEY,AMT_ABS,AMT_PCT,AMT_ROUND,AMT_NULL\n")
        f.write("K1,101.5,1008,50.4,\n")
        tmp_csv = f.name

    fields = [
        FieldSpec(name="KEY", label="Khóa", excel="KEY", db="KEY", type="text", required=True),
        FieldSpec(name="AMT_ABS", label="Amt Abs", excel="AMT_ABS", db="AMT_ABS", type="number"),
        FieldSpec(name="AMT_PCT", label="Amt Pct", excel="AMT_PCT", db="AMT_PCT", type="number"),
        FieldSpec(name="AMT_ROUND", label="Amt Round", excel="AMT_ROUND", db="AMT_ROUND", type="number"),
        FieldSpec(name="AMT_NULL", label="Amt Null", excel="AMT_NULL", db="AMT_NULL", type="number"),
    ]
    profiles = [
        ProfileSpec(
            code="BY_KEY",
            name="Theo Khóa",
            group_by=["KEY"],
            measures=[
                MeasureSpec(
                    name="AMT_ABS",
                    label="Amt Abs",
                    agg="sum",
                    field="AMT_ABS",
                    compare="abs_tol",
                    tolerance=Decimal("2.0"),
                ),
                MeasureSpec(
                    name="AMT_PCT",
                    label="Amt Pct",
                    agg="sum",
                    field="AMT_PCT",
                    compare="pct_tol",
                    tolerance=Decimal("1.0"),
                ),
                MeasureSpec(
                    name="AMT_ROUND", label="Amt Round", agg="sum", field="AMT_ROUND", compare="exact", round=0
                ),
                MeasureSpec(
                    name="AMT_NULL", label="Amt Null", agg="sum", field="AMT_NULL", compare="exact", null_as="zero"
                ),
            ],
        )
    ]
    cfg = make_test_config(fields, profiles, date_col="KEY")

    db_df = pl.DataFrame(
        [
            {
                "KEY": "K1",
                "AMT_ABS": Decimal("100.0"),
                "AMT_PCT": Decimal("1000.0"),
                "AMT_ROUND": Decimal("49.6"),
                "AMT_NULL": Decimal("0.0"),
            }
        ]
    )

    res = run_pipeline(excel_path=tmp_csv, config=cfg, fetcher=db_df)
    assert res.summary["CNT_MATCHED"] == 1


def test_golden_g11_value_map_filter() -> None:
    # G11: value_map STATUS ("HĐ Gốc" -> "ORIGINAL") + Profile filter STATUS == "ORIGINAL"
    with NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8", delete=False) as f:
        f.write("INV_NO,STATUS,AMOUNT\n")
        f.write("INV-1,HĐ Gốc,100\n")
        f.write("INV-2,HĐ Hủy,200\n")
        tmp_csv = f.name

    fields = [
        FieldSpec(name="INV_NO", label="Số HĐ", excel="INV_NO", db="INV_NO", type="text", required=True),
        FieldSpec(
            name="STATUS",
            label="Trạng thái",
            excel="STATUS",
            db="STATUS",
            type="text",
            norm=["trim", {"value_map": {"HĐ Gốc": "ORIGINAL", "HĐ Hủy": "CANCEL"}}],
        ),
        FieldSpec(name="AMOUNT", label="Số tiền", excel="AMOUNT", db="AMOUNT", type="number"),
    ]
    profiles = [
        ProfileSpec(
            code="BY_INV",
            name="Theo HĐ",
            group_by=["INV_NO"],
            filters=[{"field": "STATUS", "op": "=", "value": "ORIGINAL"}],
            measures=[MeasureSpec(name="AMOUNT", label="Số tiền", agg="sum", field="AMOUNT", compare="exact")],
        )
    ]
    cfg = make_test_config(fields, profiles, date_col="STATUS")

    db_df = pl.DataFrame(
        [
            {"INV_NO": "INV-1", "STATUS": "ORIGINAL", "AMOUNT": Decimal("100")},
            {"INV_NO": "INV-2", "STATUS": "CANCEL", "AMOUNT": Decimal("200")},
        ]
    )

    res = run_pipeline(excel_path=tmp_csv, config=cfg, fetcher=db_df)
    assert res.summary["CNT_MATCHED"] == 1
    assert len(res.result_df) == 1
    assert res.result_df.to_dicts()[0]["INV_NO"] == "INV-1"


def test_golden_g12_csv() -> None:
    # G12: CSV với dấu phân cách ';' và UTF-8-SIG
    with NamedTemporaryFile(suffix=".csv", mode="wb", delete=False) as f:
        content = "\ufeffMã HĐ;Ngày HĐ;Số tiền\nHD001;2026-02-01;1500000\nHD002;2026-02-01;2500000\n"
        f.write(content.encode("utf-8"))
        tmp_csv = f.name

    fields = [
        FieldSpec(name="INV_NO", label="Số HĐ", excel="Mã HĐ", db="INV_NO", type="text", required=True),
        FieldSpec(name="INV_DATE", label="Ngày HĐ", excel="Ngày HĐ", db="INV_DATE", type="date", required=True),
        FieldSpec(name="AMOUNT", label="Số tiền", excel="Số tiền", db="AMOUNT", type="number"),
    ]
    profiles = [
        ProfileSpec(
            code="BY_INV",
            name="Theo HĐ",
            group_by=["INV_NO"],
            measures=[MeasureSpec(name="AMOUNT", label="Số tiền", agg="sum", field="AMOUNT", compare="exact")],
        )
    ]
    cfg = make_test_config(fields, profiles, date_col="INV_DATE")

    db_df = pl.DataFrame(
        [
            {"INV_NO": "HD001", "INV_DATE": "2026-02-01", "AMOUNT": Decimal("1500000")},
            {"INV_NO": "HD002", "INV_DATE": "2026-02-01", "AMOUNT": Decimal("2500000")},
        ]
    )

    res = run_pipeline(excel_path=tmp_csv, config=cfg, fetcher=db_df)
    assert res.summary["CNT_MATCHED"] == 2
