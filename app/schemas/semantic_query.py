"""Schemas Pydantic cho Semantic Query Planner (Task 108).

Đầu vào duy nhất của Planner là ``SemanticQueryIntent`` — tuyệt đối không
nhận raw SQL từ browser. Mọi tên field/measure đều được phân giải theo
metadata whitelist của version ACTIVE trước khi biên dịch SQL.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.semantic_model import FIELD_CODE_RE

FILTER_OPERATORS = ("=", ">=", "<=", "BETWEEN", "IN", "LIKE_PREFIX", "IS_NULL", "RELATIVE_DATE")
DATE_PARTS = ("DAY", "MONTH", "QUARTER", "YEAR")
AGGREGATIONS = ("SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT")
VISUAL_TYPES = ("TABLE", "BAR", "LINE", "KPI")
RELATIVE_DATE_VALUES = ("TODAY", "YESTERDAY", "LAST_7_DAYS", "THIS_MONTH", "LAST_MONTH", "THIS_YEAR")


class QueryFieldSelection(BaseModel):
    """Một chiều (dimension) được chọn: field + phần ngày ảo tùy chọn."""

    field_id: int = Field(gt=0)
    date_part: Literal["DAY", "MONTH", "QUARTER", "YEAR"] | None = None
    alias: str | None = Field(default=None, max_length=128, pattern=FIELD_CODE_RE)


class QueryMeasureSelection(BaseModel):
    """Một measure: hoặc tham chiếu measure có sẵn, hoặc ad-hoc field + aggregation."""

    measure_id: int | None = Field(default=None, gt=0)
    field_id: int | None = Field(default=None, gt=0)
    aggregation: Literal["SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"] | None = None
    alias: str | None = Field(default=None, max_length=128, pattern=FIELD_CODE_RE)

    @model_validator(mode="after")
    def _exactly_one_source(self) -> QueryMeasureSelection:
        if self.measure_id is not None and (self.field_id is not None or self.aggregation is not None):
            raise ValueError("Measure chỉ dùng measure_id hoặc field_id + aggregation, không dùng cả hai.")
        if self.measure_id is None:
            if self.field_id is None or self.aggregation is None:
                raise ValueError("Measure ad-hoc cần đủ field_id và aggregation.")
        return self


class QueryFilter(BaseModel):
    """Một bộ lọc trên field: operator whitelist + giá trị qua bind param."""

    field_id: int = Field(gt=0)
    operator: Literal["=", ">=", "<=", "BETWEEN", "IN", "LIKE_PREFIX", "IS_NULL", "RELATIVE_DATE"]
    value: Any = None

    @model_validator(mode="after")
    def _check_value_shape(self) -> QueryFilter:
        op = self.operator
        val = self.value
        if op == "IS_NULL":
            return self
        if op == "BETWEEN":
            if not isinstance(val, list) or len(val) != 2:
                raise ValueError("BETWEEN cần value là danh sách đúng 2 phần tử.")
            return self
        if op == "IN":
            if not isinstance(val, list) or not val:
                raise ValueError("IN cần value là danh sách không rỗng.")
            return self
        if op == "RELATIVE_DATE":
            if not isinstance(val, str) or val not in RELATIVE_DATE_VALUES:
                raise ValueError(f"RELATIVE_DATE cần value thuộc {RELATIVE_DATE_VALUES}.")
            return self
        if val is None:
            raise ValueError(f"Toán tử {op} cần có value.")
        return self


class QuerySort(BaseModel):
    """Sắp xếp theo field hoặc measure đã chọn."""

    target_type: Literal["FIELD", "MEASURE"]
    id: int = Field(gt=0)
    direction: Literal["ASC", "DESC"] = "ASC"


class SemanticQueryIntent(BaseModel):
    """Ý định báo cáo: toàn bộ đầu vào của Query Planner."""

    model_version_id: int = Field(gt=0)
    dimensions: list[QueryFieldSelection] = Field(default_factory=list)
    measures: list[QueryMeasureSelection] = Field(default_factory=list)
    filters: list[QueryFilter] = Field(default_factory=list)
    sorts: list[QuerySort] = Field(default_factory=list)
    visual_type: Literal["TABLE", "BAR", "LINE", "KPI"] = "TABLE"
    limit: int = Field(default=500, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)
    request_seq: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _needs_selection(self) -> SemanticQueryIntent:
        if not self.dimensions and not self.measures:
            raise ValueError("Intent cần ít nhất một dimension hoặc measure.")
        return self


class SemanticQueryPlan(BaseModel):
    """Kết quả biên dịch: SQL read-only + binds + metadata kế hoạch."""

    sql: str
    binds: dict[str, Any] = Field(default_factory=dict)
    dialect: Literal["ORACLE", "SQLITE"]
    primary_fact_table_id: int | None = None
    tables_used: list[int] = Field(default_factory=list)
    output_columns: list[dict[str, Any]] = Field(default_factory=list)
    rls_applied: bool = False
    warnings: list[str] = Field(default_factory=list)
    # Giới hạn dòng thực tế đã áp vào SQL (service dùng để tính cờ truncated).
    row_limit: int = 500
    # True khi chart (BAR/LINE) lấy thêm 1 dòng so với số điểm hiển thị để phát hiện truncated.
    fetch_extra_row: bool = False
    # SQL chưa có ORDER BY/phân trang (service dùng làm subquery đếm total cho for_run).
    base_sql: str = ""


class SemanticQueryResult(BaseModel):
    """Kết quả thực thi preview: dữ liệu + metadata cột + cờ cắt ngắn."""

    columns: list[dict[str, Any]] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    warning_message: str | None = None
    request_seq: int | None = None
    elapsed_ms: int = 0
