from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PrecheckParams(BaseModel):
    """Tham số kiểm tra sơ bộ trước khi tạo run."""

    template_id: int
    template_version: int | None = None
    data_source_id: int | None = None
    p_from: datetime
    p_to: datetime
    confirm_prod: bool = False
    file_id: int | None = None


class PrecheckResult(BaseModel):
    """Kết quả kiểm tra sơ bộ."""

    valid: bool = True
    warnings: list[str] = Field(default_factory=list)
    data_source_env: str = ""
    est_excel_rows: int | None = None


class CreateRunParams(BaseModel):
    """Tham số tạo run đối soát mới."""

    template_id: int
    template_version: int | None = None
    profile_code: str | None = None
    profile_override: dict[str, Any] | None = None
    file_id: int
    sheet_name: str | None = None
    data_source_id: int | None = None
    p_from: datetime
    p_to: datetime
    params: dict[str, Any] | None = None
    apply_range_excel: bool = False
    confirm_prod: bool = False


class RunResponse(BaseModel):
    """Thông tin cơ bản về run đã tạo."""

    run_id: int
    status: str
    created_at: datetime


class RunListFilter(BaseModel):
    """Bộ lọc danh sách run."""

    template_id: int | None = None
    status: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    created_by: str | None = None
    is_checked: bool | None = None
    is_temp_purged: bool | None = None
    filename: str | None = None
    page: int = 1
    page_size: int = 20


class RunRowsFilter(BaseModel):
    """Bộ lọc phân trang danh sách dòng kết quả."""

    status: str | None = None
    issue_status: str | None = None
    search: str | None = None
    sort_by: str = "row_no"
    sort_dir: str = "asc"
    page: int = 1
    page_size: int = 50


class PurgeFilter(BaseModel):
    """Bộ lọc xóa dữ liệu tạm theo điều kiện."""

    template_id: int | None = None
    before_date: datetime | None = None
    only_checked: bool = True
    created_by: str | None = None
