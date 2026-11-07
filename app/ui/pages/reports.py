"""Trang Trung tâm báo cáo — task 27 bước 1, prototype Screen16 v-center."""

from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.perm import effective_menus, page_gate
from app.services.report import list_reports, set_report_favorite
from app.services.report_template import list_templates
from app.ui.components.alert_box import alert_box
from app.ui.components.command_bar import command_bar
from app.ui.components.empty_state import empty_state
from app.ui.components.page_header import page_header

try:
    dash.register_page(__name__, path="/reports", title="Trung tâm báo cáo – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "report_center"

CATEGORY_LABELS: dict[str, str] = {
    "FINANCE": "Tài chính",
    "ACCOUNTING": "Kế toán",
    "OPERATIONS": "Vận hành",
}
CATEGORY_OPTIONS: list[dict[str, str]] = [{"label": "Tất cả", "value": "all"}] + [
    {"label": label, "value": code} for code, label in CATEGORY_LABELS.items()
]


def _filter_reports(
    reports: list[dict[str, Any]],
    query: str | None,
    category: str | None,
    fav_only: bool,
) -> list[dict[str, Any]]:
    """Lọc theo tên/mã/mô tả + nhóm + chỉ yêu thích (thuần, test được)."""
    q = (query or "").strip().lower()
    out = []
    for r in reports:
        if category and category != "all" and r.get("category_code") != category:
            continue
        if fav_only and not r.get("is_favorite"):
            continue
        if q:
            hay = " ".join(str(r.get(k) or "") for k in ("name", "code", "description")).lower()
            if q not in hay:
                continue
        out.append(r)
    return out


def render_report_card(report: dict[str, Any]) -> dmc.Card:
    """Một card Report Master theo prototype (tag mã, tên, mô tả, số
    template, sao yêu thích, nút Xem báo cáo)."""
    report_id = int(report["id"])
    is_fav = bool(report.get("is_favorite"))
    return dmc.Card(
        [
            dmc.Group(
                [
                    dmc.Badge(str(report["code"]), variant="light", size="sm"),
                    dmc.ActionIcon(
                        DashIconify(
                            icon="lucide:star",
                            width=16,
                        ),
                        id={"type": "reports-fav-btn", "index": report_id},
                        variant="subtle",
                        color="yellow" if is_fav else "gray",
                        size="sm",
                        **{"aria-label": f"Yêu thích {report['code']}"},
                    ),
                ],
                justify="space-between",
            ),
            dmc.Text(str(report["name"]), fw=600, size="sm", mt="xs"),
            dmc.Text(
                str(report.get("description") or ""),
                size="xs",
                c="dimmed",
                lineClamp=2,
                style={"flex": 1, "minHeight": "32px"},
            ),
            dmc.Group(
                [
                    dmc.Badge(
                        f"{int(report.get('template_count', 0))} template",
                        color="green",
                        variant="light",
                        size="xs",
                    ),
                    dcc.Link(
                        dmc.Button(
                            "Xem báo cáo",
                            variant="filled",
                            size="xs",
                            id=f"reports-open-{report_id}",
                        ),
                        href=f"/reports/{report_id}",
                    ),
                ],
                justify="space-between",
                mt="xs",
            ),
        ],
        withBorder=True,
        radius="sm",
        p="sm",
        style={"display": "flex", "flexDirection": "column"},
    )


def render_reports_sections(reports: list[dict[str, Any]]) -> Any:
    """Cards nhóm theo category (prototype); trống → empty_state."""
    if not reports:
        return empty_state(
            "Không có báo cáo phù hợp.",
            "Thử đổi từ khóa tìm kiếm hoặc bộ lọc nhóm.",
        )
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in reports:
        groups.setdefault(str(r.get("category_code") or ""), []).append(r)
    sections = []
    for code in sorted(groups):
        label = CATEGORY_LABELS.get(code, code or "Chưa phân nhóm")
        sections.append(
            html.Div(
                [
                    dmc.Title(label, order=3, size="sm", mt="sm", mb="xs", c="dimmed"),
                    dmc.SimpleGrid(
                        [render_report_card(r) for r in groups[code]],
                        cols={"base": 1, "sm": 2, "lg": 3},
                        spacing="sm",
                    ),
                ]
            )
        )
    return html.Div(sections, style={"paddingBottom": "16px"})


def layout() -> Any:
    """Giao diện chính màn hình Trung tâm báo cáo."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="reports-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập Trung tâm báo cáo.", tone="crit"),
            ]
        )
    reports: list[dict[str, Any]] = []
    load_error: str | None = None
    if ctx:
        try:
            res = list_reports(ctx)
            if res.ok and isinstance(res.data, list):
                for r in res.data:
                    count = 0
                    try:
                        t_res = list_templates(ctx, int(r["id"]))
                        if t_res.ok and isinstance(t_res.data, list):
                            count = len(t_res.data)
                    except Exception:
                        count = 0
                    reports.append({**r, "template_count": count})
            else:
                load_error = res.message if res else "Không tải được danh sách báo cáo."
        except Exception as exc:
            load_error = str(exc)
    can_admin = bool(ctx) and "report_admin" in effective_menus(ctx)
    header_actions = []
    if can_admin:
        header_actions.append(
            dmc.Anchor(
                dmc.Button(
                    "+ Đăng ký báo cáo",
                    variant="filled",
                    size="xs",
                    id="reports-create-btn",
                ),
                href="/report-admin",
            )
        )

    return dmc.Box(
        [
            dcc.Store(id="reports-store", data=reports),
            page_header(
                title="Trung tâm báo cáo",
                subtitle="Báo cáo động cho FIN, kế toán và vận hành.",
                actions=header_actions,
            ),
            command_bar(
                search_id="reports-search",
                search_placeholder="Tên, mã, mô tả…",
                filters=[
                    dmc.Select(
                        id="reports-category",
                        data=CATEGORY_OPTIONS,
                        value="all",
                        w=160,
                        size="xs",
                        **{"aria-label": "Nhóm báo cáo"},
                    ),
                    dmc.Checkbox(
                        id="reports-fav-only",
                        label="Chỉ yêu thích",
                        size="xs",
                    ),
                ],
            ),
            html.Div(
                id="reports-error-area",
                children=alert_box(load_error, tone="crit") if load_error else html.Div(),
                **{"aria-live": "polite"},  # type: ignore[arg-type]
            ),
            dcc.Loading(
                id="reports-loading",
                type="circle",
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column"},
                children=html.Div(
                    id="reports-cards-container",
                    style={"flex": 1, "minHeight": 0, "overflow": "auto", "padding": "4px 2px"},
                    children=render_reports_sections(reports),
                    **{"aria-live": "polite"},  # type: ignore[arg-type]
                ),
            ),
        ],
        style={
            "height": "100%",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "12px 16px",
            "gap": "10px",
        },
    )


@callback(
    Output("reports-cards-container", "children"),
    Input("reports-search", "value"),
    Input("reports-category", "value"),
    Input("reports-fav-only", "checked"),
    State("reports-store", "data"),
)
def handle_reports_filter(
    query: str | None,
    category: str | None,
    fav_only: bool | None,
    reports: list[dict[str, Any]] | None,
) -> Any:
    """Lọc cards theo tìm kiếm/nhóm/yêu thích (T27-01)."""
    return render_reports_sections(_filter_reports(reports or [], query, category, bool(fav_only)))


@callback(
    Output("reports-store", "data"),
    Input({"type": "reports-fav-btn", "index": dash.ALL}, "n_clicks"),
    State("reports-store", "data"),
    prevent_initial_call=True,
)
def handle_favorite_toggle(
    n_clicks: list[int | None] | None,
    reports: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Bật/tắt yêu thích (guard n_clicks — dash_callback_safety)."""
    if not n_clicks or not any(n_clicks):
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not reports:
        raise PreventUpdate
    triggered = dash.callback_context.triggered
    if not triggered:
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    try:
        report_id = int(triggered_id["index"])
    except (TypeError, ValueError):
        raise PreventUpdate from None
    current = next((r for r in reports if int(r["id"]) == report_id), None)
    if current is None:
        raise PreventUpdate
    new_value = not bool(current.get("is_favorite"))
    res = set_report_favorite(ctx, report_id, new_value)
    if not res.ok:
        raise PreventUpdate
    return [{**r, "is_favorite": new_value} if int(r["id"]) == report_id else r for r in reports]
