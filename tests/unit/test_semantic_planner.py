"""Tests cho Semantic Query Planner — Bước 1 task 108 (test viết trước).

Kiểm tra contract SemanticQueryIntent và mở rộng app/engine/sql_dialect.py
(Oracle + SQLite). Các test Bước 2/3/4 được thêm vào cùng file này và
tests/unit/test_semantic_query_rls_security.py.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.engine import sql_dialect


def _valid_intent_payload() -> dict:
    return {
        "model_version_id": 7,
        "dimensions": [{"field_id": 11, "alias": "cust_name"}],
        "measures": [{"measure_id": 21}],
        "filters": [],
        "sorts": [{"target_type": "MEASURE", "id": 21, "direction": "DESC"}],
        "visual_type": "TABLE",
        "limit": 100,
        "offset": 0,
        "request_seq": 3,
    }


# ---------------------------------------------------------------------------
# Bước 1 — Contract SemanticQueryIntent
# ---------------------------------------------------------------------------


def test_intent_valid_parses():
    from app.schemas.semantic_query import SemanticQueryIntent

    intent = SemanticQueryIntent(**_valid_intent_payload())
    assert intent.model_version_id == 7
    assert intent.dimensions[0].field_id == 11
    assert intent.dimensions[0].alias == "cust_name"
    assert intent.measures[0].measure_id == 21
    assert intent.sorts[0].direction == "DESC"
    assert intent.visual_type == "TABLE"
    assert intent.limit == 100
    assert intent.offset == 0
    assert intent.request_seq == 3


def test_intent_rejects_unknown_operator():
    from app.schemas.semantic_query import SemanticQueryIntent

    payload = _valid_intent_payload()
    payload["filters"] = [{"field_id": 11, "operator": "LIKE", "value": "A%"}]
    with pytest.raises(ValidationError):
        SemanticQueryIntent(**payload)


def test_intent_rejects_bad_alias():
    from app.schemas.semantic_query import SemanticQueryIntent

    payload = _valid_intent_payload()
    payload["dimensions"] = [{"field_id": 11, "alias": "ten khach; DROP TABLE x"}]
    with pytest.raises(ValidationError):
        SemanticQueryIntent(**payload)


def test_intent_rejects_empty_selection():
    from app.schemas.semantic_query import SemanticQueryIntent

    payload = _valid_intent_payload()
    payload["dimensions"] = []
    payload["measures"] = []
    with pytest.raises(ValidationError):
        SemanticQueryIntent(**payload)


def test_intent_rejects_measure_without_source():
    from app.schemas.semantic_query import SemanticQueryIntent

    payload = _valid_intent_payload()
    payload["measures"] = [{"alias": "m1"}]
    with pytest.raises(ValidationError):
        SemanticQueryIntent(**payload)


def test_intent_rejects_measure_with_both_sources():
    from app.schemas.semantic_query import SemanticQueryIntent

    payload = _valid_intent_payload()
    payload["measures"] = [{"measure_id": 21, "field_id": 12, "aggregation": "SUM"}]
    with pytest.raises(ValidationError):
        SemanticQueryIntent(**payload)


def test_intent_adhoc_measure_ok():
    from app.schemas.semantic_query import SemanticQueryIntent

    payload = _valid_intent_payload()
    payload["measures"] = [{"field_id": 12, "aggregation": "SUM", "alias": "total_rev"}]
    intent = SemanticQueryIntent(**payload)
    assert intent.measures[0].field_id == 12
    assert intent.measures[0].aggregation == "SUM"


def test_intent_rejects_bad_date_part():
    from app.schemas.semantic_query import SemanticQueryIntent

    payload = _valid_intent_payload()
    payload["dimensions"] = [{"field_id": 11, "date_part": "WEEK"}]
    with pytest.raises(ValidationError):
        SemanticQueryIntent(**payload)


def test_intent_rejects_limit_out_of_range():
    from app.schemas.semantic_query import SemanticQueryIntent

    payload = _valid_intent_payload()
    payload["limit"] = 0
    with pytest.raises(ValidationError):
        SemanticQueryIntent(**payload)
    payload["limit"] = 10001
    with pytest.raises(ValidationError):
        SemanticQueryIntent(**payload)


def test_intent_filter_value_shape_checked():
    from app.schemas.semantic_query import SemanticQueryIntent

    payload = _valid_intent_payload()
    payload["filters"] = [{"field_id": 11, "operator": "BETWEEN", "value": "2026-01-01"}]
    with pytest.raises(ValidationError):
        SemanticQueryIntent(**payload)
    payload["filters"] = [{"field_id": 11, "operator": "IN", "value": ["A", "B"]}]
    intent = SemanticQueryIntent(**payload)
    assert intent.filters[0].operator == "IN"


# ---------------------------------------------------------------------------
# Bước 1 — sql_dialect: tương thích ngược + dialect Oracle/SQLite
# ---------------------------------------------------------------------------


def test_quote_identifier_oracle_unchanged():
    assert sql_dialect.quote_identifier("FACT_SALES") == '"FACT_SALES"'
    assert sql_dialect.quote_identifier("DATARAW.FACT_BILL") == '"DATARAW"."FACT_BILL"'
    assert sql_dialect.quote_identifier('"ALREADY"') == '"ALREADY"'


def test_quote_identifier_sqlite():
    assert sql_dialect.quote_identifier("FACT_SALES", dialect="SQLITE") == '"FACT_SALES"'
    assert sql_dialect.quote_identifier("main.FACT_SALES", dialect="SQLITE") == '"main"."FACT_SALES"'


def test_quote_identifier_rejects_bad_dialect():
    with pytest.raises(ValueError):
        sql_dialect.quote_identifier("X", dialect="POSTGRES")


def test_old_oracle_helpers_unchanged():
    assert sql_dialect.trunc_day('"TX_DATE"') == 'TRUNC("TX_DATE")'
    assert sql_dialect.trunc_month('"TX_DATE"') == "TRUNC(\"TX_DATE\", 'MM')"
    assert sql_dialect.concat('"A"', '"B"') == '"A" || "B"'
    assert sql_dialect.coalesce('"A"', "0") == 'COALESCE("A", 0)'


def test_date_part_expr_oracle():
    expr = '"t0"."TX_DATE"'
    assert sql_dialect.date_part_expr(expr, "DAY", "ORACLE") == 'TO_CHAR("t0"."TX_DATE", \'YYYY-MM-DD\')'
    assert sql_dialect.date_part_expr(expr, "MONTH", "ORACLE") == 'TO_CHAR("t0"."TX_DATE", \'YYYY-MM\')'
    assert sql_dialect.date_part_expr(expr, "YEAR", "ORACLE") == 'TO_CHAR("t0"."TX_DATE", \'YYYY\')'
    quarter = sql_dialect.date_part_expr(expr, "QUARTER", "ORACLE")
    assert 'TO_CHAR("t0"."TX_DATE", \'YYYY\')' in quarter
    assert "|| '-Q' ||" in quarter
    assert 'TO_CHAR("t0"."TX_DATE", \'Q\')' in quarter


def test_date_part_expr_sqlite():
    expr = '"t0"."TX_DATE"'
    assert sql_dialect.date_part_expr(expr, "DAY", "SQLITE") == 'DATE("t0"."TX_DATE")'
    assert sql_dialect.date_part_expr(expr, "MONTH", "SQLITE") == 'STRFTIME(\'%Y-%m\', "t0"."TX_DATE")'
    assert sql_dialect.date_part_expr(expr, "YEAR", "SQLITE") == 'STRFTIME(\'%Y\', "t0"."TX_DATE")'
    quarter = sql_dialect.date_part_expr(expr, "QUARTER", "SQLITE")
    assert "STRFTIME('%Y'" in quarter
    assert "STRFTIME('%m'" in quarter
    assert "'-Q'" in quarter or '"-Q"' in quarter or "-Q" in quarter


def test_date_part_expr_rejects_bad_part():
    with pytest.raises(ValueError):
        sql_dialect.date_part_expr('"t0"."TX_DATE"', "WEEK", "ORACLE")


def test_safe_divide_wraps_nullif():
    out = sql_dialect.safe_divide('SUM("t0"."REVENUE")', 'SUM("t0"."QUANTITY")')
    assert "NULLIF" in out
    assert 'NULLIF((SUM("t0"."QUANTITY")), 0)' in out
    assert out.startswith("(") and out.endswith(")")


def test_paged_sql_oracle():
    out = sql_dialect.paged_sql("SELECT a FROM t ORDER BY a", 50, 100, "ORACLE")
    assert out == "SELECT a FROM t ORDER BY a OFFSET 100 ROWS FETCH NEXT 50 ROWS ONLY"


def test_paged_sql_sqlite():
    out = sql_dialect.paged_sql("SELECT a FROM t ORDER BY a", 50, 100, "SQLITE")
    assert out == "SELECT a FROM t ORDER BY a LIMIT 50 OFFSET 100"


def test_top_limit_sql():
    assert sql_dialect.top_limit_sql("SELECT a FROM t", 10, "ORACLE") == "SELECT a FROM t FETCH FIRST 10 ROWS ONLY"
    assert sql_dialect.top_limit_sql("SELECT a FROM t", 10, "SQLITE") == "SELECT a FROM t LIMIT 10"


def test_paged_sql_rejects_bad_limit():
    with pytest.raises(ValueError):
        sql_dialect.paged_sql("SELECT a FROM t", 0, 0, "ORACLE")
    with pytest.raises(ValueError):
        sql_dialect.paged_sql("SELECT a FROM t", 10, -1, "SQLITE")


# ---------------------------------------------------------------------------
# Bước 2 — Graph Resolver (test viết trước; import lười để test Bước 1 vẫn chạy)
# ---------------------------------------------------------------------------


def _mk_field(fid, table_id, source_column, data_type, field_role="DIMENSION", **kw):
    d = {
        "id": fid,
        "table_id": table_id,
        "source_column": source_column,
        "field_code": source_column,
        "display_name": source_column,
        "description": None,
        "data_type": data_type,
        "field_role": field_role,
        "default_agg": "NONE",
        "format_mask": None,
        "is_visible": True,
        "is_filterable": True,
        "is_pk": False,
        "is_fk": False,
        "sort_by_field_id": None,
        "folder": None,
        "enable_date_hierarchy": False,
        "sensitivity": "NORMAL",
        "display_order": fid,
    }
    d.update(kw)
    return d


def _mk_table(tid, alias, role, fields, grain_desc=None, grain_keys=None):
    return {
        "id": tid,
        "model_version_id": 10,
        "source_owner": None,
        "source_object": alias,
        "object_type": "TABLE",
        "alias": alias,
        "display_name": alias,
        "table_role": role,
        "grain_desc": grain_desc,
        "grain_keys": grain_keys or [],
        "default_date_field": None,
        "is_hidden": False,
        "pos_x": 0,
        "pos_y": 0,
        "row_estimate": None,
        "description": None,
        "fields": fields,
    }


def _mk_rel(rid, name, from_table_id, from_column, to_table_id, to_column, **kw):
    d = {
        "id": rid,
        "model_version_id": 10,
        "name": name,
        "from_table_id": from_table_id,
        "from_column": from_column,
        "to_table_id": to_table_id,
        "to_column": to_column,
        "cardinality": "MANY_TO_ONE",
        "join_type": "LEFT_OUTER",
        "cross_filter": "SINGLE",
        "is_active": True,
        "validation_status": None,
        "validation": None,
    }
    d.update(kw)
    return d


def _mk_measure(mid, code, table_id, measure_type="SIMPLE", base_field_id=None, aggregation=None, expr_json=None):
    return {
        "id": mid,
        "model_version_id": 10,
        "table_id": table_id,
        "code": code,
        "name": code,
        "measure_type": measure_type,
        "base_field_id": base_field_id,
        "aggregation": aggregation,
        "expr_json": expr_json,
        "format_mask": None,
        "folder": None,
        "description": None,
    }


def _star_bundle(status="ACTIVE", extra_tables=None, extra_rels=None, extra_measures=None, extra_rls=None):
    fact = _mk_table(
        1,
        "FACT_SALES",
        "FACT",
        [
            _mk_field(101, 1, "SALES_ID", "NUMBER", "KEY", is_pk=True),
            _mk_field(102, 1, "CUSTOMER_ID", "NUMBER", "KEY", is_fk=True),
            _mk_field(103, 1, "DATE_ID", "NUMBER", "KEY", is_fk=True),
            _mk_field(104, 1, "SERVICE_ID", "NUMBER", "KEY", is_fk=True),
            _mk_field(105, 1, "TX_DATE", "DATETIME", enable_date_hierarchy=True),
            _mk_field(106, 1, "QUANTITY", "NUMBER", "MEASURE_CANDIDATE", default_agg="SUM"),
            _mk_field(107, 1, "REVENUE", "NUMBER", "MEASURE_CANDIDATE", default_agg="SUM"),
            _mk_field(108, 1, "ORG_CODE", "STRING"),
            _mk_field(109, 1, "NOTE", "STRING", "HIDDEN", is_visible=False),
        ],
        grain_desc="Theo đơn hàng",
        grain_keys=["SALES_ID"],
    )
    cust = _mk_table(
        2,
        "DIM_CUSTOMER",
        "DIMENSION",
        [
            _mk_field(201, 2, "CUSTOMER_ID", "NUMBER", "KEY", is_pk=True),
            _mk_field(202, 2, "CUSTOMER_NAME", "STRING"),
            _mk_field(203, 2, "ORG_CODE", "STRING"),
        ],
    )
    date = _mk_table(
        3,
        "DIM_DATE",
        "DIMENSION",
        [
            _mk_field(301, 3, "DATE_ID", "NUMBER", "KEY", is_pk=True),
            _mk_field(302, 3, "CAL_DATE", "DATE", enable_date_hierarchy=True),
            _mk_field(303, 3, "MONTH_NUM", "NUMBER"),
        ],
    )
    svc = _mk_table(
        4,
        "DIM_SERVICE",
        "DIMENSION",
        [
            _mk_field(401, 4, "SERVICE_ID", "NUMBER", "KEY", is_pk=True),
            _mk_field(402, 4, "SERVICE_NAME", "STRING"),
        ],
    )
    tables = [fact, cust, date, svc] + list(extra_tables or [])
    rels = [
        _mk_rel(1, "FK_SALES_CUSTOMER", 1, "CUSTOMER_ID", 2, "CUSTOMER_ID"),
        _mk_rel(2, "FK_SALES_DATE", 1, "DATE_ID", 3, "DATE_ID"),
        _mk_rel(3, "FK_SALES_SERVICE", 1, "SERVICE_ID", 4, "SERVICE_ID"),
    ] + list(extra_rels or [])
    measures = [
        _mk_measure(21, "REV_SUM", 1, base_field_id=107, aggregation="SUM"),
        _mk_measure(22, "QTY_SUM", 1, base_field_id=106, aggregation="SUM"),
        _mk_measure(
            23,
            "MARGIN_RATE",
            1,
            measure_type="CALCULATED",
            expr_json={
                "op": "DIVIDE",
                "left": {"op": "SUM", "arg": {"op": "FIELD", "field_id": 107}},
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
    ] + list(extra_measures or [])
    return {
        "model": {
            "id": 1,
            "code": "SALES",
            "name": "Sales",
            "description": None,
            "data_source_id": 1,
            "data_source": {
                "id": 1,
                "name": "SRC",
                "env": "DEV",
                "db_type": "SQLITE",
                "default_schema": "",
                "is_active": True,
            },
            "active_version_id": 10,
            "active_version_no": 1,
            "is_archived": False,
            "row_version": 1,
        },
        "version": {
            "id": 10,
            "model_id": 1,
            "version_no": 1,
            "status": status,
            "change_note": None,
            "validation": None,
            "published_by": None,
            "published_at": None,
            "created_by": "admin",
            "created_at": None,
            "updated_by": "admin",
            "updated_at": None,
            "row_version": 1,
        },
        "tables": tables,
        "relationships": rels,
        "measures": measures,
        "rls_policies": list(extra_rls or []),
    }


def _resolve(payload, bundle):
    from app.engine.semantic_planner import resolve_semantic_plan
    from app.schemas.semantic_query import SemanticQueryIntent

    return resolve_semantic_plan(SemanticQueryIntent(**payload), bundle)


def _intent(**overrides):
    payload = {
        "model_version_id": 10,
        "dimensions": [{"field_id": 202}],
        "measures": [{"measure_id": 21}],
        "filters": [],
        "sorts": [],
        "visual_type": "TABLE",
        "limit": 100,
        "offset": 0,
    }
    payload.update(overrides)
    return payload


def test_resolve_star_schema_1fact_2dim():
    plan = _resolve(
        _intent(
            dimensions=[{"field_id": 202}, {"field_id": 302, "date_part": "MONTH"}],
            measures=[{"measure_id": 21}],
        ),
        _star_bundle(),
    )
    assert plan.root_table["alias"] == "FACT_SALES"
    assert plan.primary_fact_table_id == 1
    assert sorted(plan.tables_used) == [1, 2, 3]
    assert len(plan.join_steps) == 2
    assert {s.child_table_id for s in plan.join_steps} == {2, 3}
    assert len(plan.selected_dims) == 2
    month_dim = [d for d in plan.selected_dims if d.field_id == 302][0]
    assert month_dim.date_part == "MONTH"
    assert month_dim.table_id == 3
    assert len(plan.selected_measures) == 1
    assert plan.selected_measures[0].measure_id == 21
    assert plan.selected_measures[0].output_alias == "REV_SUM"


def test_resolve_dim_only_query():
    plan = _resolve(_intent(dimensions=[{"field_id": 202}], measures=[]), _star_bundle())
    assert plan.root_table["alias"] == "DIM_CUSTOMER"
    assert plan.primary_fact_table_id is None
    assert plan.tables_used == [2]
    assert plan.join_steps == []


def test_resolve_dim_only_count_measure():
    plan = _resolve(
        _intent(dimensions=[{"field_id": 202}], measures=[{"field_id": 201, "aggregation": "COUNT"}]),
        _star_bundle(),
    )
    assert plan.root_table["alias"] == "DIM_CUSTOMER"
    assert plan.primary_fact_table_id is None
    assert plan.selected_measures[0].aggregation == "COUNT"


def test_resolve_rejects_draft_version():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(), _star_bundle(status="DRAFT"))
    assert exc.value.code == str(ErrorCode.MODEL_VERSION_LOCKED)


def test_resolve_rejects_archived_version():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(), _star_bundle(status="ARCHIVED"))
    assert exc.value.code == str(ErrorCode.MODEL_VERSION_LOCKED)


def test_resolve_rejects_validated_version():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(), _star_bundle(status="VALIDATED"))
    assert exc.value.code == str(ErrorCode.MODEL_VERSION_LOCKED)


def test_resolve_multi_fact_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    returns = _mk_table(
        5,
        "FACT_RETURNS",
        "FACT",
        [
            _mk_field(501, 5, "RETURN_ID", "NUMBER", "KEY", is_pk=True),
            _mk_field(502, 5, "AMOUNT", "NUMBER", "MEASURE_CANDIDATE", default_agg="SUM"),
        ],
        grain_desc="Theo phiếu trả",
        grain_keys=["RETURN_ID"],
    )
    ret_measure = _mk_measure(25, "RET_SUM", 5, base_field_id=502, aggregation="SUM")
    bundle = _star_bundle(extra_tables=[returns], extra_measures=[ret_measure])
    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(measures=[{"measure_id": 21}, {"measure_id": 25}]), bundle)
    assert exc.value.code == str(ErrorCode.MULTI_FACT_NOT_ALLOWED)
    assert "REV_SUM" in exc.value.message
    assert "RET_SUM" in exc.value.message


def test_resolve_ambiguous_duplicate_edge():
    from app.schemas.errors import ErrorCode, ServiceError

    dup = _mk_rel(9, "FK_SALES_CUSTOMER_2", 1, "CUSTOMER_ID", 2, "CUSTOMER_ID")
    bundle = _star_bundle(extra_rels=[dup])
    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(), bundle)
    assert exc.value.code == str(ErrorCode.AMBIGUOUS_PATH)
    assert "FK_SALES_CUSTOMER" in exc.value.message


def test_resolve_ambiguous_diamond_via_intermediate():
    from app.schemas.errors import ErrorCode, ServiceError

    region = _mk_table(
        5,
        "DIM_REGION",
        "DIMENSION",
        [
            _mk_field(501, 5, "REGION_ID", "NUMBER", "KEY", is_pk=True),
            _mk_field(502, 5, "REGION_NAME", "STRING"),
        ],
    )
    rels = [
        _mk_rel(9, "FK_CUST_REGION", 2, "REGION_ID", 5, "REGION_ID"),
        _mk_rel(10, "FK_SALES_REGION", 1, "REGION_ID", 5, "REGION_ID"),
    ]
    # FACT_SALES và DIM_CUSTOMER cần thêm cột REGION_ID để rel hợp lệ
    bundle = _star_bundle(extra_tables=[region], extra_rels=rels)
    bundle["tables"][0]["fields"].append(_mk_field(110, 1, "REGION_ID", "NUMBER", "KEY", is_fk=True))
    bundle["tables"][1]["fields"].append(_mk_field(204, 2, "REGION_ID", "NUMBER", "KEY", is_fk=True))
    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(dimensions=[{"field_id": 202}, {"field_id": 502}]), bundle)
    assert exc.value.code == str(ErrorCode.AMBIGUOUS_PATH)


def test_resolve_loop_triangle():
    from app.schemas.errors import ErrorCode, ServiceError

    bundle = _star_bundle()
    # Vòng có hướng: FACT -> DIM_CUSTOMER -> DIM_DATE -> FACT
    bundle["relationships"] = [
        _mk_rel(1, "R_AB", 1, "CUSTOMER_ID", 2, "CUSTOMER_ID"),
        _mk_rel(2, "R_BC", 2, "ORG_CODE", 3, "MONTH_NUM"),
        _mk_rel(3, "R_CA", 3, "DATE_ID", 1, "DATE_ID"),
    ]
    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(dimensions=[{"field_id": 202}, {"field_id": 302}]), bundle)
    assert exc.value.code == str(ErrorCode.RELATIONSHIP_LOOP)


def test_resolve_self_reference_loop():
    from app.schemas.errors import ErrorCode, ServiceError

    bundle = _star_bundle(extra_rels=[_mk_rel(9, "R_SELF", 2, "CUSTOMER_ID", 2, "CUSTOMER_ID")])
    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(dimensions=[{"field_id": 202}], measures=[]), bundle)
    assert exc.value.code == str(ErrorCode.RELATIONSHIP_LOOP)


def test_resolve_non_numeric_sum_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(measures=[{"field_id": 202, "aggregation": "SUM"}]), _star_bundle())
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)
    assert "SUM" in exc.value.message


def test_resolve_hidden_field_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(dimensions=[{"field_id": 109}]), _star_bundle())
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_resolve_missing_field_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(dimensions=[{"field_id": 9999}]), _star_bundle())
    assert exc.value.code == str(ErrorCode.MODEL_INVALID)


def test_resolve_missing_measure_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(measures=[{"measure_id": 9999}]), _star_bundle())
    assert exc.value.code == str(ErrorCode.MODEL_INVALID)


def test_resolve_calculated_measure_nested_refs():
    plan = _resolve(_intent(dimensions=[], measures=[{"measure_id": 23}]), _star_bundle())
    assert plan.tables_used == [1]
    assert plan.selected_measures[0].measure_id == 23
    assert plan.selected_measures[0].output_alias == "MARGIN_RATE"


def test_resolve_calculated_measure_refs_other_measure():
    plan = _resolve(_intent(dimensions=[], measures=[{"measure_id": 24}]), _star_bundle())
    assert plan.tables_used == [1]
    assert plan.selected_measures[0].output_alias == "REV_X100"


def test_resolve_measure_cycle_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    m5 = _mk_measure(
        25,
        "CYC_A",
        1,
        measure_type="CALCULATED",
        expr_json={"op": "MEASURE", "measure_id": 26},
    )
    m6 = _mk_measure(
        26,
        "CYC_B",
        1,
        measure_type="CALCULATED",
        expr_json={"op": "MEASURE", "measure_id": 25},
    )
    bundle = _star_bundle(extra_measures=[m5, m6])
    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(measures=[{"measure_id": 25}]), bundle)
    assert exc.value.code == str(ErrorCode.MODEL_INVALID)


def test_resolve_filter_on_missing_field():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(filters=[{"field_id": 9999, "operator": "=", "value": "X"}]), _star_bundle())
    assert exc.value.code == str(ErrorCode.MODEL_INVALID)


def test_resolve_rejects_dict_filter_value():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(filters=[{"field_id": 202, "operator": "=", "value": {"$ne": "A"}}]), _star_bundle())
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_resolve_sort_on_unselected_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(sorts=[{"target_type": "FIELD", "id": 203, "direction": "ASC"}]), _star_bundle())
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_resolve_duplicate_output_alias_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(
            _intent(dimensions=[{"field_id": 202, "alias": "ten"}, {"field_id": 203, "alias": "ten"}]),
            _star_bundle(),
        )
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_resolve_unreachable_table_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    # DIM_CUSTOMER và DIM_SERVICE không có quan hệ trực tiếp, không có Fact
    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(dimensions=[{"field_id": 202}, {"field_id": 402}], measures=[]), _star_bundle())
    assert exc.value.code == str(ErrorCode.MODEL_INVALID)


def test_resolve_rls_only_for_involved_tables():
    rls = [
        {
            "id": 1,
            "model_version_id": 10,
            "table_id": 2,
            "column_name": "ORG_CODE",
            "policy_type": "OWNER_USERNAME",
            "scope_attr": None,
            "admin_bypass": True,
            "is_active": True,
            "description": None,
        },
        {
            "id": 2,
            "model_version_id": 10,
            "table_id": 4,
            "column_name": "SERVICE_NAME",
            "policy_type": "ROLE_LIST",
            "scope_attr": "OPERATOR",
            "admin_bypass": False,
            "is_active": True,
            "description": None,
        },
    ]
    plan = _resolve(_intent(), _star_bundle(extra_rls=rls))
    assert len(plan.resolved_rls) == 1
    assert plan.resolved_rls[0].table_id == 2
    assert plan.resolved_rls[0].policy_type == "OWNER_USERNAME"


def test_resolve_ignores_inactive_duplicate_rel():
    dup = _mk_rel(9, "FK_SALES_CUSTOMER_2", 1, "CUSTOMER_ID", 2, "CUSTOMER_ID", is_active=False)
    plan = _resolve(_intent(), _star_bundle(extra_rels=[dup]))
    assert plan.primary_fact_table_id == 1
    assert len(plan.join_steps) == 1


def test_resolve_multi_fact_via_dimensions_only():
    from app.schemas.errors import ErrorCode, ServiceError

    returns = _mk_table(
        5,
        "FACT_RETURNS",
        "FACT",
        [_mk_field(501, 5, "RETURN_ID", "NUMBER", "KEY", is_pk=True)],
        grain_desc="Theo phiếu trả",
        grain_keys=["RETURN_ID"],
    )
    bundle = _star_bundle(extra_tables=[returns])
    with pytest.raises(ServiceError) as exc:
        _resolve(
            _intent(
                dimensions=[{"field_id": 108}, {"field_id": 501}],
                measures=[],
            ),
            bundle,
        )
    assert exc.value.code == str(ErrorCode.MULTI_FACT_NOT_ALLOWED)
    assert "FACT_SALES" in exc.value.message
    assert "FACT_RETURNS" in exc.value.message


def test_resolve_const_only_measure_without_table_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    const_measure = _mk_measure(
        25, "CONST_FIVE", None, measure_type="CALCULATED", expr_json={"op": "CONST", "value": 5}
    )
    bundle = _star_bundle(extra_measures=[const_measure])
    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(dimensions=[], measures=[{"measure_id": 25}]), bundle)
    assert exc.value.code == str(ErrorCode.MODEL_INVALID)


def test_date_part_quarter_guards_null_both_dialects():
    q_sql = sql_dialect.date_part_expr('"t0"."TX_DATE"', "QUARTER", "SQLITE")
    q_ora = sql_dialect.date_part_expr('"t0"."TX_DATE"', "QUARTER", "ORACLE")
    assert q_sql.startswith('CASE WHEN "t0"."TX_DATE" IS NULL THEN NULL ELSE ')
    assert q_ora.startswith('CASE WHEN "t0"."TX_DATE" IS NULL THEN NULL ELSE ')


def test_resolve_date_part_non_date_column_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(dimensions=[{"field_id": 202, "date_part": "MONTH"}]), _star_bundle())
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_resolve_hidden_table_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    bundle = _star_bundle()
    bundle["tables"][1]["is_hidden"] = True  # DIM_CUSTOMER
    for kw in (
        {"dimensions": [{"field_id": 202}]},
        {"dimensions": [], "measures": [{"field_id": 202, "aggregation": "COUNT"}]},
        {"dimensions": [], "measures": [{"measure_id": 21}], "filters": [{"field_id": 202, "operator": "=", "value": "A"}]},
    ):
        with pytest.raises(ServiceError) as exc:
            _resolve(_intent(**kw), bundle)
        assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)


def test_resolve_snowflake_multihop_joins_intermediate_and_applies_rls():
    region = _mk_table(
        5,
        "DIM_REGION",
        "DIMENSION",
        [
            _mk_field(501, 5, "REGION_ID", "NUMBER", "KEY", is_pk=True),
            _mk_field(502, 5, "REGION_NAME", "STRING"),
        ],
    )
    bundle = _star_bundle(
        extra_tables=[region],
        extra_rels=[_mk_rel(9, "FK_CUST_REGION", 2, "REGION_ID", 5, "REGION_ID")],
        extra_rls=[
            {
                "id": 1,
                "model_version_id": 10,
                "table_id": 2,
                "column_name": "ORG_CODE",
                "policy_type": "OWNER_USERNAME",
                "scope_attr": None,
                "admin_bypass": True,
                "is_active": True,
                "description": None,
            }
        ],
    )
    bundle["tables"][1]["fields"].append(_mk_field(204, 2, "REGION_ID", "NUMBER", "KEY", is_fk=True))
    # Không chọn cột nào của DIM_CUSTOMER (id=2), chỉ chọn FACT (21) và DIM_REGION (502).
    plan = _resolve(_intent(dimensions=[{"field_id": 502}], measures=[{"measure_id": 21}]), bundle)
    assert plan.tables_used == [1, 2, 5]
    assert [s.rel_name for s in plan.join_steps] == ["FK_SALES_CUSTOMER", "FK_CUST_REGION"]
    assert len(plan.resolved_rls) == 1
    assert plan.resolved_rls[0].table_id == 2


def test_resolve_snowflake_hidden_diamond_blocked():
    from app.schemas.errors import ErrorCode, ServiceError

    region = _mk_table(
        5,
        "DIM_REGION",
        "DIMENSION",
        [
            _mk_field(501, 5, "REGION_ID", "NUMBER", "KEY", is_pk=True),
            _mk_field(502, 5, "REGION_NAME", "STRING"),
        ],
    )
    channel = _mk_table(
        6,
        "DIM_CHANNEL",
        "DIMENSION",
        [
            _mk_field(601, 6, "CHANNEL_ID", "NUMBER", "KEY", is_pk=True),
            _mk_field(602, 6, "REGION_ID", "NUMBER", "KEY", is_fk=True),
        ],
    )
    bundle = _star_bundle(
        extra_tables=[region, channel],
        extra_rels=[
            _mk_rel(9, "FK_CUST_REGION", 2, "REGION_ID", 5, "REGION_ID"),
            _mk_rel(10, "FK_SALES_CHANNEL", 1, "CHANNEL_ID", 6, "CHANNEL_ID"),
            _mk_rel(11, "FK_CHANNEL_REGION", 6, "REGION_ID", 5, "REGION_ID"),
        ],
    )
    bundle["tables"][0]["fields"].append(_mk_field(110, 1, "CHANNEL_ID", "NUMBER", "KEY", is_fk=True))
    bundle["tables"][1]["fields"].append(_mk_field(204, 2, "REGION_ID", "NUMBER", "KEY", is_fk=True))
    with pytest.raises(ServiceError) as exc:
        _resolve(_intent(dimensions=[{"field_id": 502}], measures=[{"measure_id": 21}]), bundle)
    assert exc.value.code == str(ErrorCode.AMBIGUOUS_PATH)


def test_resolve_sort_by_adhoc_measure_and_case_insensitive_alias():
    from app.schemas.errors import ErrorCode, ServiceError

    plan = _resolve(
        _intent(
            dimensions=[{"field_id": 202}],
            measures=[{"field_id": 107, "aggregation": "SUM", "alias": "TOTAL_REV"}],
            sorts=[{"target_type": "MEASURE", "alias": "total_rev", "direction": "DESC"}],
        ),
        _star_bundle(),
    )
    assert plan.resolved_sorts[0].output_alias == "TOTAL_REV"
    assert plan.resolved_sorts[0].direction == "DESC"

    with pytest.raises(ServiceError) as exc:
        _resolve(
            _intent(
                dimensions=[{"field_id": 202, "alias": "ColA"}, {"field_id": 203, "alias": "cola"}],
                measures=[],
            ),
            _star_bundle(),
        )
    assert exc.value.code == str(ErrorCode.VALIDATION_ERROR)
