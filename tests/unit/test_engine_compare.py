from __future__ import annotations

from decimal import Decimal

import polars as pl

from app.engine.aggregate import aggregate
from app.engine.compare import compare
from app.schemas.template_config import MeasureSpec, ProfileSpec


def _make_sample_profile() -> ProfileSpec:
    return ProfileSpec(
        code="BY_INVOICE",
        name="Theo số hóa đơn",
        aggregate=True,
        group_by=["INVOICE_NO"],
        main_measure="TOTAL_AMOUNT",
        measures=[
            MeasureSpec(name="TOTAL_AMOUNT", label="Tổng tiền", agg="sum", field="AMOUNT", compare="abs_tol", tolerance=Decimal("1.0"), round=0),
            MeasureSpec(name="TOTAL_QTY", label="Số lượng", agg="sum", field="QTY", compare="exact", round=0),
            MeasureSpec(name="LINE_CNT", label="Số dòng", agg="count", compare="display_only"),
        ],
    )


def test_compare_full_outer_join_states() -> None:
    profile = _make_sample_profile()

    # Dữ liệu Excel
    excel_raw = pl.DataFrame([
        {"INVOICE_NO": "INV-MATCH", "AMOUNT": Decimal("100"), "QTY": Decimal("1"), "__row_no": 2},
        {"INVOICE_NO": "INV-DIFF", "AMOUNT": Decimal("100"), "QTY": Decimal("1"), "__row_no": 3},
        {"INVOICE_NO": "INV-MISS-DB", "AMOUNT": Decimal("50"), "QTY": Decimal("1"), "__row_no": 4},
    ])
    excel_agg = aggregate(excel_raw, profile)

    # Dữ liệu DB
    db_raw = pl.DataFrame([
        {"INVOICE_NO": "INV-MATCH", "AMOUNT": Decimal("100"), "QTY": Decimal("1")},
        {"INVOICE_NO": "INV-DIFF", "AMOUNT": Decimal("200"), "QTY": Decimal("1")},
        {"INVOICE_NO": "INV-MISS-EXCEL", "AMOUNT": Decimal("80"), "QTY": Decimal("2")},
    ])
    db_agg = aggregate(db_raw, profile)

    res_df = compare(excel_agg, db_agg, profile)
    assert len(res_df) == 4

    # INV-MATCH
    m_row = res_df.filter(pl.col("INVOICE_NO") == "INV-MATCH").to_dicts()[0]
    assert m_row["STATUS"] == "MATCHED"
    assert m_row["x__TOTAL_AMOUNT"] == Decimal("100")
    assert m_row["d__TOTAL_AMOUNT"] == Decimal("100")
    assert m_row["diff__TOTAL_AMOUNT"] == Decimal("0")
    assert m_row["x__LINE_CNT"] == 1
    assert m_row["d__LINE_CNT"] == 1

    # INV-DIFF
    diff_row = res_df.filter(pl.col("INVOICE_NO") == "INV-DIFF").to_dicts()[0]
    assert diff_row["STATUS"] == "MISMATCH"
    assert diff_row["x__TOTAL_AMOUNT"] == Decimal("100")
    assert diff_row["d__TOTAL_AMOUNT"] == Decimal("200")
    assert diff_row["diff__TOTAL_AMOUNT"] == Decimal("-100")
    assert diff_row["ABS_DIFF_MAIN"] == Decimal("100")

    # INV-MISS-DB
    miss_db = res_df.filter(pl.col("INVOICE_NO") == "INV-MISS-DB").to_dicts()[0]
    assert miss_db["STATUS"] == "MISSING_IN_DB"
    assert miss_db["x__TOTAL_AMOUNT"] == Decimal("50")
    assert miss_db["d__TOTAL_AMOUNT"] is None
    assert miss_db["diff__TOTAL_AMOUNT"] == Decimal("50")

    # INV-MISS-EXCEL
    miss_ex = res_df.filter(pl.col("INVOICE_NO") == "INV-MISS-EXCEL").to_dicts()[0]
    assert miss_ex["STATUS"] == "MISSING_IN_EXCEL"
    assert miss_ex["x__TOTAL_AMOUNT"] is None
    assert miss_ex["d__TOTAL_AMOUNT"] == Decimal("80")
    assert miss_ex["diff__TOTAL_AMOUNT"] == Decimal("-80")


