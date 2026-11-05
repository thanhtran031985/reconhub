"""app/ui/pages/lookups.py — Màn hình Quản lý Danh mục Lookup (Screen12-Lookups).

Bố cục Master–Detail 2 cột theo chuẩn designs/components/Screen12-Lookups/:
- Cột trái (Master ~35%):
    - Tiêu đề nhóm, badge số lượng loại, nút "+ Thêm loại".
    - Ô tìm kiếm loại danh mục (theo tên hoặc mã).
    - Danh sách Type kèm badge đếm mã con, tag "Hệ thống".
- Cột phải (Detail ~65%):
    - Tiêu đề loại đang chọn, mã loại, nút "Sửa loại", nút "+ Thêm giá trị" (khóa nếu nhóm cố định).
    - Khung cảnh báo chính sách (Policy alert: nhóm cố định vs nhóm mở).
    - Toolbar: ô tìm kiếm mã/nhãn, dropdown lọc trạng thái (Tất cả / Đang dùng / Ngừng dùng).
    - Bảng danh sách Code: STT, Mã, Nhãn hiển thị kèm badge preview, Thứ tự, Switch active, Nút Sửa / Xóa.
    - Dòng ghi chú chân trang: Mã ngừng dùng vẫn hiển thị trong lịch sử.
- Modals:
    - Thêm / Sửa Lookup Type.
    - Thêm / Sửa Lookup Code (chọn màu sắc, icon Lucide, thứ tự, preview badge trực tiếp).
    - Modal xác nhận xóa / vô hiệu hóa thông minh.

Phân quyền: Chỉ ADMIN truy cập; VIEWER/OPERATOR thấy thông báo không có quyền.
"""

from __future__ import annotations

import json
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.lookup import (
    create_lookup_code,
    create_lookup_type,
    delete_lookup_code,
    list_lookup_codes,
    list_lookup_types,
    toggle_lookup_code_status,
    update_lookup_code,
    update_lookup_type,
)
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm

# Màu sắc cho badge DMC (gồm "warn" là màu theme của app, dùng trong seed
# cho mã DATA_INPUT; nếu thiếu, sửa mã đó sẽ thấy ô chọn màu trống).
BADGE_COLORS = ["blue", "teal", "red", "yellow", "gray", "purple", "green", "orange", "cyan", "violet", "warn"]

# Icon Lucide thường dùng
COMMON_ICONS = [
    "lucide:check-circle",
    "lucide:clock",
    "lucide:loader",
    "lucide:check-circle-2",
    "lucide:calculator",
    "lucide:bug",
    "lucide:pencil",
    "lucide:shield",
    "lucide:more-horizontal",
    "lucide:flag",
    "lucide:alert-triangle",
    "lucide:database",
    "lucide:file",
    "lucide:users",
    "lucide:list",
    "lucide:circle",
]

# Các nhóm cố định (closed policy): không cho thêm/xóa mã hệ thống
CLOSED_POLICY_TYPES = {"ISSUE_STATUS", "DISCREPANCY_TYPE"}


def _service_message(res: Any) -> str | None:
    """Trả thông báo lỗi từ ServiceResult, hoặc None nếu thành công."""
    if res is None:
        return "Không nhận được kết quả từ service."
    ok = getattr(res, "ok", None)
    if ok:
        return None
    return getattr(res, "message", None) or "Thao tác không thành công."


def _error_state(title: str, message: str, retry_id: str) -> Any:
    """Trạng thái lỗi: giữ thông báo và nút Thử lại, không báo nhầm thành trống.

    Nút Thử lại là link tải lại trang, không phải Input của callback:
    nút này chỉ xuất hiện khi đã lỗi, mà callback Dash dùng id cố định
    vắng mặt lúc tải trang sẽ làm hỏng cả callback Master-Detail (đã
    kiểm chứng bằng Playwright: thêm Input retry cố định khiến bấm chọn
    loại không gửi request _dash-update-component nữa).
    """
    return dmc.Stack(
        [
            alert_box(title, message, tone="crit"),
            dmc.Group(
                [
                    # DMC Button ở version này không có prop href, nên dùng
                    # Anchor tải lại trang cho nút Thử lại.
                    dmc.Anchor("Thử lại", href="/lookups", id=retry_id, size="sm")
                ],
                justify="flex-start",
            ),
        ],
        gap="sm",
    )


# ─── Hàm render thành phần ───────────────────────────────────────────────────


