from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.schemas.run import RunListFilter
from app.services.perm import is_admin, page_gate
from app.services.run_service import list_runs
from app.services.temp_data import purge_runs
from app.services.template import list_templates
from app.services.user import list_users
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.status_chip import status_chip
from app.ui.formatters import format_bytes

try:
    dash.register_page(__name__, path="/history", title="Lịch sử – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "history"


def format_short_dt(iso_str: str | None) -> str:
    """Định dạng ngày giờ ngắn gọn DD/MM HH:mm."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return str(iso_str)


def format_date_range(p_from: str | None, p_to: str | None) -> str:
    """Định dạng khoảng ngày giờ: 01/02 00:00 → 05/02 23:59."""
    f_str = format_short_dt(p_from)
    t_str = format_short_dt(p_to)
    if f_str == "—" and t_str == "—":
        return "—"
    return f"{f_str} → {t_str}"


def render_header(count: int, month_year: str = "") -> dmc.Stack:
    """Tiêu đề H1 và phụ đề màn hình Lịch sử."""
    my = month_year or datetime.now().strftime("tháng %m/%Y")
    title_text = f"Lịch sử: {count} run trong {my}"
    return dmc.Stack(
        [
            dmc.Title(title_text, order=1, id="history-title"),
            dmc.Text(
                "Truy vết file gốc, version, khoảng tìm kiếm, người chạy. Chọn nhiều run để xóa dữ liệu tạm (Admin).",
                c="dimmed",
                size="sm",
            ),
        ],
        gap=4,
    )


def render_filter_bar(
    templates_options: list[dict[str, str]],
    users_options: list[dict[str, str]],
) -> dmc.Group:
    """Thanh bộ lọc 6 tiêu chí theo thiết kế Screen07 (có tìm kiếm theo thời gian chạy)."""
    now = datetime.now()
    first_day = now.replace(day=1).strftime("%Y-%m-%d")
    _, last_day_num = calendar.monthrange(now.year, now.month)
    last_day = now.replace(day=last_day_num).strftime("%Y-%m-%d")

    return dmc.Group(
        [
            dmc.DatePickerInput(
                id="history-filter-date-range",
                type="range",
                label="Thời gian chạy",
                value=[first_day, last_day],
                valueFormat="DD/MM/YYYY",
                clearable=True,
                w=220,
            ),
            dmc.Select(
                id="history-filter-template",
                label="Template",
                placeholder="Tất cả",
                data=[{"label": "Tất cả", "value": "ALL"}, *templates_options],
                value="ALL",
                w=200,
                clearable=False,
            ),
            dmc.Select(
                id="history-filter-checked",
                label="Kiểm tra",
                data=[
                    {"label": "Tất cả", "value": "ALL"},
                    {"label": "Chưa kiểm tra", "value": "UNCHECKED"},
                    {"label": "Đã kiểm tra", "value": "CHECKED"},
                ],
                value="ALL",
                w=160,
                clearable=False,
            ),
            dmc.Select(
                id="history-filter-purged",
                label="Dữ liệu tạm",
                data=[
                    {"label": "Tất cả", "value": "ALL"},
                    {"label": "Còn", "value": "RETAINED"},
                    {"label": "Đã xóa", "value": "PURGED"},
                ],
                value="ALL",
                w=150,
                clearable=False,
            ),
            dmc.Select(
                id="history-filter-user",
                label="Người chạy",
                placeholder="Tất cả",
                data=[{"label": "Tất cả", "value": "ALL"}, *users_options],
                value="ALL",
                w=160,
                clearable=False,
            ),
            dmc.TextInput(
                id="history-filter-filename",
                label="Tên file",
                placeholder="Tìm theo tên file",
                leftSection=DashIconify(icon="lucide:search", width=14),
                w=200,
            ),
        ],
        gap="md",
        align="flex-end",
    )


def render_bulk_alert(selected_count: int, is_admin: bool) -> html.Div:
    """Thanh cảnh báo thông tin chọn nhiều run kèm nút xóa dữ liệu tạm."""
    is_visible = is_admin and selected_count > 0
    return html.Div(
        id="history-bulk-alert",
        style={"display": "block" if is_visible else "none"},
        children=[
            dmc.Alert(
                id="history-bulk-alert-box",
                title=None,
                color="blue",
                variant="light",
                icon=DashIconify(icon="lucide:info", width=18),
                children=dmc.Group(
                    [
                        dmc.Text(
                            ["Đã chọn ", html.B(str(selected_count)), " run."],
                            id="history-bulk-text",
                            size="sm",
                        ),
                        button_danger(
                            "Xóa dữ liệu tạm",
                            id="history-open-bulk-modal-btn",
                            size="xs",
                            icon="lucide:trash-2",
                        ),
                    ],
                    justify="space-between",
                    align="center",
                    w="100%",
                ),
            )
        ],
    )


def render_runs_table(
    items: list[dict[str, Any]],
    is_admin: bool,
    selected_ids: set[int],
    total: int = 0,
    current_page: int = 1,
    page_size: int = 20,
    total_pages: int = 1,
) -> Any:
    """Dựng bảng lịch sử run kèm phân trang theo thiết kế Screen07."""
    if not items:
        return empty_state(
            title="Chưa có run nào",
            description="Các lần chạy sẽ hiện ở đây kèm file gốc và tham số.",
            action=dmc.Anchor(
                button_primary("Chạy đối soát", icon="lucide:play"),
                href="/runs/new",
            ),
        )

    # Header hàng
    headers = []
    if is_admin:
        # Checkbox Chọn tất cả (chỉ áp dụng với các run chưa xóa tạm)
        unpurged_runs = [r["id"] for r in items if not r.get("temp_purged_at")]
        all_checked = bool(unpurged_runs) and all(r_id in selected_ids for r_id in unpurged_runs)
        headers.append(
            dmc.TableTh(
                dmc.Center(
                    dmc.Checkbox(
                        id="history-select-all-cb",
                        checked=all_checked,
                        disabled=len(unpurged_runs) == 0,
                        size="sm",
                        style={"cursor": "pointer" if unpurged_runs else "default"},
                        **{"aria-label": "Chọn tất cả run chưa xóa dữ liệu tạm"},
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
            dmc.TableTh("Run", style={"minWidth": "80px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Thời gian chạy", style={"minWidth": "110px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Template", style={"minWidth": "150px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Profile", style={"minWidth": "110px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Khoảng tìm kiếm", style={"minWidth": "160px", "whiteSpace": "nowrap"}),
            dmc.TableTh("File", style={"minWidth": "160px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Người chạy", style={"minWidth": "100px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Trạng thái", style={"minWidth": "120px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Khớp", style={"minWidth": "80px", "textAlign": "right", "whiteSpace": "nowrap"}),
            dmc.TableTh("Kiểm tra", style={"minWidth": "130px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Dữ liệu tạm", style={"minWidth": "150px", "whiteSpace": "nowrap"}),
            dmc.TableTh("Thao tác", style={"minWidth": "110px", "textAlign": "right", "whiteSpace": "nowrap"}),
        ]
    )

    rows = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for r in items:
        r_id = r["id"]
        is_purged = bool(r.get("temp_purged_at"))
        is_selected = r_id in selected_ids

        tds = []
        if is_admin:
            tds.append(
                dmc.TableTd(
                    dmc.Center(
                        dmc.Checkbox(
                            id={"type": "history-run-cb", "index": r_id},
                            checked=is_selected and not is_purged,
                            disabled=is_purged,
                            size="sm",
                            style={"cursor": "pointer" if not is_purged else "default"},
                            **{"aria-label": f"Chọn run #{r_id}"},
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

        # Run ID
        tds.append(
            dmc.TableTd(
                dmc.Anchor(
                    f"#{r_id}",
                    href=f"/runs/{r_id}",
                    className="rh-code",
                    fw=600,
                    underline="hover",
                ),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Thời gian chạy
        tds.append(
            dmc.TableTd(
                format_short_dt(r.get("created_at")),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Template code + ver
        ver_text = f" v{r['template_version']}" if r.get("template_version") else ""
        t_code = r.get("template_code") or r.get("template_name") or "Template"
        tds.append(
            dmc.TableTd(
                f"{t_code}{ver_text}",
                className="rh-code",
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Profile code
        tds.append(
            dmc.TableTd(
                r.get("profile_code") or "—",
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Khoảng tìm kiếm
        tds.append(
            dmc.TableTd(
                format_date_range(r.get("p_from"), r.get("p_to")),
                className="rh-code",
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # File gốc
        f_name = r.get("filename") or "—"
        tds.append(
            dmc.TableTd(
                dmc.Tooltip(
                    label=f_name,
                    children=dmc.Text(
                        f_name,
                        size="sm",
                        style={
                            "maxWidth": "180px",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "whiteSpace": "nowrap",
                        },
                    ),
                    multiline=True,
                    withArrow=True,
                )
                if f_name != "—"
                else dmc.Text("—", size="sm", c="dimmed"),
                style={"maxWidth": "180px", "verticalAlign": "middle"},
            )
        )

        # Người chạy
        tds.append(
            dmc.TableTd(
                r.get("created_by") or "—",
                className="rh-code",
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )

        # Trạng thái run
        status_val = r.get("status", "QUEUED")
        has_diff = (
            (r.get("cnt_mismatch", 0) > 0)
            or (r.get("cnt_missing_in_db", 0) > 0)
            or (r.get("cnt_missing_in_excel", 0) > 0)
        )
        if status_val == "DONE":
            if has_diff:
                chip_node = status_chip("MISMATCH", label="Có lệch", icon="lucide:flag")
            else:
                chip_node = status_chip("MATCHED", label="Khớp", icon="lucide:check")
        elif status_val == "RUNNING":
            pct = r.get("progress_pct", 0)
            chip_node = status_chip("RUNNING", label=f"Đang chạy {pct}%", icon="lucide:loader")
        elif status_val == "FAILED":
            chip_node = status_chip("FAILED", label="Lỗi", icon="lucide:alert-triangle")
        else:
            chip_node = status_chip(status_val)
        tds.append(dmc.TableTd(chip_node, style={"whiteSpace": "nowrap", "verticalAlign": "middle"}))

        # % Khớp
        match_pct = r.get("match_pct")
        if match_pct is not None and status_val == "DONE":
            pct_fmt = f"{match_pct:.1f}%".replace(".", ",")
            pct_node = dmc.Text(pct_fmt, size="sm", fw=500, style={"textAlign": "right"})
        else:
            pct_node = dmc.Text("—", size="sm", c="dimmed", style={"textAlign": "right"})
        tds.append(dmc.TableTd(pct_node, style={"whiteSpace": "nowrap", "verticalAlign": "middle"}))

        # Trạng thái kiểm tra
        if r.get("checked_at"):
            chk_user = r.get("checked_by") or ""
            label_chk = f"Đã kiểm tra · {chk_user}" if chk_user else "Đã kiểm tra"
            chk_chip = status_chip("CHECKED", label=label_chk, icon="lucide:check")
        else:
            chk_chip = status_chip("UNCHECKED", label="Chưa kiểm tra", icon="lucide:circle")
        tds.append(dmc.TableTd(chk_chip, style={"whiteSpace": "nowrap", "verticalAlign": "middle"}))

        # Trạng thái dữ liệu tạm
        if is_purged:
            purged_date = format_short_dt(r.get("temp_purged_at")).split(" ")[0]
            temp_chip = status_chip("PURGED", label=f"Đã xóa {purged_date}", icon="lucide:trash-2")
        else:
            sz_fmt = format_bytes(r.get("file_size") or (1024 * 1024 * 3))
            created_dt = None
            if r.get("created_at"):
                try:
                    created_dt = datetime.fromisoformat(r["created_at"])
                except Exception:
                    pass
            days_old = (now - created_dt).days if created_dt else 0
            if days_old >= 30:
                temp_label = f"Còn {days_old} ngày · {sz_fmt}"
            else:
                temp_label = f"Còn · {sz_fmt}"
            temp_chip = status_chip("RETAINED", label=temp_label, icon="lucide:database")
        tds.append(dmc.TableTd(temp_chip, style={"whiteSpace": "nowrap", "verticalAlign": "middle"}))

        # Nút thao tác
        actions_group = [
            dmc.Anchor(
                button_subtle("Xem", size="xs"),
                href=f"/runs/{r_id}",
            )
        ]
        if not is_purged and r.get("file_id"):
            actions_group.append(
                dmc.Anchor(
                    button_subtle("Tải", size="xs", icon="lucide:download"),
                    href=f"/download/file/{r['file_id']}",
                )
            )

        tds.append(
            dmc.TableTd(
                dmc.Group(actions_group, gap=4, justify="flex-end"),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
            )
        )
        rows.append(dmc.TableTr(tds))

    # Thanh phân trang ở chân bảng
    start_idx = (current_page - 1) * page_size + 1 if total > 0 else 0
    end_idx = min(current_page * page_size, total)

    pagination_bar = dmc.Group(
        justify="space-between",
        align="center",
        p="md",
        style={"borderTop": "1px solid var(--border-subtle, #e2e8f0)"},
        children=[
            dmc.Text(
                f"Hiển thị {start_idx} – {end_idx} trong tổng số {total} run",
                size="sm",
                c="dimmed",
                fw=500,
            ),
            dmc.Pagination(
                id="history-pagination",
                total=max(total_pages, 1),
                value=current_page,
                size="sm",
            ),
        ],
    )

    return dmc.Card(
        [
            dmc.TableScrollContainer(
                minWidth=1320,
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
            pagination_bar,
        ],
        withBorder=True,
        padding=0,
        radius="sm",
    )


def render_bulk_purge_modal() -> dmc.Modal:
    """Hộp thoại xác nhận xóa dữ liệu tạm của nhiều run đã chọn (gõ XOA)."""
    return dmc.Modal(
        id="history-bulk-purge-modal",
        opened=False,
        title=dmc.Text("Xóa dữ liệu tạm của run đã chọn", fw=700, size="lg"),
        centered=True,
        size="md",
        withCloseButton=True,
        closeOnClickOutside=True,
        closeOnEscape=True,
        children=[
            dmc.Stack(
                [
                    dmc.Text(
                        id="history-bulk-purge-summary-text",
                        size="sm",
                        c="dimmed",
                    ),
                    dmc.SimpleGrid(
                        cols=2,
                        spacing="md",
                        children=[
                            dmc.Stack(
                                [
                                    dmc.Text("Sẽ xóa", fw=600, size="sm"),
                                    dmc.List(
                                        [
                                            dmc.ListItem("Dòng Excel đã nạp"),
                                            dmc.ListItem("File gốc, cache, file export đã sinh"),
                                        ],
                                        size="xs",
                                        c="dimmed",
                                    ),
                                ],
                                gap=4,
                            ),
                            dmc.Stack(
                                [
                                    dmc.Text("Giữ lại", fw=600, size="sm"),
                                    dmc.List(
                                        [
                                            dmc.ListItem("Kết quả, tổng hợp, tham số run"),
                                            dmc.ListItem("Export (sinh lại từ kết quả)"),
                                        ],
                                        size="xs",
                                        c="dimmed",
                                    ),
                                ],
                                gap=4,
                            ),
                        ],
                    ),
                    dmc.Alert(
                        "Run chưa kiểm tra sẽ được đánh dấu 'Đã xóa dữ liệu tạm' nhưng vẫn là 'Chưa kiểm tra'.",
                        title="Lưu ý",
                        color="yellow",
                        variant="light",
                        icon=DashIconify(icon="lucide:alert-triangle", width=18),
                    ),
                    dmc.Stack(
                        [
                            dmc.TextInput(
                                id="history-bulk-confirm-input",
                                label="Gõ XOA để xác nhận",
                                placeholder="XOA",
                                className="rh-code",
                            ),
                            dmc.Text(
                                id="history-bulk-confirm-error",
                                c="red",
                                size="xs",
                                style={"display": "none"},
                            ),
                        ],
                        gap=4,
                    ),
                    dmc.Group(
                        [
                            button_subtle("Hủy", id="history-bulk-cancel-btn"),
                            button_danger(
                                "Xóa dữ liệu tạm",
                                id="history-bulk-confirm-btn",
                            ),
                        ],
                        justify="flex-end",
                        mt="md",
                    ),
                ],
                gap="md",
            )
        ],
    )


def layout() -> html.Div:
    """Giao diện chính màn hình Lịch sử run."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="history-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang lịch sử.", tone="crit"),
            ]
        )
    tpl_options: list[dict[str, str]] = []
    usr_options: list[dict[str, str]] = []
    if ctx:
        try:
            tpl_res = list_templates(ctx)
            if tpl_res.ok and tpl_res.data:
                tpl_options = [{"label": f"{t['code']} – {t['name']}", "value": str(t["id"])} for t in tpl_res.data]
        except Exception:
            pass
        try:
            usr_res = list_users(ctx)
            if usr_res.ok and usr_res.data:
                usr_options = [{"label": u.username, "value": u.username} for u in usr_res.data]
        except Exception:
            pass

    is_admin_user = is_admin(ctx)

    return html.Div(
        [
            dcc.Store(id="history-selected-runs-store", data=[]),
            dcc.Store(id="history-page-store", data=1),
            dcc.Store(id="history-refresh-trigger", data=0),
            html.Div(id="history-notification-area"),
            dmc.Stack(
                [
                    render_header(count=0),
                    render_filter_bar(tpl_options, usr_options),
                    html.Div(
                        id="history-bulk-alert-container",
                        children=render_bulk_alert(0, is_admin_user),
                    ),
                    dcc.Loading(
                        id="history-loading",
                        type="circle",
                        children=html.Div(id="history-table-container"),
                    ),
                ],
                gap="lg",
                p="lg",
            ),
            render_bulk_purge_modal(),
        ]
    )


