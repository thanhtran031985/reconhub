from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash_iconify import DashIconify

STATUS_MAP: dict[str, tuple[str, str, str]] = {
    # 7 trạng thái kết quả đối soát
    "MATCHED": ("ok", "Khớp", "lucide:check"),
    "MISMATCH": ("crit", "Lệch giá trị", "lucide:equal-not"),
    "MISSING_IN_DB": ("warn", "Thiếu trong DB", "lucide:database"),
    "MISSING_IN_EXCEL": ("purple", "Thiếu trong Excel", "lucide:file-x"),
    "INCONSISTENT": ("off", "Không nhất quán", "lucide:shuffle"),
    "DUPLICATE": ("warn", "Trùng khóa", "lucide:copy"),
    "INVALID": ("crit", "Không hợp lệ", "lucide:alert-triangle"),
    # Trạng thái Run
    "QUEUED": ("off", "Chờ chạy", "lucide:clock"),
    "RUNNING": ("info", "Đang chạy", "lucide:loader"),
    "DONE": ("ok", "Đã xong", "lucide:check-circle"),
    "FAILED": ("crit", "Thất bại", "lucide:alert-circle"),
    "CANCELLED": ("off", "Đã hủy", "lucide:x-circle"),
    # Trạng thái Kiểm tra
    "CHECKED": ("ok", "Đã kiểm tra", "lucide:check-check"),
    "UNCHECKED": ("off", "Chưa kiểm tra", "lucide:circle"),
    # Trạng thái người dùng
    "ACTIVE": ("ok", "Hoạt động", "lucide:check"),
    "LOCKED": ("warn", "Tạm khóa", "lucide:clock"),
    "DISABLED": ("off", "Đã tắt", "lucide:slash"),
    "MUST_CHANGE_PW": ("info", "Chờ đổi mật khẩu", "lucide:key"),
    # Trạng thái template
    "DRAFT": ("off", "Bản nháp", "lucide:file-edit"),
    "ARCHIVED": ("off", "Đã lưu trữ", "lucide:archive"),
    # Dữ liệu tạm
    "PURGED": ("off", "Đã xóa", "lucide:trash-2"),
    "RETAINED": ("warn", "Còn lưu", "lucide:database"),
    # Môi trường
    "DEV": ("info", "DEV", "lucide:laptop"),
    "TEST": ("off", "TEST", "lucide:flask-conical"),
    "UAT": ("warn", "UAT", "lucide:test-tube-2"),
    "PROD": ("crit", "PROD", "lucide:shield-alert"),
    # Vai trò
    "ADMIN": ("primary", "Admin", "lucide:shield"),
    "TEMPLATE_OWNER": ("purple", "Template Owner", "lucide:file-cog"),
    "OPERATOR": ("info", "Operator", "lucide:play"),
    "VIEWER": ("off", "Viewer", "lucide:eye"),
}


def status_chip(
    status: str,
    label: str | None = None,
    icon: str | None = None,
    size: str = "sm",
    **kwargs: Any,
) -> dmc.Badge:
    """Chip trạng thái luôn có icon + chữ theo chuẩn design system."""
    key = status.upper() if isinstance(status, str) else str(status)
    tone, default_label, default_icon = STATUS_MAP.get(
        key, ("off", label or str(status), icon or "lucide:info")
    )

    display_label = label if label is not None else default_label
    display_icon = icon if icon is not None else default_icon

    icon_size = 14 if size == "sm" else (12 if size == "xs" else 16)
    left_sec = DashIconify(icon=display_icon, width=icon_size)

    return dmc.Badge(
        display_label,
        color=tone,
        variant="light",
        size=size,
        leftSection=left_sec,
        radius="xl",
        **kwargs,
    )

