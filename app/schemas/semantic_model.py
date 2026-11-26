"""Schemas Pydantic và hằng quy tắc cho Semantic Model (Task 106)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,59}$")
FIELD_CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
IDENT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")

TABLE_ROLES = ("FACT", "DIMENSION", "BRIDGE", "UNCLASSIFIED")
FIELD_ROLES = ("DIMENSION", "MEASURE_CANDIDATE", "KEY", "HIDDEN")
ALL_AGGREGATIONS = ("NONE", "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT")
MEASURE_AGGREGATIONS = ("SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT")
SENSITIVITIES = ("NORMAL", "INTERNAL", "RESTRICTED")
CARDINALITIES = ("MANY_TO_ONE", "ONE_TO_ONE")
JOIN_TYPES = ("LEFT_OUTER", "INNER")
CROSS_FILTERS = ("SINGLE",)
RLS_POLICY_TYPES = ("OWNER_USERNAME", "ROLE_LIST", "ORG_SCOPE_HOOK")

# Quy tắc Default Aggregation theo DATA_TYPE chuẩn của ReconHub
ALLOWED_AGG_BY_TYPE: dict[str, tuple[str, ...]] = {
    "NUMBER": ("NONE", "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"),
    "STRING": ("NONE", "COUNT", "COUNT_DISTINCT"),
    "DATE": ("NONE", "MIN", "MAX", "COUNT"),
    "DATETIME": ("NONE", "MIN", "MAX", "COUNT"),
    "BOOLEAN": ("NONE", "COUNT"),
    "BINARY": ("NONE",),
}

# Các phép toán whitelist cho Calculated Measure AST (tuyệt đối không raw SQL)
AST_AGG_OPS = frozenset({"SUM", "COUNT", "COUNT_DISTINCT", "AVG", "MIN", "MAX"})
AST_ARITH_OPS = frozenset({"ADD", "SUB", "MUL", "DIV", "DIVIDE"})
AST_FUNC_OPS = frozenset({"ROUND", "COALESCE", "CASE"})
AST_LEAF_OPS = frozenset({"FIELD", "MEASURE", "CONST"})
AST_ALL_OPS = AST_AGG_OPS | AST_ARITH_OPS | AST_FUNC_OPS | AST_LEAF_OPS


def allowed_aggregations_for(data_type: str) -> tuple[str, ...]:
    """Danh sách aggregation hợp lệ theo DATA_TYPE."""
    return ALLOWED_AGG_BY_TYPE.get(str(data_type or "STRING").upper(), ("NONE",))


class ModelCreateDTO(BaseModel):
    code: str = Field(pattern=CODE_RE)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    data_source_id: int = Field(gt=0)


class ModelCloneDTO(BaseModel):
    code: str = Field(pattern=CODE_RE)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)


class TablePositionDTO(BaseModel):
    table_id: int = Field(gt=0)
    pos_x: int
    pos_y: int


class DraftSaveDTO(BaseModel):
    code: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    expected_row_version: int | None = Field(default=None, ge=1)
    positions: list[TablePositionDTO] = Field(default_factory=list)


class TableAddDTO(BaseModel):
    source_owner: str | None = Field(default=None, max_length=60)
    source_object: str = Field(min_length=1, max_length=128, pattern=IDENT_RE)
    object_type: Literal["TABLE", "VIEW"] = "TABLE"
    alias: str | None = Field(default=None, min_length=1, max_length=60, pattern=FIELD_CODE_RE)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    table_role: Literal["FACT", "DIMENSION", "BRIDGE", "UNCLASSIFIED"] | None = None
    pos_x: int = 0
    pos_y: int = 0
    description: str | None = Field(default=None, max_length=500)


class TableUpdateDTO(BaseModel):
    alias: str | None = Field(default=None, min_length=1, max_length=60, pattern=FIELD_CODE_RE)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    table_role: Literal["FACT", "DIMENSION", "BRIDGE", "UNCLASSIFIED"] | None = None
    grain_desc: str | None = Field(default=None, max_length=500)
    grain_keys: list[str] | None = None
    default_date_field: str | None = Field(default=None, max_length=128)
    is_hidden: bool | None = None
    pos_x: int | None = None
    pos_y: int | None = None
    description: str | None = Field(default=None, max_length=500)


class FieldUpdateDTO(BaseModel):
    field_code: str | None = Field(default=None, min_length=1, max_length=128, pattern=FIELD_CODE_RE)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    field_role: Literal["DIMENSION", "MEASURE_CANDIDATE", "KEY", "HIDDEN"] | None = None
    default_agg: Literal["NONE", "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"] | None = None
    format_mask: str | None = Field(default=None, max_length=100)
    is_visible: bool | None = None
    is_filterable: bool | None = None
    sort_by_field_id: int | None = Field(default=None, ge=1)
    clear_sort_by: bool = False
    folder: str | None = Field(default=None, max_length=100)
    enable_date_hierarchy: bool | None = None
    sensitivity: Literal["NORMAL", "INTERNAL", "RESTRICTED"] | None = None


class MeasureUpsertDTO(BaseModel):
    id: int | None = Field(default=None, ge=1)
    table_id: int | None = Field(default=None, ge=1)
    code: str = Field(pattern=CODE_RE)
    name: str = Field(min_length=1, max_length=200)
    measure_type: Literal["SIMPLE", "CALCULATED"] = "SIMPLE"
    base_field_id: int | None = Field(default=None, ge=1)
    aggregation: Literal["SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"] | None = None
    expr_json: dict[str, Any] | None = None
    format_mask: str | None = Field(default=None, max_length=100)
    folder: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class RelationshipUpsertDTO(BaseModel):
    id: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=120)
    from_table_id: int = Field(gt=0)
    from_column: str = Field(min_length=1, max_length=128, pattern=IDENT_RE)
    to_table_id: int = Field(gt=0)
    to_column: str = Field(min_length=1, max_length=128, pattern=IDENT_RE)
    cardinality: Literal["MANY_TO_ONE", "ONE_TO_ONE"] = "MANY_TO_ONE"
    join_type: Literal["LEFT_OUTER", "INNER"] = "LEFT_OUTER"
    cross_filter: Literal["SINGLE"] = "SINGLE"
    is_active: bool = True


class RlsPolicyUpsertDTO(BaseModel):
    id: int | None = Field(default=None, ge=1)
    table_id: int = Field(gt=0)
    column_name: str = Field(min_length=1, max_length=128, pattern=IDENT_RE)
    policy_type: Literal["OWNER_USERNAME", "ROLE_LIST", "ORG_SCOPE_HOOK"] = "OWNER_USERNAME"
    scope_attr: str | None = Field(default=None, max_length=60)
    admin_bypass: bool = True
    is_active: bool = True
    description: str | None = Field(default=None, max_length=500)


class PublishModelDTO(BaseModel):
    change_note: str = Field(min_length=1, max_length=500)
