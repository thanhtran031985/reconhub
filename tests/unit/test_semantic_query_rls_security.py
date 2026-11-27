"""Test Bước 3 — SQL Compiler + RLS V1 + chống injection (Task 108).

Mọi test biên dịch qua ``resolve_semantic_plan`` rồi ``compile_semantic_query``
với snapshot quyền server-side (username/roles/is_admin) — KHÔNG có đường nào
cho payload từ browser tự khai quyền hay tự chèn SQL.

Quy ước bảo mật kiểm chứng ở đây:
- Mọi tên bảng/cột/alias chỉ đi qua whitelist metadata + ``quote_identifier``.
- Mọi giá trị (filter, CONST, username, role, scope) chỉ đi qua bind param.
- SQL cuối luôn pass ``sql_guard.check_report_sql``.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.engine.sql_guard import check_report_sql
from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.semantic_query import SemanticQueryIntent

FIXED_NOW = datetime(2026, 11, 27, 10, 30)  # Thứ Sáu, giờ Việt Nam (naive = giờ VN)


# ---------------------------------------------------------------------------
# Fixture bundle (Star Schema) — tự chứa, không import từ file test khác
# ---------------------------------------------------------------------------
def _mk_field(fid, tid, col, dtype, role, **kw):
    f = {
        "id": fid,
        "table_id": tid,
        "source_column": col,
        "field_code": col,
        "display_name": col,
        "data_type": dtype,
        "field_role": role,
        "default_agg": None,
        "is_visible": True,
        "is_filterable": True,
        "is_pk": False,
        "is_fk": False,
        "enable_date_hierarchy": False,
    }
    f.update(kw)
    return f


def _mk_table(tid, alias, role, fields, **kw):
    t = {
        "id": tid,
        "source_owner": "",
        "source_object": alias,
        "object_type": "TABLE",
        "alias": alias,
        "display_name": alias,
        "table_role": role,
        "grain_desc": "",
        "grain_keys": [],
        "is_hidden": False,
    }
    t["fields"] = fields
    t.update(kw)
    return t


def _mk_rel(rid, name, from_tid, from_col, to_tid, to_col, join_type="LEFT_OUTER"):
    return {
        "id": rid,
        "name": name,
        "from_table_id": from_tid,
        "from_column": from_col,
        "to_table_id": to_tid,
        "to_column": to_col,
        "cardinality": "MANY_TO_ONE",
        "join_type": join_type,
        "is_active": True,
    }


def _mk_measure(mid, code, tid, measure_type="SIMPLE", aggregation=None, base_field_id=None, expr_json=None):
    return {
        "id": mid,
        "code": code,
        "table_id": tid,
        "measure_type": measure_type,
        "base_field_id": base_field_id,
        "aggregation": aggregation,
        "expr_json": expr_json,
    }


def _star_bundle(rls=None, extra_measures=None, extra_tables=None, rels=None, tables=None):
    tables = (
        tables
        if tables is not None
        else [
            _mk_table(
                1,
                "FACT_SALES",
                "FACT",
                [
                    _mk_field(101, 1, "SALE_ID", "NUMBER", "KEY", is_pk=True),
                    _mk_field(102, 1, "CUSTOMER_ID", "NUMBER", "KEY", is_fk=True),
                    _mk_field(103, 1, "SERVICE_ID", "NUMBER", "KEY", is_fk=True),
                    _mk_field(104, 1, "SALE_DATE", "DATE", "DIMENSION", enable_date_hierarchy=True),
                    _mk_field(105, 1, "REVENUE", "NUMBER", "MEASURE_CANDIDATE", default_agg="SUM"),
                    _mk_field(106, 1, "COST", "NUMBER", "MEASURE_CANDIDATE", default_agg="SUM"),
                    _mk_field(107, 1, "QUANTITY", "NUMBER", "MEASURE_CANDIDATE", default_agg="SUM"),
                    _mk_field(108, 1, "OWNER_COL", "STRING", "DIMENSION"),
                    _mk_field(109, 1, "ORG_CODE", "STRING", "DIMENSION"),
                    _mk_field(110, 1, "ROLE_COL", "STRING", "DIMENSION"),
                ],
                grain_desc="Theo dòng bán",
                grain_keys=["SALE_ID"],
            ),
            _mk_table(
                2,
                "DIM_CUSTOMER",
                "DIMENSION",
                [
                    _mk_field(201, 2, "CUSTOMER_ID", "NUMBER", "KEY", is_pk=True),
                    _mk_field(202, 2, "CUSTOMER_NAME", "STRING", "DIMENSION"),
                    _mk_field(203, 2, "SEGMENT", "STRING", "DIMENSION"),
                    _mk_field(204, 2, "ROLE_COL", "STRING", "DIMENSION"),
                ],
            ),
            _mk_table(
                3,
                "DIM_DATE",
                "DIMENSION",
                [
                    _mk_field(301, 3, "CAL_DATE", "DATE", "DIMENSION", enable_date_hierarchy=True),
                    _mk_field(302, 3, "MONTH_LABEL", "STRING", "DIMENSION"),
                ],
            ),
            _mk_table(
                4,
                "DIM_SERVICE",
                "DIMENSION",
                [
                    _mk_field(401, 4, "SERVICE_ID", "NUMBER", "KEY", is_pk=True),
                    _mk_field(402, 4, "SERVICE_NAME", "STRING", "DIMENSION"),
                ],
            ),
        ]
    )
    if extra_tables:
        tables = tables + extra_tables
    measures = [
        _mk_measure(21, "REV_SUM", 1, aggregation="SUM", base_field_id=105),
        _mk_measure(22, "QTY_SUM", 1, aggregation="SUM", base_field_id=107),
        _mk_measure(
            23,
            "MARGIN_RATE",
            1,
            measure_type="CALCULATED",
            expr_json={
                "op": "DIVIDE",
                "left": {"op": "SUM", "arg": {"op": "FIELD", "field_id": 105}},
                "right": {"op": "SUM", "arg": {"op": "FIELD", "field_id": 106}},
            },
        ),
        _mk_measure(
            24,
            "REV_X100",
            1,
            measure_type="CALCULATED",
            expr_json={
                "op": "MUL",
                "left": {"op": "MEASURE", "measure_id": 21},
                "right": {"op": "CONST", "value": 100},
            },
        ),
        _mk_measure(25, "REV_MIN", 1, aggregation="MIN", base_field_id=105),
        _mk_measure(26, "REV_MAX", 1, aggregation="MAX", base_field_id=105),
        _mk_measure(27, "REV_AVG", 1, aggregation="AVG", base_field_id=105),
        _mk_measure(28, "CUST_COUNT", 1, aggregation="COUNT_DISTINCT", base_field_id=102),
        _mk_measure(29, "SALE_COUNT", 1, aggregation="COUNT", base_field_id=101),
    ]
    if extra_measures:
        measures = measures + extra_measures
    return {
        "model": {"id": 1, "code": "SALES", "name": "Sales", "data_source_id": 1},
        "version": {"id": 10, "status": "ACTIVE", "version_no": 1},
        "tables": tables,
        "relationships": rels
        if rels is not None
        else [
            _mk_rel(1, "SALES_CUSTOMER", 1, "CUSTOMER_ID", 2, "CUSTOMER_ID"),
            _mk_rel(2, "SALES_DATE", 1, "SALE_DATE", 3, "CAL_DATE"),
            _mk_rel(3, "SALES_SERVICE", 1, "SERVICE_ID", 4, "SERVICE_ID"),
        ],
        "measures": measures,
        "rls_policies": rls or [],
    }


def _mk_rls(pid, tid, column, policy_type, scope_attr=None, admin_bypass=True):
    return {
        "id": pid,
        "table_id": tid,
        "column_name": column,
        "policy_type": policy_type,
        "scope_attr": scope_attr,
        "admin_bypass": admin_bypass,
        "is_active": True,
    }


def _intent(**overrides):
    payload = {
        "model_version_id": 10,
        "dimensions": [{"field_id": 202}],
        "measures": [{"measure_id": 21}],
    }
    payload.update(overrides)
    return SemanticQueryIntent(**payload)


def _resolve(payload, bundle):
    from app.engine.semantic_planner import resolve_semantic_plan

    full = {
        "model_version_id": 10,
        "dimensions": [{"field_id": 202}],
        "measures": [{"measure_id": 21}],
    }
    full.update(payload)
    return resolve_semantic_plan(SemanticQueryIntent(**full), bundle)


def _compile(payload, bundle, **kwargs):
    from app.engine.semantic_sql import compile_semantic_query

    full = {
        "model_version_id": 10,
        "dimensions": [{"field_id": 202}],
        "measures": [{"measure_id": 21}],
    }
    full.update(payload)
    intent = SemanticQueryIntent(**full)
    resolved = _resolve(full, bundle)
    params = {
        "username": "owner1",
        "roles": ["OPERATOR"],
        "is_admin": False,
        "dialect": "SQLITE",
        "now": FIXED_NOW,
    }
    params.update(kwargs)
    return compile_semantic_query(resolved, intent, **params)


def _guard_ok(plan):
    ok, reason, _binds = check_report_sql(plan.sql)
    assert ok, f"SQL không pass guard: {reason}\nSQL: {plan.sql}"
    return True


# ---------------------------------------------------------------------------
# Biên dịch cơ bản: FROM / JOIN / GROUP BY / ORDER BY / LIMIT
# ---------------------------------------------------------------------------
def test_compile_star_sqlite_basic():
    plan = _compile({}, _star_bundle())
    assert plan.sql.startswith('SELECT t1."CUSTOMER_NAME" AS "CUSTOMER_NAME"')
    assert 'FROM "FACT_SALES" t0' in plan.sql
    assert 'LEFT OUTER JOIN "DIM_CUSTOMER" t1 ON t0."CUSTOMER_ID" = t1."CUSTOMER_ID"' in plan.sql
    assert 'GROUP BY t1."CUSTOMER_NAME"' in plan.sql
    assert 'ORDER BY "CUSTOMER_NAME" ASC' in plan.sql
    assert plan.sql.endswith("LIMIT 500")
    assert plan.dialect == "SQLITE"
    assert plan.primary_fact_table_id == 1
    assert plan.tables_used == [1, 2]
    assert [c["name"] for c in plan.output_columns] == ["CUSTOMER_NAME", "REV_SUM"]
    assert plan.rls_applied is False
    assert _guard_ok(plan)


def test_compile_inner_join():
    rels = [
        _mk_rel(1, "SALES_CUSTOMER", 1, "CUSTOMER_ID", 2, "CUSTOMER_ID", join_type="INNER"),
        _mk_rel(2, "SALES_DATE", 1, "SALE_DATE", 3, "CAL_DATE"),
        _mk_rel(3, "SALES_SERVICE", 1, "SERVICE_ID", 4, "SERVICE_ID"),
    ]
    plan = _compile({}, _star_bundle(rels=rels))
    assert 'INNER JOIN "DIM_CUSTOMER" t1 ON t0."CUSTOMER_ID" = t1."CUSTOMER_ID"' in plan.sql
    assert _guard_ok(plan)


def test_compile_no_dims_single_aggregate_row():
    plan = _compile({"dimensions": [], "measures": [{"measure_id": 21}]}, _star_bundle())
    assert "GROUP BY" not in plan.sql
    assert plan.sql.startswith('SELECT SUM(t0."REVENUE") AS "REV_SUM"')
    assert _guard_ok(plan)


def test_compile_oracle_dialect_schema_qualified():
    tables = _star_bundle()["tables"]
    for t in tables:
        t["source_owner"] = "SRC"
    bundle = _star_bundle(tables=tables)
    plan = _compile({}, bundle, dialect="ORACLE")
    assert 'FROM "SRC"."FACT_SALES" t0' in plan.sql
    assert 'LEFT OUTER JOIN "SRC"."DIM_CUSTOMER" t1' in plan.sql
    assert plan.sql.endswith("FETCH FIRST 500 ROWS ONLY")
    assert plan.dialect == "ORACLE"
    assert _guard_ok(plan)


def test_compile_offset_paging_both_dialects():
    plan = _compile({"offset": 50}, _star_bundle())
    assert plan.sql.endswith("LIMIT 500 OFFSET 50")
    assert _guard_ok(plan)
    plan_ora = _compile({"offset": 50}, _star_bundle(), dialect="ORACLE")
    assert plan_ora.sql.endswith("OFFSET 50 ROWS FETCH NEXT 500 ROWS ONLY")
    assert _guard_ok(plan_ora)


def test_compile_table_limit_capped_by_preview_max():
    plan = _compile({"limit": 2000}, _star_bundle(), preview_max_rows=500)
    assert plan.sql.endswith("LIMIT 500")
    assert plan.row_limit == 500
    assert plan.fetch_extra_row is False
    assert _guard_ok(plan)


def test_compile_chart_top_n_fetches_one_extra():
    plan = _compile({"visual_type": "BAR"}, _star_bundle(), chart_max_points=50)
    assert plan.sql.endswith("LIMIT 51")
    assert plan.row_limit == 51
    assert plan.fetch_extra_row is True
    assert _guard_ok(plan)


def test_compile_chart_respects_smaller_user_limit():
    plan = _compile({"visual_type": "LINE", "limit": 10}, _star_bundle(), chart_max_points=50)
    assert plan.sql.endswith("LIMIT 10")
    assert plan.fetch_extra_row is False
    assert _guard_ok(plan)


def test_compile_kpi_capped_like_table():
    plan = _compile({"visual_type": "KPI", "limit": 2000}, _star_bundle(), preview_max_rows=500)
    assert plan.sql.endswith("LIMIT 500")
    assert plan.fetch_extra_row is False
    assert _guard_ok(plan)


def test_compile_sort_on_measure_with_tie_breaker():
    plan = _compile({"sorts": [{"target_type": "MEASURE", "id": 21, "direction": "DESC"}]}, _star_bundle())
    assert 'ORDER BY "REV_SUM" DESC, "CUSTOMER_NAME" ASC' in plan.sql
    assert _guard_ok(plan)


def test_compile_no_sorts_orders_by_first_output_column():
    plan = _compile({}, _star_bundle())
    assert 'ORDER BY "CUSTOMER_NAME" ASC' in plan.sql
    assert _guard_ok(plan)


# ---------------------------------------------------------------------------
# Measures: 6 phép tổng hợp + AST lồng nhau + chia 0
# ---------------------------------------------------------------------------
def test_compile_all_six_aggregations_distinct_aliases():
    measures = [
        {"field_id": 105, "aggregation": "SUM", "alias": "M_SUM"},
        {"field_id": 105, "aggregation": "AVG", "alias": "M_AVG"},
        {"field_id": 105, "aggregation": "MIN", "alias": "M_MIN"},
        {"field_id": 105, "aggregation": "MAX", "alias": "M_MAX"},
        {"field_id": 101, "aggregation": "COUNT", "alias": "M_CNT"},
        {"field_id": 102, "aggregation": "COUNT_DISTINCT", "alias": "M_CD"},
    ]
    plan = _compile({"dimensions": [], "measures": measures}, _star_bundle())
    assert 'SUM(t0."REVENUE") AS "M_SUM"' in plan.sql
    assert 'AVG(t0."REVENUE") AS "M_AVG"' in plan.sql
    assert 'MIN(t0."REVENUE") AS "M_MIN"' in plan.sql
    assert 'MAX(t0."REVENUE") AS "M_MAX"' in plan.sql
    assert 'COUNT(t0."SALE_ID") AS "M_CNT"' in plan.sql
    assert 'COUNT(DISTINCT t0."CUSTOMER_ID") AS "M_CD"' in plan.sql
    assert _guard_ok(plan)


def test_compile_calculated_divide_wraps_nullif():
    plan = _compile({"dimensions": [], "measures": [{"measure_id": 23}]}, _star_bundle())
    assert '(((SUM(t0."REVENUE")) * 1.0) / NULLIF((SUM(t0."COST")), 0)) AS "MARGIN_RATE"' in plan.sql
    assert _guard_ok(plan)


def test_compile_measure_ref_expands_inline_with_const_bind():
    plan = _compile({"dimensions": [], "measures": [{"measure_id": 24}]}, _star_bundle())
    assert '(SUM(t0."REVENUE") * :b0) AS "REV_X100"' in plan.sql
    assert plan.binds == {"b0": 100}
    assert _guard_ok(plan)


def test_compile_ast_round_coalesce_case():
    extra = [
        _mk_measure(
            30,
            "RND",
            1,
            measure_type="CALCULATED",
            expr_json={"op": "ROUND", "value": {"op": "SUM", "arg": {"op": "FIELD", "field_id": 105}}, "digits": 2},
        ),
        _mk_measure(
            31,
            "COAL",
            1,
            measure_type="CALCULATED",
            expr_json={
                "op": "COALESCE",
                "args": [{"op": "SUM", "arg": {"op": "FIELD", "field_id": 105}}, {"op": "CONST", "value": 0}],
            },
        ),
        _mk_measure(
            32,
            "FLAG",
            1,
            measure_type="CALCULATED",
            expr_json={
                "op": "CASE",
                "branches": [{"when": {"op": "FIELD", "field_id": 107}, "then": {"op": "CONST", "value": 1}}],
                "else": {"op": "CONST", "value": 0},
            },
        ),
    ]
    plan = _compile(
        {"dimensions": [], "measures": [{"measure_id": 30}, {"measure_id": 31}, {"measure_id": 32}]},
        _star_bundle(extra_measures=extra),
    )
    assert 'ROUND(SUM(t0."REVENUE"), 2) AS "RND"' in plan.sql
    assert 'COALESCE(SUM(t0."REVENUE"), :b0) AS "COAL"' in plan.sql
    assert 'CASE WHEN (t0."QUANTITY" <> 0) THEN :b1 ELSE :b2 END AS "FLAG"' in plan.sql
    assert plan.binds == {"b0": 0, "b1": 1, "b2": 0}
    assert _guard_ok(plan)


def test_compile_unknown_ast_op_blocked_even_from_db_row():
    # Dữ liệu expr_json trong DB bị sửa tay thành op lạ -> compiler chặn, không tin DB mù.
    extra = [
        _mk_measure(
            33,
            "EVIL",
            1,
            measure_type="CALCULATED",
            expr_json={"op": "UNION", "left": {"op": "FIELD", "field_id": 105}},
        ),
    ]
    with pytest.raises(ServiceError) as exc:
        _compile({"dimensions": [], "measures": [{"measure_id": 33}]}, _star_bundle(extra_measures=extra))
    assert exc.value.code == str(ErrorCode.SQL_NOT_ALLOWED)


def test_compile_measure_cycle_blocked_at_compile_level():
    # Phòng thủ chiều sâu: nếu resolver bị bypass, compiler vẫn chặn đệ quy vô hạn.
    from app.engine.semantic_planner import ResolvedMeasure

    plan_resolved = _resolve({"dimensions": [], "measures": [{"measure_id": 21}]}, _star_bundle())
    cyclic_a = ResolvedMeasure(
        measure_id=90,
        code="CYC_A",
        table_id=1,
        base_field_id=None,
        aggregation=None,
        expr={"op": "MEASURE", "measure_id": 91},
        output_alias="CYC_A",
    )
    cyclic_b = ResolvedMeasure(
        measure_id=91,
        code="CYC_B",
        table_id=1,
        base_field_id=None,
        aggregation=None,
        expr={"op": "MEASURE", "measure_id": 90},
        output_alias="CYC_B",
    )
    plan_resolved.measure_index[90] = cyclic_a
    plan_resolved.measure_index[91] = cyclic_b
    plan_resolved.selected_measures = [cyclic_a]
    from app.engine.semantic_sql import compile_semantic_query

    with pytest.raises(ServiceError) as exc:
        compile_semantic_query(
            plan_resolved,
            _intent(dimensions=[], measures=[{"measure_id": 21}]),
            username="owner1",
            roles=["OPERATOR"],
            dialect="SQLITE",
        )
    assert exc.value.code == str(ErrorCode.MODEL_INVALID)


# ---------------------------------------------------------------------------
# Virtual Date Hierarchy
# ---------------------------------------------------------------------------
def test_compile_date_part_month_sqlite_groups_by_expression():
    plan = _compile(
        {"dimensions": [{"field_id": 301, "date_part": "MONTH", "alias": "CAL_MONTH"}]},
        _star_bundle(),
    )
    assert 'STRFTIME(\'%Y-%m\', t1."CAL_DATE") AS "CAL_MONTH"' in plan.sql
    assert "GROUP BY STRFTIME('%Y-%m', t1.\"CAL_DATE\")" in plan.sql
    assert [c["name"] for c in plan.output_columns] == ["CAL_MONTH", "REV_SUM"]
    assert _guard_ok(plan)


def test_compile_date_part_quarter_year_oracle():
    plan = _compile(
        {"dimensions": [{"field_id": 301, "date_part": "QUARTER", "alias": "CAL_Q"}]},
        _star_bundle(),
        dialect="ORACLE",
    )
    assert "TO_CHAR(t1.\"CAL_DATE\", 'YYYY') || '-Q' || TO_CHAR(t1.\"CAL_DATE\", 'Q')" in plan.sql
    assert _guard_ok(plan)
    plan_y = _compile(
        {"dimensions": [{"field_id": 301, "date_part": "YEAR", "alias": "CAL_Y"}]},
        _star_bundle(),
        dialect="SQLITE",
    )
    assert 'STRFTIME(\'%Y\', t1."CAL_DATE") AS "CAL_Y"' in plan_y.sql
    assert _guard_ok(plan_y)


# ---------------------------------------------------------------------------
# Filters: mọi operator qua bind param
# ---------------------------------------------------------------------------
def test_compile_filters_all_operators():
    filters = [
        {"field_id": 202, "operator": "=", "value": "ACME"},
        {"field_id": 105, "operator": ">=", "value": 1000},
        {"field_id": 105, "operator": "<=", "value": 9999},
        {"field_id": 105, "operator": "BETWEEN", "value": [100, 200]},
        {"field_id": 203, "operator": "IN", "value": ["VIP", "STD"]},
        {"field_id": 202, "operator": "LIKE_PREFIX", "value": "AC"},
        {"field_id": 203, "operator": "IS_NULL"},
        {"field_id": 104, "operator": "RELATIVE_DATE", "value": "TODAY"},
    ]
    plan = _compile({"filters": filters}, _star_bundle())
    sql = plan.sql
    assert 't1."CUSTOMER_NAME" = :b0' in sql
    assert 't0."REVENUE" >= :b1' in sql
    assert 't0."REVENUE" <= :b2' in sql
    assert 't0."REVENUE" BETWEEN :b3 AND :b4' in sql
    assert 't1."SEGMENT" IN (:b5, :b6)' in sql
    assert 't1."CUSTOMER_NAME" LIKE :b7 ESCAPE ' in sql
    assert 't1."SEGMENT" IS NULL' in sql
    assert 't0."SALE_DATE" >= :b8 AND t0."SALE_DATE" < :b9' in sql
    assert plan.binds["b0"] == "ACME"
    assert plan.binds["b1"] == 1000
    assert plan.binds["b3"] == 100
    assert plan.binds["b4"] == 200
    assert plan.binds["b5"] == "VIP"
    assert plan.binds["b7"] == "AC%"
    assert plan.binds["b8"] == datetime(2026, 11, 27, 0, 0)
    assert plan.binds["b9"] == datetime(2026, 11, 28, 0, 0)
    assert "ACME" not in sql and "VIP" not in sql  # giá trị không bao giờ nằm trong SQL text
    assert _guard_ok(plan)


def test_compile_like_prefix_escapes_wildcards():
    plan = _compile(
        {"filters": [{"field_id": 202, "operator": "LIKE_PREFIX", "value": r"100%_a\b"}]},
        _star_bundle(),
    )
    assert plan.binds["b0"] == r"100\%\_a\\b%"
    assert r"100%_a\b" not in plan.sql
    assert _guard_ok(plan)


@pytest.mark.parametrize(
    "value, start, end",
    [
        ("TODAY", datetime(2026, 11, 27), datetime(2026, 11, 28)),
        ("YESTERDAY", datetime(2026, 11, 26), datetime(2026, 11, 27)),
        ("LAST_7_DAYS", datetime(2026, 11, 21), datetime(2026, 11, 28)),
        ("THIS_MONTH", datetime(2026, 11, 1), datetime(2026, 12, 1)),
        ("LAST_MONTH", datetime(2026, 10, 1), datetime(2026, 11, 1)),
        ("THIS_YEAR", datetime(2026, 1, 1), datetime(2027, 1, 1)),
    ],
)
def test_compile_relative_date_all_values(value, start, end):
    plan = _compile(
        {"filters": [{"field_id": 104, "operator": "RELATIVE_DATE", "value": value}]},
        _star_bundle(),
    )
    assert plan.binds["b0"] == start
    assert plan.binds["b1"] == end
    assert _guard_ok(plan)


# ---------------------------------------------------------------------------
# Chống injection: alias / field / operator / filter / sort
# ---------------------------------------------------------------------------
def test_compile_filter_injection_value_stays_in_bind():
    evil = "x' OR '1'='1"
    plan = _compile(
        {"filters": [{"field_id": 202, "operator": "=", "value": evil}]},
        _star_bundle(),
    )
    assert evil not in plan.sql
    assert plan.binds["b0"] == evil
    assert _guard_ok(plan)


def test_compile_alias_union_blocked_by_guard_fail_closed():
    with pytest.raises(ServiceError) as exc:
        _compile({"dimensions": [{"field_id": 202, "alias": "UNION"}]}, _star_bundle())
    assert exc.value.code == str(ErrorCode.SQL_NOT_ALLOWED)


def test_compile_alias_delete_blocked_by_guard_fail_closed():
    with pytest.raises(ServiceError) as exc:
        _compile({"dimensions": [{"field_id": 202, "alias": "DELETE"}]}, _star_bundle())
    assert exc.value.code == str(ErrorCode.SQL_NOT_ALLOWED)


def test_compile_bad_alias_rejected_by_schema():
    with pytest.raises(ValidationError):  # Pydantic ValidationError: alias chứa ; và khoảng trắng
        SemanticQueryIntent(
            model_version_id=10,
            dimensions=[{"field_id": 202, "alias": "a; DROP TABLE x"}],
            measures=[{"measure_id": 21}],
        )


def test_compile_bad_operator_rejected_by_schema():
    with pytest.raises(ValidationError):  # Pydantic ValidationError: operator ngoài whitelist
        SemanticQueryIntent(
            model_version_id=10,
            dimensions=[{"field_id": 202}],
            measures=[{"measure_id": 21}],
            filters=[{"field_id": 202, "operator": "= 1 OR 1=1 --", "value": "x"}],
        )


def test_compile_sort_on_unselected_field_blocked():
    with pytest.raises(ServiceError) as exc:
        _compile({"sorts": [{"target_type": "FIELD", "id": 203}]}, _star_bundle())
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_compile_column_with_double_quote_is_escaped():
    # Cột trong metadata chứa dấu " -> compiler phải nhân đôi, không được phá quote.
    tables = _star_bundle()["tables"]
    tables[0]["fields"][4]["source_column"] = 'REV"ENUE'
    plan = _compile({"dimensions": [], "measures": [{"measure_id": 21}]}, _star_bundle(tables=tables))
    assert 'SUM(t0."REV""ENUE")' in plan.sql
    assert _guard_ok(plan)


def test_quote_identifier_escapes_double_quote():
    from app.engine.sql_dialect import quote_identifier

    assert quote_identifier('REV"ENUE') == '"REV""ENUE"'
    assert quote_identifier("SRC.FACT_SALES") == '"SRC"."FACT_SALES"'
    assert quote_identifier('"FACT_SALES"') == '"FACT_SALES"'


# ---------------------------------------------------------------------------
# RLS V1: server-side, fail-closed
# ---------------------------------------------------------------------------
def test_compile_rls_owner_username_binds_ctx_username():
    rls = [_mk_rls(1, 1, "OWNER_COL", "OWNER_USERNAME")]
    plan = _compile({}, _star_bundle(rls=rls))
    assert 't0."OWNER_COL" = :b0' in plan.sql
    assert plan.binds["b0"] == "owner1"
    assert plan.rls_applied is True
    assert _guard_ok(plan)


def test_compile_rls_username_with_quote_stays_in_bind():
    rls = [_mk_rls(1, 1, "OWNER_COL", "OWNER_USERNAME")]
    plan = _compile({}, _star_bundle(rls=rls), username="x' OR '1'='1")
    assert "x' OR '1'='1" not in plan.sql
    assert plan.binds["b0"] == "x' OR '1'='1"
    assert _guard_ok(plan)


def test_compile_rls_role_list_binds_ctx_roles():
    rls = [_mk_rls(1, 2, "ROLE_COL", "ROLE_LIST")]
    plan = _compile({}, _star_bundle(rls=rls), roles=["OPERATOR", "VIEWER"])
    assert 't1."ROLE_COL" IN (:b0, :b1)' in plan.sql
    assert plan.binds["b0"] == "OPERATOR"
    assert plan.binds["b1"] == "VIEWER"
    assert plan.rls_applied is True
    assert _guard_ok(plan)


def test_compile_rls_role_list_no_roles_fail_closed():
    rls = [_mk_rls(1, 2, "ROLE_COL", "ROLE_LIST")]
    plan = _compile({}, _star_bundle(rls=rls), roles=[])
    assert "1 = 0" in plan.sql
    assert plan.rls_applied is True
    assert any("không có role" in w for w in plan.warnings)
    assert _guard_ok(plan)


def test_compile_rls_org_scope_binds_scope_value():
    rls = [_mk_rls(1, 1, "ORG_CODE", "ORG_SCOPE_HOOK", scope_attr="org_code")]
    plan = _compile({}, _star_bundle(rls=rls), org_scopes={"org_code": "VTOS"})
    assert 't0."ORG_CODE" = :b0' in plan.sql
    assert plan.binds["b0"] == "VTOS"
    assert plan.rls_applied is True
    assert _guard_ok(plan)


def test_compile_rls_org_scope_missing_fail_closed():
    rls = [_mk_rls(1, 1, "ORG_CODE", "ORG_SCOPE_HOOK", scope_attr="org_code")]
    with pytest.raises(ServiceError) as exc:
        _compile({}, _star_bundle(rls=rls), org_scopes={})
    assert exc.value.code == str(ErrorCode.RLS_SCOPE_MISSING)


def test_compile_rls_org_scope_attr_not_configured_fail_closed():
    rls = [_mk_rls(1, 1, "ORG_CODE", "ORG_SCOPE_HOOK", scope_attr=None)]
    with pytest.raises(ServiceError) as exc:
        _compile({}, _star_bundle(rls=rls), org_scopes={"org_code": "VTOS"})
    assert exc.value.code == str(ErrorCode.RLS_SCOPE_MISSING)


def test_compile_rls_org_scope_empty_string_returns_no_rows():
    rls = [_mk_rls(1, 1, "ORG_CODE", "ORG_SCOPE_HOOK", scope_attr="org_code")]
    plan = _compile({}, _star_bundle(rls=rls), org_scopes={"org_code": ""})
    assert "1 = 0" in plan.sql
    assert plan.rls_applied is True
    assert _guard_ok(plan)


def test_compile_rls_admin_bypass_skips_policy():
    rls = [_mk_rls(1, 1, "OWNER_COL", "OWNER_USERNAME", admin_bypass=True)]
    plan = _compile({}, _star_bundle(rls=rls), is_admin=True)
    assert "OWNER_COL" not in plan.sql
    assert plan.rls_applied is False
    assert _guard_ok(plan)


def test_compile_rls_admin_without_bypass_still_applies():
    rls = [_mk_rls(1, 1, "OWNER_COL", "OWNER_USERNAME", admin_bypass=False)]
    plan = _compile({}, _star_bundle(rls=rls), is_admin=True)
    assert 't0."OWNER_COL" = :b0' in plan.sql
    assert plan.binds["b0"] == "owner1"
    assert plan.rls_applied is True
    assert _guard_ok(plan)


def test_compile_rls_only_for_involved_tables():
    rls = [_mk_rls(1, 4, "SERVICE_NAME", "OWNER_USERNAME")]  # DIM_SERVICE không tham gia
    plan = _compile({}, _star_bundle(rls=rls))
    assert "SERVICE_NAME" not in plan.sql
    assert plan.rls_applied is False
    assert _guard_ok(plan)


def test_compile_rls_multiple_policies_anded():
    rls = [
        _mk_rls(1, 1, "OWNER_COL", "OWNER_USERNAME"),
        _mk_rls(2, 2, "ROLE_COL", "ROLE_LIST"),
    ]
    plan = _compile({}, _star_bundle(rls=rls))
    assert 't0."OWNER_COL" = :b0' in plan.sql
    assert 't1."ROLE_COL" IN (:b1)' in plan.sql
    assert plan.rls_applied is True
    assert _guard_ok(plan)


def test_compile_output_columns_types():
    plan = _compile(
        {"dimensions": [{"field_id": 301, "date_part": "MONTH", "alias": "CAL_MONTH"}]},
        _star_bundle(),
    )
    cols = {c["name"]: c for c in plan.output_columns}
    assert cols["CAL_MONTH"]["data_type"] == "STRING"  # date_part trả chuỗi ISO
    assert cols["REV_SUM"]["data_type"] == "NUMBER"
    assert _guard_ok(plan)


def test_compile_invalid_dialect_rejected():
    with pytest.raises(ValueError):
        _compile({}, _star_bundle(), dialect="MYSQL")


def test_compile_scalar_filter_none_value_blocked():
    from app.engine.semantic_sql import compile_semantic_query

    resolved = _resolve({"filters": [{"field_id": 202, "operator": "=", "value": "ACME"}]}, _star_bundle())
    resolved.resolved_filters[0].value = None  # giả lập plan bị sửa sau khi duyệt
    with pytest.raises(ServiceError) as exc:
        compile_semantic_query(resolved, _intent(), username="owner1", roles=["OPERATOR"], dialect="SQLITE")
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_compile_between_none_endpoint_blocked():
    from app.engine.semantic_sql import compile_semantic_query

    resolved = _resolve({"filters": [{"field_id": 105, "operator": "BETWEEN", "value": [100, 200]}]}, _star_bundle())
    resolved.resolved_filters[0].value = [100, None]
    with pytest.raises(ServiceError) as exc:
        compile_semantic_query(resolved, _intent(), username="owner1", roles=["OPERATOR"], dialect="SQLITE")
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_compile_in_with_none_item_blocked():
    from app.engine.semantic_sql import compile_semantic_query

    resolved = _resolve({"filters": [{"field_id": 203, "operator": "IN", "value": ["VIP"]}]}, _star_bundle())
    resolved.resolved_filters[0].value = ["VIP", None]
    with pytest.raises(ServiceError) as exc:
        compile_semantic_query(resolved, _intent(), username="owner1", roles=["OPERATOR"], dialect="SQLITE")
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_compile_const_bool_binds_as_int():
    extra = [
        _mk_measure(
            34,
            "BOOLC",
            1,
            measure_type="CALCULATED",
            expr_json={
                "op": "COALESCE",
                "args": [{"op": "SUM", "arg": {"op": "FIELD", "field_id": 105}}, {"op": "CONST", "value": True}],
            },
        ),
    ]
    plan = _compile({"dimensions": [], "measures": [{"measure_id": 34}]}, _star_bundle(extra_measures=extra))
    assert plan.binds["b0"] == 1
    assert type(plan.binds["b0"]) is int
    assert _guard_ok(plan)


def test_compile_tie_breaker_when_sort_is_first_column():
    plan = _compile({"sorts": [{"target_type": "FIELD", "id": 202, "direction": "DESC"}]}, _star_bundle())
    assert 'ORDER BY "CUSTOMER_NAME" DESC, "REV_SUM" ASC' in plan.sql
    assert _guard_ok(plan)


def test_compile_tracks_date_bind_types_and_null_safe_quarter():
    plan = _compile(
        {
            "dimensions": [{"field_id": 301, "date_part": "QUARTER", "alias": "CAL_Q"}],
            "filters": [
                {"field_id": 104, "operator": ">=", "value": "2026-11-01"},
                {"field_id": 104, "operator": "RELATIVE_DATE", "value": "TODAY"},
            ],
        },
        _star_bundle(),
        dialect="ORACLE",
    )
    assert plan.bind_types == {"b0": "DATE", "b1": "DATE", "b2": "DATE"}
    assert "CASE WHEN" in plan.sql
    assert _guard_ok(plan)
