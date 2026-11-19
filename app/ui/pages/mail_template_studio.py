"""Page Mail Template Studio: Trình thiết kế email kéo thả và quản lý đa phiên bản.

Tuân thủ thiết kế Fluent Compact, Master-Detail 3 vùng:
1. Panel Trái: Thư viện 10 loại component + Biến sự kiện (Tokens) + Scenario test.
2. Panel Giữa: Canvas email mô phỏng hộp thư, hỗ trợ Desktop (600px) / Mobile (375px),
   chế độ Chỉnh sửa (Editor) và Xem trước (Live Preview).
3. Panel Phải: Bảng thuộc tính component (Nội dung, Giao diện, Điều kiện hiển thị).
"""

from __future__ import annotations

import copy
import json
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import (
    ALL,
    Input,
    Output,
    State,
    callback,
    clientside_callback,
    dcc,
    html,
    no_update,
)
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.engine.mail_event_registry import (
    get_sample_payload,
    list_event_definitions,
)
from app.engine.mail_renderer import (
    evaluate_condition,
    resolve_tokens,
    validate_design,
)
from app.engine.mail_token_inspector import (
    get_available_pages,
    get_mock_payload_for_page,
    get_table_columns_options_for_page,
    introspect_tokens_for_page,
)
from app.services.mail_template_studio import (
    activate_version,
    create_mail_template,
    get_mail_template_detail,
    list_mail_templates,
    save_draft_version,
)
from app.services.mail_template_studio import (
    test_send_template as exec_test_send_template,
)
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.empty_state import empty_state
from app.ui.components.notification import notify_error, notify_success

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/mail-template-studio",
        title="Mail Template Studio — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "mail_template_studio"

COMPONENT_TYPES: list[tuple[str, str, str]] = [
    ("header", "lucide:heading", "Tiêu đề (Header)"),
    ("text", "lucide:type", "Đoạn văn (Text)"),
    ("indicator", "lucide:disc", "Chỉ báo (Indicator)"),
    ("info", "lucide:layout-list", "Thông tin (Info)"),
    ("kpi", "lucide:bar-chart-2", "Chỉ số (KPI)"),
    ("table", "lucide:table", "Bảng dữ liệu (Table)"),
    ("alert", "lucide:alert-triangle", "Cảnh báo (Alert)"),
    ("button", "lucide:external-link", "Nút liên kết (Button)"),
    ("divider", "lucide:minus", "Đường kẻ (Divider)"),
    ("spacer", "lucide:move-vertical", "Khoảng cách (Spacer)"),
    ("footer", "lucide:align-left", "Chân trang (Footer)"),
]

TYPE_LABEL_MAP = {c[0]: c[2] for c in COMPONENT_TYPES}


def _make_block(block_type: str, next_id: int) -> dict[str, Any]:
    """Khởi tạo một block component mới với giá trị mặc định chuẩn."""
    text_defaults = {
        "header": "ReconHub | Thông báo nghiệp vụ",
        "text": "Xin chào {{actor.name}},\nNội dung thông báo kết quả xử lý nghiệp vụ.",
        "indicator": "● Hoàn tất xử lý: {{items_count}} bản ghi",
        "info": "Thông tin phiên làm việc",
        "kpi": "Thống kê kết quả",
        "table": "Bảng dữ liệu chi tiết",
        "alert": "Cảnh báo: Có {{summary.failed}} mục phát sinh lỗi cần lưu ý.",
        "button": "Mở liên kết đối tượng",
        "footer": "Email tự động từ ReconHub. Vui lòng không trả lời thư này.",
        "divider": "",
        "spacer": "",
    }
    block: dict[str, Any] = {
        "id": next_id,
        "type": block_type,
        "text": text_defaults.get(block_type, ""),
        "color": (
            "#1e3a5f"
            if block_type == "header"
            else "#b54708"
            if block_type == "alert"
            else "#047857"
            if block_type == "indicator"
            else "#ffffff"
            if block_type == "button"
            else "#26354a"
        ),
        "bg": (
            "#fff4e5"
            if block_type == "alert"
            else "#ecfdf5"
            if block_type == "indicator"
            else "#2563eb"
            if block_type == "button"
            else "#ffffff"
        ),
        "size": 20 if block_type == "header" else 13 if block_type in ("button", "indicator") else 14,
        "pad_top": 12 if block_type == "spacer" else 8 if block_type == "indicator" else 16,
        "pad_bottom": 12 if block_type == "spacer" else 8 if block_type == "indicator" else 16,
        "pad_left": 24,
        "pad_right": 24,
        "align": "center" if block_type == "button" else "left",
        "condition": "errors" if block_type == "alert" else "always",
        "limit": 5,
        "url": "links.result",
        "columns": ["name", "status", "detail"],
        "table_scope": "all",
    }
    if block_type == "button":
        block["button_shape"] = "rounded"
        block["button_width"] = "auto"
    elif block_type == "indicator":
        block["indicator_type"] = "dot"
        block["indicator_shape"] = "round"
        block["indicator_color"] = "#047857"
        block["border_color"] = "#a7f3d0"
    return block


