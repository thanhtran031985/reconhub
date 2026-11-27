"""Trang Report Studio Center (/report-studio) — Bước 3 task 109.

Danh sách báo cáo Studio: tìm kiếm, lọc trạng thái/model, AgGrid + cột
thao tác (Thiết kế, Xem, Clone, Phát hành, Lưu trữ, Ảnh hưởng), modal
tạo báo cáo mới (chỉ liệt kê Semantic Model đang ACTIVE).
"""

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
from app.schemas.report_studio import StudioCloneDTO, StudioReportCreateDTO
from app.services.perm import page_gate
from app.services.report_studio import (
    archive_studio_report,
    clone_studio_report,
    create_studio_report,
    get_studio_draft,
    list_studio_reports,
    publish_studio_report,
)
from app.services.semantic_model import impact_analysis, list_models
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

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/report-studio",
        title="Report Studio – ReconHub",
    )
except Exception:
    pass

MENU_CODE = "report_studio"

STATUS_LABELS: dict[str, str] = {
    "DRAFT": "Bản nháp",
    "DRY_RUN_OK": "Đã kiểm tra",
    "ACTIVE": "Đang phát hành",
    "ARCHIVED": "Đã lưu trữ",
}

STATUS_OPTIONS: list[dict[str, str]] = [
    {"label": "Tất cả trạng thái", "value": "ALL"},
    {"label": "Bản nháp", "value": "DRAFT"},
    {"label": "Đã kiểm tra", "value": "DRY_RUN_OK"},
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


def filter_studio_reports(
    reports: list[dict[str, Any]] | None,
    query: str | None = None,
    status: str | None = "ALL",
    model_version_id: str | int | None = None,
) -> list[dict[str, Any]]:
    """Lọc danh sách báo cáo Studio theo từ khóa, trạng thái, model."""
    items = list(reports or [])
    q = (query or "").strip().lower()
    st = str(status or "ALL").upper()
    mv = str(model_version_id).strip() if model_version_id not in (None, "", "ALL") else ""
    out: list[dict[str, Any]] = []
    for r in items:
        if mv and str(r.get("model_version_id")) != mv:
            continue
        r_status = str(r.get("version_status") or "DRAFT").upper()
        if st != "ALL" and r_status != st:
            continue
        if q:
            hay = " ".join(
                str(x or "")
                for x in (
                    r.get("code"),
                    r.get("name"),
                    r.get("category_code"),
                    r.get("model_code"),
                    r.get("description"),
                )
            ).lower()
            if q not in hay:
                continue
        out.append(r)
    return out


def studio_reports_to_grid_rows(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chuẩn hóa danh sách báo cáo Studio sang dữ liệu dòng cho AgGrid."""
    rows: list[dict[str, Any]] = []
    for r in reports:
        status = str(r.get("version_status") or "DRAFT").upper()
        rows.append(
            {
                "id": int(r["id"]),
                "code": str(r.get("code") or ""),
                "name": str(r.get("name") or ""),
                "category_code": str(r.get("category_code") or ""),
                "model_code": str(r.get("model_code") or ""),
                "model_version_id": int(r["model_version_id"]),
                "version_no": int(r.get("version_no") or 0),
                "version_label": f"v{int(r.get('version_no') or 0)}",
                "visual_count": int(r.get("visual_count") or 0),
                "status": status,
                "status_label": STATUS_LABELS.get(status, status),
                "is_archived": not bool(r.get("is_active", True)),
                "can_publish": status == "DRY_RUN_OK",
            }
        )
    return rows


def _grid_column_defs() -> list[dict[str, Any]]:
    return [
        {
            "field": "code",
            "headerName": "Mã báo cáo",
            "width": 165,
            "pinned": "left",
            "cellClass": "rh-code",
        },
        {
            "field": "name",
            "headerName": "Tên báo cáo",
            "minWidth": 200,
            "flex": 1,
        },
        {
            "field": "model_code",
            "headerName": "Semantic Model",
            "width": 150,
            "cellClass": "rh-code",
        },
        {
            "field": "version_label",
            "headerName": "Phiên bản",
            "width": 90,
        },
        {
            "field": "visual_count",
            "headerName": "Visual",
            "width": 80,
        },
        {
            "field": "status_label",
            "headerName": "Trạng thái",
            "width": 140,
            "cellRenderer": "rsStudioStatusCell",
        },
        {
            "colId": "actions",
            "headerName": "Thao tác",
            "width": 430,
            "minWidth": 420,
            "sortable": False,
            "filter": False,
            "resizable": False,
            "cellRenderer": "rsStudioActionsCell",
        },
    ]


def render_studio_reports_body(
    rows: list[dict[str, Any]],
    *,
    loading: bool = False,
    has_filter: bool = False,
    error_msg: str | None = None,
) -> Any:
    """Dựng vùng hiển thị chính theo đúng 4 trạng thái Fluent Compact."""
    if loading:
        return skeleton_grid(rows=8, cols=7, id="rs-center-skeleton")

    if error_msg and not rows:
        return error_state(
            id="rs-center-error",
            title="Không thể tải danh sách báo cáo Studio",
            message=error_msg,
            action=button_primary(
                "Thử lại",
                id={"type": "rs-center-retry-btn", "k": "full"},
                icon="lucide:refresh-cw",
                size="xs",
            ),
        )

    parts: list[Any] = []
    if error_msg:
        parts.append(
            error_state(
                id="rs-center-error-banner",
                title="Không thể làm mới danh sách báo cáo",
                message=f"{error_msg} Đang hiển thị dữ liệu đã tải trước đó.",
                action=button_primary(
                    "Thử lại",
                    id={"type": "rs-center-retry-btn", "k": "banner"},
                    icon="lucide:refresh-cw",
                    size="xs",
                ),
                banner_only=True,
            )
        )

    if not rows:
        if has_filter:
            return empty_state(
                title="Không có báo cáo khớp bộ lọc",
                description="Hãy đổi từ khóa tìm kiếm hoặc xóa bộ lọc để xem toàn bộ báo cáo.",
                action=button_subtle(
                    "Xóa bộ lọc",
                    id={"type": "rs-center-clear-filter-btn", "k": "empty"},
                    icon="lucide:x",
                ),
            )
        return empty_state(
            title="Chưa có báo cáo Studio",
            description="Tạo báo cáo đầu tiên từ một Semantic Model đang phát hành.",
            action=button_primary(
                "Tạo báo cáo",
                id={"type": "rs-center-empty-create-btn", "k": "empty"},
                icon="lucide:plus",
            ),
        )

    grid_node = data_grid(
        id={"type": "rs-center-grid", "k": "main"},
        columnDefs=_grid_column_defs(),
        rowData=rows,
        rowModelType="clientSide",
        getRowId="params.data.id.toString()",
        dashGridOptions={"suppressRowClickSelection": True},
    )
    parts.append(grid_node)
    if len(parts) == 1:
        return grid_node
    return dmc.Stack(parts, gap="xs", style={"flex": 1, "minHeight": 0})


def studio_model_options(ctx: Ctx) -> list[dict[str, str]]:
    """Chỉ liệt kê Semantic Model đang có version ACTIVE (để tạo báo cáo)."""
    res = list_models(ctx)
    if not res.ok or not res.data:
        return []
    opts: list[dict[str, str]] = []
    for m in res.data:
        active_id = m.get("active_version_id")
        if not active_id or m.get("is_archived"):
            continue
        act_no = m.get("active_version_no")
        label = f"{m.get('code')} — {m.get('name')}"
        if act_no:
            label += f" (v{act_no})"
        opts.append({"label": label, "value": str(active_id)})
    return opts


def render_create_report_modal(ctx: Ctx) -> Any:
    """Modal tạo báo cáo Studio mới (chỉ chọn model ACTIVE)."""
    opts = studio_model_options(ctx)
    return dmc.Modal(
        id="rs-center-create-modal",
        title=dmc.Text("Tạo báo cáo Studio mới", fw=700, size="md"),
        opened=False,
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="rs-center-create-alert"),
                dmc.TextInput(
                    id="rs-center-create-code",
                    label="Mã báo cáo",
                    description="Chữ hoa, số và dấu gạch dưới (bất biến sau khi tạo).",
                    placeholder="VD: RPT_SALES_MONTHLY",
                    withAsterisk=True,
                    size="xs",
                    className="rh-code",
                ),
                dmc.TextInput(
                    id="rs-center-create-name",
                    label="Tên báo cáo",
                    placeholder="VD: Báo cáo doanh thu theo tháng",
                    withAsterisk=True,
                    size="xs",
                ),
                dmc.Select(
                    id="rs-center-create-model",
                    label="Semantic Model (đang phát hành)",
                    data=opts,
                    value=opts[0]["value"] if opts else None,
                    searchable=True,
                    withAsterisk=True,
                    size="xs",
                ),
                dmc.Textarea(
                    id="rs-center-create-desc",
                    label="Mô tả",
                    placeholder="Mục đích sử dụng của báo cáo...",
                    minRows=2,
                    size="xs",
                ),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="rs-center-create-cancel", size="xs"),
                        button_primary(
                            "Tạo & mở Studio",
                            id="rs-center-create-submit",
                            icon="lucide:arrow-right",
                            size="xs",
                        ),
                    ],
                    justify="flex-end",
                    gap="xs",
                    mt="xs",
                ),
            ],
            gap="xs",
        ),
    )


def submit_create_studio_report(
    ctx: Ctx | None,
    *,
    code: str | None,
    name: str | None,
    model_version_id: str | int | None,
    description: str | None = None,
) -> tuple[int | None, str | None, list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Validate DTO, gọi create_studio_report và nạp lại danh sách."""
    if ctx is None:
        return None, "Phiên đăng nhập đã hết hạn.", None, None
    try:
        mv_id = int(str(model_version_id)) if model_version_id not in (None, "") else 0
    except ValueError:
        mv_id = 0
    if mv_id <= 0:
        return None, "Vui lòng chọn Semantic Model đang phát hành.", None, None
    try:
        dto = StudioReportCreateDTO(
            code=str(code or "").strip().upper(),
            name=str(name or "").strip(),
            description=str(description or "").strip() or None,
            model_version_id=mv_id,
        )
    except Exception:
        return (
            None,
            "Mã báo cáo chỉ gồm chữ hoa, số, dấu gạch dưới (bắt đầu bằng chữ cái) và tên không được rỗng.",
            None,
            None,
        )
    res = create_studio_report(ctx, dto.model_dump())
    if not res.ok or not res.data:
        return None, res.message or "Không thể tạo báo cáo.", None, None
    list_res = list_studio_reports(ctx)
    rows = studio_reports_to_grid_rows(list_res.data or []) if list_res.ok else None
    new_id = int(res.data["report"]["id"])
    return new_id, None, rows, toast_success(f"Đã tạo báo cáo {dto.code}.")


def submit_clone_studio_report(
    ctx: Ctx | None,
    *,
    source_report_id: int | None,
    code: str | None,
    name: str | None,
) -> tuple[str | None, list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Nhân bản báo cáo Studio (bản nháp mới, không tự phát hành)."""
    if ctx is None:
        return "Phiên đăng nhập đã hết hạn.", None, None
    if not source_report_id:
        return "Thiếu thông tin báo cáo gốc để nhân bản.", None, None
    try:
        dto = StudioCloneDTO(
            code=str(code or "").strip().upper(),
            name=str(name or "").strip(),
        )
    except Exception:
        return (
            "Mã báo cáo mới chỉ gồm chữ hoa, số, gạch dưới và tên không được để trống.",
            None,
            None,
        )
    res = clone_studio_report(ctx, int(source_report_id), dto.model_dump())
    if not res.ok or not res.data:
        return res.message or "Không thể nhân bản báo cáo.", None, None
    list_res = list_studio_reports(ctx)
    rows = studio_reports_to_grid_rows(list_res.data or []) if list_res.ok else None
    return None, rows, toast_success(f"Đã nhân bản sang báo cáo {dto.code}.")


def confirm_archive_studio_report(
    ctx: Ctx | None,
    report_id: int | None,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None, str | None]:
    """Lưu trữ báo cáo Studio (không xóa vật lý dữ liệu)."""
    if ctx is None:
        return None, None, "Phiên đăng nhập đã hết hạn."
    if not report_id:
        return None, None, "Thiếu thông tin báo cáo cần lưu trữ."
    res = archive_studio_report(ctx, int(report_id))
    if not res.ok:
        return None, None, res.message or "Không thể lưu trữ báo cáo."
    list_res = list_studio_reports(ctx)
    rows = studio_reports_to_grid_rows(list_res.data or []) if list_res.ok else None
    code = (res.data or {}).get("code") or f"#{report_id}"
    return rows, toast_success(f"Đã chuyển báo cáo {code} sang trạng thái Lưu trữ."), None


def build_impact_drawer_content(ctx: Ctx | None, report_id: int | None) -> Any:
    """Drawer Ảnh hưởng: breaking changes của model + visual bị ảnh hưởng."""
    if ctx is None:
        return alert_box(title="Chưa đăng nhập", message="Vui lòng đăng nhập lại.", tone="crit")
    if not report_id:
        return empty_state(
            title="Chưa chọn báo cáo",
            description="Chọn nút Ảnh hưởng trên một dòng báo cáo để kiểm tra tác động.",
        )
    listed = list_studio_reports(ctx)
    target = next((r for r in (listed.data or []) if int(r["id"]) == int(report_id)), None)
    if target is None:
        return error_state(title="Không đọc được báo cáo", message="Báo cáo không còn trong danh sách.")
    detail_res = get_studio_draft(ctx, int(target["version_id"]))
    if not detail_res.ok or not detail_res.data:
        return error_state(
            title="Không đọc được bản nháp báo cáo",
            message=detail_res.message or "Vui lòng thử lại.",
        )
    model = (detail_res.data.get("model") or {}).get("model") or {}
    model_id = int(model.get("id") or 0)
    imp_res = impact_analysis(ctx, model_id)
    if not imp_res.ok or not imp_res.data:
        return error_state(
            title="Không phân tích được ảnh hưởng",
            message=imp_res.message or "Vui lòng thử lại.",
        )
    imp = imp_res.data
    breaking = list(imp.get("breaking_changes") or [])
    visuals = list(imp.get("visuals") or [])
    blocks: list[Any] = [
        dmc.Paper(
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            dmc.Text(str(target.get("name") or ""), fw=600, size="sm"),
                            dmc.Text(str(target.get("code") or ""), size="xs", c="dimmed", className="rh-code"),
                        ],
                        gap=2,
                    ),
                    dmc.Badge(
                        STATUS_LABELS.get(str(target.get("version_status") or ""), ""),
                        size="xs",
                        variant="light",
                    ),
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
    else:
        blocks.append(
            alert_box(
                title="Không có breaking change chưa phát hành",
                message="Cấu trúc model hiện tại tương thích với báo cáo này.",
                tone="ok",
            )
        )
    blocks.append(dmc.Text("Visual bị ảnh hưởng", fw=600, size="sm"))
    if visuals:
        blocks.append(
            dmc.Stack(
                [
                    dmc.Paper(
                        dmc.Group(
                            [
                                dmc.Text(str(v.get("visual_title") or v.get("code") or v), size="xs", fw=600),
                                dmc.Badge(str(v.get("report_code") or ""), size="xs", variant="light"),
                            ],
                            justify="space-between",
                        ),
                        withBorder=True,
                        p="xs",
                        radius="sm",
                    )
                    for v in visuals
                ],
                gap="xs",
            )
        )
    else:
        blocks.append(
            empty_state(
                title="Chưa có visual bị ảnh hưởng",
                description="Chưa có visual nào trong báo cáo dùng field/measure đã thay đổi.",
                icon="lucide:check-circle-2",
            )
        )
    return dmc.Stack(blocks, gap="sm")


def _load_model_filter_options(ctx: Ctx) -> list[dict[str, str]]:
    opts = studio_model_options(ctx)
    if not opts:
        return [{"label": "Tất cả model", "value": "ALL"}]
    return [{"label": "Tất cả model", "value": "ALL"}] + opts


def layout() -> Any:
    """Layout chính của Report Studio Center (/report-studio)."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate is not None:
        return gate
    assert ctx is not None

    initial_reports: list[dict[str, Any]] = []
    initial_err: str | None = None
    try:
        res = list_studio_reports(ctx)
        if res.ok:
            initial_reports = list(res.data or [])
        else:
            initial_err = res.message or "Không tải được danh sách báo cáo."
    except ServiceError as exc:
        initial_err = exc.message

    initial_rows = studio_reports_to_grid_rows(initial_reports)
    model_filter_opts = _load_model_filter_options(ctx)

    clone_modal = dmc.Modal(
        id="rs-center-clone-modal",
        title=dmc.Text("Nhân bản báo cáo Studio", fw=700, size="md"),
        opened=False,
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="rs-center-clone-alert"),
                dmc.Text(id="rs-center-clone-src-label", size="xs", c="dimmed"),
                dmc.TextInput(
                    id="rs-center-clone-code",
                    label="Mã báo cáo mới",
                    withAsterisk=True,
                    size="xs",
                    className="rh-code",
                ),
                dmc.TextInput(
                    id="rs-center-clone-name",
                    label="Tên báo cáo mới",
                    withAsterisk=True,
                    size="xs",
                ),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="rs-center-clone-cancel", size="xs"),
                        button_primary("Nhân bản", id="rs-center-clone-submit", icon="lucide:copy", size="xs"),
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
        id="rs-center-impact-drawer",
        title="Phân tích ảnh hưởng (Impact Analysis)",
        children=html.Div(id="rs-center-impact-content"),
        size=520,
        opened=False,
    )

    archive_modal = modal_confirm(
        id="rs-center-archive-modal",
        title="Lưu trữ báo cáo Studio",
        description=dmc.Stack(
            [
                dmc.Text(id="rs-center-archive-desc", size="sm"),
                dmc.Text(
                    "Giữ lại: Toàn bộ lịch sử phiên bản và dữ liệu báo cáo vẫn còn trong DB.",
                    size="xs",
                    c="dimmed",
                ),
            ],
            gap="xs",
        ),
        confirm_label="Lưu trữ báo cáo",
        danger=True,
        opened=False,
    )

    publish_modal = dmc.Modal(
        id="rs-center-publish-modal",
        title=dmc.Text("Phát hành báo cáo Studio", fw=700, size="md"),
        opened=False,
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="rs-center-publish-alert"),
                dmc.Text(id="rs-center-publish-src-label", size="xs", c="dimmed"),
                dmc.Textarea(
                    id="rs-center-publish-note",
                    label="Change note",
                    placeholder="Mô tả thay đổi trong phiên bản phát hành...",
                    minRows=2,
                    withAsterisk=True,
                    size="xs",
                ),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="rs-center-publish-cancel", size="xs"),
                        button_primary("Phát hành", id="rs-center-publish-submit", icon="lucide:upload-cloud", size="xs"),
                    ],
                    justify="flex-end",
                    gap="xs",
                    mt="xs",
                ),
            ],
            gap="xs",
        ),
    )

    return dmc.Box(
        [
            dcc.Location(id="rs-center-redirect", refresh=True),
            dcc.Store(id="rs-center-reports-store", data=initial_reports),
            dcc.Store(id="rs-center-selected-id", data=None),
            dcc.Store(id="rs-center-selected-version-id", data=None),
            dmc.NotificationContainer(id="rs-center-notif", position="top-right", **{"aria-live": "polite"}),
            page_header(
                title="Report Studio",
                subtitle="Thiết kế báo cáo từ Semantic Model (Table, Matrix, KPI, Bar, Line).",
                actions=[
                    button_primary(
                        "Tạo báo cáo",
                        id="rs-center-create-btn",
                        icon="lucide:plus",
                        size="xs",
                        radius="xl",
                        **{"aria-label": "Tạo báo cáo Studio mới"},  # type: ignore[arg-type]
                    )
                ],
                mb=0,
            ),
            command_bar(
                search_id="rs-center-search",
                search_placeholder="Tìm mã hoặc tên báo cáo...",
                search_debounce=250,
                filters=[
                    dmc.Select(
                        id="rs-center-status-filter",
                        data=STATUS_OPTIONS,
                        value="ALL",
                        size="xs",
                        w=175,
                        **{"aria-label": "Lọc theo trạng thái"},
                    ),
                    dmc.Select(
                        id="rs-center-model-filter",
                        data=model_filter_opts,
                        value="ALL",
                        size="xs",
                        w=220,
                        **{"aria-label": "Lọc theo Semantic Model"},
                    ),
                ],
                actions=[
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:refresh-cw", width=15),
                        id="rs-center-refresh-btn",
                        variant="subtle",
                        color="gray",
                        size="sm",
                        radius="xl",
                        **{"aria-label": "Làm mới danh sách báo cáo"},
                    )
                ],
                mb=0,
            ),
            html.Div(
                render_studio_reports_body(
                    initial_rows,
                    loading=False,
                    has_filter=False,
                    error_msg=initial_err,
                ),
                id="rs-center-body",
                className="rs-center-body",
                **{"aria-live": "polite"},  # type: ignore[arg-type]
            ),
            render_create_report_modal(ctx),
            clone_modal,
            impact_drawer,
            archive_modal,
            publish_modal,
        ],
        id="rs-center-page",
        className="rs-center-page",
    )


