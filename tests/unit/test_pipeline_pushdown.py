from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import polars as pl

from app.engine.pipeline import run_pipeline
from app.schemas.template_config import TemplateConfig


class _PushdownFetcher:
    """Giả lập Oracle đã GROUP BY sẵn theo đúng SQL pushdown của sql_builder.

    Các cột trả về là tên group_by và tên measure (TOTAL_AMOUNT...), không
    còn cột trường gốc (AMOUNT...). Đây là dạng dữ liệu thật mà đường chạy
    qua /runs/new nhận được khi pushdown_aggregate bật (mặc định).
    """

    def __init__(self, df: pl.DataFrame):
        self.df = df
        self.seen_sql: str | None = None

    def fetch_df(self, conn, sql, binds):
        self.seen_sql = sql
        return self.df


def _dtp_config() -> TemplateConfig:
    return TemplateConfig.model_validate(
        json.loads(Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json").read_text(encoding="utf-8"))
    )


def test_pipeline_pushdown_db_amounts_are_not_zero() -> None:
    """DB đã gộp sẵn từ Oracle thì measure DB phải là tổng thật, không phải 0.

    Tái hiện ảnh /runs/1012 tab Thiếu trong Excel: mọi nhóm chỉ có trong DB
    đều hiện cột DB = 0 dù chứng từ có trong DB. Nguyên nhân là pipeline
    gọi aggregate() mà không truyền is_db_pushdown, nên nó gộp lại theo tên
    trường gốc (AMOUNT) vốn không có trong DataFrame đã gộp sẵn, tổng SUM
    rơi về 0 cho mọi nhóm.
    """
    cfg = _dtp_config()
    assert cfg.db_source.pushdown_aggregate is True

    pushdown_db = pl.DataFrame(
        [
            {
                "INVOICE_NO": "DB-ONLY-001",
                "TOTAL_AMOUNT": Decimal("900000"),
                "TOTAL_QTY": Decimal("1"),
                "INV_DATE": "2026-02-01",
                "INV_DATE__CNT_DIST": 1,
                "LINE_CNT": 1,
            },
            {
                "INVOICE_NO": "DB-ONLY-002",
                "TOTAL_AMOUNT": Decimal("1425000"),
                "TOTAL_QTY": Decimal("2"),
                "INV_DATE": "2026-02-01",
                "INV_DATE__CNT_DIST": 1,
                "LINE_CNT": 1,
            },
        ]
    )
    fetcher = _PushdownFetcher(pushdown_db)

    res = run_pipeline(
        excel_path=Path("samples/dtp_sample_200.xlsx"),
        config=cfg,
        profile_code="BY_INVOICE",
        params={
            "p_from": "2026-02-01 00:00:00",
            "p_to": "2026-02-02 23:59:59",
            "apply_range_excel": True,
        },
        fetcher=fetcher,
    )

    # SQL thật sự đã pushdown (có GROUP BY) thì pipeline mới được dùng nhánh đó.
    assert fetcher.seen_sql is not None
    assert "GROUP BY" in fetcher.seen_sql

    rows = {r["KEY_TEXT"]: r for r in res.result_df.to_dicts()}
    assert rows["DB-ONLY-001"]["STATUS"] == "MISSING_IN_EXCEL"
    assert rows["DB-ONLY-001"]["d__TOTAL_AMOUNT"] == Decimal("900000")
    assert rows["DB-ONLY-002"]["STATUS"] == "MISSING_IN_EXCEL"
    assert rows["DB-ONLY-002"]["d__TOTAL_AMOUNT"] == Decimal("1425000")
