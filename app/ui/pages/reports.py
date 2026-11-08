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
    """Một card Report Master (giữ tương thích)."""
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
    """Bảng gom nhóm theo danh mục chuẩn Screen16 preview.html (.rlist)."""
    if not reports:
        return empty_state(
            "Không có báo cáo phù hợp.",
            "Thử đổi từ khóa tìm kiếm hoặc bộ lọc nhóm.",
        )
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in reports:
        groups.setdefault(str(r.get("category_code") or ""), []).append(r)

    th_base: dict[str, Any] = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--surface-2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "11px",
        "fontWeight": 600,
        "borderBottom": "1px solid var(--line, #E0E0E0)",
        "whiteSpace": "nowrap",
    }

    tbody_children: list[Any] = []
    for code in sorted(groups):
        label = CATEGORY_LABELS.get(code, code or "Chưa phân nhóm")
        items = groups[code]
        # Group header row
        tbody_children.append(
            dmc.TableTr(
                dmc.TableTd(
                    f"{label} · {len(items)} báo cáo",
                    tableProps={"colSpan": 6},
                    style={
                        "height": "28px",
                        "backgroundColor": "var(--surface-2, #FAFAFA)",
                        "fontSize": "11px",
                        "fontWeight": 600,
                        "color": "var(--text-muted, #757575)",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.04em",
                        "padding": "0 12px",
                    },
                ),
                className="grp",
            )
        )
        for r in items:
            report_id = int(r["id"])
            is_fav = bool(r.get("is_favorite"))
            tbody_children.append(
                dmc.TableTr(
                    [
                        # Mã
                        dmc.TableTd(
                            dmc.Anchor(
                                str(r["code"]),
                                href=f"/reports/{report_id}",
                                className="rh-code",
                                fw=600,
                                size="sm",
                                style={"textDecoration": "none"},
                            ),
                            style={"padding": "0 12px", "whiteSpace": "nowrap"},
                        ),
                        # Tên báo cáo
                        dmc.TableTd(
                            dmc.Text(str(r["name"]), fw=600, size="sm"),
                            style={"padding": "0 12px", "whiteSpace": "nowrap"},
                        ),
                        # Mô tả
                        dmc.TableTd(
                            dmc.Text(
                                str(r.get("description") or "—"),
                                size="xs",
                                c="dimmed",
                                lineClamp=1,
                                style={"maxWidth": "420px"},
                            ),
                            style={"padding": "0 12px"},
                        ),
                        # Template count
                        dmc.TableTd(
                            dmc.Badge(
                                f"{int(r.get('template_count', 0))} template",
                                color="teal",
                                variant="light",
                                size="xs",
                            ),
                            style={"padding": "0 12px", "whiteSpace": "nowrap"},
                        ),
                        # Yêu thích
                        dmc.TableTd(
                            dmc.ActionIcon(
                                DashIconify(
                                    icon="lucide:star",
                                    width=16,
                                ),
                                id={"type": "reports-fav-btn", "index": report_id},
                                variant="subtle",
                                color="yellow" if is_fav else "gray",
                                size="sm",
                                **{"aria-label": f"Yêu thích {r['code']}"},
                            ),
                            style={"padding": "0 8px", "textAlign": "center", "width": "40px"},
                        ),
                        # Thao tác
                        dmc.TableTd(
                            dcc.Link(
                                dmc.Button(
                                    "Xem báo cáo",
                                    variant="light",
                                    size="xs",
                                    id=f"reports-open-{report_id}",
                                ),
                                href=f"/reports/{report_id}",
                            ),
                            style={"padding": "0 12px", "textAlign": "right", "whiteSpace": "nowrap", "width": "1%"},
                        ),
                    ],
                    className="report-row",
                    style={"height": "40px"},
                )
            )

    return dmc.Paper(
        dmc.TableScrollContainer(
            dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr(
                            [
                                dmc.TableTh("Mã", style={**th_base, "width": "140px"}),
                                dmc.TableTh("Tên báo cáo", style={**th_base, "width": "240px"}),
                                dmc.TableTh("Mô tả", style=th_base),
                                dmc.TableTh("Template", style={**th_base, "width": "120px"}),
                                dmc.TableTh("", style={**th_base, "width": "50px", "textAlign": "center"}),
                                dmc.TableTh("", style={**th_base, "width": "120px", "textAlign": "right"}),
                            ]
                        )
                    ),
                    dmc.TableTbody(tbody_children),
                ],
                striped=True,
                highlightOnHover=True,
                withTableBorder=False,
                className="rlist",
            ),
            minWidth=800,
        ),
        withBorder=True,
        radius="sm",
        style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
    )


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
                actions=[
                    dmc.Text(
                        f"{len(reports)} báo cáo",
                        id="reports-catalog-meta",
                        size="xs",
                        c="dimmed",
                        style={"whiteSpace": "nowrap"},
                        **{"aria-live": "polite"},
                    )
                ],
            ),
            html.Div(
                id="reports-error-area",
                children=alert_box(load_error, tone="crit") if load_error else html.Div(),
                **{"aria-live": "polite"},  # type: ignore[arg-type]
            ),
            html.Div(
                id="reports-cards-container",
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
                children=render_reports_sections(reports),
                **{"aria-live": "polite"},  # type: ignore[arg-type]
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
    Output("reports-catalog-meta", "children"),
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
) -> tuple[Any, str]:
    """Lọc danh sách báo cáo theo tìm kiếm/nhóm/yêu thích (T27-01)."""
    filtered = _filter_reports(reports or [], query, category, bool(fav_only))
    return render_reports_sections(filtered), f"{len(filtered)} báo cáo"


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
