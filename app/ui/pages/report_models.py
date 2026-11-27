"""Trang Model Center (/report-models) — Bước 1 task 107 (REPORT-STUDIO-01B)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.schemas.errors import ServiceError
from app.schemas.semantic_model import ModelCloneDTO, ModelCreateDTO
from app.services.data_source import options_data_sources
from app.services.perm import page_gate
from app.services.semantic_model import (
    archive_model,
    clone_model,
    create_model,
    get_model,
    impact_analysis,
    list_models,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.command_bar import command_bar
from app.ui.components.data_grid import data_grid
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.error_state import error_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import toast_error, toast_success
from app.ui.components.page_header import page_header
from app.ui.components.skeleton_grid import skeleton_grid
from app.ui.components.status_chip import status_chip

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/report-models",
        title="Mô hình báo cáo – ReconHub",
    )
except Exception:
    pass

MENU_CODE = "report_model"

STATUS_LABELS: dict[str, str] = {
    "DRAFT": "Bản nháp",
    "VALIDATED": "Đã kiểm tra",
    "ACTIVE": "Đang phát hành",
    "ARCHIVED": "Đã lưu trữ",
}

STATUS_OPTIONS: list[dict[str, str]] = [
    {"label": "Tất cả trạng thái", "value": "ALL"},
    {"label": "Bản nháp", "value": "DRAFT"},
    {"label": "Đã kiểm tra", "value": "VALIDATED"},
    {"label": "Đang phát hành", "value": "ACTIVE"},
    {"label": "Đã lưu trữ", "value": "ARCHIVED"},
]


def _fmt_dt(val: Any) -> str:
    if not val:
        return "—"
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y %H:%M")
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", ""))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(val)


def filter_models(
    models: list[dict[str, Any]] | None,
    query: str | None = None,
    data_source_id: str | int | None = None,
    status: str | None = "ALL",
) -> list[dict[str, Any]]:
    """Lọc danh sách Semantic Model theo từ khóa, Data Source và trạng thái."""
    items = list(models or [])
    q = (query or "").strip().lower()
    ds_str = str(data_source_id).strip() if data_source_id not in (None, "", "ALL") else ""
    st = str(status or "ALL").upper()

    out: list[dict[str, Any]] = []
    for m in items:
        if ds_str and str(m.get("data_source_id")) != ds_str:
            continue
        m_status = str(m.get("status") or "DRAFT").upper()
        if st != "ALL" and m_status != st:
            continue
        if q:
            ds_name = str((m.get("data_source") or {}).get("name") or "")
            hay = " ".join(
                str(x or "")
                for x in (m.get("code"), m.get("name"), m.get("description"), ds_name)
            ).lower()
            if q not in hay:
                continue
        out.append(m)
    return out


def models_to_grid_rows(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chuẩn hóa danh sách model sang dữ liệu dòng cho AgGrid."""
    rows: list[dict[str, Any]] = []
    for m in models:
        ds = m.get("data_source") or {}
        ds_name = str(ds.get("name") or f"DS #{m.get('data_source_id')}")
        ds_env = str(ds.get("env") or "")
        ds_label = f"{ds_name} ({ds_env})" if ds_env else ds_name
        fact_c = int(m.get("fact_count") or 0)
        dim_c = int(m.get("dimension_count") or 0)
        rel_c = int(m.get("relationship_count") or 0)
        act_no = m.get("active_version_no")
        draft_ver = m.get("draft_version") or {}
        draft_no = draft_ver.get("version_no")
        status = str(m.get("status") or "DRAFT").upper()

        ver_parts = []
        if act_no:
            ver_parts.append(f"v{act_no} (Active)")
        if draft_no:
            ver_parts.append(f"v{draft_no} (Draft)")
        active_label = " · ".join(ver_parts) if ver_parts else "—"

        rows.append(
            {
                "id": int(m["id"]),
                "code": str(m.get("code") or ""),
                "name": str(m.get("name") or ""),
                "description": str(m.get("description") or ""),
                "data_source_id": int(m["data_source_id"]),
                "ds_label": ds_label,
                "counts_label": f"{fact_c}F / {dim_c}D / {rel_c}R",
                "active_version_label": active_label,
                "status": status,
                "status_label": STATUS_LABELS.get(status, status),
                "updated_at": str(m.get("updated_at") or ""),
                "updated_label": _fmt_dt(m.get("updated_at")),
                "is_archived": bool(m.get("is_archived")),
            }
        )
    return rows


