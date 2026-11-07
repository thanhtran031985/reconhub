"""Màn chi tiết Bộ đối soát — Bước 8 task 18 (Screen13).

/batches/<def_id> (hoặc /batches/new): thông tin bộ, kỳ thử + xem trước tham số,
cảnh báo template Archived, bảng mục (sửa inline), hộp thoại Thêm template,
lưu bộ theo phong cách Fluent Compact + Master–Detail.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.context import Role
from app.core.session import get_current_ctx
from app.services.batch_def import (
    activate_batch_def,
    add_batch_def_items,
    addable_templates,
    archive_batch_def,
    create_batch_def,
    get_batch_def,
    preview_params,
    remove_batch_def_item,
    update_batch_def,
    update_batch_def_item,
)
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.status_chip import status_chip

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path_template="/batches/<def_id>",
        path="/batches/1",
        title="Bộ đối soát – ReconHub",
    )
except Exception:
    pass

MENU_CODE = "batch_def"


def _can_write(ctx: Any) -> bool:
    if ctx is None:
        return False
    return Role.ADMIN in ctx.roles or Role.TEMPLATE_OWNER in ctx.roles


def _params_text(override: Any) -> str:
    if not override:
        return ""
    try:
        if isinstance(override, dict):
            # Format dạng JSON hoặc key=val
            return json.dumps(override, ensure_ascii=False)
        return str(override)
    except Exception:
        return ""


def render_def_items_table(
    items: list[dict[str, Any]],
    can_write: bool = False,
    preview_map: dict[str, dict[str, Any]] | None = None,
    filter_q: str = "",
) -> Any:
    """Hàm thuần dựng bảng mục của bộ (sửa inline khi có quyền)."""
    if not items:
        return empty_state(
            title="Bộ này chưa có template nào",
            description="Thêm template từ danh sách template đã đăng ký và đang Active để bắt đầu.",
            action=(
                button_primary("Thêm template vào bộ", icon="lucide:plus", id="bdef-empty-add-btn", size="xs")
                if can_write
                else None
            ),
        )

    preview_map = preview_map or {}
    q = filter_q.strip().lower()
    filtered_items = items
    if q:
        filtered_items = [
            it for it in items
            if q in str(it.get("template_code", "")).lower() or q in str(it.get("template_name", "")).lower()
        ]

    if not filtered_items:
        return empty_state(
            title="Không có template khớp tìm kiếm",
            description="Hãy thử thay đổi từ khóa tìm kiếm.",
        )

    rows = []
    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--surface-2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "11px",
        "fontWeight": 600,
        "textAlign": "center",
        "whiteSpace": "nowrap",
        "borderBottom": "1px solid var(--line, #E0E0E0)",
    }

    for idx, it in enumerate(filtered_items, start=1):
        item_id = int(it.get("id") or 0)
        archived = str(it.get("template_status", "")) == "ARCHIVED"
        override_text = _params_text(it.get("params_override") or {})
        ds_text = f"DS #{it['data_source_id']}" if it.get("data_source_id") else "Mặc định template"
        profile = str(it.get("profile_code") or "—")
        tmpl_code = str(it.get("template_code", ""))

        # Giá trị với kỳ thử
        calc_cell: Any = dmc.Text("—", size="xs", c="dimmed")
        if tmpl_code in preview_map:
            p_info = preview_map[tmpl_code]
            p_vals = p_info.get("params") or {}
            p_errs = p_info.get("errors") or []
            if p_errs:
                calc_cell = dmc.Text("; ".join(str(e.get("message") or e) for e in p_errs), size="xs", c="red")
            elif p_vals:
                calc_cell = dmc.Stack(
                    [
                        dmc.Text(f"{k} = {v}", size="xs", className="rh-code", c="teal")
                        for k, v in list(p_vals.items())[:3]
                    ],
                    gap=0,
                )

        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(str(it.get("seq_no") or idx), size="xs", ta="center"), style={"verticalAlign": "middle"}),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Group(
                                    [
                                        dmc.Text(str(it.get("template_name", "")), fw=600, size="xs"),
                                        status_chip("ARCHIVED", label="Đã lưu trữ")
                                        if archived
                                        else dmc.Text("", size="xs"),
                                    ],
                                    gap="xs",
                                ),
                                dmc.Text(
                                    f"{tmpl_code} · {profile}",
                                    size="xs",
                                    c="dimmed",
                                    className="rh-code",
                                ),
                            ],
                            gap=2,
                        ),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Text(f"v{it.get('template_version') or '?'}", size="xs", className="rh-code", ta="center"),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.TextInput(
                            id={"type": "bdef-item-pattern", "index": item_id},
                            value=str(it.get("file_pattern", "")),
                            disabled=not can_write,
                            size="xs",
                            style={"minWidth": 120},
                            styles={"input": {"height": "26px", "minHeight": "26px", "fontSize": "11px", "fontFamily": "var(--mono)"}},
                        ),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.Checkbox(
                                    id={"type": "bdef-item-multi", "index": item_id},
                                    checked=bool(it.get("multi_file")),
                                    disabled=not can_write,
                                    size="xs",
                                ),
                            ],
                            justify="center",
                        ),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.Checkbox(
                                    id={"type": "bdef-item-required", "index": item_id},
                                    checked=bool(it.get("is_required")),
                                    disabled=not can_write,
                                    size="xs",
                                ),
                            ],
                            justify="center",
                        ),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.NumberInput(
                            id={"type": "bdef-item-priority", "index": item_id},
                            value=int(it.get("priority") or 100),
                            min=1,
                            max=1000,
                            step=1,
                            disabled=not can_write,
                            size="xs",
                            style={"width": 75},
                            styles={"input": {"height": "26px", "minHeight": "26px", "fontSize": "11px"}},
                        ),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Text(ds_text, size="xs", className="rh-code", c="dimmed", ta="center"),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.TextInput(
                            id={"type": "bdef-item-params", "index": item_id},
                            value=override_text,
                            placeholder="{}",
                            disabled=not can_write,
                            size="xs",
                            style={"minWidth": 140},
                            styles={"input": {"height": "26px", "minHeight": "26px", "fontSize": "11px", "fontFamily": "var(--mono)"}},
                        ),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(calc_cell, style={"verticalAlign": "middle", "minWidth": 140}),
                    dmc.TableTd(
                        dmc.ActionIcon(
                            DashIconify(icon="lucide:trash-2", width=14),
                            id={"type": "bdef-item-remove", "index": item_id},
                            color="red",
                            variant="subtle",
                            size="sm",
                            **{"aria-label": f"Gỡ {tmpl_code}"},
                        )
                        if can_write
                        else dmc.Text(""),
                        style={"verticalAlign": "middle", "textAlign": "center"},
                    ),
                ]
            )
        )

    return dmc.TableScrollContainer(
        minWidth=950,
        style={"flex": 1, "minHeight": 0, "overflow": "auto"},
        children=dmc.Table(
            [
                dmc.TableThead(
                    dmc.TableTr(
                        [
                            dmc.TableTh("#", style={**th_style, "width": "40px"}),
                            dmc.TableTh("Template đã đăng ký", style={**th_style, "minWidth": "190px", "textAlign": "left"}),
                            dmc.TableTh("Version", style={**th_style, "width": "65px"}),
                            dmc.TableTh("Mẫu tên file", style={**th_style, "minWidth": "130px"}),
                            dmc.TableTh("Gộp", style={**th_style, "width": "50px"}),
                            dmc.TableTh("Bắt buộc", style={**th_style, "width": "65px"}),
                            dmc.TableTh("Ưu tiên", style={**th_style, "width": "80px"}),
                            dmc.TableTh("Data Source", style={**th_style, "width": "110px"}),
                            dmc.TableTh("Tham số ghi đè", style={**th_style, "minWidth": "150px"}),
                            dmc.TableTh("Giá trị với kỳ thử", style={**th_style, "minWidth": "150px", "textAlign": "left"}),
                            dmc.TableTh("", style={**th_style, "width": "50px"}),
                        ]
                    )
                ),
                dmc.TableTbody(rows),
            ],
            striped=False,
            highlightOnHover=True,
            verticalSpacing=3,
            style={"fontSize": "12px"},
        ),
    )


def render_preview_result(preview: dict[str, Any] | None, error: str | None = None) -> Any:
    """Hàm thuần dựng bảng xem trước tham số với kỳ thử."""
    if error:
        return alert_box(title="Không xem trước được tham số", message=error, tone="crit")
    if preview is None:
        return dmc.Text("Nhập kỳ (YYYY-MM) rồi bấm Xem trước tham số.", size="xs", c="dimmed")
    items = preview.get("items") or []
    if not items:
        return empty_state(title="Bộ chưa có mục nào", description="Thêm template vào bộ trước.")
    rows = []
    for it in items:
        params = it.get("params") or {}
        errors = it.get("errors") or []
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(str(it.get("template_code", "")), className="rh-code", size="xs")),
                    dmc.TableTd(
                        dmc.Text(
                            json.dumps(params, ensure_ascii=False),
                            size="xs",
                            className="rh-code",
                            style={"whiteSpace": "pre-wrap", "wordBreak": "break-all"},
                        )
                    ),
                    dmc.TableTd(
                        dmc.Text(
                            "; ".join(str(e.get("message") or e) for e in errors),
                            size="xs",
                            c="red",
                        )
                        if errors
                        else dmc.Text("Hợp lệ", size="xs", c="teal")
                    ),
                ]
            )
        )
    th_prev = {"textAlign": "center", "fontSize": "11px", "fontWeight": 600}
    return dmc.Table(
        [
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh("Template", style=th_prev),
                        dmc.TableTh("Giá trị đã tính", style=th_prev),
                        dmc.TableTh("Lỗi", style=th_prev),
                    ]
                )
            ),
            dmc.TableTbody(rows),
        ],
        striped=True,
        style={"fontSize": "11px"},
    )


def render_addable_list(
    templates: list[dict[str, Any]] | None,
    error: str | None = None,
) -> Any:
    """Hàm thuần dựng danh sách template trong hộp thoại Thêm template."""
    if error:
        return alert_box(title="Không tải được danh sách template", message=error, tone="crit")
    if not templates:
        return empty_state(
            title="Không có template nào khớp",
            description="Thử thay đổi từ khóa tìm kiếm hoặc bỏ lọc.",
        )
    rows = []
    for t in templates:
        tid = int(t.get("template_id") or 0)
        addable = bool(t.get("addable"))
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Checkbox(
                            id={"type": "bdef-add-check", "index": tid},
                            disabled=not addable,
                            size="xs",
                        ),
                        style={"textAlign": "center"},
                    ),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(str(t.get("code", "")), fw=600, size="xs", className="rh-code"),
                                dmc.Text(str(t.get("name", "")), size="xs", c="dimmed"),
                            ],
                            gap=0,
                        )
                    ),
                    dmc.TableTd(status_chip(str(t.get("status", ""))), style={"textAlign": "center"}),
                    dmc.TableTd(dmc.Text(f"v{t.get('version') or '?'}", size="xs", className="rh-code", ta="center")),
                    dmc.TableTd(
                        dmc.Text(
                            str(t.get("reason") or "Thêm được"),
                            size="xs",
                            c="red" if not addable else "dimmed",
                        )
                    ),
                ]
            )
        )
    th_add = {"textAlign": "center", "fontSize": "11px", "fontWeight": 600}
    return dmc.Table(
        [
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh("", style={**th_add, "width": "40px"}),
                        dmc.TableTh("Template", style=th_add),
                        dmc.TableTh("Trạng thái", style=th_add),
                        dmc.TableTh("Version", style=th_add),
                        dmc.TableTh("Ghi chú", style=th_add),
                    ]
                )
            ),
            dmc.TableTbody(rows),
        ],
        striped=True,
        style={"fontSize": "12px"},
    )


def layout(def_id: str | int | None = 1, **kwargs: Any) -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return dmc.Box(
            [
                dcc.Location(id="bdef-edit-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang Bộ đối soát.", tone="crit"),
            ],
            p="md",
        )

    is_new = str(def_id).lower() == "new"
    def_id_val: int | str = "new" if is_new else int(def_id or 1)
    trial_period = datetime.now().strftime("%Y-%m")

    return html.Div(
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "8px 14px",
            "gap": "6px",
        },
        children=[
            dcc.Store(id="bdef-edit-store"),
            dcc.Store(id="bdef-edits-store", data={}),
            dcc.Store(id="bdef-remove-target"),
            dcc.Store(id="bdef-def-id", data=def_id_val),
            dcc.Store(id="bdef-addable-store"),
            dcc.Store(id="bdef-preview-store", data={}),
            dcc.Location(id="bdef-edit-redirect", refresh=True),

            # Navigation back + Header 1 dòng
            dmc.Box(
                [
                    dmc.Anchor(
                        dmc.Group(
                            [
                                DashIconify(icon="lucide:arrow-left", width=12),
                                dmc.Text("Danh sách bộ đối soát", size="xs"),
                            ],
                            gap=4,
                        ),
                        href="/batches",
                        underline=False,
                        style={"display": "inline-flex", "marginBottom": "2px"},
                    ),
                    html.Div(id="bdef-edit-header"),
                    html.Div(id="bdef-edit-notifications"),
                ],
                style={"flexShrink": 0},
            ),

            # Master–Detail Grid: Trái 310px (Config + Công thức + Kỳ thử), Phải flex 1 (Templates)
            dmc.Box(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "310px minmax(0, 1fr)",
                    "flex": 1,
                    "minHeight": 0,
                    "gap": "8px",
                    "overflow": "hidden",
                },
                children=[
                    # Cột TRÁI: Master Config (cuộn độc lập)
                    dmc.Box(
                        style={
                            "display": "flex",
                            "flexDirection": "column",
                            "gap": "6px",
                            "minHeight": 0,
                            "overflowY": "auto",
                            "paddingRight": "2px",
                        },
                        children=[
                            # Card 1: Thông tin bộ
                            dmc.Paper(
                                dmc.Stack(
                                    [
                                        dmc.Title("Thông tin bộ", order=5),
                                        dmc.TextInput(
                                            id="bdef-info-code",
                                            label="Mã bộ",
                                            placeholder="VD: DOANH_THU_CUOI_THANG",
                                            size="xs",
                                            disabled=not is_new,
                                            styles={"input": {"fontFamily": "var(--mono)", "fontSize": "11px", "height": "28px", "minHeight": "28px"}},
                                        ),
                                        dmc.TextInput(
                                            id="bdef-info-name",
                                            label="Tên bộ *",
                                            placeholder="VD: Đối soát doanh thu cuối tháng",
                                            size="xs",
                                            styles={"input": {"fontSize": "12px", "height": "28px", "minHeight": "28px"}},
                                        ),
                                        dmc.NumberInput(
                                            id="bdef-info-max-parallel",
                                            label="Số run song song mỗi Data Source",
                                            description="Tránh dồn nhiều truy vấn cùng lúc vào Oracle qua VPN.",
                                            value=2,
                                            min=1,
                                            max=4,
                                            step=1,
                                            size="xs",
                                            styles={"input": {"fontSize": "12px", "height": "28px", "minHeight": "28px"}},
                                        ),
                                        dmc.Textarea(
                                            id="bdef-info-desc",
                                            label="Mô tả",
                                            placeholder="Mô tả mục đích bộ đối soát",
                                            size="xs",
                                            autosize=True,
                                            minRows=1,
                                            maxRows=3,
                                            styles={"input": {"fontSize": "11px"}},
                                        ),
                                    ],
                                    gap="xs",
                                ),
                                p="xs",
                                withBorder=True,
                                radius="sm",
                            ),

                            # Card 2: Công thức tham số theo kỳ
                            dmc.Paper(
                                dmc.Stack(
                                    [
                                        dmc.Title("Công thức tham số theo kỳ", order=5),
                                        dmc.Table(
                                            dmc.TableTbody(
                                                [
                                                    dmc.TableTr([dmc.TableTd(dmc.Text("{ky.tu}", className="rh-code", size="xs")), dmc.TableTd(dmc.Text("Đầu kỳ 00:00:00", size="xs"))]),
                                                    dmc.TableTr([dmc.TableTd(dmc.Text("{ky.den}", className="rh-code", size="xs")), dmc.TableTd(dmc.Text("Cuối kỳ 23:59:59", size="xs"))]),
                                                    dmc.TableTr([dmc.TableTd(dmc.Text("{ky.tu-1d}", className="rh-code", size="xs")), dmc.TableTd(dmc.Text("Lùi/tiến N ngày (±Nd)", size="xs"))]),
                                                    dmc.TableTr([dmc.TableTd(dmc.Text("{ky.thang}", className="rh-code", size="xs")), dmc.TableTd(dmc.Text("Kỳ số YYYYMM", size="xs"))]),
                                                    dmc.TableTr([dmc.TableTd(dmc.Text("{ky.nam}", className="rh-code", size="xs")), dmc.TableTd(dmc.Text("Năm YYYY", size="xs"))]),
                                                ]
                                            ),
                                            style={"fontSize": "11px"},
                                        ),
                                        dmc.Text(
                                            "Ô tham số để trống = dùng mặc định template. Chỉ ghi đè được tham số có trong template.",
                                            size="xs",
                                            c="dimmed",
                                        ),
                                    ],
                                    gap=4,
                                ),
                                p="xs",
                                withBorder=True,
                                radius="sm",
                            ),

                            # Card 3: Xem trước với kỳ
                            dmc.Paper(
                                dmc.Stack(
                                    [
                                        dmc.Title("Xem trước với kỳ", order=5),
                                        dmc.Group(
                                            [
                                                dmc.TextInput(
                                                    id="bdef-trial-period",
                                                    label="Kỳ thử (YYYY-MM)",
                                                    value=trial_period,
                                                    size="xs",
                                                    style={"flex": 1},
                                                    styles={"input": {"fontSize": "11px", "height": "28px", "minHeight": "28px"}},
                                                ),
                                                button_subtle("Tính lại", id="bdef-preview-btn", icon="lucide:refresh-cw", size="xs"),
                                            ],
                                            align="flex-end",
                                            gap="xs",
                                        ),
                                        dmc.Text(id="bdef-trial-hint", size="xs", c="dimmed"),
                                        alert_box(
                                            title="Gợi ý kiểm tra",
                                            message="Cột 'Giá trị với kỳ thử' bên phải giúp soát công thức trước khi lưu.",
                                            tone="info",
                                        ),
                                    ],
                                    gap=4,
                                ),
                                p="xs",
                                withBorder=True,
                                radius="sm",
                            ),

                            html.Div(id="bdef-archived-alert"),
                        ],
                    ),

                    # Cột PHẢI: Detail Templates
                    dmc.Paper(
                        style={
                            "display": "flex",
                            "flexDirection": "column",
                            "minHeight": 0,
                            "height": "100%",
                            "overflow": "hidden",
                        },
                        withBorder=True,
                        radius="sm",
                        children=[
                            # Toolbar trên bảng template
                            dmc.Group(
                                [
                                    dmc.Group(
                                        [
                                            dmc.Title("Template trong bộ", order=5),
                                            html.Span(id="bdef-items-count", style={"fontSize": "11px", "color": "var(--ink-soft, #616161)"}),
                                        ],
                                        gap="xs",
                                    ),
                                    dmc.Group(
                                        [
                                            dmc.TextInput(
                                                id="bdef-items-search",
                                                placeholder="Tìm template, hệ thống...",
                                                size="xs",
                                                w=220,
                                                styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "11px"}},
                                            ),
                                            button_primary("Thêm template vào bộ", icon="lucide:plus", id="bdef-add-open-btn", size="xs"),
                                        ],
                                        gap="xs",
                                    ),
                                ],
                                justify="space-between",
                                align="center",
                                p="xs",
                                style={"borderBottom": "1px solid var(--line, #E0E0E0)", "backgroundColor": "var(--surface-2, #FAFAFA)", "flexShrink": 0},
                            ),

                            # Bảng template
                            html.Div(
                                id="bdef-edit-content",
                                style={
                                    "flex": 1,
                                    "minHeight": 0,
                                    "overflow": "hidden",
                                    "display": "flex",
                                    "flexDirection": "column",
                                },
                            ),

                            # Sticky Footer
                            dmc.Group(
                                [
                                    dmc.Text(id="bdef-dirty-hint", size="xs", c="dimmed"),
                                    dmc.Group(
                                        [
                                            button_primary("Lưu bộ đối soát", id="bdef-save-btn", icon="lucide:save", size="xs"),
                                        ],
                                        gap="xs",
                                    ),
                                ],
                                justify="space-between",
                                align="center",
                                p="xs",
                                style={
                                    "borderTop": "1px solid var(--line, #E0E0E0)",
                                    "backgroundColor": "var(--surface-2, #FAFAFA)",
                                    "flexShrink": 0,
                                },
                            ),
                        ],
                    ),
                ],
            ),

            # Modal Thêm template vào bộ
            dmc.Modal(
                id="bdef-add-modal",
                title="Thêm template vào bộ",
                size="xl",
                centered=True,
                children=[
                    dmc.Stack(
                        [
                            dmc.Group(
                                [
                                    dmc.TextInput(
                                        id="bdef-add-search",
                                        placeholder="Tìm theo mã hoặc tên template...",
                                        leftSection=DashIconify(icon="lucide:search", width=14),
                                        style={"flex": 1},
                                        size="xs",
                                    ),
                                    dmc.Select(
                                        id="bdef-add-filter",
                                        data=[
                                            {"label": "Chỉ template thêm được", "value": "addable"},
                                            {"label": "Tất cả", "value": "all"},
                                        ],
                                        value="addable",
                                        style={"width": 190},
                                        size="xs",
                                    ),
                                ],
                                gap="xs",
                            ),
                            html.Div(
                                id="bdef-add-list",
                                style={"maxHeight": "280px", "overflowY": "auto"},
                            ),
                            html.Div(id="bdef-add-config"),
                            dmc.Group(
                                [
                                    button_subtle("Hủy", id="bdef-add-cancel", size="xs"),
                                    button_primary("Thêm template", id="bdef-add-submit", size="xs"),
                                ],
                                justify="flex-end",
                                gap="xs",
                            ),
                        ],
                        gap="sm",
                    )
                ],
            ),
            modal_confirm(
                id="bdef-remove-modal",
                title="Gỡ template khỏi bộ",
                description="Template sẽ được gỡ khỏi bộ đối soát. Các lần chạy bộ cũ không bị ảnh hưởng.",
                confirm_label="Gỡ khỏi bộ",
            ),
            modal_confirm(
                id="bdef-edit-archive-modal",
                title="Lưu trữ bộ đối soát",
                description="Bộ đối soát đã lưu trữ không thể tạo lần chạy mới. Các lần chạy cũ vẫn xem được.",
                confirm_label="Lưu trữ",
            ),
        ],
    )


@callback(
    Output("bdef-edit-store", "data"),
    Input("bdef-def-id", "data"),
)
def _load_def(def_id: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return {"error": "Bạn cần đăng nhập để xem bộ đối soát."}
    if str(def_id).lower() == "new":
        return {
            "id": "new",
            "code": "",
            "name": "",
            "description": "",
            "status": "DRAFT",
            "max_parallel_per_ds": 2,
            "cnt_items": 0,
            "items": [],
            "row_version": 1,
        }
    try:
        def_id_int = int(def_id)
    except (TypeError, ValueError):
        return {"error": "Bộ đối soát không hợp lệ."}
    res = get_batch_def(ctx, def_id_int)
    if not res.ok:
        return {"error": res.message or "Không tìm thấy bộ đối soát."}
    return res.data


@callback(
    Output("bdef-edit-header", "children"),
    Output("bdef-info-code", "value"),
    Output("bdef-info-name", "value"),
    Output("bdef-info-max-parallel", "value"),
    Output("bdef-info-desc", "value"),
    Output("bdef-archived-alert", "children"),
    Input("bdef-edit-store", "data"),
)
def _populate_info(store_data: Any) -> tuple[Any, str, str, int, str, Any]:
    ctx = get_current_ctx()
    can_write = _can_write(ctx)
    if not store_data or (isinstance(store_data, dict) and store_data.get("error")):
        return None, "", "", 2, "", None

    is_new = str(store_data.get("id")) == "new"
    status = str(store_data.get("status", "DRAFT"))
    items = store_data.get("items") or []
    archived = [it for it in items if str(it.get("template_status", "")) == "ARCHIVED"]

    arch_alert = None
    if archived:
        arch_alert = alert_box(
            title="Có template đã lưu trữ trong bộ",
            message=f"{len(archived)} template trong bộ đã bị Archive ({', '.join(str(it.get('template_code')) for it in archived)}). Khi chạy sẽ bị bỏ qua.",
            tone="warn",
        )

    header_actions = []
    if can_write and not is_new:
        if status == "DRAFT":
            header_actions.append(button_subtle("Kích hoạt", id="bdef-activate-btn", icon="lucide:play", size="xs"))
        if status != "ARCHIVED":
            header_actions.append(button_subtle("Lưu trữ", id="bdef-archive-btn", icon="lucide:archive", size="xs"))

    header = dmc.Group(
        [
            dmc.Group(
                [
                    dmc.Title(
                        f"Bộ đối soát: {store_data.get('name') or '(Chưa đặt tên)'}" if not is_new else "Tạo mới bộ đối soát",
                        order=4,
                    ),
                    status_chip(status) if not is_new else status_chip("DRAFT", label="Bản nháp mới"),
                ],
                gap="xs",
                align="center",
            ),
            dmc.Group(header_actions, gap="xs"),
        ],
        justify="space-between",
        align="center",
    )

    return (
        header,
        str(store_data.get("code") or ""),
        str(store_data.get("name") or ""),
        int(store_data.get("max_parallel_per_ds") or 2),
        str(store_data.get("description") or ""),
        arch_alert,
    )


@callback(
    Output("bdef-edit-content", "children"),
    Output("bdef-items-count", "children"),
    Input("bdef-edit-store", "data"),
    Input("bdef-items-search", "value"),
    Input("bdef-preview-store", "data"),
)
def _render_items(store_data: Any, search: str | None, preview_data: Any) -> tuple[Any, str]:
    ctx = get_current_ctx()
    can_write = _can_write(ctx)
    if store_data is None:
        return dmc.Stack([dmc.Skeleton(height=36, radius="sm") for _ in range(4)], gap="xs"), ""
    if isinstance(store_data, dict) and store_data.get("error"):
        return alert_box(title="Không thể tải bộ đối soát", message=str(store_data["error"]), tone="crit"), ""

    items = store_data.get("items") or []
    table = render_def_items_table(
        items,
        can_write=can_write,
        preview_map=preview_data if isinstance(preview_data, dict) else {},
        filter_q=search or "",
    )
    return table, f"({len(items)} template)"


@callback(
    Output("bdef-preview-store", "data"),
    Output("bdef-trial-hint", "children"),
    Input("bdef-def-id", "data"),
    Input("bdef-trial-period", "value"),
    Input("bdef-preview-btn", "n_clicks"),
)
def _calc_preview(def_id: Any, period: str | None, _n: Any) -> tuple[dict[str, Any], str]:
    p = (period or "").strip()
    if not p:
        return {}, "Nhập kỳ thử dạng YYYY-MM."
    hint = f"Kỳ thử: {p}-01 00:00:00 → cuối tháng 23:59:59"
    if str(def_id).lower() == "new":
        return {}, hint
    ctx = get_current_ctx()
    if ctx is None:
        return {}, hint
    try:
        def_id_int = int(def_id)
    except (TypeError, ValueError):
        return {}, hint
    res = preview_params(ctx, def_id_int, p)
    if not res.ok or not res.data:
        return {}, hint
    items_prev = res.data.get("items") or []
    mapping = {str(it.get("template_code")): it for it in items_prev}
    return mapping, hint


@callback(
    Output("bdef-edits-store", "data"),
    Output("bdef-dirty-hint", "children"),
    Input({"type": "bdef-item-pattern", "index": ALL}, "value"),
    Input({"type": "bdef-item-multi", "index": ALL}, "checked"),
    Input({"type": "bdef-item-required", "index": ALL}, "checked"),
    Input({"type": "bdef-item-priority", "index": ALL}, "value"),
    Input({"type": "bdef-item-params", "index": ALL}, "value"),
    State("bdef-edits-store", "data"),
    State("bdef-edit-store", "data"),
    prevent_initial_call=True,
)
def _track_item_edits(
    patterns: Any, multis: Any, requireds: Any, priorities: Any, params_list: Any, edits: Any, store_data: Any
) -> tuple[Any, Any]:
    if not store_data or store_data.get("error"):
        return dash.no_update, ""
    originals = {int(it["id"]): it for it in (store_data.get("items") or []) if str(it.get("id")).isdigit()}
    new_edits: dict[str, Any] = dict(edits or {})
    fields = [
        ("file_pattern", patterns),
        ("multi_file", multis),
        ("is_required", requireds),
        ("priority", priorities),
        ("params_override", params_list),
    ]
    item_ids = [int(it["id"]) for it in (store_data.get("items") or []) if str(it.get("id")).isdigit()]
    for pos, item_id in enumerate(item_ids):
        orig = originals.get(item_id, {})
        changed: dict[str, Any] = {}
        for key, values in fields:
            if values is None or pos >= len(values):
                continue
            val = values[pos]
            if key == "params_override":
                cur = _params_text(orig.get("params_override") or {})
                if (val or "") != cur:
                    changed[key] = val or ""
            elif key in ("multi_file", "is_required"):
                if bool(val) != bool(orig.get(key)):
                    changed[key] = bool(val)
            elif key == "priority":
                try:
                    if int(val or 0) != int(orig.get("priority") or 0):
                        changed[key] = int(val or 0)
                except (TypeError, ValueError):
                    pass
            else:
                if (val or "") != str(orig.get(key) or ""):
                    changed[key] = val or ""
        if changed:
            new_edits[str(item_id)] = changed
        else:
            new_edits.pop(str(item_id), None)
    hint = f"Có {len(new_edits)} mục thay đổi chưa lưu." if new_edits else "Chưa có thay đổi."
    return new_edits, hint


@callback(
    Output("bdef-edit-notifications", "children"),
    Output("bdef-edit-store", "data", allow_duplicate=True),
    Output("bdef-edits-store", "data", allow_duplicate=True),
    Output("bdef-dirty-hint", "children", allow_duplicate=True),
    Output("bdef-edit-redirect", "href"),
    Input("bdef-save-btn", "n_clicks"),
    State("bdef-def-id", "data"),
    State("bdef-edit-store", "data"),
    State("bdef-edits-store", "data"),
    State("bdef-info-code", "value"),
    State("bdef-info-name", "value"),
    State("bdef-info-desc", "value"),
    State("bdef-info-max-parallel", "value"),
    prevent_initial_call=True,
)
def _save_def(
    _n: Any,
    def_id: Any,
    store_data: Any,
    edits: Any,
    code: str | None,
    name: str | None,
    desc: str | None,
    max_parallel: Any,
) -> tuple[Any, Any, Any, Any, Any]:
    if not _n:
        return dash.no_update, dash.no_update, dash.no_update, "", dash.no_update
    ctx = get_current_ctx()
    if ctx is None:
        return notify_error("Bạn cần đăng nhập."), dash.no_update, dash.no_update, "", dash.no_update

    name_clean = (name or "").strip()
    if not name_clean:
        return notify_error("Tên bộ đối soát không được để trống."), dash.no_update, dash.no_update, "", dash.no_update

    # Nếu đang tạo mới (def_id == 'new')
    if str(def_id).lower() == "new":
        code_clean = (code or "").strip().upper()
        if not code_clean:
            return notify_error("Mã bộ đối soát không được để trống."), dash.no_update, dash.no_update, "", dash.no_update
        res = create_batch_def(
            ctx,
            {
                "code": code_clean,
                "name": name_clean,
                "description": (desc or "").strip() or None,
                "max_parallel_per_ds": int(max_parallel or 2),
            },
        )
        if not res.ok or not res.data:
            return notify_error(res.message or "Không tạo được bộ đối soát."), dash.no_update, dash.no_update, "", dash.no_update
        new_id = int(res.data["id"])
        # Thêm các item nếu có
        pending_items = store_data.get("items") or []
        if pending_items:
            add_batch_def_items(ctx, new_id, pending_items)
        return notify_success("Tạo bộ đối soát thành công."), dash.no_update, {}, "", f"/batches/{new_id}"

    # Đang sửa bộ đã có
    def_id_int = int(def_id)
    errors: list[str] = []
    if (
        name_clean != str(store_data.get("name", ""))
        or (desc or "").strip() != str(store_data.get("description") or "")
        or int(max_parallel or 2) != int(store_data.get("max_parallel_per_ds") or 2)
    ):
        res = update_batch_def(
            ctx,
            def_id_int,
            {
                "name": name_clean,
                "description": (desc or "").strip() or None,
                "max_parallel_per_ds": int(max_parallel or 2),
            },
            row_version=int(store_data.get("row_version") or 0),
        )
        if not res.ok:
            errors.append(res.message or "Không lưu được thông tin bộ.")

    for item_id_str, changed in (edits or {}).items():
        payload: dict[str, Any] = {}
        if "file_pattern" in changed:
            payload["file_pattern"] = changed["file_pattern"]
        if "multi_file" in changed:
            payload["multi_file"] = changed["multi_file"]
        if "is_required" in changed:
            payload["is_required"] = changed["is_required"]
        if "priority" in changed:
            payload["priority"] = changed["priority"]
        if "params_override" in changed:
            raw = (changed["params_override"] or "").strip()
            if raw == "":
                payload["params_override"] = {}
            else:
                try:
                    parsed = json.loads(raw)
                except Exception:
                    errors.append(f"Mục #{item_id_str}: tham số ghi đè không phải JSON hợp lệ.")
                    continue
                if not isinstance(parsed, dict):
                    errors.append(f"Mục #{item_id_str}: tham số ghi đè phải là một object JSON.")
                    continue
                payload["params_override"] = parsed
        orig = next((it for it in (store_data.get("items") or []) if int(it["id"]) == int(item_id_str)), None)
        res = update_batch_def_item(
            ctx,
            int(item_id_str),
            payload,
            row_version=int(orig["row_version"]) if orig else None,
        )
        if not res.ok:
            errors.append(res.message or f"Không lưu được mục #{item_id_str}.")

    if errors:
        return notify_error("; ".join(errors)), dash.no_update, dash.no_update, "", dash.no_update

    refreshed = get_batch_def(ctx, def_id_int)
    if not refreshed.ok:
        return notify_error(refreshed.message or "Không tải lại được bộ."), dash.no_update, dash.no_update, "", dash.no_update
    now_str = datetime.now().strftime("%H:%M:%S")
    return (
        notify_success("Đã lưu bộ đối soát thành công."),
        refreshed.data,
        {},
        f"Đã lưu lúc {now_str}.",
        dash.no_update,
    )


@callback(
    Output("bdef-add-modal", "opened"),
    Output("bdef-remove-modal", "opened", allow_duplicate=True),
    Input("bdef-add-open-btn", "n_clicks"),
    Input("bdef-add-cancel", "n_clicks"),
    State("bdef-add-modal", "opened"),
    prevent_initial_call=True,
)
def _toggle_add_modal(_open: Any, _cancel: Any, opened: bool) -> tuple[Any, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, dash.no_update
    trig = ctx_dash.triggered_id
    if trig == "bdef-add-cancel":
        return False, False
    if trig == "bdef-add-open-btn" and bool(_open):
        return True, False
    return False, dash.no_update


@callback(
    Output("bdef-add-list", "children"),
    Output("bdef-addable-store", "data"),
    Input("bdef-add-modal", "opened"),
    Input("bdef-add-search", "value"),
    Input("bdef-add-filter", "value"),
    State("bdef-def-id", "data"),
)
def _load_addable(opened: bool, search: str | None, filter_value: str | None, def_id: Any) -> tuple[Any, Any]:
    if not opened:
        return None, dash.no_update
    ctx = get_current_ctx()
    if ctx is None:
        return render_addable_list(None, error="Bạn cần đăng nhập."), None
    # Nếu def_id == 'new', dùng def_id=0 hoặc lấy addable
    did = 0 if str(def_id).lower() == "new" else int(def_id)
    res = addable_templates(ctx, did, q=(search or "").strip() or None, include_unavailable=(filter_value == "all"))
    if not res.ok:
        return render_addable_list(None, error=res.message), None
    return render_addable_list(res.data), res.data


@callback(
    Output("bdef-add-config", "children"),
    Input({"type": "bdef-add-check", "index": ALL}, "checked"),
    Input({"type": "bdef-add-check", "index": ALL}, "id"),
    State("bdef-addable-store", "data"),
)
def _render_add_config(checked_list: Any, check_ids: Any, addable: Any) -> Any:
    selected = [int(c["index"]) for c, v in zip(check_ids or [], checked_list or [], strict=False) if v]
    if not selected:
        return None
    by_id = {int(t["template_id"]): t for t in (addable or [])}
    rows = []
    th_cfg = {"textAlign": "center", "fontSize": "11px", "fontWeight": 600}
    for tmpl_id in selected:
        t = by_id.get(tmpl_id, {})
        code = str(t.get("code", ""))
        suggest_pat = f"*{code.split('_')[0]}*" if "_" in code else f"*{code}*"
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(f"{code} — {t.get('name', '')}", fw=600, size="xs")),
                    dmc.TableTd(
                        dmc.TextInput(
                            id={"type": "bdef-add-pattern", "index": tmpl_id},
                            value=suggest_pat,
                            size="xs",
                            styles={"input": {"height": "26px", "fontSize": "11px", "fontFamily": "var(--mono)"}},
                        )
                    ),
                    dmc.TableTd(
                        dmc.Group([dmc.Checkbox(id={"type": "bdef-add-multi", "index": tmpl_id}, checked=False, size="xs")], justify="center")
                    ),
                    dmc.TableTd(
                        dmc.Group([dmc.Checkbox(id={"type": "bdef-add-required", "index": tmpl_id}, checked=True, size="xs")], justify="center")
                    ),
                    dmc.TableTd(
                        dmc.NumberInput(
                            id={"type": "bdef-add-priority", "index": tmpl_id},
                            value=100,
                            min=1,
                            max=1000,
                            step=1,
                            size="xs",
                            style={"width": 75},
                            styles={"input": {"height": "26px", "fontSize": "11px"}},
                        )
                    ),
                ]
            )
        )
    return dmc.Stack(
        [
            dmc.Divider(label=f"Cách chạy trong bộ ({len(selected)} template đã chọn)", labelPosition="left"),
            dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr(
                            [
                                dmc.TableTh("Template", style=th_cfg),
                                dmc.TableTh("Mẫu tên file *", style=th_cfg),
                                dmc.TableTh("Gộp", style=th_cfg),
                                dmc.TableTh("Bắt buộc", style=th_cfg),
                                dmc.TableTh("Ưu tiên", style=th_cfg),
                            ]
                        )
                    ),
                    dmc.TableTbody(rows),
                ],
                striped=True,
                style={"fontSize": "11px"},
            ),
        ],
        gap="xs",
    )


@callback(
    Output("bdef-edit-notifications", "children", allow_duplicate=True),
    Output("bdef-edit-store", "data", allow_duplicate=True),
    Output("bdef-add-modal", "opened", allow_duplicate=True),
    Input("bdef-add-submit", "n_clicks"),
    State("bdef-def-id", "data"),
    State("bdef-edit-store", "data"),
    State({"type": "bdef-add-check", "index": ALL}, "checked"),
    State({"type": "bdef-add-check", "index": ALL}, "id"),
    State({"type": "bdef-add-pattern", "index": ALL}, "value"),
    State({"type": "bdef-add-pattern", "index": ALL}, "id"),
    State({"type": "bdef-add-required", "index": ALL}, "checked"),
    State({"type": "bdef-add-required", "index": ALL}, "id"),
    State({"type": "bdef-add-multi", "index": ALL}, "checked"),
    State({"type": "bdef-add-multi", "index": ALL}, "id"),
    State({"type": "bdef-add-priority", "index": ALL}, "value"),
    State({"type": "bdef-add-priority", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def _submit_add_templates(
    _n: Any,
    def_id: Any,
    store_data: Any,
    checked_list: Any,
    check_ids: Any,
    patterns: Any,
    pattern_ids: Any,
    requireds: Any,
    required_ids: Any,
    multis: Any,
    multi_ids: Any,
    priorities: Any,
    priority_ids: Any,
) -> tuple[Any, Any, bool]:
    if not _n:
        return dash.no_update, dash.no_update, True
    ctx = get_current_ctx()
    if ctx is None:
        return notify_error("Bạn cần đăng nhập."), dash.no_update, True
    selected = [int(c["index"]) for c, v in zip(check_ids or [], checked_list or [], strict=False) if v]
    if not selected:
        return notify_error("Chưa chọn template nào để thêm.", title="Cảnh báo"), dash.no_update, True

    by_index: dict[str, dict[str, Any]] = {}
    for values, ids in [
        (patterns, pattern_ids),
        (requireds, required_ids),
        (multis, multi_ids),
        (priorities, priority_ids),
    ]:
        for val, ident in zip(values or [], ids or [], strict=False):
            by_index.setdefault(str(ident["index"]), {})[str(ident["type"])] = val

    did = 0 if str(def_id).lower() == "new" else int(def_id)
    addable = addable_templates(ctx, did, include_unavailable=True)
    code_by_id = {}
    name_by_id = {}
    if addable.ok:
        code_by_id = {int(t["template_id"]): str(t["code"]) for t in (addable.data or [])}
        name_by_id = {int(t["template_id"]): str(t.get("name") or "") for t in (addable.data or [])}

    items_to_add: list[dict[str, Any]] = []
    for tmpl_id in selected:
        cfg = by_index.get(str(tmpl_id), {})
        pattern = cfg.get("bdef-add-pattern") or f"*{code_by_id.get(tmpl_id, '')}*"
        items_to_add.append(
            {
                "template_id": tmpl_id,
                "template_code": code_by_id.get(tmpl_id, ""),
                "template_name": name_by_id.get(tmpl_id, ""),
                "file_pattern": pattern,
                "multi_file": bool(cfg.get("bdef-add-multi", False)),
                "is_required": bool(cfg.get("bdef-add-required", True)),
                "priority": int(cfg.get("bdef-add-priority") or 100),
                "params_override": {},
            }
        )

    # Nếu đang tạo mới (new), lưu tạm vào store_data
    if str(def_id).lower() == "new":
        curr_items = list(store_data.get("items") or [])
        curr_items.extend(items_to_add)
        store_data["items"] = curr_items
        store_data["cnt_items"] = len(curr_items)
        return notify_success(f"Đã thêm {len(items_to_add)} template."), store_data, False

    # Nếu sửa bộ đã có
    res = add_batch_def_items(ctx, int(def_id), items_to_add)
    if not res.ok:
        return notify_error(res.message or "Không thêm được template."), dash.no_update, True
    refreshed = get_batch_def(ctx, int(def_id))
    if not refreshed.ok:
        return notify_error(refreshed.message or "Không tải lại được bộ."), dash.no_update, True
    return notify_success(f"Đã thêm {len(items_to_add)} template vào bộ."), refreshed.data, False


@callback(
    Output("bdef-remove-modal", "opened"),
    Output("bdef-remove-target", "data"),
    Output("bdef-add-modal", "opened", allow_duplicate=True),
    Input({"type": "bdef-item-remove", "index": ALL}, "n_clicks"),
    Input("bdef-remove-modal-cancel", "n_clicks"),
    State("bdef-remove-modal", "opened"),
    prevent_initial_call=True,
)
def _open_remove_modal(remove_clicks: Any, _cancel: Any, opened: bool) -> tuple[bool, Any, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, dash.no_update, dash.no_update
    triggered = ctx_dash.triggered_id
    if triggered == "bdef-remove-modal-cancel":
        return False, dash.no_update, dash.no_update
    if isinstance(triggered, dict) and triggered.get("type") == "bdef-item-remove":
        if any(c for c in (remove_clicks or []) if c):
            return True, {"item_id": triggered["index"]}, False
    return False, dash.no_update, dash.no_update


@callback(
    Output("bdef-edit-notifications", "children", allow_duplicate=True),
    Output("bdef-edit-store", "data", allow_duplicate=True),
    Output("bdef-remove-modal", "opened", allow_duplicate=True),
    Input("bdef-remove-modal-confirm", "n_clicks"),
    State("bdef-remove-target", "data"),
    State("bdef-def-id", "data"),
    State("bdef-edit-store", "data"),
    prevent_initial_call=True,
)
def _confirm_remove_item(_n: Any, target: Any, def_id: Any, store_data: Any) -> tuple[Any, Any, bool]:
    if not _n:
        return dash.no_update, dash.no_update, False
    ctx = get_current_ctx()
    if ctx is None:
        return notify_error("Bạn cần đăng nhập."), dash.no_update, False
    if not target or not target.get("item_id"):
        return dash.no_update, dash.no_update, False

    target_id = target["item_id"]
    if str(def_id).lower() == "new":
        curr_items = [it for it in (store_data.get("items") or []) if it.get("id") != target_id]
        store_data["items"] = curr_items
        store_data["cnt_items"] = len(curr_items)
        return notify_success("Đã gỡ template."), store_data, False

    res = remove_batch_def_item(ctx, int(target_id))
    if not res.ok:
        return notify_error(res.message or "Không gỡ được template."), dash.no_update, False
    refreshed = get_batch_def(ctx, int(def_id))
    if not refreshed.ok:
        return notify_error(refreshed.message or "Không tải lại được bộ."), dash.no_update, False
    return notify_success("Đã gỡ template khỏi bộ."), refreshed.data, False


@callback(
    Output("bdef-edit-archive-modal", "opened"),
    Input("bdef-archive-btn", "n_clicks"),
    Input("bdef-edit-archive-modal-cancel", "n_clicks"),
    State("bdef-edit-archive-modal", "opened"),
    prevent_initial_call=True,
)
def _toggle_archive_modal(_open: Any, _cancel: Any, opened: bool) -> bool:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False
    triggered = ctx_dash.triggered_id
    if triggered == "bdef-edit-archive-modal-cancel":
        return False
    if triggered == "bdef-archive-btn" and bool(_open):
        return True
    return False


@callback(
    Output("bdef-edit-notifications", "children", allow_duplicate=True),
    Output("bdef-edit-store", "data", allow_duplicate=True),
    Output("bdef-edit-archive-modal", "opened", allow_duplicate=True),
    Input("bdef-edit-archive-modal-confirm", "n_clicks"),
    Input("bdef-activate-btn", "n_clicks"),
    State("bdef-def-id", "data"),
    prevent_initial_call=True,
)
def _run_def_action(_confirm: Any, _activate: Any, def_id: Any) -> tuple[Any, Any, bool]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered or str(def_id).lower() == "new":
        return dash.no_update, dash.no_update, False
    triggered = ctx_dash.triggered_id
    ctx = get_current_ctx()
    if ctx is None:
        return notify_error("Bạn cần đăng nhập."), dash.no_update, False
    def_id_int = int(def_id)
    if triggered == "bdef-activate-btn" and bool(_activate):
        res = activate_batch_def(ctx, def_id_int)
        action_name = "kích hoạt"
    elif triggered == "bdef-edit-archive-modal-confirm" and bool(_confirm):
        res = archive_batch_def(ctx, def_id_int)
        action_name = "lưu trữ"
    else:
        return dash.no_update, dash.no_update, False
    if not res.ok:
        return notify_error(res.message or f"Không {action_name} được bộ."), dash.no_update, False
    refreshed = get_batch_def(ctx, def_id_int)
    if not refreshed.ok:
        return notify_error(refreshed.message or "Không tải lại được bộ."), dash.no_update, False
    return notify_success(f"Đã {action_name} bộ đối soát thành công."), refreshed.data, False
