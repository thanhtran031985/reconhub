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