def _render_canvas_blocks(
    blocks: list[dict[str, Any]],
    selected_id: int | None,
    scenario_data: dict[str, Any],
    view_mode: str,
) -> list[Any]:
    """Render danh sách các block trên Canvas theo chế độ Chỉnh sửa hoặc Xem trước."""
    rendered_elements: list[Any] = []

    for idx, b in enumerate(blocks):
        b_id = b.get("id")
        b_type = b.get("type", "text")
        b_text = b.get("text", "")
        cond = b.get("condition", "always")
        is_visible = evaluate_condition(cond, scenario_data)

        # Chế độ Xem trước: ẩn hoàn toàn các block không thỏa điều kiện
        if view_mode == "preview" and not is_visible:
            continue

        resolved_text = resolve_tokens(b_text, scenario_data, escape_html=False)
        pad_top = b.get("pad_top", b.get("pad", 16))
        pad_bottom = b.get("pad_bottom", b.get("pad", 16))
        pad_left = b.get("pad_left", 24)
        pad_right = b.get("pad_right", 24)

        inner_content: Any = None
        if b_type == "divider":
            inner_content = dmc.Divider(color="#dce3ed", my="xs")
        elif b_type == "spacer":
            inner_content = html.Div(style={"height": f"{max(8, pad_top)}px"})
        elif b_type == "button":
            btn_color = b.get("color", "#ffffff")
            btn_bg = b.get("bg", "#2563eb")
            b_shape = b.get("button_shape", "rounded")
            if b_shape == "round":
                b_radius = "24px"
            elif b_shape == "square":
                b_radius = "0px"
            else:
                b_radius = "6px"

            b_width = b.get("button_width", "auto")
            is_full = b_width == "full"
            is_light_bg = str(btn_bg).lower() in ("#ffffff", "#fff")
            border_css = "1px solid #cbd5e1" if is_light_bg else "none"
            box_shadow = "0 1px 3px rgba(0,0,0,0.08)" if is_light_bg else "0 1px 2px rgba(0,0,0,0.05)"

            inner_content = html.Div(
                html.Span(
                    resolved_text,
                    style={
                        "display": "block" if is_full else "inline-block",
                        "width": "100%" if is_full else "auto",
                        "backgroundColor": btn_bg,
                        "color": btn_color,
                        "borderRadius": b_radius,
                        "padding": "10px 24px",
                        "fontSize": f"{b.get('size', 13)}px",
                        "fontWeight": "600",
                        "border": border_css,
                        "boxShadow": box_shadow,
                        "textAlign": "center",
                        "cursor": "pointer",
                        "boxSizing": "border-box",
                        "transition": "all 0.15s ease",
                    },
                ),
                style={
                    "textAlign": b.get("align", "center"),
                    "width": "100%",
                },
            )
        elif b_type == "header":
            inner_content = dcc.Markdown(
                resolved_text,
                dangerously_allow_html=True,
                className="mail-canvas-markdown",
                style={
                    "fontSize": f"{b.get('size', 20)}px",
                    "fontWeight": "700",
                    "color": b.get("color", "#1e3a5f"),
                    "lineHeight": "1.3",
                },
            )
        elif b_type == "footer":
            inner_content = dcc.Markdown(
                resolved_text,
                dangerously_allow_html=True,
                className="mail-canvas-markdown",
                style={
                    "fontSize": f"{b.get('size', 11)}px",
                    "color": b.get("color", "#64748b"),
                    "borderTop": "1px solid #e5eaf1",
                    "paddingTop": "10px",
                },
            )
        elif b_type == "alert":
            alert_col = b.get("color", "#b54708")
            alert_bg = b.get("bg", "#fff4e5")
            border_col = b.get("border_color") or alert_col
            inner_content = dmc.Paper(
                dcc.Markdown(
                    resolved_text,
                    dangerously_allow_html=True,
                    className="mail-canvas-markdown",
                    style={
                        "fontSize": f"{b.get('size', 14)}px",
                        "color": alert_col,
                        "fontWeight": "500",
                    },
                ),
                p="sm",
                radius="sm",
                bg=alert_bg,
                style={"borderLeft": f"4px solid {border_col}"},
            )
        elif b_type == "kpi":
            lbl1 = str(b.get("kpi1_label") or "Tổng số")
            val1 = (
                scenario_data.get("summary.total")
                or scenario_data.get("summary_total")
                or scenario_data.get("items_count")
                or scenario_data.get("total")
                or 0
            )
            lbl2 = str(b.get("kpi2_label") or "Thành công")
            val2 = (
                scenario_data.get("summary.success")
                or scenario_data.get("summary_success")
                or scenario_data.get("success_count")
                or 0
            )
            lbl3 = str(b.get("kpi3_label") or "Có lỗi")
            val3 = (
                scenario_data.get("summary.failed")
                or scenario_data.get("summary_failed")
                or scenario_data.get("failed_count")
                or scenario_data.get("errors_count")
                or 0
            )
            inner_content = dmc.Stack(
                [
                    dmc.Text(
                        resolved_text,
                        fw=600,
                        size=f"{b.get('size', 14)}px",
                        c=b.get("color", "#26354a"),
                    ),
                    dmc.SimpleGrid(
                        cols=3,
                        spacing="xs",
                        children=[
                            dmc.Paper(
                                dmc.Stack(
                                    [
                                        dmc.Text(lbl1, size="11px", c="dimmed"),
                                        dmc.Text(str(val1), fw=700, size="20px", c="#1e3a5f"),
                                    ],
                                    gap=2,
                                    align="center",
                                ),
                                p="xs",
                                radius="sm",
                                bg="#f3f6fa",
                            ),
                            dmc.Paper(
                                dmc.Stack(
                                    [
                                        dmc.Text(lbl2, size="11px", c="green"),
                                        dmc.Text(str(val2), fw=700, size="20px", c="#047857"),
                                    ],
                                    gap=2,
                                    align="center",
                                ),
                                p="xs",
                                radius="sm",
                                bg="#ecfdf5",
                            ),
                            dmc.Paper(
                                dmc.Stack(
                                    [
                                        dmc.Text(lbl3, size="11px", c="red"),
                                        dmc.Text(str(val3), fw=700, size="20px", c="#b91c1c"),
                                    ],
                                    gap=2,
                                    align="center",
                                ),
                                p="xs",
                                radius="sm",
                                bg="#fef2f2",
                            ),
                        ],
                    ),
                ],
                gap=8,
            )
        elif b_type == "table":
            raw_items = (
                scenario_data.get(b.get("data_key", ""))
                or scenario_data.get("items")
                or scenario_data.get("batch.items")
                or scenario_data.get("rows")
                or scenario_data.get("data")
                or scenario_data.get("files_list")
                or []
            )
            if isinstance(raw_items, (list, tuple)) and raw_items and isinstance(raw_items[0], str):
                items = [{"name": str(s), "status": "Đính kèm", "detail": "Hoàn tất"} for s in raw_items]
            elif isinstance(raw_items, list):
                items = raw_items
            else:
                items = []

            table_scope = b.get("table_scope", "all")
            if table_scope in ("target_only", "single_user"):
                target_uname = scenario_data.get("user.username") or scenario_data.get("username")
                if target_uname:
                    matched = [
                        it
                        for it in items
                        if isinstance(it, dict) and str(it.get("username", "")).lower() == str(target_uname).lower()
                    ]
                    if matched:
                        items = matched
                    else:
                        items = items[:1] if items else []
                elif items:
                    items = items[:1]

            limit = int(b.get("limit", 5))
            cols = b.get("columns") or ["name", "status", "detail"]
            if items and isinstance(items[0], dict):
                item_keys = set(items[0].keys())
                if not any(c in item_keys for c in cols):
                    cols = [
                        c
                        for c in [
                            "username",
                            "full_name",
                            "email",
                            "roles",
                            "is_active",
                            "code",
                            "name",
                            "status",
                            "detail",
                        ]
                        if c in item_keys
                    ] or list(item_keys)[:3]

            from app.engine.mail_token_inspector import COLUMN_LABELS

            def _resolve_canvas_col_label(c_name: str) -> str:
                up = c_name.upper()
                if up in COLUMN_LABELS:
                    return COLUMN_LABELS[up]
                fb = {
                    "name": "Tên",
                    "status": "Trạng thái",
                    "detail": "Chi tiết",
                    "filename": "Tệp tin",
                    "rows": "Số dòng",
                    "roles": "Vai trò",
                }
                return fb.get(c_name.lower(), c_name.replace("_", " ").title())

            headers = [
                html.Th(
                    _resolve_canvas_col_label(c),
                    style={
                        "textAlign": "left",
                        "padding": "6px",
                        "backgroundColor": "#f2f5f9",
                        "fontSize": "11px",
                    },
                )
                for c in cols
            ]
            rows = []
            for it in items[:limit]:
                tds = [
                    html.Td(
                        str(it.get(c, "")),
                        style={
                            "padding": "6px",
                            "borderBottom": "1px solid #e5eaf1",
                            "fontSize": "11px",
                        },
                    )
                    for c in cols
                ]
                rows.append(html.Tr(tds))

            inner_content = dmc.Stack(
                [
                    dmc.Text(
                        resolved_text,
                        fw=600,
                        size=f"{b.get('size', 14)}px",
                        c=b.get("color", "#26354a"),
                    ),
                    html.Table(
                        [html.Thead(html.Tr(headers)), html.Tbody(rows)],
                        style={"width": "100%", "borderCollapse": "collapse"},
                    )
                    if rows
                    else dmc.Text(
                        "Không có mục cần kiểm tra trong dữ liệu hiện tại.", size="xs", c="dimmed"
                    ),
                ],
                gap=6,
            )
        elif b_type == "info":
            inner_content = dmc.Stack(
                [
                    dmc.Text(
                        resolved_text,
                        fw=600,
                        size=f"{b.get('size', 14)}px",
                        c=b.get("color", "#26354a"),
                    ),
                    dmc.Paper(
                        dmc.Stack(
                            [
                                dmc.Text(
                                    f"Kỳ: {scenario_data.get('batch.period', '—')}", size="xs"
                                ),
                                dmc.Text(
                                    f"Người chạy: {scenario_data.get('actor.name', '—')}",
                                    size="xs",
                                ),
                                dmc.Text(
                                    f"Mã phiên: {scenario_data.get('batch.run_code', '—')}",
                                    size="xs",
                                ),
                            ],
                            gap=4,
                        ),
                        p="xs",
                        radius="sm",
                        bg="#f8fafc",
                    ),
                ],
                gap=6,
            )
        elif b_type == "indicator":
            ind_type = b.get("indicator_type", "dot")
            ind_col = b.get("color", "#047857")
            ind_bg = b.get("bg", "#ecfdf5")
            ind_shape = b.get("indicator_shape", "round")
            ind_radius = "50%" if ind_shape == "round" else ("4px" if ind_shape == "rounded" else "0px")
            border_col = b.get("border_color", ind_col)

            if ind_type == "bar":
                inner_content = html.Div(
                    dcc.Markdown(
                        resolved_text,
                        dangerously_allow_html=True,
                        className="mail-canvas-markdown",
                        style={
                            "fontSize": f"{b.get('size', 13)}px",
                            "color": ind_col,
                            "fontWeight": "600",
                        },
                    ),
                    style={
                        "borderLeft": f"4px solid {ind_col}",
                        "backgroundColor": ind_bg,
                        "padding": "8px 12px",
                        "borderRadius": "0 4px 4px 0",
                    },
                )
            elif ind_type == "badge":
                inner_content = html.Div(
                    html.Span(
                        resolved_text,
                        style={
                            "display": "inline-block",
                            "padding": "4px 12px",
                            "borderRadius": ind_radius,
                            "backgroundColor": ind_bg,
                            "color": ind_col,
                            "border": f"1px solid {border_col}",
                            "fontSize": f"{b.get('size', 13)}px",
                            "fontWeight": "600",
                        },
                    ),
                    style={"textAlign": b.get("align", "left")},
                )
            else:  # dot
                inner_content = html.Div(
                    [
                        html.Span(
                            style={
                                "display": "inline-block",
                                "width": "10px",
                                "height": "10px",
                                "borderRadius": ind_radius,
                                "backgroundColor": ind_col,
                                "marginRight": "8px",
                                "verticalAlign": "middle",
                            }
                        ),
                        html.Span(
                            resolved_text,
                            style={
                                "fontSize": f"{b.get('size', 14)}px",
                                "color": b.get("color", "#26354a"),
                                "verticalAlign": "middle",
                            },
                        ),
                    ],
                    style={"textAlign": b.get("align", "left")},
                )
        else:
            has_indicator = bool(b.get("has_indicator", False))
            if has_indicator:
                ind_type = b.get("indicator_type", "dot")
                ind_col = b.get("indicator_color", "#2563eb")
                ind_shape = b.get("indicator_shape", "round")
                ind_radius = "50%" if ind_shape == "round" else ("4px" if ind_shape == "rounded" else "0px")
                ind_label = resolve_tokens(b.get("indicator_text", ""), scenario_data, escape_html=False)

                if ind_type == "bar":
                    inner_content = html.Div(
                        dcc.Markdown(
                            resolved_text,
                            dangerously_allow_html=True,
                            className="mail-canvas-markdown",
                            style={
                                "fontSize": f"{b.get('size', 14)}px",
                                "color": b.get("color", "#26354a"),
                                "lineHeight": "1.6",
                            },
                        ),
                        style={
                            "borderLeft": f"4px solid {ind_col}",
                            "paddingLeft": "12px",
                        },
                    )
                elif ind_type == "badge":
                    badge_span = html.Span(
                        ind_label or "THÔNG BÁO",
                        style={
                            "display": "inline-block",
                            "padding": "2px 8px",
                            "borderRadius": ind_radius,
                            "backgroundColor": f"{ind_col}1a",
                            "color": ind_col,
                            "border": f"1px solid {ind_col}",
                            "fontSize": "11px",
                            "fontWeight": "700",
                            "marginRight": "8px",
                            "verticalAlign": "middle",
                        },
                    )
                    inner_content = html.Div(
                        [
                            badge_span,
                            dcc.Markdown(
                                resolved_text,
                                dangerously_allow_html=True,
                                className="mail-canvas-markdown",
                                style={
                                    "fontSize": f"{b.get('size', 14)}px",
                                    "color": b.get("color", "#26354a"),
                                    "lineHeight": "1.6",
                                    "display": "inline",
                                },
                            ),
                        ]
                    )
                else:  # dot
                    dot_span = html.Span(
                        style={
                            "display": "inline-block",
                            "width": "10px",
                            "height": "10px",
                            "borderRadius": ind_radius,
                            "backgroundColor": ind_col,
                            "marginRight": "8px",
                            "verticalAlign": "middle",
                        }
                    )
                    inner_content = html.Div(
                        [
                            dot_span,
                            dcc.Markdown(
                                resolved_text,
                                dangerously_allow_html=True,
                                className="mail-canvas-markdown",
                                style={
                                    "fontSize": f"{b.get('size', 14)}px",
                                    "color": b.get("color", "#26354a"),
                                    "lineHeight": "1.6",
                                    "display": "inline",
                                },
                            ),
                        ]
                    )
            else:
                inner_content = dcc.Markdown(
                    resolved_text,
                    dangerously_allow_html=True,
                    className="mail-canvas-markdown",
                    style={
                        "fontSize": f"{b.get('size', 14)}px",
                        "color": b.get("color", "#26354a"),
                        "lineHeight": "1.6",
                        "whiteSpace": "pre-wrap",
                    },
                )

        if view_mode == "edit":
            is_selected = b_id == selected_id
            border_style = "2px solid #2563eb" if is_selected else "1px solid #e2e8f0"
            opacity_style = "1" if is_visible else "0.4"

            toolbar = dmc.Group(
                [
                    dmc.Group(
                        [
                            DashIconify(
                                icon="lucide:grip-vertical",
                                width=14,
                                color="#94a3b8",
                                className="mail-drag-handle",
                                style={"cursor": "grab"},
                            ),
                            dmc.Badge(
                                TYPE_LABEL_MAP.get(b_type, b_type),
                                size="xs",
                                variant="light",
                                color="blue" if is_selected else "gray",
                            ),
                        ],
                        gap=4,
                        align="center",
                    ),
                    dmc.Group(
                        [
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:arrow-up", width=12),
                                id={"type": "mail-block-btn", "action": "up", "index": b_id},
                                size="xs",
                                variant="subtle",
                                disabled=(idx == 0),
                                n_clicks=0,
                            ),
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:arrow-down", width=12),
                                id={"type": "mail-block-btn", "action": "down", "index": b_id},
                                size="xs",
                                variant="subtle",
                                disabled=(idx == len(blocks) - 1),
                                n_clicks=0,
                            ),
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:copy", width=12),
                                id={"type": "mail-block-btn", "action": "copy", "index": b_id},
                                size="xs",
                                variant="subtle",
                                n_clicks=0,
                            ),
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:trash-2", width=12),
                                id={"type": "mail-block-btn", "action": "del", "index": b_id},
                                size="xs",
                                variant="subtle",
                                color="red",
                                n_clicks=0,
                            ),
                        ],
                        gap=2,
                    ),
                ],
                justify="space-between",
                align="center",
                p="4px 8px",
                style={"backgroundColor": "#f8fafc", "borderBottom": "1px solid #e2e8f0"},
            )

            hidden_hint = None
            if not is_visible:
                hidden_hint = dmc.Text(
                    "(Ẩn trong dữ liệu thử nghiệm hiện tại theo điều kiện hiển thị)",
                    size="10px",
                    c="orange",
                    mt=4,
                )

            # Khối click để chọn (Sử dụng html.Div với n_clicks để Dash nhận diện sự kiện 100%)
            card_bg = "#ffffff" if b_type == "button" else b.get("bg", "#ffffff")
            block_card = dmc.Paper(
                [
                    toolbar,
                    html.Div(
                        [inner_content, hidden_hint],
                        id={"type": "mail-block-select", "index": b_id},
                        n_clicks=0,
                        style={
                            "cursor": "pointer",
                            "textAlign": b.get("align", "left"),
                            "padding": f"{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px",
                        },
                    ),
                ],
                radius="sm",
                withBorder=True,
                mb="xs",
                style={
                    "border": border_style,
                    "opacity": opacity_style,
                    "backgroundColor": card_bg,
                    "boxShadow": "0 1px 3px rgba(0,0,0,0.05)" if is_selected else "none",
                },
            )
            rendered_elements.append(
                html.Div(
                    block_card,
                    className="mail-drag-item",
                    **{  # type: ignore[arg-type]
                        "data-block-id": str(b_id),
                        "data-block-idx": str(idx),
                    },
                )
            )
        else:
            card_bg = "#ffffff" if b_type == "button" else b.get("bg", "#ffffff")
            rendered_elements.append(
                dmc.Box(
                    inner_content,
                    style={
                        "backgroundColor": card_bg,
                        "textAlign": b.get("align", "left"),
                        "padding": f"{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px",
                    },
                )
            )

    return rendered_elements


