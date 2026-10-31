from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from sqlalchemy import desc, select

from app.core.context import Role
from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_purge_log,
)
from app.schemas.run import PurgeFilter
from app.services.data_source import (
    create_data_source,
    list_data_sources,
    test_data_source,
    update_data_source,
)
from app.services.oracle_admin import generate_target_user_sql
from app.services.temp_data import preview, purge_filter, usage
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.code_block import code_block
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.kpi_card import kpi_card
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.status_chip import status_chip
from app.ui.formatters import format_bytes, format_datetime

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/data-sources",
        title="Data Sources & Lưu trữ — ReconHub",
    )
except Exception:
    pass


def render_data_sources_table(
    items: list[dict[str, Any]] | None,
    loading: bool = False,
    error: str | None = None,
) -> Any:
    """Bảng danh sách nguồn dữ liệu đối soát."""
    if loading:
        return dmc.Stack([dmc.Skeleton(height=48, radius="md") for _ in range(4)], gap="sm")

    if error:
        return alert_box(
            "Lỗi tải danh sách nguồn", error, tone="crit", action=button_danger("Thử lại", id="ds-retry-btn", size="xs")
        )

    if not items or len(items) == 0:
        return empty_state(
            title="Chưa có nguồn đối soát nào",
            description="Đăng ký kết nối Oracle để thực hiện truy vấn và đối soát dữ liệu.",
            action=button_primary("Thêm nguồn đối soát", id="ds-add-btn-empty", icon="lucide:plus"),
        )

    rows = []
    for it in items:
        ds_id = it.get("id")
        name = it.get("name", "")
        env = it.get("environment", "DEV")
        host = it.get("host", "")
        port = it.get("port", 1521)
        service = it.get("service_name", "")
        user = it.get("username", "")
        schema = it.get("default_schema") or "—"
        check_st = it.get("last_check_status")
        check_ms = it.get("last_check_ms")
        tmpl_count = it.get("template_count", 0)

        # Trạng thái kiểm tra kết nối gần nhất
        if check_st == "RO_OK":
            check_badge = dmc.Badge(
                f"Chỉ đọc · {check_ms or 0}ms",
                color="ok",
                variant="light",
                leftSection=DashIconify(icon="lucide:check-circle-2", width=12),
                size="xs",
            )
        elif check_st == "RO_WARN":
            check_badge = dmc.Badge(
                "Có quyền ghi",
                color="warn",
                variant="light",
                leftSection=DashIconify(icon="lucide:alert-triangle", width=12),
                size="xs",
            )
        elif check_st:
            check_badge = dmc.Badge(
                "Lỗi kết nối",
                color="crit",
                variant="light",
                leftSection=DashIconify(icon="lucide:alert-circle", width=12),
                size="xs",
            )
        else:
            check_badge = dmc.Text("—", size="xs", c="dimmed")

        row = html.Tr(
            [
                html.Td(dmc.Text(name, fw=600, size="sm")),
                html.Td(status_chip(env, size="xs")),
                html.Td(
                    dmc.Text(f"{host}:{port}/{service}", ff="monospace", size="xs"),
                ),
                html.Td(dmc.Text(user, size="sm")),
                html.Td(dmc.Text(schema, ff="monospace", size="xs")),
                html.Td(check_badge),
                html.Td(dmc.Badge(f"{tmpl_count} template", variant="light", color="gray", size="xs")),
                html.Td(
                    dmc.Group(
                        [
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:activity", width=16),
                                id={"type": "ds-test-btn", "index": ds_id},
                                variant="subtle",
                                color="primary",
                            ),
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:edit-3", width=16),
                                id={"type": "ds-edit-btn", "index": ds_id},
                                variant="subtle",
                                color="gray",
                            ),
                        ],
                        gap="xs",
                    )
                ),
            ]
        )
        rows.append(row)

    table = dmc.Table(
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
        children=[
            html.Thead(
                html.Tr(
                    [
                        html.Th("Tên nguồn"),
                        html.Th("Môi trường"),
                        html.Th("Máy chủ (Host:Port/Service)"),
                        html.Th("User"),
                        html.Th("Schema"),
                        html.Th("Kiểm tra gần nhất"),
                        html.Th("Sử dụng"),
                        html.Th("Thao tác"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
    )

    return dmc.Paper(table, withBorder=True, radius="md", p=0)


def render_storage_tab(
    usage_info: dict[str, Any],
    purge_logs: list[dict[str, Any]],
) -> Any:
    """Tab quản lý lưu trữ RECON_APP và xóa dữ liệu tạm theo điều kiện."""
    temp_bytes = usage_info.get("temp_bytes", 0)
    warning_gb = usage_info.get("warning_gb", 2.0)
    warning_days = usage_info.get("warning_days", 30)
    is_warn = usage_info.get("is_warning", False)
    uncheck = usage_info.get("uncheck_count", 0)
    stale = usage_info.get("stale_count", 0)

    # 1. Khối Dữ liệu tạm (KPI + Cấu hình ngưỡng)
    temp_kpis = dmc.SimpleGrid(
        cols=3,
        children=[
            kpi_card(
                "Dung lượng tạm hiện tại",
                format_bytes(temp_bytes),
                tone="warn" if is_warn else "primary",
                meta=f"Ngưỡng cảnh báo: {warning_gb:.1f} GB",
                icon="lucide:database",
            ),
            kpi_card(
                "Run chưa kiểm tra",
                str(uncheck),
                tone="warn" if uncheck > 0 else "ok",
                meta="Cần kiểm tra trước khi xóa",
                icon="lucide:clock",
            ),
            kpi_card(
                "Giữ quá hạn",
                str(stale),
                tone="crit" if stale > 0 else "ok",
                meta=f"Quá {warning_days} ngày",
                icon="lucide:calendar-x",
            ),
        ],
    )

    # 2. Bảng nhật ký xóa
    log_rows = []
    for log in purge_logs:
        purged_at = format_datetime(log.get("PURGED_AT") or log.get("purged_at"))
        scope = log.get("SCOPE") or log.get("scope") or "—"
        runs_cnt = log.get("RUNS_COUNT") or log.get("runs_count") or 0
        rows_cnt = log.get("ROWS_COUNT") or log.get("rows_count") or 0
        freed = format_bytes(log.get("FREED_BYTES") or log.get("freed_bytes") or 0)
        purged_by = log.get("PURGED_BY") or log.get("purged_by") or "—"

        log_rows.append(
            html.Tr(
                [
                    html.Td(dmc.Text(purged_at, size="xs")),
                    html.Td(dmc.Badge(scope, variant="light", color="gray", size="xs")),
                    html.Td(dmc.Text(str(runs_cnt), size="xs")),
                    html.Td(dmc.Text(f"{rows_cnt:,}".replace(",", "."), size="xs")),
                    html.Td(dmc.Text(freed, size="xs", fw=600)),
                    html.Td(dmc.Text(f"@{purged_by}", size="xs", c="dimmed")),
                ]
            )
        )

    log_table = (
        dmc.Table(
            striped=True,
            children=[
                html.Thead(
                    html.Tr(
                        [
                            html.Th("Thời gian"),
                            html.Th("Phạm vi"),
                            html.Th("Số run"),
                            html.Th("Dòng đã xóa"),
                            html.Th("Giải phóng"),
                            html.Th("Người xóa"),
                        ]
                    )
                ),
                html.Tbody(log_rows),
            ],
        )
        if log_rows
        else dmc.Text("Chưa có lịch sử xóa dữ liệu tạm nào.", size="sm", c="dimmed", py="md", ta="center")
    )

    # Khối SQL Oracle
    target_sql = generate_target_user_sql("RECON_APP", "ReconHub2026#Secure")

    return dmc.Stack(
        [
            # Cảnh báo nguyên tắc xóa dữ liệu tạm
            alert_box(
                title="Nguyên tắc an toàn dữ liệu tạm (ADR-012)",
                message="Dữ liệu Excel đã nạp là dữ liệu tạm. Hệ thống KHÔNG tự động xóa; người dùng chủ động xóa theo yêu cầu. Sau khi xóa các dòng dữ liệu tạm, kết quả đối soát và file export Excel được giữ trọn vẹn.",
                tone="info",
                icon="lucide:shield-check",
            ),
            # Chỉ số dữ liệu tạm
            temp_kpis,
            # Khối xóa dữ liệu tạm theo điều kiện
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Title("Xóa dữ liệu tạm theo điều kiện", order=4),
                        dmc.Text(
                            "Chọn phạm vi các run muốn xóa dữ liệu Excel tạm để giải phóng dung lượng bộ nhớ.",
                            size="sm",
                            c="dimmed",
                        ),
                        dmc.SimpleGrid(
                            cols=4,
                            children=[
                                dmc.Select(
                                    id="ds-purge-filter-template",
                                    label="Template",
                                    placeholder="Tất cả template",
                                    data=[],
                                    clearable=True,
                                ),
                                dmc.Select(
                                    id="ds-purge-filter-checked",
                                    label="Trạng thái kiểm tra",
                                    placeholder="Tất cả",
                                    data=[
                                        {"value": "", "label": "Tất cả"},
                                        {"value": "Y", "label": "Đã kiểm tra xong"},
                                        {"value": "N", "label": "Chưa kiểm tra"},
                                    ],
                                    value="Y",
                                ),
                                dmc.NumberInput(
                                    id="ds-purge-filter-days",
                                    label="Chạy trước (số ngày)",
                                    placeholder="VD: 30",
                                ),
                                dmc.TextInput(
                                    id="ds-purge-filter-user",
                                    label="Người chạy",
                                    placeholder="Username",
                                ),
                            ],
                        ),
                        dmc.Group(
                            [
                                button_primary("Xem trước", id="ds-purge-preview-btn", icon="lucide:eye"),
                            ],
                            justify="flex-start",
                        ),
                        html.Div(id="ds-purge-preview-alert"),
                    ],
                    gap="md",
                ),
                withBorder=True,
                p="lg",
                radius="md",
            ),
            # Nhật ký xóa
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Title("Nhật ký xóa dữ liệu tạm", order=4),
                        log_table,
                    ],
                    gap="sm",
                ),
                withBorder=True,
                p="lg",
                radius="md",
            ),
            # Đích Oracle
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Title("Đích lưu trữ Oracle (Chuẩn bị)", order=4),
                                dmc.Badge("Task 13", color="purple", variant="light", size="sm"),
                            ],
                            gap="sm",
                        ),
                        dmc.Text(
                            "Khi cần chuyển RECON_APP từ SQLite sang Oracle, chạy script sau trên cơ sở dữ liệu Oracle để khởi tạo schema:",
                            size="sm",
                            c="dimmed",
                        ),
                        code_block(target_sql, language="sql"),
                    ],
                    gap="sm",
                ),
                withBorder=True,
                p="lg",
                radius="md",
            ),
        ],
        gap="lg",
    )


