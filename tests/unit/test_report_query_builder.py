"""Tests cho whitelist query builder — Bước 3 task 22 (test viết trước).

build_report_query sinh SELECT cho nguồn VIEW/TABLE từ metadata đã
discover; mọi identifier phải nằm trong whitelist, giá trị luôn bind
không nối chuỗi (T22-03, T22-06).
"""

from __future__ import annotations

import pytest

from app.schemas.errors import ErrorCode, ServiceError
from app.services.report_source import build_report_query

COLUMNS = [
    {"name": "AMOUNT", "data_type": "NUMBER"},
    {"name": "ORG", "data_type": "STRING"},
    {"name": "TXN_DATE", "data_type": "DATE"},
]


def test_select_basic():
    sql, binds = build_report_query(
        "VIEW", "FIN", "V_REVENUE", COLUMNS, selected=["AMOUNT", "ORG"]
    )
    assert sql == 'SELECT "AMOUNT", "ORG" FROM "FIN"."V_REVENUE"'
    assert binds == {}


def test_select_all_when_no_selected():
    sql, binds = build_report_query("TABLE", "FIN", "FIN_REVENUE", COLUMNS)
    assert sql == 'SELECT "AMOUNT", "ORG", "TXN_DATE" FROM "FIN"."FIN_REVENUE"'
    assert binds == {}


def test_filter_equals_binds_value():
    sql, binds = build_report_query(
        "VIEW",
        "FIN",
        "V_REVENUE",
        COLUMNS,
        selected=["AMOUNT"],
        filters=[{"column": "ORG", "operator": "=", "code": "p_org", "value": "BDP"}],
    )
    assert sql == 'SELECT "AMOUNT" FROM "FIN"."V_REVENUE" WHERE "ORG" = :p_org'
    assert binds == {"p_org": "BDP"}


def test_filter_comparison_operators():
    sql, binds = build_report_query(
        "VIEW",
        "FIN",
        "V_REVENUE",
        COLUMNS,
        selected=["AMOUNT"],
        filters=[
            {"column": "TXN_DATE", "operator": ">=", "code": "p_from", "value": "2026-01-01"},
            {"column": "TXN_DATE", "operator": "<=", "code": "p_to", "value": "2026-01-31"},
        ],
    )
    assert '"TXN_DATE" >= :p_from AND "TXN_DATE" <= :p_to' in sql
    assert binds == {"p_from": "2026-01-01", "p_to": "2026-01-31"}


def test_filter_between_two_binds():
    sql, binds = build_report_query(
        "VIEW",
        "FIN",
        "V_REVENUE",
        COLUMNS,
        selected=["AMOUNT"],
        filters=[
            {
                "column": "AMOUNT",
                "operator": "BETWEEN",
                "code": "p_amt",
                "value": [100, 500],
            }
        ],
    )
    assert '"AMOUNT" BETWEEN :p_amt_from AND :p_amt_to' in sql
    assert binds == {"p_amt_from": 100, "p_amt_to": 500}


def test_filter_in_one_bind_per_value():
    sql, binds = build_report_query(
        "VIEW",
        "FIN",
        "V_REVENUE",
        COLUMNS,
        selected=["AMOUNT"],
        filters=[
            {
                "column": "ORG",
                "operator": "IN",
                "code": "p_orgs",
                "value": ["BDP", "HCM"],
            }
        ],
    )
    assert '"ORG" IN (:p_orgs_1, :p_orgs_2)' in sql
    assert binds == {"p_orgs_1": "BDP", "p_orgs_2": "HCM"}


def test_filter_like_prefix_appends_percent_in_bind():
    sql, binds = build_report_query(
        "VIEW",
        "FIN",
        "V_REVENUE",
        COLUMNS,
        selected=["AMOUNT"],
        filters=[
            {"column": "ORG", "operator": "LIKE_PREFIX", "code": "p_org", "value": "BD"}
        ],
    )
    assert '"ORG" LIKE :p_org' in sql
    assert binds == {"p_org": "BD%"}


