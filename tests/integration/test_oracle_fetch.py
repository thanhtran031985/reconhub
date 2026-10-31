from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.engine import get_recon_engine
from app.db.metadata import recon_data_source
from app.engine.fetch import fetch_df
from app.engine.sql_builder import build_source_sql
from app.schemas.template_config import TemplateConfig
from app.services.source_conn import open_source_connection


@pytest.mark.oracle
def test_oracle_fetch_dtp_by_invoice() -> None:
    settings = get_settings()
    if not settings.ORACLE_TEST_HOST or not settings.ORACLE_TEST_USER:
        pytest.skip("Bỏ qua test Oracle: thiếu biến môi trường ORACLE_TEST_* hoặc không có VPN")

    # Lấy ID của Data Source ORACLE_TEST
    engine = get_recon_engine()
    with engine.connect() as conn:
        ds_rec = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.CODE == "ORACLE_TEST")).mappings().first()
        )

    if not ds_rec:
        pytest.skip("Chưa tạo Data Source ORACLE_TEST trong CSDL")

    # Đọc template mẫu
    tmpl_path = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
    tmpl_data = json.loads(tmpl_path.read_text(encoding="utf-8"))
    config = TemplateConfig.model_validate(tmpl_data)

    profile = next(p for p in config.profiles if p.code == "BY_INVOICE")
    params = {
        "p_from": datetime(2026, 2, 1, 0, 0, 0),
        "p_to": datetime(2026, 2, 5, 23, 59, 59),
        "p_org": "BDP",
    }

    sql, binds = build_source_sql(config, profile=profile, params=params)

    ora_conn = open_source_connection(int(ds_rec["ID"]))
    try:
        df = fetch_df(ora_conn, sql, binds)
        assert len(df) == 190
        assert "INVOICE_NO" in df.columns
        assert "TOTAL_AMOUNT" in df.columns
        assert "TOTAL_QTY" in df.columns
        assert "LINE_CNT" in df.columns
        assert "INV_DATE" in df.columns
    finally:
        ora_conn.close()