def _render_tokens_badges(variables: Any) -> Any:
    """Render danh sách token badges từ danh mục biến hoặc từ introspected tokens.

    Phân chia thành 2 Tab rõ ràng: Trường bảng & Hệ thống, có cuộn độc lập và giữ nguyên chữ thường.
    """
    if isinstance(variables, dict) and ("table_fields" in variables or "system_fields" in variables):
        t_fields = variables.get("table_fields", [])
        s_fields = variables.get("system_fields", [])

        def _make_badge(var: dict[str, Any]) -> Any:
            k = var.get("key", "")
            lbl = var.get("label", "")
            d_type = var.get("data_type", "string")
            is_link = "link" in k
            return html.Span(
                dmc.Badge(
                    f"{{{{{k}}}}}",
                    size="xs",
                    variant="outline",
                    color="blue" if is_link else ("teal" if var.get("category") == "table" else "gray"),
                    tt="none",
                    style={"cursor": "pointer", "margin": "2px", "textTransform": "none", "fontSize": "11px"},
                ),
                id={"type": "mail-token-add", "token": k},
                title=f"{lbl} ({d_type}) — Bấm để chèn",
                n_clicks=0,
                style={"cursor": "pointer", "display": "inline-block"},
            )

        t_badges = [_make_badge(v) for v in t_fields]
        s_badges = [_make_badge(v) for v in s_fields]

        return dmc.Tabs(
            [
                dmc.TabsList(
                    [
                        dmc.TabsTab(
                            f"Trường bảng ({len(t_badges)})",
                            value="table",
                            leftSection=DashIconify(icon="lucide:table", width=13, color="#0d9488"),
                            style={"fontSize": "11px", "padding": "4px 8px"},
                        ),
                        dmc.TabsTab(
                            f"Hệ thống ({len(s_badges)})",
                            value="system",
                            leftSection=DashIconify(icon="lucide:settings", width=13, color="#64748b"),
                            style={"fontSize": "11px", "padding": "4px 8px"},
                        ),
                    ],
                    mb=6,
                ),
                dmc.TabsPanel(
                    html.Div(
                        dmc.Group(t_badges, gap=4)
                        if t_badges
                        else dmc.Text("Không có trường dữ liệu bảng.", size="xs", c="dimmed"),
                        style={
                            "maxHeight": "calc(100vh - 430px)",
                            "minHeight": "180px",
                            "overflowY": "auto",
                            "paddingRight": "4px",
                        },
                    ),
                    value="table",
                ),
                dmc.TabsPanel(
                    html.Div(
                        dmc.Group(s_badges, gap=4)
                        if s_badges
                        else dmc.Text("Không có trường hệ thống.", size="xs", c="dimmed"),
                        style={
                            "maxHeight": "calc(100vh - 430px)",
                            "minHeight": "180px",
                            "overflowY": "auto",
                            "paddingRight": "4px",
                        },
                    ),
                    value="system",
                ),
            ],
            value="table",
            color="teal",
            variant="outline",
        )

    badges = []
    for var in (variables or []):
        k = var.get("key", "")
        lbl = var.get("label", "")
        d_type = var.get("data_type", "string")
        badges.append(
            html.Span(
                dmc.Badge(
                    f"{{{{{k}}}}}",
                    size="xs",
                    variant="outline",
                    color="blue" if "link" in k else "gray",
                    tt="none",
                    style={"cursor": "pointer", "margin": "2px", "textTransform": "none", "fontSize": "11px"},
                ),
                id={"type": "mail-token-add", "token": k},
                title=f"{lbl} ({d_type}) — Bấm để chèn",
                n_clicks=0,
                style={"cursor": "pointer", "display": "inline-block"},
            )
        )
    return html.Div(
        dmc.Group(badges, gap=4)
        if badges
        else dmc.Text("Không có biến nào cho sự kiện này.", size="xs", c="dimmed"),
        style={"maxHeight": "calc(100vh - 430px)", "minHeight": "180px", "overflowY": "auto", "paddingRight": "4px"},
    )


