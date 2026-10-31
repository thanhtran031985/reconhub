from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from pydantic_core import InitErrorDetails, ValidationError

NAME_REGEX = r"^[A-Z][A-Z0-9_]{0,29}$"
_NAME_PATTERN = re.compile(NAME_REGEX)


class RowFilter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: str | None = None
    excel_col: str | None = None
    op: Literal["is_null", "not_null", "equals", "not_equals", "in", "regex"]
    value: Any = None

    @model_validator(mode="after")
    def _validate_target(self) -> RowFilter:
        if not self.field and not self.excel_col:
            raise ValueError("RowFilter yêu cầu ít nhất một trong hai: 'field' hoặc 'excel_col'")
        return self


class RowFilters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    drop_if: list[RowFilter] = Field(default_factory=list)
    keep_if: list[RowFilter] = Field(default_factory=list)


class FileSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sheet: str
    sheet_pattern: str | None = None
    header_row: int = Field(default=1, ge=1)
    data_start_row: int = Field(default=2, ge=1)
    skip_footer_rows: int = Field(default=0, ge=0)
    detect_by_headers: list[str] = Field(default_factory=list)
    row_filters: RowFilters = Field(default_factory=RowFilters)
    thousand_sep: str = ","
    decimal_sep: str = "."

    @field_validator("data_start_row")
    @classmethod
    def _validate_data_start_row(cls, v: int, info: ValidationInfo) -> int:
        header_row = info.data.get("header_row", 1)
        if v <= header_row:
            raise ValueError(f"data_start_row ({v}) phải lớn hơn header_row ({header_row})")
        return v


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(pattern=NAME_REGEX)
    label: str
    excel: str | None = None
    excel_aliases: list[str] = Field(default_factory=list)
    db: str | None = None
    type: Literal["text", "number", "date", "datetime"]
    format: str | None = None
    norm: list[str | dict[str, Any]] = Field(default_factory=list)
    required: bool = False


