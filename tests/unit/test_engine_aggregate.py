from __future__ import annotations

from decimal import Decimal

import polars as pl

from app.engine.aggregate import aggregate
from app.schemas.template_config import MeasureSpec, ProfileSpec


def test_aggregate_standard_measures() -> None:
    data = [
        {"INVOICE_NO": "INV-001", "AMOUNT": Decimal("100.50"), "QTY": Decimal("2"), "INV_DATE": "2026-02-01", "__row_no": 2},
        {"INVOICE_NO": "INV-001", "AMOUNT": Decimal("200.25"), "QTY": Decimal("3"), "INV_DATE": "2026-02-01", "__row_no": 3},
        {"INVOICE_NO": "INV-002", "AMOUNT": Decimal("50.00"), "QTY": Decimal("1"), "INV_DATE": "2026-02-01", "__row_no": 4},
    ]
    df = pl.DataFrame(data)

    profile = ProfileSpec(
        code="BY_INVOICE",
        name="Theo số hóa đơn",
        aggregate=True,
        group_by=["INVOICE_NO"],
        measures=[
            MeasureSpec(name="TOTAL_AMOUNT", label="Tổng tiền", agg="sum", field="AMOUNT", compare="abs_tol", round=2),
            MeasureSpec(name="TOTAL_QTY", label="Số lượng", agg="sum", field="QTY", compare="exact", round=0),
            MeasureSpec(name="INV_DATE", label="Ngày HĐ", agg="first_distinct", field="INV_DATE", compare="exact"),
            MeasureSpec(name="LINE_CNT", label="Số dòng", agg="count", compare="display_only"),
        ],
    )

    agg_df = aggregate(df, profile)
    assert len(agg_df) == 2

    # Tìm dòng INV-001
    inv1 = agg_df.filter(pl.col("INVOICE_NO") == "INV-001").to_dicts()[0]
    assert inv1["__key"] == "INV-001"
    assert inv1["KEY_TEXT"] == "INV-001"
    assert inv1["TOTAL_AMOUNT"] == Decimal("300.75")
    assert inv1["TOTAL_QTY"] == Decimal("5")
    assert inv1["INV_DATE"] == "2026-02-01"
    assert inv1["LINE_CNT"] == 2
    assert inv1["__row_nos"] == [2, 3]
    assert inv1["__rows"] == 2
    assert inv1["__is_inconsistent"] is False
    assert inv1["__is_duplicate"] is False

    # Tìm dòng INV-002
    inv2 = agg_df.filter(pl.col("INVOICE_NO") == "INV-002").to_dicts()[0]
    assert inv2["TOTAL_AMOUNT"] == Decimal("50.00")
    assert inv2["LINE_CNT"] == 1
    assert inv2["__row_nos"] == [4]
    assert inv2["__rows"] == 1


def test_aggregate_multiple_group_by() -> None:
    data = [
        {"INV_DATE": "2026-02-01", "POINT": "BDP", "AMOUNT": Decimal("100"), "__row_no": 2},
        {"INV_DATE": "2026-02-01", "POINT": "BD5", "AMOUNT": Decimal("200"), "__row_no": 3},
    ]
    df = pl.DataFrame(data)

    profile = ProfileSpec(
        code="BY_DAY_POINT",
        name="Ngày × Điểm",
        aggregate=True,
        group_by=["INV_DATE", "POINT"],
        measures=[
            MeasureSpec(name="TOTAL_AMOUNT", label="Tổng tiền", agg="sum", field="AMOUNT"),
        ],
    )

    agg_df = aggregate(df, profile)
    assert len(agg_df) == 2
    row1 = agg_df.filter(pl.col("POINT") == "BDP").to_dicts()[0]
    assert row1["__key"] == "2026-02-01\x1fBDP"
    assert row1["KEY_TEXT"] == "2026-02-01 | BDP"
    assert row1["TOTAL_AMOUNT"] == Decimal("100")


def test_aggregate_first_distinct_inconsistent_g07() -> None:
    # G07: 1 HĐ có 2 ngày khác nhau -> INCONSISTENT
    data = [
        {"INVOICE_NO": "INV-G07", "INV_DATE": "2026-02-01", "AMOUNT": Decimal("100"), "__row_no": 2},
        {"INVOICE_NO": "INV-G07", "INV_DATE": "2026-02-02", "AMOUNT": Decimal("200"), "__row_no": 3},
    ]
    df = pl.DataFrame(data)

    profile = ProfileSpec(
        code="BY_INVOICE",
        name="Theo số hóa đơn",
        aggregate=True,
        group_by=["INVOICE_NO"],
        measures=[
            MeasureSpec(name="TOTAL_AMOUNT", label="Tổng tiền", agg="sum", field="AMOUNT"),
            MeasureSpec(name="INV_DATE", label="Ngày HĐ", agg="first_distinct", field="INV_DATE"),
        ],
    )

    agg_df = aggregate(df, profile)
    assert len(agg_df) == 1
    row = agg_df.to_dicts()[0]
    assert row["__is_inconsistent"] is True
    assert row["__is_duplicate"] is False
    assert row["__row_nos"] == [2, 3]


