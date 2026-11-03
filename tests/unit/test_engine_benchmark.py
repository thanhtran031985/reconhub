from __future__ import annotations

import time
from decimal import Decimal

import polars as pl
import pytest

from app.engine.aggregate import aggregate
from app.engine.compare import compare
from app.schemas.template_config import MeasureSpec, ProfileSpec


@pytest.mark.bench
def test_engine_benchmark_200k_rows() -> None:
    n_rows = 200_000
    n_unique_keys = 100_000

    print(f"\n[BENCHMARK] Bat dau benchmark {n_rows:,} dong...")

    t0 = time.perf_counter()
    # Sinh du lieu tong hop 200.000 dong
    invoices = [f"INV_{i % n_unique_keys:06d}" for i in range(n_rows)]
    amounts = [Decimal("150.50")] * n_rows
    qtys = [Decimal("2")] * n_rows
    dates = ["2026-02-01"] * n_rows
    row_nos = list(range(1, n_rows + 1))

    excel_df = pl.DataFrame(
        {
            "INVOICE_NO": invoices,
            "AMOUNT": amounts,
            "QTY": qtys,
            "INV_DATE": dates,
            "__row_no": row_nos,
        }
    )

    db_df = pl.DataFrame(
        {
            "INVOICE_NO": [f"INV_{i:06d}" for i in range(n_unique_keys)],
            "AMOUNT": [Decimal("301.00")] * n_unique_keys,
            "QTY": [Decimal("4")] * n_unique_keys,
            "INV_DATE": ["2026-02-01"] * n_unique_keys,
        }
    )
    t_gen = time.perf_counter() - t0
    print(f"[BENCHMARK] Sinh du lieu 200k dong: {t_gen:.2f}s")

    profile = ProfileSpec(
        code="BY_INVOICE",
        name="Theo so hoa don",
        aggregate=True,
        group_by=["INVOICE_NO"],
        main_measure="TOTAL_AMOUNT",
        measures=[
            MeasureSpec(name="TOTAL_AMOUNT", label="Tong tien", agg="sum", field="AMOUNT", compare="exact", round=2),
            MeasureSpec(name="TOTAL_QTY", label="So luong", agg="sum", field="QTY", compare="exact", round=0),
            MeasureSpec(name="INV_DATE", label="Ngay HD", agg="first_distinct", field="INV_DATE", compare="exact"),
            MeasureSpec(name="LINE_CNT", label="So dong", agg="count", compare="display_only"),
        ],
    )

    # 1. Do Aggregate Excel
    t_agg_start = time.perf_counter()
    excel_agg = aggregate(excel_df, profile)
    t_agg_excel = time.perf_counter() - t_agg_start
    print(f"[BENCHMARK] Aggregate 200.000 dong Excel -> {len(excel_agg):,} nhom: {t_agg_excel:.2f}s")

    # 2. Do Aggregate DB
    t_db_start = time.perf_counter()
    db_agg = aggregate(db_df, profile)
    t_agg_db = time.perf_counter() - t_db_start
    print(f"[BENCHMARK] Aggregate 100.000 dong DB -> {len(db_agg):,} nhom: {t_agg_db:.2f}s")

    # 3. Do Compare
    t_cmp_start = time.perf_counter()
    res_df = compare(excel_agg, db_agg, profile)
    t_cmp = time.perf_counter() - t_cmp_start
    print(f"[BENCHMARK] Compare Full Outer Join 100.000 nhom: {t_cmp:.2f}s")

    total_time = t_agg_excel + t_agg_db + t_cmp
    print(f"[BENCHMARK] Tong thoi gian xu ly: {total_time:.2f}s")

    assert len(res_df) == n_unique_keys
    assert res_df["STATUS"].to_list().count("MATCHED") == n_unique_keys
    assert total_time < 30.0


