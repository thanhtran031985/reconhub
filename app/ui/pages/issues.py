from __future__ import annotations

from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.context import Role
from app.core.session import get_current_ctx
from app.services.issue import (
    bulk_update_issues_by_ids,
    get_issue,
    list_assignees,
    list_issues,
    list_reasons,
    update_issue_by_id,
)
from app.services.template import list_templates
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.kpi_card import kpi_card
from app.ui.components.status_chip import status_chip

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/issues",
        title="Xử lý chênh lệch — ReconHub",
    )
except Exception:
    pass

MUTATION_ROLES = {Role.ADMIN, Role.OPERATOR, Role.TEMPLATE_OWNER}


def render_header(kpis: dict[str, int]) -> dmc.Stack:
    """Tiêu đề H1 và phụ đề màn hình Xử lý chênh lệch."""
    open_cnt = kpis.get("open", 0)
    title_text = f"Xử lý chênh lệch: {open_cnt} đang mở"
    return dmc.Stack(
        [
            dmc.Title(title_text, order=1, id="issues-page-title"),
            dmc.Text(
                "Chênh lệch theo template và khóa logic, được theo dõi và giữ qua các lần chạy đối soát.",
                c="dimmed",
                size="sm",
            ),
        ],
        gap=4,
    )


def render_kpi_cards(kpis: dict[str, int]) -> dmc.SimpleGrid:
    """Các thẻ KPI tổng quan trạng thái chênh lệch."""
    return dmc.SimpleGrid(
        cols={"base": 1, "xs": 2, "md": 5},
        spacing="md",
        children=[
            kpi_card(
                label="Tổng chênh lệch",
                value=kpis.get("total", 0),
                tone="primary",
                icon="lucide:alert-circle",
            ),
            kpi_card(
                label="Chờ xử lý (Mở)",
                value=kpis.get("open", 0),
                tone="warn",
                icon="lucide:flag",
            ),
            kpi_card(
                label="Đang xử lý",
                value=kpis.get("in_progress", 0),
                tone="info",
                icon="lucide:clock",
            ),
            kpi_card(
                label="Đã xử lý",
                value=kpis.get("resolved", 0),
                tone="ok",
                icon="lucide:check-circle",
            ),
            kpi_card(
                label="Đã chấp nhận lệch",
                value=kpis.get("accepted", 0),
                tone="purple",
                icon="lucide:shield-check",
            ),
        ],
    )


def render_filter_bar(
    templates: list[dict[str, Any]],
    assignees: list[dict[str, Any]],
) -> dmc.Paper:
    """Thanh lọc theo template, trạng thái, người xử lý và tìm kiếm theo khóa."""
    tmpl_options = [{"value": "ALL", "label": "Tất cả Template"}] + [
        {"value": str(t["id"]), "label": f"{t['code']} – {t['name']}"} for t in templates
    ]

    status_options = [
        {"value": "ALL", "label": "Tất cả trạng thái"},
        {"value": "OPEN", "label": "Chờ xử lý (Mở)"},
        {"value": "IN_PROGRESS", "label": "Đang xử lý"},
        {"value": "RESOLVED", "label": "Đã xử lý"},
        {"value": "ACCEPTED", "label": "Đã chấp nhận lệch"},
    ]

    assignee_options = [
        {"value": "ALL", "label": "Tất cả người xử lý"},
        {"value": "UNASSIGNED", "label": "Chưa giao"},
    ] + [{"value": str(u["ID"]), "label": f"{u['FULL_NAME'] or u['USERNAME']} (@{u['USERNAME']})"} for u in assignees]

    return dmc.Paper(
        withBorder=True,
        p="sm",
        radius="sm",
        children=dmc.Group(
            [
                dmc.Select(
                    id="issues-filter-template",
                    data=tmpl_options,
                    value="ALL",
                    searchable=True,
                    style={"width": 260},
                    placeholder="Lọc theo template",
                ),
                dmc.Select(
                    id="issues-filter-status",
                    data=status_options,
                    value="ALL",
                    style={"width": 180},
                    placeholder="Trạng thái",
                ),
                dmc.Select(
                    id="issues-filter-assignee",
                    data=assignee_options,
                    value="ALL",
                    searchable=True,
                    style={"width": 220},
                    placeholder="Người xử lý",
                ),
                dmc.TextInput(
                    id="issues-filter-search",
                    placeholder="Tìm theo khóa...",
                    leftSection=DashIconify(icon="lucide:search", width=16),
                    style={"flex": 1, "minWidth": 180},
                ),
                button_subtle("Làm mới", id="issues-refresh-btn", icon="lucide:refresh-cw"),
            ],
            gap="sm",
            align="center",
        ),
    )


