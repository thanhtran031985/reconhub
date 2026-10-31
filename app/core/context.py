from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.errors import ErrorCode, ServiceError


class Role(StrEnum):
    ADMIN = "ADMIN"
    TEMPLATE_OWNER = "TEMPLATE_OWNER"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


# Bản đồ viết tắt vai trò sang mã chuẩn
ROLE_ALIASES: dict[str, str] = {
    "AD": Role.ADMIN,
    "ADMIN": Role.ADMIN,
    "TO": Role.TEMPLATE_OWNER,
    "TEMPLATE_OWNER": Role.TEMPLATE_OWNER,
    "OP": Role.OPERATOR,
    "OPERATOR": Role.OPERATOR,
    "VI": Role.VIEWER,
    "VIEWER": Role.VIEWER,
}


class Ctx(BaseModel):
    """Ngữ cảnh người dùng hiện tại thực hiện thao tác."""

    user_id: int
    username: str
    full_name: str
    roles: list[str] = Field(default_factory=list)

    def has_role(self, *required_roles: str) -> bool:
        """Kiểm tra xem user có ít nhất một trong các vai trò yêu cầu không."""
        user_norm_roles = {ROLE_ALIASES.get(r.upper(), r.upper()) for r in self.roles}
        required_norm_roles = {ROLE_ALIASES.get(r.upper(), r.upper()) for r in required_roles}
        return bool(user_norm_roles.intersection(required_norm_roles))


def require_role(ctx: Ctx | None, *roles: str) -> None:
    """Kiểm tra quyền truy cập của người dùng.

    Ném ServiceError UNAUTHENTICATED nếu chưa đăng nhập hoặc FORBIDDEN nếu thiếu vai trò.
    """
    if ctx is None:
        raise ServiceError(ErrorCode.UNAUTHENTICATED, "Chưa đăng nhập, vui lòng đăng nhập để tiếp tục")

    if roles and not ctx.has_role(*roles):
        raise ServiceError(ErrorCode.FORBIDDEN, "Bạn không có quyền thực hiện hành động này")