def test_compare_inconsistent_priority() -> None:
    profile = ProfileSpec(
        code="BY_INVOICE",
        name="Theo hóa đơn",
        aggregate=True,
        group_by=["INVOICE_NO"],
        measures=[
            MeasureSpec(name="INV_DATE", label="Ngày HĐ", agg="first_distinct", field="INV_DATE"),
        ],
    )
    # Excel có inconsistent
    excel_raw = pl.DataFrame([
        {"INVOICE_NO": "INV-INC", "INV_DATE": "2026-02-01", "__row_no": 2},
        {"INVOICE_NO": "INV-INC", "INV_DATE": "2026-02-02", "__row_no": 3},
    ])
    excel_agg = aggregate(excel_raw, profile)

    db_raw = pl.DataFrame([
        {"INVOICE_NO": "INV-INC", "INV_DATE": "2026-02-01"},
    ])
    db_agg = aggregate(db_raw, profile)

    res_df = compare(excel_agg, db_agg, profile)
    row = res_df.to_dicts()[0]
    assert row["STATUS"] == "INCONSISTENT"


def test_compare_duplicate_priority() -> None:
    profile = ProfileSpec(
        code="NO_AGG",
        name="Không gộp",
        aggregate=False,
        group_by=["INVOICE_NO"],
        measures=[
            MeasureSpec(name="AMOUNT", label="Thành tiền", agg="value", field="AMOUNT"),
        ],
    )
    # Excel trùng khóa khi aggregate=False
    excel_raw = pl.DataFrame([
        {"INVOICE_NO": "INV-DUP", "AMOUNT": Decimal("100"), "__row_no": 2},
        {"INVOICE_NO": "INV-DUP", "AMOUNT": Decimal("100"), "__row_no": 3},
    ])
    excel_agg = aggregate(excel_raw, profile)

    db_raw = pl.DataFrame([
        {"INVOICE_NO": "INV-DUP", "AMOUNT": Decimal("100")},
    ])
    db_agg = aggregate(db_raw, profile)

    res_df = compare(excel_agg, db_agg, profile)
    for r in res_df.to_dicts():
        assert r["STATUS"] == "DUPLICATE"


def test_compare_tolerance_and_round_g10() -> None:
    profile = ProfileSpec(
        code="BY_KEY",
        name="Theo khóa",
        aggregate=True,
        group_by=["KEY"],
        measures=[
            MeasureSpec(name="M_ABS", label="M Abs", agg="sum", field="M_ABS", compare="abs_tol", tolerance=Decimal("2.0")),
            MeasureSpec(name="M_PCT", label="M Pct", agg="sum", field="M_PCT", compare="pct_tol", tolerance=Decimal("1.0")),
            MeasureSpec(name="M_ROUND", label="M Round", agg="sum", field="M_ROUND", compare="exact", round=0),
            MeasureSpec(name="M_NULL", label="M Null As Zero", agg="sum", field="M_NULL", compare="exact", null_as="zero"),
        ],
    )

    excel_raw = pl.DataFrame([
        {
            "KEY": "K1",
            "M_ABS": Decimal("101.5"),  # Chênh 1.5 <= 2.0 -> MATCH
            "M_PCT": Decimal("1008.0"),  # Chênh 8 / 1008 = 0.79% <= 1% -> MATCH
            "M_ROUND": Decimal("50.4"),  # Làm tròn -> 50
            "M_NULL": None,  # null_as="zero" -> 0
            "__row_no": 2,
        },
        {
            "KEY": "K2",
            "M_ABS": Decimal("105.0"),  # Chênh 5.0 > 2.0 -> MISMATCH
            "M_PCT": Decimal("1000.0"),
            "M_ROUND": Decimal("50.0"),
            "M_NULL": Decimal("0"),
            "__row_no": 3,
        },
    ])
    excel_agg = aggregate(excel_raw, profile)

    db_raw = pl.DataFrame([
        {
            "KEY": "K1",
            "M_ABS": Decimal("100.0"),
            "M_PCT": Decimal("1000.0"),
            "M_ROUND": Decimal("49.6"),  # Làm tròn -> 50
            "M_NULL": Decimal("0"),
        },
        {
            "KEY": "K2",
            "M_ABS": Decimal("100.0"),
            "M_PCT": Decimal("1000.0"),
            "M_ROUND": Decimal("50.0"),
            "M_NULL": Decimal("0"),
        },
    ])
    db_agg = aggregate(db_raw, profile)

    res_df = compare(excel_agg, db_agg, profile)
    k1 = res_df.filter(pl.col("KEY") == "K1").to_dicts()[0]
    assert k1["STATUS"] == "MATCHED"

    k2 = res_df.filter(pl.col("KEY") == "K2").to_dicts()[0]
    assert k2["STATUS"] == "MISMATCH"