@callback(
    Output("history-page-store", "data"),
    Input("history-pagination", "value"),
    Input("history-filter-date-range", "value"),
    Input("history-filter-template", "value"),
    Input("history-filter-checked", "value"),
    Input("history-filter-purged", "value"),
    Input("history-filter-user", "value"),
    Input("history-filter-filename", "value"),
    State("history-page-store", "data"),
    prevent_initial_call=True,
)
def handle_history_page(
    page_val: int | None,
    _dt: Any,
    _tpl: Any,
    _chk: Any,
    _purge: Any,
    _usr: Any,
    _fn: Any,
    current_page: int,
) -> int:
    """Xử lý chuyển trang hoặc reset về trang 1 khi thay đổi bộ lọc."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return 1
    trigger_prop = ctx_dash.triggered[0]["prop_id"]
    if "history-pagination" in trigger_prop and page_val:
        return int(page_val)
    return 1


@callback(
    Output("history-table-container", "children"),
    Output("history-title", "children"),
    Input("history-filter-template", "value"),
    Input("history-filter-checked", "value"),
    Input("history-filter-purged", "value"),
    Input("history-filter-user", "value"),
    Input("history-filter-filename", "value"),
    Input("history-filter-date-range", "value"),
    Input("history-page-store", "data"),
    Input("history-refresh-trigger", "data"),
    State("history-selected-runs-store", "data"),
)
def update_history_table(
    tpl_val: str | None = "ALL",
    chk_val: str | None = "ALL",
    purge_val: str | None = "ALL",
    usr_val: str | None = "ALL",
    file_val: str | None = "",
    date_range_or_refresh: Any = None,
    page_or_selected: Any = 1,
    refresh_val: int = 0,
    selected_data: list[int] | None = None,
) -> tuple[Any, str]:
    """Cập nhật bảng danh sách run theo các bộ lọc tiêu chí và phân trang."""
    ctx = get_current_ctx()
    if ctx is None:
        return (
            alert_box(
                "Bạn cần đăng nhập để xem lịch sử run.",
                tone="crit",
            ),
            "Lịch sử run",
        )

    # Tương thích nếu hàm được gọi trực tiếp với 7 tham số từ test cũ:
    # update_history_table(tpl, chk, purge, usr, file, _refresh, selected_data)
    if isinstance(date_range_or_refresh, int):
        date_range = None
        current_page = 1
        selected_ids_input = page_or_selected if isinstance(page_or_selected, (list, set)) else []
    else:
        date_range = date_range_or_refresh
        current_page = int(page_or_selected) if page_or_selected else 1
        selected_ids_input = selected_data or []

    is_admin_user = is_admin(ctx)
    selected_ids = set(selected_ids_input)

    # Xây dựng filter object
    template_id = int(tpl_val) if tpl_val and tpl_val != "ALL" and str(tpl_val).isdigit() else None
    created_by = usr_val if usr_val and usr_val != "ALL" else None
    filename_search = file_val.strip() if file_val and file_val.strip() else None

    is_checked = None
    if chk_val == "CHECKED":
        is_checked = True
    elif chk_val == "UNCHECKED":
        is_checked = False

    is_temp_purged = None
    if purge_val == "PURGED":
        is_temp_purged = True
    elif purge_val == "RETAINED":
        is_temp_purged = False

    # Xử lý lọc theo khoảng thời gian chạy
    from_date: datetime | None = None
    to_date: datetime | None = None
    date_title_suffix = ""

    if date_range and isinstance(date_range, (list, tuple)) and len(date_range) > 0:
        start_str = date_range[0]
        end_str = date_range[1] if len(date_range) > 1 else None
        if start_str:
            try:
                from_date = datetime.strptime(start_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
            except Exception:
                pass
        if end_str:
            try:
                to_date = datetime.strptime(end_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            except Exception:
                pass

        if from_date and to_date:
            if from_date.month == to_date.month and from_date.year == to_date.year:
                date_title_suffix = f"trong tháng {from_date.strftime('%m/%Y')}"
            else:
                date_title_suffix = f"({from_date.strftime('%d/%m/%Y')} → {to_date.strftime('%d/%m/%Y')})"
        elif from_date:
            date_title_suffix = f"(từ {from_date.strftime('%d/%m/%Y')})"

    filter_obj = RunListFilter(
        template_id=template_id,
        created_by=created_by,
        filename=filename_search,
        is_checked=is_checked,
        is_temp_purged=is_temp_purged,
        from_date=from_date,
        to_date=to_date,
        page=current_page,
        page_size=20,
    )

    try:
        res = list_runs(ctx, filter_obj)
        if not res.ok:
            return (
                alert_box(
                    f"Không tải được lịch sử run. Lỗi: {res.message}",
                    tone="crit",
                    action=button_subtle("Thử lại", id="history-retry-btn", size="sm"),
                ),
                "Lịch sử run",
            )

        items = res.data.get("items", []) if res.data else []
        total = res.data.get("total", len(items)) if res.data else 0
        total_pages = res.data.get("total_pages", 1) if res.data else 1

        if not date_title_suffix:
            date_title_suffix = datetime.now().strftime("trong tháng %m/%Y")
        title_text = f"Lịch sử: {total} run {date_title_suffix}".strip()

        table_node = render_runs_table(
            items,
            is_admin=is_admin_user,
            selected_ids=selected_ids,
            total=total,
            current_page=current_page,
            page_size=20,
            total_pages=total_pages,
        )
        return table_node, title_text

    except Exception as e:
        return (
            alert_box(
                f"Lỗi hệ thống khi tải lịch sử: {e!s}",
                tone="crit",
                action=button_subtle("Thử lại", id="history-retry-btn", size="sm"),
            ),
            "Lịch sử run",
        )


@callback(
    Output("history-bulk-alert-container", "children"),
    Input("history-selected-runs-store", "data"),
)
def update_bulk_alert(selected_data: list[int] | None) -> Any:
    """Cập nhật thanh thông báo khi có run được chọn."""
    ctx = get_current_ctx()
    is_admin_user = is_admin(ctx)
    count = len(selected_data or [])
    return render_bulk_alert(count, is_admin_user)


@callback(
    Output("history-selected-runs-store", "data"),
    Input({"type": "history-run-cb", "index": dash.ALL}, "checked"),
    Input("history-select-all-cb", "checked"),
    State("history-selected-runs-store", "data"),
    prevent_initial_call=True,
)
def handle_run_selection(
    cb_values: list[bool],
    select_all_val: bool | None,
    current_selected: list[int] | None,
) -> list[int]:
    """Xử lý chọn run đơn lẻ hoặc chọn tất cả."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return current_selected or []

    trigger_id = ctx_dash.triggered[0]["prop_id"]

    # Nếu trigger là "history-select-all-cb"
    if "history-select-all-cb" in trigger_id:
        if select_all_val:
            all_inputs = ctx_dash.inputs_list[0]
            ids = [item["id"]["index"] for item in all_inputs]
            return ids
        else:
            return []

    # Nếu trigger là 1 checkbox cụ thể
    new_selected = []
    all_inputs = ctx_dash.inputs_list[0]
    for item in all_inputs:
        if item.get("value"):
            new_selected.append(item["id"]["index"])

    return new_selected