def layout(**kwargs: Any) -> Any:
    """Giao diện Master-Detail 3 Panel của Mail Template Studio."""
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập để truy cập Mail Template Studio.", tone="crit")

    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="mail-studio-forbidden-loc", href=gate),
                alert_box("Bạn không có quyền truy cập màn hình này.", tone="crit"),
            ]
        )

    # Nạp danh sách template có sẵn
    tpl_list_res = list_mail_templates(ctx)
    templates = (
        tpl_list_res.data
        if tpl_list_res.ok and isinstance(tpl_list_res.data, list)
        else []
    )

    selected_tmpl_id = templates[0]["id"] if templates else None
    init_detail = None
    if selected_tmpl_id:
        det_res = get_mail_template_detail(ctx, selected_tmpl_id)
        if det_res.ok and isinstance(det_res.data, dict):
            init_detail = det_res.data

    init_cur_v = init_detail.get("current_version") if init_detail else None
    init_design = init_cur_v.get("design_json") if init_cur_v else {"blocks": []}
    init_blocks = init_design.get("blocks", []) if isinstance(init_design, dict) else []
    init_subject = init_cur_v.get("subject_template", "") if init_cur_v else ""
    init_preheader = init_cur_v.get("preheader_template", "") if init_cur_v else ""
    init_v_id = init_cur_v.get("id") if init_cur_v else None
    init_v_no = init_cur_v.get("version_no", 1) if init_cur_v else 1
    init_status = init_cur_v.get("status", "DRAFT") if init_cur_v else "DRAFT"
    init_event_code = init_detail.get("template", {}).get("event_code", "USER_CREATED") if init_detail else "USER_CREATED"
    init_menu_code = init_detail.get("template", {}).get("menu_code", "user") if init_detail else "user"

    # Ưu tiên nạp tokens tự động theo Page (Dynamic Token Introspection)
    init_tokens_data = introspect_tokens_for_page(init_menu_code)
    initial_tokens_badges = _render_tokens_badges(init_tokens_data)

    init_selected_block_id = init_blocks[0].get("id") if init_blocks else None

    init_state = {
        "template_id": selected_tmpl_id,
        "event_code": init_event_code,
        "menu_code": init_menu_code,
        "version_id": init_v_id,
        "version_no": init_v_no,
        "status": init_status,
        "selected_block_id": init_selected_block_id,
        "scenario": "success",
        "device_mode": "desktop",
        "view_mode": "edit",
        "subject": init_subject,
        "preheader": init_preheader,
        "design_json": init_design,
        "dirty": False,
        "seq": max([b.get("id", 0) for b in init_blocks] + [10]),
    }

    event_options = [
        {"value": e.code, "label": f"{e.label} ({e.code})"}
        for e in list_event_definitions()
    ]

    template_select_data = [
        {
            "value": str(t["id"]),
            "label": f"{t['name']} [{t['active_status']} v{t['active_version_no'] or '1'}]",
        }
        for t in templates
    ]

    return dmc.Box(
        [
            # Stores quản lý state
            dcc.Store(id="mail-studio-state", data=init_state),
            dcc.Store(id="mail-studio-sync-trigger", data=1),
            dcc.Store(id="mail-studio-reorder-store"),
            dcc.Download(id="mail-studio-download"),
            html.Div(id="mail-studio-notifications"),

            # Top Command Bar
            dmc.Paper(
                dmc.Group(
                    [
                        dmc.Group(
                            [
                                DashIconify(icon="lucide:mail", width=22, color="#2563eb"),
                                dmc.Stack(
                                    [
                                        dmc.Text(
                                            "Mail Template Studio",
                                            fw=700,
                                            size="md",
                                            c="#1e293b",
                                        ),
                                        dmc.Text(
                                            "Thiết kế email kéo thả tương thích đa nền tảng",
                                            size="xs",
                                            c="dimmed",
                                        ),
                                    ],
                                    gap=0,
                                ),
                            ],
                            gap="xs",
                        ),
                        dmc.Group(
                            [
                                dmc.Select(
                                    id="mail-studio-template-select",
                                    data=template_select_data,
                                    value=str(selected_tmpl_id) if selected_tmpl_id else None,
                                    style={"width": "300px"},
                                    size="xs",
                                    placeholder="Chọn mẫu email để chỉnh sửa...",
                                ),
                                dmc.Button(
                                    "Tạo mẫu mới",
                                    id="mail-studio-btn-open-create",
                                    variant="light",
                                    size="xs",
                                    leftSection=DashIconify(icon="lucide:plus", width=14),
                                    n_clicks=0,
                                ),
                                dmc.Badge(
                                    f"v{init_v_no} · {init_status}",
                                    id="mail-studio-badge-status",
                                    color="green" if init_status == "ACTIVE" else "orange",
                                    size="sm",
                                    variant="filled",
                                ),
                                dmc.Divider(orientation="vertical"),
                                dmc.Button(
                                    "Kiểm tra",
                                    id="mail-studio-btn-validate",
                                    variant="default",
                                    size="xs",
                                    leftSection=DashIconify(icon="lucide:check-circle", width=14),
                                    n_clicks=0,
                                ),
                                dmc.Button(
                                    "Gửi thử",
                                    id="mail-studio-btn-open-test",
                                    variant="default",
                                    size="xs",
                                    leftSection=DashIconify(icon="lucide:send", width=14),
                                    n_clicks=0,
                                ),
                                dmc.Button(
                                    "Lưu nháp",
                                    id="mail-studio-btn-save-draft",
                                    variant="default",
                                    size="xs",
                                    leftSection=DashIconify(icon="lucide:save", width=14),
                                    n_clicks=0,
                                ),
                                dmc.Button(
                                    "Kích hoạt",
                                    id="mail-studio-btn-activate",
                                    variant="filled",
                                    color="blue",
                                    size="xs",
                                    leftSection=DashIconify(icon="lucide:shield-check", width=14),
                                    n_clicks=0,
                                ),
                                dmc.ActionIcon(
                                    DashIconify(icon="lucide:download", width=15),
                                    id="mail-studio-btn-export-json",
                                    variant="default",
                                    size="sm",
                                    n_clicks=0,
                                    **{"aria-label": "Tải Design JSON"},
                                ),
                            ],
                            gap="xs",
                        ),
                    ],
                    justify="space-between",
                    align="center",
                ),
                p="xs",
                withBorder=True,
                radius="sm",
                mb="xs",
            ),

            # Bố cục 3 Panel
            dmc.Grid(
                [
                    # 1. Panel Trái: Thư viện component & Tokens
                    dmc.GridCol(
                        [
                            dmc.Paper(
                                dmc.Stack(
                                    [
                                        dmc.Group(
                                            [
                                                DashIconify(
                                                    icon="lucide:box", width=16, color="#2563eb"
                                                ),
                                                dmc.Text("Thư viện component", fw=600, size="sm"),
                                            ],
                                            gap="xs",
                                        ),
                                        dmc.Text(
                                            "Bấm vào component để thêm vào Canvas:",
                                            size="11px",
                                            c="dimmed",
                                        ),
                                        # Lưới 11 component (3 component trên 1 hàng)
                                        dmc.SimpleGrid(
                                            cols=3,
                                            spacing="xs",
                                            children=[
                                                html.Div(
                                                    dmc.Paper(
                                                        dmc.Stack(
                                                            [
                                                                DashIconify(
                                                                    icon=icon,
                                                                    width=15,
                                                                    color="#2563eb",
                                                                ),
                                                                dmc.Text(
                                                                    label.split(" (")[0],
                                                                    size="11px",
                                                                    fw=500,
                                                                    ta="center",
                                                                    style={"lineHeight": "1.2"},
                                                                ),
                                                            ],
                                                            gap=4,
                                                            align="center",
                                                            justify="center",
                                                        ),
                                                        p="6px 4px",
                                                        radius="sm",
                                                        withBorder=True,
                                                        style={
                                                            "cursor": "pointer",
                                                            "backgroundColor": "#ffffff",
                                                            "transition": "all 0.15s ease",
                                                            "minHeight": "52px",
                                                            "display": "flex",
                                                            "alignItems": "center",
                                                            "justifyContent": "center",
                                                        },
                                                    ),
                                                    id={
                                                        "type": "mail-tile-add",
                                                        "block_type": c_type,
                                                    },
                                                    n_clicks=0,
                                                    style={"cursor": "pointer"},
                                                )
                                                for c_type, icon, label in COMPONENT_TYPES
                                            ],
                                        ),
                                        dmc.Divider(my="xs"),
                                        # Danh mục biến dữ liệu
                                        dmc.Group(
                                            [
                                                DashIconify(
                                                    icon="lucide:code", width=16, color="#10b981"
                                                ),
                                                dmc.Text(
                                                    "Biến sự kiện (Tokens)", fw=600, size="sm"
                                                ),
                                            ],
                                            gap="xs",
                                        ),
                                        dmc.Group(
                                            [
                                                dmc.Select(
                                                    id="mail-studio-page-select",
                                                    placeholder="Chọn màn hình gửi thư...",
                                                    data=get_available_pages(),
                                                    value=init_menu_code,
                                                    size="xs",
                                                    style={"flex": 1},
                                                ),
                                                dmc.ActionIcon(
                                                    DashIconify(icon="lucide:database", width=15),
                                                    id="mail-studio-btn-fetch-tokens",
                                                    size="sm",
                                                    variant="light",
                                                    color="teal",
                                                    n_clicks=0,
                                                    style={"marginTop": "2px"},
                                                    **{"aria-label": "Quét lại toàn bộ token của bảng từ Page"},
                                                ),
                                            ],
                                            gap="xs",
                                            align="center",
                                        ),
                                        dmc.Text(
                                            "Bấm token để chèn ngay vào nội dung:",
                                            size="11px",
                                            c="dimmed",
                                        ),
                                        html.Div(
                                            initial_tokens_badges,
                                            id="mail-studio-tokens-container",
                                            style={"flex": 1, "overflowY": "auto", "minHeight": "200px"},
                                        ),
                                    ],
                                    gap=6,
                                    style={"flex": 1, "display": "flex", "flexDirection": "column"},
                                ),
                                p="xs",
                                withBorder=True,
                                radius="sm",
                                style={
                                    "height": "calc(100vh - 145px)",
                                    "maxHeight": "calc(100vh - 145px)",
                                    "overflowY": "auto",
                                    "display": "flex",
                                    "flexDirection": "column",
                                },
                            )
                        ],
                        span={"base": 12, "md": 3},
                    ),

                    # 2. Panel Giữa: Email Canvas
                    dmc.GridCol(
                        [
                            dmc.Paper(
                                dmc.Stack(
                                    [
                                        dmc.Group(
                                            [
                                                dmc.Group(
                                                    [
                                                        dmc.SegmentedControl(
                                                            id="mail-studio-device-toggle",
                                                            value="desktop",
                                                            data=[
                                                                {
                                                                    "value": "desktop",
                                                                    "label": "Desktop (600px)",
                                                                },
                                                                {
                                                                    "value": "mobile",
                                                                    "label": "Mobile (375px)",
                                                                },
                                                            ],
                                                            size="xs",
                                                        ),
                                                        dmc.Group(
                                                            [
                                                                dmc.Text("Nền ngoài:", size="xs", c="dimmed"),
                                                                dmc.SegmentedControl(
                                                                    id="mail-studio-canvas-bg-toggle",
                                                                    value=init_state.get("design_json", {}).get("canvasSettings", {}).get("bgColor", "#f3f5f9"),
                                                                    data=[
                                                                        {"value": "#f3f5f9", "label": "Xám nhẹ"},
                                                                        {"value": "#ffffff", "label": "Trắng tinh"},
                                                                    ],
                                                                    size="xs",
                                                                ),
                                                            ],
                                                            gap=4,
                                                            align="center",
                                                        ),
                                                    ],
                                                    gap="xs",
                                                    align="center",
                                                ),
                                                dmc.SegmentedControl(
                                                    id="mail-studio-mode-toggle",
                                                    value="edit",
                                                    data=[
                                                        {"value": "edit", "label": "Chỉnh sửa"},
                                                        {"value": "preview", "label": "Xem trước"},
                                                    ],
                                                    size="xs",
                                                ),
                                            ],
                                            justify="space-between",
                                            align="center",
                                        ),
                                        dmc.SimpleGrid(
                                            cols=2,
                                            spacing="xs",
                                            children=[
                                                dmc.TextInput(
                                                    id="mail-studio-subject-input",
                                                    label="Tiêu đề email (Subject)",
                                                    value=init_subject,
                                                    size="xs",
                                                ),
                                                dmc.TextInput(
                                                    id="mail-studio-preheader-input",
                                                    label="Preheader (văn bản xem trước hộp thư)",
                                                    value=init_preheader,
                                                    size="xs",
                                                ),
                                            ],
                                        ),
                                        dmc.Box(
                                            dmc.Box(
                                                id="mail-studio-canvas-content",
                                                style={
                                                    "maxWidth": "600px",
                                                    "margin": "0 auto",
                                                    "backgroundColor": "#ffffff",
                                                    "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
                                                    "borderRadius": "6px",
                                                    "overflow": "hidden",
                                                    "transition": "max-width 0.2s ease-in-out",
                                                },
                                            ),
                                            id="mail-studio-canvas-wrapper",
                                            p="md",
                                            style={
                                                "backgroundColor": init_state.get("design_json", {}).get("canvasSettings", {}).get("bgColor", "#f3f5f9"),
                                                "borderRadius": "6px",
                                                "flex": "1",
                                                "minHeight": "480px",
                                                "maxHeight": "calc(100vh - 275px)",
                                                "overflowY": "auto",
                                                "overflowX": "hidden",
                                                "transition": "background-color 0.2s ease-in-out",
                                            },
                                        ),
                                    ],
                                    gap="xs",
                                    style={"height": "100%"},
                                ),
                                p="sm",
                                withBorder=True,
                                radius="sm",
                                style={
                                    "height": "calc(100vh - 160px)",
                                    "minHeight": "680px",
                                    "display": "flex",
                                    "flexDirection": "column",
                                },
                            )
                        ],
                        span={"base": 12, "md": 6},
                    ),

                    # 3. Panel Phải: Bảng thuộc tính component (luôn hiện diện cố định các input)
                    dmc.GridCol(
                        [
                            dmc.Paper(
                                dmc.Stack(
                                    [
                                        dmc.Group(
                                            [
                                                DashIconify(
                                                    icon="lucide:sliders",
                                                    width=16,
                                                    color="#2563eb",
                                                ),
                                                dmc.Text(
                                                    "Thuộc tính component",
                                                    id="mail-studio-prop-title",
                                                    fw=600,
                                                    size="sm",
                                                ),
                                            ],
                                            gap="xs",
                                        ),
                                        dmc.Divider(mb="xs"),
                                        # Alert khi chưa có block
                                        html.Div(
                                            empty_state(
                                                title="Chưa chọn khối",
                                                description="Bấm vào một khối trên Canvas để tùy biến.",
                                            ),
                                            id="mail-studio-prop-empty-alert",
                                            style={"display": "none"},
                                        ),
                                        # Form chỉnh sửa thuộc tính
                                        dmc.Stack(
                                            [
                                                # Nội dung
                                                html.Div(
                                                    dmc.Textarea(
                                                        id="mail-studio-prop-text",
                                                        label="Nội dung / Nhãn",
                                                        description="Hỗ trợ chèn token từ danh mục bên trái",
                                                        value="",
                                                        autosize=True,
                                                        minRows=3,
                                                    ),
                                                    id="mail-studio-prop-text-wrap",
                                                ),
                                                # Cấu hình Chỉ báo (Indicator)
                                                html.Div(
                                                    dmc.Stack(
                                                        [
                                                            dmc.Divider(my="xs"),
                                                            dmc.Group(
                                                                [
                                                                    dmc.Text("Chỉ báo (Indicator)", size="xs", fw=600),
                                                                    dmc.Switch(
                                                                        id="mail-studio-prop-ind-enabled",
                                                                        size="xs",
                                                                        checked=False,
                                                                        label="Bật",
                                                                    ),
                                                                ],
                                                                justify="space-between",
                                                                align="center",
                                                            ),
                                                            html.Div(
                                                                dmc.Stack(
                                                                    [
                                                                        dmc.SegmentedControl(
                                                                            id="mail-studio-prop-ind-type",
                                                                            data=[
                                                                                {"value": "dot", "label": "Chấm tròn ●"},
                                                                                {"value": "bar", "label": "Thanh đứng ▍"},
                                                                                {"value": "badge", "label": "Huy hiệu"},
                                                                            ],
                                                                            value="dot",
                                                                            size="xs",
                                                                            fullWidth=True,
                                                                        ),
                                                                        dmc.SimpleGrid(
                                                                            cols=2,
                                                                            spacing="xs",
                                                                            children=[
                                                                                dmc.ColorInput(
                                                                                    id="mail-studio-prop-ind-color",
                                                                                    label="Màu chỉ báo",
                                                                                    value="#2563eb",
                                                                                    withEyeDropper=False,
                                                                                    popoverProps={"withinPortal": True},
                                                                                    size="xs",
                                                                                    swatches=[
                                                                                        "#2563eb",
                                                                                        "#059669",
                                                                                        "#d97706",
                                                                                        "#dc2626",
                                                                                        "#7c3aed",
                                                                                        "#475569",
                                                                                    ],
                                                                                    format="hex",
                                                                                ),
                                                                                dmc.Select(
                                                                                    id="mail-studio-prop-ind-shape",
                                                                                    label="Kiểu viền / Bo",
                                                                                    data=[
                                                                                        {"value": "round", "label": "Tròn (50%)"},
                                                                                        {"value": "rounded", "label": "Bo nhẹ (4px)"},
                                                                                        {"value": "square", "label": "Vuông (0px)"},
                                                                                    ],
                                                                                    value="round",
                                                                                    size="xs",
                                                                                ),
                                                                            ],
                                                                        ),
                                                                        html.Div(
                                                                            dmc.TextInput(
                                                                                id="mail-studio-prop-ind-text",
                                                                                label="Chữ trong huy hiệu",
                                                                                placeholder="vd: QUAN TRỌNG, THÀNH CÔNG...",
                                                                                size="xs",
                                                                            ),
                                                                            id="mail-studio-prop-ind-text-wrap",
                                                                        ),
                                                                    ],
                                                                    gap=6,
                                                                ),
                                                                id="mail-studio-prop-ind-options",
                                                            ),
                                                        ],
                                                        gap=4,
                                                    ),
                                                    id="mail-studio-prop-ind-wrap",
                                                    style={"display": "none"},
                                                ),
                                                # Đích đến URL an toàn
                                                html.Div(
                                                    dmc.Select(
                                                        id="mail-studio-prop-url",
                                                        label="Đích đến an toàn (Safe Link)",
                                                        description="Chỉ dùng liên kết hệ thống cho phép",
                                                        data=[
                                                            {
                                                                "value": "links.login",
                                                                "label": "links.login • Mở trang đăng nhập (/login)",
                                                            },
                                                            {
                                                                "value": "links.page",
                                                                "label": "links.page • Mở màn hình nghiệp vụ",
                                                            },
                                                            {
                                                                "value": "links.result",
                                                                "label": "links.result • Mở kết quả phiên chạy",
                                                            },
                                                            {
                                                                "value": "links.download",
                                                                "label": "links.download • Tải file kết xuất",
                                                            },
                                                            {
                                                                "value": "links.template",
                                                                "label": "links.template • Quản lý template",
                                                            },
                                                        ],
                                                        value="links.result",
                                                    ),
                                                    id="mail-studio-prop-url-wrap",
                                                    style={"display": "none"},
                                                ),
                                                # Cấu hình Nút liên kết (Hình dạng & Chiều rộng)
                                                html.Div(
                                                    dmc.Stack(
                                                        [
                                                            dmc.Select(
                                                                id="mail-studio-prop-btn-shape",
                                                                label="Hình dạng nút (Shape)",
                                                                description="Bo góc nhẹ, bo tròn hoặc vuông",
                                                                data=[
                                                                    {"value": "rounded", "label": "Bo góc (Rounded - 6px)"},
                                                                    {"value": "round", "label": "Bo tròn (Pill - 24px)"},
                                                                    {"value": "square", "label": "Vuông (Square - 0px)"},
                                                                ],
                                                                value="rounded",
                                                                size="xs",
                                                            ),
                                                            dmc.Box(
                                                                [
                                                                    dmc.Text("Độ rộng nút:", size="xs", fw=500, mb=4),
                                                                    dmc.SegmentedControl(
                                                                        id="mail-studio-prop-btn-width",
                                                                        data=[
                                                                            {"value": "auto", "label": "Tự co giãn"},
                                                                            {"value": "full", "label": "Toàn hàng"},
                                                                        ],
                                                                        value="auto",
                                                                        fullWidth=True,
                                                                        size="xs",
                                                                    ),
                                                                ]
                                                            ),
                                                        ],
                                                        gap=6,
                                                    ),
                                                    id="mail-studio-prop-btn-options-wrap",
                                                    style={"display": "none"},
                                                ),
                                                # Cấu hình Bảng dữ liệu
                                                html.Div(
                                                    dmc.Stack(
                                                        [
                                                            dmc.Box(
                                                                [
                                                                    dmc.Text("Phạm vi dữ liệu bảng:", size="xs", fw=500, mb=4),
                                                                    dmc.SegmentedControl(
                                                                        id="mail-studio-prop-table-scope",
                                                                        data=[
                                                                            {"value": "all", "label": "Tất cả danh sách user"},
                                                                            {"value": "target_only", "label": "Chỉ đích danh user đó"},
                                                                        ],
                                                                        value="all",
                                                                        fullWidth=True,
                                                                        size="xs",
                                                                    ),
                                                                ]
                                                            ),
                                                            dmc.NumberInput(
                                                                id="mail-studio-prop-limit",
                                                                label="Số dòng tối đa (1–20)",
                                                                min=1,
                                                                max=20,
                                                                value=5,
                                                            ),
                                                            dmc.Text(
                                                                "Cột hiển thị:",
                                                                size="xs",
                                                                fw=500,
                                                            ),
                                                            dmc.CheckboxGroup(
                                                                id="mail-studio-prop-columns",
                                                                value=[
                                                                    "name",
                                                                    "status",
                                                                    "detail",
                                                                ],
                                                                children=dmc.Stack(
                                                                    id="mail-studio-prop-columns-stack",
                                                                    children=[
                                                                        dmc.Checkbox(
                                                                            label="Tên Template",
                                                                            value="name",
                                                                            size="xs",
                                                                        ),
                                                                        dmc.Checkbox(
                                                                            label="Trạng thái",
                                                                            value="status",
                                                                            size="xs",
                                                                        ),
                                                                        dmc.Checkbox(
                                                                            label="Chi tiết",
                                                                            value="detail",
                                                                            size="xs",
                                                                        ),
                                                                    ],
                                                                    gap=4,
                                                                ),
                                                            ),
                                                        ],
                                                        gap=6,
                                                    ),
                                                    id="mail-studio-prop-table-wrap",
                                                    style={"display": "none"},
                                                ),
                                                # Cỡ chữ (px)
                                                dmc.NumberInput(
                                                    id="mail-studio-prop-size",
                                                    label="Cỡ chữ (px)",
                                                    min=10,
                                                    max=36,
                                                    value=14,
                                                ),
                                                # Khoảng cách đệm (Padding - px: Trên, Dưới, Trái, Phải)
                                                dmc.Box(
                                                    [
                                                        dmc.Text(
                                                            "Khoảng đệm (Padding - px):",
                                                            size="xs",
                                                            fw=500,
                                                            mb=4,
                                                        ),
                                                        dmc.SimpleGrid(
                                                            cols=4,
                                                            spacing="xs",
                                                            children=[
                                                                dmc.NumberInput(
                                                                    id="mail-studio-prop-pad-top",
                                                                    label="Trên",
                                                                    min=0,
                                                                    max=60,
                                                                    value=16,
                                                                    size="xs",
                                                                ),
                                                                dmc.NumberInput(
                                                                    id="mail-studio-prop-pad-bottom",
                                                                    label="Dưới",
                                                                    min=0,
                                                                    max=60,
                                                                    value=16,
                                                                    size="xs",
                                                                ),
                                                                dmc.NumberInput(
                                                                    id="mail-studio-prop-pad-left",
                                                                    label="Trái",
                                                                    min=0,
                                                                    max=60,
                                                                    value=24,
                                                                    size="xs",
                                                                ),
                                                                dmc.NumberInput(
                                                                    id="mail-studio-prop-pad-right",
                                                                    label="Phải",
                                                                    min=0,
                                                                    max=60,
                                                                    value=24,
                                                                    size="xs",
                                                                ),
                                                            ],
                                                        ),
                                                    ]
                                                ),
                                                # Màu chữ & Màu nền (Color Picker với palette)
                                                dmc.SimpleGrid(
                                                    cols=2,
                                                    spacing="xs",
                                                    children=[
                                                        dmc.ColorInput(
                                                            id="mail-studio-prop-color",
                                                            label="Màu chữ",
                                                            value="#26354a",
                                                            withEyeDropper=False,
                                                            popoverProps={"withinPortal": True},
                                                            size="xs",
                                                            swatches=[
                                                                "#1e3a5f",
                                                                "#2563eb",
                                                                "#059669",
                                                                "#d97706",
                                                                "#dc2626",
                                                                "#475569",
                                                                "#000000",
                                                                "#ffffff",
                                                            ],
                                                            format="hex",
                                                        ),
                                                        dmc.ColorInput(
                                                            id="mail-studio-prop-bg",
                                                            label="Màu nền",
                                                            value="#ffffff",
                                                            withEyeDropper=False,
                                                            popoverProps={"withinPortal": True},
                                                            size="xs",
                                                            swatches=[
                                                                "#ffffff",
                                                                "#f8fafc",
                                                                "#f1f5f9",
                                                                "#e2e8f0",
                                                                "#ecfdf5",
                                                                "#fef2f2",
                                                                "#fff4e5",
                                                                "#1e293b",
                                                            ],
                                                            format="hex",
                                                        ),
                                                    ],
                                                ),
                                                # Căn lề
                                                dmc.Select(
                                                    id="mail-studio-prop-align",
                                                    label="Căn lề (Align)",
                                                    data=[
                                                        {"value": "left", "label": "Căn trái"},
                                                        {"value": "center", "label": "Căn giữa"},
                                                        {"value": "right", "label": "Căn phải"},
                                                    ],
                                                    value="left",
                                                ),
                                                # Điều kiện hiển thị
                                                dmc.Select(
                                                    id="mail-studio-prop-cond",
                                                    label="Điều kiện hiển thị",
                                                    description="Tự động ẩn/hiện theo kịch bản dữ liệu",
                                                    data=[
                                                        {
                                                            "value": "always",
                                                            "label": "Luôn hiển thị",
                                                        },
                                                        {
                                                            "value": "target_only",
                                                            "label": "Chỉ khi gửi đích danh user đó",
                                                        },
                                                        {
                                                            "value": "all_users",
                                                            "label": "Chỉ khi gửi danh sách tất cả user",
                                                        },
                                                        {
                                                            "value": "errors",
                                                            "label": "Chỉ khi có lỗi (summary.failed > 0)",
                                                        },
                                                        {
                                                            "value": "noerrors",
                                                            "label": "Chỉ khi thành công (summary.failed == 0)",
                                                        },
                                                    ],
                                                    value="always",
                                                ),
                                            ],
                                            id="mail-studio-prop-form",
                                            gap=8,
                                        ),
                                    ],
                                    gap=4,
                                ),
                                p="sm",
                                withBorder=True,
                                radius="sm",
                                style={
                                    "height": "calc(100vh - 160px)",
                                    "minHeight": "680px",
                                    "overflowY": "auto",
                                },
                            )
                        ],
                        span={"base": 12, "md": 3},
                    ),
                ],
                gutter="xs",
            ),

            # Modal Tạo mới
            dmc.Modal(
                id="mail-studio-modal-create",
                title="Tạo mới mẫu email nghiệp vụ",
                children=dmc.Stack(
                    [
                        dmc.TextInput(
                            id="mail-studio-new-code",
                            label="Mã định danh (CODE)",
                            placeholder="vd: TMPL_BATCH_RUN_ERROR",
                            required=True,
                        ),
                        dmc.TextInput(
                            id="mail-studio-new-name",
                            label="Tên hiển thị mẫu email",
                            placeholder="vd: Thông báo lỗi phiên chạy bộ đối soát",
                            required=True,
                        ),
                        dmc.Select(
                            id="mail-studio-new-page",
                            label="Màn hình gửi thư (Page)",
                            data=get_available_pages(),
                            value="user",
                            required=True,
                        ),
                        dmc.Select(
                            id="mail-studio-new-event",
                            label="Sự kiện nghiệp vụ",
                            data=event_options,
                            value=event_options[0]["value"] if event_options else None,
                            required=True,
                        ),
                        dmc.Textarea(
                            id="mail-studio-new-desc",
                            label="Mô tả mục đích sử dụng",
                            minRows=2,
                        ),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Hủy",
                                    id="mail-studio-new-cancel",
                                    variant="default",
                                    size="xs",
                                    n_clicks=0,
                                ),
                                dmc.Button(
                                    "Khởi tạo mẫu",
                                    id="mail-studio-new-submit",
                                    size="xs",
                                    n_clicks=0,
                                ),
                            ],
                            justify="flex-end",
                            mt="sm",
                        ),
                    ],
                    gap="xs",
                ),
                opened=False,
            ),

            # Modal Kiểm tra
            dmc.Modal(
                id="mail-studio-modal-validate",
                title="Kết quả kiểm tra mẫu email",
                children=html.Div(id="mail-studio-validate-content"),
                opened=False,
            ),

            # Modal Gửi thử
            dmc.Modal(
                id="mail-studio-modal-test",
                title="Gửi email thử nghiệm",
                children=dmc.Stack(
                    [
                        dmc.Alert(
                            "Email thử nghiệm chỉ sử dụng dữ liệu mẫu (mock scenario), không dùng dữ liệu Oracle thật. Tiêu đề sẽ được gắn tiền tố [TEST].",
                            color="blue",
                            variant="light",
                        ),
                        dmc.TextInput(
                            id="mail-studio-test-email",
                            label="Địa chỉ email nhận thử nghiệm",
                            value=getattr(ctx, "email", None) or "designer@reconhub.local",
                            required=True,
                        ),
                        dmc.Select(
                            id="mail-studio-test-scenario",
                            label="Kịch bản dữ liệu kiểm thử",
                            data=[
                                {"value": "success", "label": "Thành công (Success)"},
                                {"value": "error", "label": "Có lỗi phát sinh (Error)"},
                                {"value": "empty", "label": "Không có dữ liệu (Empty)"},
                            ],
                            value="success",
                        ),
                        html.Div(id="mail-studio-test-alert"),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Hủy",
                                    id="mail-studio-test-cancel",
                                    variant="default",
                                    size="xs",
                                    n_clicks=0,
                                ),
                                dmc.Button(
                                    "Gửi ngay",
                                    id="mail-studio-test-submit",
                                    size="xs",
                                    leftSection=DashIconify(icon="lucide:send", width=14),
                                    n_clicks=0,
                                ),
                            ],
                            justify="flex-end",
                            mt="sm",
                        ),
                    ],
                    gap="xs",
                ),
                opened=False,
            ),
        ],
        p="sm",
    )