def layout() -> Any:
    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return dmc.Container(
            alert_box(
                title="Quyền truy cập bị từ chối",
                message="Trang Data Sources và Cấu hình lưu trữ chỉ dành cho Quản trị viên (ADMIN).",
                tone="crit",
            ),
            size="md",
            py="xl",
        )

    return dmc.Container(
        [
            dcc.Store(id="ds-store-list"),
            dcc.Store(id="ds-store-storage"),
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.Stack(
                                [
                                    dmc.Title("Data Sources & Lưu trữ", order=2),
                                    dmc.Text(
                                        "Quản lý kết nối Oracle đối soát và hạ tầng lưu trữ RECON_APP.",
                                        size="sm",
                                        c="dimmed",
                                    ),
                                ],
                                gap=2,
                            ),
                            dmc.Group(
                                [
                                    dmc.ActionIcon(
                                        DashIconify(icon="lucide:refresh-cw", width=16),
                                        id="ds-refresh-btn",
                                        variant="subtle",
                                        color="gray",
                                        size="lg",
                                    ),
                                    button_primary("Thêm nguồn đối soát", id="ds-add-btn", icon="lucide:plus"),
                                ],
                                gap="sm",
                            ),
                        ],
                        justify="space-between",
                        align="flex-start",
                    ),
                    # 2 Tabs
                    dmc.Tabs(
                        id="ds-tabs",
                        value="sources",
                        children=[
                            dmc.TabsList(
                                [
                                    dmc.TabsTab(
                                        "Nguồn đối soát",
                                        value="sources",
                                        leftSection=DashIconify(icon="lucide:database", width=16),
                                    ),
                                    dmc.TabsTab(
                                        "Lưu trữ RECON_APP",
                                        value="storage",
                                        leftSection=DashIconify(icon="lucide:hard-drive", width=16),
                                    ),
                                ]
                            ),
                            dmc.TabsPanel(
                                html.Div(id="ds-sources-content", style={"paddingTop": "16px"}),
                                value="sources",
                            ),
                            dmc.TabsPanel(
                                html.Div(id="ds-storage-content", style={"paddingTop": "16px"}),
                                value="storage",
                            ),
                        ],
                    ),
                ],
                gap="lg",
                py="xl",
            ),
            # Drawer Thêm/Sửa Nguồn
            drawer_right(
                id="ds-drawer",
                title="Cấu hình nguồn đối soát",
                opened=False,
                children=dmc.Stack(
                    [
                        dcc.Store(id="ds-drawer-id"),
                        dmc.Select(
                            id="ds-drawer-env",
                            label="Môi trường",
                            data=[
                                {"value": "DEV", "label": "DEV (Phát triển)"},
                                {"value": "UAT", "label": "UAT (Kiểm thử)"},
                                {"value": "PROD", "label": "PROD (Vận hành)"},
                            ],
                            value="DEV",
                            withAsterisk=True,
                        ),
                        dmc.TextInput(
                            id="ds-drawer-name",
                            label="Tên nguồn đối soát",
                            placeholder="VD: Oracle ERP Billing",
                            withAsterisk=True,
                        ),
                        dmc.TextInput(
                            id="ds-drawer-host",
                            label="Host / IP",
                            placeholder="VD: 10.0.1.50",
                            withAsterisk=True,
                        ),
                        dmc.NumberInput(
                            id="ds-drawer-port",
                            label="Port",
                            value=1521,
                            withAsterisk=True,
                        ),
                        dmc.TextInput(
                            id="ds-drawer-service",
                            label="Service Name",
                            placeholder="VD: ORCLPDB1",
                            withAsterisk=True,
                        ),
                        dmc.TextInput(
                            id="ds-drawer-user",
                            label="Username (chỉ đọc)",
                            placeholder="VD: RECON_RO",
                            withAsterisk=True,
                        ),
                        dmc.PasswordInput(
                            id="ds-drawer-pwd",
                            label="Mật khẩu",
                            description="Để trống nếu không muốn thay đổi mật khẩu đã lưu",
                        ),
                        dmc.TextInput(
                            id="ds-drawer-schema",
                            label="Schema mặc định",
                            placeholder="VD: BILLING",
                        ),
                        dmc.NumberInput(
                            id="ds-drawer-timeout",
                            label="Timeout (giây)",
                            value=600,
                        ),
                        html.Div(id="ds-drawer-alert"),
                        dmc.Group(
                            [
                                button_subtle("Kiểm tra kết nối", id="ds-drawer-test-btn", icon="lucide:activity"),
                                button_subtle("Hủy", id="ds-drawer-cancel-btn"),
                                button_primary("Lưu", id="ds-drawer-save-btn", icon="lucide:save"),
                            ],
                            justify="flex-end",
                            gap="sm",
                            mt="lg",
                        ),
                    ],
                    gap="md",
                ),
            ),
            # Modal xác nhận Xóa dữ liệu tạm với từ khóa XOA
            modal_confirm(
                id="ds-purge-confirm-modal",
                title="Xác nhận xóa dữ liệu tạm theo điều kiện",
                description="Thao tác này sẽ xóa vĩnh viễn các dòng dữ liệu tạm của các run thỏa mãn điều kiện. Kết quả đối soát RECON_RESULT_* và file export Excel được giữ trọn vẹn.",
                confirm_text="XOA",
                confirm_label="Xóa dữ liệu tạm",
                danger=True,
            ),
            dcc.Store(id="ds-purge-preview-store"),
        ],
        size="xl",
    )