def test_filter_is_null_no_bind():
    sql, binds = build_report_query(
        "VIEW",
        "FIN",
        "V_REVENUE",
        COLUMNS,
        selected=["AMOUNT"],
        filters=[{"column": "ORG", "operator": "IS_NULL", "code": "p_org", "value": None}],
    )
    assert '"ORG" IS NULL' in sql
    assert binds == {}


def test_empty_filter_value_skipped():
    sql, binds = build_report_query(
        "VIEW",
        "FIN",
        "V_REVENUE",
        COLUMNS,
        selected=["AMOUNT"],
        filters=[
            {"column": "ORG", "operator": "=", "code": "p_org", "value": ""},
            {"column": "ORG", "operator": "=", "code": "p_org2", "value": None},
        ],
    )
    assert "WHERE" not in sql
    assert binds == {}


def test_sort_asc_desc():
    sql, _ = build_report_query(
        "VIEW",
        "FIN",
        "V_REVENUE",
        COLUMNS,
        selected=["AMOUNT"],
        sorts=[
            {"column": "TXN_DATE", "direction": "DESC"},
            {"column": "ORG", "direction": "asc"},
        ],
    )
    assert sql.endswith('ORDER BY "TXN_DATE" DESC, "ORG" ASC')


def test_column_names_case_insensitive():
    sql, _ = build_report_query(
        "VIEW", "FIN", "V_REVENUE", COLUMNS, selected=["amount", "org"]
    )
    assert '"AMOUNT", "ORG"' in sql


def test_values_never_in_sql_text():
    """T22-03: giá trị nguy hiểm chỉ nằm trong binds, không nối vào SQL."""
    evil = "BDP' OR '1'='1; DROP TABLE fin_revenue --"
    sql, binds = build_report_query(
        "VIEW",
        "FIN",
        "V_REVENUE",
        COLUMNS,
        selected=["AMOUNT"],
        filters=[{"column": "ORG", "operator": "=", "code": "p_org", "value": evil}],
    )
    assert evil not in sql
    assert "DROP" not in sql
    assert binds == {"p_org": evil}


@pytest.mark.parametrize(
    "kwargs",
    [
        # Cột không có trong whitelist
        {"selected": ["AMOUNT", "SECRET_COL"]},
        {"filters": [{"column": "SECRET_COL", "operator": "=", "code": "p_x", "value": 1}]},
        {"sorts": [{"column": "SECRET_COL", "direction": "ASC"}]},
        # Identifier lạ
        {"owner": 'FIN"; DROP TABLE t --'},
        {"object_name": "V_REVENUE; DELETE FROM t"},
        {"selected": ['AMOUNT" OR "1"="1']},
        # Operator lạ / hướng sort lạ
        {
            "filters": [
                {"column": "ORG", "operator": "!=", "code": "p_x", "value": "BDP"}
            ]
        },
        {"sorts": [{"column": "ORG", "direction": "SIDEWAYS"}]},
        # BETWEEN thiếu 1 đầu, IN rỗng
        {
            "filters": [
                {"column": "AMOUNT", "operator": "BETWEEN", "code": "p_a", "value": [100]}
            ]
        },
    ],
)
def test_whitelist_rejects(kwargs):
    call_kwargs = {
        "source_type": "VIEW",
        "owner": "FIN",
        "object_name": "V_REVENUE",
        "columns": COLUMNS,
    }
    call_kwargs.update(kwargs)
    with pytest.raises(ServiceError) as exc_info:
        build_report_query(**call_kwargs)
    assert exc_info.value.code == ErrorCode.SQL_NOT_ALLOWED


def test_empty_whitelist_rejected():
    with pytest.raises(ServiceError) as exc_info:
        build_report_query("VIEW", "FIN", "V_REVENUE", [])
    assert exc_info.value.code == ErrorCode.SQL_NOT_ALLOWED


def test_custom_sql_not_through_builder():
    with pytest.raises(ServiceError) as exc_info:
        build_report_query(
            "CUSTOM_SQL", "FIN", "V_REVENUE", COLUMNS, selected=["AMOUNT"]
        )
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