def render_type_list(
    ctx: Any,
    selected_type: str | None = None,
    search_query: str = "",
) -> tuple[Any, int]:
    """Render danh sách Lookup Type ở cột trái kèm bộ lọc tìm kiếm.

    Trả về (component_ui, total_types_count).
    """
    res = list_lookup_types(ctx)
    err = _service_message(res)
    if err:
        return (_error_state("Không tải được danh sách loại", err, "lookups-type-retry-btn"), 0)
    types = res.data if res.data else []
    total_count = len(types)

    q = (search_query or "").strip().lower()
    if q:
        filtered_types = [
            t for t in types if q in (t.get("lookup_type") or "").lower() or q in (t.get("type_name") or "").lower()
        ]
    else:
        filtered_types = types

    if not filtered_types:
        return (
            empty_state(
                title="Không có loại khớp tìm kiếm" if q else "Chưa có loại danh mục",
                description="Thử đổi từ khóa tìm kiếm hoặc bấm '+ Thêm loại'."
                if q
                else "Bấm '+ Thêm loại' để tạo nhóm đầu tiên.",
            ),
            total_count,
        )

    items = []
    for t in filtered_types:
        lt = t.get("lookup_type", "")
        is_selected = lt == selected_type
        is_sys = (t.get("is_system") or "N") == "Y"
        is_type_active = (t.get("is_active") or "Y") == "Y"
        code_count = t.get("code_count", 0)
        code_total = t.get("code_total_count", code_count)

        # Thẻ loại theo thiết kế: Paper có viền làm khung thẻ, nút bên
        # trong làm vùng bấm. Dùng dmc.Button, không dùng UnstyledButton:
        # UnstyledButton của Dash Mantine không phát n_clicks nên callback
        # chọn loại không bao giờ chạy (đã kiểm chứng bằng Playwright).
        items.append(
            dmc.Paper(
                dmc.Button(
                    id={"type": "lookups-type-item", "index": lt},
                    n_clicks=0,
                    variant="subtle",
                    color="gray",
                    fullWidth=True,
                    justify="flex-start",
                    **{
                        "aria-label": f"Chọn loại {t.get('type_name') or lt} ({lt}), {code_total} giá trị, {code_count} đang dùng"
                    },
                    style={
                        "height": "auto",
                        "textAlign": "left",
                        "padding": "0",
                        "backgroundColor": "transparent",
                        "transition": "background-color 0.15s ease",
                    },
                    children=dmc.Stack(
                        gap=4,
                        children=[
                            dmc.Text(
                                t.get("type_name") or lt,
                                size="md",
                                fw=700,
                            ),
                            dmc.Text(
                                lt,
                                size="sm",
                                c="dimmed",
                                className="rh-code mono",
                            ),
                            dmc.Group(
                                gap="xs",
                                children=[
                                    dmc.Badge(
                                        f"{code_total} giá trị · {code_count} đang dùng",
                                        size="sm",
                                        color="gray",
                                        variant="light",
                                        tt="none",
                                    ),
                                    dmc.Badge("Hệ thống", size="sm", color="blue", variant="light") if is_sys else None,
                                    dmc.Badge("Ngừng dùng", size="sm", color="gray", variant="light")
                                    if not is_type_active
                                    else None,
                                ],
                            ),
                        ],
                    ),
                ),
                withBorder=True,
                radius="md",
                p="md",
                style={
                    "backgroundColor": "var(--primary-soft)" if is_selected else "transparent",
                    "borderColor": "var(--primary)" if is_selected else None,
                    "borderWidth": "2px" if is_selected else None,
                },
            )
        )

    return dmc.Stack(items, gap="sm"), total_count


def render_policy_alert(lookup_type: str | None) -> Any:
    """Render thông báo policy theo nguyên mẫu Screen12."""
    if not lookup_type:
        return html.Div(id="lookups-policy-alert")

    is_closed = lookup_type in CLOSED_POLICY_TYPES
    if is_closed:
        return dmc.Alert(
            "Nhóm mã cố định: được sửa nhãn, màu, icon và thứ tự. Không thêm, xóa hoặc tắt mã hệ thống.",
            color="yellow",
            variant="light",
            mb="md",
            id="lookups-policy-alert",
        )
    return dmc.Alert(
        "Nhóm mở: thêm mã tùy chỉnh. Mã đã dùng chỉ nên vô hiệu hóa để giữ lịch sử.",
        color="blue",
        variant="light",
        mb="md",
        id="lookups-policy-alert",
    )


def render_code_table(
    ctx: Any,
    lookup_type: str | None,
    can_edit: bool = True,
    search_query: str = "",
    active_filter: str = "all",
) -> Any:
    """Render bảng Lookup Code ở cột phải kèm bộ lọc tìm kiếm & trạng thái."""
    if not lookup_type:
        return empty_state(
            title="Chọn loại danh mục",
            description="Bấm vào một loại danh mục ở cột trái để xem và quản lý các giá trị.",
            icon="lucide:arrow-left",
        )

    res = list_lookup_codes(ctx, lookup_type=lookup_type)
    err = _service_message(res)
    if err:
        return _error_state("Không tải được danh sách mã", err, "lookups-code-retry-btn")
    codes = res.data if res.data else []

    # Lọc theo search_query và active_filter
    q = (search_query or "").strip().lower()
    filtered_codes = []
    for c in codes:
        is_active = (c.get("is_active") or "Y") == "Y"
        code = (c.get("lookup_code") or "").lower()
        meaning = (c.get("meaning") or "").lower()

        # Lọc trạng thái
        if active_filter == "Y" and not is_active:
            continue
        if active_filter == "N" and is_active:
            continue

        # Tìm kiếm mã hoặc nhãn
        if q and q not in code and q not in meaning:
            continue

        filtered_codes.append(c)

    if not filtered_codes:
        return dmc.Stack(
            [
                empty_state(
                    title="Không có giá trị khớp" if (q or active_filter != "all") else "Chưa có giá trị nào",
                    description=(
                        "Thử đổi bộ lọc tìm kiếm hoặc trạng thái."
                        if (q or active_filter != "all")
                        else f"Bấm '+ Thêm giá trị' để tạo mã đầu tiên cho '{lookup_type}'."
                    ),
                )
            ]
        )

    headers = [
        dmc.TableTh("STT", style={"width": "44px", "textAlign": "center"}),
        dmc.TableTh("Mã Code", style={"minWidth": "140px"}),
        dmc.TableTh("Nhãn hiển thị / Badge", style={"minWidth": "220px"}),
        dmc.TableTh("Thứ tự", style={"width": "70px", "textAlign": "center"}),
        dmc.TableTh("Trạng thái", style={"width": "110px", "textAlign": "center"}),
        dmc.TableTh("Thao tác", style={"width": "90px", "textAlign": "right"}),
    ]

    rows = []
    for i, c in enumerate(filtered_codes, 1):
        code = c.get("lookup_code", "")
        meaning = c.get("meaning", "")
        color = c.get("color_badge") or "gray"
        icon = c.get("icon_name") or "lucide:circle"
        order = c.get("display_order", 0)
        is_active = (c.get("is_active") or "Y") == "Y"
        is_sys = (c.get("is_system") or "N") == "Y"

        badge_preview = dmc.Badge(
            dmc.Group(
                [
                    DashIconify(icon=icon, width=13),
                    dmc.Text(meaning, size="xs"),
                ],
                gap=4,
            ),
            color=color,
            variant="light",
            size="sm",
        )

        # Nút thật (ActionIcon) thay cho Div bấm được: tab tới được, có
        # aria-label, vùng bấm size xl của Mantine (~44px). Mã hệ thống bị
        # disabled thật nên không mở được modal xóa.
        action_btns = dmc.Group(
            gap=8,
            justify="flex-end",
            children=[
                dmc.ActionIcon(
                    DashIconify(icon="lucide:pencil", width=18),
                    id={"type": "lookups-edit-code-btn", "index": f"{lookup_type}|{code}"},
                    n_clicks=0,
                    variant="subtle",
                    color="primary",
                    size="xl",
                    **{"aria-label": f"Sửa mã {code}"},
                )
                if can_edit
                else None,
                dmc.ActionIcon(
                    DashIconify(icon="lucide:trash-2", width=18),
                    id={"type": "lookups-delete-code-btn", "index": f"{lookup_type}|{code}"},
                    n_clicks=0,
                    variant="subtle",
                    color="crit",
                    size="xl",
                    disabled=is_sys,
                    **{"aria-label": f"Mã hệ thống, không thể xóa mã {code}" if is_sys else f"Xóa mã {code}"},
                )
                if can_edit
                else None,
            ],
        )

        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(str(i), style={"textAlign": "center", "color": "var(--ink-soft)"}),
                    dmc.TableTd(
                        dmc.Group(
                            gap="xs",
                            children=[
                                dmc.Text(code, size="xs", className="rh-code mono", fw=600),
                                dmc.Badge("Hệ thống", size="xs", color="gray", variant="outline") if is_sys else None,
                            ],
                        )
                    ),
                    dmc.TableTd(badge_preview),
                    dmc.TableTd(str(order), style={"textAlign": "center"}),
                    dmc.TableTd(
                        dmc.Group(
                            gap="xs",
                            justify="center",
                            children=[
                                dmc.Switch(
                                    id={"type": "lookups-toggle-code-switch", "index": f"{lookup_type}|{code}"},
                                    checked=is_active,
                                    size="md",
                                    disabled=is_sys or not can_edit,
                                    **{
                                        "aria-label": f"Mã hệ thống, không thể tắt mã {code}"
                                        if is_sys
                                        else f"Bật hoặc tắt mã {code}"
                                    },
                                ),
                                dmc.Text("Bật" if is_active else "Tắt", size="xs", c="dimmed"),
                            ],
                        ),
                        style={"textAlign": "center"},
                    ),
                    dmc.TableTd(action_btns),
                ],
            )
        )

    return dmc.Card(
        [
            dmc.TableScrollContainer(
                minWidth=650,
                children=dmc.Table(
                    [
                        dmc.TableThead(dmc.TableTr(headers)),
                        dmc.TableTbody(rows),
                    ],
                    striped=False,
                    highlightOnHover=True,
                    withTableBorder=False,
                    withColumnBorders=False,
                    verticalSpacing="sm",
                ),
            ),
            dmc.Divider(mt="md", mb="xs"),
            dmc.Text(
                "Mã ngừng dùng vẫn hiển thị trong lịch sử, nhưng không còn trong lựa chọn tạo mới.",
                size="xs",
                c="dimmed",
                ta="left",
                p="xs",
            ),
        ],
        withBorder=True,
        radius="sm",
        padding="xs",
    )