@callback(
    Output("rs-center-reports-store", "data"),
    Output("rs-center-body", "children"),
    Output("rs-center-search", "value"),
    Output("rs-center-status-filter", "value"),
    Output("rs-center-model-filter", "value"),
    Input("rs-center-search", "value"),
    Input("rs-center-status-filter", "value"),
    Input("rs-center-model-filter", "value"),
    Input("rs-center-refresh-btn", "n_clicks"),
    Input({"type": "rs-center-retry-btn", "k": ALL}, "n_clicks"),
    Input({"type": "rs-center-clear-filter-btn", "k": ALL}, "n_clicks"),
    State("rs-center-reports-store", "data"),
    prevent_initial_call=True,
)
def handle_center_filter_or_refresh(
    query: str | None,
    status: str | None,
    model_filter: str | None,
    refresh_clicks: int | None,
    retry_clicks: list[int | None] | None,
    clear_clicks: list[int | None] | None,
    cached_reports: list[dict[str, Any]] | None,
) -> tuple[Any, Any, Any, Any, Any]:
    """Lọc client-side hoặc nạp lại danh sách từ service khi bấm Làm mới/Thử lại."""
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate

    trig = dash.callback_context.triggered_id
    if trig is None:
        raise PreventUpdate
    is_clear = isinstance(trig, dict) and trig.get("type") == "rs-center-clear-filter-btn"
    if is_clear:
        if not any(clear_clicks or []):
            raise PreventUpdate
        filtered = filter_studio_reports(cached_reports, query="", status="ALL", model_version_id="ALL")
        return (
            dash.no_update,
            render_studio_reports_body(studio_reports_to_grid_rows(filtered), has_filter=False),
            "",
            "ALL",
            "ALL",
        )

    is_retry = isinstance(trig, dict) and trig.get("type") == "rs-center-retry-btn"
    if is_retry and not any(retry_clicks or []):
        raise PreventUpdate
    if trig == "rs-center-refresh-btn" and not refresh_clicks:
        raise PreventUpdate

    is_refresh_req = (trig == "rs-center-refresh-btn") or is_retry
    if not is_refresh_req and trig not in ("rs-center-search", "rs-center-status-filter", "rs-center-model-filter"):
        raise PreventUpdate
    reports = list(cached_reports or [])
    err_msg: str | None = None
    if is_refresh_req:
        res = list_studio_reports(ctx)
        if res.ok:
            reports = list(res.data or [])
        else:
            err_msg = res.message or "Không tải được danh sách báo cáo."

    has_filter = bool(
        (query or "").strip()
        or (status not in (None, "", "ALL"))
        or (model_filter not in (None, "", "ALL"))
    )
    filtered = filter_studio_reports(reports, query=query, status=status, model_version_id=model_filter)
    return (
        reports if is_refresh_req and err_msg is None else dash.no_update,
        render_studio_reports_body(
            studio_reports_to_grid_rows(filtered), has_filter=has_filter, error_msg=err_msg
        ),
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )


