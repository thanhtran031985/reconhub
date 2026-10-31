from __future__ import annotations

from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorCode(StrEnum):
    # Xác thực & Phân quyền & Chung
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    STALE_DATA = "STALE_DATA"

    # Người dùng & Đăng nhập
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    PASSWORD_CHANGE_REQUIRED = "PASSWORD_CHANGE_REQUIRED"
    PASSWORD_EMPTY = "PASSWORD_EMPTY"
    USERNAME_EXISTS = "USERNAME_EXISTS"
    LAST_ADMIN = "LAST_ADMIN"

    # Nguồn dữ liệu (Data Source)
    DS_CONNECT_FAILED = "DS_CONNECT_FAILED"
    DS_NOT_READ_ONLY = "DS_NOT_READ_ONLY"
    DS_IN_USE = "DS_IN_USE"
    DS_CURRENT_METADATA_LOCKED = "DS_CURRENT_METADATA_LOCKED"

    # Bảng & Cột & SQL
    TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
    COLUMN_NOT_FOUND = "COLUMN_NOT_FOUND"
    SQL_NOT_ALLOWED = "SQL_NOT_ALLOWED"
    SQL_DESCRIBE_FAILED = "SQL_DESCRIBE_FAILED"
    SQL_PARAM_MISSING = "SQL_PARAM_MISSING"

    # Template
    TEMPLATE_INVALID = "TEMPLATE_INVALID"
    TEMPLATE_CODE_EXISTS = "TEMPLATE_CODE_EXISTS"
    TEMPLATE_NOT_ACTIVE = "TEMPLATE_NOT_ACTIVE"
    TEMPLATE_VERSION_LOCKED = "TEMPLATE_VERSION_LOCKED"
    DRY_RUN_REQUIRED = "DRY_RUN_REQUIRED"

    # File Excel
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_TYPE_NOT_ALLOWED = "FILE_TYPE_NOT_ALLOWED"
    SHEET_NOT_FOUND = "SHEET_NOT_FOUND"
    EXCEL_COLUMN_MISSING = "EXCEL_COLUMN_MISSING"
    TEMPLATE_NOT_DETECTED = "TEMPLATE_NOT_DETECTED"

    # Tham số chạy (Run params)
    INVALID_RANGE = "INVALID_RANGE"
    RANGE_TOO_LARGE = "RANGE_TOO_LARGE"
    PROD_CONFIRM_REQUIRED = "PROD_CONFIRM_REQUIRED"
    DUPLICATE_RUN_WARNING = "DUPLICATE_RUN_WARNING"

    # Truy vấn nguồn & Engine
    SOURCE_TIMEOUT = "SOURCE_TIMEOUT"
    SOURCE_TOO_MANY_ROWS = "SOURCE_TOO_MANY_ROWS"
    SOURCE_QUERY_FAILED = "SOURCE_QUERY_FAILED"
    SOURCE_CONNECTION_LOST = "SOURCE_CONNECTION_LOST"
    EXCEL_TOO_MANY_ROWS = "EXCEL_TOO_MANY_ROWS"

    # Trạng thái chạy & Dữ liệu tạm
    RUN_NOT_DONE = "RUN_NOT_DONE"
    RUN_CANCELLED = "RUN_CANCELLED"
    RUN_BUSY = "RUN_BUSY"
    TEMP_DATA_PURGED = "TEMP_DATA_PURGED"
    PURGE_CONFIRM_MISMATCH = "PURGE_CONFIRM_MISMATCH"
    MAINTENANCE_MODE = "MAINTENANCE_MODE"

    # Di chuyển metadata
    MIGRATION_TARGET_NOT_EMPTY = "MIGRATION_TARGET_NOT_EMPTY"
    MIGRATION_RUNNING = "MIGRATION_RUNNING"
    MIGRATION_COUNT_MISMATCH = "MIGRATION_COUNT_MISMATCH"

    # Lỗi hệ thống
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ServiceError(Exception):
    """Exception nghiệp vụ được ném trong service, bắt bởi decorator @service."""

    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = message
        self.details = details or {}


class ServiceResult(BaseModel, Generic[T]):
    """Kết quả trả về chuẩn của mọi service ReconHub."""

    ok: bool
    data: T | None = None
    code: str | None = None  # mã lỗi cố định từ ErrorCode
    message: str | None = None  # thông báo tiếng Việt có dấu
    details: dict[str, Any] | None = None  # chi tiết bổ sung (vd lỗi validate)

    @classmethod
    def success(cls, data: T | None = None, message: str | None = None) -> ServiceResult[T]:
        return cls(ok=True, data=data, message=message)

    @classmethod
    def fail(
        cls,
        code: ErrorCode | str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> ServiceResult[T]:
        return cls(
            ok=False,
            code=str(code),
            message=message,
            details=details,
        )