def _modal_type_form(
    modal_id: str,
    title: str,
    lookup_type_val: str = "",
    type_name_val: str = "",
    description_val: str = "",
    readonly_code: bool = False,
) -> Any:
    """Modal Thêm / Sửa Lookup Type."""
    return dmc.Modal(
        id=modal_id,
        title=dmc.Text(title, fw=700, size="lg"),
        opened=False,
        centered=True,
        size="md",
        children=dmc.Stack(
            [
                dmc.TextInput(
                    id=f"{modal_id}-code-input",
                    label="Mã loại (LOOKUP_TYPE) *",
                    placeholder="VD: ISSUE_REASON, CURRENCY…",
                    value=lookup_type_val,
                    required=True,
                    disabled=readonly_code,
                    size="sm",
                    description="Chữ hoa, số và gạch dưới; không đổi sau khi tạo.",
                ),
                dmc.TextInput(
                    id=f"{modal_id}-name-input",
                    label="Tên hiển thị *",
                    placeholder="VD: Nguyên nhân chênh lệch",
                    value=type_name_val,
                    required=True,
                    size="sm",
                ),
                dmc.Textarea(
                    id=f"{modal_id}-desc-input",
                    label="Mô tả",
                    placeholder="Diễn giải mục đích của danh mục này…",
                    value=description_val,
                    size="sm",
                    minRows=2,
                ),
                html.Div(id=f"{modal_id}-alert"),
                dmc.Group(
                    justify="flex-end",
                    children=[
                        button_subtle("Hủy", id=f"{modal_id}-cancel-btn"),
                        button_primary("Lưu", id=f"{modal_id}-save-btn", icon="lucide:save"),
                    ],
                ),
            ],
            gap="sm",
        ),
    )


