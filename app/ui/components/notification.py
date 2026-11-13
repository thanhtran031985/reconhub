"""Thành phần thông báo (toast notification) cho ReconHub dựa trên Mantine Notification."""

from __future__ import annotations

import uuid
from typing import Any

import dash_mantine_components as dmc
from dash_iconify import DashIconify


def notify_success(message: str, title: str = "Thành công", notif_id: str | None = None) -> Any:
    return dmc.Notification(
        id=notif_id or f"notif-success-{uuid.uuid4().hex[:8]}",
        title=title,
        message=message,
        color="teal",
        icon=DashIconify(icon="lucide:check", width=18),
        action="show",
        autoClose=4000,
    )


def notify_error(message: str, title: str = "Lỗi", notif_id: str | None = None) -> Any:
    return dmc.Notification(
        id=notif_id or f"notif-error-{uuid.uuid4().hex[:8]}",
        title=title,
        message=message,
        color="red",
        icon=DashIconify(icon="lucide:alert-circle", width=18),
        action="show",
        autoClose=6000,
    )


def notify_warning(message: str, title: str = "Cảnh báo", notif_id: str | None = None) -> Any:
    return dmc.Notification(
        id=notif_id or f"notif-warn-{uuid.uuid4().hex[:8]}",
        title=title,
        message=message,
        color="orange",
        icon=DashIconify(icon="lucide:alert-triangle", width=18),
        action="show",
        autoClose=5000,
    )


def notify_info(message: str, title: str = "Thông tin", notif_id: str | None = None) -> Any:
    return dmc.Notification(
        id=notif_id or f"notif-info-{uuid.uuid4().hex[:8]}",
        title=title,
        message=message,
        color="blue",
        icon=DashIconify(icon="lucide:info", width=18),
        action="show",
        autoClose=4000,
    )


def _toast_dict(message: str, title: str, color: str, icon: str, auto_close_ms: int) -> dict[str, Any]:
    """Dict cho prop `sendNotifications` của dmc.NotificationContainer
    (DMC 2.8.1) — cách duy nhất để toast hiện: `dmc.Notification` trần
    trong html.Div không render (đã chứng minh live, task 81 follow-up).
    Icon ở dạng dict component Dash (namespace/type/props)."""
    return {
        "id": f"notif-{uuid.uuid4().hex[:8]}",
        "title": title,
        "message": message,
        "color": color,
        "icon": {"namespace": "dash_iconify", "type": "DashIconify", "props": {"icon": icon, "width": 18}},
        "action": "show",
        "autoClose": auto_close_ms,
    }


def toast_success(message: str, title: str = "Thành công") -> dict[str, Any]:
    """Dict toast thành công cho sendNotifications (xem _toast_dict)."""
    return _toast_dict(message, title, "teal", "lucide:check", 4000)


def toast_error(message: str, title: str = "Lỗi") -> dict[str, Any]:
    """Dict toast lỗi cho sendNotifications (xem _toast_dict)."""
    return _toast_dict(message, title, "red", "lucide:alert-circle", 6000)
