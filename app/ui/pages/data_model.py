"""Page Mô hình dữ liệu — Data Model Explorer (task 31, DATA-MODEL-01).

Route /data-model, menu code data_model (nhóm QUẢN TRỊ). Layout Fluent
Compact, trang vừa viewport (Box calc(100vh - 88px), 3 panel cuộn trong).
Dữ liệu từ service app.services.data_model (manifest/history đã commit +
drift live); page chỉ đọc metadata, không đọc dữ liệu dòng.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.data_model import get_data_model
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.command_bar import command_bar
from app.ui.components.page_header import page_header

try:
    dash.register_page(__name__, path="/data-model", title="Mô hình dữ liệu – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "data_model"

DOMAIN_OPTIONS: list[dict[str, str]] = [
    {"label": "Tất cả phân hệ", "value": "all"},
    {"label": "Core", "value": "core"},
    {"label": "Đối soát", "value": "recon"},
    {"label": "Báo cáo", "value": "report"},
    {"label": "Quản trị", "value": "admin"},
    {"label": "Khác", "value": "other"},
]

MODE_OPTIONS: list[dict[str, str]] = [
    {"label": "Hiển thị quan hệ", "value": "relations"},
    {"label": "Chỉ tên table", "value": "compact"},
]

# Giờ hiển thị "Cập nhật" theo giờ Việt Nam (quy ước của app: p_from/p_to
# nhập theo giờ Việt Nam). Manifest lưu generated_at theo UTC.
_VN_TZ = timezone(timedelta(hours=7))

HEALTH_TEXT: dict[str, str] = {
    "SYNCED": "✓ Schema đồng bộ",
    "DRIFT": "⚠ Schema drift",
    "UNKNOWN": "? Không xác định",
    "ERROR": "✕ Lỗi metadata",
}

HEALTH_COLOR: dict[str, str] = {
    "SYNCED": "teal",
    "DRIFT": "yellow",
    "UNKNOWN": "gray",
    "ERROR": "red",
}


def format_last_sync(generated_at: str | None) -> str:
    """Định dạng generated_at (ISO, UTC) thành DD/MM/YYYY HH:mm:ss giờ VN."""
    if not generated_at:
        return "Cập nhật: —"
    try:
        dt = datetime.fromisoformat(generated_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(_VN_TZ)
        return f"Cập nhật: {local.strftime('%d/%m/%Y %H:%M:%S')}"
    except Exception:
        return "Cập nhật: —"


def health_badge(status: str) -> dmc.Badge:
    """Badge read-only trạng thái schema health (không phải button)."""
    label = HEALTH_TEXT.get(status, HEALTH_TEXT["UNKNOWN"])
    color = HEALTH_COLOR.get(status, "gray")
    icon = {
        "SYNCED": "lucide:check",
        "DRIFT": "lucide:alert-triangle",
        "UNKNOWN": "lucide:help-circle",
        "ERROR": "lucide:x-circle",
    }.get(status, "lucide:help-circle")
    return dmc.Badge(
        label,
        id="data-model-health-badge",
        color=color,
        variant="light",
        size="sm",
        leftSection=DashIconify(icon=icon, width=14),
        **{"aria-label": f"Trạng thái schema: {label}"},
    )


def render_command_bar(domain: str, mode: str, health_status: str, generated_at: str | None) -> Any:
    """Thanh command bar: search + domain + mode + health + last sync."""
    return command_bar(
        search_id="data-model-search",
        search_placeholder="Tìm table hoặc column…",
        filters=[
            dmc.Select(
                id="data-model-domain-filter",
                data=DOMAIN_OPTIONS,
                value=domain,
                size="xs",
                w=150,
                clearable=False,
                **{"aria-label": "Lọc theo phân hệ"},
            ),
            dmc.Select(
                id="data-model-mode-select",
                data=MODE_OPTIONS,
                value=mode,
                size="xs",
                w=160,
                clearable=False,
                **{"aria-label": "Chế độ hiển thị"},
            ),
            html.Div(
                id="data-model-health-container",
                children=health_badge(health_status),
                style={"display": "flex", "alignItems": "center"},
            ),
            dmc.Text(
                format_last_sync(generated_at),
                id="data-model-last-sync",
                size="xs",
                c="dimmed",
            ),
        ],
        actions=[
            html.Div(id="data-model-drift-action-container"),
        ],
        id="data-model-command-bar",
    )


def render_panel_skeleton() -> Any:
    """Skeleton lúc load đầu cho một panel."""
    return dmc.Stack(
        [dmc.Skeleton(height=28), dmc.Skeleton(height=28), dmc.Skeleton(height=28)],
        gap="xs",
        p="sm",
    )


def layout(**kwargs: Any) -> Any:
    """Giao diện chính màn hình Mô hình dữ liệu. Query ?table=&domain=&mode=."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="data-model-gate-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang mô hình dữ liệu.", tone="crit"),
            ]
        )

    table_param = str(kwargs.get("table") or "").strip() or None
    domain_param = str(kwargs.get("domain") or "all").strip() or "all"
    if domain_param not in {o["value"] for o in DOMAIN_OPTIONS}:
        domain_param = "all"
    mode_param = str(kwargs.get("mode") or "relations").strip() or "relations"
    if mode_param not in {o["value"] for o in MODE_OPTIONS}:
        mode_param = "relations"

    initial_selection: dict[str, Any] = (
        {"kind": "table", "table": table_param}
        if table_param
        else {
            "kind": None,
            "table": None,
        }
    )
    initial_ui: dict[str, Any] = {
        "domain": domain_param,
        "mode": mode_param,
        "expanded": {},
        "center_table": None,
        "history_table": None,
    }

    manifest_data: dict[str, Any] | None = None
    load_error = ""
    if ctx is not None:
        res = get_data_model(ctx)
        if res.ok and res.data:
            manifest_data = res.data
        else:
            load_error = res.message or "Không thể đọc metadata database."

    health_status = "UNKNOWN"
    generated_at: str | None = None
    counts = {"tables": 0, "columns": 0, "relationships": 0}
    if manifest_data is not None:
        health_status = str(manifest_data.get("drift", {}).get("status") or "UNKNOWN")
        generated_at = manifest_data.get("manifest", {}).get("generated_at")
        counts = manifest_data.get("counts", counts)

    return dmc.Box(
        [
            dcc.Store(id="data-model-manifest-store", data=manifest_data),
            dcc.Store(id="data-model-selection-store", data=initial_selection),
            dcc.Store(id="data-model-ui-store", data=initial_ui),
            dcc.Store(id="data-model-dblclick-store", data=None),
            dcc.Store(id="data-model-zoom-store", data=1.0),
            dcc.Store(id="data-model-sync-trigger", data=0),
            dcc.Store(id="data-model-sync-result-store", data=None),
            dcc.Store(id="data-model-history-filter-store", data={"query": "", "change_type": "all", "table": None}),
            dcc.Store(id="data-model-drift-filter-store", data="all"),
            dcc.Location(id="data-model-location", refresh=False),
            html.Div(id="data-model-notification-area"),
            html.Div(id="data-model-center-sink"),
            page_header(
                title="Mô hình dữ liệu",
                subtitle="ER Diagram được sinh tự động từ metadata database, migrations và model của ứng dụng.",
                actions=[
                    button_subtle(
                        "Lịch sử thay đổi",
                        id="data-model-history-btn",
                        icon="lucide:history",
                        size="xs",
                    ),
                    button_primary(
                        "Đồng bộ schema",
                        id="data-model-sync-btn",
                        icon="lucide:refresh-cw",
                        size="xs",
                    ),
                ],
            ),
            render_command_bar(domain_param, mode_param, health_status, generated_at),
            html.Div(
                id="data-model-error-container",
                children=(
                    alert_box(
                        load_error,
                        tone="crit",
                        action=button_subtle("Thử lại", id="data-model-retry-btn", size="sm"),
                    )
                    if load_error
                    else None
                ),
            ),
            dcc.Loading(
                id="data-model-loading",
                type="circle",
                children=dmc.Group(
                    [
                        dmc.Paper(
                            [
                                dmc.Group(
                                    [
                                        dmc.Text("Schema Explorer", fw=600, size="sm"),
                                        dmc.Text(
                                            f"{counts['tables']} tables",
                                            id="data-model-explorer-count",
                                            size="xs",
                                            c="dimmed",
                                        ),
                                    ],
                                    justify="space-between",
                                    px="sm",
                                    pt="xs",
                                ),
                                html.Div(
                                    id="data-model-explorer-container",
                                    children=render_panel_skeleton(),
                                    style={"flex": 1, "minHeight": 0, "overflow": "auto"},
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            style={
                                "flex": 2,
                                "minWidth": 0,
                                "display": "flex",
                                "flexDirection": "column",
                                "overflow": "hidden",
                            },
                        ),
                        dmc.Paper(
                            [
                                dmc.Group(
                                    [
                                        dmc.Text("ER Diagram", fw=600, size="sm"),
                                        dmc.Group(
                                            [
                                                dmc.ActionIcon(
                                                    DashIconify(icon="lucide:zoom-in", width=14),
                                                    id="data-model-zoom-in-btn",
                                                    variant="subtle",
                                                    color="gray",
                                                    size="sm",
                                                    **{"aria-label": "Phóng to ER Diagram"},
                                                ),
                                                dmc.ActionIcon(
                                                    DashIconify(icon="lucide:zoom-out", width=14),
                                                    id="data-model-zoom-out-btn",
                                                    variant="subtle",
                                                    color="gray",
                                                    size="sm",
                                                    **{"aria-label": "Thu nhỏ ER Diagram"},
                                                ),
                                                dmc.ActionIcon(
                                                    DashIconify(icon="lucide:maximize", width=14),
                                                    id="data-model-fit-btn",
                                                    variant="subtle",
                                                    color="gray",
                                                    size="sm",
                                                    **{"aria-label": "Vừa màn hình"},
                                                ),
                                            ],
                                            gap=0,
                                        ),
                                    ],
                                    justify="space-between",
                                    px="sm",
                                    pt="xs",
                                ),
                                html.Div(
                                    id="data-model-canvas-container",
                                    children=render_panel_skeleton(),
                                    style={"flex": 1, "minHeight": 0, "overflow": "auto"},
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            style={
                                "flex": 5,
                                "minWidth": 0,
                                "display": "flex",
                                "flexDirection": "column",
                                "overflow": "hidden",
                            },
                        ),
                        dmc.Paper(
                            [
                                dmc.Text("Chi tiết", fw=600, size="sm", px="sm", pt="xs"),
                                html.Div(
                                    id="data-model-detail-container",
                                    children=render_panel_skeleton(),
                                    style={"flex": 1, "minHeight": 0, "overflow": "auto"},
                                ),
                            ],
                            withBorder=True,
                            radius="sm",
                            style={
                                "flex": 3,
                                "minWidth": 0,
                                "display": "flex",
                                "flexDirection": "column",
                                "overflow": "hidden",
                            },
                        ),
                    ],
                    gap="xs",
                    align="stretch",
                    style={"flex": 1, "minHeight": 0, "flexWrap": "nowrap"},
                    className="dm-workspace",
                ),
                parent_style={
                    "flex": 1,
                    "minHeight": 0,
                    "display": "flex",
                    "flexDirection": "column",
                    "overflow": "hidden",
                },
            ),
            dmc.Group(
                [
                    dmc.Text(
                        f"{counts['tables']} tables · {counts['columns']} columns · {counts['relationships']} relationships",
                        id="data-model-status-counts",
                        size="xs",
                        c="dimmed",
                    ),
                    dmc.Text(
                        "SQLAlchemy Core models + Alembic migrations + SQLite metadata",
                        size="xs",
                        c="dimmed",
                    ),
                ],
                justify="space-between",
                px="xs",
                pt=4,
                id="data-model-status-bar",
                style={"flexShrink": 0},
            ),
        ],
        style={
            "height": "calc(100vh - 88px)",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "12px 16px",
            "gap": "8px",
        },
        className="dm-page",
    )