def _modal_code_form(
    modal_id: str,
    title: str,
    lookup_type_val: str = "",
    lookup_code_val: str = "",
    meaning_val: str = "",
    color_val: str = "blue",
    icon_val: str = "lucide:circle",
    order_val: int = 1,
    description_val: str = "",
    readonly_code: bool = False,
) -> Any:
    """Modal Thêm / Sửa Lookup Code."""
    color_options = [{"value": c, "label": c.capitalize()} for c in BADGE_COLORS]
    icon_options = [{"value": ic, "label": ic.replace("lucide:", "")} for ic in COMMON_ICONS]

    return dmc.Modal(
        id=modal_id,
        title=dmc.Text(title, fw=700, size="lg"),
        opened=False,
        centered=True,
        size="lg",
        children=dmc.Stack(
            [
                dmc.Group(
                    grow=True,
                    children=[
                        dmc.TextInput(
                            id=f"{modal_id}-code-input",
                            label="Mã giá trị (LOOKUP_CODE) *",
                            placeholder="VD: OPEN, ROUNDING, VND…",
                            value=lookup_code_val,
                            required=True,
                            disabled=readonly_code,
                            size="sm",
                            description="Chữ hoa, số và gạch dưới; không đổi sau khi tạo.",
                        ),
                        dmc.TextInput(
                            id=f"{modal_id}-meaning-input",
                            label="Nhãn hiển thị *",
                            placeholder="VD: Đang kiểm tra",
                            value=meaning_val,
                            required=True,
                            size="sm",
                        ),
                    ],
                ),
                dmc.Group(
                    grow=True,
                    children=[
                        dmc.Select(
                            id=f"{modal_id}-color-select",
                            label="Màu Badge",
                            data=color_options,
                            value=color_val,
                            size="sm",
                        ),
                        dmc.Select(
                            id=f"{modal_id}-icon-input",
                            label="Biểu tượng Lucide",
                            data=icon_options,
                            value=icon_val,
                            size="sm",
                        ),
                        dmc.NumberInput(
                            id=f"{modal_id}-order-input",
                            label="Thứ tự hiển thị",
                            value=order_val,
                            min=0,
                            size="sm",
                        ),
                    ],
                ),
                dmc.Textarea(
                    id=f"{modal_id}-desc-input",
                    label="Mô tả (tùy chọn)",
                    placeholder="Diễn giải chi tiết về giá trị này…",
                    value=description_val,
                    size="sm",
                    minRows=2,
                ),
                # Badge preview (được callback preview cập nhật trực tiếp
                # khi đổi nhãn/màu/icon, giống bảng thật).
                dmc.Group(
                    [
                        dmc.Text("Xem trước badge:", size="sm", c="dimmed"),
                        dmc.Badge(
                            dmc.Group(
                                [
                                    DashIconify(icon=icon_val, width=13),
                                    dmc.Text(meaning_val or "Nhãn mẫu", size="xs"),
                                ],
                                gap=4,
                            ),
                            color=color_val,
                            variant="light",
                            size="md",
                        ),
                    ],
                    id=f"{modal_id}-preview",
                    gap="xs",
                    align="center",
                ),
                html.Div(id=f"{modal_id}-alert"),
                dmc.Group(
                    justify="flex-end",
                    children=[
                        button_subtle("Hủy", id=f"{modal_id}-cancel-btn"),
                        button_primary("Lưu", id=f"{modal_id}-save-btn", icon="lucide:save"),
                    ],
                ),
                # Hidden để truyền lookup_type xuống callback
                dcc.Store(
                    id=f"{modal_id}-context-store",
                    data={"lookup_type": lookup_type_val, "lookup_code": lookup_code_val},
                ),
            ],
            gap="sm",
        ),
    )


# ─── Layout ──────────────────────────────────────────────────────────────────

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/lookups",
        title="Danh mục Lookups — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "lookup"