@pytest.mark.bench
def test_engine_benchmark_1m_rows() -> None:
    n_rows = 1_000_000
    n_unique_keys = 500_000

    print("\n[BENCHMARK] Bat dau benchmark 1.000.000 dong (Spec 07 muc 5)...")

    t0 = time.perf_counter()
    # Sinh dữ liệu 1.000.000 dòng
    keys = pl.int_range(0, n_rows, eager=True) % n_unique_keys
    inv_series = ("INV_" + keys.cast(pl.Utf8).str.zfill(7)).alias("INVOICE_NO")
    amt_series = pl.Series("AMOUNT", [Decimal("100.00")] * n_rows)
    qty_series = pl.Series("QTY", [Decimal("1")] * n_rows)
    date_series = pl.Series("INV_DATE", ["2026-02-01"] * n_rows)
    row_no_series = pl.int_range(1, n_rows + 1, eager=True).alias("__row_no")

    excel_df = pl.DataFrame([inv_series, amt_series, qty_series, date_series, row_no_series])

    db_keys = pl.int_range(0, n_unique_keys, eager=True)
    db_inv = ("INV_" + db_keys.cast(pl.Utf8).str.zfill(7)).alias("INVOICE_NO")
    db_amt = pl.Series("AMOUNT", [Decimal("200.00")] * n_unique_keys)
    db_qty = pl.Series("QTY", [Decimal("2")] * n_unique_keys)
    db_date = pl.Series("INV_DATE", ["2026-02-01"] * n_unique_keys)

    db_df = pl.DataFrame([db_inv, db_amt, db_qty, db_date])
    t_gen = time.perf_counter() - t0
    print(f"[BENCHMARK] Sinh du lieu 1.000.000 dong: {t_gen:.2f}s")

    profile = ProfileSpec(
        code="BY_INVOICE",
        name="Theo so hoa don",
        aggregate=True,
        group_by=["INVOICE_NO"],
        main_measure="TOTAL_AMOUNT",
        measures=[
            MeasureSpec(name="TOTAL_AMOUNT", label="Tong tien", agg="sum", field="AMOUNT", compare="exact", round=2),
            MeasureSpec(name="TOTAL_QTY", label="So luong", agg="sum", field="QTY", compare="exact", round=0),
            MeasureSpec(name="INV_DATE", label="Ngay HD", agg="first_distinct", field="INV_DATE", compare="exact"),
            MeasureSpec(name="LINE_CNT", label="So dong", agg="count", compare="display_only"),
        ],
    )

    # 1. Đo Aggregate Excel (1.000.000 dòng)
    t_agg_excel_start = time.perf_counter()
    excel_agg = aggregate(excel_df, profile)
    t_agg_excel = time.perf_counter() - t_agg_excel_start
    print(f"[BENCHMARK] Aggregate 1.000.000 dong Excel -> {len(excel_agg):,} nhom: {t_agg_excel:.2f}s")

    # 2. Đo Aggregate DB (500.000 dòng)
    t_agg_db_start = time.perf_counter()
    db_agg = aggregate(db_df, profile)
    t_agg_db = time.perf_counter() - t_agg_db_start
    print(f"[BENCHMARK] Aggregate 500.000 dong DB -> {len(db_agg):,} nhom: {t_agg_db:.2f}s")

    # 3. Đo Compare (500.000 nhóm)
    t_cmp_start = time.perf_counter()
    res_df = compare(excel_agg, db_agg, profile)
    t_cmp = time.perf_counter() - t_cmp_start
    print(f"[BENCHMARK] Compare Full Outer Join 500.000 nhom: {t_cmp:.2f}s")

    total_engine_time = t_agg_excel + t_agg_db + t_cmp
    print(f"[BENCHMARK] Tong thoi gian xu ly loi engine: {total_engine_time:.2f}s")

    assert len(res_df) == n_unique_keys
    assert res_df["STATUS"].to_list().count("MATCHED") == n_unique_keys
    assert total_engine_time < 120.0, f"Thoi gian xu ly ({total_engine_time:.2f}s) vuot qua 120s"