def test_aggregate_false_duplicate_g08() -> None:
    # G08: profile.aggregate = False, khóa lặp -> DUPLICATE
    data = [
        {"INVOICE_NO": "INV-DUP", "AMOUNT": Decimal("100"), "__row_no": 2},
        {"INVOICE_NO": "INV-DUP", "AMOUNT": Decimal("200"), "__row_no": 3},
        {"INVOICE_NO": "INV-UNIQUE", "AMOUNT": Decimal("300"), "__row_no": 4},
    ]
    df = pl.DataFrame(data)

    profile = ProfileSpec(
        code="NO_AGG",
        name="Không gộp",
        aggregate=False,
        group_by=["INVOICE_NO"],
        measures=[
            MeasureSpec(name="AMOUNT", label="Thành tiền", agg="value", field="AMOUNT"),
        ],
    )

    agg_df = aggregate(df, profile)
    assert len(agg_df) == 3

    dup_rows = agg_df.filter(pl.col("INVOICE_NO") == "INV-DUP").to_dicts()
    assert len(dup_rows) == 2
    for r in dup_rows:
        assert r["__is_duplicate"] is True

    unique_rows = agg_df.filter(pl.col("INVOICE_NO") == "INV-UNIQUE").to_dicts()
    assert len(unique_rows) == 1
    assert unique_rows[0]["__is_duplicate"] is False


def test_aggregate_count_distinct_min_max() -> None:
    data = [
        {"GRP": "G1", "TAG": "A", "VAL": Decimal("10"), "__row_no": 1},
        {"GRP": "G1", "TAG": "B", "VAL": Decimal("30"), "__row_no": 2},
        {"GRP": "G1", "TAG": "A", "VAL": Decimal("20"), "__row_no": 3},
    ]
    df = pl.DataFrame(data)

    profile = ProfileSpec(
        code="BY_GRP",
        name="Theo nhóm",
        aggregate=True,
        group_by=["GRP"],
        measures=[
            MeasureSpec(name="DIST_TAG", label="Số tag phân biệt", agg="count_distinct", field="TAG"),
            MeasureSpec(name="MIN_VAL", label="Min", agg="min", field="VAL"),
            MeasureSpec(name="MAX_VAL", label="Max", agg="max", field="VAL"),
        ],
    )

    agg_df = aggregate(df, profile)
    row = agg_df.to_dicts()[0]
    assert row["DIST_TAG"] == 2
    assert row["MIN_VAL"] == Decimal("10")
    assert row["MAX_VAL"] == Decimal("30")


def test_aggregate_db_pushdown() -> None:
    # Dữ liệu từ Oracle Pushdown aggregate đã có sẵn measure và INV_DATE__CNT_DIST
    data = [
        {"INVOICE_NO": "INV-P01", "TOTAL_AMOUNT": Decimal("100"), "INV_DATE": "2026-02-01", "INV_DATE__CNT_DIST": 1},
        {"INVOICE_NO": "INV-P02", "TOTAL_AMOUNT": Decimal("200"), "INV_DATE": "2026-02-01", "INV_DATE__CNT_DIST": 2},
    ]
    df = pl.DataFrame(data)

    profile = ProfileSpec(
        code="BY_INVOICE",
        name="Theo số hóa đơn",
        aggregate=True,
        group_by=["INVOICE_NO"],
        measures=[
            MeasureSpec(name="TOTAL_AMOUNT", label="Tổng tiền", agg="sum", field="AMOUNT"),
            MeasureSpec(name="INV_DATE", label="Ngày HĐ", agg="first_distinct", field="INV_DATE"),
        ],
    )

    agg_df = aggregate(df, profile, is_db_pushdown=True)
    assert len(agg_df) == 2

    row1 = agg_df.filter(pl.col("INVOICE_NO") == "INV-P01").to_dicts()[0]
    assert row1["__is_inconsistent"] is False
    assert row1["__key"] == "INV-P01"
    assert row1["KEY_TEXT"] == "INV-P01"

    row2 = agg_df.filter(pl.col("INVOICE_NO") == "INV-P02").to_dicts()[0]
    assert row2["__is_inconsistent"] is True


def test_aggregate_empty_df() -> None:
    df = pl.DataFrame(schema={"INVOICE_NO": pl.Utf8, "AMOUNT": pl.Decimal(38, 4)})
    profile = ProfileSpec(
        code="BY_INVOICE",
        name="Theo số hóa đơn",
        aggregate=True,
        group_by=["INVOICE_NO"],
        measures=[
            MeasureSpec(name="TOTAL_AMOUNT", label="Tổng tiền", agg="sum", field="AMOUNT"),
        ],
    )

    agg_df = aggregate(df, profile)
    assert len(agg_df) == 0
    assert "__key" in agg_df.columns
    assert "KEY_TEXT" in agg_df.columns
    assert "__is_inconsistent" in agg_df.columns
    assert "__is_duplicate" in agg_df.columns