def layout(**kwargs: Any) -> Any:
    """Layout chính màn hình Quản lý Lookup Code & Type theo Screen12."""
    ctx = get_current_ctx()
    if ctx is None:
        return html.Div(
            [
                dcc.Location(id="lookups-forbidden-redirect", href="/login"),
                alert_box("Bạn cần đăng nhập để truy cập trang này.", tone="crit"),
            ]
        )

    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="lookups-forbidden-redirect", href=gate),
                alert_box("Chỉ quản trị viên mới có quyền quản lý danh mục Lookups.", tone="crit"),
            ]
        )

    type_list_ui, total_types_count = render_type_list(ctx, selected_type=None)
    code_table_ui = render_code_table(ctx, lookup_type=None)

    return html.Div(
        [
            dcc.Store(id="lookups-selected-type-store", data=None),
            dcc.Store(id="lookups-refresh-store", data=0),
            # Tiêu đề & mô tả màn hình
            dmc.Group(
                justify="space-between",
                align="flex-start",
                mb="md",
                children=[
                    dmc.Stack(
                        gap=4,
                        children=[
                            dmc.Title("Danh mục hệ thống", order=2),
                            dmc.Text(
                                "Quản lý nhãn, màu và biểu tượng dùng chung. Mã nghiệp vụ luôn được giữ nguyên.",
                                c="dimmed",
                                size="sm",
                            ),
                        ],
                    ),
                ],
            ),
            # Vùng thông báo chung của trang (lỗi xóa, aria-live cho
            # trình đọc màn hình). Mặc định trống.
            html.Div(id="lookups-page-alert", **{"aria-live": "polite"}),
            # Layout 2 cột
            dmc.Grid(
                gutter="md",
                children=[
                    # Cột trái (Master ~35%): Danh sách Lookup Type
                    dmc.GridCol(
                        span={"base": 12, "md": 4},
                        children=dmc.Card(
                            [
                                # Header cột trái
                                dmc.Group(
                                    justify="space-between",
                                    align="center",
                                    mb="xs",
                                    children=[
                                        dmc.Group(
                                            gap="xs",
                                            children=[
                                                dmc.Text("Loại danh mục", fw=700, size="md"),
                                                dmc.Badge(
                                                    f"{total_types_count} loại",
                                                    id="lookups-type-count-badge",
                                                    color="gray",
                                                    size="sm",
                                                    variant="light",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                # Ô tìm kiếm Type, có nhãn như thiết kế
                                dmc.TextInput(
                                    id="lookups-type-search-input",
                                    label="Tìm loại danh mục",
                                    placeholder="Tên hoặc mã loại...",
                                    leftSection=DashIconify(icon="lucide:search", width=14),
                                    size="sm",
                                    mb="sm",
                                ),
                                # Danh sách Type
                                html.Div(
                                    id="lookups-type-list",
                                    children=type_list_ui,
                                ),
                                # Nút thêm loại ở cuối cột trái như thiết kế,
                                # thay cho nút ở header trước đây. Id giữ
                                # nguyên để callback mở modal không đổi.
                                dmc.Button(
                                    "+ Thêm loại danh mục",
                                    id="lookups-add-type-btn",
                                    variant="outline",
                                    color="gray",
                                    fullWidth=True,
                                    size="sm",
                                    mt="sm",
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            padding="md",
                            style={"minHeight": "520px"},
                        ),
                    ),
                    # Cột phải (Detail ~65%): Bảng Lookup Code
                    dmc.GridCol(
                        span={"base": 12, "md": 8},
                        children=dmc.Card(
                            [
                                # Header cột phải
                                dmc.Group(
                                    justify="space-between",
                                    align="center",
                                    mb="xs",
                                    children=[
                                        dmc.Group(
                                            gap="xs",
                                            align="center",
                                            children=[
                                                dmc.Text(
                                                    id="lookups-code-header",
                                                    children="Chọn loại danh mục ở cột trái",
                                                    fw=700,
                                                    size="md",
                                                ),
                                                dmc.Badge(
                                                    id="lookups-code-type-badge",
                                                    children="",
                                                    color="gray",
                                                    size="xs",
                                                    variant="outline",
                                                    style={"display": "none"},
                                                ),
                                            ],
                                        ),
                                        dmc.Group(
                                            gap="xs",
                                            children=[
                                                button_subtle(
                                                    "Sửa loại",
                                                    id="lookups-edit-type-btn",
                                                    size="xs",
                                                    icon="lucide:pencil",
                                                    disabled=True,
                                                ),
                                                button_primary(
                                                    "Thêm giá trị",
                                                    id="lookups-add-code-btn",
                                                    size="xs",
                                                    icon="lucide:plus",
                                                    disabled=True,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                # Alert policy
                                html.Div(id="lookups-policy-alert-container", children=render_policy_alert(None)),
                                # Toolbar: Tìm kiếm Code & Lọc trạng thái
                                dmc.Group(
                                    align="flex-end",
                                    gap="xs",
                                    mb="sm",
                                    children=[
                                        dmc.TextInput(
                                            id="lookups-code-search-input",
                                            placeholder="Tìm mã hoặc nhãn…",
                                            leftSection=DashIconify(icon="lucide:search", width=14),
                                            size="xs",
                                            style={"flex": 1, "minWidth": "160px"},
                                        ),
                                        dmc.Select(
                                            id="lookups-code-active-filter",
                                            data=[
                                                {"value": "all", "label": "Tất cả trạng thái"},
                                                {"value": "Y", "label": "Đang dùng"},
                                                {"value": "N", "label": "Ngừng dùng"},
                                            ],
                                            value="all",
                                            size="xs",
                                            style={"width": "150px"},
                                        ),
                                    ],
                                ),
                                dmc.Divider(mb="xs"),
                                # Bảng Code
                                html.Div(
                                    id="lookups-code-table",
                                    children=code_table_ui,
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            padding="md",
                            style={"minHeight": "520px"},
                        ),
                    ),
                ],
            ),
            # Modal Thêm Lookup Type
            _modal_type_form("lookups-add-type-modal", "Thêm loại danh mục mới"),
            # Modal Sửa Lookup Type
            _modal_type_form("lookups-edit-type-modal", "Sửa loại danh mục", readonly_code=True),
            # Modal Thêm Lookup Code
            _modal_code_form("lookups-add-code-modal", "Thêm giá trị mới"),
            # Modal Sửa Lookup Code
            _modal_code_form("lookups-edit-code-modal", "Sửa giá trị", readonly_code=True),
            # Modal Xác nhận xóa
            modal_confirm(
                id="lookups-delete-code-modal",
                title="Xác nhận xóa giá trị",
                description="Bạn có chắc muốn xóa mã này? Nếu mã đã được dùng trong dữ liệu đối soát, hệ thống sẽ tự động vô hiệu hóa thay vì xóa hoàn toàn để bảo toàn lịch sử.",
                confirm_label="Xác nhận",
                cancel_label="Hủy",
                danger=True,
                opened=False,
            ),
            dcc.Store(id="lookups-delete-target-store", data=None),
        ],
        style={"padding": "24px"},
    )


# ─── Callbacks ───────────────────────────────────────────────────────────────


def handle_select_type(selected_type: str | None) -> tuple[Any, str | None]:
    """Hàm thuần xử lý chọn Lookup Type ở cột trái — trả (code_table_ui, selected_store)."""
    ctx = get_current_ctx()
    if not ctx or not selected_type:
        return render_code_table(None, lookup_type=None), None
    code_table = render_code_table(ctx, lookup_type=selected_type)
    return code_table, selected_type


@callback(
    Output("lookups-code-table", "children"),
    Output("lookups-selected-type-store", "data"),
    Output("lookups-code-header", "children"),
    Output("lookups-code-type-badge", "children"),
    Output("lookups-code-type-badge", "style"),
    Output("lookups-add-code-btn", "disabled"),
    Output("lookups-edit-type-btn", "disabled"),
    Output("lookups-policy-alert-container", "children"),
    Output("lookups-type-list", "children"),
    Output("lookups-type-count-badge", "children"),
    Input({"type": "lookups-type-item", "index": dash.ALL}, "n_clicks"),
    Input("lookups-refresh-store", "data"),
    Input("lookups-type-search-input", "value"),
    Input("lookups-code-search-input", "value"),
    Input("lookups-code-active-filter", "value"),
    State("lookups-selected-type-store", "data"),
    prevent_initial_call=True,
)
def cb_master_detail_sync(
    _clicks: list[int | None],
    _refresh: int | None,
    type_search: str | None,
    code_search: str | None,
    active_filter: str | None,
    current_selected: str | None,
) -> tuple[Any, str | None, str, str, dict[str, str], bool, bool, Any, Any, str]:
    """Đồng bộ Master–Detail: chọn type, tìm kiếm, lọc trạng thái, refresh."""
    ctx = get_current_ctx()
    ctx_dash = dash.callback_context
    triggered = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""

    selected_type = current_selected
    # Guard: khi danh sách loại được render lại (tìm kiếm/refresh), Dash
    # có thể kích hoạt callback với n_clicks=0 của nút mới xuất hiện.
    # Chỉ coi là bấm chọn khi giá trị kích hoạt > 0.
    _triggered_value = ctx_dash.triggered[0].get("value") if ctx_dash.triggered else None
    if "lookups-type-item" in triggered and _triggered_value:
        try:
            id_dict = json.loads(triggered.split(".")[0])
            selected_type = id_dict.get("index")
        except Exception:
            pass

    # Render danh sách Type (cột trái)
    type_list_ui, total_types_count = render_type_list(
        ctx,
        selected_type=selected_type,
        search_query=type_search or "",
    )

    # Render bảng Code (cột phải)
    code_table_ui = render_code_table(
        ctx,
        lookup_type=selected_type,
        search_query=code_search or "",
        active_filter=active_filter or "all",
    )

    policy_ui = render_policy_alert(selected_type)

    if selected_type:
        # Tiêu đề dùng tên hiển thị, badge giữ mã để phân biệt.
        type_name = selected_type
        if ctx:
            _types_res = list_lookup_types(ctx)
            if _types_res.ok and _types_res.data:
                _found = next(
                    (t for t in _types_res.data if t.get("lookup_type") == selected_type),
                    None,
                )
                if _found and _found.get("type_name"):
                    type_name = _found["type_name"]
        header = f"{type_name} ({selected_type})"
        badge_text = selected_type
        badge_style = {"display": "inline-flex"}
        is_closed = selected_type in CLOSED_POLICY_TYPES
        add_disabled = is_closed  # Nhóm cố định không cho thêm mã mới
        edit_type_disabled = False
    else:
        header = "Chọn loại danh mục ở cột trái"
        badge_text = ""
        badge_style = {"display": "none"}
        add_disabled = True
        edit_type_disabled = True

    count_badge_text = f"{total_types_count} loại"

    return (
        code_table_ui,
        selected_type,
        header,
        badge_text,
        badge_style,
        add_disabled,
        edit_type_disabled,
        policy_ui,
        type_list_ui,
        count_badge_text,
    )


# --- Modal Thêm Lookup Type ---


@callback(
    Output("lookups-add-type-modal", "opened"),
    Output("lookups-add-type-modal-alert", "children"),
    Input("lookups-add-type-btn", "n_clicks"),
    Input("lookups-add-type-modal-cancel-btn", "n_clicks"),
    Input("lookups-add-type-modal-save-btn", "n_clicks"),
    State("lookups-add-type-modal-code-input", "value"),
    State("lookups-add-type-modal-name-input", "value"),
    State("lookups-add-type-modal-desc-input", "value"),
    prevent_initial_call=True,
)
def cb_add_type_modal(
    open_clicks: int | None,
    cancel_clicks: int | None,
    save_clicks: int | None,
    code_val: str | None,
    name_val: str | None,
    desc_val: str | None,
) -> tuple[bool, Any]:
    ctx_dash = dash.callback_context
    triggered = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""
    if "lookups-add-type-btn" in triggered:
        return True, None
    if "cancel" in triggered:
        return False, None
    if "save" in triggered:
        ctx = get_current_ctx()
        if not ctx or not code_val or not name_val:
            return True, alert_box("Chưa lưu được", "Vui lòng nhập mã loại và tên hiển thị.", tone="crit")
        res = create_lookup_type(ctx, lookup_type=code_val, type_name=name_val, description=desc_val)
        err = _service_message(res)
        if err:
            # Giữ modal mở và giữ dữ liệu đã nhập, hiện lỗi gần nút Lưu.
            return True, alert_box("Chưa lưu được", err, tone="crit")
        return False, None
    return False, None


# --- Modal Sửa Lookup Type ---


@callback(
    Output("lookups-edit-type-modal", "opened"),
    Output("lookups-edit-type-modal-code-input", "value"),
    Output("lookups-edit-type-modal-name-input", "value"),
    Output("lookups-edit-type-modal-desc-input", "value"),
    Output("lookups-edit-type-modal-alert", "children"),
    Input("lookups-edit-type-btn", "n_clicks"),
    Input("lookups-edit-type-modal-cancel-btn", "n_clicks"),
    Input("lookups-edit-type-modal-save-btn", "n_clicks"),
    State("lookups-selected-type-store", "data"),
    State("lookups-edit-type-modal-name-input", "value"),
    State("lookups-edit-type-modal-desc-input", "value"),
    prevent_initial_call=True,
)
def cb_edit_type_modal(
    open_clicks: int | None,
    cancel_clicks: int | None,
    save_clicks: int | None,
    selected_type: str | None,
    name_val: str | None,
    desc_val: str | None,
) -> tuple[bool, str, str, str, Any]:
    ctx_dash = dash.callback_context
    triggered = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""

    if "lookups-edit-type-btn" in triggered:
        if not selected_type:
            return False, "", "", "", None
        ctx = get_current_ctx()
        if not ctx:
            return False, "", "", "", None
        res = list_lookup_types(ctx)
        types = res.data if res.ok and res.data else []
        found = next((t for t in types if t.get("lookup_type") == selected_type), None)
        if not found:
            return False, "", "", "", None
        return (
            True,
            found.get("lookup_type", ""),
            found.get("type_name", ""),
            found.get("description") or "",
            None,
        )

    if "cancel" in triggered:
        return False, "", "", "", None

    if "save" in triggered:
        ctx = get_current_ctx()
        if not ctx or not selected_type or not name_val:
            return (
                True,
                selected_type or "",
                name_val or "",
                desc_val or "",
                alert_box("Chưa lưu được", "Vui lòng nhập tên hiển thị.", tone="crit"),
            )
        res = update_lookup_type(ctx, lookup_type=selected_type, type_name=name_val, description=desc_val)
        err = _service_message(res)
        if err:
            return True, selected_type, name_val, desc_val or "", alert_box("Chưa lưu được", err, tone="crit")
        return False, "", "", "", None

    return False, "", "", "", None


# --- Refresh Store Trigger ---


@callback(
    Output("lookups-refresh-store", "data"),
    Input("lookups-add-type-modal", "opened"),
    Input("lookups-edit-type-modal", "opened"),
    Input("lookups-add-code-modal", "opened"),
    Input("lookups-edit-code-modal", "opened"),
    Input("lookups-delete-code-modal", "opened"),
    State("lookups-refresh-store", "data"),
    prevent_initial_call=True,
)
def cb_trigger_refresh(
    type_add_modal: bool | None,
    type_edit_modal: bool | None,
    add_code_modal: bool | None,
    edit_code_modal: bool | None,
    delete_code_modal: bool | None,
    current_refresh: int | None,
) -> Any:
    """Khi bất kỳ modal nào đóng lại → tăng counter refresh để cập nhật UI."""
    ctx_dash = dash.callback_context
    val = current_refresh or 0
    triggered_val = ctx_dash.triggered[0]["value"] if ctx_dash.triggered else None
    if triggered_val is False:
        return val + 1
    return dash.no_update


# --- Badge preview trực tiếp trong modal code ---
# Prototype cập nhật preview ngay khi nhập; trước đây preview chỉ dựng
# một lần với giá trị ban đầu nên đổi màu/icon không thấy gì cho tới khi lưu.


def _live_badge_preview(meaning_val: str | None, color_val: str | None, icon_val: str | None) -> Any:
    return dmc.Group(
        [
            dmc.Text("Xem trước badge:", size="sm", c="dimmed"),
            dmc.Badge(
                dmc.Group(
                    [
                        DashIconify(icon=icon_val or "lucide:circle", width=13),
                        dmc.Text(meaning_val or "Nhãn mẫu", size="xs"),
                    ],
                    gap=4,
                ),
                color=color_val or "gray",
                variant="light",
                size="md",
            ),
        ],
        gap="xs",
        align="center",
    )


@callback(
    Output("lookups-add-code-modal-preview", "children"),
    Input("lookups-add-code-modal-meaning-input", "value"),
    Input("lookups-add-code-modal-color-select", "value"),
    Input("lookups-add-code-modal-icon-input", "value"),
    prevent_initial_call=True,
)
def cb_add_code_preview(meaning_val: str | None, color_val: str | None, icon_val: str | None) -> Any:
    return _live_badge_preview(meaning_val, color_val, icon_val)


@callback(
    Output("lookups-edit-code-modal-preview", "children"),
    Input("lookups-edit-code-modal-meaning-input", "value"),
    Input("lookups-edit-code-modal-color-select", "value"),
    Input("lookups-edit-code-modal-icon-input", "value"),
    prevent_initial_call=True,
)
def cb_edit_code_preview(meaning_val: str | None, color_val: str | None, icon_val: str | None) -> Any:
    return _live_badge_preview(meaning_val, color_val, icon_val)


# --- Modal Thêm Lookup Code ---


@callback(
    Output("lookups-add-code-modal", "opened"),
    Output("lookups-add-code-modal-context-store", "data"),
    Output("lookups-add-code-modal-alert", "children"),
    Input("lookups-add-code-btn", "n_clicks"),
    Input("lookups-add-code-modal-cancel-btn", "n_clicks"),
    Input("lookups-add-code-modal-save-btn", "n_clicks"),
    State("lookups-selected-type-store", "data"),
    State("lookups-add-code-modal-code-input", "value"),
    State("lookups-add-code-modal-meaning-input", "value"),
    State("lookups-add-code-modal-order-input", "value"),
    State("lookups-add-code-modal-color-select", "value"),
    State("lookups-add-code-modal-icon-input", "value"),
    State("lookups-add-code-modal-desc-input", "value"),
    prevent_initial_call=True,
)
def cb_add_code_modal(
    open_clicks: int | None,
    cancel_clicks: int | None,
    save_clicks: int | None,
    lookup_type: str | None,
    code_val: str | None,
    meaning_val: str | None,
    order_val: int | None,
    color_val: str | None,
    icon_val: str | None,
    desc_val: str | None,
) -> tuple[bool, dict[str, Any]]:
    ctx_dash = dash.callback_context
    triggered = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""
    context = {"lookup_type": lookup_type, "lookup_code": None}
    if "lookups-add-code-btn" in triggered:
        return True, context, None
    if "cancel" in triggered:
        return False, context, None
    if "save" in triggered:
        ctx = get_current_ctx()
        if not ctx or not lookup_type or not code_val or not meaning_val:
            return True, context, alert_box("Chưa lưu được", "Vui lòng nhập mã giá trị và nhãn hiển thị.", tone="crit")
        res = create_lookup_code(
            ctx,
            lookup_type=lookup_type,
            lookup_code=code_val,
            meaning=meaning_val,
            display_order=int(order_val or 0),
            color_badge=color_val,
            icon_name=icon_val,
            description=desc_val,
        )
        err = _service_message(res)
        if err:
            return True, context, alert_box("Chưa lưu được", err, tone="crit")
        return False, context, None
    return False, context, None


# --- Modal Sửa Lookup Code ---


@callback(
    Output("lookups-edit-code-modal", "opened"),
    Output("lookups-edit-code-modal-code-input", "value"),
    Output("lookups-edit-code-modal-meaning-input", "value"),
    Output("lookups-edit-code-modal-order-input", "value"),
    Output("lookups-edit-code-modal-color-select", "value"),
    Output("lookups-edit-code-modal-icon-input", "value"),
    Output("lookups-edit-code-modal-desc-input", "value"),
    Output("lookups-edit-code-modal-context-store", "data"),
    Output("lookups-edit-code-modal-alert", "children"),
    Input({"type": "lookups-edit-code-btn", "index": dash.ALL}, "n_clicks"),
    Input("lookups-edit-code-modal-cancel-btn", "n_clicks"),
    Input("lookups-edit-code-modal-save-btn", "n_clicks"),
    State("lookups-edit-code-modal-meaning-input", "value"),
    State("lookups-edit-code-modal-order-input", "value"),
    State("lookups-edit-code-modal-color-select", "value"),
    State("lookups-edit-code-modal-icon-input", "value"),
    State("lookups-edit-code-modal-desc-input", "value"),
    State("lookups-edit-code-modal-context-store", "data"),
    prevent_initial_call=True,
)
def cb_edit_code_modal(
    _edit_clicks: list[int | None],
    _cancel: int | None,
    _save: int | None,
    meaning_val: str | None,
    order_val: int | None,
    color_val: str | None,
    icon_val: str | None,
    desc_val: str | None,
    context: dict[str, Any] | None,
) -> tuple[bool, str, str, int, str, str, str, dict[str, Any], Any]:
    ctx_dash = dash.callback_context
    triggered = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""
    empty_ctx: dict[str, Any] = {"lookup_type": None, "lookup_code": None}

    if "lookups-edit-code-btn" in triggered:
        _edit_triggered_value = ctx_dash.triggered[0].get("value") if ctx_dash.triggered else None
        if not _edit_triggered_value:
            # Bảng vừa render lại, nút Sửa mới xuất hiện với n_clicks=0:
            # không phải người dùng bấm, không được tự mở modal.
            return False, "", "", 0, "gray", "lucide:tag", "", empty_ctx, None
        try:
            id_dict = json.loads(triggered.split(".")[0])
            idx = id_dict.get("index", "")
            parts = idx.split("|", 1)
            lt, code = parts[0], parts[1] if len(parts) > 1 else ""
        except Exception:
            return False, "", "", 0, "gray", "lucide:tag", "", empty_ctx, None

        user_ctx = get_current_ctx()
        if not user_ctx:
            return False, "", "", 0, "gray", "lucide:tag", "", empty_ctx, None

        res = list_lookup_codes(user_ctx, lookup_type=lt)
        codes = res.data if res.ok and res.data else []
        found = next((c for c in codes if c.get("lookup_code") == code), None)
        if not found:
            return False, "", "", 0, "gray", "lucide:tag", "", empty_ctx, None

        return (
            True,
            found.get("lookup_code", ""),
            found.get("meaning", ""),
            int(found.get("display_order") or 0),
            found.get("color_badge") or "gray",
            found.get("icon_name") or "lucide:circle",
            found.get("description") or "",
            {"lookup_type": lt, "lookup_code": code},
            None,
        )

    if "cancel" in triggered:
        return False, "", "", 0, "gray", "lucide:tag", "", empty_ctx, None

    if "save" in triggered:
        user_ctx = get_current_ctx()
        ctx_data = context or {}
        lt = ctx_data.get("lookup_type")
        code = ctx_data.get("lookup_code")
        if not user_ctx or not lt or not code:
            return (
                True,
                code or "",
                meaning_val or "",
                int(order_val or 0),
                color_val or "gray",
                icon_val or "lucide:circle",
                desc_val or "",
                ctx_data,
                alert_box("Chưa lưu được", "Không xác định được mã cần sửa.", tone="crit"),
            )
        res = update_lookup_code(
            user_ctx,
            lookup_type=lt,
            lookup_code=code,
            meaning=meaning_val,
            display_order=int(order_val or 0),
            color_badge=color_val,
            icon_name=icon_val,
            description=desc_val,
        )
        err = _service_message(res)
        if err:
            return (
                True,
                code,
                meaning_val or "",
                int(order_val or 0),
                color_val or "gray",
                icon_val or "lucide:circle",
                desc_val or "",
                ctx_data,
                alert_box("Chưa lưu được", err, tone="crit"),
            )
        return False, "", "", 0, "gray", "lucide:tag", "", empty_ctx, None, None

    return False, "", "", 0, "gray", "lucide:tag", "", empty_ctx, None


# --- Switch Toggle Active ---


@callback(
    Output({"type": "lookups-toggle-code-switch", "index": dash.MATCH}, "checked"),
    Input({"type": "lookups-toggle-code-switch", "index": dash.MATCH}, "checked"),
    prevent_initial_call=True,
)
def cb_toggle_code(checked: bool) -> bool:
    ctx_dash = dash.callback_context
    triggered = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""
    user_ctx = get_current_ctx()
    if not user_ctx:
        return not checked  # rollback
    try:
        id_dict = json.loads(triggered.split(".")[0])
        idx = id_dict.get("index", "")
        parts = idx.split("|", 1)
        lt, code = parts[0], parts[1] if len(parts) > 1 else ""
        res = toggle_lookup_code_status(user_ctx, lookup_type=lt, lookup_code=code, is_active=checked)
        if _service_message(res):
            return not checked  # rollback khi service trả fail
    except Exception:
        return not checked  # rollback nếu lỗi
    return checked


# --- Nút Xóa Code ---


@callback(
    Output("lookups-delete-code-modal", "opened"),
    Output("lookups-delete-target-store", "data"),
    Output("lookups-page-alert", "children"),
    Input({"type": "lookups-delete-code-btn", "index": dash.ALL}, "n_clicks"),
    Input("lookups-delete-code-modal-cancel-btn", "n_clicks"),
    Input("lookups-delete-code-modal-confirm-btn", "n_clicks"),
    State("lookups-delete-target-store", "data"),
    prevent_initial_call=True,
)
def cb_delete_code_modal(
    _delete_clicks: list[int | None],
    _cancel: int | None,
    _confirm: int | None,
    target_store: dict[str, Any] | None,
) -> tuple[bool, dict[str, Any] | None, Any]:
    ctx_dash = dash.callback_context
    triggered = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""

    if "lookups-delete-code-btn" in triggered:
        _del_triggered_value = ctx_dash.triggered[0].get("value") if ctx_dash.triggered else None
        if not _del_triggered_value:
            return False, None, None
        try:
            id_dict = json.loads(triggered.split(".")[0])
            idx = id_dict.get("index", "")
            parts = idx.split("|", 1)
            lt, code = parts[0], parts[1] if len(parts) > 1 else ""
            return True, {"lookup_type": lt, "lookup_code": code}, None
        except Exception:
            return False, None, None

    if "cancel" in triggered:
        return False, None, None

    if "confirm" in triggered:
        user_ctx = get_current_ctx()
        if user_ctx and target_store:
            res = delete_lookup_code(
                user_ctx,
                lookup_type=target_store.get("lookup_type", ""),
                lookup_code=target_store.get("lookup_code", ""),
            )
            err = _service_message(res)
            if err:
                # Giữ modal mở? Modal xác nhận không có ô alert, nên đóng
                # modal và hiện lỗi ở vùng thông báo chung của trang để
                # người dùng thấy rõ, dữ liệu không bị xóa.
                return False, None, alert_box("Chưa xóa được", err, tone="crit")
        return False, None, None

    return False, None, None
