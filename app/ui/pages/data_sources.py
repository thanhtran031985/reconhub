from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from sqlalchemy import desc, select

from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_metadata_migration,
    recon_purge_log,
)
from app.schemas.run import PurgeFilter
from app.services.data_source import (
    activate_data_source,
    create_data_source,
    deactivate_data_source,
    get_active_environment,
    list_data_sources,
    test_data_source,
    test_data_source_config,
    update_data_source,
)
from app.services.metadata_migration import (
    clean_target_schema,
    delete_old_sqlite,
    get_active_migration,
    get_latest_migration,
    get_migration_for_poll,
    get_migration_run_result,
    precheck,
    run_migration_background,
)
from app.services.migration_checklist import (
    MANUAL_STEP_KEY,
    MIGRATION_STEP_KEYS,
    MIGRATION_STEP_LABELS,
    advance_fake_checklist,
    build_fake_checklist,
    error_step_index,
    mark_items_done,
    mark_step_error,
    new_checklist,
    overall_status,
    progress_counts,
    refresh_status,
    running_item,
    running_step_index,
    save_checklist,
    set_item_status,
    step_counts,
    step_status,
)
from app.services.oracle_admin import generate_target_user_sql
from app.services.perm import is_admin, page_gate
from app.services.temp_data import preview, purge_filter, usage
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.code_block import code_block
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.kpi_card import kpi_card
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.page_header import page_header
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

