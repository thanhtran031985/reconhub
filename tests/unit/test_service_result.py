from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from app.core.context import Ctx, Role, require_role
from app.schemas.errors import ErrorCode, ServiceError, ServiceResult
from app.services import service


class SampleInput(BaseModel):
    name: str = Field(min_length=3)
    age: int = Field(ge=0)


def test_service_result_success() -> None:
    res = ServiceResult.success(data={"id": 1}, message="Thành công")
    assert res.ok is True
    assert res.data == {"id": 1}
    assert res.code is None
    assert res.message == "Thành công"


def test_service_result_fail() -> None:
    res: ServiceResult[None] = ServiceResult.fail(
        ErrorCode.NOT_FOUND,
        "Không tìm thấy bản ghi",
        details={"id": 10},
    )
    assert res.ok is False
    assert res.data is None
    assert res.code == ErrorCode.NOT_FOUND
    assert res.message == "Không tìm thấy bản ghi"
    assert res.details == {"id": 10}


def test_require_role_success() -> None:
    ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=[Role.ADMIN])
    # Không raise exception
    require_role(ctx, Role.ADMIN)
    require_role(ctx, Role.OPERATOR, Role.ADMIN)


def test_require_role_unauthenticated() -> None:
    with pytest.raises(ServiceError) as exc_info:
        require_role(None, Role.ADMIN)
    assert exc_info.value.code == ErrorCode.UNAUTHENTICATED
    assert "chưa đăng nhập" in exc_info.value.message.lower()


def test_require_role_forbidden() -> None:
    ctx = Ctx(user_id=2, username="viewer", full_name="Viewer", roles=[Role.VIEWER])
    with pytest.raises(ServiceError) as exc_info:
        require_role(ctx, Role.ADMIN, Role.OPERATOR)
    assert exc_info.value.code == ErrorCode.FORBIDDEN
    assert "không có quyền" in exc_info.value.message.lower()


def test_service_decorator_success() -> None:
    @service
    def my_service(x: int) -> dict[str, int]:
        return {"result": x * 2}

    res = my_service(5)
    assert res.ok is True
    assert res.data == {"result": 10}


def test_service_decorator_validation_error() -> None:
    @service
    def create_sample(data: dict[str, Any]) -> dict[str, Any]:
        parsed = SampleInput.model_validate(data)
        return parsed.model_dump()

    res = create_sample({"name": "a", "age": -5})
    assert res.ok is False
    assert res.code == ErrorCode.VALIDATION_ERROR
    assert res.details is not None
    assert "errors" in res.details
    # Kiểm tra details có chứa path của field lỗi
    errors = res.details["errors"]
    fields = [err["field"] for err in errors]
    assert "name" in fields
    assert "age" in fields


def test_service_decorator_service_error() -> None:
    @service
    def guarded_service(ctx: Ctx | None) -> str:
        require_role(ctx, Role.ADMIN)
        return "ok"

    ctx = Ctx(user_id=2, username="user", full_name="User", roles=[Role.VIEWER])
    res = guarded_service(ctx)
    assert res.ok is False
    assert res.code == ErrorCode.FORBIDDEN


def test_service_decorator_internal_error_hides_stack() -> None:
    @service
    def crashing_service() -> None:
        raise ZeroDivisionError("Cố ý chia cho 0 để test lỗi nội bộ")

    res = crashing_service()
    assert res.ok is False
    assert res.code == ErrorCode.INTERNAL_ERROR
    assert "mã tham chiếu" in res.message or "Lỗi hệ thống" in res.message
    # Không để lộ chi tiết ZeroDivisionError trong message trả về
    assert "ZeroDivisionError" not in (res.message or "")
    assert res.details is not None
    assert "request_id" in res.details
