from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.engine.sql_builder import build_source_sql
from app.schemas.template_config import (
    DbSourceSpec,
    FieldSpec,
    FileSpec,
    MeasureSpec,
    ParamSpec,
    ProfileSpec,
    SourceFilter,
    StaticFilter,
    TemplateConfig,
)


@pytest.fixture
def dtp_template() -> TemplateConfig:
    path = Path("samples/templates/DTP_HOA_DON_TAC_NGHIEP.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return TemplateConfig.model_validate(data)


def test_build_source_sql_dtp_table(dtp_template: TemplateConfig) -> None:
    p_from = datetime(2026, 2, 1, 0, 0, 0)
    p_to = datetime(2026, 2, 5, 23, 59, 59)
    params = {"p_from": p_from, "p_to": p_to, "p_org": "BDP"}

    sql, binds = build_source_sql(dtp_template, profile=None, params=params)

    # Kiểm tra cấu trúc câu lệnh SELECT
    assert sql.startswith("SELECT")
    assert '"RECON_SRC"."SRC_FACT_INVOICE_DTP"' in sql
    assert '"INVOICE_NO"' in sql
    assert '"INVOICE_DATE"' in sql
    assert '"AMOUNT"' in sql
    # Cột Dịch vụ không map db -> không có trong SELECT
    assert '"Dịch vụ"' not in sql

    # Kiểm tra mệnh đề WHERE và bind params
    assert '"INVOICE_DATE" >= :p_from' in sql
    assert '"INVOICE_DATE" <= :p_to' in sql
    assert '"ORG_CODE" = :p_org' in sql

    assert binds["p_from"] == p_from
    assert binds["p_to"] == p_to
    assert binds["p_org"] == "BDP"


def test_build_source_sql_skip_if_empty() -> None:
    config = TemplateConfig(
        schema_version=1,
        file=FileSpec(sheet="S1"),
        fields=[
            FieldSpec(name="INV", label="Inv", excel="INV", db="INVOICE_NO", type="text"),
            FieldSpec(name="DT", label="Dt", excel="DT", db="INV_DATE", type="datetime"),
        ],
        db_source=DbSourceSpec(
            kind="table",
            table="FACT_TABLE",
            params=[
                ParamSpec(name="p_from", type="datetime", source="user", label="From"),
                ParamSpec(name="p_to", type="datetime", source="user", label="To"),
            ],
            filters=[
                SourceFilter(param="p_from", column="INV_DATE", op=">="),
                SourceFilter(param="p_to", column="INV_DATE", op="<="),
                SourceFilter(param="p_branch", column="BRANCH_CODE", op="=", skip_if_empty=True),
            ],
        ),
        profiles=[
            ProfileSpec(
                code="P1",
                name="Default",
                is_default=True,
                group_by=["INV"],
                measures=[MeasureSpec(name="CNT", label="Cnt", agg="count")],
            )
        ],
    )

    # 1. p_branch có giá trị
    sql1, binds1 = build_source_sql(
        config,
        params={"p_from": "2026-01-01", "p_to": "2026-01-31", "p_branch": "HN01"},
    )
    assert '"BRANCH_CODE" = :p_branch' in sql1
    assert binds1["p_branch"] == "HN01"

    # 2. p_branch rỗng và skip_if_empty=True -> điều kiện bị bỏ qua
    sql2, binds2 = build_source_sql(
        config,
        params={"p_from": "2026-01-01", "p_to": "2026-01-31", "p_branch": ""},
    )
    assert '"BRANCH_CODE"' not in sql2
    assert "p_branch" not in binds2


def test_build_source_sql_static_where() -> None:
    config = TemplateConfig(
        schema_version=1,
        file=FileSpec(sheet="S1"),
        fields=[FieldSpec(name="ID", label="ID", excel="ID", db="ID", type="number")],
        db_source=DbSourceSpec(
            kind="table",
            table="MY_SCHEMA.MY_TABLE",
            params=[
                ParamSpec(name="p_from", type="datetime", source="user", label="From"),
                ParamSpec(name="p_to", type="datetime", source="user", label="To"),
            ],
            filters=[
                SourceFilter(param="p_from", column="ID", op=">="),
                SourceFilter(param="p_to", column="ID", op="<="),
            ],
            static_where=[
                StaticFilter(column="STATUS", op="=", value="ACTIVE"),
                StaticFilter(column="DELETED_AT", op="!=", value=None),
                StaticFilter(column="KIND", op="in", value=["A", "B"]),
            ],
        ),
        profiles=[
            ProfileSpec(
                code="P1",
                name="Default",
                is_default=True,
                group_by=["ID"],
                measures=[MeasureSpec(name="CNT", label="Cnt", agg="count")],
            )
        ],
    )

    sql, _ = build_source_sql(config, params={"p_from": 1, "p_to": 10})
    assert '"MY_SCHEMA"."MY_TABLE"' in sql
    assert "\"STATUS\" = 'ACTIVE'" in sql
    assert '"DELETED_AT" IS NOT NULL' in sql
    assert "\"KIND\" IN ('A', 'B')" in sql
