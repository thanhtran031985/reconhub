"""Pydantic schemas cho Report Studio — task 109 Bước 2.

Visual gắn vào một RECON_RPT_TPL_VER có SOURCE_TYPE='SEMANTIC_MODEL'
và MODEL_VERSION_ID trỏ phiên bản model ACTIVE đã pin. Mọi field/measure
trong visual phải thuộc đúng phiên bản model đó (kiểm tra ở service).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

VISUAL_TYPES = ("TABLE", "MATRIX", "KPI", "BAR", "LINE")
WELL_ROLES = ("X", "Y", "ROWS", "COLUMNS", "VALUES", "VALUE", "SERIES")
GRID_SPANS = (3, 4, 6, 8, 12)
HEIGHT_SIZES = ("S", "M", "L")
AGGREGATIONS = ("NONE", "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT")
DATE_PARTS = ("DAY", "MONTH", "QUARTER", "YEAR")

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,59}$")

VisualType = Literal["TABLE", "MATRIX", "KPI", "BAR", "LINE"]
WellRole = Literal["X", "Y", "ROWS", "COLUMNS", "VALUES", "VALUE", "SERIES"]
Aggregation = Literal["NONE", "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"]
DatePart = Literal["DAY", "MONTH", "QUARTER", "YEAR"]


class StudioVisualFieldDTO(BaseModel):
    """Một mục trong Data Well của visual: đúng một field hoặc một measure."""

    well_role: WellRole
    field_id: int | None = Field(default=None, gt=0)
    measure_id: int | None = Field(default=None, gt=0)
    aggregation: Aggregation = "NONE"
    date_part: DatePart | None = None
    alias: str | None = Field(default=None, max_length=128)
    label_override: str | None = Field(default=None, max_length=200)
    format_mask: str | None = Field(default=None, max_length=64)
    sort_direction: Literal["ASC", "DESC"] | None = None
    display_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "StudioVisualFieldDTO":
        if (self.field_id is None) == (self.measure_id is None):
            raise ValueError("Mỗi trường visual phải gắn đúng một field hoặc một measure.")
        return self


class StudioVisualDTO(BaseModel):
    """Một visual trong bản nháp báo cáo Studio."""

    code: str = Field(pattern=_CODE_RE)
    title: str = Field(min_length=1, max_length=200)
    visual_type: VisualType
    display_order: int = Field(default=0, ge=0)
    grid_span: Literal[3, 4, 6, 8, 12] = 12
    height_size: Literal["S", "M", "L"] = "M"
    config: dict[str, Any] = Field(default_factory=dict)
    fields: list[StudioVisualFieldDTO] = Field(min_length=1)


class StudioReportCreateDTO(BaseModel):
    """Payload tạo báo cáo Studio mới (report + template MAIN + version 1 DRAFT)."""

    code: str = Field(pattern=_CODE_RE)
    name: str = Field(min_length=1, max_length=200)
    model_version_id: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=500)
    category_code: str | None = Field(default=None, max_length=60)
    visuals: list[StudioVisualDTO] = Field(default_factory=list)


class StudioDraftSaveDTO(BaseModel):
    """Payload lưu nháp: thay toàn bộ visuals (và params khi có)."""

    row_version: int = Field(ge=1)
    visuals: list[StudioVisualDTO] = Field(default_factory=list)
    params: list[dict[str, Any]] | None = None


class StudioPublishDTO(BaseModel):
    """Payload phát hành: change note bắt buộc (không được rỗng)."""

    change_note: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _note_not_blank(self) -> "StudioPublishDTO":
        if not self.change_note.strip():
            raise ValueError("Change note không được để trống.")
        return self


class StudioCloneDTO(BaseModel):
    """Payload nhân bản báo cáo Studio sang mã mới."""

    code: str = Field(pattern=_CODE_RE)
    name: str = Field(min_length=1, max_length=200)