# Callbacks nạp dữ liệu Sources
@callback(
    Output("ds-store-list", "data"),
    Input("ds-refresh-btn", "n_clicks"),
    Input("ds-drawer-save-btn", "n_clicks"),
)
def load_sources_data(*args: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return {"items": [], "error": "Chưa đăng nhập"}

    res = list_data_sources(ctx, purpose="SOURCE")
    if not res.ok:
        return {"items": [], "error": res.message}

    return {"items": res.data or [], "error": None}


@callback(
    Output("ds-sources-content", "children"),
    Input("ds-store-list", "data"),
)
def update_sources_table(store_data: Any) -> Any:
    if not store_data:
        return render_data_sources_table(items=None, loading=True)
    return render_data_sources_table(
        items=store_data.get("items"),
        loading=False,
        error=store_data.get("error"),
    )


# Callbacks nạp dữ liệu Storage
@callback(
    Output("ds-store-storage", "data"),
    Input("ds-refresh-btn", "n_clicks"),
    Input("ds-purge-confirm-modal-confirm", "n_clicks"),
)
def load_storage_data(*args: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return {}

    usage_res = usage(ctx)
    usage_data = usage_res.data.model_dump() if usage_res.ok and usage_res.data else {}

    # Lấy nhật ký xóa
    engine = get_recon_engine()
    purge_logs: list[dict[str, Any]] = []
    with engine.connect() as conn:
        stmt = select(recon_purge_log).order_by(desc(recon_purge_log.c.PURGED_AT)).limit(10)
        purge_logs = [dict(r) for r in conn.execute(stmt).mappings().all()]

    return {"usage": usage_data, "purge_logs": purge_logs}


@callback(
    Output("ds-storage-content", "children"),
    Input("ds-store-storage", "data"),
)
def update_storage_content(store_data: Any) -> Any:
    if not store_data:
        return dmc.Stack([dmc.Skeleton(height=100, radius="md") for _ in range(3)], gap="md")

    return render_storage_tab(
        usage_info=store_data.get("usage", {}),
        purge_logs=store_data.get("purge_logs", []),
    )


# Callback mở Drawer Thêm
@callback(
    Output("ds-drawer", "opened"),
    Output("ds-drawer-id", "data"),
    Output("ds-drawer-name", "value"),
    Output("ds-drawer-env", "value"),
    Output("ds-drawer-host", "value"),
    Output("ds-drawer-port", "value"),
    Output("ds-drawer-service", "value"),
    Output("ds-drawer-user", "value"),
    Output("ds-drawer-schema", "value"),
    Output("ds-drawer-timeout", "value"),
    Input("ds-add-btn", "n_clicks"),
    Input({"type": "ds-edit-btn", "index": ALL}, "n_clicks"),
    Input("ds-drawer-cancel-btn", "n_clicks"),
    State("ds-drawer", "opened"),
    prevent_initial_call=True,
)
def handle_drawer_open(*args: Any) -> Any:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, None, "", "DEV", "", 1521, "", "", "", 600

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]
    if "ds-drawer-cancel-btn" in trigger_id:
        return False, None, "", "DEV", "", 1521, "", "", "", 600

    if trigger_id == "ds-add-btn":
        return True, None, "", "DEV", "", 1521, "", "", "", 600

    try:
        parsed = json.loads(trigger_id)
        ds_id = parsed.get("index")
        if ds_id is not None:
            engine = get_recon_engine()
            with engine.connect() as conn:
                row = (
                    conn.execute(select(recon_data_source).where(recon_data_source.c.ID == int(ds_id)))
                    .mappings()
                    .first()
                )
                if row:
                    return (
                        True,
                        ds_id,
                        row["NAME"],
                        row["ENV"],
                        row["HOST"] or "",
                        row["PORT"] or 1521,
                        row["SERVICE_NAME"] or "",
                        row["USERNAME"] or "",
                        row["DEFAULT_SCHEMA"] or "",
                        row["CALL_TIMEOUT_S"] or 600,
                    )
    except Exception:
        pass

    return False, None, "", "DEV", "", 1521, "", "", "", 600


# Callback Xem trước Xóa dữ liệu tạm
@callback(
    Output("ds-purge-preview-alert", "children"),
    Output("ds-purge-preview-store", "data"),
    Input("ds-purge-preview-btn", "n_clicks"),
    State("ds-purge-filter-template", "value"),
    State("ds-purge-filter-checked", "value"),
    State("ds-purge-filter-days", "value"),
    State("ds-purge-filter-user", "value"),
    prevent_initial_call=True,
)
def handle_purge_preview(
    n_clicks: Any,
    tmpl_val: str | None,
    checked_val: str | None,
    days_val: Any,
    user_val: str | None,
) -> tuple[Any, Any]:
    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return alert_box("Lỗi", "Chưa đăng nhập", tone="crit"), None

    b_date = datetime.now() - timedelta(days=int(days_val)) if days_val else None
    tid_int = int(tmpl_val) if tmpl_val and str(tmpl_val).isdigit() else None

    p_filter = PurgeFilter(
        template_id=tid_int,
        before_date=b_date,
        only_checked=checked_val == "Y" if checked_val else False,
        created_by=user_val.strip() if user_val else None,
    )

    res = preview(ctx, p_filter)
    if not res.ok or not res.data:
        return alert_box("Lỗi xem trước", res.message, tone="crit"), None

    d = res.data
    alert_node = alert_box(
        title=f"Tìm thấy {d.run_count} run phù hợp để xóa",
        message=dmc.Stack(
            [
                dmc.Text(
                    f"Số dòng tạm sẽ xóa: {d.row_count:,} dòng · Ước tính giải phóng: {format_bytes(d.freed_bytes_estimate)} · Số file gốc: {d.file_count}".replace(
                        ",", "."
                    ),
                    size="sm",
                ),
                dmc.Text("Lưu ý: Kết quả đối soát và báo cáo Excel được lưu vĩnh viễn.", size="xs", c="dimmed"),
                button_danger(
                    f"Xóa dữ liệu tạm ({d.run_count} run)",
                    id="ds-purge-open-modal-btn",
                    size="xs",
                ),
            ],
            gap="xs",
        ),
        tone="warn",
        icon="lucide:alert-triangle",
    )

    return alert_node, p_filter.model_dump()


# Callback mở modal xác nhận Xóa
@callback(
    Output("ds-purge-confirm-modal", "opened"),
    Input("ds-purge-open-modal-btn", "n_clicks"),
    Input("ds-purge-confirm-modal-cancel", "n_clicks"),
    State("ds-purge-confirm-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_purge_confirm_modal(open_clicks: Any, cancel_clicks: Any, is_opened: bool) -> bool:
    return not is_opened


# Callback thực hiện Purge khi gõ đúng XOA
@callback(
    Output("ds-purge-confirm-modal", "opened", allow_duplicate=True),
    Input("ds-purge-confirm-modal-confirm", "n_clicks"),
    State("ds-purge-confirm-modal-input", "value"),
    State("ds-purge-preview-store", "data"),
    prevent_initial_call=True,
)
def handle_execute_purge(n_clicks: Any, input_val: str | None, filter_data: Any) -> bool:
    if input_val != "XOA" or not filter_data:
        return False

    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return False

    p_filter = PurgeFilter(**filter_data)
    purge_filter(ctx, p_filter, confirm_text="XOA")
    return False


# Callback Lưu nguồn đối soát (Thêm mới hoặc Cập nhật)
@callback(
    Output("ds-drawer-alert", "children"),
    Output("ds-drawer", "opened", allow_duplicate=True),
    Input("ds-drawer-save-btn", "n_clicks"),
    State("ds-drawer-id", "data"),
    State("ds-drawer-env", "value"),
    State("ds-drawer-name", "value"),
    State("ds-drawer-host", "value"),
    State("ds-drawer-port", "value"),
    State("ds-drawer-service", "value"),
    State("ds-drawer-user", "value"),
    State("ds-drawer-pwd", "value"),
    State("ds-drawer-schema", "value"),
    State("ds-drawer-timeout", "value"),
    prevent_initial_call=True,
)
def handle_save_data_source(
    n_clicks: Any,
    ds_id: Any,
    env_val: str | None,
    name_val: str | None,
    host_val: str | None,
    port_val: Any,
    service_val: str | None,
    user_val: str | None,
    pwd_val: str | None,
    schema_val: str | None,
    timeout_val: Any,
) -> tuple[Any, bool]:
    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return alert_box("Lỗi", "Chưa đăng nhập", tone="crit"), True

    if not name_val or not host_val or not service_val or not user_val:
        return alert_box("Lỗi", "Vui lòng điền đầy đủ các trường bắt buộc", tone="crit"), True

    from app.schemas.data_source import DataSourceCreateDTO, DataSourceUpdateDTO

    try:
        p_val = int(port_val) if port_val else 1521
        to_val = int(timeout_val) if timeout_val else 600

        if ds_id is None:
            # Thêm mới
            dto_create = DataSourceCreateDTO(
                name=name_val.strip(),
                env=(env_val or "DEV").strip().upper(),
                purpose="SOURCE",
                db_type="ORACLE",
                host=host_val.strip(),
                port=p_val,
                service_name=service_val.strip(),
                username=user_val.strip(),
                password=pwd_val.strip() if pwd_val else "",
                default_schema=schema_val.strip() if schema_val else None,
                call_timeout_s=to_val,
            )
            res = create_data_source(ctx, dto_create)
            if not res.ok:
                return alert_box("Không thể tạo nguồn", res.message, tone="crit"), True
        else:
            # Cập nhật
            dto_update = DataSourceUpdateDTO(
                name=name_val.strip(),
                host=host_val.strip(),
                port=p_val,
                service_name=service_val.strip(),
                username=user_val.strip(),
                password=pwd_val.strip() if pwd_val else None,
                default_schema=schema_val.strip() if schema_val else None,
                call_timeout_s=to_val,
            )
            res = update_data_source(ctx, int(ds_id), dto_update)
            if not res.ok:
                return alert_box("Không thể cập nhật", res.message, tone="crit"), True

        return None, False
    except Exception as e:
        return alert_box("Lỗi hệ thống", str(e), tone="crit"), True


# Callback kiểm tra kết nối trong Drawer
@callback(
    Output("ds-drawer-alert", "children", allow_duplicate=True),
    Input("ds-drawer-test-btn", "n_clicks"),
    State("ds-drawer-id", "data"),
    prevent_initial_call=True,
)
def handle_test_drawer_connection(n_clicks: Any, ds_id: Any) -> Any:
    if not ds_id:
        return alert_box("Lưu ý", "Vui lòng lưu nguồn trước khi thực hiện kiểm tra kết nối", tone="info")

    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return alert_box("Lỗi", "Chưa đăng nhập", tone="crit")

    res = test_data_source(ctx, int(ds_id))
    if res.ok and res.data:
        d = res.data
        if d.get("status") == "RO_OK":
            return alert_box("Kết nối thành công", f"Chỉ đọc · {d.get('latency_ms', 0)}ms", tone="ok")
        elif d.get("status") == "RO_WARN":
            return alert_box("Cảnh báo", f"User có quyền ghi trên schema · {d.get('latency_ms', 0)}ms", tone="warn")
        else:
            return alert_box("Thất bại", d.get("message") or "Không kết nối được đến máy chủ Oracle", tone="crit")
    return alert_box("Lỗi kết nối", res.message, tone="crit")