def test_compare_display_only_measure() -> None:
    profile = ProfileSpec(
        code="BY_KEY",
        name="Theo khóa",
        aggregate=True,
        group_by=["KEY"],
        measures=[
            MeasureSpec(name="AMOUNT", label="Tiền", agg="sum", field="AMOUNT", compare="exact"),
            MeasureSpec(name="NOTE", label="Ghi chú", agg="first_distinct", field="NOTE", compare="display_only"),
        ],
    )
    excel_raw = pl.DataFrame([{"KEY": "K1", "AMOUNT": Decimal("100"), "NOTE": "Note A", "__row_no": 2}])
    excel_agg = aggregate(excel_raw, profile)

    db_raw = pl.DataFrame([{"KEY": "K1", "AMOUNT": Decimal("100"), "NOTE": "Note B"}])
    db_agg = aggregate(db_raw, profile)

    res_df = compare(excel_agg, db_agg, profile)
    k1 = res_df.to_dicts()[0]
    assert k1["STATUS"] == "MATCHED"
    assert k1["x__NOTE"] == "Note A"
    assert k1["d__NOTE"] == "Note B"


def test_compare_sorting_order() -> None:
    profile = ProfileSpec(
        code="BY_KEY",
        name="Theo khóa",
        aggregate=True,
        group_by=["KEY"],
        main_measure="AMOUNT",
        measures=[
            MeasureSpec(name="AMOUNT", label="Tiền", agg="sum", field="AMOUNT", compare="exact"),
        ],
    )
    # Gồm: 1 MATCHED, 2 MISMATCH (lệch 50 và lệch 200), 1 MISSING_IN_DB
    excel_raw = pl.DataFrame([
        {"KEY": "K_MATCH", "AMOUNT": Decimal("100"), "__row_no": 1},
        {"KEY": "K_DIFF_SMALL", "AMOUNT": Decimal("150"), "__row_no": 2},
        {"KEY": "K_DIFF_LARGE", "AMOUNT": Decimal("300"), "__row_no": 3},
        {"KEY": "K_MISS_DB", "AMOUNT": Decimal("70"), "__row_no": 4},
    ])
    excel_agg = aggregate(excel_raw, profile)

    db_raw = pl.DataFrame([
        {"KEY": "K_MATCH", "AMOUNT": Decimal("100")},
        {"KEY": "K_DIFF_SMALL", "AMOUNT": Decimal("100")},
        {"KEY": "K_DIFF_LARGE", "AMOUNT": Decimal("100")},
    ])
    db_agg = aggregate(db_raw, profile)

    res_df = compare(excel_agg, db_agg, profile)
    keys_in_order = res_df["KEY"].to_list()
    # Thứ tự ưu tiên: MISSING_IN_DB > MISMATCH (|diff| giảm dần: K_DIFF_LARGE rồi K_DIFF_SMALL) > MATCHED
    assert keys_in_order == ["K_MISS_DB", "K_DIFF_LARGE", "K_DIFF_SMALL", "K_MATCH"]
