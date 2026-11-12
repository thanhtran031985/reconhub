"""Task 69 — normalize phía DB phải khớp cột theo tên cột DB (f.db).

Bối cảnh: run #1033 (template SMP) lỗi Polars
    could not append value: 2026-07-08 of type: date to the builder
khi `compare()` dựng kết quả từ 2 phía.

Cơ chế (đã tái hiện end-to-end, xem test_pipeline_...):
- Field ngày của template SMP có tên logic khác tên cột DB
  (vd: field "NGAY_HD", db "INVOICE_DATE", type "date").
- Phía Excel: resolve_columns map về "NGAY_HD" -> normalize -> `date`,
  rồi pipeline alias thành "INVOICE_DATE" (Date).
- Phía DB: `normalize(db_raw, side="db")` chỉ khớp cột theo tên field
  (f.name) nên cột "INVOICE_DATE" (datetime thô từ Oracle) KHÔNG được
  chuẩn hóa, giữ nguyên Datetime.
- `aggregate()` cho ra excel_agg Date / db_agg Datetime; `compare()`
  gộp 2 phía vào cùng cột INVOICE_DATE của result_rows (date ở dòng
  Excel, datetime ở dòng chỉ có trong DB) -> `pl.from_dicts` lỗi đúng
  message của run #1033 (traceback: compare.py:290, qua pipeline.py:253).

Sửa ở `normalize()`: khi side="db", khớp cột theo f.db nữa (ngoài f.name),
để giá trị DB được chuẩn hóa theo đúng kiểu khai báo của field và 2 phía
cùng kiểu -> khóa khớp nhau, kết quả MATCHED thay vì crash.

LƯU Ý (lệch so với plan ban đầu): plan nói sửa 3 chỗ `pl.from_dicts`
trong filters.py, nhưng kiểm chứng cho thấy các chỗ đó KHÔNG thể lỗi:
`rows` ở đó lấy từ `df.to_dicts()` nên giá trị luôn khớp với `df.schema`
(một DataFrame Polars không thể chứa `date` trong cột Datetime — mọi
đường dựng frame hoặc upcast, hoặc lỗi ngay lúc dựng). Lỗi thật nằm ở
`compare()` (trộn 2 phía), gốc là `normalize()` bỏ qua cột DB.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl

from app.engine.normalize import normalize
from app.engine.pipeline import run_pipeline
from app.schemas.template_config import FieldSpec, TemplateConfig


class _Fetcher:
    """Giả lập Oracle đã GROUP BY sẵn (pushdown), INVOICE_DATE là datetime."""

    def __init__(self, df: pl.DataFrame):
        self.df = df

    def fetch_df(self, conn, sql, binds):
        return self.df


def _smp_config(field_name: str = "NGAY_HD", date_type: str = "date") -> TemplateConfig:
    """Config kiểu SMP: group_by [INVOICE_NO, INVOICE_DATE], lọc theo INVOICE_DATE.

    field_name: tên logic của trường ngày (khác tên cột DB khi = "NGAY_HD").
    """
    return TemplateConfig.model_validate(
        {
            "schema_version": 1,
            "file": {
                "sheet": "Sheet1",
                "header_row": 1,
                "data_start_row": 2,
                "skip_footer_rows": 0,
                "row_filters": {"drop_if": [], "keep_if": []},
                "thousand_sep": ",",
                "decimal_sep": ".",
            },
            "fields": [
                {"name": "INVOICE_NO", "label": "So HD", "excel": "INVOICE_NO", "type": "text", "db": "INVOICE_NO"},
                {
                    "name": field_name,
                    "label": "Ngay HD",
                    "excel": "INVOICE_DATE",
                    "type": date_type,
                    "db": "INVOICE_DATE",
                },
                {
                    "name": "TOTAL_AMOUNT",
                    "label": "Tien",
                    "excel": "TOTAL_AMOUNT",
                    "type": "number",
                    "db": "TOTAL_AMOUNT",
                },
            ],
            "db_source": {
                "kind": "table",
                "table": "DATARAW.FACT_BILL",
                "filters": [
                    {"param": "p_from", "column": "INVOICE_DATE", "op": ">=", "cast": "none"},
                    {"param": "p_to", "column": "INVOICE_DATE", "op": "<=", "cast": "none"},
                    {"param": "p_org", "column": "ORG_CODE", "op": "=", "cast": "none"},
                ],
                "static_where": [{"column": "APPLICATION", "op": "=", "value": "SMP"}],
                "params": [
                    {"name": "p_from", "type": "datetime", "source": "user", "label": "Tu ngay", "required": True},
                    {"name": "p_to", "type": "datetime", "source": "user", "label": "Den ngay", "required": True},
                    {
                        "name": "p_org",
                        "type": "text",
                        "source": "default",
                        "default": "BDP",
                        "label": "Don vi",
                        "required": True,
                    },
                ],
                "pushdown_aggregate": True,
            },
            "time_filter": {
                "excel_field": field_name,
                "db_column": "INVOICE_DATE",
                "granularity": "date",
            },
            "profiles": [
                {
                    "name": "BY_INVOICE",
                    "code": "BY_INVOICE",
                    "label": "Theo HD",
                    "group_by": ["INVOICE_NO", "INVOICE_DATE"],
                    "measures": [
                        {
                            "name": "TOTAL_AMOUNT",
                            "label": "Tong tien",
                            "agg": "sum",
                            "field": "TOTAL_AMOUNT",
                        }
                    ],
                    "is_default": True,
                }
            ],
        }
    )


def _smp_excel(tmp_path: Path) -> Path:
    """File Excel kiểu SMP: 3 hóa đơn tháng 7/2026."""
    path = tmp_path / "smp.xlsx"
    pl.DataFrame(
        {
            "INVOICE_NO": ["INV-001", "INV-002", "INV-003"],
            "INVOICE_DATE": [date(2026, 7, 8), date(2026, 7, 9), date(2026, 7, 10)],
            "TOTAL_AMOUNT": [100, 200, 300],
        }
    ).write_excel(path)
    return path


def _smp_db() -> pl.DataFrame:
    """Dữ liệu DB đã pushdown: INVOICE_DATE là datetime (Oracle DATE).

    INV-001 khớp Excel, INV-999 chỉ có trong DB -> result_rows trộn
    date (dòng Excel) và datetime (dòng DB) nếu 2 phía khác kiểu.
    """
    return pl.DataFrame(
        [
            {
                "INVOICE_NO": "INV-001",
                "INVOICE_DATE": datetime(2026, 7, 8, 10, 30),
                "TOTAL_AMOUNT": Decimal("100"),
                "LINE_CNT": 1,
            },
            {
                "INVOICE_NO": "INV-999",
                "INVOICE_DATE": datetime(2026, 7, 9, 11, 0),
                "TOTAL_AMOUNT": Decimal("999"),
                "LINE_CNT": 1,
            },
        ]
    )


def _run_smp(tmp_path: Path, cfg: TemplateConfig) -> dict[str, dict[str, object]]:
    res = run_pipeline(
        excel_path=_smp_excel(tmp_path),
        config=cfg,
        profile_code="BY_INVOICE",
        params={
            "p_from": "2026-07-01 00:00:00",
            "p_to": "2026-07-31 23:59:59",
            "p_org": "BDP",
            "apply_range_excel": True,
        },
        fetcher=_Fetcher(_smp_db()),
    )
    return {str(r["KEY_TEXT"]): r for r in res.result_df.to_dicts()}


def test_pipeline_smp_field_name_differs_from_db_column(tmp_path: Path) -> None:
    """Tên field ngày (NGAY_HD) khác tên cột DB (INVOICE_DATE) -> không crash.

    Trước sửa: lỗi Polars đúng như run #1033
    (could not append value: 2026-07-08 of type: date to the builder).
    Sau sửa: DB cũng chuẩn hóa về `date` nên khóa khớp, INV-001 MATCHED.
    """
    rows = _run_smp(tmp_path, _smp_config(field_name="NGAY_HD", date_type="date"))
    assert rows["INV-001 | 2026-07-08"]["STATUS"] == "MATCHED"
    assert rows["INV-001 | 2026-07-08"]["d__TOTAL_AMOUNT"] == Decimal("100")
    assert rows["INV-999 | 2026-07-09"]["STATUS"] == "MISSING_IN_EXCEL"
    assert rows["INV-002 | 2026-07-09"]["STATUS"] == "MISSING_IN_DB"


def test_pipeline_smp_matching_names_still_ok(tmp_path: Path) -> None:
    """Hồi quy: tên field trùng tên cột DB thì vẫn chạy như trước."""
    rows = _run_smp(tmp_path, _smp_config(field_name="INVOICE_DATE", date_type="date"))
    assert rows["INV-001 | 2026-07-08"]["STATUS"] == "MATCHED"
    assert rows["INV-999 | 2026-07-09"]["STATUS"] == "MISSING_IN_EXCEL"


def test_normalize_db_side_matches_column_by_db_name() -> None:
    """normalize(side='db') chuẩn hóa cột mang tên cột DB (f.db)."""
    fields = [
        FieldSpec(name="NGAY_HD", label="Ngay HD", excel="INVOICE_DATE", type="date", db="INVOICE_DATE"),
        FieldSpec(name="TOTAL_AMOUNT", label="Tien", excel="TOTAL_AMOUNT", type="number", db="TOTAL_AMOUNT"),
    ]
    df = pl.DataFrame(
        {
            "INVOICE_NO": ["INV-001"],
            "INVOICE_DATE": [datetime(2026, 7, 8, 10, 30)],
            "TOTAL_AMOUNT": [Decimal("100")],
        }
    )
    valid_df, invalid_df = normalize(df, fields, side="db")
    assert len(invalid_df) == 0
    assert valid_df.schema["INVOICE_DATE"] == pl.Date
    assert valid_df["INVOICE_DATE"][0] == date(2026, 7, 8)


def test_normalize_db_side_datetime_field_keeps_datetime() -> None:
    """Field type 'datetime' với cột tên DB -> giữ nguyên datetime."""
    fields = [
        FieldSpec(name="NGAY_HD", label="Ngay HD", excel="INVOICE_DATE", type="datetime", db="INVOICE_DATE"),
    ]
    df = pl.DataFrame({"INVOICE_DATE": [datetime(2026, 7, 8, 10, 30)]})
    valid_df, invalid_df = normalize(df, fields, side="db")
    assert len(invalid_df) == 0
    assert valid_df.schema["INVOICE_DATE"] == pl.Datetime("us")
    assert valid_df["INVOICE_DATE"][0] == datetime(2026, 7, 8, 10, 30)


def test_normalize_excel_side_ignores_db_name() -> None:
    """Phía Excel: cột chỉ trùng tên cột DB (không phải tên field) thì giữ nguyên.

    Hành vi cũ không đổi — chỉ phía DB mới khớp theo f.db.
    """
    fields = [
        FieldSpec(name="NGAY_HD", label="Ngay HD", excel="INVOICE_DATE", type="date", db="INVOICE_DATE"),
    ]
    df = pl.DataFrame({"INVOICE_DATE": ["2026-07-08"]})
    valid_df, invalid_df = normalize(df, fields, side="excel")
    assert len(invalid_df) == 0
    # Không được chuẩn hóa -> vẫn là chuỗi thô như cũ.
    assert valid_df.schema["INVOICE_DATE"] == pl.Utf8
    assert valid_df["INVOICE_DATE"][0] == "2026-07-08"


def test_normalize_db_side_name_and_db_columns_both_normalized() -> None:
    """Cả 2 cột (tên field và tên cột DB) cùng có mặt thì đều được chuẩn hóa."""
    fields = [
        FieldSpec(name="NGAY_HD", label="Ngay HD", excel="INVOICE_DATE", type="date", db="INVOICE_DATE"),
    ]
    df = pl.DataFrame(
        {
            "NGAY_HD": [datetime(2026, 7, 8, 9, 0)],
            "INVOICE_DATE": [datetime(2026, 7, 9, 10, 30)],
        }
    )
    valid_df, invalid_df = normalize(df, fields, side="db")
    assert len(invalid_df) == 0
    assert valid_df["NGAY_HD"][0] == date(2026, 7, 8)
    assert valid_df["INVOICE_DATE"][0] == date(2026, 7, 9)