MENU_CODE = "data_source"


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

    td_style = {"whiteSpace": "nowrap", "verticalAlign": "middle"}
    td_center_style = {"textAlign": "center", "verticalAlign": "middle", "whiteSpace": "nowrap"}
    td_right_style = {"textAlign": "right", "whiteSpace": "nowrap", "verticalAlign": "middle"}

    rows = []
    for it in items:
        ds_id = it.get("id")
        name = it.get("name", "")
        env = it.get("env") or it.get("environment", "DEV")
        host = it.get("host", "")
        port = it.get("port", 1521)
        service = it.get("service_name", "")
        user = it.get("username", "")
        schema = it.get("default_schema") or "—"
        check_st = it.get("last_check_status")
        check_ok = it.get("last_test_ok")
        check_ms = it.get("last_test_ms") or it.get("last_check_ms")
        check_msg = it.get("last_test_msg") or ""
        tmpl_count = it.get("template_count", 0)
        is_active = bool(it.get("is_active", False))

        # Trạng thái kiểm tra kết nối gần nhất
        if check_st == "RO_OK" or check_ok == "Y":
            check_badge = dmc.Badge(
                f"Chỉ đọc · {check_ms or 0}ms",
                color="ok",
                variant="light",
                leftSection=DashIconify(icon="lucide:check-circle-2", width=12),
                size="xs",
            )
        elif check_st == "RO_WARN" or check_ok == "W" or ("quyền ghi" in check_msg.lower()):
            check_badge = dmc.Badge(
                f"Có quyền ghi · {check_ms or 0}ms" if check_ms else "Có quyền ghi",
                color="warn",
                variant="light",
                leftSection=DashIconify(icon="lucide:alert-triangle", width=12),
                size="xs",
            )
        elif check_ok == "N" or (check_st and check_st not in ("RO_OK", "RO_WARN")):
            check_badge = dmc.Badge(
                "Không kết nối được",
                color="crit",
                variant="light",
                leftSection=DashIconify(icon="lucide:alert-circle", width=12),
                size="xs",
            )
        else:
            check_badge = dmc.Text("—", size="xs", c="dimmed")

        row = dmc.TableTr(
            [
                dmc.TableTd(
                    dmc.Center(
                        dmc.Switch(
                            id={"type": "ds-active-switch", "index": ds_id},
                            checked=is_active,
                            size="sm",
                            color="blue",
                        )
                    ),
                    style=td_center_style,
                ),
                dmc.TableTd(dmc.Text(name, fw=600, size="sm"), style=td_style),
                dmc.TableTd(status_chip(env, size="xs"), style=td_style),
                dmc.TableTd(dmc.Text(f"{host}:{port}/{service}", className="rh-code", size="xs"), style=td_style),
                dmc.TableTd(dmc.Text(user, size="sm"), style=td_style),
                dmc.TableTd(dmc.Text(schema, className="rh-code", size="xs"), style=td_style),
                dmc.TableTd(check_badge, style=td_style),
                dmc.TableTd(dmc.Badge(f"{tmpl_count} template", variant="light", color="gray", size="xs"), style=td_style),
                dmc.TableTd(
                    dmc.Group(
                        [
                            dmc.Tooltip(
                                label="Kiểm tra kết nối",
                                children=dmc.ActionIcon(
                                    DashIconify(icon="lucide:activity", width=16),
                                    id={"type": "ds-test-btn", "index": ds_id},
                                    variant="subtle",
                                    color="primary",
                                ),
                            ),
                            dmc.Tooltip(
                                label="Sửa cấu hình",
                                children=dmc.ActionIcon(
                                    DashIconify(icon="lucide:edit-3", width=16),
                                    id={"type": "ds-edit-btn", "index": ds_id},
                                    variant="subtle",
                                    color="gray",
                                ),
                            ),
                        ],
                        gap="xs",
                        justify="flex-end",
                    ),
                    style=td_right_style,
                ),
            ]
        )
        rows.append(row)

    th_style = {
        "position": "sticky",
        "top": 0,
        "zIndex": 1,
        "backgroundColor": "var(--mantine-color-body, #fff)",
        "whiteSpace": "nowrap",
        "textAlign": "center",
    }
    headers = [
        dmc.TableTh("Kích hoạt", style={"minWidth": "90px", **th_style}),
        dmc.TableTh("Tên nguồn", style={"minWidth": "160px", **th_style}),
        dmc.TableTh("Môi trường", style={"minWidth": "110px", **th_style}),
        dmc.TableTh("Máy chủ (Host:Port/Service)", style={"minWidth": "240px", **th_style}),
        dmc.TableTh("User", style={"minWidth": "120px", **th_style}),
        dmc.TableTh("Schema", style={"minWidth": "120px", **th_style}),
        dmc.TableTh("Kiểm tra gần nhất", style={"minWidth": "160px", **th_style}),
        dmc.TableTh("Sử dụng", style={"minWidth": "110px", **th_style}),
        dmc.TableTh("Thao tác", style={"minWidth": "100px", **th_style}),
    ]

    return dmc.Card(
        [
            dmc.TableScrollContainer(
                minWidth=1180,
                style={"flex": 1, "minHeight": 0, "overflowY": "auto"},
                children=dmc.Table(
                    [
                        dmc.TableThead(dmc.TableTr(headers)),
                        dmc.TableTbody(rows),
                    ],
                    striped=False,
                    highlightOnHover=True,
                    withTableBorder=False,
                    withColumnBorders=False,
                    verticalSpacing="xs",
                ),
            ),
        ],
        withBorder=True,
        radius="sm",
        padding=0,
        style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column"},
    )


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
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Text(purged_at, size="xs"), style={"whiteSpace": "nowrap", "verticalAlign": "middle"}
                    ),
                    dmc.TableTd(
                        dmc.Badge(scope, variant="light", color="gray", size="xs"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Text(str(runs_cnt), size="xs"), style={"whiteSpace": "nowrap", "verticalAlign": "middle"}
                    ),
                    dmc.TableTd(
                        dmc.Text(f"{rows_cnt:,}".replace(",", "."), size="xs"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Text(freed, size="xs", fw=600), style={"whiteSpace": "nowrap", "verticalAlign": "middle"}
                    ),
                    dmc.TableTd(
                        dmc.Text(f"@{purged_by}", size="xs", c="dimmed", className="rh-code"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                ]
            )
        )

    log_headers = [
        dmc.TableTh("Thời gian", style={"minWidth": "140px", "whiteSpace": "nowrap"}),
        dmc.TableTh("Phạm vi", style={"minWidth": "110px", "whiteSpace": "nowrap"}),
        dmc.TableTh("Số run", style={"minWidth": "90px", "whiteSpace": "nowrap"}),
        dmc.TableTh("Dòng đã xóa", style={"minWidth": "120px", "whiteSpace": "nowrap"}),
        dmc.TableTh("Giải phóng", style={"minWidth": "120px", "whiteSpace": "nowrap"}),
        dmc.TableTh("Người xóa", style={"minWidth": "120px", "whiteSpace": "nowrap"}),
    ]

    log_table = (
        dmc.Card(
            [
                dmc.TableScrollContainer(
                    minWidth=750,
                    children=dmc.Table(
                        [
                            dmc.TableThead(dmc.TableTr(log_headers)),
                            dmc.TableTbody(log_rows),
                        ],
                        striped=False,
                        highlightOnHover=True,
                        withTableBorder=False,
                        withColumnBorders=False,
                        verticalSpacing="sm",
                    ),
                ),
            ],
            withBorder=True,
            radius="sm",
            padding=0,
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
                    button_danger(
                        "Xóa bản lưu SQLite cũ", id="ds-mig-delete-sqlite-open-btn", icon="lucide:trash", size="xs"
                    ),
                    html.Div(id="ds-mig-delete-sqlite-alert"),
                ],
                gap="sm",
            )
        else:
            sqlite_status_node = dmc.Text(
                "Không tìm thấy thông tin bản lưu SQLite cũ cần dọn dẹp.", size="sm", c="dimmed"
            )
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
                        # Nút "Xem trước" cùng hàng với 4 ô lọc, căn đáy
                        # theo ô nhập (không căn theo label) — task 65.
                        html.Div(
                            style={
                                "display": "flex",
                                "gap": "12px",
                                "alignItems": "flex-end",
                                "flexWrap": "nowrap",
                            },
                            children=[
                                html.Div(
                                    dmc.Select(
                                        id="ds-purge-filter-template",
                                        label="Template",
                                        placeholder="Tất cả template",
                                        data=[],
                                        clearable=True,
                                    ),
                                    style={"flex": "1", "minWidth": "0"},
                                ),
                                html.Div(
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
                                    style={"flex": "1", "minWidth": "0"},
                                ),
                                html.Div(
                                    dmc.NumberInput(
                                        id="ds-purge-filter-days",
                                        label="Chạy trước (số ngày)",
                                        placeholder="VD: 30",
                                    ),
                                    style={"flex": "1", "minWidth": "0"},
                                ),
                                html.Div(
                                    dmc.TextInput(
                                        id="ds-purge-filter-user",
                                        label="Người chạy",
                                        placeholder="Username",
                                    ),
                                    style={"flex": "1", "minWidth": "0"},
                                ),
                                html.Div(
                                    button_primary("Xem trước", id="ds-purge-preview-btn", icon="lucide:eye"),
                                    style={"flexShrink": "0"},
                                ),
                            ],
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
            # 2 card migration + script cùng một hàng (task 65): 2 cột
            # từ md (992px), dưới đó xếp dọc theo ui-dash.
            dmc.SimpleGrid(
                cols={"base": 1, "md": 2},
                spacing="md",
                children=[
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
                                    placeholder="Chọn Data Source Oracle..."
                                    if target_options
                                    else "Chưa có Data Source Oracle nào",
                                    data=target_options,
                                    clearable=True,
                                ),
                                dmc.Select(
                                    id="ds-mig-mode-select",
                                    label="Chế độ chuyển dữ liệu",
                                    data=[
                                        {
                                            "value": "NO_TEMP",
                                            "label": "NO_TEMP — Bỏ qua dữ liệu Excel tạm (Khuyên dùng)",
                                        },
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
                                button_subtle(
                                    "Xóa schema đích", id="ds-mig-clean-open-btn", color="red", icon="lucide:trash-2"
                                ),
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
        ],
        gap="lg",
    )


def layout() -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return dmc.Container(
            alert_box(
                title="Quyền truy cập bị từ chối",
                message="Trang Data Sources và Cấu hình lưu trữ chỉ dành cho Quản trị viên (ADMIN).",
                tone="crit",
            ),
            size="md",
            py="xl",
        )
    if ctx is None or not is_admin(ctx):
        return dmc.Container(
            alert_box(
                title="Quyền truy cập bị từ chối",
                message="Trang Data Sources và Cấu hình lưu trữ chỉ dành cho Quản trị viên (ADMIN).",
                tone="crit",
            ),
            size="md",
            py="xl",
        )

    return html.Div(
        style={
            "height": "calc(100vh - 48px)",
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "8px 12px",
        },
        children=[
            dcc.Store(id="ds-store-list"),
            dcc.Store(id="ds-store-storage"),
            dcc.Store(id="ds-active-trigger"),
            # Header
            page_header(
                title="Data Sources & Lưu trữ",
                subtitle="Quản lý kết nối Oracle đối soát và hạ tầng lưu trữ RECON_APP.",
                actions=[
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:refresh-cw", width=14),
                        id="ds-refresh-btn",
                        variant="subtle",
                        color="gray",
                        size="sm",
                    ),
                    button_primary("Thêm nguồn đối soát", id="ds-add-btn", icon="lucide:plus", size="xs"),
                ],
                style={"marginBottom": "8px"},
            ),
            # 2 Tabs
            dmc.Tabs(
                id="ds-tabs",
                value="sources",
                style={
                    "flex": 1,
                    "minHeight": 0,
                    "display": "flex",
                    "flexDirection": "column",
                    "overflow": "hidden",
                },
                children=[
                    dmc.TabsList(
                        [
                            dmc.TabsTab(
                                "Nguồn đối soát",
                                value="sources",
                                leftSection=DashIconify(icon="lucide:database", width=14),
                            ),
                            dmc.TabsTab(
                                "Lưu trữ RECON_APP",
                                value="storage",
                                leftSection=DashIconify(icon="lucide:hard-drive", width=14),
                            ),
                        ]
                    ),
                    dmc.TabsPanel(
                        [
                            html.Div(id="ds-active-alert", style={"paddingTop": "8px"}),
                            html.Div(
                                id="ds-sources-content",
                                style={
                                    "flex": 1,
                                    "minHeight": 0,
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "overflow": "hidden",
                                    "paddingTop": "8px",
                                },
                            ),
                        ],
                        value="sources",
                        style={
                            "flex": 1,
                            "minHeight": 0,
                            "display": "flex",
                            "flexDirection": "column",
                            "overflow": "hidden",
                        },
                    ),
                    dmc.TabsPanel(
                        html.Div(
                            id="ds-storage-content",
                            style={
                                "flex": 1,
                                "minHeight": 0,
                                "display": "flex",
                                "flexDirection": "column",
                                "overflowY": "auto",
                                "paddingTop": "12px",
                            },
                        ),
                        value="storage",
                        style={
                            "flex": 1,
                            "minHeight": 0,
                            "display": "flex",
                            "flexDirection": "column",
                            "overflow": "hidden",
                        },
                    ),
                ],
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
            # Modal chuyển dữ liệu sang Oracle (Task 63, layout 2 card
            # task 64): stepper 6 bước + switch thật/fake. Nút "Chuyển sang
            # Oracle" chỉ mở modal, chạy thật bắt đầu từ nút "Bắt đầu".
            # Modal vừa trang (~88vh), footer cố định; chỉ card detail
            # cuộn riêng khi checklist dài.
            dmc.Modal(
                id="ds-mig-modal",
                title=dmc.Text("Chuyển dữ liệu sang Oracle", fw=700, size="md"),
                size="1100px",
                opened=False,
                styles={
                    "content": {"height": "88vh", "display": "flex", "flexDirection": "column"},
                    "body": {
                        "flex": "1",
                        "minHeight": "0",
                        "display": "flex",
                        "flexDirection": "column",
                    },
                },
                children=dmc.Stack(
                    [
                        html.Div(id="ds-mig-modal-summary"),
                        dmc.Switch(
                            id="ds-mig-real-switch",
                            label="Migration thật",
                            checked=False,
                            size="sm",
                        ),
                        html.Div(id="ds-mig-real-warning"),
                        # Thanh tiến độ chạy từng bước (follow-up task 65):
                        # lúc idle để trống, hiện từ khi bấm Bắt đầu.
                        html.Div(id="ds-mig-progress"),
                        html.Div(
                            style={"display": "flex", "gap": "10px", "flex": "1", "minHeight": "0"},
                            children=[
                                dmc.Paper(
                                    [
                                        dmc.Text("Tiến trình", size="xs", fw=600, c="dimmed"),
                                        html.Div(id="ds-mig-stepper"),
                                    ],
                                    withBorder=True,
                                    radius="sm",
                                    p="sm",
                                    style={
                                        "width": "330px",
                                        "flexShrink": "0",
                                        "display": "flex",
                                        "flexDirection": "column",
                                        "minHeight": "0",
                                    },
                                ),
                                dmc.Paper(
                                    [
                                        html.Div(
                                            id="ds-mig-detail",
                                            style={
                                                "display": "flex",
                                                "flexDirection": "column",
                                                "flex": "1",
                                                "minHeight": "0",
                                            },
                                        )
                                    ],
                                    withBorder=True,
                                    radius="sm",
                                    p="sm",
                                    style={
                                        "flex": "1",
                                        "minHeight": "0",
                                        "display": "flex",
                                        "flexDirection": "column",
                                    },
                                ),
                            ],
                        ),
                        dmc.Group(
                            [
                                button_subtle("Đóng", id="ds-mig-modal-close-btn"),
                                button_primary("Bắt đầu", id="ds-mig-run-btn", icon="lucide:play"),
                            ],
                            justify="flex-end",
                            gap="sm",
                        ),
                    ],
                    gap="xs",
                    style={"flex": "1", "minHeight": "0"},
                ),
                radius="lg",
                withCloseButton=True,
            ),
            dcc.Store(id="ds-mig-state"),
            dcc.Store(id="ds-mig-selected-step"),
            dcc.Store(id="ds-mig-real-run-store"),
            dcc.Store(id="ds-mig-last-checklist-store"),
            dcc.Store(id="ds-mig-done-store"),
            dcc.Interval(id="ds-mig-fake-tick", interval=400, n_intervals=0, disabled=True),
            dcc.Interval(id="ds-mig-real-tick", interval=1500, n_intervals=0, disabled=True),
            dcc.Store(id="ds-purge-preview-store"),
        ],
    )


# Callbacks nạp dữ liệu Sources
@callback(
    Output("ds-store-list", "data"),
    Input("ds-refresh-btn", "n_clicks"),
    Input("ds-drawer-save-btn", "n_clicks"),
    Input("ds-active-trigger", "data"),
)
def load_sources_data(*args: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return {"items": [], "error": "Chưa đăng nhập"}

    res = list_data_sources(ctx, purpose="SOURCE")
    if not res.ok:
        return {"items": [], "error": res.message}

    raw_items = []
    for item in res.data or []:
        if hasattr(item, "model_dump"):
            raw_items.append(item.model_dump(mode="json"))
        elif isinstance(item, dict):
            raw_items.append(dict(item))
    return {"items": raw_items, "error": None}


@callback(
    Output("app-header-env-badge", "children", allow_duplicate=True),
    Output("app-header-env-badge", "color", allow_duplicate=True),
    Output("ds-active-trigger", "data"),
    Output("ds-active-alert", "children"),
    Input({"type": "ds-active-switch", "index": ALL}, "checked"),
    State({"type": "ds-active-switch", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def handle_ds_active_toggle(checked_values: list[bool], id_list: list[dict[str, Any]]) -> Any:
    """Xử lý bật/tắt switch kích hoạt Data Source đối soát và cập nhật Header Badge."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        raise dash.exceptions.PreventUpdate

    triggered_prop = ctx_dash.triggered[0]["prop_id"]
    if "ds-active-switch" not in triggered_prop:
        raise dash.exceptions.PreventUpdate

    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        raise dash.exceptions.PreventUpdate

    triggered_id = dash.ctx.triggered_id
    if not isinstance(triggered_id, dict) or triggered_id.get("type") != "ds-active-switch":
        raise dash.exceptions.PreventUpdate

    ds_id = triggered_id.get("index")
    if ds_id is None:
        raise dash.exceptions.PreventUpdate

    new_checked = False
    for item_id, val in zip(id_list, checked_values, strict=False):
        if item_id.get("index") == ds_id:
            new_checked = bool(val)
            break

    if new_checked:
        res = activate_data_source(ctx, int(ds_id))
    else:
        res = deactivate_data_source(ctx, int(ds_id))

    env = get_active_environment()
    env_badge_color = {
        "dev": "blue",
        "test": "gray",
        "uat": "yellow",
        "prod": "red",
    }.get(env.lower(), "blue")

    if not res.ok:
        alert_node = alert_box("Thao tác thất bại", res.message, tone="crit")
    else:
        st_text = "kích hoạt" if new_checked else "vô hiệu hóa"
        alert_node = alert_box(
            "Cập nhật môi trường thành công",
            f"Đã {st_text} nguồn dữ liệu thành công. Môi trường đối soát hiện tại: {env.upper()}.",
            tone="ok",
        )

    return env.upper(), env_badge_color, time.time(), alert_node


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
    # Task 63: nạp lại sau khi migration thật xong (khối SQLite cũ đổi trạng thái).
    Input("ds-mig-done-store", "data"),
)
def load_storage_data(*args: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
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


# Callback mở Drawer Thêm/Sửa
@callback(
    Output("ds-drawer", "opened"),
    Output("ds-drawer-id", "data"),
    Output("ds-drawer-name", "value"),
    Output("ds-drawer-env", "value"),
    Output("ds-drawer-host", "value"),
    Output("ds-drawer-port", "value"),
    Output("ds-drawer-service", "value"),
    Output("ds-drawer-user", "value"),
    Output("ds-drawer-pwd", "value"),
    Output("ds-drawer-schema", "value"),
    Output("ds-drawer-timeout", "value"),
    Output("ds-drawer-alert", "children", allow_duplicate=True),
    Input("ds-add-btn", "n_clicks"),
    Input({"type": "ds-edit-btn", "index": ALL}, "n_clicks"),
    Input("ds-drawer-cancel-btn", "n_clicks"),
    State("ds-drawer", "opened"),
    prevent_initial_call=True,
)
def handle_drawer_open(*args: Any) -> Any:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, None, "", "DEV", "", 1521, "", "", "", "", 600, None

    trigger = ctx_dash.triggered[0]
    trigger_val = trigger.get("value")
    trigger_id = trigger["prop_id"].split(".")[0]

    if "ds-drawer-cancel-btn" in trigger_id or not trigger_val:
        return False, None, "", "DEV", "", 1521, "", "", "", "", 600, None

    if trigger_id == "ds-add-btn":
        return True, None, "", "DEV", "", 1521, "", "", "", "", 600, None

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
                        "",  # Mật khẩu luôn để trống khi hiển thị form sửa
                        row["DEFAULT_SCHEMA"] or "",
                        row["CALL_TIMEOUT_S"] or 600,
                        None,  # Xóa alert cũ
                    )
    except Exception:
        pass

    return False, None, "", "DEV", "", 1521, "", "", "", "", 600, None


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
    if ctx is None or not is_admin(ctx):
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

    return alert_node, p_filter.model_dump(mode="json")


# Callback mở modal xác nhận Xóa
@callback(
    Output("ds-purge-confirm-modal", "opened"),
    Input("ds-purge-open-modal-btn", "n_clicks"),
    Input("ds-purge-confirm-modal-cancel", "n_clicks"),
    State("ds-purge-confirm-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_purge_confirm_modal(open_clicks: Any, cancel_clicks: Any, is_opened: bool) -> bool:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False
    trigger = ctx_dash.triggered[0]
    trigger_id = trigger["prop_id"].split(".")[0]
    trigger_val = trigger.get("value")
    return trigger_id == "ds-purge-open-modal-btn" and bool(trigger_val)


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
    if ctx is None or not is_admin(ctx):
        return False

    p_filter = PurgeFilter(**filter_data)
    purge_filter(ctx, p_filter, confirm_text="XOA")
    return False


# Callback Lưu nguồn đối soát (Thêm mới hoặc Cập nhật)
@callback(
    Output("ds-drawer-alert", "children", allow_duplicate=True),
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
    if ctx is None or not is_admin(ctx):
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
    State("ds-drawer-host", "value"),
    State("ds-drawer-port", "value"),
    State("ds-drawer-service", "value"),
    State("ds-drawer-user", "value"),
    State("ds-drawer-pwd", "value"),
    State("ds-drawer-timeout", "value"),
    prevent_initial_call=True,
)
def handle_test_drawer_connection(
    n_clicks: Any,
    ds_id: Any,
    host_val: str | None,
    port_val: Any,
    service_val: str | None,
    user_val: str | None,
    pwd_val: str | None,
    timeout_val: Any,
) -> Any:
    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return alert_box("Lỗi", "Chưa đăng nhập hoặc không đủ quyền Quản trị viên.", tone="crit")

    # Nếu chưa nhập host, service hoặc user
    if not host_val or not service_val or not user_val:
        if ds_id:
            res = test_data_source(ctx, int(ds_id))
        else:
            return alert_box(
                "Thiếu thông tin",
                "Vui lòng nhập Host, Service Name và Username để kiểm tra kết nối.",
                tone="warn",
                icon="lucide:alert-triangle",
            )
    else:
        p_val = int(port_val) if port_val else 1521
        to_val = int(timeout_val) if timeout_val else 600
        res = test_data_source_config(
            ctx=ctx,
            host=host_val.strip(),
            port=p_val,
            service_name=service_val.strip(),
            username=user_val.strip(),
            password=pwd_val.strip() if pwd_val else None,
            ds_id=int(ds_id) if ds_id else None,
            call_timeout_s=to_val,
            purpose="SOURCE",
        )

    if res.ok and res.data:
        d = res.data
        st = d.get("status")
        ms = d.get("latency_ms") or d.get("ms", 0)
        msg = d.get("message", "")
        privs = d.get("write_privileges", [])

        if st == "RO_OK" or (d.get("ok") and d.get("read_only") is True):
            return alert_box(
                title="Kết nối thành công",
                message=msg or f"Kết nối Oracle thành công ({ms}ms). Tài khoản chỉ đọc hợp lệ.",
                tone="ok",
                icon="lucide:check-circle-2",
            )
        elif st == "RO_WARN" or (d.get("ok") and (privs or not d.get("read_only", True))):
            return alert_box(
                title="Cảnh báo quyền ghi",
                message=f"{msg}. Nguồn đối soát nên sử dụng tài khoản chỉ đọc (SELECT) để bảo đảm an toàn dữ liệu. Bạn vẫn có thể lưu cấu hình này để sử dụng.",
                tone="warn",
                icon="lucide:alert-triangle",
            )
        elif d.get("ok"):
            return alert_box(
                title="Kết nối thành công",
                message=msg or f"Kết nối thành công ({ms}ms).",
                tone="ok",
                icon="lucide:check-circle-2",
            )
        else:
            return alert_box(
                title="Kết nối thất bại",
                message=msg
                or "Không thể kết nối đến máy chủ Oracle. Vui lòng kiểm tra lại kết nối VPN hoặc thông tin máy chủ.",
                tone="crit",
                icon="lucide:alert-circle",
            )

    return alert_box(
        title="Kết nối thất bại",
        message=res.message or "Lỗi khi kiểm tra kết nối đến cơ sở dữ liệu.",
        tone="crit",
        icon="lucide:alert-circle",
    )


# Callback kiểm tra kết nối nhanh từ bảng danh sách
@callback(
    Output("ds-store-list", "data", allow_duplicate=True),
    Input({"type": "ds-test-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_table_test_connection(n_clicks: list[Any]) -> Any:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update
    trigger = ctx_dash.triggered[0]
    trigger_id = trigger["prop_id"].split(".")[0]
    trigger_val = trigger.get("value")
    if not trigger_val:
        return dash.no_update

    try:
        parsed = json.loads(trigger_id)
        ds_id = parsed.get("index")
        if ds_id is not None:
            ctx = get_current_ctx()
            if ctx and is_admin(ctx):
                test_data_source(ctx, int(ds_id))
                refreshed = list_data_sources(ctx, purpose="SOURCE")
                if refreshed.ok and refreshed.data:
                    return {"items": [item.model_dump(mode="json") for item in refreshed.data], "error": None}
    except Exception:
        pass
    return dash.no_update


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
    if ctx is None or not is_admin(ctx):
        return alert_box("Từ chối", "Chỉ Quản trị viên (ADMIN) mới có quyền thực hiện.", tone="crit")

    res = precheck(ctx, int(target_ds_id), mode=mode or "NO_TEMP")
    if not res.ok or not res.data:
        return alert_box("Kiểm tra thất bại", res.message or "Không thể kiểm tra đích.", tone="crit")

    d = res.data
    table_rows = []
    for t in d.get("tables", []):
        table_rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Text(t["table"], size="xs", className="rh-code"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Text(f"{t['rows']:,}".replace(",", "."), size="xs"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Text(format_bytes(t["bytes_est"]), size="xs"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                ]
            )
        )

    t_node = dmc.Table(
        striped=False,
        highlightOnHover=True,
        verticalSpacing="xs",
        children=[
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh("Tên bảng", style={"whiteSpace": "nowrap"}),
                        dmc.TableTh("Số dòng", style={"whiteSpace": "nowrap"}),
                        dmc.TableTh("Ước tính", style={"whiteSpace": "nowrap"}),
                    ]
                )
            ),
            dmc.TableTbody(table_rows),
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


# --- Stepper chuyển Oracle trong modal (Task 63) ---


# Index bước 7 "Các bước làm tay" trong stepper (task 65).
_MIG_MANUAL_IDX = MIGRATION_STEP_KEYS.index(MANUAL_STEP_KEY)


def _empty_mig_state() -> dict[str, Any]:
    """Khung stepper 7 bước chưa chạy (bước 7 chưa có dòng con)."""
    return {
        "mode": "fake",
        "migration_id": None,
        "target_ds_id": 0,
        "target_name": "",
        "mode_label": "NO_TEMP",
        "status": "idle",
        "error": None,
        "steps": [
            {"key": key, "label": label, "error": None, "items": []}
            for key, label in zip(MIGRATION_STEP_KEYS, MIGRATION_STEP_LABELS, strict=True)
        ],
        "report": None,
        "next_steps": None,
    }


_MIG_CIRCLE_BASE: dict[str, Any] = {
    "display": "inline-flex",
    "alignItems": "center",
    "justifyContent": "center",
    "width": "28px",
    "height": "28px",
    "borderRadius": "50%",
    "fontSize": "13px",
    "fontWeight": 600,
    "flexShrink": 0,
}


def _mig_selected_index(state: dict[str, Any] | None, selected_idx: Any) -> int:
    """Bước đang chọn: giá trị store nếu hợp lệ, ngược lại bước đang chạy."""
    state = state or _empty_mig_state()
    steps = state.get("steps", [])
    if isinstance(selected_idx, int) and 0 <= selected_idx < len(steps):
        return selected_idx
    return running_step_index(state)


def _mig_count_unit(step_key: str) -> str:
    """Đơn vị đếm dòng phụ của stepper: bước sao chép đếm theo bảng."""
    return "bảng" if step_key == "copy" else "việc"


def _render_mig_stepper(state: dict[str, Any] | None, selected_idx: Any = None) -> Any:
    """Stepper dọc 7 bước (task 64, Master–Detail; bước 7 manual task 65):
    chỉ tên bước + dòng phụ trạng thái, bấm được để chọn bước (detail nằm
    ở card phải).

    Dòng phụ: xong "✓ n/n việc xong" (xanh); đang chạy "Đang: <item đang
    làm>" + "n/m bảng xong" (bước manual: "Tiếp theo: <item>"); chờ
    "Chờ • 0/m việc"; lỗi hiện thông báo lỗi. Vòng tròn đánh số kiểu
    wizard: xong ✓ xanh, đang chạy nền primary, lỗi ✗ đỏ, chưa chạy
    vòng xám.
    """
    if not state or not state.get("steps"):
        state = _empty_mig_state()
    steps = state["steps"]
    selected = _mig_selected_index(state, selected_idx)
    # Bước hiện tại: bước đang chạy/lỗi; nếu chưa có thì bước chờ đầu tiên
    # — nhưng lúc state còn idle (chưa bấm Bắt đầu) thì KHÔNG tô bước nào
    # là đang chạy, cả 7 bước đều hiện "Chờ" (task 65, sửa lỗi idle).
    overall = overall_status(state)
    current_idx = -1
    for i, step in enumerate(steps):
        if step_status(step) in ("running", "error"):
            current_idx = i
            break
    if current_idx < 0 and overall != "idle":
        for i, step in enumerate(steps):
            if step_status(step) == "pending":
                current_idx = i
                break

    ellipsis = {"whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"}
    blocks: list[Any] = []
    for i, step in enumerate(steps):
        st = step_status(step)
        is_current = i == current_idx
        is_selected = i == selected
        done, total = step_counts(step)
        unit = _mig_count_unit(str(step.get("key", "")))
        if st == "done":
            circle_text = "✓"
            circle_style = {
                **_MIG_CIRCLE_BASE,
                "border": "1px solid var(--success, #107c10)",
                "color": "var(--success, #107c10)",
                "backgroundColor": "var(--bg-surface, #fff)",
            }
            sub_lines: list[Any] = [dmc.Text(f"✓ {done}/{total} {unit} xong", size="xs", c="green")]
        elif st == "error":
            circle_text = "✗"
            circle_style = {
                **_MIG_CIRCLE_BASE,
                "border": "1px solid var(--danger, #c50f1f)",
                "color": "var(--danger, #c50f1f)",
                "backgroundColor": "var(--bg-surface, #fff)",
            }
            sub_lines = [dmc.Text(step.get("error") or "Lỗi", size="xs", c="red", style=ellipsis)]
        elif is_current:
            circle_text = str(i + 1)
            circle_style = {
                **_MIG_CIRCLE_BASE,
                "backgroundColor": "var(--primary, #0f6cbd)",
                "border": "1px solid var(--primary, #0f6cbd)",
                "color": "#fff",
            }
            run_item = running_item(step)
            if run_item is not None:
                # Bước manual không "chạy" mà chờ user làm tay: dòng phụ
                # ghi việc tiếp theo cần làm thay vì "Đang:" (task 65).
                prefix = "Tiếp theo:" if str(step.get("key", "")) == MANUAL_STEP_KEY else "Đang:"
                sub_lines = [
                    dmc.Text(f"{prefix} {run_item.get('label', '')}", size="xs", c="blue", style=ellipsis),
                    dmc.Text(f"{done}/{total} {unit} xong", size="xs", c="dimmed"),
                ]
            else:
                sub_lines = [dmc.Text("Đang chạy…", size="xs", c="blue")]
        else:
            circle_text = str(i + 1)
            circle_style = {
                **_MIG_CIRCLE_BASE,
                "border": "1px solid var(--border, #e0e0e0)",
                "color": "var(--text-muted, #616161)",
                "backgroundColor": "var(--bg-surface, #fff)",
            }
            sub_lines = [dmc.Text(f"Chờ • 0/{total} {unit}" if total else "Chờ", size="xs", c="dimmed")]
        connector = (
            html.Div(
                style={
                    "width": "1px",
                    "flex": "1",
                    "minHeight": "12px",
                    "backgroundColor": "var(--border, #e0e0e0)",
                }
            )
            if i < len(steps) - 1
            else html.Div()
        )
        blocks.append(
            html.Div(
                id={"type": "mig-step", "index": i},
                n_clicks=0,
                style={
                    "display": "flex",
                    "gap": "10px",
                    "padding": "4px 8px",
                    "borderRadius": "6px",
                    "cursor": "pointer",
                    **({"backgroundColor": "var(--mantine-color-blue-0)"} if is_selected else {}),
                },
                children=[
                    html.Div(
                        style={
                            "display": "flex",
                            "flexDirection": "column",
                            "alignItems": "center",
                            "flexShrink": "0",
                        },
                        children=[html.Span(circle_text, style=circle_style), connector],
                    ),
                    html.Div(
                        style={"paddingTop": "4px", "minWidth": "0", "flex": "1"},
                        children=[
                            dmc.Text(
                                step.get("label", f"Bước {i + 1}"),
                                size="sm",
                                fw=600 if is_current else 500,
                            ),
                            *sub_lines,
                        ],
                    ),
                ],
            )
        )
    return dmc.Stack(blocks, gap=0)


def _render_mig_progress(state: dict[str, Any] | None) -> Any:
    """Thanh tiến độ chạy từng bước (follow-up task 65): % theo số việc
    xong/tổng số việc của 6 bước tự động (không tính bước 7 manual).
    Lúc idle trả div trống (không hiện bar); xong thì 100%; lỗi thì bar
    đỏ + tên bước lỗi."""
    if not state or not state.get("steps"):
        return html.Div()
    overall = overall_status(state)
    if overall == "idle":
        return html.Div()
    done, total = progress_counts(state)
    if total <= 0:
        return html.Div()
    pct = int(round(100 * done / total))
    if overall == "done":
        return dmc.Stack(
            [
                dmc.Text(f"Hoàn tất {done}/{total} việc", size="xs", c="dimmed"),
                dmc.Progress(value=100, size="sm", color="green"),
            ],
            gap=4,
        )
    if overall == "error":
        err_idx = error_step_index(state)
        err_idx = err_idx if err_idx is not None else running_step_index(state)
        label = MIGRATION_STEP_LABELS[err_idx] if 0 <= err_idx < len(MIGRATION_STEP_LABELS) else f"Bước {err_idx + 1}"
        return dmc.Stack(
            [
                dmc.Text(
                    f"Lỗi ở bước {err_idx + 1}/6 · {label} — {done}/{total} việc ({pct}%)",
                    size="xs",
                    c="red",
                ),
                dmc.Progress(value=pct, size="sm", color="red"),
            ],
            gap=4,
        )
    run_idx = running_step_index(state)
    label = MIGRATION_STEP_LABELS[run_idx] if 0 <= run_idx < len(MIGRATION_STEP_LABELS) else f"Bước {run_idx + 1}"
    return dmc.Stack(
        [
            dmc.Text(
                f"Đang chạy bước {run_idx + 1}/6 · {label} — {done}/{total} việc ({pct}%)",
                size="xs",
                c="dimmed",
            ),
            dmc.Progress(value=pct, size="sm", color="blue"),
        ],
        gap=4,
    )


def _render_mig_detail(state: dict[str, Any] | None, selected_idx: Any = None, alert: Any = None) -> Any:
    """Card chi tiết bước (task 64, Master–Detail; bước 7 manual task 65):
    header (tên bước + badge trạng thái + "n/m việc xong") + checklist
    dòng con của bước đang chọn (cuộn riêng khi dài) + báo cáo đối chiếu
    ở bước Hoàn tất khi chạy xong. Bước manual có checkbox để tick từng
    việc làm tay; chưa chạy xong 6 bước thì chỉ hiện ghi chú.
    """
    if not state or not state.get("steps"):
        state = _empty_mig_state()
    steps = state["steps"]
    idx = _mig_selected_index(state, selected_idx)
    step = steps[idx]
    st = step_status(step)
    done, total = step_counts(step)
    # Lúc idle (chưa bấm Bắt đầu) không bước nào là "đang chạy" — tránh
    # badge "Đang chạy" ở detail bước 7 khi user bấm vào nó (task 65).
    is_current = idx == running_step_index(state) and overall_status(state) != "idle"
    is_manual = str(step.get("key", "")) == MANUAL_STEP_KEY
    if st == "done":
        badge = dmc.Badge("Xong", color="green", variant="light", size="xs")
    elif st == "error":
        badge = dmc.Badge("Lỗi", color="red", variant="light", size="xs")
    elif is_manual and step.get("items"):
        badge = dmc.Badge("Cần làm tay", color="blue", variant="light", size="xs")
    elif is_current:
        badge = dmc.Badge("Đang chạy", color="blue", variant="light", size="xs")
    else:
        badge = dmc.Badge("Chờ", color="gray", variant="light", size="xs")
    header = dmc.Group(
        [
            dmc.Text(step.get("label", f"Bước {idx + 1}"), size="sm", fw=700),
            badge,
            dmc.Text(
                f"{done}/{total} việc xong",
                size="xs",
                c="dimmed",
                style={"marginLeft": "auto"},
            ),
        ],
        gap="xs",
        align="center",
    )
    run_item = running_item(step) if (is_current and st not in ("done", "error")) else None
    item_rows: list[Any] = []
    for item in step.get("items", []):
        ist = item.get("status")
        is_run = run_item is not None and item.get("id") == run_item.get("id")
        if is_manual:
            # Bước làm tay: checkbox để user tick khi xong từng việc
            # (task 65). Việc tiếp theo được gắn nhãn để dễ thấy.
            item_rows.append(
                dmc.Group(
                    [
                        dmc.Checkbox(
                            id={"type": "mig-manual-check", "item": str(item.get("id", ""))},
                            checked=ist == "done",
                            size="xs",
                        ),
                        dmc.Text(
                            item.get("label", ""),
                            size="xs",
                            style=(
                                {"fontWeight": 600, "color": "var(--primary, #0f6cbd)"}
                                if is_run
                                else (
                                    {"color": "var(--text-muted, #616161)"}
                                    if ist == "pending"
                                    else {}
                                )
                            ),
                        ),
                        dmc.Badge("Tiếp theo", color="blue", variant="light", size="xs")
                        if is_run
                        else html.Div(),
                    ],
                    gap="xs",
                    align="center",
                )
            )
            continue
        if ist == "done":
            icon, color = "✓", "green"
            row_style: dict[str, Any] = {}
            label_style: dict[str, Any] = {}
            extra: Any = html.Div()
        elif is_run:
            icon, color = "●", "blue"
            row_style = {
                "backgroundColor": "var(--mantine-color-blue-0)",
                "borderRadius": "6px",
                "padding": "4px 6px",
            }
            label_style = {"fontWeight": 600, "color": "var(--primary, #0f6cbd)"}
            extra = dmc.Badge("Đang chạy", color="blue", variant="light", size="xs")
        elif ist == "error":
            icon, color = "✗", "red"
            row_style = {}
            label_style = {}
            extra = html.Div()
        else:
            icon, color = "○", "dimmed"
            row_style = {}
            label_style = {"color": "var(--text-muted, #616161)"}
            extra = html.Div()
        item_rows.append(
            dmc.Group(
                [
                    dmc.Text(icon, size="xs", c=color, style={"width": "14px", "flexShrink": 0}),
                    dmc.Text(item.get("label", ""), size="xs", style=label_style),
                    dmc.Text(item.get("detail") or "", size="xs", c="dimmed"),
                    extra,
                ],
                gap="xs",
                align="center",
                style=row_style,
            )
        )
    content: list[Any] = []
    if alert is not None:
        content.append(alert)
    if step.get("error"):
        content.append(alert_box("Bước này lỗi", str(step.get("error")), tone="crit"))
    if not item_rows:
        if is_manual:
            content.append(
                dmc.Text(
                    "Chạy xong 6 bước thì mới làm các bước này.",
                    size="sm",
                    c="dimmed",
                    py="md",
                    ta="center",
                )
            )
        else:
            content.append(
                dmc.Text(
                    "Chưa có dữ liệu — bấm “Bắt đầu” để chạy.",
                    size="sm",
                    c="dimmed",
                    py="md",
                    ta="center",
                )
            )
    else:
        content.extend(item_rows)
    # Báo cáo đối chiếu nằm ở detail bước Hoàn tất (key "finish", task 65)
    # — không dời sang bước 7 manual (bước cuối trong stepper).
    if str(step.get("key", "")) == "finish" and overall_status(state) == "done":
        content.append(
            _render_mig_report(
                state.get("report"),
                migration_id=state.get("migration_id"),
                fake=str(state.get("mode")) == "fake",
            )
        )
    return dmc.Stack(
        [
            header,
            dmc.ScrollArea(
                dmc.Stack(content, gap="xs"),
                style={"flex": "1", "minHeight": "0"},
            ),
        ],
        gap="xs",
        style={"flex": "1", "minHeight": "0"},
    )


def _render_mig_report(
    report: dict[str, Any] | None,
    migration_id: int | None = None,
    fake: bool = False,
) -> Any:
    """Bảng đối chiếu từng bảng sau khi migration xong.

    Follow-up task 65: không vẽ khối "Các bước tiếp theo cần thực hiện"
    nữa — 4 bước đó đã là item tick được của bước 7 "Các bước làm tay".
    Nguồn dữ liệu next_steps trong state vẫn giữ nguyên (dùng để tạo
    item bước 7), chỉ bỏ phần vẽ ở đây.

    D10: đọc đúng khóa source_rows/target_rows của REPORT_JSON (code cũ đọc
    nhầm src_rows/tgt_rows nên bảng luôn hiện 0).
    """
    comp_rows: list[Any] = []
    for t_name, info in (report or {}).items():
        comp_rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Text(t_name, size="xs", className="rh-code"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Text(f"{info.get('source_rows', 0):,}".replace(",", "."), size="xs"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Text(f"{info.get('target_rows', 0):,}".replace(",", "."), size="xs"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Badge("Khớp SHA256", color="ok", variant="light", size="xs")
                        if info.get("checksum_matched")
                        else dmc.Badge("Chưa kiểm tra", color="gray", variant="light", size="xs"),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                ]
            )
        )
    t_report = dmc.Table(
        striped=False,
        highlightOnHover=True,
        verticalSpacing="xs",
        children=[
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh("Bảng", style={"whiteSpace": "nowrap"}),
                        dmc.TableTh("Nguồn (SQLite)", style={"whiteSpace": "nowrap"}),
                        dmc.TableTh("Đích (Oracle)", style={"whiteSpace": "nowrap"}),
                        dmc.TableTh("Đối chiếu", style={"whiteSpace": "nowrap"}),
                    ]
                )
            ),
            dmc.TableTbody(comp_rows),
        ],
    )
    if migration_id:
        title = f"Chuyển dữ liệu thành công! (Phiên #{migration_id})"
    elif fake:
        title = "Chuyển dữ liệu thành công (mô phỏng)!"
    else:
        title = "Chuyển dữ liệu thành công!"
    return alert_box(
        title=title,
        message=dmc.Stack(
            [
                dmc.Text("Tất cả các bảng đã được sao chép và đối chiếu toàn vẹn dữ liệu:", size="sm", fw=600),
                dmc.ScrollArea(t_report, h=220),
            ],
            gap="xs",
        ),
        tone="ok",
        icon="lucide:check-circle-2",
    )


def _mig_target_name(ctx: Any, ds_id: Any) -> str:
    """Tên Data Source đích theo id (fallback 'ID <id>' khi không tìm thấy)."""
    try:
        res = list_data_sources(ctx)
        if res.ok and res.data:
            for item in res.data:
                data = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
                if int(data.get("id", -1)) == int(ds_id):
                    return str(data.get("name", ""))
    except Exception:
        pass
    return f"ID {ds_id}"


@callback(
    Output("ds-mig-modal", "opened"),
    Output("ds-mig-modal-summary", "children"),
    Output("ds-mig-real-switch", "checked"),
    Output("ds-mig-real-warning", "children", allow_duplicate=True),
    Output("ds-mig-stepper", "children", allow_duplicate=True),
    Output("ds-mig-detail", "children", allow_duplicate=True),
    Output("ds-mig-selected-step", "data", allow_duplicate=True),
    Output("ds-mig-state", "data", allow_duplicate=True),
    Output("ds-mig-real-run-store", "data", allow_duplicate=True),
    Output("ds-mig-fake-tick", "disabled", allow_duplicate=True),
    Output("ds-mig-real-tick", "disabled", allow_duplicate=True),
    Output("ds-mig-run-btn", "disabled", allow_duplicate=True),
    Output("ds-mig-result-container", "children", allow_duplicate=True),
    Output("ds-mig-progress", "children", allow_duplicate=True),
    Input("ds-mig-start-btn", "n_clicks"),
    Input("ds-mig-modal-close-btn", "n_clicks"),
    State("ds-mig-modal", "opened"),
    State("ds-mig-target-select", "value"),
    State("ds-mig-mode-select", "value"),
    prevent_initial_call=True,
)
def toggle_mig_modal(
    open_clicks: Any, close_clicks: Any, is_opened: bool, target_ds_id: Any, mode: str | None
) -> tuple[Any, ...]:
    """Mở modal chuyển Oracle / đóng modal (task 63, layout 2 card task 64).

    Mở: tóm tắt đích + chế độ, reset switch về fake, khôi phục phiên
    PROCESSING nếu có (bước chọn mặc định = bước đang chạy). Đóng: dừng
    cả 2 tick (migration thật vẫn chạy nền, mở lại sẽ thấy đúng tiến độ).
    """
    no_update_14 = (dash.no_update,) * 14
    if not open_clicks and not close_clicks:
        return no_update_14
    triggered = dash.callback_context.triggered_id
    # Task 65: nút mở nằm trong tab Lưu trữ nên bị tạo lại mỗi khi tab vẽ
    # lại (vd reload storage sau khi migration thật DONE) — n_clicks về 0
    # và callback kích hoạt dù user không bấm. Click thật luôn có n_clicks
    # >= 1 nên lần kích hoạt với nút vừa bấm = 0 là giả, bỏ qua để modal
    # không tự đóng. (Guard cũ chỉ chặn (0, 0); trường hợp (0, >= 1) —
    # user từng bấm Đóng trước đó — vẫn lọt và đọc target_ds_id=None do
    # select đích cũng bị tạo lại, trả opened=False.)
    if triggered == "ds-mig-start-btn" and not open_clicks:
        return no_update_14
    if triggered == "ds-mig-modal-close-btn" and not close_clicks:
        return no_update_14
    if triggered == "ds-mig-modal-close-btn":
        return (False, *(dash.no_update,) * 8, True, True, dash.no_update, dash.no_update, dash.no_update)
    if triggered != "ds-mig-start-btn":
        return no_update_14
    # Task 65: mở lại để khôi phục phiên (đang chạy / DONE còn bước tay)
    # KHÔNG cần select đích — hai nhánh dưới dùng TARGET_DS_ID lưu trong DB.
    # Chỉ mở mới (empty state, cuối hàm) mới cần target để ghi tóm tắt.
    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return (
            False,
            *(dash.no_update,) * 11,
            alert_box("Từ chối", "Chỉ Quản trị viên (ADMIN) mới có quyền thực hiện.", tone="crit"),
            dash.no_update,
        )
    mode_label = mode or "NO_TEMP"
    active = get_active_migration(ctx)
    if active.ok and active.data:
        target_name = _mig_target_name(ctx, active.data.get("TARGET_DS_ID"))
        summary = dmc.Stack(
            [
                dmc.Text(f"Đang có phiên #{active.data.get('ID')} chạy dở.", size="sm", fw=600),
                dmc.Text(
                    f"Đích: {target_name} · Chế độ: {active.data.get('MODE')} · Mở lại để theo dõi tiến độ.",
                    size="sm",
                    c="dimmed",
                ),
            ],
            gap=2,
        )
        checklist = active.data.get("checklist") or _empty_mig_state()
        selected = running_step_index(checklist)
        started_at = active.data.get("CREATED_AT")
        run_store = {
            "run_token": None,
            "target_ds_id": int(active.data.get("TARGET_DS_ID") or 0),
            "mode": str(active.data.get("MODE") or "NO_TEMP"),
            "started_at": started_at.isoformat() if hasattr(started_at, "isoformat") else str(started_at or ""),
            "migration_id": int(active.data.get("ID") or 0),
        }
        return (
            True,
            summary,
            False,
            html.Div(),
            _render_mig_stepper(checklist, selected),
            _render_mig_detail(checklist, selected),
            selected,
            checklist,
            run_store,
            True,
            False,
            True,
            dash.no_update,
            _render_mig_progress(checklist),
        )
    # Task 65: không có phiên đang chạy thì khôi phục phiên DONE gần nhất
    # còn bước làm tay chưa tick hết — tick đã lưu trong CHECKLIST_JSON
    # không bị mất khi đóng/mở lại modal.
    latest = get_latest_migration(ctx)
    if latest.ok and latest.data and str(latest.data.get("STATUS")) == "DONE":
        checklist = latest.data.get("checklist") or _empty_mig_state()
        manual_step = next(
            (s for s in checklist.get("steps", []) if s.get("key") == MANUAL_STEP_KEY),
            None,
        )
        manual_items = manual_step.get("items", []) if manual_step else []
        pending = sum(1 for i in manual_items if i.get("status") != "done")
        if manual_items and pending > 0:
            done_target_name = _mig_target_name(ctx, latest.data.get("TARGET_DS_ID"))
            summary = dmc.Stack(
                [
                    dmc.Text(
                        f"Phiên #{latest.data.get('ID')} đã xong — còn {pending}/{len(manual_items)} bước làm tay chưa đánh dấu.",
                        size="sm",
                        fw=600,
                    ),
                    dmc.Text(
                        f"Đích: {done_target_name} · Chế độ: {latest.data.get('MODE')} · Tick các bước làm tay khi hoàn thành.",
                        size="sm",
                        c="dimmed",
                    ),
                ],
                gap=2,
            )
            return (
                True,
                summary,
                False,
                html.Div(),
                _render_mig_stepper(checklist, _MIG_MANUAL_IDX),
                _render_mig_detail(checklist, _MIG_MANUAL_IDX),
                _MIG_MANUAL_IDX,
                checklist,
                None,
                True,
                True,
                False,
                dash.no_update,
                _render_mig_progress(checklist),
            )
    # Task 65: chỉ mở mới (không có phiên để khôi phục) mới cần target —
    # select đích có thể đã reset về None sau khi tab Lưu trữ vẽ lại.
    if not target_ds_id:
        return (
            False,
            *(dash.no_update,) * 11,
            alert_box("Lưu ý", "Vui lòng chọn Data Source Oracle đích trước khi chuyển.", tone="warn"),
            dash.no_update,
        )
    target_name = _mig_target_name(ctx, target_ds_id)
    summary = dmc.Stack(
        [
            dmc.Text(f"Đích: {target_name} · Chế độ: {mode_label}", size="sm", fw=600),
            dmc.Text(
                "Mặc định chạy giả lập để kiểm tra trước — không ghi gì sang Oracle. "
                "Gạt switch 'Migration thật' để chạy thật.",
                size="sm",
                c="dimmed",
            ),
        ],
        gap=2,
    )
    empty = _empty_mig_state()
    return (
        True,
        summary,
        False,
        html.Div(),
        _render_mig_stepper(empty, 0),
        _render_mig_detail(empty, 0),
        0,
        None,
        None,
        True,
        True,
        False,
        dash.no_update,
        _render_mig_progress(empty),
    )


@callback(
    Output("ds-mig-state", "data", allow_duplicate=True),
    Output("ds-mig-real-run-store", "data", allow_duplicate=True),
    Output("ds-mig-fake-tick", "disabled", allow_duplicate=True),
    Output("ds-mig-real-tick", "disabled", allow_duplicate=True),
    Output("ds-mig-stepper", "children", allow_duplicate=True),
    Output("ds-mig-detail", "children", allow_duplicate=True),
    Output("ds-mig-selected-step", "data", allow_duplicate=True),
    Output("ds-mig-run-btn", "disabled", allow_duplicate=True),
    Output("ds-mig-progress", "children", allow_duplicate=True),
    Input("ds-mig-run-btn", "n_clicks"),
    State("ds-mig-target-select", "value"),
    State("ds-mig-mode-select", "value"),
    State("ds-mig-real-switch", "checked"),
    prevent_initial_call=True,
)
def handle_mig_run(n_clicks: Any, target_ds_id: Any, mode: str | None, real_checked: Any) -> tuple[Any, ...]:
    """Bắt đầu chạy trong modal: fake = precheck thật + mô phỏng; real =
    precheck thật + migration thật trong luồng nền."""
    if not n_clicks:
        return (dash.no_update,) * 9
    ctx = get_current_ctx()
    empty = _empty_mig_state()
    if ctx is None or not is_admin(ctx):
        return (
            None,
            None,
            True,
            True,
            _render_mig_stepper(empty, 0),
            _render_mig_detail(
                empty,
                0,
                alert=alert_box(
                    "Từ chối",
                    "Chỉ Quản trị viên (ADMIN) mới có quyền thực hiện.",
                    tone="crit",
                ),
            ),
            0,
            False,
            _render_mig_progress(empty),
        )
    if not target_ds_id:
        return (
            None,
            None,
            True,
            True,
            _render_mig_stepper(empty, 0),
            _render_mig_detail(
                empty,
                0,
                alert=alert_box(
                    "Lưu ý",
                    "Vui lòng chọn Data Source Oracle đích trước khi chuyển.",
                    tone="warn",
                ),
            ),
            0,
            False,
            _render_mig_progress(empty),
        )
    mode_label = mode or "NO_TEMP"
    res = precheck(ctx, int(target_ds_id), mode=mode_label)
    if not res.ok or not res.data:
        err_state = _empty_mig_state()
        mark_step_error(err_state, "precheck", res.message or "Kiểm tra trước thất bại.")
        return (
            err_state,
            None,
            True,
            True,
            _render_mig_stepper(err_state, 0),
            _render_mig_detail(
                err_state,
                0,
                alert=alert_box(
                    "Kiểm tra thất bại",
                    res.message or "Không thể kiểm tra đích.",
                    tone="crit",
                ),
            ),
            0,
            False,
            _render_mig_progress(err_state),
        )
    if not real_checked:
        state = build_fake_checklist(res.data)
        selected = running_step_index(state)
        return (
            state,
            None,
            False,
            True,
            _render_mig_stepper(state, selected),
            _render_mig_detail(state, selected),
            selected,
            True,
            _render_mig_progress(state),
        )
    active = get_active_migration(ctx)
    if active.ok and active.data:
        checklist = active.data.get("checklist") or _empty_mig_state()
        selected = running_step_index(checklist)
        return (
            checklist,
            None,
            True,
            True,
            _render_mig_stepper(checklist, selected),
            _render_mig_detail(
                checklist,
                selected,
                alert=alert_box(
                    "Đang chạy",
                    f"Đang có phiên #{active.data.get('ID')} chạy. Hãy mở lại modal để theo dõi.",
                    tone="warn",
                ),
            ),
            selected,
            False,
            _render_mig_progress(checklist),
        )
    run_token = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    thread = threading.Thread(
        target=run_migration_background,
        args=(ctx, int(target_ds_id), mode_label, run_token),
        daemon=True,
    )
    thread.start()
    run_store = {
        "run_token": run_token,
        "target_ds_id": int(target_ds_id),
        "mode": mode_label,
        "started_at": started_at,
    }
    init_state = new_checklist(
        mode="real",
        target_ds_id=int(target_ds_id),
        target_name=str(res.data.get("target_name", "")),
        mode_label=mode_label,
        tables=list(res.data.get("tables", [])),
        top_tables=[],
    )
    mark_items_done(init_state, "precheck")
    refresh_status(init_state)
    selected = running_step_index(init_state)
    return (
        init_state,
        run_store,
        True,
        False,
        _render_mig_stepper(init_state, selected),
        _render_mig_detail(init_state, selected),
        selected,
        True,
        _render_mig_progress(init_state),
    )


@callback(
    Output("ds-mig-state", "data", allow_duplicate=True),
    Output("ds-mig-stepper", "children", allow_duplicate=True),
    Output("ds-mig-fake-tick", "disabled", allow_duplicate=True),
    Output("ds-mig-detail", "children", allow_duplicate=True),
    Output("ds-mig-selected-step", "data", allow_duplicate=True),
    Output("ds-mig-run-btn", "disabled", allow_duplicate=True),
    Output("ds-mig-progress", "children", allow_duplicate=True),
    Input("ds-mig-fake-tick", "n_intervals"),
    State("ds-mig-state", "data"),
    State("ds-mig-selected-step", "data"),
    prevent_initial_call=True,
)
def handle_mig_fake_tick(n_intervals: Any, state: Any, selected: Any) -> tuple[Any, ...]:
    """Mỗi tick mô phỏng xong thêm 4 dòng checklist (task 63, D8).

    Bước chọn giữ nguyên lựa chọn của user (sticky); chỉ khi chạy xong
    mới nhảy sang bước 7 "Các bước làm tay" để thấy ngay 4 bước tay
    (task 65, thay D4 task 64 chọn bước 6).
    """
    if not state:
        return (dash.no_update, dash.no_update, True, dash.no_update, dash.no_update, dash.no_update, dash.no_update)
    new_state = advance_fake_checklist(state, per_tick=4)
    selected = _mig_selected_index(new_state, selected)
    if overall_status(new_state) == "done":
        return (
            new_state,
            _render_mig_stepper(new_state, _MIG_MANUAL_IDX),
            True,
            _render_mig_detail(new_state, _MIG_MANUAL_IDX),
            _MIG_MANUAL_IDX,
            False,
            _render_mig_progress(new_state),
        )
    return (
        new_state,
        _render_mig_stepper(new_state, selected),
        False,
        _render_mig_detail(new_state, selected),
        dash.no_update,
        True,
        _render_mig_progress(new_state),
    )


@callback(
    Output("ds-mig-state", "data", allow_duplicate=True),
    Output("ds-mig-stepper", "children", allow_duplicate=True),
    Output("ds-mig-detail", "children", allow_duplicate=True),
    Output("ds-mig-real-tick", "disabled", allow_duplicate=True),
    Output("ds-mig-run-btn", "disabled", allow_duplicate=True),
    Output("ds-mig-selected-step", "data", allow_duplicate=True),
    Output("ds-mig-done-store", "data"),
    Output("ds-mig-last-checklist-store", "data"),
    Output("ds-mig-progress", "children", allow_duplicate=True),
    Input("ds-mig-real-tick", "n_intervals"),
    State("ds-mig-real-run-store", "data"),
    State("ds-mig-last-checklist-store", "data"),
    State("ds-mig-selected-step", "data"),
    prevent_initial_call=True,
)
def handle_mig_real_tick(n_intervals: Any, run_store: Any, last_raw: Any, selected: Any) -> tuple[Any, ...]:
    """Poll phiên migration thật mỗi 1,5s: vẽ stepper + detail từ
    CHECKLIST_JSON, dừng khi DONE/FAILED, không vẽ lại khi checklist
    không đổi. Bước chọn giữ nguyên lựa chọn của user; chỉ khi xong mới
    nhảy sang bước 7 "Các bước làm tay" (task 65), khi lỗi nhảy sang
    bước lỗi."""
    if not run_store:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            True,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )
    ctx = get_current_ctx()
    if ctx is None or not is_admin(ctx):
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            True,
            False,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )
    token = run_store.get("run_token")
    if token:
        outcome = get_migration_run_result(token)
        if outcome is not None and not outcome.get("ok") and not outcome.get("migration_id"):
            err_state = _empty_mig_state()
            mark_step_error(err_state, "precheck", str(outcome.get("message") or "Chuyển dữ liệu thất bại."))
            return (
                err_state,
                _render_mig_stepper(err_state, 0),
                _render_mig_detail(
                    err_state,
                    0,
                    alert=alert_box(
                        "Chuyển dữ liệu thất bại",
                        str(outcome.get("message") or "Có lỗi xảy ra trong quá trình chuyển."),
                        tone="crit",
                    ),
                ),
                True,
                False,
                0,
                dash.no_update,
                dash.no_update,
                _render_mig_progress(err_state),
            )
    row_res = get_migration_for_poll(ctx, int(run_store["target_ds_id"]), str(run_store.get("started_at") or ""))
    if not row_res.ok or not row_res.data:
        started = str(run_store.get("started_at") or "")
        try:
            elapsed = (
                datetime.now(timezone.utc).replace(tzinfo=None) - datetime.fromisoformat(started)
            ).total_seconds()
        except (ValueError, TypeError):
            elapsed = 0
        if elapsed > 30:
            empty = _empty_mig_state()
            return (
                empty,
                _render_mig_stepper(empty, 0),
                _render_mig_detail(
                    empty,
                    0,
                    alert=alert_box(
                        "Chuyển dữ liệu thất bại",
                        "Không thấy phiên migration sau 30 giây — có thể kiểm tra trước thất bại. Hãy thử lại.",
                        tone="crit",
                    ),
                ),
                True,
                False,
                0,
                dash.no_update,
                dash.no_update,
                _render_mig_progress(empty),
            )
        return (dash.no_update,) * 9
    row = row_res.data
    checklist = row.get("checklist") or _empty_mig_state()
    raw = json.dumps(checklist, sort_keys=True, ensure_ascii=False)
    if raw == (last_raw or ""):
        return (dash.no_update,) * 9
    selected = _mig_selected_index(checklist, selected)
    status = str(row.get("STATUS") or "")
    if status == "DONE":
        return (
            checklist,
            _render_mig_stepper(checklist, _MIG_MANUAL_IDX),
            _render_mig_detail(checklist, _MIG_MANUAL_IDX),
            True,
            False,
            _MIG_MANUAL_IDX,
            {"migration_id": int(row.get("ID") or 0)},
            raw,
            _render_mig_progress(checklist),
        )
    if status == "FAILED":
        err_idx = error_step_index(checklist)
        err_idx = err_idx if err_idx is not None else running_step_index(checklist)
        return (
            checklist,
            _render_mig_stepper(checklist, err_idx),
            _render_mig_detail(
                checklist,
                err_idx,
                alert=alert_box(
                    "Chuyển dữ liệu thất bại",
                    f"{row.get('ERROR_MSG') or 'Có lỗi xảy ra trong quá trình chuyển.'} Hãy xóa schema đích rồi chạy lại.",
                    tone="crit",
                ),
            ),
            True,
            False,
            err_idx,
            dash.no_update,
            raw,
            _render_mig_progress(checklist),
        )
    return (
        checklist,
        _render_mig_stepper(checklist, selected),
        _render_mig_detail(checklist, selected),
        False,
        True,
        dash.no_update,
        dash.no_update,
        raw,
        _render_mig_progress(checklist),
    )


@callback(
    Output("ds-mig-selected-step", "data", allow_duplicate=True),
    Output("ds-mig-detail", "children", allow_duplicate=True),
    Output("ds-mig-stepper", "children", allow_duplicate=True),
    Input({"type": "mig-step", "index": ALL}, "n_clicks"),
    State("ds-mig-state", "data"),
    State("ds-mig-selected-step", "data"),
    prevent_initial_call=True,
)
def handle_mig_step_click(clicks: Any, state: Any, selected: Any) -> tuple[Any, ...]:
    """Bấm một bước trong stepper thì chọn bước đó để xem detail (task 64).

    Follow-up task 65: trả thêm stepper vẽ lại theo bước vừa bấm — trước
    đây chỉ trả detail nên highlight bên trái giữ nguyên ở bước cũ (vd
    bấm bước 6 sau khi xong, detail sang "Hoàn tất" nhưng highlight vẫn
    ở bước 7).

    Guard: lần vẽ lại stepper (tick/poll) tạo lại các div với n_clicks=0
    sẽ kích hoạt callback — trả no_update khi không có click thật.
    """
    if not any(c for c in (clicks or [])):
        return dash.no_update, dash.no_update, dash.no_update
    triggered = dash.callback_context.triggered_id
    if not isinstance(triggered, dict) or triggered.get("type") != "mig-step":
        return dash.no_update, dash.no_update, dash.no_update
    idx = triggered.get("index")
    if not isinstance(idx, int):
        return dash.no_update, dash.no_update, dash.no_update
    checklist = state or _empty_mig_state()
    return idx, _render_mig_detail(checklist, idx), _render_mig_stepper(checklist, idx)


@callback(
    Output("ds-mig-state", "data", allow_duplicate=True),
    Output("ds-mig-stepper", "children", allow_duplicate=True),
    Output("ds-mig-detail", "children", allow_duplicate=True),
    Input({"type": "mig-manual-check", "item": ALL}, "checked"),
    State("ds-mig-state", "data"),
    State("ds-mig-selected-step", "data"),
    prevent_initial_call=True,
)
def handle_mig_manual_tick(checked_list: Any, state: Any, selected: Any) -> tuple[Any, ...]:
    """Tick một bước làm tay (task 65): fake chỉ đổi ds-mig-state; thật
    lưu vào CHECKLIST_JSON của phiên migration (ADMIN).

    Guard: lần vẽ lại detail (tick/poll) tạo lại checkbox cũng kích hoạt
    callback — bỏ qua khi giá trị mới bằng đúng trạng thái đã lưu.
    """
    checklist = state or _empty_mig_state()
    triggered = dash.callback_context.triggered
    triggered_id = dash.callback_context.triggered_id
    if not triggered or not isinstance(triggered_id, dict) or triggered_id.get("type") != "mig-manual-check":
        return dash.no_update, dash.no_update, dash.no_update
    item_id = str(triggered_id.get("item") or "")
    first = triggered[0]
    new_checked = bool(first.get("value")) if isinstance(first, dict) else False
    new_state = copy.deepcopy(checklist)
    changed = set_item_status(
        new_state, MANUAL_STEP_KEY, item_id, "done" if new_checked else "pending"
    )
    if not changed:
        return dash.no_update, dash.no_update, dash.no_update
    selected_idx = _mig_selected_index(new_state, selected)
    if str(new_state.get("mode")) == "real" and new_state.get("migration_id"):
        ctx = get_current_ctx()
        if ctx is None or not is_admin(ctx):
            return (
                checklist,
                _render_mig_stepper(checklist, selected_idx),
                _render_mig_detail(checklist, selected_idx),
            )
        try:
            save_checklist(get_recon_engine(), int(new_state["migration_id"]), new_state)
        except Exception:
            # Lưu lỗi thì vẽ lại từ state cũ (checkbox tự về trạng thái cũ).
            return (
                checklist,
                _render_mig_stepper(checklist, selected_idx),
                _render_mig_detail(checklist, selected_idx),
            )
    return (
        new_state,
        _render_mig_stepper(new_state, selected_idx),
        _render_mig_detail(new_state, selected_idx),
    )


@callback(
    Output("ds-mig-real-warning", "children", allow_duplicate=True),
    Input("ds-mig-real-switch", "checked"),
    prevent_initial_call=True,
)
def handle_mig_real_switch(checked: Any) -> Any:
    """Bật switch 'Migration thật' thì hiện cảnh báo rõ (task 63)."""
    if not checked:
        return html.Div()
    return alert_box(
        title="Migration thật",
        message="Hệ thống sẽ ghi dữ liệu thật sang Oracle đích và bật chế độ bảo trì — không ai chạy đối soát mới được trong lúc chuyển. Chỉ bật khi đã kiểm tra kỹ bằng chế độ giả lập.",
        tone="warn",
        icon="lucide:alert-triangle",
    )



@callback(
    Output("ds-mig-clean-modal", "opened"),
    Input("ds-mig-clean-open-btn", "n_clicks"),
    Input("ds-mig-clean-modal-cancel", "n_clicks"),
    State("ds-mig-clean-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_clean_modal(open_clicks: Any, cancel_clicks: Any, is_opened: bool) -> bool:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False
    trigger = ctx_dash.triggered[0]
    trigger_id = trigger["prop_id"].split(".")[0]
    trigger_val = trigger.get("value")
    return trigger_id == "ds-mig-clean-open-btn" and bool(trigger_val)


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
    if ctx is None or not is_admin(ctx):
        return False, alert_box("Lỗi", "Chưa đăng nhập", tone="crit")

    # Lấy thông tin default schema của target ds
    engine = get_recon_engine()
    with engine.connect() as conn:
        ds_row = (
            conn.execute(select(recon_data_source).where(recon_data_source.c.ID == int(target_ds_id)))
            .mappings()
            .first()
        )

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
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False
    trigger = ctx_dash.triggered[0]
    trigger_id = trigger["prop_id"].split(".")[0]
    trigger_val = trigger.get("value")
    return trigger_id == "ds-mig-delete-sqlite-open-btn" and bool(trigger_val)


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
    if ctx is None or not is_admin(ctx):
        return False, alert_box("Lỗi", "Chưa đăng nhập", tone="crit")

    # Lấy tên file sqlite từ bản migration gần nhất
    engine = get_recon_engine()
    with engine.connect() as conn:
        mig_row = (
            conn.execute(
                select(recon_metadata_migration)
                .where(
                    recon_metadata_migration.c.STATUS == "DONE",
                    recon_metadata_migration.c.OLD_SQLITE_DELETED_AT.is_(None),
                )
                .order_by(desc(recon_metadata_migration.c.ID))
            )
            .mappings()
            .first()
        )

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
