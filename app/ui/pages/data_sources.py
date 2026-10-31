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
    recon_metadata_migration,
    recon_purge_log,
)
from app.schemas.run import PurgeFilter
from app.services.data_source import (
    create_data_source,
    list_data_sources,
    test_data_source,
    update_data_source,
)
from app.services.metadata_migration import (
    clean_target_schema,
    delete_old_sqlite,
    precheck,
    start_migration,
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
    is_oracle: bool = False,
    oracle_sources: list[dict[str, Any]] | None = None,
    latest_migration: dict[str, Any] | None = None,
) -> Any:
    """Tab quản lý lưu trữ RECON_APP và xóa dữ liệu tạm theo điều kiện."""
    temp_bytes = usage_info.get("temp_bytes", 0)
    warning_gb = usage_info.get("warning_gb", 2.0)
    warning_days = usage_info.get("warning_days", 30)
    is_warn = usage_info.get("is_warning", False)
    uncheck = usage_info.get("uncheck_count", 0)
    stale = usage_info.get("stale_count", 0)
    oracle_list = oracle_sources or []

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
        purged_at = format_datetime(log.get("CREATED_AT") or log.get("PURGED_AT") or log.get("purged_at"))
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

    target_options = [
        {
            "value": str(ds["ID"]),
            "label": f"{ds['NAME']} ({ds.get('ENV', 'ORACLE')}) — {ds.get('USERNAME', '')}@{ds.get('HOST', '')}:{ds.get('PORT', 1521)}/{ds.get('SERVICE_NAME', '')}",
        }
        for ds in oracle_list
    ]

    if is_oracle and latest_migration is not None:
        sqlite_path_text = latest_migration.get("OLD_SQLITE_PATH")
        sqlite_deleted = bool(latest_migration.get("OLD_SQLITE_DELETED_AT"))
        if sqlite_deleted:
            sqlite_status_node = alert_box(
                title="Bản lưu SQLite cũ đã được xóa",
                message=f"Bản lưu SQLite cũ đã được xóa an toàn lúc {format_datetime(latest_migration.get('OLD_SQLITE_DELETED_AT'))}.",
                tone="ok",
                icon="lucide:check-circle-2",
            )
        elif sqlite_path_text:
            sqlite_status_node = dmc.Stack(
                [
                    alert_box(
                        title="Bản lưu SQLite cũ đang được lưu trữ an toàn",
                        message=f"Đường dẫn file: {sqlite_path_text}. File này được giữ nguyên làm dự phòng sau khi chuyển sang Oracle.",
                        tone="info",
                        icon="lucide:hard-drive",
                    ),
                    button_danger("Xóa bản lưu SQLite cũ", id="ds-mig-delete-sqlite-open-btn", icon="lucide:trash", size="xs"),
                    html.Div(id="ds-mig-delete-sqlite-alert"),
                ],
                gap="sm",
            )
        else:
            sqlite_status_node = dmc.Text("Không tìm thấy thông tin bản lưu SQLite cũ cần dọn dẹp.", size="sm", c="dimmed")
    else:
        sqlite_status_node = alert_box(
            title="Đang chạy trên SQLite",
            message="Ứng dụng hiện đang chạy trực tiếp trên cơ sở dữ liệu SQLite nguồn. Chức năng xóa bản lưu SQLite chỉ được kích hoạt sau khi ReconHub đã chuyển sang chạy trên Oracle.",
            tone="info",
            icon="lucide:info",
        )

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
            # Khối Chuyển dữ liệu sang Oracle (Task 13)
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Title("Chuyển dữ liệu sang Oracle", order=4),
                                dmc.Badge("Metadata Migration", color="blue", variant="light", size="sm"),
                            ],
                            gap="sm",
                        ),
                        dmc.Text(
                            "Di chuyển toàn bộ metadata, cấu hình template, lịch sử chạy và kết quả đối soát từ SQLite sang schema Oracle đích.",
                            size="sm",
                            c="dimmed",
                        ),
                        dmc.SimpleGrid(
                            cols=2,
                            children=[
                                dmc.Select(
                                    id="ds-mig-target-select",
                                    label="Data Source Oracle đích",
                                    placeholder="Chọn Data Source Oracle..." if target_options else "Chưa có Data Source Oracle nào",
                                    data=target_options,
                                    clearable=True,
                                ),
                                dmc.Select(
                                    id="ds-mig-mode-select",
                                    label="Chế độ chuyển dữ liệu",
                                    data=[
                                        {"value": "NO_TEMP", "label": "NO_TEMP — Bỏ qua dữ liệu Excel tạm (Khuyên dùng)"},
                                        {"value": "FULL", "label": "FULL — Toàn bộ (gồm cả dữ liệu Excel tạm)"},
                                        {"value": "CONFIG_ONLY", "label": "CONFIG_ONLY — Chỉ cấu hình & người dùng"},
                                    ],
                                    value="NO_TEMP",
                                ),
                            ],
                        ),
                        dmc.Group(
                            [
                                button_primary("Kiểm tra trước", id="ds-mig-precheck-btn", icon="lucide:check-square"),
                                button_subtle("Xóa schema đích", id="ds-mig-clean-open-btn", color="red", icon="lucide:trash-2"),
                                button_primary("Chuyển sang Oracle", id="ds-mig-start-btn", icon="lucide:arrow-right"),
                            ],
                            justify="flex-start",
                            gap="sm",
                        ),
                        html.Div(id="ds-mig-result-container"),
                    ],
                    gap="md",
                ),
                withBorder=True,
                p="lg",
                radius="md",
            ),
            # Khối Bản lưu SQLite cũ (Task 13)
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Title("Bản lưu SQLite cũ", order=4),
                        dmc.Text(
                            "Quản lý và giải phóng file cơ sở dữ liệu SQLite nguồn sau khi toàn bộ hệ thống đã chuyển sang vận hành trên Oracle.",
                            size="sm",
                            c="dimmed",
                        ),
                        sqlite_status_node,
                    ],
                    gap="sm",
                ),
                withBorder=True,
                p="lg",
                radius="md",
            ),
            # Script tạo schema Oracle
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Title("Script khởi tạo schema đích Oracle", order=4),
                        dmc.Text(
                            "Trước khi chuyển dữ liệu, có thể chạy script sau trên cơ sở dữ liệu Oracle để khởi tạo user và phân quyền:",
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
            # Modal xác nhận Xóa bảng schema đích
            modal_confirm(
                id="ds-mig-clean-modal",
                title="Xác nhận xóa bảng schema đích",
                description="Thao tác này sẽ DROP toàn bộ các bảng RECON_* trên schema đích để chuẩn bị chạy lại migration. Dữ liệu trên SQLite nguồn hoàn toàn không bị ảnh hưởng.",
                confirm_text="XOA",
                confirm_label="Xác nhận xóa bảng đích",
                danger=True,
            ),
            # Modal xác nhận Xóa bản lưu SQLite cũ
            modal_confirm(
                id="ds-mig-delete-sqlite-modal",
                title="Xác nhận xóa bản lưu SQLite cũ",
                description="Thao tác này sẽ xóa vĩnh viễn file cơ sở dữ liệu SQLite nguồn trên máy chủ. Hãy chắc chắn rằng hệ thống Oracle đã vận hành ổn định.",
                confirm_text="XOA",
                confirm_label="Xác nhận xóa file SQLite",
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

    raw_items = []
    for item in (res.data or []):
        if hasattr(item, "model_dump"):
            raw_items.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            raw_items.append(dict(item))
    return {"items": raw_items, "error": None}


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
    Input("ds-mig-delete-sqlite-modal-confirm", "n_clicks"),
)
def load_storage_data(*args: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return {}

    usage_res = usage(ctx)
    if usage_res.ok and usage_res.data:
        if hasattr(usage_res.data, "model_dump"):
            usage_data = usage_res.data.model_dump(mode="json")
        elif isinstance(usage_res.data, dict):
            usage_data = dict(usage_res.data)
        else:
            usage_data = {}
    else:
        usage_data = {}

    # Lấy nhật ký xóa và cấu hình lưu trữ
    engine = get_recon_engine()
    is_oracle = engine.dialect.name == "oracle"
    purge_logs: list[dict[str, Any]] = []
    oracle_sources: list[dict[str, Any]] = []
    latest_mig: dict[str, Any] | None = None

    with engine.connect() as conn:
        stmt = select(recon_purge_log).order_by(desc(recon_purge_log.c.CREATED_AT)).limit(10)
        for r in conn.execute(stmt).mappings().all():
            d = dict(r)
            for k, v in list(d.items()):
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
            purge_logs.append(d)

        ds_stmt = select(recon_data_source).where(
            recon_data_source.c.DB_TYPE == "ORACLE",
            recon_data_source.c.IS_ACTIVE == "Y",
        )
        for r in conn.execute(ds_stmt).mappings().all():
            d = dict(r)
            for k, v in list(d.items()):
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
            oracle_sources.append(d)

        mig_stmt = select(recon_metadata_migration).order_by(desc(recon_metadata_migration.c.ID)).limit(1)
        mig_row = conn.execute(mig_stmt).mappings().first()
        if mig_row:
            latest_mig = dict(mig_row)
            for k, v in list(latest_mig.items()):
                if hasattr(v, "isoformat"):
                    latest_mig[k] = v.isoformat()

    return {
        "usage": usage_data,
        "purge_logs": purge_logs,
        "is_oracle": is_oracle,
        "oracle_sources": oracle_sources,
        "latest_migration": latest_mig,
    }


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
        is_oracle=store_data.get("is_oracle", False),
        oracle_sources=store_data.get("oracle_sources", []),
        latest_migration=store_data.get("latest_migration"),
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

    d = res.data or {}
    r_count = d.get("run_count", 0)
    rows_est = d.get("rows_estimated", 0)
    bytes_est = d.get("bytes_estimated", 0)

    alert_node = alert_box(
        title=f"Tìm thấy {r_count} run phù hợp để xóa",
        message=dmc.Stack(
            [
                dmc.Text(
                    f"Số dòng tạm sẽ xóa: {rows_est:,} dòng · Ước tính giải phóng: {format_bytes(bytes_est)} · Số run: {r_count}".replace(
                        ",", "."
                    ),
                    size="sm",
                ),
                dmc.Text("Lưu ý: Kết quả đối soát và báo cáo Excel được lưu vĩnh viễn.", size="xs", c="dimmed"),
                button_danger(
                    f"Xóa dữ liệu tạm ({r_count} run)",
                    id="ds-purge-open-modal-btn",
                    size="xs",
                ),
            ],
            gap="xs",
        ),
        tone="warn",
        icon="lucide:alert-triangle",
    )

    return alert_node, p_filter.model_dump(mode='json')


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


# Callbacks chuyển metadata sang Oracle (Task 13)
@callback(
    Output("ds-mig-result-container", "children"),
    Input("ds-mig-precheck-btn", "n_clicks"),
    State("ds-mig-target-select", "value"),
    State("ds-mig-mode-select", "value"),
    prevent_initial_call=True,
)
def handle_migration_precheck(n_clicks: Any, target_ds_id: Any, mode: str | None) -> Any:
    if not target_ds_id:
        return alert_box("Lưu ý", "Vui lòng chọn Data Source Oracle đích trước khi kiểm tra.", tone="warn")

    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return alert_box("Từ chối", "Chỉ Quản trị viên (ADMIN) mới có quyền thực hiện.", tone="crit")

    res = precheck(ctx, int(target_ds_id), mode=mode or "NO_TEMP")
    if not res.ok or not res.data:
        return alert_box("Kiểm tra thất bại", res.message or "Không thể kiểm tra đích.", tone="crit")

    d = res.data
    table_rows = []
    for t in d.get("tables", []):
        table_rows.append(
            html.Tr(
                [
                    html.Td(dmc.Text(t["table"], size="xs", ff="monospace")),
                    html.Td(dmc.Text(f"{t['rows']:,}".replace(",", "."), size="xs")),
                    html.Td(dmc.Text(format_bytes(t["bytes_est"]), size="xs")),
                ]
            )
        )

    t_node = dmc.Table(
        striped=True,
        children=[
            html.Thead(
                html.Tr(
                    [
                        html.Th("Tên bảng"),
                        html.Th("Số dòng"),
                        html.Th("Ước tính"),
                    ]
                )
            ),
            html.Tbody(table_rows),
        ],
    )

    return alert_box(
        title=f"Đích sẵn sàng: {d['target_name']} ({d['target_env']})",
        message=dmc.Stack(
            [
                dmc.Text(
                    f"Chế độ: {d['mode']} · Tổng số dòng: {d['total_rows']:,} · Dung lượng ước tính: {format_bytes(d['total_bytes_est'])}".replace(
                        ",", "."
                    ),
                    size="sm",
                    fw=600,
                ),
                dmc.ScrollArea(t_node, h=200),
                dmc.Text("Sẵn sàng chuyển. Nhấn 'Chuyển sang Oracle' để thực hiện.", size="xs", c="dimmed"),
            ],
            gap="xs",
        ),
        tone="ok",
        icon="lucide:check-circle-2",
    )


@callback(
    Output("ds-mig-result-container", "children", allow_duplicate=True),
    Input("ds-mig-start-btn", "n_clicks"),
    State("ds-mig-target-select", "value"),
    State("ds-mig-mode-select", "value"),
    prevent_initial_call=True,
)
def handle_migration_start(n_clicks: Any, target_ds_id: Any, mode: str | None) -> Any:
    if not target_ds_id:
        return alert_box("Lưu ý", "Vui lòng chọn Data Source Oracle đích trước khi chuyển.", tone="warn")

    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return alert_box("Từ chối", "Chỉ Quản trị viên (ADMIN) mới có quyền thực hiện.", tone="crit")

    res = start_migration(ctx, int(target_ds_id), mode=mode or "NO_TEMP")
    if not res.ok or not res.data:
        return alert_box("Chuyển dữ liệu thất bại", res.message or "Có lỗi xảy ra trong quá trình chuyển.", tone="crit")

    d = res.data
    report = d.get("report", {})
    comp_rows = []
    for t_name, info in report.items():
        comp_rows.append(
            html.Tr(
                [
                    html.Td(dmc.Text(t_name, size="xs", ff="monospace")),
                    html.Td(dmc.Text(f"{info.get('src_rows', 0):,}".replace(",", "."), size="xs")),
                    html.Td(dmc.Text(f"{info.get('tgt_rows', 0):,}".replace(",", "."), size="xs")),
                    html.Td(
                        dmc.Badge("Khớp SHA256", color="ok", variant="light", size="xs")
                        if info.get("checksum_matched")
                        else dmc.Badge("Chưa kiểm tra", color="gray", variant="light", size="xs")
                    ),
                ]
            )
        )

    t_report = dmc.Table(
        striped=True,
        children=[
            html.Thead(
                html.Tr(
                    [
                        html.Th("Bảng"),
                        html.Th("Nguồn (SQLite)"),
                        html.Th("Đích (Oracle)"),
                        html.Th("Đối chiếu"),
                    ]
                )
            ),
            html.Tbody(comp_rows),
        ],
    )

    steps_list = [dmc.Text(s, size="xs") for s in d.get("next_steps", [])]

    return alert_box(
        title=f"Chuyển dữ liệu thành công! (Phiên #{d.get('migration_id')})",
        message=dmc.Stack(
            [
                dmc.Text("Tất cả các bảng đã được sao chép và đối chiếu toàn vẹn dữ liệu:", size="sm", fw=600),
                dmc.ScrollArea(t_report, h=220),
                dmc.Divider(),
                dmc.Text("Các bước tiếp theo cần thực hiện:", size="sm", fw=600),
                dmc.Stack(steps_list, gap=4),
            ],
            gap="xs",
        ),
        tone="ok",
        icon="lucide:check-circle-2",
    )


@callback(
    Output("ds-mig-clean-modal", "opened"),
    Input("ds-mig-clean-open-btn", "n_clicks"),
    Input("ds-mig-clean-modal-cancel", "n_clicks"),
    State("ds-mig-clean-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_clean_modal(open_clicks: Any, cancel_clicks: Any, is_opened: bool) -> bool:
    return not is_opened


@callback(
    Output("ds-mig-clean-modal", "opened", allow_duplicate=True),
    Output("ds-mig-result-container", "children", allow_duplicate=True),
    Input("ds-mig-clean-modal-confirm", "n_clicks"),
    State("ds-mig-clean-modal-input", "value"),
    State("ds-mig-target-select", "value"),
    prevent_initial_call=True,
)
def handle_clean_schema(n_clicks: Any, input_val: str | None, target_ds_id: Any) -> tuple[bool, Any]:
    if input_val != "XOA" or not target_ds_id:
        return False, dash.no_update

    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return False, alert_box("Lỗi", "Chưa đăng nhập", tone="crit")

    # Lấy thông tin default schema của target ds
    engine = get_recon_engine()
    with engine.connect() as conn:
        ds_row = conn.execute(
            select(recon_data_source).where(recon_data_source.c.ID == int(target_ds_id))
        ).mappings().first()

    if not ds_row:
        return False, alert_box("Lỗi", "Không tìm thấy Data Source đích", tone="crit")

    schema_name = str(ds_row.get("DEFAULT_SCHEMA") or ds_row.get("USERNAME") or "").upper()
    res = clean_target_schema(ctx, int(target_ds_id), confirm_schema=schema_name)
    if not res.ok or not res.data:
        return False, alert_box("Lỗi dọn dẹp schema", res.message or "Lỗi dọn dẹp", tone="crit")

    return False, alert_box(
        "Đã dọn dẹp schema đích",
        f"Đã drop các bảng RECON_* trên schema '{schema_name}' ({len(res.data.get('dropped_tables', []))} bảng).",
        tone="ok",
    )


@callback(
    Output("ds-mig-delete-sqlite-modal", "opened"),
    Input("ds-mig-delete-sqlite-open-btn", "n_clicks"),
    Input("ds-mig-delete-sqlite-modal-cancel", "n_clicks"),
    State("ds-mig-delete-sqlite-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_delete_sqlite_modal(open_clicks: Any, cancel_clicks: Any, is_opened: bool) -> bool:
    return not is_opened


@callback(
    Output("ds-mig-delete-sqlite-modal", "opened", allow_duplicate=True),
    Output("ds-mig-delete-sqlite-alert", "children"),
    Input("ds-mig-delete-sqlite-modal-confirm", "n_clicks"),
    State("ds-mig-delete-sqlite-modal-input", "value"),
    prevent_initial_call=True,
)
def handle_delete_sqlite(n_clicks: Any, input_val: str | None) -> tuple[bool, Any]:
    if input_val != "XOA":
        return False, dash.no_update

    ctx = get_current_ctx()
    if ctx is None or Role.ADMIN not in ctx.roles:
        return False, alert_box("Lỗi", "Chưa đăng nhập", tone="crit")

    # Lấy tên file sqlite từ bản migration gần nhất
    engine = get_recon_engine()
    with engine.connect() as conn:
        mig_row = conn.execute(
            select(recon_metadata_migration)
            .where(
                recon_metadata_migration.c.STATUS == "DONE",
                recon_metadata_migration.c.OLD_SQLITE_DELETED_AT.is_(None),
            )
            .order_by(desc(recon_metadata_migration.c.ID))
        ).mappings().first()

    if not mig_row or not mig_row.get("OLD_SQLITE_PATH"):
        return False, alert_box("Lỗi", "Không tìm thấy file SQLite cũ cần xóa.", tone="crit")

    from pathlib import Path
    f_name = Path(mig_row["OLD_SQLITE_PATH"]).name
    res = delete_old_sqlite(ctx, confirm_filename=f_name)
    if not res.ok or not res.data:
        return False, alert_box("Không thể xóa", res.message or "Lỗi khi xóa", tone="crit")

    return False, alert_box(
        "Thành công",
        f"Đã xóa file SQLite cũ '{f_name}', giải phóng {format_bytes(res.data.get('bytes_freed', 0))}.",
        tone="ok",
    )