class DerivedExpr(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fn: Literal["trunc_day", "trunc_month", "concat", "substr", "coalesce"]
    args: list[Any] = Field(default_factory=list)


class DerivedSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(pattern=NAME_REGEX)
    label: str
    type: Literal["text", "number", "date", "datetime"]
    expr: DerivedExpr


class SourceFilter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    param: str
    column: str
    op: Literal[">=", "<=", "=", "in", "like"]
    cast: Literal["none", "trunc_day"] = "none"
    skip_if_empty: bool = False


class StaticFilter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    column: str
    op: Literal["=", "!=", ">", "<", ">=", "<=", "in", "like"]
    value: Any = None


class ParamSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    type: Literal["text", "number", "date", "datetime"]
    source: Literal["user", "default"]
    default: Any = None
    label: str
    required: bool = False
    suggest: Literal["yesterday", "last_month", "none"] = "none"


class DbSourceSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: Literal["table", "sql"] = "table"
    table: str | None = None
    filters: list[SourceFilter] = Field(default_factory=list)
    static_where: list[StaticFilter] = Field(default_factory=list)
    sql: str | None = None
    params: list[ParamSpec] = Field(default_factory=list)
    pushdown_aggregate: bool = True


class TimeFilterSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    excel_field: str | None = None
    db_column: str | None = None
    granularity: Literal["datetime", "date"] = "datetime"
    max_range_days: int = Field(default=93, gt=0)


class MeasureSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(pattern=NAME_REGEX)
    label: str
    agg: Literal["sum", "count", "count_distinct", "min", "max", "first_distinct", "value"]
    field: str | None = None
    compare: Literal["exact", "abs_tol", "pct_tol", "display_only"] = "exact"
    tolerance: Decimal | float | None = None
    round: int | None = None
    ignore_case: bool = False
    null_as: Literal["null", "zero", "empty"] = "null"


class ProfileSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str = Field(pattern=NAME_REGEX)
    name: str
    is_default: bool = False
    aggregate: bool = True
    group_by: list[str] = Field(min_length=1)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    measures: list[MeasureSpec] = Field(min_length=1)
    main_measure: str | None = None
    drilldown_to: str | None = None


class ControlTotalLocate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    excel_col: str
    equals: Any


class ControlTotalSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    locate: ControlTotalLocate
    value_col: str
    tolerance: Decimal | float = 0


def _make_error(loc: tuple[int | str, ...], msg: str, input_val: Any = None) -> InitErrorDetails:
    return {
        "type": "value_error",
        "loc": loc,
        "input": input_val,
        "ctx": {"error": ValueError(msg)},
    }


class TemplateConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    file: FileSpec
    fields: list[FieldSpec]
    derived: list[DerivedSpec] = Field(default_factory=list)
    db_source: DbSourceSpec
    time_filter: TimeFilterSpec | None = None
    control_total: ControlTotalSpec | None = None
    profiles: list[ProfileSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_cross_rules(self) -> TemplateConfig:
        errors: list[InitErrorDetails] = []

        field_types: dict[str, str] = {}
        excel_fields: set[str] = set()
        db_fields: set[str] = set()

        # 1. Trùng lặp trường trong fields
        seen_names: dict[str, tuple[str, int]] = {}
        for idx, f in enumerate(self.fields):
            if f.name in seen_names:
                prev_loc, prev_idx = seen_names[f.name]
                errors.append(
                    _make_error(
                        ("fields", idx, "name"),
                        f"Trùng tên trường '{f.name}' (đã có trong {prev_loc}[{prev_idx}])",
                        f.name,
                    )
                )
            else:
                seen_names[f.name] = ("fields", idx)
            field_types[f.name] = f.type
            if f.excel or f.excel_aliases:
                excel_fields.add(f.name)
            if f.db:
                db_fields.add(f.name)

        # Trùng lặp trường trong derived
        for idx, d in enumerate(self.derived):
            if d.name in seen_names:
                prev_loc, prev_idx = seen_names[d.name]
                errors.append(
                    _make_error(
                        ("derived", idx, "name"),
                        f"Trùng tên trường derived '{d.name}' (đã có trong {prev_loc}[{prev_idx}])",
                        d.name,
                    )
                )
            else:
                seen_names[d.name] = ("derived", idx)
            field_types[d.name] = d.type
            excel_fields.add(d.name)
            db_fields.add(d.name)

        # 2. DbSourceSpec validation
        if self.db_source.kind == "table" and not self.db_source.table:
            errors.append(
                _make_error(("db_source", "table"), "Bắt buộc phải chỉ định bảng/view ('table') khi kind='table'")
            )

        param_map: dict[str, tuple[int, ParamSpec]] = {
            p.name: (i, p) for i, p in enumerate(self.db_source.params)
        }
        for req_param in ("p_from", "p_to"):
            if req_param not in param_map:
                errors.append(
                    _make_error(("db_source", "params"), f"Thiếu tham số bắt buộc '{req_param}' trong params")
                )
            else:
                i, p = param_map[req_param]
                if p.source != "user":
                    errors.append(
                        _make_error(
                            ("db_source", "params", i, "source"),
                            f"Tham số '{req_param}' phải có source='user'",
                            p.source,
                        )
                    )

        if self.db_source.kind == "table":
            filter_params = {f.param for f in self.db_source.filters}
            for req_param in ("p_from", "p_to"):
                if req_param not in filter_params:
                    errors.append(
                        _make_error(
                            ("db_source", "filters"),
                            f"Thiếu filter cho tham số '{req_param}' trong filters khi kind='table'",
                        )
                    )

        # 3. Profiles validation
        default_count = sum(1 for p in self.profiles if p.is_default)
        if default_count != 1:
            errors.append(
                _make_error(
                    ("profiles",),
                    f"Cấu hình profiles phải có đúng 1 profile mặc định (hiện có {default_count})",
                )
            )

        profile_codes: set[str] = {p.code for p in self.profiles}
        for p_idx, prof in enumerate(self.profiles):
            for g_idx, g_col in enumerate(prof.group_by):
                if g_col not in seen_names:
                    errors.append(
                        _make_error(
                            ("profiles", p_idx, "group_by", g_idx),
                            f"Trường group_by '{g_col}' không tồn tại trong fields/derived",
                            g_col,
                        )
                    )
                else:
                    if g_col not in excel_fields:
                        errors.append(
                            _make_error(
                                ("profiles", p_idx, "group_by", g_idx),
                                f"Trường group_by '{g_col}' không có nguồn Excel",
                                g_col,
                            )
                        )
                    if g_col not in db_fields:
                        errors.append(
                            _make_error(
                                ("profiles", p_idx, "group_by", g_idx),
                                f"Trường group_by '{g_col}' không có cột tương ứng phía DB",
                                g_col,
                            )
                        )

            measure_names: set[str] = set()
            for m_idx, m in enumerate(prof.measures):
                measure_names.add(m.name)
                if m.field:
                    if m.field not in seen_names:
                        errors.append(
                            _make_error(
                                ("profiles", p_idx, "measures", m_idx, "field"),
                                f"Trường '{m.field}' không tồn tại trong fields/derived",
                                m.field,
                            )
                        )
                    else:
                        f_type = field_types[m.field]
                        if m.agg == "sum" and f_type != "number":
                            errors.append(
                                _make_error(
                                    ("profiles", p_idx, "measures", m_idx, "agg"),
                                    f"Measure '{m.name}' có agg='sum' nhưng trường '{m.field}' có kiểu '{f_type}' (cần 'number')",
                                    m.agg,
                                )
                            )
                elif m.agg != "count":
                    errors.append(
                        _make_error(
                            ("profiles", p_idx, "measures", m_idx, "field"),
                            f"Measure '{m.name}' thiếu 'field'",
                        )
                    )

                if m.agg == "value" and prof.aggregate:
                    errors.append(
                        _make_error(
                            ("profiles", p_idx, "measures", m_idx, "agg"),
                            f"Measure '{m.name}' có agg='value' chỉ được phép khi aggregate=False",
                            m.agg,
                        )
                    )

            if prof.main_measure and prof.main_measure not in measure_names:
                errors.append(
                    _make_error(
                        ("profiles", p_idx, "main_measure"),
                        f"main_measure '{prof.main_measure}' không tồn tại trong danh sách measures",
                        prof.main_measure,
                    )
                )

            if prof.drilldown_to and prof.drilldown_to not in profile_codes:
                errors.append(
                    _make_error(
                        ("profiles", p_idx, "drilldown_to"),
                        f"drilldown_to '{prof.drilldown_to}' không trỏ tới profile hợp lệ",
                        prof.drilldown_to,
                    )
                )

        # 4. Kiểm tra chu trình drilldown (cycle)
        drill_map: dict[str, str] = {p.code: p.drilldown_to for p in self.profiles if p.drilldown_to}
        for code in drill_map:
            visited = set()
            curr = code
            while curr in drill_map:
                if curr in visited:
                    errors.append(
                        _make_error(
                            ("profiles",),
                            f"Phát hiện chu trình vòng lặp (drilldown cycle) bắt đầu từ '{code}'",
                            code,
                        )
                    )
                    break
                visited.add(curr)
                curr = drill_map[curr]

        # 5. Kiểm tra time_filter
        if self.time_filter and self.time_filter.excel_field:
            if self.time_filter.excel_field not in seen_names:
                errors.append(
                    _make_error(
                        ("time_filter", "excel_field"),
                        f"Trường time_filter.excel_field '{self.time_filter.excel_field}' không tồn tại trong fields/derived",
                        self.time_filter.excel_field,
                    )
                )

        if errors:
            raise ValidationError.from_exception_data("TemplateConfig", errors)

        return self