def render_issues_table(
    issues: list[dict[str, Any]],
    selected_ids: list[int],
    can_edit: bool,
) -> Any:
    """Dựng bảng dữ liệu chênh lệch với checkbox chọn và nút hành động theo chuẩn Screen09."""
    if not issues:
        return empty_state(
            title="Không tìm thấy chênh lệch nào",
            description="Không có bản ghi chênh lệch nào phù hợp với bộ lọc hiện tại.",
            icon="lucide:check-circle-2",
        )

    headers = []
    if can_edit:
        all_selected = len(issues) > 0 and all(it["ID"] in selected_ids for it in issues)
        headers.append(
            dmc.TableTh(
                dmc.Center(
                    dmc.Checkbox(
                        id="issues-select-all",
                        checked=all_selected,
                        disabled=len(issues) == 0,
                        size="sm",
                        style={"cursor": "pointer" if issues else "default"},
                        **{"aria-label": "Chọn tất cả chênh lệch"},
                    )
                ),
                w=44,
                style={
                    "width": "44px",
                    "minWidth": "44px",
                    "maxWidth": "44px",
                    "textAlign": "center",
                    "verticalAlign": "middle",
                    "padding": "0 8px",
                },
            )
        )

    headers.extend(
        [
            dmc.TableTh("Khóa đối soát", style={"minWidth": "160px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Template & Profile", style={"minWidth": "180px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Trạng thái xử lý", style={"minWidth": "140px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Nguyên nhân", style={"minWidth": "150px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Người xử lý", style={"minWidth": "140px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Lần đầu / Gần nhất", style={"minWidth": "130px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Thao tác", style={"minWidth": "90px", "textAlign": "right", "whiteSpace": "nowrap"}),
        ]
    )

    tbody_rows = []
    for it in issues:
        i_id = int(it["ID"])
        is_checked = i_id in selected_ids

        tds = []
        if can_edit:
            tds.append(
                dmc.TableTd(
                    dmc.Center(
                        dmc.Checkbox(
                            id={"type": "issues-row-select", "index": i_id},
                            checked=is_checked,
                            size="sm",
                            style={"cursor": "pointer"},
                            **{"aria-label": f"Chọn chênh lệch #{i_id}"},
                        )
                    ),
                    w=44,
                    style={
                        "width": "44px",
                        "minWidth": "44px",
                        "maxWidth": "44px",
                        "textAlign": "center",
                        "verticalAlign": "middle",
                        "padding": "0 8px",
                    },
                )
            )

        # Khóa đối soát
        tds.append(
            dmc.TableTd(
                dmc.Text(it.get("KEY_TEXT", "—"), fw=600, className="rh-code", size="sm"),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Template & Profile
        tmpl_label = (
            f"{it.get('TEMPLATE_CODE') or it.get('TEMPLATE_NAME') or '—'} · {it.get('PROFILE_CODE') or 'DEFAULT'}"
        )
        tds.append(
            dmc.TableTd(
                dmc.Text(tmpl_label, size="sm"),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Trạng thái xử lý
        st = str(it.get("STATUS", "OPEN"))
        tds.append(
            dmc.TableTd(
                status_chip(st),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Nguyên nhân
        reason_label = it.get("REASON_LABEL") or it.get("REASON_CODE") or "—"
        tds.append(
            dmc.TableTd(
                dmc.Text(reason_label, size="sm"),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Người xử lý
        assignee_label = it.get("ASSIGNEE_NAME") or (
            f"@{it.get('ASSIGNEE_USERNAME')}" if it.get("ASSIGNEE_USERNAME") else "—"
        )
        tds.append(
            dmc.TableTd(
                dmc.Text(assignee_label, size="sm", className="rh-code" if it.get("ASSIGNEE_USERNAME") else None),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Lần đầu / Gần nhất
        runs_label = f"#{it.get('FIRST_RUN_ID', '—')} / #{it.get('LAST_RUN_ID', '—')}"
        tds.append(
            dmc.TableTd(
                dmc.Text(runs_label, size="sm", className="rh-code", c="dimmed"),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Thao tác
        action_btn = button_subtle(
            "Xử lý",
            id={"type": "issues-row-action", "index": i_id},
            size="xs",
            icon="lucide:pencil",
        )
        tds.append(
            dmc.TableTd(
                dmc.Group([action_btn], justify="flex-end"),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        tbody_rows.append(
            dmc.TableTr(
                tds,
                style={
                    "backgroundColor": "var(--mantine-color-blue-light)" if is_checked else "transparent",
                },
            )
        )

    # Thanh thống kê ở chân bảng
    pagination_bar = dmc.Group(
        justify="space-between",
        align="center",
        p="md",
        style={"borderTop": "1px solid var(--border-subtle, #e2e8f0)"},
        children=[
            dmc.Text(
                f"Hiển thị {len(issues)} chênh lệch",
                size="sm",
                c="dimmed",
                fw=500,
            ),
        ],
    )

    return dmc.Card(
        [
            dmc.TableScrollContainer(
                minWidth=1100,
                children=dmc.Table(
                    [
                        dmc.TableThead(dmc.TableTr(headers)),
                        dmc.TableTbody(tbody_rows),
                    ],
                    striped=False,
                    highlightOnHover=True,
                    withTableBorder=False,
                    withColumnBorders=False,
                    verticalSpacing="sm",
                ),
            ),
            pagination_bar,
        ],
        withBorder=True,
        padding=0,
        radius="sm",
    )


def layout(**kwargs: Any) -> Any:
    """Layout chính màn hình Xử lý chênh lệch (Screen09)."""
    ctx = get_current_ctx()
    if ctx is None:
        return html.Div(
            [
                dcc.Location(id="issues-forbidden-redirect", href="/forbidden"),
                alert_box("Bạn cần đăng nhập để truy cập màn hình này.", tone="crit"),
            ]
        )

    can_edit = bool(set(ctx.roles) & MUTATION_ROLES)

    # Nạp danh sách Template và Assignees
    tmpl_res = list_templates(ctx)
    templates = tmpl_res.data if tmpl_res.ok and tmpl_res.data else []

    assignees_res = list_assignees(ctx)
    assignees = assignees_res.data if assignees_res.ok and assignees_res.data else []

    reasons_res = list_reasons(ctx)
    reasons = reasons_res.data if reasons_res.ok and reasons_res.data else []

    # Danh mục cho modal/drawer
    status_options = [
        {"value": "OPEN", "label": "Chờ xử lý (Mở)"},
        {"value": "IN_PROGRESS", "label": "Đang xử lý"},
        {"value": "RESOLVED", "label": "Đã xử lý"},
        {"value": "ACCEPTED", "label": "Đã chấp nhận lệch"},
    ]
    reason_options = [{"value": r["CODE"], "label": r["LABEL"]} for r in reasons]
    assignee_options = [
        {"value": str(u["ID"]), "label": f"{u['FULL_NAME'] or u['USERNAME']} (@{u['USERNAME']})"} for u in assignees
    ]

    return dmc.Stack(
        [
            # Stores lưu trạng thái UI
            dcc.Store(id="issues-selected-store", data=[]),
            dcc.Store(id="issues-reload-trigger", data=0),
            # Header
            html.Div(id="issues-header-container", children=render_header({})),
            # KPI Cards
            html.Div(id="issues-kpi-container", children=render_kpi_cards({})),
            # Filter bar
            render_filter_bar(templates, assignees),
            # Thanh hành động hàng loạt (khi có chọn dòng)
            html.Div(id="issues-bulk-bar-container"),
            # Bảng dữ liệu chênh lệch
            html.Div(
                id="issues-table-container",
                children=dmc.Center(dmc.Loader(size="md", my="xl")),
            ),
            # Drawer cập nhật issue đơn lẻ
            drawer_right(
                id="issues-edit-drawer",
                title="Cập nhật xử lý chênh lệch",
                opened=False,
                size=500,
                children=dmc.Stack(
                    [
                        html.Div(id="issues-drawer-header-info"),
                        dmc.Select(
                            id="issues-drawer-status",
                            label="Trạng thái",
                            data=status_options,
                            value="OPEN",
                            disabled=not can_edit,
                        ),
                        dmc.Select(
                            id="issues-drawer-reason",
                            label="Nguyên nhân chênh lệch",
                            placeholder="Chọn nguyên nhân",
                            data=reason_options,
                            value=None,
                            clearable=True,
                            disabled=not can_edit,
                        ),
                        dmc.Select(
                            id="issues-drawer-assignee",
                            label="Người xử lý",
                            placeholder="Chọn người được giao",
                            data=assignee_options,
                            value=None,
                            clearable=True,
                            disabled=not can_edit,
                        ),
                        dmc.Textarea(
                            id="issues-drawer-note",
                            label="Ghi chú giải trình",
                            placeholder="Nhập ghi chú chi tiết...",
                            minRows=3,
                            disabled=not can_edit,
                        ),
                        dcc.Store(id="issues-drawer-issue-id", data=None),
                        html.Div(id="issues-drawer-feedback"),
                        dmc.Group(
                            [
                                button_primary(
                                    "Lưu xử lý",
                                    id="issues-drawer-save-btn",
                                    icon="lucide:save",
                                    disabled=not can_edit,
                                ),
                            ],
                            justify="flex-end",
                            mt="sm",
                        )
                        if can_edit
                        else None,
                    ],
                    gap="sm",
                ),
            ),
        ],
        gap="md",
        p="md",
    )


@callback(
    Output("issues-header-container", "children"),
    Output("issues-kpi-container", "children"),
    Output("issues-table-container", "children"),
    Input("issues-filter-template", "value"),
    Input("issues-filter-status", "value"),
    Input("issues-filter-assignee", "value"),
    Input("issues-filter-search", "value"),
    Input("issues-refresh-btn", "n_clicks"),
    Input("issues-reload-trigger", "data"),
    State("issues-selected-store", "data"),
)
def update_issues_view(
    tmpl_val: str | None,
    st_val: str | None,
    assignee_val: str | None,
    search_val: str | None,
    _refresh: int | None,
    _trigger: int | None,
    selected_ids: list[int] | None,
) -> tuple[Any, Any, Any]:
    """Cập nhật dữ liệu bảng và thẻ KPI khi người dùng thay đổi bộ lọc hoặc bấm Làm mới."""
    ctx = get_current_ctx()
    if ctx is None:
        return dash.no_update, dash.no_update, dash.no_update

    t_id = int(tmpl_val) if tmpl_val and tmpl_val != "ALL" and tmpl_val.isdigit() else None
    st = st_val if st_val and st_val != "ALL" else None

    ass_id = None
    if assignee_val and assignee_val != "ALL":
        if assignee_val.isdigit():
            ass_id = int(assignee_val)

    res = list_issues(
        ctx,
        template_id=t_id,
        status=st,
        assignee_id=ass_id,
        search=search_val.strip() if search_val else None,
        page=1,
        page_size=100,
    )

    if not res.ok:
        err_ui = alert_box(f"Không tải được danh sách chênh lệch: {res.message}", tone="crit")
        return dash.no_update, dash.no_update, err_ui

    data = res.data or {}
    kpis = data.get("kpis", {})
    items = data.get("items", [])

    header_ui = render_header(kpis)
    kpi_ui = render_kpi_cards(kpis)

    can_edit = bool(set(ctx.roles) & MUTATION_ROLES)
    table_ui = render_issues_table(items, selected_ids or [], can_edit=can_edit)

    return header_ui, kpi_ui, table_ui


@callback(
    Output("issues-selected-store", "data"),
    Input("issues-select-all", "checked"),
    Input({"type": "issues-row-select", "index": ALL}, "checked"),
    State({"type": "issues-row-select", "index": ALL}, "id"),
    State("issues-selected-store", "data"),
    prevent_initial_call=True,
)
def handle_selection(
    select_all_checked: bool | None,
    row_checked_list: list[bool | None],
    row_ids: list[dict[str, Any]],
    current_selected: list[int] | None,
) -> list[int]:
    """Cập nhật danh sách ID các dòng được chọn (chọn tất cả hoặc chọn lẻ)."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return current_selected or []

    trigger_prop = ctx_dash.triggered[0]["prop_id"]

    if trigger_prop.startswith("issues-select-all"):
        if select_all_checked:
            return [int(item["index"]) for item in row_ids]
        return []

    # Chọn đơn lẻ
    selected: list[int] = []
    for checked, r_id in zip(row_checked_list, row_ids, strict=False):
        if checked:
            selected.append(int(r_id["index"]))
    return selected


@callback(
    Output("issues-bulk-bar-container", "children"),
    Input("issues-selected-store", "data"),
)
def render_bulk_action_bar(selected_ids: list[int] | None) -> Any:
    """Hiển thị thanh công cụ hàng loạt khi có dòng được chọn."""
    if not selected_ids:
        return html.Div()

    ctx = get_current_ctx()
    if ctx is None:
        return html.Div()

    reasons_res = list_reasons(ctx)
    reasons = reasons_res.data if reasons_res.ok and reasons_res.data else []

    assignees_res = list_assignees(ctx)
    assignees = assignees_res.data if assignees_res.ok and assignees_res.data else []

    status_options = [
        {"value": "OPEN", "label": "Chờ xử lý (Mở)"},
        {"value": "IN_PROGRESS", "label": "Đang xử lý"},
        {"value": "RESOLVED", "label": "Đã xử lý"},
        {"value": "ACCEPTED", "label": "Đã chấp nhận lệch"},
    ]
    reason_options = [{"value": r["CODE"], "label": r["LABEL"]} for r in reasons]
    assignee_options = [
        {"value": str(u["ID"]), "label": f"{u['FULL_NAME'] or u['USERNAME']} (@{u['USERNAME']})"} for u in assignees
    ]

    return alert_box(
        title=f"Đã chọn {len(selected_ids)} dòng chênh lệch",
        tone="info",
        message=dmc.Group(
            [
                dmc.Select(
                    id="issues-bulk-reason",
                    placeholder="Nguyên nhân",
                    data=reason_options,
                    clearable=True,
                    style={"width": 220},
                ),
                dmc.Select(
                    id="issues-bulk-assignee",
                    placeholder="Giao cho",
                    data=assignee_options,
                    clearable=True,
                    style={"width": 200},
                ),
                dmc.Select(
                    id="issues-bulk-status",
                    placeholder="Trạng thái",
                    data=status_options,
                    clearable=True,
                    style={"width": 180},
                ),
                button_primary("Áp dụng hàng loạt", id="issues-bulk-apply-btn", size="sm"),
            ],
            gap="xs",
            mt="xs",
        ),
    )


@callback(
    Output("issues-reload-trigger", "data", allow_duplicate=True),
    Output("issues-selected-store", "data", allow_duplicate=True),
    Input("issues-bulk-apply-btn", "n_clicks"),
    State("issues-selected-store", "data"),
    State("issues-bulk-reason", "value"),
    State("issues-bulk-assignee", "value"),
    State("issues-bulk-status", "value"),
    prevent_initial_call=True,
)
def handle_bulk_apply(
    n_clicks: int | None,
    selected_ids: list[int] | None,
    reason_code: str | None,
    assignee_val: str | None,
    status_val: str | None,
) -> tuple[Any, Any]:
    """Áp dụng cập nhật trạng thái/nguyên nhân/người xử lý hàng loạt cho các dòng đã chọn."""
    if not n_clicks or not selected_ids:
        return dash.no_update, dash.no_update

    ctx = get_current_ctx()
    if ctx is None:
        return dash.no_update, dash.no_update

    ass_id = int(assignee_val) if assignee_val and assignee_val.isdigit() else None

    bulk_update_issues_by_ids(
        ctx,
        issue_ids=selected_ids,
        reason_code=reason_code,
        assignee_id=ass_id,
        status=status_val,
    )

    import time

    return int(time.time()), []


@callback(
    Output("issues-edit-drawer", "opened"),
    Output("issues-drawer-header-info", "children"),
    Output("issues-drawer-status", "value"),
    Output("issues-drawer-reason", "value"),
    Output("issues-drawer-assignee", "value"),
    Output("issues-drawer-note", "value"),
    Output("issues-drawer-issue-id", "data"),
    Output("issues-drawer-feedback", "children"),
    Input({"type": "issues-row-action", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def open_issue_edit_drawer(
    clicks: list[int | None],
) -> tuple[bool, Any, str, str | None, str | None, str | None, int | None, Any]:
    """Mở Drawer chỉnh sửa chi tiết khi bấm nút 'Xử lý' trên dòng."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered or not any(clicks):
        return False, dash.no_update, "OPEN", None, None, None, None, None

    trigger_prop = ctx_dash.triggered[0]["prop_id"]
    import json

    row_meta = json.loads(trigger_prop.split(".")[0])
    issue_id = int(row_meta["index"])

    ctx = get_current_ctx()
    if ctx is None:
        return False, dash.no_update, "OPEN", None, None, None, None, None

    res = get_issue(ctx, issue_id=issue_id)
    if not res.ok or not res.data:
        return False, dash.no_update, "OPEN", None, None, None, None, None

    iss = res.data
    st = str(iss.get("STATUS", "OPEN"))
    r_code = iss.get("REASON_CODE")
    ass_id_str = str(iss["ASSIGNEE_ID"]) if iss.get("ASSIGNEE_ID") else None
    note_val = iss.get("NOTE") or ""

    hdr = dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text(iss.get("KEY_TEXT", "—"), fw=700, className="mono", size="lg"),
                    status_chip(st),
                ],
                gap="sm",
            ),
            dmc.Text(
                f"Template: {iss.get('TEMPLATE_NAME') or iss.get('TEMPLATE_CODE')} ({iss.get('PROFILE_CODE')})",
                size="sm",
                c="dimmed",
            ),
            dmc.Text(
                f"Phát hiện lần đầu ở Run #{iss.get('FIRST_RUN_ID', '—')} · Gần nhất ở Run #{iss.get('LAST_RUN_ID', '—')}",
                size="xs",
                c="dimmed",
            ),
        ],
        gap=4,
        mb="md",
    )

    return True, hdr, st, r_code, ass_id_str, note_val, issue_id, None


@callback(
    Output("issues-drawer-feedback", "children", allow_duplicate=True),
    Output("issues-reload-trigger", "data", allow_duplicate=True),
    Input("issues-drawer-save-btn", "n_clicks"),
    State("issues-drawer-issue-id", "data"),
    State("issues-drawer-status", "value"),
    State("issues-drawer-reason", "value"),
    State("issues-drawer-assignee", "value"),
    State("issues-drawer-note", "value"),
    prevent_initial_call=True,
)
def save_issue_detail(
    n_clicks: int | None,
    issue_id: int | None,
    status_val: str | None,
    reason_code: str | None,
    assignee_val: str | None,
    note_val: str | None,
) -> tuple[Any, Any]:
    """Lưu thông tin cập nhật của một Issue từ Drawer."""
    if not n_clicks or not issue_id:
        return dash.no_update, dash.no_update

    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Phiên làm việc hết hạn. Vui lòng đăng nhập lại.", tone="crit"), dash.no_update

    ass_id = int(assignee_val) if assignee_val and assignee_val.isdigit() else None

    res = update_issue_by_id(
        ctx,
        issue_id=issue_id,
        reason_code=reason_code,
        assignee_id=ass_id,
        status=status_val,
        note=note_val,
    )

    if not res.ok:
        return alert_box(f"Lỗi cập nhật: {res.message}", tone="crit"), dash.no_update

    import time

    return alert_box("Đã lưu cập nhật xử lý chênh lệch.", tone="ok"), int(time.time())
