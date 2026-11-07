"""Trang thông báo chức năng tạm ngưng (task 19, spec 11 mục 4).

Khi Admin tạm ẩn một menu, vai trò thường vào đúng menu đó sẽ bị
chuyển tới đây thay vì /forbidden. ADMIN vẫn vào được menu đang ẩn.
Page này không có MENU_CODE (miễn trừ như /forbidden).
"""

from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import dcc
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.perm import menu_state

try:
    dash.register_page(__name__, path="/suspended", title="Chức năng tạm ngưng – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass


def layout(menu: str | None = None, **kwargs: Any) -> Any:
    """Hiển thị lý do tạm ẩn của menu (lấy từ query ?menu=<code> nếu có)."""
    ctx = get_current_ctx()
    reason = "Chức năng này đang tạm ngưng."
    menu_code = menu or kwargs.get("menu")
    if menu_code:
        state = menu_state(str(menu_code))
        if state and state.get("HIDDEN_REASON"):
            reason = str(state["HIDDEN_REASON"])
    user_name = ctx.full_name if ctx else ""
    return dmc.Center(
        dmc.Stack(
            [
                dmc.ThemeIcon(
                    DashIconify(icon="lucide:pause-circle", width=36),
                    size=64,
                    radius="xl",
                    color="orange",
                    variant="light",
                ),
                dmc.Title("Chức năng tạm ngưng", order=3),
                dmc.Text(reason, size="sm", fw=500, ta="center"),
                dmc.Text(
                    "Quản trị viên đã tạm ẩn chức năng này. Nếu cần dùng gấp, hãy liên hệ quản trị viên.",
                    c="dimmed",
                    size="xs",
                    ta="center",
                    maw=440,
                ),
                dmc.Group(
                    [
                        dcc.Link(
                            dmc.Button(
                                "Về Dashboard",
                                leftSection=DashIconify(icon="lucide:arrow-left", width=14),
                                variant="default",
                                size="sm",
                            ),
                            href="/",
                        ),
                        dmc.Text(f"Người dùng: {user_name}", c="dimmed", size="xs") if user_name else dmc.Text(""),
                    ],
                    gap="md",
                    align="center",
                    mt="xs",
                ),
            ],
            align="center",
            gap="sm",
        ),
        style={"height": "calc(100vh - 48px)", "overflow": "hidden"},
    )