def _grid_column_defs() -> list[dict[str, Any]]:
    return [
        {
            "field": "code",
            "headerName": "Mã mô hình",
            "width": 165,
            "pinned": "left",
            "cellClass": "rh-code",
        },
        {
            "field": "name",
            "headerName": "Tên mô hình",
            "minWidth": 210,
            "flex": 1,
        },
        {
            "field": "counts_label",
            "headerName": "Fact / Dim / Rel",
            "width": 140,
            "cellClass": "rh-code",
        },
        {
            "field": "active_version_label",
            "headerName": "Phiên bản",
            "width": 150,
        },
        {
            "field": "status_label",
            "headerName": "Trạng thái",
            "width": 140,
            "cellRenderer": "rmModelStatusCell",
        },
        {
            "field": "updated_label",
            "headerName": "Cập nhật",
            "width": 130,
        },
        {
            "colId": "actions",
            "headerName": "Thao tác",
            "width": 360,
            "minWidth": 350,
            "sortable": False,
            "filter": False,
            "resizable": False,
            "cellRenderer": "rmModelActionsCell",
        },
    ]


def render_models_body(
    rows: list[dict[str, Any]],
    *,
    loading: bool = False,
    has_filter: bool = False,
    error_msg: str | None = None,
) -> Any:
    """Dựng vùng hiển thị chính theo đúng 4 trạng thái Fluent Compact."""
    if loading:
        return skeleton_grid(rows=8, cols=7, id="rm-center-skeleton")

    if error_msg and not rows:
        return error_state(
            id="rm-center-error",
            title="Không thể tải danh sách mô hình",
            message=error_msg,
            action=button_primary(
                "Thử lại",
                id={"type": "rm-center-retry-btn", "k": "full"},
                icon="lucide:refresh-cw",
                size="xs",
            ),
        )

    parts: list[Any] = []
    if error_msg:
        parts.append(
            error_state(
                id="rm-center-error-banner",
                title="Không thể làm mới danh sách mô hình",
                message=f"{error_msg} Đang hiển thị dữ liệu đã tải trước đó.",
                action=button_primary(
                    "Thử lại",
                    id={"type": "rm-center-retry-btn", "k": "banner"},
                    icon="lucide:refresh-cw",
                    size="xs",
                ),
                banner_only=True,
            )
        )

    if not rows:
        if has_filter:
            return empty_state(
                title="Không có mô hình khớp bộ lọc",
                description="Hãy đổi từ khóa tìm kiếm hoặc xóa bộ lọc để xem toàn bộ mô hình.",
                action=button_subtle(
                    "Xóa bộ lọc",
                    id={"type": "rm-center-clear-filter-btn", "k": "empty"},
                    icon="lucide:x",
                ),
            )
        return empty_state(
            title="Chưa có mô hình báo cáo",
            description="Tạo mô hình ngữ nghĩa đầu tiên từ Data Source Oracle hoặc SQLite.",
            action=button_primary(
                "Tạo mô hình",
                id={"type": "rm-center-empty-create-btn", "k": "empty"},
                icon="lucide:plus",
            ),
        )

    grid_node = data_grid(
        id={"type": "rm-center-grid", "k": "main"},
        columnDefs=_grid_column_defs(),
        rowData=rows,
        rowModelType="clientSide",
        getRowId="params.data.id.toString()",
        dashGridOptions={
            "suppressRowClickSelection": True,
        },
    )
    parts.append(grid_node)
    if len(parts) == 1:
        return grid_node
    return dmc.Stack(parts, gap="xs", style={"flex": 1, "minHeight": 0})


def _load_ds_options(ctx: Ctx) -> list[dict[str, str]]:
    res = options_data_sources(ctx, purpose="SOURCE")
    if not res.ok or not res.data:
        return []
    return [
        {"label": f"{ds.name} ({ds.env} · {ds.db_type})", "value": str(ds.id)}
        for ds in res.data
    ]