@callback(
    Output("rs-center-create-modal", "opened"),
    Output("rs-center-create-alert", "children"),
    Output("rs-center-create-code", "value"),
    Output("rs-center-create-name", "value"),
    Output("rs-center-create-desc", "value"),
    Input("rs-center-create-btn", "n_clicks"),
    Input({"type": "rs-center-empty-create-btn", "k": ALL}, "n_clicks"),
    Input("rs-center-create-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def handle_create_modal_toggle(
    btn_clicks: int | None,
    empty_clicks: list[int | None] | None,
    cancel_clicks: int | None,
) -> tuple[bool, Any, Any, Any, Any]:
    trig = dash.callback_context.triggered_id
    if trig == "rs-center-create-cancel" and cancel_clicks:
        return False, None, dash.no_update, dash.no_update, dash.no_update
    if trig == "rs-center-create-btn" and btn_clicks:
        return True, None, "", "", ""
    if isinstance(trig, dict) and trig.get("type") == "rs-center-empty-create-btn" and any(empty_clicks or []):
        return True, None, "", "", ""
    raise PreventUpdate


@callback(
    Output("rs-center-create-modal", "opened", allow_duplicate=True),
    Output("rs-center-create-alert", "children", allow_duplicate=True),
    Output("rs-center-redirect", "href", allow_duplicate=True),
    Output("rs-center-notif", "sendNotifications", allow_duplicate=True),
    Input("rs-center-create-submit", "n_clicks"),
    State("rs-center-create-code", "value"),
    State("rs-center-create-name", "value"),
    State("rs-center-create-model", "value"),
    State("rs-center-create-desc", "value"),
    prevent_initial_call=True,
)
def handle_create_submit(
    n_clicks: int | None,
    code: str | None,
    name: str | None,
    model_version_id: str | None,
    desc: str | None,
) -> tuple[bool, Any, Any, Any]:
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    new_id, err, _rows, toast = submit_create_studio_report(
        ctx, code=code, name=name, model_version_id=model_version_id, description=desc
    )
    if err or not new_id:
        return True, alert_box(message=err or "Không thể tạo báo cáo.", tone="crit"), dash.no_update, dash.no_update
    return False, None, f"/report-studio/{new_id}", [toast] if toast else dash.no_update


@callback(
    Output("rs-center-redirect", "href", allow_duplicate=True),
    Output("rs-center-selected-id", "data"),
    Output("rs-center-selected-version-id", "data"),
    Output("rs-center-clone-modal", "opened", allow_duplicate=True),
    Output("rs-center-clone-alert", "children", allow_duplicate=True),
    Output("rs-center-clone-src-label", "children"),
    Output("rs-center-clone-code", "value"),
    Output("rs-center-clone-name", "value"),
    Output("rs-center-impact-drawer", "opened", allow_duplicate=True),
    Output("rs-center-impact-content", "children"),
    Output("rs-center-archive-modal", "opened", allow_duplicate=True),
    Output("rs-center-archive-desc", "children"),
    Output("rs-center-publish-modal", "opened", allow_duplicate=True),
    Output("rs-center-publish-alert", "children", allow_duplicate=True),
    Output("rs-center-publish-src-label", "children"),
    Input({"type": "rs-center-grid", "k": ALL}, "cellRendererData"),
    State("rs-center-reports-store", "data"),
    prevent_initial_call=True,
)
def handle_grid_action(
    cell_data_list: list[dict[str, Any] | None] | None,
    reports: list[dict[str, Any]] | None,
) -> tuple[Any, ...]:
    cell_data = next((c for c in (cell_data_list or []) if isinstance(c, dict)), None)
    if not isinstance(cell_data, dict):
        raise PreventUpdate
    payload = cell_data.get("value")
    if not isinstance(payload, dict):
        raise PreventUpdate
    action = str(payload.get("action") or "")
    report_id = payload.get("id")
    if not report_id:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate

    target = next((r for r in (reports or []) if int(r["id"]) == int(report_id)), None) or {}
    code = str(target.get("code") or f"#{report_id}")
    name = str(target.get("name") or "")

    no = dash.no_update
    if action == "design":
        return f"/report-studio/{int(report_id)}", int(report_id), int(target.get("version_id") or 0), no, no, no, no, no, no, no, no, no, no, no, no
    if action == "view":
        return f"/reports/{int(report_id)}", int(report_id), no, no, no, no, no, no, no, no, no, no, no, no, no
    if action == "clone":
        return (
            no,
            int(report_id),
            no,
            True,
            None,
            f"Nhân bản từ báo cáo gốc: {code} — {name}",
            f"{code}_COPY",
            f"{name} (Bản sao)",
            no,
            no,
            no,
            no,
            no,
            no,
            no,
        )
    if action == "impact":
        content = build_impact_drawer_content(ctx, int(report_id))
        return no, int(report_id), no, no, no, no, no, no, True, content, no, no, no, no, no
    if action == "archive":
        msg = f"Sẽ chuyển báo cáo {code} ({name}) sang trạng thái Lưu trữ (giữ lại toàn bộ phiên bản và dữ liệu)."
        return no, int(report_id), no, no, no, no, no, no, no, no, True, msg, no, no, no
    if action == "publish":
        if str(target.get("version_status") or "") != "DRY_RUN_OK":
            return (
                no, int(report_id), no, no, no, no, no, no, no, no, no, no,
                True,
                alert_box(message="Chỉ phát hành được bản nháp đã kiểm tra (DRY_RUN_OK). Hãy mở Studio và bấm Kiểm tra trước.", tone="warn"),
                f"Báo cáo: {code} — {name}",
            )
        return (
            no, int(report_id), int(target.get("version_id") or 0), no, no, no, no, no,
            no, no, no, no, True, None, f"Báo cáo: {code} — {name}",
        )
    raise PreventUpdate


@callback(
    Output("rs-center-clone-modal", "opened", allow_duplicate=True),
    Output("rs-center-clone-alert", "children", allow_duplicate=True),
    Output("rs-center-reports-store", "data", allow_duplicate=True),
    Output("rs-center-body", "children", allow_duplicate=True),
    Output("rs-center-notif", "sendNotifications", allow_duplicate=True),
    Input("rs-center-clone-submit", "n_clicks"),
    Input("rs-center-clone-cancel", "n_clicks"),
    State("rs-center-selected-id", "data"),
    State("rs-center-clone-code", "value"),
    State("rs-center-clone-name", "value"),
    State("rs-center-search", "value"),
    State("rs-center-status-filter", "value"),
    State("rs-center-model-filter", "value"),
    prevent_initial_call=True,
)
def handle_clone_submit(
    sub_clicks: int | None,
    cancel_clicks: int | None,
    src_id: int | None,
    code: str | None,
    name: str | None,
    query: str | None,
    st_filter: str | None,
    model_filter: str | None,
) -> tuple[bool, Any, Any, Any, Any]:
    trig = dash.callback_context.triggered_id
    if trig == "rs-center-clone-cancel":
        return False, None, dash.no_update, dash.no_update, dash.no_update
    if not sub_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    err, _rows, toast = submit_clone_studio_report(ctx, source_report_id=src_id, code=code, name=name)
    if err or ctx is None:
        return True, alert_box(message=err or "Không thể nhân bản.", tone="crit"), dash.no_update, dash.no_update, dash.no_update
    reports = list_studio_reports(ctx).data or []
    has_filter = bool(
        (query or "").strip()
        or (st_filter not in (None, "", "ALL"))
        or (model_filter not in (None, "", "ALL"))
    )
    filtered = filter_studio_reports(reports, query=query, status=st_filter, model_version_id=model_filter)
    return False, None, reports, render_studio_reports_body(studio_reports_to_grid_rows(filtered), has_filter=has_filter), [toast] if toast else dash.no_update


@callback(
    Output("rs-center-archive-modal", "opened", allow_duplicate=True),
    Output("rs-center-reports-store", "data", allow_duplicate=True),
    Output("rs-center-body", "children", allow_duplicate=True),
    Output("rs-center-notif", "sendNotifications", allow_duplicate=True),
    Input("rs-center-archive-modal-confirm", "n_clicks"),
    Input("rs-center-archive-modal-cancel", "n_clicks"),
    State("rs-center-selected-id", "data"),
    State("rs-center-search", "value"),
    State("rs-center-status-filter", "value"),
    State("rs-center-model-filter", "value"),
    prevent_initial_call=True,
)
def handle_archive_confirm(
    conf_clicks: int | None,
    cancel_clicks: int | None,
    report_id: int | None,
    query: str | None,
    st_filter: str | None,
    model_filter: str | None,
) -> tuple[bool, Any, Any, Any]:
    trig = dash.callback_context.triggered_id
    if trig == "rs-center-archive-modal-cancel":
        return False, dash.no_update, dash.no_update, dash.no_update
    if not conf_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    _rows, toast, err = confirm_archive_studio_report(ctx, report_id)
    if err or ctx is None:
        return False, dash.no_update, dash.no_update, [toast_error(err or "Không thể lưu trữ báo cáo.")]
    reports = list_studio_reports(ctx).data or []
    has_filter = bool(
        (query or "").strip()
        or (st_filter not in (None, "", "ALL"))
        or (model_filter not in (None, "", "ALL"))
    )
    filtered = filter_studio_reports(reports, query=query, status=st_filter, model_version_id=model_filter)
    return False, reports, render_studio_reports_body(studio_reports_to_grid_rows(filtered), has_filter=has_filter), [toast] if toast else dash.no_update


@callback(
    Output("rs-center-publish-modal", "opened", allow_duplicate=True),
    Output("rs-center-publish-alert", "children", allow_duplicate=True),
    Output("rs-center-reports-store", "data", allow_duplicate=True),
    Output("rs-center-body", "children", allow_duplicate=True),
    Output("rs-center-notif", "sendNotifications", allow_duplicate=True),
    Input("rs-center-publish-submit", "n_clicks"),
    Input("rs-center-publish-cancel", "n_clicks"),
    State("rs-center-selected-version-id", "data"),
    State("rs-center-publish-note", "value"),
    State("rs-center-search", "value"),
    State("rs-center-status-filter", "value"),
    State("rs-center-model-filter", "value"),
    prevent_initial_call=True,
)
def handle_publish_submit(
    sub_clicks: int | None,
    cancel_clicks: int | None,
    version_id: int | None,
    note: str | None,
    query: str | None,
    st_filter: str | None,
    model_filter: str | None,
) -> tuple[bool, Any, Any, Any, Any]:
    trig = dash.callback_context.triggered_id
    if trig == "rs-center-publish-cancel":
        return False, None, dash.no_update, dash.no_update, dash.no_update
    if not sub_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not version_id:
        return True, alert_box(message="Thiếu thông tin phiên bản để phát hành.", tone="crit"), dash.no_update, dash.no_update, dash.no_update
    res = publish_studio_report(ctx, int(version_id), {"change_note": note or ""})
    if not res.ok:
        return True, alert_box(message=res.message or "Không thể phát hành.", tone="crit"), dash.no_update, dash.no_update, dash.no_update
    reports = list_studio_reports(ctx).data or []
    has_filter = bool(
        (query or "").strip()
        or (st_filter not in (None, "", "ALL"))
        or (model_filter not in (None, "", "ALL"))
    )
    filtered = filter_studio_reports(reports, query=query, status=st_filter, model_version_id=model_filter)
    return (
        False,
        None,
        reports,
        render_studio_reports_body(studio_reports_to_grid_rows(filtered), has_filter=has_filter),
        [toast_success("Đã phát hành báo cáo Studio.")],
    )
