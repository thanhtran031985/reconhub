from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.engine.sql_builder import build_source_sql
from app.schemas.template_config import TemplateConfig


@pytest.fixture
def dtp_template() -> TemplateConfig:
    path = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return TemplateConfig.model_validate(data)


def test_build_sql_profile_by_invoice(dtp_template: TemplateConfig) -> None:
    profile = next(p for p in dtp_template.profiles if p.code == "BY_INVOICE")
    params = {
        "p_from": datetime(2026, 2, 1, 0, 0, 0),
        "p_to": datetime(2026, 2, 5, 23, 59, 59),
        "p_org": "BDP",
    }

    sql, binds = build_source_sql(dtp_template, profile=profile, params=params)

    # Kiểm tra cấu trúc câu lệnh bọc ngoài
    assert "GROUP BY" in sql
    assert "FROM (" in sql
    assert ") src" in sql

    # Kiểm tra các measures gộp
    assert 'SUM("src"."AMOUNT") AS "TOTAL_AMOUNT"' in sql
    assert 'SUM("src"."QUANTITY") AS "TOTAL_QTY"' in sql
    assert 'COUNT(*) AS "LINE_CNT"' in sql
    # first_distinct trên INV_DATE
    assert 'MIN(TRUNC("src"."INVOICE_DATE")) AS "INV_DATE"' in sql
    assert 'COUNT(DISTINCT TRUNC("src"."INVOICE_DATE")) AS "INV_DATE__CNT_DIST"' in sql

    # Kiểm tra group by
    assert "GROUP BY" in sql
    assert 'UPPER(TRIM("src"."INVOICE_NO"))' in sql


def test_build_sql_profile_by_day_point(dtp_template: TemplateConfig) -> None:
    profile = next(p for p in dtp_template.profiles if p.code == "BY_DAY_POINT")
    params = {
        "p_from": datetime(2026, 2, 1, 0, 0, 0),
        "p_to": datetime(2026, 2, 5, 23, 59, 59),
        "p_org": "BDP",
    }

    sql, binds = build_source_sql(dtp_template, profile=profile, params=params)

    assert "GROUP BY" in sql
    assert 'TRUNC("src"."INVOICE_DATE")' in sql
    assert 'UPPER(TRIM("src"."COLLECT_POINT"))' in sql
    assert 'COUNT(DISTINCT UPPER(TRIM("src"."INVOICE_NO"))) AS "INV_CNT"' in sql


def test_build_sql_profile_by_line(dtp_template: TemplateConfig) -> None:
    profile = next(p for p in dtp_template.profiles if p.code == "BY_LINE")
    params = {
        "p_from": datetime(2026, 2, 1, 0, 0, 0),
        "p_to": datetime(2026, 2, 5, 23, 59, 59),
        "p_org": "BDP",
    }

    sql, binds = build_source_sql(dtp_template, profile=profile, params=params)

    assert "GROUP BY" in sql
    assert 'UPPER(TRIM("src"."INVOICE_NO"))' in sql
    assert 'UPPER(TRIM("src"."SERVICE_CODE"))' in sql
    assert 'TRIM("src"."PIN_NO")' in sql
    assert 'SUM("src"."AMOUNT") AS "AMOUNT"' in sql
    assert 'SUM("src"."QUANTITY") AS "QTY"' in sql


def test_build_sql_no_pushdown_aggregate(dtp_template: TemplateConfig) -> None:
    # Tắt cờ pushdown_aggregate
    dtp_template.db_source.pushdown_aggregate = False
    profile = next(p for p in dtp_template.profiles if p.code == "BY_INVOICE")
    params = {
        "p_from": datetime(2026, 2, 1, 0, 0, 0),
        "p_to": datetime(2026, 2, 5, 23, 59, 59),
        "p_org": "BDP",
    }

    sql, binds = build_source_sql(dtp_template, profile=profile, params=params)

    # Không sinh GROUP BY khi pushdown_aggregate bị tắt
    assert "GROUP BY" not in sql
    assert ") src" not in sql
