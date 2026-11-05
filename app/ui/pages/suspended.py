"""Trang thông báo chức năng tạm ngưng (task 19, spec 11 mục 4).

Khi Admin tạm ẩn một menu, vai trò thường vào đúng menu đó sẽ bị
chuyển tới đây thay vì /forbidden. ADMIN vẫn vào được menu đang ẩn.
Page này không có MENU_CODE (miễn trừ như /forbidden).
"""

from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import dcc, html

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
    return html.Div(
        [
            dmc.Container(
                dmc.Stack(
                    [
                        dmc.Title("Chức năng tạm ngưng", order=1),
                        dmc.Text(reason, size="md"),
                        dmc.Text(
                            "Quản trị viên đã tạm ẩn chức năng này. Nếu cần dùng gấp, hãy liên hệ quản trị viên.",
                            c="dimmed",
                            size="sm",
                        ),
                        dmc.Group(
                            [
                                dcc.Link("Về Dashboard", href="/"),
                                dmc.Text(f"Người dùng: {user_name}", c="dimmed", size="sm"),
                            ],
                            gap="md",
                        ),
                    ],
                    gap="md",
                ),
                size="md",
                py="xl",
            )
        ]
    )