@callback(
    Output("history-bulk-purge-modal", "opened"),
    Output("history-bulk-purge-summary-text", "children"),
    Output("history-bulk-confirm-input", "value"),
    Output("history-bulk-confirm-error", "style"),
    Output("history-bulk-confirm-error", "children"),
    Input("history-open-bulk-modal-btn", "n_clicks"),
    Input("history-bulk-cancel-btn", "n_clicks"),
    State("history-bulk-purge-modal", "opened"),
    State("history-selected-runs-store", "data"),
    prevent_initial_call=True,
)
def toggle_bulk_purge_modal(
    open_clicks: int | None,
    cancel_clicks: int | None,
    is_opened: bool,
    selected_data: list[int] | None,
) -> tuple[Any, ...]:
    """Mở hoặc đóng hộp thoại xác nhận xóa dữ liệu tạm của các run đã chọn."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, "", "", {"display": "none"}, ""

    trigger_id = ctx_dash.triggered[0]["prop_id"]

    # Đóng modal khi bấm Hủy
    if "history-bulk-cancel-btn" in trigger_id:
        return False, "", "", {"display": "none"}, ""

    # Mở modal khi người dùng bấm thật sự vào nút "Xóa dữ liệu tạm"
    if "history-open-bulk-modal-btn" in trigger_id and open_clicks and open_clicks > 0:
        count = len(selected_data or [])
        summary = f"Đã chọn {count} run. Dữ liệu tạm của các run này sẽ được giải phóng khỏi ổ đĩa."
        return True, summary, "", {"display": "none"}, ""

    return False, "", "", {"display": "none"}, ""


@callback(
    Output("history-bulk-confirm-error", "style", allow_duplicate=True),
    Output("history-bulk-confirm-error", "children", allow_duplicate=True),
    Output("history-bulk-purge-modal", "opened", allow_duplicate=True),
    Output("history-selected-runs-store", "data", allow_duplicate=True),
    Output("history-refresh-trigger", "data", allow_duplicate=True),
    Output("history-notification-area", "children"),
    Input("history-bulk-confirm-btn", "n_clicks"),
    State("history-bulk-confirm-input", "value"),
    State("history-selected-runs-store", "data"),
    State("history-refresh-trigger", "data"),
    prevent_initial_call=True,
)
def handle_confirm_bulk_purge(
    n_clicks: int | None,
    confirm_text: str | None,
    selected_data: list[int] | None,
    refresh_count: int,
) -> tuple[Any, ...]:
    """Thực thi xóa dữ liệu tạm của danh sách run khi nhập đúng từ khóa 'XOA'."""
    if not n_clicks or n_clicks <= 0:
        return {"display": "none"}, "", dash.no_update, dash.no_update, dash.no_update, None

    if not confirm_text or confirm_text.strip() != "XOA":
        return (
            {"display": "block"},
            "Bạn phải nhập chính xác 'XOA' để xác nhận.",
            True,
            dash.no_update,
            dash.no_update,
            None,
        )

    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return (
            {"display": "block"},
            "Chỉ có Quản trị viên (Admin) mới có quyền xóa dữ liệu tạm.",
            True,
            dash.no_update,
            dash.no_update,
            None,
        )

    run_ids = selected_data or []
    if not run_ids:
        return {"display": "none"}, "", False, [], refresh_count + 1, None

    res = purge_runs(ctx, run_ids)
    if not res.ok:
        return (
            {"display": "block"},
            f"Lỗi xóa dữ liệu tạm: {res.message}",
            True,
            dash.no_update,
            dash.no_update,
            None,
        )

    freed = res.data.get("bytes_freed", 0) if res.data else 0
    notif = dmc.Notification(
        id="history-purge-success-notif",
        title="Thành công",
        message=f"Đã xóa dữ liệu tạm của {len(run_ids)} run (giải phóng {format_bytes(freed)}).",
        color="teal",
        icon=DashIconify(icon="lucide:check", width=18),
        action="show",
    )

    return {"display": "none"}, "", False, [], refresh_count + 1, notif
