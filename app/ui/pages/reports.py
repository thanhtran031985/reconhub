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
from app.services.report import create_report, list_reports, set_report_favorite
from app.services.report_template import list_templates
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.command_bar import command_bar
from app.ui.components.empty_state import empty_state
from app.ui.components.notification import notify_error, notify_success
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

# Task 75: options Nhóm báo cáo cho modal "Tạo mã báo cáo" (cùng nguồn
# với Select nhóm ở wizard bước 1).
NEW_REPORT_CATEGORY_OPTIONS: list[dict[str, str]] = [
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
                        "color": "var(--ink-soft, #757575)",
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
        # Task 75: tạo mã báo cáo riêng (chỉ Report Master, chưa có template).
        header_actions.append(
            dmc.Button(
                "Tạo mã báo cáo",
                variant="light",
                size="xs",
                id="reports-new-report-btn",
            )
        )

    return dmc.Box(
        [
            dcc.Store(id="reports-store", data=reports),
            # Task 75: modal tạo mã báo cáo — đặt ngoài container danh sách
            # để lần vẽ lại hub không tạo lại modal (mẫu modal task 74).
            # Chỉ ADMIN thấy (như nút mở modal).
            (
                dmc.Modal(
                    id="reports-new-report-modal",
                    title="Tạo mã báo cáo",
                    opened=False,
                    children=dmc.Stack(
                        [
                            dmc.TextInput(
                                id="reports-new-report-code",
                                label="Mã báo cáo *",
                                placeholder="VD: FIN_REVENUE",
                                style={"fontFamily": "var(--font-mono, Consolas, monospace)"},
                                **{"aria-label": "Mã báo cáo mới"},
                            ),
                            dmc.TextInput(
                                id="reports-new-report-name",
                                label="Tên báo cáo *",
                                placeholder="VD: Báo cáo doanh thu",
                                **{"aria-label": "Tên báo cáo mới"},
                            ),
                            dmc.Select(
                                id="reports-new-report-category",
                                label="Nhóm báo cáo",
                                data=NEW_REPORT_CATEGORY_OPTIONS,
                                value="FINANCE",
                                clearable=False,
                                **{"aria-label": "Nhóm báo cáo mới"},
                            ),
                            dmc.TextInput(
                                id="reports-new-report-owner",
                                label="Chủ sở hữu nghiệp vụ",
                                placeholder="VD: FIN",
                                **{"aria-label": "Chủ sở hữu mới"},
                            ),
                            dmc.Textarea(
                                id="reports-new-report-description",
                                label="Mô tả báo cáo",
                                autosize=True,
                                minRows=2,
                                placeholder="Mô tả ngắn về báo cáo.",
                                **{"aria-label": "Mô tả báo cáo mới"},
                            ),
                            html.Div(id="reports-new-report-alert"),
                            dmc.Group(
                                [
                                    button_subtle("Hủy", id="reports-new-report-cancel"),
                                    button_primary("Lưu", id="reports-new-report-save"),
                                ],
                                justify="flex-end",
                                gap="sm",
                            ),
                        ],
                        gap="sm",
                    ),
                )
                if can_admin
                else html.Div()
            ),
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


def _new_report_field_error_text(err: dict[str, Any]) -> str:
    """Text lỗi field cho modal tạo mã báo cáo (bản gọn của _field_error_text ở report_admin)."""
    field = str(err.get("field") or "")
    err_type = str(err.get("type") or "")
    if err_type in ("missing", "string_too_short"):
        return f"{field}: bắt buộc nhập."
    if err_type == "string_too_long":
        return f"{field}: quá dài."
    if err_type == "string_pattern_mismatch":
        return f"{field}: sai định dạng (viết hoa, không dấu)."
    msg = str(err.get("message", "") or "")
    return f"{field}: {msg}" if msg else f"{field}: không hợp lệ."


def _new_report_err_alert(res: Any) -> Any:
    """Alert lỗi cho modal tạo mã báo cáo (dạng toast như modal task 74)."""
    if res is None:
        return None
    details = getattr(res, "details", None)
    errors = details.get("errors") if isinstance(details, dict) else None
    msg = getattr(res, "message", None) or "Có lỗi xảy ra."
    if errors and isinstance(errors, list):
        lines = [_new_report_field_error_text(e) for e in errors if isinstance(e, dict)]
        if lines:
            return notify_error(f"{msg}\n" + "\n".join(f"• {line}" for line in lines))
    return notify_error(msg)


def handle_new_report_save(
    n_clicks: int | None,
    code: str | None,
    name: str | None,
    category_code: str | None,
    owner: str | None,
    description: str | None,
    reports: list[dict[str, Any]] | None,
    query: str | None,
    category: str | None,
    fav_only: bool | None,
) -> tuple[bool, Any, Any, Any, Any, Any]:
    """Task 75: Lưu modal 'Tạo mã báo cáo' -> (mở, alert_modal, store, sections, meta, toast).

    Chỉ gọi create_report (không tạo template): báo cáo mới hiện ở hub
    với badge 0 template. Trùng mã báo cáo -> CONFLICT, modal ở lại mở.
    """
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    try:
        rep_res = create_report(
            ctx,
            {
                "code": (code or "").strip(),
                "name": (name or "").strip(),
                "category_code": category_code or "FINANCE",
                "owner": (owner or "").strip(),
                "description": (description or "").strip() or None,
                "default_favorite": False,
                "is_visible": True,
            },
        )
    except Exception as exc:  # noqa: BLE001 - service đã bọc, phòng thủ thêm
        return (
            True,
            notify_error(f"Tạo mã báo cáo lỗi: {exc}"),
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )
    if not rep_res.ok or not isinstance(rep_res.data, dict):
        return (
            True,
            _new_report_err_alert(rep_res),
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )
    new_store = list(reports or []) + [{**rep_res.data, "template_count": 0}]
    filtered = _filter_reports(new_store, query, category, bool(fav_only))
    return (
        False,
        None,
        new_store,
        render_reports_sections(filtered),
        f"{len(filtered)} báo cáo",
        notify_success(f"Đã tạo mã báo cáo {rep_res.data.get('code')}."),
    )


@callback(
    Output("reports-new-report-modal", "opened"),
    Output("reports-new-report-code", "value"),
    Output("reports-new-report-name", "value"),
    Output("reports-new-report-category", "value"),
    Output("reports-new-report-owner", "value"),
    Output("reports-new-report-description", "value"),
    Output("reports-new-report-alert", "children"),
    Input("reports-new-report-btn", "n_clicks"),
    Input("reports-new-report-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def handle_new_report_modal_toggle(
    open_clicks: int | None,
    cancel_clicks: int | None,
) -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    """Task 75: mở modal 'Tạo mã báo cáo' (xóa trắng form) / Hủy đóng modal."""
    triggered = dash.callback_context.triggered_id
    if triggered == "reports-new-report-cancel":
        return False, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    if not open_clicks:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )
    return True, "", "", "FINANCE", "", "", None


@callback(
    Output("reports-new-report-modal", "opened", allow_duplicate=True),
    Output("reports-new-report-alert", "children", allow_duplicate=True),
    Output("reports-store", "data", allow_duplicate=True),
    Output("reports-cards-container", "children", allow_duplicate=True),
    Output("reports-catalog-meta", "children", allow_duplicate=True),
    Output("reports-error-area", "children"),
    Input("reports-new-report-save", "n_clicks"),
    State("reports-store", "data"),
    State("reports-new-report-code", "value"),
    State("reports-new-report-name", "value"),
    State("reports-new-report-category", "value"),
    State("reports-new-report-owner", "value"),
    State("reports-new-report-description", "value"),
    State("reports-search", "value"),
    State("reports-category", "value"),
    State("reports-fav-only", "checked"),
    prevent_initial_call=True,
)
def handle_new_report_save_click(
    n_clicks: int | None,
    reports: list[dict[str, Any]] | None,
    code: str | None,
    name: str | None,
    category_code: str | None,
    owner: str | None,
    description: str | None,
    query: str | None,
    category: str | None,
    fav_only: bool | None,
) -> tuple[bool, Any, Any, Any, Any, Any]:
    """Task 75: bấm Lưu trong modal -> tạo mã báo cáo, hub làm mới."""
    return handle_new_report_save(
        n_clicks, code, name, category_code, owner, description, reports, query, category, fav_only
    )