# --- Callbacks ---


@callback(
    Output("mail-studio-tokens-container", "children"),
    Input("mail-studio-state", "data"),
    Input("mail-studio-page-select", "value"),
    Input("mail-studio-btn-fetch-tokens", "n_clicks"),
)
def update_tokens_container(
    state: dict[str, Any] | None,
    page_code: str | None = None,
    n_fetch: int | None = None,
) -> Any:
    """Hiển thị danh sách token theo Page được chọn hoặc Event Schema."""
    active_page = page_code or (state.get("menu_code") if state else None) or "user"
    introspected = introspect_tokens_for_page(active_page)
    return _render_tokens_badges(introspected)


@callback(
    Output("mail-studio-canvas-content", "children"),
    Output("mail-studio-canvas-content", "style"),
    Output("mail-studio-canvas-wrapper", "style"),
    Input("mail-studio-state", "data"),
    Input("mail-studio-page-select", "value"),
)
def render_canvas(
    state: dict[str, Any] | None,
    page_select_val: str | None = None,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    """Cập nhật giao diện Canvas mỗi khi state thay đổi."""
    if not state:
        return html.Div(), {}, {}

    ctx = get_current_ctx()
    if not ctx:
        return html.Div(), {}, {}

    tmpl_id = state.get("template_id")
    event_code = state.get("event_code") or "GENERAL_EXPORT"
    menu_code = page_select_val or state.get("menu_code") or "user"
    if tmpl_id and not state.get("event_code"):
        det_res = get_mail_template_detail(ctx, tmpl_id)
        if det_res.ok and isinstance(det_res.data, dict):
            event_code = det_res.data.get("template", {}).get("event_code", "GENERAL_EXPORT")
            menu_code = det_res.data.get("template", {}).get("menu_code", "user")

    scenario_name = state.get("scenario", "success")
    scenario_data = get_sample_payload(event_code, scenario_name)
    page_mock = get_mock_payload_for_page(menu_code, scenario_name)
    merged_scenario = {**page_mock, **scenario_data}

    design = state.get("design_json", {})
    blocks = design.get("blocks", []) if isinstance(design, dict) else []
    selected_id = state.get("selected_block_id")
    view_mode = state.get("view_mode", "edit")
    device_mode = state.get("device_mode", "desktop")

    canvas_bg = design.get("canvasSettings", {}).get("bgColor", "#f3f5f9")
    max_w = "375px" if device_mode == "mobile" else "600px"
    canvas_style = {
        "maxWidth": max_w,
        "margin": "0 auto",
        "backgroundColor": "#ffffff",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
        "borderRadius": "6px",
        "overflow": "hidden",
        "transition": "max-width 0.2s ease-in-out",
    }
    wrapper_style = {
        "backgroundColor": canvas_bg,
        "borderRadius": "6px",
        "flex": "1",
        "minHeight": "480px",
        "maxHeight": "calc(100vh - 275px)",
        "overflowY": "auto",
        "overflowX": "hidden",
        "transition": "background-color 0.2s ease-in-out",
    }

    canvas_children = _render_canvas_blocks(blocks, selected_id, merged_scenario, view_mode)
    return canvas_children, canvas_style, wrapper_style


@callback(
    Output("mail-studio-prop-title", "children"),
    Output("mail-studio-prop-text", "value"),
    Output("mail-studio-prop-url", "value"),
    Output("mail-studio-prop-limit", "value"),
    Output("mail-studio-prop-columns", "value"),
    Output("mail-studio-prop-columns-stack", "children"),
    Output("mail-studio-prop-table-scope", "value"),
    Output("mail-studio-prop-size", "value"),
    Output("mail-studio-prop-pad-top", "value"),
    Output("mail-studio-prop-pad-bottom", "value"),
    Output("mail-studio-prop-pad-left", "value"),
    Output("mail-studio-prop-pad-right", "value"),
    Output("mail-studio-prop-color", "value"),
    Output("mail-studio-prop-bg", "value"),
    Output("mail-studio-prop-align", "value"),
    Output("mail-studio-prop-cond", "value"),
    Output("mail-studio-prop-text-wrap", "style"),
    Output("mail-studio-prop-url-wrap", "style"),
    Output("mail-studio-prop-table-wrap", "style"),
    Output("mail-studio-prop-empty-alert", "style"),
    Output("mail-studio-prop-form", "style"),
    Output("mail-studio-prop-ind-enabled", "checked"),
    Output("mail-studio-prop-ind-type", "value"),
    Output("mail-studio-prop-ind-color", "value"),
    Output("mail-studio-prop-ind-shape", "value"),
    Output("mail-studio-prop-ind-text", "value"),
    Output("mail-studio-prop-ind-wrap", "style"),
    Output("mail-studio-prop-btn-options-wrap", "style"),
    Output("mail-studio-prop-btn-shape", "value"),
    Output("mail-studio-prop-btn-width", "value"),
    Output("mail-studio-prop-color", "label"),
    Output("mail-studio-prop-bg", "label"),
    Input("mail-studio-sync-trigger", "data"),
    State("mail-studio-state", "data"),
)
def sync_properties_panel(
    trigger_cnt: int | None,
    state: dict[str, Any] | None,
) -> tuple[
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    Any,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    bool,
    str,
    str,
    str,
    str,
    dict[str, Any],
    dict[str, Any],
    str,
    str,
    str,
    str,
]:
    """Đồng bộ giá trị từ block đang chọn vào form thuộc tính ở Panel Phải."""
    if not state:
        raise PreventUpdate

    blocks = state.get("design_json", {}).get("blocks", [])
    selected_id = state.get("selected_block_id")

    block = next((b for b in blocks if b.get("id") == selected_id), None)
    if not block:
        # Ẩn form, hiện empty alert
        default_checkboxes = [
            dmc.Checkbox(label="Tên Template", value="name", size="xs"),
            dmc.Checkbox(label="Trạng thái", value="status", size="xs"),
            dmc.Checkbox(label="Chi tiết", value="detail", size="xs"),
        ]
        return (
            "Thuộc tính component",
            "",
            "links.result",
            5,
            ["name", "status", "detail"],
            default_checkboxes,
            "all",
            14,
            16,
            16,
            24,
            24,
            "#26354a",
            "#ffffff",
            "left",
            "always",
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
            {"display": "block"},
            {"display": "none"},
            False,
            "dot",
            "#2563eb",
            "round",
            "",
            {"display": "none"},
            {"display": "none"},
            "rounded",
            "auto",
            "Màu chữ",
            "Màu nền",
        )

    b_type = block.get("type", "text")
    type_name = TYPE_LABEL_MAP.get(b_type, b_type)
    title = f"Thuộc tính: {type_name}"

    text_wrap_style = {"display": "none"} if b_type in ("divider", "spacer") else {"display": "block"}
    url_wrap_style = {"display": "block"} if b_type == "button" else {"display": "none"}
    btn_wrap_style = {"display": "block"} if b_type == "button" else {"display": "none"}
    table_wrap_style = {"display": "block"} if b_type == "table" else {"display": "none"}

    btn_shape = block.get("button_shape", "rounded")
    btn_width = block.get("button_width", "auto")

    # Lấy danh sách cột động theo page hiện tại
    menu_code = state.get("menu_code", "user")
    col_opts = get_table_columns_options_for_page(menu_code)
    col_checkboxes = [
        dmc.Checkbox(label=lbl, value=val, size="xs")
        for val, lbl in col_opts
    ]
    valid_col_keys = [val for val, _ in col_opts]
    raw_block_cols = block.get("columns", [])
    resolved_cols = [c for c in raw_block_cols if c in valid_col_keys]
    if not resolved_cols:
        resolved_cols = valid_col_keys[:3] if valid_col_keys else ["name", "status", "detail"]

    pad_top = int(block.get("pad_top", block.get("pad", 16)))
    pad_bottom = int(block.get("pad_bottom", block.get("pad", 16)))
    pad_left = int(block.get("pad_left", 24))
    pad_right = int(block.get("pad_right", 24))

    # Xử lý Indicator
    if b_type == "indicator":
        ind_wrap_style = {"display": "block"}
        ind_enabled = True
        ind_type = block.get("indicator_type", "dot")
        ind_color = block.get("color", "#047857")
        ind_shape = block.get("indicator_shape", "round")
        ind_text = block.get("indicator_text", "")
    elif b_type == "text":
        ind_wrap_style = {"display": "block"}
        ind_enabled = bool(block.get("has_indicator", False))
        ind_type = block.get("indicator_type", "dot")
        ind_color = block.get("indicator_color", "#2563eb")
        ind_shape = block.get("indicator_shape", "round")
        ind_text = block.get("indicator_text", "")
    else:
        ind_wrap_style = {"display": "none"}
        ind_enabled = False
        ind_type = "dot"
        ind_color = "#2563eb"
        ind_shape = "round"
        ind_text = ""

    color_label = "Màu chữ nút" if b_type == "button" else ("Màu chữ / Viền" if b_type == "alert" else "Màu chữ")
    bg_label = "Màu nền nút" if b_type == "button" else ("Màu nền hộp" if b_type == "alert" else "Màu nền")

    return (
        title,
        block.get("text", ""),
        block.get("url", "links.result"),
        int(block.get("limit", 5)),
        resolved_cols,
        col_checkboxes,
        block.get("table_scope", "all"),
        int(block.get("size", 14)),
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        block.get("color", "#ffffff" if b_type == "button" else "#26354a"),
        block.get("bg", "#2563eb" if b_type == "button" else "#ffffff"),
        block.get("align", "left"),
        block.get("condition", "always"),
        text_wrap_style,
        url_wrap_style,
        table_wrap_style,
        {"display": "none"},
        {"display": "flex", "flexDirection": "column"},
        ind_enabled,
        ind_type,
        ind_color,
        ind_shape,
        ind_text,
        ind_wrap_style,
        btn_wrap_style,
        btn_shape,
        btn_width,
        color_label,
        bg_label,
    )


@callback(
    Output("mail-studio-state", "data", allow_duplicate=True),
    Output("mail-studio-sync-trigger", "data", allow_duplicate=True),
    Input({"type": "mail-tile-add", "block_type": ALL}, "n_clicks"),
    State("mail-studio-state", "data"),
    State("mail-studio-sync-trigger", "data"),
    prevent_initial_call=True,
)
def handle_add_block(
    n_clicks_list: list[int | None],
    state: dict[str, Any] | None,
    sync_cnt: int | None,
) -> tuple[Any, int]:
    """Thêm một block mới vào Canvas khi bấm vào tile ở Panel Trái."""
    if not state or not any(n_clicks_list):
        raise PreventUpdate

    trig_id = dash.ctx.triggered_id
    if not isinstance(trig_id, dict):
        raise PreventUpdate

    block_type = trig_id.get("block_type", "text")

    st = copy.deepcopy(state)
    design = st.get("design_json", {})
    blocks = design.setdefault("blocks", [])

    next_seq = st.get("seq", 10) + 1
    new_block = _make_block(block_type, next_seq)

    # Chèn ngay sau block đang chọn hoặc ở cuối
    sel_id = st.get("selected_block_id")
    insert_idx = len(blocks)
    if sel_id:
        for idx, b in enumerate(blocks):
            if b.get("id") == sel_id:
                insert_idx = idx + 1
                break

    blocks.insert(insert_idx, new_block)
    st["selected_block_id"] = new_block["id"]
    st["seq"] = next_seq
    st["dirty"] = True

    return st, (sync_cnt or 0) + 1


@callback(
    Output("mail-studio-state", "data", allow_duplicate=True),
    Output("mail-studio-sync-trigger", "data", allow_duplicate=True),
    Input({"type": "mail-block-select", "index": ALL}, "n_clicks"),
    State("mail-studio-state", "data"),
    State("mail-studio-sync-trigger", "data"),
    prevent_initial_call=True,
)
def handle_select_block(
    n_clicks_list: list[int | None],
    state: dict[str, Any] | None,
    sync_cnt: int | None,
) -> tuple[Any, int]:
    """Chọn block khi bấm trực tiếp vào vùng nội dung trên Canvas."""
    if not state or not any(n_clicks_list):
        raise PreventUpdate

    trig_id = dash.ctx.triggered_id
    if not isinstance(trig_id, dict):
        raise PreventUpdate

    sel_id = trig_id.get("index")
    if sel_id == state.get("selected_block_id"):
        raise PreventUpdate

    st = copy.deepcopy(state)
    st["selected_block_id"] = sel_id
    return st, (sync_cnt or 0) + 1


@callback(
    Output("mail-studio-state", "data", allow_duplicate=True),
    Output("mail-studio-sync-trigger", "data", allow_duplicate=True),
    Input({"type": "mail-block-btn", "action": ALL, "index": ALL}, "n_clicks"),
    State("mail-studio-state", "data"),
    State("mail-studio-sync-trigger", "data"),
    prevent_initial_call=True,
)
def handle_block_action(
    n_clicks_list: list[int | None],
    state: dict[str, Any] | None,
    sync_cnt: int | None,
) -> tuple[Any, int]:
    """Xử lý Lên (up), Xuống (down), Nhân bản (copy), Xóa (del) trên từng block."""
    if not state or not any(n_clicks_list):
        raise PreventUpdate

    trig_id = dash.ctx.triggered_id
    if not isinstance(trig_id, dict):
        raise PreventUpdate

    action = trig_id.get("action")
    target_id = trig_id.get("index")

    st = copy.deepcopy(state)
    blocks = st.get("design_json", {}).get("blocks", [])

    idx = next((i for i, b in enumerate(blocks) if b.get("id") == target_id), -1)
    if idx < 0:
        raise PreventUpdate

    if action == "del":
        blocks.pop(idx)
        st["selected_block_id"] = blocks[min(idx, len(blocks) - 1)]["id"] if blocks else None
        st["dirty"] = True
    elif action == "copy":
        next_seq = st.get("seq", 10) + 1
        cloned = copy.deepcopy(blocks[idx])
        cloned["id"] = next_seq
        blocks.insert(idx + 1, cloned)
        st["selected_block_id"] = next_seq
        st["seq"] = next_seq
        st["dirty"] = True
    elif action == "up" and idx > 0:
        blocks[idx], blocks[idx - 1] = blocks[idx - 1], blocks[idx]
        st["selected_block_id"] = target_id
        st["dirty"] = True
    elif action == "down" and idx < len(blocks) - 1:
        blocks[idx], blocks[idx + 1] = blocks[idx + 1], blocks[idx]
        st["selected_block_id"] = target_id
        st["dirty"] = True

    return st, (sync_cnt or 0) + 1


@callback(
    Output("mail-studio-prop-text", "value", allow_duplicate=True),
    Output("mail-studio-state", "data", allow_duplicate=True),
    Input({"type": "mail-token-add", "token": ALL}, "n_clicks"),
    State("mail-studio-prop-text", "value"),
    State("mail-studio-state", "data"),
    prevent_initial_call=True,
)
def handle_token_insert(
    n_clicks_list: list[int | None],
    current_text: str | None,
    state: dict[str, Any] | None,
) -> tuple[str, Any]:
    """Bấm vào Token ở Panel Trái -> Chèn ngay token vào text của khối đang chọn."""
    if not state or not any(n_clicks_list):
        raise PreventUpdate

    trig_id = dash.ctx.triggered_id
    if not isinstance(trig_id, dict):
        raise PreventUpdate

    token = trig_id.get("token")
    if not token:
        raise PreventUpdate

    st = copy.deepcopy(state)
    sel_id = st.get("selected_block_id")
    blocks = st.get("design_json", {}).get("blocks", [])

    block = next((b for b in blocks if b.get("id") == sel_id), None)
    token_str = f"{{{{{token}}}}}"

    new_text = f"{current_text or ''} {token_str}".strip()
    if block:
        block["text"] = new_text
        st["dirty"] = True

    return new_text, st


@callback(
    Output("mail-studio-state", "data", allow_duplicate=True),
    Input("mail-studio-prop-text", "value"),
    Input("mail-studio-prop-url", "value"),
    Input("mail-studio-prop-limit", "value"),
    Input("mail-studio-prop-columns", "value"),
    Input("mail-studio-prop-size", "value"),
    Input("mail-studio-prop-pad-top", "value"),
    Input("mail-studio-prop-pad-bottom", "value"),
    Input("mail-studio-prop-pad-left", "value"),
    Input("mail-studio-prop-pad-right", "value"),
    Input("mail-studio-prop-color", "value"),
    Input("mail-studio-prop-bg", "value"),
    Input("mail-studio-prop-align", "value"),
    Input("mail-studio-prop-cond", "value"),
    Input("mail-studio-prop-ind-enabled", "checked"),
    Input("mail-studio-prop-ind-type", "value"),
    Input("mail-studio-prop-ind-color", "value"),
    Input("mail-studio-prop-ind-shape", "value"),
    Input("mail-studio-prop-ind-text", "value"),
    Input("mail-studio-prop-btn-shape", "value"),
    Input("mail-studio-prop-btn-width", "value"),
    Input("mail-studio-prop-table-scope", "value"),
    State("mail-studio-state", "data"),
    prevent_initial_call=True,
)
def handle_property_change(
    text_val: str | None,
    url_val: str | None,
    limit_val: int | None,
    columns_val: list[str] | None,
    size_val: int | None,
    pad_top_val: int | None,
    pad_bottom_val: int | None,
    pad_left_val: int | None,
    pad_right_val: int | None,
    color_val: str | None,
    bg_val: str | None,
    align_val: str | None,
    cond_val: str | None,
    ind_enabled: bool | None,
    ind_type: str | None,
    ind_color: str | None,
    ind_shape: str | None,
    ind_text: str | None,
    btn_shape_val: str | None,
    btn_width_val: str | None,
    table_scope_val: str | None,
    state: dict[str, Any] | None,
) -> Any:
    """Cập nhật các thuộc tính của block khi người dùng gõ vào form Panel Phải."""
    if not state or not state.get("selected_block_id"):
        raise PreventUpdate

    st = copy.deepcopy(state)
    sel_id = st["selected_block_id"]
    blocks = st.get("design_json", {}).get("blocks", [])

    block = next((b for b in blocks if b.get("id") == sel_id), None)
    if not block:
        raise PreventUpdate

    if text_val is not None:
        block["text"] = text_val
    if url_val is not None:
        block["url"] = url_val
    if limit_val is not None:
        block["limit"] = max(1, min(20, int(limit_val)))
    if columns_val is not None:
        block["columns"] = columns_val
    if table_scope_val is not None:
        block["table_scope"] = table_scope_val
    if size_val is not None:
        block["size"] = max(10, min(36, int(size_val)))
    if pad_top_val is not None:
        block["pad_top"] = max(0, min(60, int(pad_top_val)))
        block["pad"] = block["pad_top"]
    if pad_bottom_val is not None:
        block["pad_bottom"] = max(0, min(60, int(pad_bottom_val)))
    if pad_left_val is not None:
        block["pad_left"] = max(0, min(60, int(pad_left_val)))
    if pad_right_val is not None:
        block["pad_right"] = max(0, min(60, int(pad_right_val)))
    if color_val is not None:
        block["color"] = color_val
    if bg_val is not None:
        block["bg"] = bg_val
    if align_val is not None:
        block["align"] = align_val
    if cond_val is not None:
        block["condition"] = cond_val

    if ind_enabled is not None:
        block["has_indicator"] = bool(ind_enabled)
    if ind_type is not None:
        block["indicator_type"] = ind_type
    if ind_color is not None:
        block["indicator_color"] = ind_color
        if block.get("type") == "indicator":
            block["color"] = ind_color
    if ind_shape is not None:
        block["indicator_shape"] = ind_shape
    if ind_text is not None:
        block["indicator_text"] = ind_text

    if btn_shape_val is not None:
        block["button_shape"] = btn_shape_val
    if btn_width_val is not None:
        block["button_width"] = btn_width_val

    st["dirty"] = True
    return st


clientside_callback(
    """
    function(isChecked) {
        return isChecked ? {'display': 'block'} : {'display': 'none'};
    }
    """,
    Output("mail-studio-prop-ind-options", "style"),
    Input("mail-studio-prop-ind-enabled", "checked"),
)


clientside_callback(
    """
    function(indType) {
        return indType === 'badge' ? {'display': 'block'} : {'display': 'none'};
    }
    """,
    Output("mail-studio-prop-ind-text-wrap", "style"),
    Input("mail-studio-prop-ind-type", "value"),
)


@callback(
    Output("mail-studio-state", "data", allow_duplicate=True),
    Input("mail-studio-canvas-bg-toggle", "value"),
    State("mail-studio-state", "data"),
    prevent_initial_call=True,
)
def handle_canvas_bg_change(bg_color: str | None, state: dict[str, Any] | None) -> Any:
    if not state or not bg_color:
        raise PreventUpdate
    st = copy.deepcopy(state)
    design = st.setdefault("design_json", {})
    canvas_settings = design.setdefault("canvasSettings", {})
    if canvas_settings.get("bgColor") == bg_color:
        raise PreventUpdate
    canvas_settings["bgColor"] = bg_color
    st["dirty"] = True
    return st


@callback(
    Output("mail-studio-state", "data", allow_duplicate=True),
    Output("mail-studio-sync-trigger", "data", allow_duplicate=True),
    Input("mail-studio-reorder-store", "data"),
    State("mail-studio-state", "data"),
    State("mail-studio-sync-trigger", "data"),
    prevent_initial_call=True,
)
def handle_drag_reorder(
    reorder_data: dict[str, Any] | None,
    state: dict[str, Any] | None,
    sync_cnt: int | None,
) -> tuple[Any, int]:
    """Sắp xếp lại thứ tự block khi người dùng kéo thả trên Canvas."""
    if not reorder_data or not state:
        raise PreventUpdate

    from_id = reorder_data.get("from_id")
    to_id = reorder_data.get("to_id")
    if from_id is None or to_id is None or from_id == to_id:
        raise PreventUpdate

    st = copy.deepcopy(state)
    blocks = st.get("design_json", {}).get("blocks", [])

    from_idx = next((i for i, b in enumerate(blocks) if b.get("id") == from_id), -1)
    to_idx = next((i for i, b in enumerate(blocks) if b.get("id") == to_id), -1)

    if from_idx < 0 or to_idx < 0:
        raise PreventUpdate

    moved_block = blocks.pop(from_idx)
    blocks.insert(to_idx, moved_block)
    st["selected_block_id"] = from_id
    st["dirty"] = True
    return st, (sync_cnt or 0) + 1


@callback(
    Output("mail-studio-state", "data", allow_duplicate=True),
    Input("mail-studio-device-toggle", "value"),
    Input("mail-studio-mode-toggle", "value"),
    Input("mail-studio-subject-input", "value"),
    Input("mail-studio-preheader-input", "value"),
    State("mail-studio-state", "data"),
    prevent_initial_call=True,
)
def handle_top_bar_changes(
    device_mode: str,
    view_mode: str,
    subject: str,
    preheader: str,
    state: dict[str, Any] | None,
) -> Any:
    """Cập nhật chế độ xem, tiêu đề Subject, Preheader."""
    if not state:
        raise PreventUpdate

    st = copy.deepcopy(state)
    st["device_mode"] = device_mode or "desktop"
    st["view_mode"] = view_mode or "edit"
    st["subject"] = subject or ""
    st["preheader"] = preheader or ""
    return st


@callback(
    Output("mail-studio-modal-validate", "opened"),
    Output("mail-studio-validate-content", "children"),
    Input("mail-studio-btn-validate", "n_clicks"),
    State("mail-studio-state", "data"),
    prevent_initial_call=True,
)
def handle_validate(n_clicks: int | None, state: dict[str, Any] | None) -> tuple[bool, Any]:
    """Kiểm tra toàn diện tính hợp lệ của template và hiển thị modal kết quả."""
    if not state or not n_clicks:
        raise PreventUpdate

    ctx = get_current_ctx()
    if not ctx:
        return False, None

    tmpl_id = state.get("template_id")
    event_code = "GENERAL_EXPORT"
    tmpl_name = "Mẫu email"
    menu_code = state.get("menu_code") or "user"
    if tmpl_id:
        det_res = get_mail_template_detail(ctx, tmpl_id)
        if det_res.ok and isinstance(det_res.data, dict):
            event_code = det_res.data.get("template", {}).get("event_code", "GENERAL_EXPORT")
            tmpl_name = det_res.data.get("template", {}).get("name", "Mẫu email")
            menu_code = det_res.data.get("template", {}).get("menu_code") or menu_code

    design = state.get("design_json", {})
    subject = state.get("subject", "")

    errors = validate_design(design, event_code, subject=subject, name=tmpl_name, menu_code=menu_code)

    if errors:
        err_items = [dmc.List(children=[dmc.ListItem(err) for err in errors], size="sm", c="red")]
        content = dmc.Alert(
            title=f"Phát hiện {len(errors)} vấn đề cần xử lý:",
            children=dmc.Stack(err_items, gap=6),
            color="red",
            variant="light",
        )
    else:
        content = dmc.Alert(
            title="Mẫu email hợp lệ hoàn toàn!",
            children="Biến dữ liệu đúng schema sự kiện, không chứa URL ngoài trái phép, các component tương thích sâu với Outlook và Gmail.",
            color="green",
            variant="light",
            icon=DashIconify(icon="lucide:check-circle-2", width=20),
        )

    return True, content


@callback(
    Output("mail-studio-notifications", "children", allow_duplicate=True),
    Output("mail-studio-badge-status", "children", allow_duplicate=True),
    Output("mail-studio-badge-status", "color", allow_duplicate=True),
    Output("mail-studio-state", "data", allow_duplicate=True),
    Input("mail-studio-btn-save-draft", "n_clicks"),
    State("mail-studio-state", "data"),
    State("mail-studio-page-select", "value"),
    prevent_initial_call=True,
)
def handle_save_draft(
    n_clicks: int | None,
    state: dict[str, Any] | None,
    page_select: str | None = None,
) -> Any:
    """Lưu bản nháp version hiện tại (tự động clone sang draft mới nếu đang ở Active)."""
    if not state or not n_clicks:
        raise PreventUpdate

    ctx = get_current_ctx()
    if not ctx:
        return notify_error("Chưa đăng nhập"), no_update, no_update, no_update

    tmpl_id = state.get("template_id")
    if not tmpl_id:
        return notify_error("Chưa chọn mẫu email để lưu"), no_update, no_update, no_update

    v_id = state.get("version_id")
    subject = state.get("subject", "")
    preheader = state.get("preheader", "")
    design = state.get("design_json", {})
    page_code = page_select or state.get("menu_code")

    save_res = save_draft_version(
        ctx,
        template_id=tmpl_id,
        version_id=v_id,
        subject=subject,
        preheader=preheader,
        design_json=design,
        page_code=page_code,
    )

    if not save_res.ok:
        return notify_error(save_res.message or "Lưu bản nháp thất bại"), no_update, no_update, no_update

    save_data = save_res.data if isinstance(save_res.data, dict) else {}
    cur_v = save_data.get("current_version", {})
    new_v_no = cur_v.get("version_no", state.get("version_no", 1))
    new_status = cur_v.get("status", "DRAFT")

    st = copy.deepcopy(state)
    st["version_id"] = cur_v.get("id")
    st["version_no"] = new_v_no
    st["status"] = new_status
    st["dirty"] = False
    if page_code:
        st["menu_code"] = page_code

    badge_text = f"v{new_v_no} · {new_status}"
    badge_color = "green" if new_status == "ACTIVE" else "orange"

    return (
        notify_success(f"Đã lưu bản nháp v{new_v_no} ({new_status}) thành công!"),
        badge_text,
        badge_color,
        st,
    )


@callback(
    Output("mail-studio-notifications", "children", allow_duplicate=True),
    Output("mail-studio-badge-status", "children", allow_duplicate=True),
    Output("mail-studio-badge-status", "color", allow_duplicate=True),
    Output("mail-studio-state", "data", allow_duplicate=True),
    Input("mail-studio-btn-activate", "n_clicks"),
    State("mail-studio-state", "data"),
    prevent_initial_call=True,
)
def handle_activate(n_clicks: int | None, state: dict[str, Any] | None) -> Any:
    """Kích hoạt phiên bản đang chọn thành ACTIVE phục vụ cho worker/email nghiệp vụ."""
    if not state or not n_clicks:
        raise PreventUpdate

    ctx = get_current_ctx()
    if not ctx:
        return notify_error("Chưa đăng nhập"), no_update, no_update, no_update

    tmpl_id = state.get("template_id")
    v_id = state.get("version_id")
    if not tmpl_id or not v_id:
        return notify_error("Chưa có phiên bản để kích hoạt"), no_update, no_update, no_update

    act_res = activate_version(ctx, template_id=tmpl_id, version_id=v_id)
    if not act_res.ok:
        return notify_error(act_res.message or "Không thể kích hoạt phiên bản"), no_update, no_update, no_update

    act_data = act_res.data if isinstance(act_res.data, dict) else {}
    cur_v = act_data.get("current_version", {})
    v_no = cur_v.get("version_no", 1)

    st = copy.deepcopy(state)
    st["status"] = "ACTIVE"
    st["dirty"] = False

    return (
        notify_success(f"Phiên bản v{v_no} đã được kích hoạt thành công (ACTIVE)!"),
        f"v{v_no} · ACTIVE",
        "green",
        st,
    )


@callback(
    Output("mail-studio-download", "data"),
    Input("mail-studio-btn-export-json", "n_clicks"),
    State("mail-studio-state", "data"),
    prevent_initial_call=True,
)
def handle_export_json(n_clicks: int | None, state: dict[str, Any] | None) -> Any:
    """Tải tệp JSON thiết kế mẫu email về máy."""
    if not state or not n_clicks:
        raise PreventUpdate

    export_payload = {
        "schemaVersion": 1,
        "templateId": state.get("template_id"),
        "versionNo": state.get("version_no"),
        "status": state.get("status"),
        "subject": state.get("subject"),
        "preheader": state.get("preheader"),
        "design": state.get("design_json"),
    }

    raw_json = json.dumps(export_payload, indent=2, ensure_ascii=False)
    return dcc.send_string(raw_json, filename=f"mail-template-v{state.get('version_no', 1)}.json")  # type: ignore[attr-defined,no-untyped-call]


@callback(
    Output("mail-studio-modal-test", "opened"),
    Input("mail-studio-btn-open-test", "n_clicks"),
    Input("mail-studio-test-cancel", "n_clicks"),
    State("mail-studio-modal-test", "opened"),
    prevent_initial_call=True,
)
def toggle_test_modal(n_open: int | None, n_cancel: int | None, is_open: bool) -> bool:
    """Đóng/mở modal gửi thử email."""
    return not is_open


@callback(
    Output("mail-studio-test-alert", "children"),
    Output("mail-studio-notifications", "children", allow_duplicate=True),
    Input("mail-studio-test-submit", "n_clicks"),
    State("mail-studio-test-email", "value"),
    State("mail-studio-test-scenario", "value"),
    State("mail-studio-state", "data"),
    prevent_initial_call=True,
)
def handle_test_send(
    n_clicks: int | None,
    recipient: str | None,
    scenario: str | None,
    state: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Thực hiện gửi email thử nghiệm."""
    if not state or not n_clicks:
        raise PreventUpdate

    ctx = get_current_ctx()
    if not ctx:
        return dmc.Alert("Chưa đăng nhập", color="red"), no_update

    tmpl_id = state.get("template_id")
    v_id = state.get("version_id")
    if not tmpl_id or not v_id:
        return dmc.Alert("Chưa có phiên bản để gửi thử.", color="red"), no_update

    res = exec_test_send_template(
        ctx,
        template_id=tmpl_id,
        version_id=v_id,
        recipient_email=recipient,
        scenario=scenario or "success",
    )

    if not res.ok:
        return (
            dmc.Alert(res.message or "Lỗi gửi thử nghiệm", color="red", variant="light"),
            notify_error(res.message or "Gửi thử nghiệm thất bại"),
        )

    test_data = res.data if isinstance(res.data, dict) else {}
    msg = f"Đã gửi email thử nghiệm thành công tới {test_data.get('recipient')}!"
    return (
        dmc.Alert(msg, color="green", variant="light"),
        notify_success(msg),
    )


@callback(
    Output("mail-studio-modal-create", "opened"),
    Input("mail-studio-btn-open-create", "n_clicks"),
    Input("mail-studio-new-cancel", "n_clicks"),
    State("mail-studio-modal-create", "opened"),
    prevent_initial_call=True,
)
def toggle_create_modal(n_open: int | None, n_cancel: int | None, is_open: bool) -> bool:
    """Đóng/mở modal tạo template mới."""
    return not is_open


@callback(
    Output("mail-studio-template-select", "data"),
    Output("mail-studio-template-select", "value"),
    Output("mail-studio-modal-create", "opened", allow_duplicate=True),
    Output("mail-studio-notifications", "children", allow_duplicate=True),
    Input("mail-studio-new-submit", "n_clicks"),
    State("mail-studio-new-code", "value"),
    State("mail-studio-new-name", "value"),
    State("mail-studio-new-page", "value"),
    State("mail-studio-new-event", "value"),
    State("mail-studio-new-desc", "value"),
    prevent_initial_call=True,
)
def handle_create_template(
    n_clicks: int | None,
    code: str | None,
    name: str | None,
    page_code: str | None,
    event_code: str | None,
    desc: str | None,
) -> tuple[Any, Any, bool, Any]:
    """Tạo mới một template và nạp ngay vào Studio."""
    if not n_clicks:
        raise PreventUpdate

    ctx = get_current_ctx()
    if not ctx:
        return no_update, no_update, False, notify_error("Chưa đăng nhập")

    res = create_mail_template(
        ctx,
        code=code or "",
        name=name or "",
        event_code=event_code or "USER_CREATED",
        description=desc or "",
        menu_code=page_code or "user",
    )

    if not res.ok:
        return no_update, no_update, True, notify_error(res.message or "Tạo template thất bại")

    # Nạp lại danh sách template
    list_res = list_mail_templates(ctx)
    templates = list_res.data if list_res.ok and isinstance(list_res.data, list) else []
    select_data = [
        {
            "value": str(t["id"]),
            "label": f"{t['name']} [{t['active_status']} v{t['active_version_no'] or '1'}]",
        }
        for t in templates
    ]

    created_data = res.data if isinstance(res.data, dict) else {}
    new_id = str(created_data.get("template", {}).get("id"))
    return select_data, new_id, False, notify_success(f"Đã tạo thành công template '{name}'!")


@callback(
    Output("mail-studio-state", "data", allow_duplicate=True),
    Output("mail-studio-sync-trigger", "data", allow_duplicate=True),
    Output("mail-studio-subject-input", "value", allow_duplicate=True),
    Output("mail-studio-preheader-input", "value", allow_duplicate=True),
    Output("mail-studio-badge-status", "children", allow_duplicate=True),
    Output("mail-studio-badge-status", "color", allow_duplicate=True),
    Output("mail-studio-page-select", "value", allow_duplicate=True),
    Input("mail-studio-template-select", "value"),
    State("mail-studio-state", "data"),
    State("mail-studio-sync-trigger", "data"),
    prevent_initial_call=True,
)
def handle_switch_template(
    tmpl_id_str: str | None,
    state: dict[str, Any] | None,
    sync_cnt: int | None,
) -> tuple[Any, int, Any, Any, Any, Any, Any]:
    """Chuyển đổi template đang làm việc từ dropdown."""
    if not tmpl_id_str:
        raise PreventUpdate

    ctx = get_current_ctx()
    if not ctx:
        raise PreventUpdate

    tmpl_id = int(tmpl_id_str)
    det_res = get_mail_template_detail(ctx, tmpl_id)
    if not det_res.ok or not isinstance(det_res.data, dict):
        raise PreventUpdate

    detail = det_res.data
    cur_v = detail.get("current_version") or {}
    design = cur_v.get("design_json") or {"blocks": []}
    blocks = design.get("blocks", []) if isinstance(design, dict) else []
    v_no = cur_v.get("version_no", 1)
    status = cur_v.get("status", "DRAFT")
    subject = cur_v.get("subject_template", "")
    preheader = cur_v.get("preheader_template", "")
    menu_code = detail.get("template", {}).get("menu_code", "user")

    st = copy.deepcopy(state or {})
    st["template_id"] = tmpl_id
    st["event_code"] = detail.get("template", {}).get("event_code", "USER_CREATED")
    st["menu_code"] = menu_code
    st["version_id"] = cur_v.get("id")
    st["version_no"] = v_no
    st["status"] = status
    st["selected_block_id"] = blocks[0].get("id") if blocks else None
    st["subject"] = subject
    st["preheader"] = preheader
    st["design_json"] = design
    st["dirty"] = False
    st["seq"] = max([b.get("id", 0) for b in blocks] + [10])

    badge_text = f"v{v_no} · {status}"
    badge_color = "green" if status == "ACTIVE" else "orange"

    return st, (sync_cnt or 0) + 1, subject, preheader, badge_text, badge_color, menu_code