def submit_create_model(
    ctx: Ctx | None,
    *,
    code: str | None,
    name: str | None,
    ds_id: str | int | None,
    description: str | None = None,
) -> tuple[int | None, str | None, list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Validate DTO, gọi create_model và nạp lại danh sách."""
    if ctx is None:
        return None, "Phiên đăng nhập đã hết hạn.", None, None
    try:
        parsed_ds = int(str(ds_id)) if ds_id not in (None, "") else 0
    except ValueError:
        parsed_ds = 0
    if parsed_ds <= 0:
        return None, "Vui lòng chọn Data Source nguồn.", None, None

    try:
        dto = ModelCreateDTO(
            code=str(code or "").strip().upper(),
            name=str(name or "").strip(),
            description=str(description or "").strip() or None,
            data_source_id=parsed_ds,
        )
    except Exception:
        return (
            None,
            "Mã mô hình chỉ gồm chữ hoa, số, dấu gạch dưới (bắt đầu bằng chữ cái) và tên không được rỗng.",
            None,
            None,
        )

    res = create_model(ctx, dto.model_dump())
    if not res.ok or not res.data:
        return None, res.message or "Không thể tạo mô hình.", None, None

    list_res = list_models(ctx, include_archived=True)
    rows = models_to_grid_rows(list_res.data or []) if list_res.ok else None
    new_id = int(res.data["id"])
    return new_id, None, rows, toast_success(f"Đã tạo mô hình {dto.code}.")


def submit_clone_model(
    ctx: Ctx | None,
    *,
    source_model_id: int | None,
    code: str | None,
    name: str | None,
    description: str | None = None,
) -> tuple[str | None, list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Nhân bản mô hình thành một Model & bản Draft mới."""
    if ctx is None:
        return "Phiên đăng nhập đã hết hạn.", None, None
    if not source_model_id:
        return "Thiếu thông tin mô hình gốc để nhân bản.", None, None
    try:
        dto = ModelCloneDTO(
            code=str(code or "").strip().upper(),
            name=str(name or "").strip(),
            description=str(description or "").strip() or None,
        )
    except Exception:
        return (
            "Mã mô hình mới chỉ gồm chữ hoa, số, gạch dưới và tên không được để trống.",
            None,
            None,
        )

    res = clone_model(ctx, int(source_model_id), dto.model_dump())
    if not res.ok or not res.data:
        return res.message or "Không thể nhân bản mô hình.", None, None

    list_res = list_models(ctx, include_archived=True)
    rows = models_to_grid_rows(list_res.data or []) if list_res.ok else None
    return None, rows, toast_success(f"Đã nhân bản sang mô hình {dto.code}.")


def build_impact_drawer_content(ctx: Ctx | None, model_id: int | None) -> Any:
    """Dựng nội dung Drawer Impact Analysis (chỉ đọc)."""
    if ctx is None:
        return alert_box(title="Chưa đăng nhập", message="Vui lòng đăng nhập lại.", tone="crit")
    if not model_id:
        return empty_state(
            title="Chưa chọn mô hình",
            description="Chọn nút Ảnh hưởng trên một dòng mô hình để kiểm tra tác động.",
        )

    model_res = get_model(ctx, int(model_id))
    if not model_res.ok or not model_res.data:
        return error_state(
            title="Không đọc được thông tin mô hình",
            message=model_res.message or "Vui lòng thử lại.",
        )
    model = model_res.data
    imp_res = impact_analysis(ctx, int(model_id))
    if not imp_res.ok or not imp_res.data:
        return error_state(
            title="Không phân tích được ảnh hưởng",
            message=imp_res.message or "Vui lòng thử lại.",
        )
    imp = imp_res.data
    breaking = list(imp.get("breaking_changes") or [])
    warnings: list[dict[str, Any]] = []
    reports = list(imp.get("reports") or [])
    visuals = list(imp.get("visuals") or [])
    if visuals and not reports:
        reports = [
            {"report_code": v.get("report_code"), "report_name": v.get("report_name"), "visual_count": 1}
            for v in visuals
        ]

    blocks: list[Any] = [
        dmc.Paper(
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            dmc.Text(str(model.get("name") or ""), fw=600, size="sm"),
                            dmc.Text(str(model.get("code") or ""), size="xs", c="dimmed", className="rh-code"),
                        ],
                        gap=2,
                    ),
                    status_chip(str(model.get("status") or "DRAFT"), size="xs"),
                ],
                justify="space-between",
                align="center",
            ),
            withBorder=True,
            p="xs",
            radius="sm",
            bg="var(--surface-2)",
        )
    ]

    if breaking:
        blocks.append(
            alert_box(
                title=f"Phát hiện {len(breaking)} thay đổi phá vỡ cấu trúc (Breaking changes)",
                message=dmc.Stack(
                    [dmc.Text(f"• {b.get('message') or b}", size="xs") for b in breaking[:10]],
                    gap=4,
                ),
                tone="warn",
            )
        )
    elif warnings:
        blocks.append(
            alert_box(
                title=f"Có {len(warnings)} lưu ý giữa bản nháp và bản đang phát hành",
                message=dmc.Stack(
                    [dmc.Text(f"• {w.get('message') or w}", size="xs") for w in warnings[:8]],
                    gap=4,
                ),
                tone="info",
            )
        )
    else:
        blocks.append(
            alert_box(
                title="Không có breaking change chưa phát hành",
                message="Cấu trúc bản hiện tại tương thích với phiên bản đang hoạt động.",
                tone="ok",
            )
        )

    blocks.append(dmc.Text("Báo cáo bị ảnh hưởng", fw=600, size="sm"))
    if reports:
        blocks.append(
            dmc.Stack(
                [
                    dmc.Paper(
                        dmc.Group(
                            [
                                dmc.Text(str(r.get("report_name") or r.get("report_code") or r), size="xs", fw=600),
                                dmc.Badge(str(r.get("visual_count") or 0) + " visual", size="xs", variant="light"),
                            ],
                            justify="space-between",
                        ),
                        withBorder=True,
                        p="xs",
                        radius="sm",
                    )
                    for r in reports
                ],
                gap="xs",
            )
        )
    else:
        blocks.append(
            empty_state(
                title="Chưa có báo cáo phụ thuộc",
                description="Chưa có báo cáo hoặc visual nào đang tham chiếu tới mô hình này.",
                icon="lucide:check-circle-2",
            )
        )
    return dmc.Stack(blocks, gap="sm")


