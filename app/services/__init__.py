from __future__ import annotations

import functools
import uuid
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from pydantic import ValidationError

from app.core.logging import get_logger
from app.schemas.errors import ErrorCode, ServiceError, ServiceResult

P = ParamSpec("P")
R = TypeVar("R")
logger = get_logger("service")


def service(func: Callable[P, R]) -> Callable[P, ServiceResult[Any]]:
    """Decorator bọc các hàm service nghiệp vụ.

    Tự động chuẩn hóa kết quả thành ServiceResult, chuyển đổi ValidationError
    và ServiceError thành kết quả lỗi chuẩn, và ẩn stack trace của lỗi nội bộ.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> ServiceResult[Any]:
        try:
            res = func(*args, **kwargs)
            if isinstance(res, ServiceResult):
                return res
            return ServiceResult.success(data=res)

        except ServiceError as exc:
            return ServiceResult.fail(code=exc.code, message=exc.message, details=exc.details)

        except ValidationError as exc:
            err_details = []
            for err in exc.errors():
                loc = ".".join(str(part) for part in err.get("loc", []))
                err_details.append(
                    {
                        "field": loc,
                        "message": err.get("msg", ""),
                        "type": err.get("type", ""),
                    }
                )
            return ServiceResult.fail(
                code=ErrorCode.VALIDATION_ERROR,
                message="Dữ liệu không hợp lệ",
                details={"errors": err_details},
            )

        except Exception as exc:
            req_id = uuid.uuid4().hex[:12]
            logger.error(
                "service_internal_error",
                request_id=req_id,
                function=func.__qualname__,
                error=str(exc),
                exc_info=True,
            )
            return ServiceResult.fail(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Lỗi hệ thống nội bộ (mã tham chiếu: {req_id})",
                details={"request_id": req_id},
            )

    return wrapper


__all__ = ["service"]