def confirm_archive_model(
    ctx: Ctx | None,
    model_id: int | None,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None, str | None]:
    """Lưu trữ mô hình (không xóa vật lý dữ liệu)."""
    if ctx is None:
        return None, None, "Phiên đăng nhập đã hết hạn."
    if not model_id:
        return None, None, "Thiếu thông tin mô hình cần lưu trữ."
    res = archive_model(ctx, int(model_id))
    if not res.ok:
        return None, None, res.message or "Không thể lưu trữ mô hình."
    list_res = list_models(ctx, include_archived=True)
    rows = models_to_grid_rows(list_res.data or []) if list_res.ok else None
    code = (res.data or {}).get("code") or f"#{model_id}"
    return rows, toast_success(f"Đã chuyển mô hình {code} sang trạng thái Lưu trữ."), None


def layout() -> Any:
    """Layout chính của Model Center (/report-models)."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate is not None:
        return gate
    assert ctx is not None

    ds_options = _load_ds_options(ctx)

    initial_models: list[dict[str, Any]] = []
    initial_err: str | None = None
    try:
        res = list_models(ctx, include_archived=True)
        if res.ok:
            initial_models = list(res.data or [])
        else:
            initial_err = res.message or "Không tải được danh sách mô hình."
    except ServiceError as exc:
        initial_err = exc.message

    initial_rows = models_to_grid_rows(initial_models)

    create_modal = dmc.Modal(
        id="rm-center-create-modal",
        title=dmc.Text("Tạo mô hình báo cáo mới", fw=700, size="md"),
        opened=False,
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="rm-center-create-alert"),
                dmc.TextInput(
                    id="rm-center-create-code",
                    label="Mã mô hình",
                    description="Chữ hoa, số và dấu gạch dưới (bất biến sau khi tạo).",
                    placeholder="VD: DTP_SALES_MODEL",
                    withAsterisk=True,
                    size="xs",
                    className="rh-code",
                ),
                dmc.TextInput(
                    id="rm-center-create-name",
                    label="Tên mô hình",
                    placeholder="VD: Mô hình doanh thu tác nghiệp",
                    withAsterisk=True,
                    size="xs",
                ),
                html.Div(
                    dmc.Select(
                        id="rm-center-create-ds",
                        label="Data Source nguồn",
                        data=ds_options,
                        value=ds_options[0]["value"] if ds_options else None,
                        searchable=True,
                        withAsterisk=True,
                        size="xs",
                    ),
                    style={"display": "none"} if len(ds_options) <= 1 else None,
                ),
                dmc.Textarea(
                    id="rm-center-create-desc",
                    label="Mô tả",
                    placeholder="Mục đích sử dụng và phạm vi dữ liệu...",
                    minRows=2,
                    size="xs",
                ),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="rm-center-create-cancel", size="xs"),
                        button_primary("Tạo & mở Studio", id="rm-center-create-submit", icon="lucide:arrow-right", size="xs"),
                    ],
                    justify="flex-end",
                    gap="xs",
                    mt="xs",
                ),
            ],
            gap="xs",
        ),
    )

    clone_modal = dmc.Modal(
        id="rm-center-clone-modal",
        title=dmc.Text("Nhân bản mô hình (Clone)", fw=700, size="md"),
        opened=False,
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="rm-center-clone-alert"),
                dmc.Text(id="rm-center-clone-src-label", size="xs", c="dimmed"),
                dmc.TextInput(
                    id="rm-center-clone-code",
                    label="Mã mô hình mới",
                    withAsterisk=True,
                    size="xs",
                    className="rh-code",
                ),
                dmc.TextInput(
                    id="rm-center-clone-name",
                    label="Tên mô hình mới",
                    withAsterisk=True,
                    size="xs",
                ),
                dmc.Textarea(
                    id="rm-center-clone-desc",
                    label="Mô tả",
                    minRows=2,
                    size="xs",
                ),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="rm-center-clone-cancel", size="xs"),
                        button_primary("Nhân bản", id="rm-center-clone-submit", icon="lucide:copy", size="xs"),
                    ],
                    justify="flex-end",
                    gap="xs",
                    mt="xs",
                ),
            ],
            gap="xs",
        ),
    )

    impact_drawer = drawer_right(
        id="rm-center-impact-drawer",
        title="Phân tích ảnh hưởng (Impact Analysis)",
        children=html.Div(id="rm-center-impact-content"),
        size=520,
        opened=False,
    )

    archive_modal = modal_confirm(
        id="rm-center-archive-modal",
        title="Lưu trữ mô hình báo cáo",
        description=dmc.Stack(
            [
                dmc.Text(id="rm-center-archive-desc", size="sm"),
                dmc.Text(
                    "Giữ lại: Toàn bộ lịch sử phiên bản cũ và các báo cáo đang gắn phiên bản Active trước đó vẫn hoạt động bình thường.",
                    size="xs",
                    c="dimmed",
                ),
            ],
            gap="xs",
        ),
        confirm_label="Lưu trữ mô hình",
        danger=True,
        opened=False,
    )

    return dmc.Box(
        [
            dcc.Location(id="rm-center-redirect", refresh=True),
            dcc.Store(id="rm-center-models-store", data=initial_models),
            dcc.Store(id="rm-center-selected-id", data=None),
            dmc.NotificationContainer(id="rm-center-notif", position="top-right", **{"aria-live": "polite"}),
            page_header(
                title="Mô hình báo cáo",
                subtitle="Thiết kế Semantic Model (Fact, Dimension, Relationship, Measure).",
                actions=[
                    button_primary(
                        "Tạo mô hình",
                        id="rm-center-create-btn",
                        icon="lucide:plus",
                        size="xs",
                        radius="xl",
                        **{"aria-label": "Tạo mô hình báo cáo mới"},  # type: ignore[arg-type]
                    )
                ],
                mb=0,
            ),
            command_bar(
                search_id="rm-center-search",
                search_placeholder="Tìm mã hoặc tên mô hình...",
                search_debounce=250,
                filters=[
                    dmc.Select(
                        id="rm-center-status-filter",
                        data=STATUS_OPTIONS,
                        value="ALL",
                        size="xs",
                        w=175,
                        **{"aria-label": "Lọc theo trạng thái"},
                    ),
                ],
                actions=[
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:refresh-cw", width=15),
                        id="rm-center-refresh-btn",
                        variant="subtle",
                        color="gray",
                        size="sm",
                        radius="xl",
                        **{"aria-label": "Làm mới danh sách mô hình"},
                    )
                ],
                mb=0,
            ),
            html.Div(
                render_models_body(
                    initial_rows,
                    loading=False,
                    has_filter=False,
                    error_msg=initial_err,
                ),
                id="rm-center-body",
                className="rm-center-body",
                **{"aria-live": "polite"},  # type: ignore[arg-type]
            ),
            create_modal,
            clone_modal,
            impact_drawer,
            archive_modal,
        ],
        id="rm-center-page",
        className="rm-center-page",
    )


@callback(
    Output("rm-center-models-store", "data"),
    Output("rm-center-body", "children"),
    Output("rm-center-search", "value"),
    Output("rm-center-status-filter", "value"),
    Input("rm-center-search", "value"),
    Input("rm-center-status-filter", "value"),
    Input("rm-center-refresh-btn", "n_clicks"),
    Input({"type": "rm-center-retry-btn", "k": ALL}, "n_clicks"),
    Input({"type": "rm-center-clear-filter-btn", "k": ALL}, "n_clicks"),
    State("rm-center-models-store", "data"),
    prevent_initial_call=True,
)
def handle_center_filter_or_refresh(
    query: str | None,
    status: str | None,
    refresh_clicks: int | None,
    retry_clicks: list[int | None] | None,
    clear_clicks: list[int | None] | None,
    cached_models: list[dict[str, Any]] | None,
) -> tuple[Any, Any, Any, Any]:
    """Lọc client-side hoặc nạp lại danh sách từ service khi bấm Làm mới/Thử lại."""
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate

    trig = dash.callback_context.triggered_id
    if trig is None:
        raise PreventUpdate
    is_clear = isinstance(trig, dict) and trig.get("type") == "rm-center-clear-filter-btn"
    if is_clear:
        if not any(clear_clicks or []):
            raise PreventUpdate
        filtered = filter_models(cached_models, query="", data_source_id="ALL", status="ALL")
        return (
            dash.no_update,
            render_models_body(models_to_grid_rows(filtered), has_filter=False),
            "",
            "ALL",
        )

    is_retry = isinstance(trig, dict) and trig.get("type") == "rm-center-retry-btn"
    if is_retry and not any(retry_clicks or []):
        raise PreventUpdate
    if trig == "rm-center-refresh-btn" and not refresh_clicks:
        raise PreventUpdate

    is_refresh_req = (trig == "rm-center-refresh-btn") or is_retry
    if not is_refresh_req and trig not in ("rm-center-search", "rm-center-status-filter"):
        raise PreventUpdate
    models = list(cached_models or [])
    err_msg: str | None = None
    if is_refresh_req:
        res = list_models(ctx, include_archived=True)
        if res.ok:
            models = list(res.data or [])
        else:
            err_msg = res.message or "Không tải được danh sách mô hình."

    has_filter = bool((query or "").strip() or (status not in (None, "", "ALL")))
    filtered = filter_models(models, query=query, data_source_id="ALL", status=status)
    return (
        models if is_refresh_req and err_msg is None else dash.no_update,
        render_models_body(models_to_grid_rows(filtered), has_filter=has_filter, error_msg=err_msg),
        dash.no_update,
        dash.no_update,
    )


@callback(
    Output("rm-center-create-modal", "opened"),
    Output("rm-center-create-alert", "children"),
    Output("rm-center-create-code", "value"),
    Output("rm-center-create-name", "value"),
    Output("rm-center-create-desc", "value"),
    Input("rm-center-create-btn", "n_clicks"),
    Input({"type": "rm-center-empty-create-btn", "k": ALL}, "n_clicks"),
    Input("rm-center-create-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def handle_create_modal_toggle(
    btn_clicks: int | None,
    empty_clicks: list[int | None] | None,
    cancel_clicks: int | None,
) -> tuple[bool, Any, Any, Any, Any]:
    trig = dash.callback_context.triggered_id
    if trig == "rm-center-create-cancel" and cancel_clicks:
        return False, None, dash.no_update, dash.no_update, dash.no_update
    if trig == "rm-center-create-btn" and btn_clicks:
        return True, None, "", "", ""
    if isinstance(trig, dict) and trig.get("type") == "rm-center-empty-create-btn" and any(empty_clicks or []):
        return True, None, "", "", ""
    raise PreventUpdate


@callback(
    Output("rm-center-create-modal", "opened", allow_duplicate=True),
    Output("rm-center-create-alert", "children", allow_duplicate=True),
    Output("rm-center-redirect", "href", allow_duplicate=True),
    Output("rm-center-notif", "sendNotifications", allow_duplicate=True),
    Input("rm-center-create-submit", "n_clicks"),
    State("rm-center-create-code", "value"),
    State("rm-center-create-name", "value"),
    State("rm-center-create-ds", "value"),
    State("rm-center-create-desc", "value"),
    prevent_initial_call=True,
)
def handle_create_submit(
    n_clicks: int | None,
    code: str | None,
    name: str | None,
    ds_id: str | None,
    desc: str | None,
) -> tuple[bool, Any, Any, Any]:
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    new_id, err, _rows, toast = submit_create_model(ctx, code=code, name=name, ds_id=ds_id, description=desc)
    if err or not new_id:
        return True, alert_box(message=err or "Không thể tạo mô hình.", tone="crit"), dash.no_update, dash.no_update
    return False, None, f"/report-models/{new_id}", [toast] if toast else dash.no_update


@callback(
    Output("rm-center-redirect", "href", allow_duplicate=True),
    Output("rm-center-selected-id", "data"),
    Output("rm-center-clone-modal", "opened", allow_duplicate=True),
    Output("rm-center-clone-alert", "children", allow_duplicate=True),
    Output("rm-center-clone-src-label", "children"),
    Output("rm-center-clone-code", "value"),
    Output("rm-center-clone-name", "value"),
    Output("rm-center-clone-desc", "value"),
    Output("rm-center-impact-drawer", "opened", allow_duplicate=True),
    Output("rm-center-impact-content", "children"),
    Output("rm-center-archive-modal", "opened", allow_duplicate=True),
    Output("rm-center-archive-desc", "children"),
    Input({"type": "rm-center-grid", "k": ALL}, "cellRendererData"),
    State("rm-center-models-store", "data"),
    prevent_initial_call=True,
)
def handle_grid_action(
    cell_data_list: list[dict[str, Any] | None] | None,
    models: list[dict[str, Any]] | None,
) -> tuple[Any, ...]:
    cell_data = next((c for c in (cell_data_list or []) if isinstance(c, dict)), None)
    if not isinstance(cell_data, dict):
        raise PreventUpdate
    payload = cell_data.get("value")
    if not isinstance(payload, dict):
        raise PreventUpdate
    action = str(payload.get("action") or "")
    model_id = payload.get("id")
    if not model_id:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate

    target = next((m for m in (models or []) if int(m["id"]) == int(model_id)), None) or {}
    code = str(target.get("code") or f"#{model_id}")
    name = str(target.get("name") or "")

    no = dash.no_update
    if action == "open":
        return f"/report-models/{int(model_id)}", int(model_id), no, no, no, no, no, no, no, no, no, no
    if action == "clone":
        return (
            no,
            int(model_id),
            True,
            None,
            f"Nhân bản từ mô hình gốc: {code} — {name}",
            f"{code}_COPY",
            f"{name} (Bản sao)",
            str(target.get("description") or ""),
            no,
            no,
            no,
            no,
        )
    if action == "impact":
        content = build_impact_drawer_content(ctx, int(model_id))
        return no, int(model_id), no, no, no, no, no, no, True, content, no, no
    if action == "archive":
        imp_res = impact_analysis(ctx, int(model_id))
        imp_count = len((imp_res.data or {}).get("reports") or []) if imp_res.ok else 0
        msg = (
            f"Sẽ chuyển mô hình {code} ({name}) sang trạng thái Lưu trữ "
            f"(hiện có {imp_count} báo cáo tham chiếu; không chọn được cho báo cáo mới)."
        )
        return no, int(model_id), no, no, no, no, no, no, no, no, True, msg
    raise PreventUpdate


@callback(
    Output("rm-center-clone-modal", "opened", allow_duplicate=True),
    Output("rm-center-clone-alert", "children", allow_duplicate=True),
    Output("rm-center-models-store", "data", allow_duplicate=True),
    Output("rm-center-body", "children", allow_duplicate=True),
    Output("rm-center-notif", "sendNotifications", allow_duplicate=True),
    Input("rm-center-clone-submit", "n_clicks"),
    Input("rm-center-clone-cancel", "n_clicks"),
    State("rm-center-selected-id", "data"),
    State("rm-center-clone-code", "value"),
    State("rm-center-clone-name", "value"),
    State("rm-center-clone-desc", "value"),
    State("rm-center-search", "value"),
    State("rm-center-ds-filter", "value"),
    State("rm-center-status-filter", "value"),
    prevent_initial_call=True,
)
def handle_clone_submit(
    sub_clicks: int | None,
    cancel_clicks: int | None,
    src_id: int | None,
    code: str | None,
    name: str | None,
    desc: str | None,
    query: str | None,
    ds_filter: str | None,
    st_filter: str | None,
) -> tuple[bool, Any, Any, Any, Any]:
    trig = dash.callback_context.triggered_id
    if trig == "rm-center-clone-cancel":
        return False, None, dash.no_update, dash.no_update, dash.no_update
    if not sub_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    err, _rows, toast = submit_clone_model(ctx, source_model_id=src_id, code=code, name=name, description=desc)
    if err or ctx is None:
        return True, alert_box(message=err or "Không thể nhân bản.", tone="crit"), dash.no_update, dash.no_update, dash.no_update
    models = list_models(ctx, include_archived=True).data or []
    has_filter = bool((query or "").strip() or (ds_filter not in (None, "", "ALL")) or (st_filter not in (None, "", "ALL")))
    filtered = filter_models(models, query=query, data_source_id=ds_filter, status=st_filter)
    return False, None, models, render_models_body(models_to_grid_rows(filtered), has_filter=has_filter), [toast] if toast else dash.no_update


@callback(
    Output("rm-center-archive-modal", "opened", allow_duplicate=True),
    Output("rm-center-models-store", "data", allow_duplicate=True),
    Output("rm-center-body", "children", allow_duplicate=True),
    Output("rm-center-notif", "sendNotifications", allow_duplicate=True),
    Input("rm-center-archive-modal-confirm", "n_clicks"),
    Input("rm-center-archive-modal-cancel", "n_clicks"),
    State("rm-center-selected-id", "data"),
    State("rm-center-search", "value"),
    State("rm-center-ds-filter", "value"),
    State("rm-center-status-filter", "value"),
    prevent_initial_call=True,
)
def handle_archive_confirm(
    conf_clicks: int | None,
    cancel_clicks: int | None,
    model_id: int | None,
    query: str | None,
    ds_filter: str | None,
    st_filter: str | None,
) -> tuple[bool, Any, Any, Any]:
    trig = dash.callback_context.triggered_id
    if trig == "rm-center-archive-modal-cancel":
        return False, dash.no_update, dash.no_update, dash.no_update
    if not conf_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    _rows, toast, err = confirm_archive_model(ctx, model_id)
    if err or ctx is None:
        return False, dash.no_update, dash.no_update, [toast_error(err or "Không thể lưu trữ mô hình.")]
    models = list_models(ctx, include_archived=True).data or []
    has_filter = bool((query or "").strip() or (ds_filter not in (None, "", "ALL")) or (st_filter not in (None, "", "ALL")))
    filtered = filter_models(models, query=query, data_source_id=ds_filter, status=st_filter)
    return False, models, render_models_body(models_to_grid_rows(filtered), has_filter=has_filter), [toast] if toast else dash.no_update
