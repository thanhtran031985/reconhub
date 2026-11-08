"""Trang Quản trị báo cáo + Wizard 6 bước — task 27 bước 3, prototype Screen16.

Danh sách Report Master/template/version + wizard tạo/sửa template:
1. Thông tin, 2. Nguồn dữ liệu, 3. Tham số & LOV, 4. Cấu hình cột,
5. Xem trước (dry-run), 6. Hoàn tất (kích hoạt).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.engine.catalog import list_columns as list_db_columns
from app.services.data_source import list_data_sources
from app.services.lookup import list_lookup_types
from app.services.perm import page_gate
from app.services.report import create_report, get_report, list_reports, update_report
from app.services.report_column import (
    list_columns,
    move_column,
    preview_result_layout,
    refresh_columns,
    restore_column_order,
    update_columns,
)
from app.services.report_param import (
    auto_layout,
    create_param,
    delete_param,
    move_param,
    preview_layout,
    update_param,
    validate_layout,
)
from app.services.report_run import dry_run_version
from app.services.report_source import (
    analyze_version_source,
    apply_source_diff,
    list_report_objects,
    validate_version_sql,
)
from app.services.report_template import (
    activate_version,
    archive_version,
    clone_version,
    create_template,
    get_template,
    get_version,
    list_templates,
    update_template,
    update_version_source,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary
from app.ui.components.command_bar import command_bar
from app.ui.components.empty_state import empty_state
from app.ui.components.page_header import page_header
from app.ui.components.report_widgets import _format_cell, render_param_form, render_result_table
from app.ui.components.status_chip import STATUS_MAP, status_chip

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path_template="/report-admin/<action>",
        path="/report-admin",
        title="Quản trị báo cáo — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "report_admin"

CATEGORY_OPTIONS = [
    {"label": "Tài chính", "value": "FINANCE"},
    {"label": "Kế toán", "value": "ACCOUNTING"},
    {"label": "Vận hành", "value": "OPERATIONS"},
]
CATEGORY_LABELS: dict[str, str] = {
    "FINANCE": "Tài chính",
    "ACCOUNTING": "Kế toán",
    "OPERATIONS": "Vận hành",
}
CATEGORY_FILTER_OPTIONS: list[dict[str, str]] = [{"label": "Tất cả nhóm", "value": "all"}] + CATEGORY_OPTIONS
STATUS_FILTER_OPTIONS: list[dict[str, str]] = [
    {"label": "Tất cả trạng thái", "value": ""},
    {"label": "Hoạt động (ACTIVE)", "value": "ACTIVE"},
    {"label": "Bản nháp (DRAFT)", "value": "DRAFT"},
    {"label": "Sẵn sàng (DRY_RUN_OK)", "value": "DRY_RUN_OK"},
    {"label": "Đã lưu trữ (ARCHIVED)", "value": "ARCHIVED"},
]
SOURCE_TYPE_OPTIONS = [
    {"label": "SQL tùy biến (CUSTOM_SQL)", "value": "CUSTOM_SQL"},
    {"label": "View (VIEW)", "value": "VIEW"},
    {"label": "Bảng (TABLE)", "value": "TABLE"},
]
DATA_TYPE_OPTIONS = [
    {"label": "Chuỗi", "value": "STRING"},
    {"label": "Số", "value": "NUMBER"},
    {"label": "Ngày", "value": "DATE"},
    {"label": "Ngày giờ", "value": "DATETIME"},
    {"label": "Đúng/Sai", "value": "BOOLEAN"},
]
CONTROL_TYPE_OPTIONS = [
    {"label": "Ô nhập text", "value": "TEXT"},
    {"label": "Ô nhập số", "value": "NUMBER"},
    {"label": "Chọn ngày", "value": "DATE"},
    {"label": "Chọn một (Select)", "value": "SELECT"},
    {"label": "Chọn nhiều (MultiSelect)", "value": "MULTI_SELECT"},
    {"label": "Khoảng ngày", "value": "DATE_RANGE"},
]
LOV_TYPE_OPTIONS = [
    {"label": "Không có", "value": "NONE"},
    {"label": "Danh sách tĩnh", "value": "STATIC"},
    {"label": "SQL", "value": "SQL"},
    {"label": "Lookup", "value": "LOOKUP"},
]
FILTER_OPERATOR_OPTIONS = [
    {"label": "=", "value": "="},
    {"label": ">=", "value": ">="},
    {"label": "<=", "value": "<="},
    {"label": ">", "value": ">"},
    {"label": "<", "value": "<"},
    {"label": "BETWEEN", "value": "BETWEEN"},
    {"label": "IN", "value": "IN"},
    {"label": "LIKE_PREFIX", "value": "LIKE_PREFIX"},
    {"label": "IS_NULL", "value": "IS_NULL"},
]
FORMAT_MASKS = {
    "NUMBER": ["#,##0", "#,##0.00", "#,##0%"],
    "DATE": ["DD/MM/YYYY", "DD/MM/YYYY HH:mm", "MM/YYYY", "YYYY-MM-DD"],
    "DATETIME": ["DD/MM/YYYY", "DD/MM/YYYY HH:mm", "DD/MM/YYYY HH:mm:ss"],
    "STRING": [],
    "BOOLEAN": [],
}
ALIGNMENT_OPTIONS = [
    {"label": "Trái", "value": "LEFT"},
    {"label": "Giữa", "value": "CENTER"},
    {"label": "Phải", "value": "RIGHT"},
]
STEP_LABELS = [
    ("Thông tin", "Báo cáo & template"),
    ("Nguồn dữ liệu", "Data Source & SQL"),
    ("Tham số & LOV", "Form tham số"),
    ("Cấu hình cột", "Grid kết quả"),
    ("Xem trước", "Dry-run"),
    ("Hoàn tất", "Kích hoạt"),
]


# ─── State ─────────────────────────────────────────────────────────────────


def _fresh_state() -> dict[str, Any]:
    return {
        "mode": "wizard",
        "report_id": None,
        "template_id": None,
        "version_id": None,
        "version_status": "DRAFT",
        "step": 1,
        "max_step": 1,
        "analyzed": False,
        "dry_run_ok": False,
        "editing_param_id": None,
    }


def _version_detail(ctx: Ctx, version_id: int | None) -> dict[str, Any]:
    if not version_id:
        return {}
    res = get_version(ctx, int(version_id))
    return res.data if res.ok and isinstance(res.data, dict) else {}


def _state_from_version(ctx: Ctx, template_id: int, version_id: int) -> dict[str, Any] | None:
    """State wizard khi mở sửa/clone một version."""
    detail = _version_detail(ctx, version_id)
    if not detail:
        return None
    state = _fresh_state()
    state.update(
        {
            "report_id": None,  # điền ở callback mở (cần report_id)
            "template_id": int(template_id),
            "version_id": int(version_id),
            "version_status": str(detail.get("status", "DRAFT")),
            "step": 1,
            "max_step": 6 if detail.get("columns") else (2 if detail.get("sql_text") else 1),
            "analyzed": bool(detail.get("columns")),
            "dry_run_ok": str(detail.get("status")) == "DRY_RUN_OK",
        }
    )
    return state


def _draft_version_of(ctx: Ctx, template_id: int) -> dict[str, Any] | None:
    """Version DRAFT mới nhất của template (để Sửa); None nếu không có."""
    res = get_template(ctx, int(template_id))
    if not res.ok or not isinstance(res.data, dict):
        return None
    drafts: list[dict[str, Any]] = [v for v in res.data.get("versions", []) if v.get("status") == "DRAFT"]
    if not drafts:
        return None
    return max(drafts, key=lambda v: int(v.get("version_no") or 0))


def _param_values_from_inputs(param_values: list[Any] | None, param_ids: list[dict[str, Any]] | None) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for val, pid in zip(param_values or [], param_ids or [], strict=False):
        code = str(pid.get("index", ""))
        if code.endswith("__from") or code.endswith("__to"):
            base = code.rsplit("__", 1)[0]
            slot = "from" if code.endswith("__from") else "to"
            if val is not None and val != "":
                values.setdefault(base, {})[slot] = val
            continue
        if isinstance(val, list) and len(val) == 2:
            values[code] = {"from": val[0], "to": val[1]}
        elif val is not None and val != "":
            values[code] = val
    return values


def _parse_static_text(text: str | None) -> list[dict[str, str]]:
    """Textarea 'value|label' mỗi dòng → static_json [{"value","label"}]."""
    items: list[dict[str, str]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            value, label = line.split("|", 1)
        else:
            value, label = line, line
        items.append({"value": value.strip(), "label": label.strip()})
    return items


def _static_text_from_lov(lov: dict[str, Any] | None) -> str:
    if not lov:
        return ""
    items = lov.get("static_json") or []
    return "\n".join(f"{i.get('value', '')}|{i.get('label', '')}" for i in items)


def _lov_payload(
    lov_type: str | None,
    lov_sql: str | None,
    lov_lookup_type: str | None,
    lov_static_text: str | None,
    data_source_id: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"lov_type": lov_type or "NONE"}
    if lov_type == "STATIC":
        payload["static_json"] = _parse_static_text(lov_static_text)
    elif lov_type == "SQL":
        payload["sql_text"] = (lov_sql or "").strip() or None
        payload["data_source_id"] = data_source_id
    elif lov_type == "LOOKUP":
        payload["lookup_type"] = (lov_lookup_type or "").strip() or None
    return payload


# ─── Render: danh sách ───────────────────────────────────────────────────────


def _status_badge(status: str) -> Any:
    if status == "DRY_RUN_OK":
        return status_chip("ACTIVE", label="Sẵn sàng", icon="lucide:check-circle")
    if status in STATUS_MAP:
        return status_chip(status)
    return dmc.Badge(status, color="gray", variant="light")


def render_report_list(
    reports: list[dict[str, Any]] | None,
    loading: bool = False,
    error: str | None = None,
    search_term: str = "",
    status_filter: str = "",
    category_filter: str = "",
    page: int = 1,
    page_size: int = 10,
) -> Any:
    """Danh sách Report Master + template/version theo phong cách Fluent Compact tương tự /batches."""
    if loading:
        return dmc.Stack(
            [dmc.Skeleton(height=38, radius="sm") for _ in range(5)],
            gap="xs",
            p="xs",
        )
    if error:
        return alert_box(
            title="Không thể tải danh sách báo cáo",
            message=error,
            tone="crit",
            action=button_danger("Thử lại", id="admin-retry-btn", size="xs"),
        )
    if reports is None or len(reports) == 0:
        return empty_state(
            title="Chưa có báo cáo nào",
            description="Bấm “Báo cáo mới” để đăng ký báo cáo và template đầu tiên.",
            action=dmc.Anchor(
                button_primary("Báo cáo mới", icon="lucide:plus", id="admin-empty-new-btn", size="xs"),
                href="/report-admin/new",
                underline=False,
            ),
        )

    flat_rows: list[dict[str, Any]] = []
    for report in reports:
        cat_code = str(report.get("category_code") or "")
        templates = report.get("templates") or []
        if not templates:
            flat_rows.append(
                {
                    "report_id": report.get("id"),
                    "report_code": str(report.get("code") or ""),
                    "report_name": str(report.get("name") or ""),
                    "description": str(report.get("description") or ""),
                    "category_code": cat_code,
                    "owner": str(report.get("owner") or "—"),
                    "tpl_id": None,
                    "tpl_code": "—",
                    "tpl_name": "Chưa có template",
                    "ver_id": None,
                    "version_no": None,
                    "status": "ACTIVE" if report.get("is_active") else "DRAFT",
                    "is_active": False,
                }
            )
        else:
            for tpl in templates:
                versions = tpl.get("versions") or []
                if not versions:
                    flat_rows.append(
                        {
                            "report_id": report.get("id"),
                            "report_code": str(report.get("code") or ""),
                            "report_name": str(report.get("name") or ""),
                            "description": str(report.get("description") or ""),
                            "category_code": cat_code,
                            "owner": str(report.get("owner") or "—"),
                            "tpl_id": tpl.get("id"),
                            "tpl_code": str(tpl.get("code") or ""),
                            "tpl_name": str(tpl.get("name") or ""),
                            "ver_id": None,
                            "version_no": None,
                            "status": "DRAFT",
                            "is_active": False,
                        }
                    )
                else:
                    for ver in versions:
                        is_active = tpl.get("active_version_id") == ver.get("id")
                        flat_rows.append(
                            {
                                "report_id": report.get("id"),
                                "report_code": str(report.get("code") or ""),
                                "report_name": str(report.get("name") or ""),
                                "description": str(report.get("description") or ""),
                                "category_code": cat_code,
                                "owner": str(report.get("owner") or "—"),
                                "tpl_id": tpl.get("id"),
                                "tpl_code": str(tpl.get("code") or ""),
                                "tpl_name": str(tpl.get("name") or ""),
                                "ver_id": ver.get("id"),
                                "version_no": ver.get("version_no"),
                                "status": str(ver.get("status") or "DRAFT"),
                                "is_active": is_active,
                            }
                        )

    filtered = flat_rows
    if search_term:
        st = search_term.strip().lower()
        filtered = [
            r
            for r in filtered
            if st in r["report_code"].lower()
            or st in r["report_name"].lower()
            or st in r["tpl_code"].lower()
            or st in r["tpl_name"].lower()
            or st in r["description"].lower()
        ]
    if status_filter and status_filter.upper() != "ALL":
        filtered = [r for r in filtered if r["status"] == status_filter]
    if category_filter and category_filter.upper() != "ALL":
        filtered = [r for r in filtered if r["category_code"] == category_filter]

    if not filtered:
        return empty_state(
            title="Không có báo cáo khớp bộ lọc",
            description="Hãy thử thay đổi từ khóa tìm kiếm hoặc bỏ bớt bộ lọc.",
        )

    total_items = len(filtered)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    curr_page = min(max(1, page), total_pages)
    start_idx = (curr_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    paged_items = filtered[start_idx:end_idx]

    th_base: dict[str, Any] = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--surface-2, #FAFAFA)",
        "zIndex": 1,
        "height": "34px",
        "fontSize": "11px",
        "fontWeight": 600,
        "borderBottom": "1px solid var(--line, #E0E0E0)",
        "whiteSpace": "nowrap",
        "textAlign": "center",
    }

    table_rows = []
    for it in paged_items:
        tpl_id = it.get("tpl_id")
        ver_id = it.get("ver_id")
        status = it.get("status") or "DRAFT"
        is_active = it.get("is_active")

        menu_items: list[Any] = []
        if tpl_id:
            menu_items.append(
                dmc.MenuItem(
                    "Sửa",
                    id={"type": "admin-edit", "index": tpl_id},
                    href=f"/report-admin/{tpl_id}",
                    leftSection=DashIconify(icon="lucide:edit-3", width=14),
                )
            )
        if ver_id:
            menu_items.append(
                dmc.MenuItem(
                    "Clone",
                    id={"type": "admin-clone", "index": ver_id},
                    leftSection=DashIconify(icon="lucide:copy", width=14),
                )
            )
            menu_items.append(
                dmc.MenuItem(
                    "Lưu trữ",
                    id={"type": "admin-archive-ver", "index": ver_id},
                    color="orange",
                    leftSection=DashIconify(icon="lucide:archive", width=14),
                )
            )

        action_cell = dmc.Group(
            [
                dmc.Anchor(
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:edit-3", width=14),
                        variant="subtle",
                        color="gray",
                        size="sm",
                        id={"type": "admin-quick-edit", "index": tpl_id or 0},
                        **{"aria-label": f"Sửa {it['tpl_code']}"},
                    ),
                    href=f"/report-admin/{tpl_id}" if tpl_id else "#",
                    underline=False,
                )
                if tpl_id
                else html.Div(),
                dmc.Menu(
                    [
                        dmc.MenuTarget(
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:more-vertical", width=14),
                                variant="subtle",
                                color="gray",
                                size="sm",
                                **{"aria-label": "Thao tác khác"},
                            )
                        ),
                        dmc.MenuDropdown(menu_items),
                    ],
                    position="bottom-end",
                    withArrow=True,
                )
                if menu_items
                else html.Div(),
            ],
            gap="xs",
            justify="center",
            style={"flexWrap": "nowrap"},
        )

        cat_badge = dmc.Badge(
            CATEGORY_LABELS.get(it["category_code"], it["category_code"] or "—"),
            variant="light",
            size="xs",
        )

        ver_badge: Any = "—"
        if it.get("version_no") is not None:
            ver_badge = dmc.Badge(
                f"v{it['version_no']}" + (" ACTIVE" if is_active else ""),
                color="green" if is_active else "gray",
                variant="filled" if is_active else "light",
                size="xs",
            )

        table_rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Anchor(
                                    dmc.Text(
                                        it["tpl_code"] if it["tpl_code"] != "—" else it["report_code"],
                                        className="rh-code",
                                        fw=700,
                                        size="sm",
                                    ),
                                    href=f"/report-admin/{tpl_id}" if tpl_id else "/report-admin/new",
                                    underline=False,
                                ),
                                dmc.Text(it["report_code"], size="10px", c="dimmed", className="rh-code"),
                            ],
                            gap=0,
                        ),
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(it["tpl_name"], fw=600, size="sm"),
                                dmc.Text(
                                    f"{it['report_name']} · {it['description']}".strip(" ·"),
                                    size="xs",
                                    c="dimmed",
                                    lineClamp=1,
                                ),
                            ],
                            gap=2,
                        ),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Group([cat_badge], justify="center"),
                        style={"verticalAlign": "middle", "textAlign": "center"},
                    ),
                    dmc.TableTd(
                        dmc.Group([_status_badge(status)], justify="center"),
                        style={"verticalAlign": "middle", "textAlign": "center"},
                    ),
                    dmc.TableTd(
                        dmc.Group([ver_badge], justify="center"),
                        style={"verticalAlign": "middle", "textAlign": "center"},
                    ),
                    dmc.TableTd(
                        dmc.Text(it["owner"], size="sm", ta="center"),
                        style={"verticalAlign": "middle", "textAlign": "center"},
                    ),
                    dmc.TableTd(
                        action_cell,
                        style={"whiteSpace": "nowrap", "verticalAlign": "middle", "textAlign": "center"},
                    ),
                ]
            )
        )

    pagination_bar = dmc.Group(
        [
            dmc.Text(
                f"Hiển thị {start_idx + 1 if total_items > 0 else 0} – {end_idx} trong tổng số {total_items} mục",
                size="xs",
                c="dimmed",
                fw=500,
            ),
            dmc.Pagination(
                id="admin-pagination",
                total=total_pages,
                value=curr_page,
                size="xs",
            )
            if total_pages > 1
            else html.Div(id="admin-pagination", style={"display": "none"}),
        ],
        justify="space-between",
        align="center",
        px="sm",
        py=6,
        style={
            "borderTop": "1px solid var(--line, #E0E0E0)",
            "backgroundColor": "var(--surface, #FFFFFF)",
            "flexShrink": 0,
        },
    )

    return dmc.Paper(
        [
            dmc.TableScrollContainer(
                minWidth=880,
                style={"flex": 1, "minHeight": 0, "overflow": "auto"},
                children=dmc.Table(
                    [
                        dmc.TableThead(
                            dmc.TableTr(
                                [
                                    dmc.TableTh("Mã", style={**th_base, "minWidth": "160px"}),
                                    dmc.TableTh(
                                        "Tên & Mô tả", style={**th_base, "minWidth": "240px", "textAlign": "left"}
                                    ),
                                    dmc.TableTh("Nhóm", style={**th_base, "minWidth": "110px"}),
                                    dmc.TableTh("Trạng thái", style={**th_base, "minWidth": "110px"}),
                                    dmc.TableTh("Version", style={**th_base, "minWidth": "110px"}),
                                    dmc.TableTh("Chủ sở hữu", style={**th_base, "minWidth": "100px"}),
                                    dmc.TableTh("Thao tác", style={**th_base, "minWidth": "110px"}),
                                ]
                            )
                        ),
                        dmc.TableTbody(table_rows),
                    ],
                    striped=False,
                    highlightOnHover=True,
                    verticalSpacing=4,
                    style={"fontSize": "12px"},
                ),
            ),
            pagination_bar,
        ],
        withBorder=True,
        radius="sm",
        style={
            "flex": 1,
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "backgroundColor": "var(--surface, #FFFFFF)",
            "border": "1px solid var(--line, #E0E0E0)",
        },
    )


def _load_reports_with_templates(ctx: Ctx) -> list[dict[str, Any]]:
    """Danh sách report kèm template + versions (list_templates không trả versions)."""
    reports: list[dict[str, Any]] = []
    res = list_reports(ctx)
    if not res.ok or not isinstance(res.data, list):
        return reports
    for rep in res.data:
        tpl_res = list_templates(ctx, int(rep["id"]))
        templates = tpl_res.data if tpl_res.ok and isinstance(tpl_res.data, list) else []
        enriched = []
        for tpl in templates:
            detail_res = get_template(ctx, int(tpl["id"]))
            if detail_res.ok and isinstance(detail_res.data, dict):
                enriched.append(detail_res.data)
            else:
                enriched.append(tpl)
        rep = dict(rep)
        rep["templates"] = enriched
        reports.append(rep)
    return reports


# ─── Layout ────────────────────────────────────────────────────────────────


def layout(action: str | None = None, **kwargs: Any) -> Any:
    """Giao diện chính: danh sách hoặc wizard (/report-admin, /report-admin/new, /report-admin/<id>).

    Hỗ trợ cả route /report-admin/<action> và query string (?new=1, ?template=, ?clone=).
    """
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="admin-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền quản trị báo cáo.", tone="crit"),
            ]
        )
    reports: list[dict[str, Any]] = []
    if ctx:
        try:
            reports = _load_reports_with_templates(ctx)
        except Exception:
            reports = []

    # Xác định initial mode: wizard hay list
    initial_mode = "list"
    initial_state: dict[str, Any] = {"mode": "list", "step": 1, "max_step": 1}

    if action == "new" or str(kwargs.get("new", "")).lower() in ("1", "true"):
        initial_mode = "wizard"
        initial_state = _fresh_state()
    elif action and action.isdigit():
        tpl_id = int(action)
        new_state, _ = handle_open_edit(1, tpl_id)
        if new_state:
            initial_mode = "wizard"
            initial_state = new_state
    elif kwargs.get("template"):
        try:
            tpl_id = int(str(kwargs.get("template")))
            new_state, _ = handle_open_edit(1, tpl_id)
            if new_state:
                initial_mode = "wizard"
                initial_state = new_state
        except (ValueError, TypeError):
            pass
    elif kwargs.get("clone"):
        try:
            ver_id = int(str(kwargs.get("clone")))
            new_state, _ = handle_clone(1, ver_id)
            if new_state:
                initial_mode = "wizard"
                initial_state = new_state
        except (ValueError, TypeError):
            pass

    return html.Div(
        [
            dcc.Location(id="admin-location", refresh=False),
            dcc.Store(id="admin-state-store", data=initial_state),
            dcc.Store(id="admin-dryrun-store", data=None),
            dcc.Store(id="admin-alert-store", data=None),
            dcc.Store(id="admin-reports-store", data=reports),
            html.Div(id="admin-alert", **{"aria-live": "polite"}),  # type: ignore[arg-type]
            html.Div(
                id="admin-list-container",
                children=[
                    page_header(
                        title="Quản trị báo cáo",
                        subtitle="Danh sách Report Master và wizard cấu hình template báo cáo",
                        actions=[
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:refresh-cw", width=14),
                                id="admin-refresh-btn",
                                variant="subtle",
                                color="gray",
                                size="sm",
                                **{"aria-label": "Làm mới danh sách"},
                            ),
                            dmc.Anchor(
                                button_primary("+ Báo cáo mới", icon="lucide:plus", id="admin-new-btn", size="xs"),
                                href="/report-admin/new",
                                underline=False,
                            ),
                        ],
                    ),
                    command_bar(
                        search_id="admin-filter-search",
                        search_placeholder="Tìm theo mã hoặc tên báo cáo...",
                        filters=[
                            dmc.Select(
                                id="admin-filter-status",
                                data=STATUS_FILTER_OPTIONS,
                                value="",
                                w=170,
                                size="xs",
                                styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                            ),
                            dmc.Select(
                                id="admin-filter-category",
                                data=CATEGORY_FILTER_OPTIONS,
                                value="all",
                                w=160,
                                size="xs",
                                styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                            ),
                            html.Span(
                                id="admin-count-text",
                                style={"fontSize": "11px", "color": "var(--ink-soft, #616161)", "marginLeft": "auto"},
                            ),
                        ],
                    ),
                    html.Div(
                        id="admin-table-container",
                        children=render_report_list(reports),
                        style={
                            "flex": 1,
                            "minHeight": 0,
                            "display": "flex",
                            "flexDirection": "column",
                            "overflow": "hidden",
                        },
                    ),
                ],
                style={
                    "display": "none" if initial_mode == "wizard" else "flex",
                    "flexDirection": "column",
                    "flex": "1 1 0%",
                    "minHeight": 0,
                    "overflow": "hidden",
                    "padding": "8px 12px",
                    "gap": "6px",
                    "height": "100%",
                },
            ),
            dcc.Loading(
                id="admin-wizard-loading",
                type="circle",
                children=html.Div(
                    id="admin-wizard-container",
                    children=render_wizard(initial_state) if initial_mode == "wizard" else [],
                    style={
                        "display": "flex" if initial_mode == "wizard" else "none",
                        "flexDirection": "column",
                        "flex": "1 1 0%",
                        "minHeight": 0,
                        "overflow": "hidden",
                        "height": "100%",
                    },
                ),
                style={"flex": "1 1 0%", "minHeight": 0, "display": "flex", "flexDirection": "column", "height": "100%"},
            ),
        ],
        style={
            "height": "calc(100vh - 48px)",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "backgroundColor": "var(--mantine-color-body)",
        },
    )


# ─── Render: wizard ────────────────────────────────────────────────────────


def _ds_options(ctx: Ctx) -> list[dict[str, Any]]:
    try:
        res = list_data_sources(ctx)
    except Exception:
        return []
    items = res.data if hasattr(res, "data") else res
    if not isinstance(items, list):
        return []
    sorted_items = sorted(items, key=lambda x: 0 if getattr(x, "db_type", "") == "SQLITE" else 1)
    return [{"label": f"{ds.name} ({ds.env})", "value": str(ds.id)} for ds in sorted_items if hasattr(ds, "id")]


def _lookup_options(ctx: Ctx) -> list[dict[str, str]]:
    try:
        res = list_lookup_types(ctx)
    except Exception:
        return []
    items = res.data if hasattr(res, "data") else res
    if not isinstance(items, list):
        return []
    return [
        {
            "label": str(i.get("lookup_type") or i.get("LOOKUP_TYPE")),
            "value": str(i.get("lookup_type") or i.get("LOOKUP_TYPE")),
        }
        for i in items
        if isinstance(i, dict)
    ]


def render_step1(state: dict[str, Any]) -> Any:
    """Bước 1: thông tin chung (bố cục 4 cột theo preview.html)."""
    ctx = get_current_ctx()
    report: dict[str, Any] = {}
    template: dict[str, Any] = {}
    version: dict[str, Any] = {}
    editing = bool(state.get("report_id") and state.get("template_id"))
    if ctx and editing:
        rep_res = get_report(ctx, int(state["report_id"]))
        if rep_res.ok and isinstance(rep_res.data, dict):
            report = rep_res.data
        tpl_res = get_template(ctx, int(state["template_id"]))
        if tpl_res.ok and isinstance(tpl_res.data, dict):
            template = tpl_res.data
        version = _version_detail(ctx, state.get("version_id"))

    tpl_status = str(template.get("status") or version.get("status") or "DRAFT")

    return dmc.Stack(
        [
            html.Div(
                [
                    dmc.Title("1. Thông tin chung", order=3, style={"fontSize": "15px", "fontWeight": 600, "margin": 0}),
                    dmc.Text(
                        "Khai báo Report Master và template đầu tiên. Bố cục giữ đúng màn thiết kế đã duyệt.",
                        size="xs",
                        c="dimmed",
                        mt=2,
                        mb="xs",
                    ),
                ]
            ),
            dmc.SimpleGrid(
                cols={"base": 1, "sm": 2, "md": 4},
                spacing="sm",
                children=[
                    dmc.TextInput(
                        id="admin-s1-report-code",
                        label="Mã báo cáo *",
                        value=str(report.get("code") or ""),
                        disabled=editing,
                        placeholder="VD: FIN_REVENUE",
                        description="Viết hoa, không dấu; không đổi sau khi tạo.",
                        inputWrapperOrder=["label", "input", "description"],
                        style={"fontFamily": "var(--font-mono, Consolas, monospace)"},
                        **{"aria-label": "Mã báo cáo"},
                    ),
                    dmc.TextInput(
                        id="admin-s1-report-name",
                        label="Tên báo cáo *",
                        value=str(report.get("name") or ""),
                        placeholder="VD: Báo cáo doanh thu",
                        **{"aria-label": "Tên báo cáo"},
                    ),
                    dmc.Select(
                        id="admin-s1-category",
                        label="Nhóm báo cáo *",
                        data=CATEGORY_OPTIONS,
                        value=str(report.get("category_code") or "FINANCE"),
                        clearable=False,
                    ),
                    dmc.TextInput(
                        id="admin-s1-tpl-code",
                        label="Mã template *",
                        value=str(template.get("code") or ""),
                        disabled=editing,
                        placeholder="VD: REVENUE_DETAIL",
                        style={"fontFamily": "var(--font-mono, Consolas, monospace)"},
                        **{"aria-label": "Mã template"},
                    ),
                    dmc.TextInput(
                        id="admin-s1-tpl-name",
                        label="Tên template *",
                        value=str(template.get("name") or ""),
                        placeholder="VD: Chi tiết doanh thu",
                    ),
                    dmc.NumberInput(
                        id="admin-s1-display-order",
                        label="Thứ tự template",
                        value=int(template.get("display_order") or 1),
                        min=1,
                    ),
                    dmc.TextInput(
                        id="admin-s1-owner",
                        label="Chủ sở hữu nghiệp vụ",
                        value=str(report.get("owner") or ""),
                        placeholder="VD: FIN",
                    ),
                    dmc.Select(
                        id="admin-s1-tpl-status",
                        label="Trạng thái",
                        data=[
                            {"label": "DRAFT - Đang soạn thảo", "value": "DRAFT"},
                            {"label": "ACTIVE - Đang dùng", "value": "ACTIVE"},
                            {"label": "ARCHIVED - Lưu trữ", "value": "ARCHIVED"},
                        ],
                        value=tpl_status,
                        disabled=True,
                    ),
                ],
            ),
            dmc.Textarea(
                id="admin-s1-description",
                label="Mô tả báo cáo",
                value=str(report.get("description") or ""),
                autosize=True,
                minRows=2,
                placeholder="Báo cáo chi tiết và tổng hợp doanh thu theo đơn vị, khách hàng và dịch vụ.",
                mt="xs",
            ),
            dmc.Group(
                [
                    dmc.Checkbox(
                        id="admin-s1-default-fav",
                        label="Đánh dấu báo cáo yêu thích mặc định",
                        checked=bool(report.get("default_favorite", False)),
                    ),
                    dmc.Checkbox(
                        id="admin-s1-visible",
                        label="Hiển thị trong Trung tâm báo cáo sau khi kích hoạt",
                        checked=bool(report.get("is_visible", True)),
                    ),
                ],
                mt="xs",
            ),
            dmc.Alert(
                "Một Report Master có thể chứa nhiều template động. Sau khi hoàn tất template này, Admin có thể thêm các template “Theo đơn vị”, “Theo khách hàng” hoặc “Theo dịch vụ”.",
                color="orange",
                variant="light",
                mt="xs",
            ),
            html.Div(
                [
                    dmc.NumberInput(id="admin-s1-timeout", value=int(version.get("timeout_sec") or 300)),
                    dmc.NumberInput(id="admin-s1-preview-max", value=int(version.get("preview_max_rows") or 100)),
                    dmc.NumberInput(id="admin-s1-export-max", value=int(version.get("export_max_rows") or 1000000)),
                    dmc.Button("Lưu và tiếp tục", id="admin-s1-hidden-save-btn"),
                ],
                style={"display": "none"},
            ),
        ],
        gap="xs",
    )


def render_step2(state: dict[str, Any]) -> Any:
    """Bước 2: Data Source và SQL (bố cục theo preview.html)."""
    ctx = get_current_ctx()
    version = _version_detail(ctx, state.get("version_id")) if ctx else {}
    ds_opts = _ds_options(ctx) if ctx else []
    source_type = str(version.get("source_type") or "TABLE")
    ds_id = version.get("data_source_id") or (ds_opts[0]["value"] if ds_opts else None)

    # Objects được nạp tự động qua callback handle_s2_source_type_and_objects
    initial_objects: list[dict[str, str]] = []

    return dmc.Stack(
        [
            html.Div(
                [
                    dmc.Title("2. Nguồn dữ liệu & SQL (Data Source)", order=3, style={"fontSize": "15px", "fontWeight": 600, "margin": 0}),
                    dmc.Text(
                        "Chọn Data Source, cấu hình nguồn dữ liệu (Table / View / Custom SQL) và phân tích SQL.",
                        size="xs",
                        c="dimmed",
                        mt=2,
                        mb="xs",
                    ),
                ]
            ),
            dmc.SimpleGrid(
                cols={"base": 1, "sm": 2, "md": 4},
                spacing="sm",
                children=[
                    dmc.Select(
                        id="admin-s2-ds",
                        label="Data Source *",
                        data=ds_opts,
                        value=str(ds_id) if ds_id else None,
                        placeholder="Chọn Data Source…",
                        searchable=True,
                        clearable=False,
                    ),
                    dmc.Select(
                        id="admin-s2-source-type",
                        label="Loại nguồn",
                        data=SOURCE_TYPE_OPTIONS,
                        value=source_type,
                        clearable=False,
                    ),
                    dmc.NumberInput(
                        id="admin-s2-timeout",
                        label="Timeout (giây)",
                        value=int(version.get("timeout_sec") or 300),
                        min=1,
                        max=600,
                    ),
                    dmc.NumberInput(
                        id="admin-s2-preview-max",
                        label="Tối đa dòng preview",
                        value=int(version.get("preview_max_rows") or 100),
                        min=1,
                    ),
                ],
            ),
            # Table / View Picker Box (hiển thị khi loại nguồn là VIEW hoặc TABLE)
            html.Div(
                id="admin-s2-object-box",
                style={"display": "block" if source_type in ("VIEW", "TABLE") else "none"},
                children=[
                    dmc.Paper(
                        withBorder=True,
                        radius="sm",
                        p="sm",
                        style={"backgroundColor": "var(--bg-subtle, #f8fafc)"},
                        children=[
                            dmc.SimpleGrid(
                                cols={"base": 1, "sm": 2},
                                spacing="sm",
                                children=[
                                    dmc.TextInput(
                                        id="admin-s2-owner",
                                        label="Schema (owner)",
                                        value=str(version.get("source_owner") or ""),
                                        placeholder="VD: DATARAW hoặc FIN (tùy chọn)",
                                    ),
                                    dmc.Select(
                                        id="admin-s2-object-select",
                                        label="Chọn Bảng / View để tự sinh SQL *",
                                        data=initial_objects,
                                        value=str(version.get("source_object")) if version.get("source_object") else None,
                                        placeholder="Chọn bảng hoặc view từ Data Source...",
                                        searchable=True,
                                        clearable=True,
                                    ),
                                ],
                            ),
                            dmc.Group(
                                [
                                    dmc.Text(
                                        "Khi chọn Bảng/View, hệ thống sẽ tự động sinh câu lệnh SQL và điền vào ô bên dưới. Ưu tiên VIEW đã lọc sẵn.",
                                        size="xs",
                                        c="dimmed",
                                    ),
                                    dmc.Button(
                                        "Tải lại danh sách",
                                        id="admin-s2-load-objects-btn",
                                        variant="subtle",
                                        size="xs",
                                        leftSection=DashIconify(icon="lucide:refresh-cw", width=14),
                                    ),
                                ],
                                justify="space-between",
                                align="center",
                                mt="xs",
                            ),
                            html.Div(
                                [
                                    dmc.TextInput(id="admin-s2-object", value=str(version.get("source_object") or "")),
                                    dmc.Button(id="admin-s2-analyze-object-btn"),
                                ],
                                style={"display": "none"},
                            ),
                        ],
                    )
                ],
            ),
            # SQL Section
            dmc.Group(
                [
                    dmc.Badge("SELECT / WITH SELECT only", color="orange", variant="light"),
                    dmc.Button(
                        "Phân tích SQL",
                        id="admin-s2-analyze-btn",
                        variant="filled",
                        size="sm",
                        leftSection=DashIconify(icon="lucide:scan", width=16),
                    ),
                ],
                justify="space-between",
                align="center",
                mt="xs",
            ),
            dmc.Textarea(
                id="admin-s2-sql",
                value=str(version.get("sql_text") or ""),
                autosize=True,
                minRows=7,
                placeholder="SELECT invoice_no, invoice_date, customer_name, total_amount\nFROM fin_invoice\nWHERE invoice_date >= :p_from_date...",
                style={
                    "fontFamily": "var(--font-mono, Consolas, monospace)",
                    "fontSize": "12.5px",
                    "lineHeight": "1.6",
                },
                styles={
                    "input": {
                        "backgroundColor": "#0a1427",
                        "color": "#dce8ff",
                        "fontFamily": "var(--font-mono, Consolas, monospace)",
                    }
                },
                **{"aria-label": "Câu lệnh SQL"},
            ),
            # Analysis Status
            html.Div(
                id="admin-s2-analyzed",
                children=[
                    (
                        dmc.Alert(
                            "✓ Phát hiện nguồn dữ liệu hợp lệ. SQL sẵn sàng cho bước Tham số và Cột.",
                            color="green",
                            variant="light",
                        )
                        if state.get("analyzed")
                        else dmc.Text(
                            "Phân tích SQL để sinh danh sách tham số và cột.",
                            size="xs",
                            c="dimmed",
                        )
                    )
                ],
            ),
            html.Div(
                dmc.NumberInput(id="admin-s2-export-max", value=int(version.get("export_max_rows") or 1000000)),
                style={"display": "none"},
            ),
        ],
        gap="xs",
    )


def _render_param_canvas(params: list[dict[str, Any]], violations: list[dict[str, Any]]) -> Any:
    """Canvas hiển thị trực quan các hàng tìm kiếm (tối đa 12 cột mỗi hàng theo chuẩn Screen16 preview.html)."""
    if not params:
        return html.Div(
            empty_state("Chưa có tham số nào.", "Thêm tham số hoặc phân tích SQL ở Bước 2."),
            id="param-canvas",
        )

    rows_map: dict[int, list[dict[str, Any]]] = {}
    for p in sorted(params, key=lambda x: (int(x.get("display_row") or 1), int(x.get("display_order") or 0))):
        r = int(p.get("display_row") or 1)
        rows_map.setdefault(r, []).append(p)

    violation_rows = {v.get("row") for v in violations}

    row_sections = []
    for r in sorted(rows_map.keys()):
        p_list = rows_map[r]
        total_span = sum(min(12, max(1, int(p.get("grid_span") or 1))) for p in p_list)
        is_over = total_span > 12 or r in violation_rows

        status_badge = (
            dmc.Badge(
                f"Vượt {total_span - 12} cột" if total_span > 12 else "Vượt cột",
                color="red",
                variant="light",
                size="xs",
            )
            if is_over
            else dmc.Badge("Hợp lệ", color="green", variant="light", size="xs")
        )

        boxes = []
        for p in p_list:
            span = min(12, max(1, int(p.get("grid_span") or 1)))
            boxes.append(
                html.Div(
                    [
                        dmc.Group(
                            [
                                dmc.Text(str(p.get("label") or p.get("code")), size="xs", fw=600, truncate="end"),
                                dmc.Badge(f"{span}/12", size="xs", variant="outline"),
                            ],
                            justify="space-between",
                            gap="xs",
                            wrap="nowrap",
                        ),
                        dmc.Text(
                            f"[{p.get('control_type', 'TEXT')}]",
                            size="xs",
                            c="dimmed",
                            style={
                                "height": "24px",
                                "lineHeight": "24px",
                                "backgroundColor": "var(--surface-2, #FAFAFA)",
                                "borderRadius": "4px",
                                "padding": "0 6px",
                                "border": "1px solid var(--line, #E0E0E0)",
                                "marginTop": "4px",
                                "textAlign": "center",
                                "fontSize": "11px",
                            },
                        ),
                    ],
                    style={
                        "gridColumn": f"span {span}",
                        "backgroundColor": "var(--surface-1, #FFFFFF)",
                        "border": "1px solid var(--line, #E0E0E0)",
                        "borderRadius": "4px",
                        "padding": "6px 8px",
                    },
                )
            )

        row_sections.append(
            dmc.Paper(
                [
                    dmc.Group(
                        [
                            dmc.Group(
                                [
                                    dmc.Text(f"Hàng {r}", fw=600, size="xs"),
                                    dmc.Badge(f"{total_span}/12", size="xs", variant="light", color="red" if is_over else "blue"),
                                ],
                                gap="xs",
                            ),
                            status_badge,
                        ],
                        justify="space-between",
                        mb="xs",
                    ),
                    html.Div(
                        boxes,
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(12, 1fr)",
                            "gap": "6px",
                        },
                    ),
                ],
                withBorder=True,
                p="xs",
                radius="sm",
                style={
                    "borderStyle": "dashed",
                    "borderColor": "var(--crimson-7, #e03131)" if is_over else "var(--line, #E0E0E0)",
                    "backgroundColor": "rgba(224, 49, 49, 0.04)" if is_over else "transparent",
                    "marginBottom": "8px",
                },
            )
        )

    return html.Div(row_sections, id="param-canvas")


def render_step3(state: dict[str, Any]) -> Any:
    """Bước 3: tham số & LOV + layout 12 cột chuẩn Master-Detail Screen16."""
    ctx = get_current_ctx()
    version = _version_detail(ctx, state.get("version_id")) if ctx else {}
    params = version.get("params", [])
    violations = []
    if ctx and state.get("version_id"):
        val_res = validate_layout(ctx, int(state["version_id"]))
        if val_res.ok and isinstance(val_res.data, dict):
            violations = val_res.data.get("violations", [])
    editing_id = state.get("editing_param_id")
    editing = None
    if editing_id:
        editing = next((p for p in params if int(p["id"]) == int(editing_id)), None)
    lov = (editing or {}).get("lov") or {}
    lookup_opts = _lookup_options(ctx) if ctx else []
    rows = []
    for p in params:
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(str(p["code"]), className="rh-code", fw=600),
                    dmc.TableTd(str(p["label"])),
                    dmc.TableTd(f"{p['data_type']} / {p['control_type']}"),
                    dmc.TableTd(f"Hàng {p['display_row']} · span {p['grid_span']}"),
                    dmc.TableTd(str((p.get("lov") or {}).get("lov_type", "NONE"))),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.ActionIcon(
                                    DashIconify(icon="lucide:arrow-up", width=14),
                                    id={"type": "admin-param-up", "index": p["id"]},
                                    variant="subtle",
                                    size="xs",
                                    **{"aria-label": f"Dời tham số {p['code']} lên"},
                                ),
                                dmc.ActionIcon(
                                    DashIconify(icon="lucide:arrow-down", width=14),
                                    id={"type": "admin-param-down", "index": p["id"]},
                                    variant="subtle",
                                    size="xs",
                                    **{"aria-label": f"Dời tham số {p['code']} xuống"},
                                ),
                                dmc.Button(
                                    "Sửa",
                                    size="xs",
                                    variant="subtle",
                                    id={"type": "admin-param-edit", "index": p["id"]},
                                ),
                                dmc.Button(
                                    "Xóa",
                                    size="xs",
                                    variant="subtle",
                                    color="red",
                                    id={"type": "admin-param-del", "index": p["id"]},
                                    **{"aria-label": f"Xóa tham số {p['code']}"},
                                ),
                            ],
                            gap="xs",
                        )
                    ),
                ]
            )
        )

    # Master Column (Trái): Danh sách tham số, Canvas 12 cột và Form trường
    master_content = dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text("Danh sách tham số", fw=600, size="sm"),
                    dmc.Button(
                        "Tự sắp xếp",
                        id="admin-p-autolayout-btn",
                        variant="light",
                        size="xs",
                    ),
                ],
                justify="space-between",
            ),
            (
                dmc.Alert(
                    "Layout vượt 12 cột ở: "
                    + ", ".join(f"hàng {v['row']} (tổng {v['total']})" for v in violations)
                    + ". Sửa lại trước khi qua bước sau.",
                    color="red",
                    title="Layout chưa hợp lệ",
                )
                if violations
                else html.Div()
            ),
            dmc.ScrollArea(
                dmc.Table(
                    [
                        dmc.TableThead(
                            dmc.TableTr(
                                [
                                    dmc.TableTh("Mã"),
                                    dmc.TableTh("Nhãn"),
                                    dmc.TableTh("Kiểu / Control"),
                                    dmc.TableTh("Vị trí"),
                                    dmc.TableTh("LOV"),
                                    dmc.TableTh(""),
                                ]
                            )
                        ),
                        dmc.TableTbody(rows),
                    ],
                    striped=True,
                    withTableBorder=True,
                ),
                h=160,
            )
            if rows
            else empty_state("Chưa có tham số nào.", "Thêm tham số bên dưới."),
            dmc.Divider(my="xs"),
            dmc.Text("Thiết kế layout tham số tìm kiếm (Canvas 12 cột)", fw=600, size="sm"),
            _render_param_canvas(params, violations),
            dmc.Divider(label="Thêm tham số" if not editing else f"Sửa tham số {editing.get('code')}", labelPosition="left"),
            dmc.TextInput(
                id="admin-p-code",
                label="Mã tham số",
                value=str(editing.get("code") or "") if editing else "",
                disabled=bool(editing),
                placeholder="VD: p_org (viết thường, bắt đầu bằng p_)",
            ),
            dmc.TextInput(
                id="admin-p-label",
                label="Nhãn",
                value=str(editing.get("label") or "") if editing else "",
                placeholder="VD: Đơn vị",
            ),
            dmc.Group(
                [
                    dmc.Select(
                        id="admin-p-data-type",
                        label="Kiểu dữ liệu",
                        data=DATA_TYPE_OPTIONS,
                        value=str(editing.get("data_type") or "STRING") if editing else "STRING",
                        clearable=False,
                    ),
                    dmc.Select(
                        id="admin-p-control-type",
                        label="Control",
                        data=CONTROL_TYPE_OPTIONS,
                        value=str(editing.get("control_type") or "TEXT") if editing else "TEXT",
                        clearable=False,
                    ),
                    dmc.Checkbox(
                        id="admin-p-required",
                        label="Bắt buộc",
                        checked=bool(editing.get("required")) if editing else False,
                    ),
                ],
                grow=True,
                align="end",
            ),
            dmc.Group(
                [
                    dmc.Select(
                        id="admin-p-default-type",
                        label="Mặc định",
                        data=[
                            {"label": "Không có", "value": "NONE"},
                            {"label": "Giá trị tĩnh", "value": "STATIC"},
                            {"label": "Hôm nay", "value": "TODAY"},
                            {"label": "Giá trị LOV đầu tiên", "value": "FIRST_LOV"},
                        ],
                        value=str(editing.get("default_type") or "NONE") if editing else "NONE",
                        clearable=False,
                    ),
                    dmc.TextInput(
                        id="admin-p-default-value",
                        label="Giá trị mặc định",
                        value=str(editing.get("default_value") or "") if editing else "",
                    ),
                ],
                grow=True,
                align="end",
            ),
            dmc.Group(
                [
                    dmc.NumberInput(
                        id="admin-p-row",
                        label="Hàng",
                        value=int(editing.get("display_row") or 1) if editing else 1,
                        min=1,
                    ),
                    dmc.NumberInput(
                        id="admin-p-order",
                        label="Thứ tự",
                        value=int(editing.get("display_order") or 10) if editing else 10,
                        min=0,
                    ),
                    dmc.NumberInput(
                        id="admin-p-span",
                        label="Span (1–12)",
                        value=int(editing.get("grid_span") or 6) if editing else 6,
                        min=1,
                        max=12,
                    ),
                    dmc.Checkbox(
                        id="admin-p-visible",
                        label="Hiển thị",
                        checked=bool(editing.get("is_visible", True)) if editing else True,
                    ),
                ],
                grow=True,
                align="end",
            ),
            dmc.Group(
                [
                    dmc.TextInput(
                        id="admin-p-filter-col",
                        label="Cột lọc (VIEW/TABLE)",
                        value=str(editing.get("filter_column") or "") if editing else "",
                        placeholder="VD: ORG",
                    ),
                    dmc.Select(
                        id="admin-p-filter-op",
                        label="Toán tử lọc",
                        data=FILTER_OPERATOR_OPTIONS,
                        value=str(editing.get("filter_operator") or "=") if editing else "=",
                        clearable=True,
                    ),
                ],
                grow=True,
                align="end",
            ),
        ],
        gap="sm",
    )

    # Detail Column (Phải): LOV Side Panel
    detail_content = dmc.Paper(
        dmc.Stack(
            [
                dmc.Title(
                    f"Cấu hình LOV: {editing.get('code')}" if editing else "Cấu hình LOV",
                    order=4,
                    size="sm",
                ),
                dmc.Text(
                    "Chọn một tham số ở danh sách bên trái để cấu hình danh sách giá trị chọn (LOV).",
                    size="xs",
                    c="dimmed",
                ),
                dmc.Select(
                    id="admin-p-lov-type",
                    label="Loại LOV",
                    data=LOV_TYPE_OPTIONS,
                    value=str(lov.get("lov_type") or "NONE"),
                    clearable=False,
                ),
                dmc.Textarea(
                    id="admin-p-lov-static",
                    label="Danh sách tĩnh (mỗi dòng: value|label)",
                    value=_static_text_from_lov(lov),
                    autosize=True,
                    minRows=2,
                    placeholder="HN|Hà Nội\nHCM|TP. Hồ Chí Minh",
                ),
                dmc.Textarea(
                    id="admin-p-lov-sql",
                    label="SQL LOV (trả về 2 cột VALUE và LABEL)",
                    value=str(lov.get("sql_text") or ""),
                    autosize=True,
                    minRows=3,
                    placeholder="SELECT code AS value, name AS label FROM ...",
                ),
                dmc.Select(
                    id="admin-p-lov-lookup",
                    label="Lookup type",
                    data=lookup_opts,
                    value=str(lov.get("lookup_type") or ""),
                    placeholder="Chọn lookup type…",
                    searchable=True,
                    clearable=True,
                ),
                dmc.Group(
                    [
                        dmc.Button(
                            "Lưu tham số",
                            id="admin-p-save-btn",
                            variant="filled",
                        ),
                        (
                            dmc.Button(
                                "Hủy sửa",
                                id="admin-p-cancel-edit-btn",
                                variant="subtle",
                            )
                            if editing
                            else html.Div()
                        ),
                    ],
                    mt="sm",
                ),
                html.Div(id="admin-p-alert"),
            ],
            gap="sm",
        ),
        withBorder=True,
        p="md",
        radius="sm",
        style={"backgroundColor": "var(--surface-1, #FFFFFF)"},
        id="lovside",
    )

    return dmc.Stack(
        [
            dmc.Title("3. Tham số & Cấu hình LOV", order=3),
            dmc.Grid(
                [
                    dmc.GridCol(master_content, span={"base": 12, "lg": 7}),
                    dmc.GridCol(detail_content, span={"base": 12, "lg": 5}),
                ],
                gutter="md",
            ),
        ],
        gap="md",
    )


def _render_columns_preview(columns: list[dict[str, Any]]) -> Any:
    """Preview header cột và dữ liệu mẫu giả lập cho bước 4 (Screen16 preview.html)."""
    visible = [c for c in columns if c.get("web_visible")]
    if not visible:
        return empty_state("Chưa có cột hiển thị.", "Bật Web ở grid cột.")
    header = [
        dmc.TableTh(
            c.get("label") or c.get("field_name"),
            style={
                "textAlign": "right" if c.get("alignment") == "RIGHT" or c.get("data_type") == "NUMBER" else "left",
                "minWidth": f"{c.get('column_width') or 120}px",
                "whiteSpace": "nowrap",
                "fontSize": "11px",
                "fontWeight": 600,
            },
        )
        for c in visible
    ]
    mock_row_1 = []
    mock_row_2 = []
    for c in visible:
        dtype = c.get("data_type", "STRING")
        field = str(c.get("field_name", "")).upper()
        val1: Any
        val2: Any
        if dtype == "NUMBER":
            val1 = 10000000
            val2 = 8000000
        elif dtype in ("DATE", "DATETIME"):
            val1 = "2026-10-01T08:00:00"
            val2 = "2026-10-02T09:30:00"
        elif "CODE" in field or "NO" in field:
            val1 = "HD000123"
            val2 = "HD000124"
        elif "NAME" in field:
            val1 = "Công ty ABC"
            val2 = "Công ty XYZ"
        else:
            val1 = "Dữ liệu mẫu 1"
            val2 = "Dữ liệu mẫu 2"
        mock_row_1.append(
            dmc.TableTd(
                _format_cell(val1, c),
                style={
                    "textAlign": "right" if c.get("alignment") == "RIGHT" or dtype == "NUMBER" else "left",
                    "height": "28px",
                    "whiteSpace": "nowrap",
                },
            )
        )
        mock_row_2.append(
            dmc.TableTd(
                _format_cell(val2, c),
                style={
                    "textAlign": "right" if c.get("alignment") == "RIGHT" or dtype == "NUMBER" else "left",
                    "height": "28px",
                    "whiteSpace": "nowrap",
                },
            )
        )

    return dmc.ScrollArea(
        dmc.Table(
            [
                dmc.TableThead(dmc.TableTr(header)),
                dmc.TableTbody([dmc.TableTr(mock_row_1), dmc.TableTr(mock_row_2)]),
            ],
            striped=True,
            highlightOnHover=True,
            withTableBorder=True,
        ),
        h=120,
    )


def render_step4(state: dict[str, Any]) -> Any:
    """Bước 4: cấu hình cột."""
    ctx = get_current_ctx()
    columns: list[dict[str, Any]] = []
    if ctx and state.get("version_id"):
        res = list_columns(ctx, int(state["version_id"]))
        if res.ok and isinstance(res.data, list):
            columns = res.data
    rows = []
    for i, c in enumerate(columns):
        masks = FORMAT_MASKS.get(str(c.get("data_type")), [])
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(str(c["field_name"])),
                    dmc.TableTd(
                        dmc.TextInput(
                            value=str(c.get("label") or ""),
                            id={"type": "admin-col-label", "index": c["id"]},
                            **{"aria-label": f"Nhãn cột {c['field_name']}"},
                        )
                    ),
                    dmc.TableTd(str(c.get("data_type"))),
                    dmc.TableTd(
                        dmc.Select(
                            data=[{"label": m, "value": m} for m in masks] + [{"label": "(không)", "value": ""}],
                            value=str(c.get("format_mask") or ""),
                            id={"type": "admin-col-format", "index": c["id"]},
                            clearable=False,
                        )
                        if masks
                        else "—"
                    ),
                    dmc.TableTd(
                        dmc.Select(
                            data=ALIGNMENT_OPTIONS,
                            value=str(c.get("alignment") or "LEFT"),
                            id={"type": "admin-col-align", "index": c["id"]},
                            clearable=False,
                        )
                    ),
                    dmc.TableTd(
                        dmc.NumberInput(
                            value=c.get("width"),
                            id={"type": "admin-col-width", "index": c["id"]},
                            min=40,
                            max=400,
                            placeholder="Tự động",
                        )
                    ),
                    dmc.TableTd(
                        dmc.Checkbox(
                            checked=bool(c.get("web_visible")),
                            id={"type": "admin-col-web", "index": c["id"]},
                            **{"aria-label": f"Hiện web cột {c['field_name']}"},
                        )
                    ),
                    dmc.TableTd(
                        dmc.Checkbox(
                            checked=bool(c.get("excel_visible")),
                            id={"type": "admin-col-excel", "index": c["id"]},
                            **{"aria-label": f"Hiện Excel cột {c['field_name']}"},
                        )
                    ),
                    dmc.TableTd(
                        dmc.Checkbox(
                            checked=bool(c.get("is_total")),
                            id={"type": "admin-col-total", "index": c["id"]},
                            disabled=str(c.get("data_type")) != "NUMBER",
                            **{"aria-label": f"Tổng cột {c['field_name']}"},
                        )
                    ),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.ActionIcon(
                                    DashIconify(icon="lucide:arrow-up", width=16),
                                    id={"type": "admin-col-up", "index": c["id"]},
                                    variant="subtle",
                                    disabled=i == 0,
                                    **{"aria-label": f"Dời cột {c['field_name']} lên"},
                                ),
                                dmc.ActionIcon(
                                    DashIconify(icon="lucide:arrow-down", width=16),
                                    id={"type": "admin-col-down", "index": c["id"]},
                                    variant="subtle",
                                    disabled=i == len(columns) - 1,
                                    **{"aria-label": f"Dời cột {c['field_name']} xuống"},
                                ),
                            ],
                            gap="xs",
                        )
                    ),
                ]
            )
        )
    return dmc.Stack(
        [
            dmc.Title("Cấu hình cột", order=3),
            (
                dmc.ScrollArea(
                    dmc.Table(
                        [
                            dmc.TableThead(
                                dmc.TableTr(
                                    [
                                        dmc.TableTh("Trường DB"),
                                        dmc.TableTh("Nhãn"),
                                        dmc.TableTh("Kiểu"),
                                        dmc.TableTh("Định dạng"),
                                        dmc.TableTh("Canh"),
                                        dmc.TableTh("Rộng"),
                                        dmc.TableTh("Web"),
                                        dmc.TableTh("Excel"),
                                        dmc.TableTh("Tổng"),
                                        dmc.TableTh(""),
                                    ]
                                )
                            ),
                            dmc.TableTbody(rows),
                        ],
                        striped=True,
                        withTableBorder=True,
                    )
                )
                if rows
                else empty_state(
                    "Chưa có cột nào.",
                    "Quay lại bước 2 và phân tích nguồn dữ liệu trước.",
                )
            ),
            dmc.Group(
                [
                    dmc.Button(
                        "Lưu cột",
                        id="admin-col-save-btn",
                        variant="filled",
                    ),
                    dmc.Button(
                        "Làm mới cột",
                        id="admin-col-refresh-btn",
                        variant="subtle",
                    ),
                    dmc.Button(
                        "Khôi phục thứ tự",
                        id="admin-col-restore-btn",
                        variant="subtle",
                    ),
                ]
            ),
            dmc.Divider(label="Xem trước layout", labelPosition="left"),
            _render_columns_preview(columns),
        ],
        gap="sm",
    )


def render_step5(state: dict[str, Any], dry_run: dict[str, Any] | None = None) -> Any:
    """Bước 5: xem trước + dry-run (bám sát preview.html)."""
    ctx = get_current_ctx()
    version = _version_detail(ctx, state.get("version_id")) if ctx else {}
    preview: dict[str, Any] = {"rows": []}
    if ctx and state.get("version_id"):
        res = preview_layout(ctx, int(state["version_id"]))
        if res.ok and isinstance(res.data, dict):
            preview = res.data
    options_by_code: dict[str, list[dict[str, str]]] = {}
    for row in preview.get("rows", []):
        for entry in row.get("params", []):
            if entry.get("control_type") in ("SELECT", "MULTI_SELECT"):
                options_by_code[str(entry["code"])] = []
    result_area: Any = dmc.Text("Chưa chạy dry-run.", size="sm", c="dimmed")
    if dry_run:
        layout_res = preview_result_layout(ctx, int(state["version_id"])) if ctx and state.get("version_id") else None
        layout_data = (
            layout_res.data if layout_res and layout_res.ok and isinstance(layout_res.data, dict) else {"columns": []}
        )
        result_area = dmc.Stack(
            [
                dmc.Text(
                    f"Tổng {dry_run.get('total')} dòng · "
                    f"{dry_run.get('query_ms')} ms · "
                    f"hiển thị tối đa {len(dry_run.get('rows', []))} dòng mẫu",
                    size="sm",
                ),
                render_result_table(layout_data, dry_run.get("rows", [])),
            ],
            gap="sm",
        )

    params_count = len(version.get("params", []))
    lov_count = sum(1 for p in version.get("params", []) if (p.get("lov") or {}).get("lov_type", "NONE") != "NONE")
    cols_count = len([c for c in version.get("columns", []) if c.get("web_visible")])
    if cols_count == 0 and ctx and state.get("version_id"):
        c_res = list_columns(ctx, int(state["version_id"]))
        if c_res.ok and isinstance(c_res.data, list):
            cols_count = len([c for c in c_res.data if c.get("web_visible", True)])

    kpi_cards = dmc.SimpleGrid(
        cols=3,
        spacing="sm",
        mt="md",
        children=[
            dmc.Paper(
                withBorder=True,
                p="xs",
                radius="sm",
                children=[
                    dmc.Text(str(params_count), fw=700, size="lg"),
                    dmc.Text("tham số", size="xs", c="dimmed"),
                ],
            ),
            dmc.Paper(
                withBorder=True,
                p="xs",
                radius="sm",
                children=[
                    dmc.Text(str(lov_count), fw=700, size="lg"),
                    dmc.Text("LOV động/tĩnh", size="xs", c="dimmed"),
                ],
            ),
            dmc.Paper(
                withBorder=True,
                p="xs",
                radius="sm",
                children=[
                    dmc.Text(str(cols_count), fw=700, size="lg"),
                    dmc.Text("cột hiển thị", size="xs", c="dimmed"),
                ],
            ),
        ],
    )

    return dmc.Stack(
        [
            html.Div(
                [
                    dmc.Title("5. Xem trước", order=3, style={"fontSize": "15px", "fontWeight": 600, "margin": 0}),
                    dmc.Alert(
                        "Preview dùng tối đa 100 dòng. Kích hoạt chỉ khi SQL, tham số, LOV và mapping cột đều hợp lệ.",
                        color="orange",
                        variant="light",
                        mt=2,
                        mb="xs",
                    ),
                ]
            ),
            (
                dmc.Alert(
                    "Đã dry-run OK — có thể qua bước Hoàn tất để kích hoạt.",
                    color="green",
                    title="Dry-run OK",
                    variant="light",
                )
                if state.get("dry_run_ok")
                else html.Div()
            ),
            render_param_form(preview, options_by_code),
            dmc.Group(
                [
                    dmc.Button(
                        "Chạy dry-run",
                        id="admin-dryrun-btn",
                        variant="filled",
                        size="sm",
                        leftSection=DashIconify(icon="lucide:play", width=14),
                    ),
                ],
                mt="xs",
            ),
            html.Div(id="admin-dryrun-result", children=result_area, style={"marginTop": "8px"}),
            kpi_cards,
        ],
        gap="xs",
    )


def render_step6(state: dict[str, Any]) -> Any:
    """Bước 6: hoàn tất + kích hoạt (chuẩn Screen16 preview.html)."""
    ctx = get_current_ctx()
    version = _version_detail(ctx, state.get("version_id")) if ctx else {}
    template: dict[str, Any] = {}
    report: dict[str, Any] = {}
    if ctx and state.get("template_id"):
        tpl_res = get_template(ctx, int(state["template_id"]))
        if tpl_res.ok and isinstance(tpl_res.data, dict):
            template = tpl_res.data
            rep_res = get_report(ctx, int(template.get("report_id") or 0))
            if rep_res.ok and isinstance(rep_res.data, dict):
                report = rep_res.data
    status = str(version.get("status") or state.get("version_status") or "DRAFT")
    can_activate = state.get("dry_run_ok") or status == "DRY_RUN_OK"

    if status == "ACTIVE":
        return dmc.Stack(
            [
                dmc.Paper(
                    withBorder=True,
                    radius="sm",
                    p="xl",
                    style={"textAlign": "center", "backgroundColor": "var(--bg-subtle, #f8fafc)"},
                    children=[
                        DashIconify(icon="lucide:check-circle-2", width=48, color="var(--success, #107c10)"),
                        dmc.Title(
                            f"✓ Đã kích hoạt {report.get('code') or ''} / {template.get('name') or template.get('code') or ''} / v{version.get('version_no') or 1}",
                            order=3,
                            mt="sm",
                        ),
                        dmc.Text(
                            "SQL, parameter, LOV và column metadata được snapshot theo version.",
                            size="sm",
                            c="dimmed",
                            mt=4,
                        ),
                        dmc.Badge("ACTIVE", color="green", variant="filled", size="lg", mt="sm"),
                        dmc.Group(
                            [
                                dcc.Link(
                                    dmc.Button("Về Trung tâm báo cáo", variant="filled", size="sm"),
                                    href="/reports",
                                ),
                                dcc.Link(
                                    dmc.Button("Xem báo cáo chi tiết", variant="default", size="sm"),
                                    href=f"/reports/{report.get('id') or state.get('report_id')}",
                                ),
                                dcc.Link(
                                    dmc.Button("Quay lại danh sách", variant="subtle", size="sm"),
                                    href="/report-admin",
                                ),
                            ],
                            justify="center",
                            mt="xl",
                        ),
                    ],
                )
            ],
            gap="sm",
        )

    return dmc.Stack(
        [
            html.Div(
                [
                    dmc.Title("6. Hoàn tất & Kích hoạt", order=3, style={"fontSize": "15px", "fontWeight": 600, "margin": 0}),
                    dmc.Text(
                        "Kiểm tra lại toàn bộ cấu hình trước khi đưa template vào hoạt động.",
                        size="xs",
                        c="dimmed",
                        mt=2,
                        mb="xs",
                    ),
                ]
            ),
            dmc.Text(
                f"Báo cáo: {report.get('code') or '—'} — {report.get('name') or ''}",
                size="sm",
            ),
            dmc.Text(
                f"Template: {template.get('code') or '—'} — version {version.get('version_no') or '—'}",
                size="sm",
            ),
            dmc.Group(
                [
                    dmc.Text("Trạng thái:", size="sm", fw=500),
                    _status_badge(status),
                ],
                gap="xs",
            ),
            dmc.Alert(
                "Kích hoạt đưa version này thành ACTIVE của template (version ACTIVE cũ chuyển ARCHIVED).",
                color="blue",
                title="Kích hoạt template",
                variant="light",
            ),
            dmc.Group(
                [
                    dmc.Button(
                        "Kích hoạt template",
                        id="admin-activate-btn",
                        variant="filled",
                        size="sm",
                        disabled=not can_activate or status == "ACTIVE",
                    ),
                    dcc.Link(
                        dmc.Button(
                            "Về Trung tâm báo cáo",
                            variant="subtle",
                            size="sm",
                        ),
                        href="/reports",
                    ),
                ],
                mt="md",
            ),
            (
                dmc.Text(
                    "Chưa dry-run xong — quay lại bước 5 và chạy dry-run trước.",
                    size="xs",
                    c="dimmed",
                )
                if not can_activate and status != "ACTIVE"
                else html.Div()
            ),
        ],
        gap="xs",
    )


def _render_step_ribbon(current_step: int, max_step: int) -> Any:
    """Ribbon thanh bước chuẩn Fluent Ribbon Screen16 preview.html."""
    items = []
    for i, (label, _desc) in enumerate(STEP_LABELS):
        step_num = i + 1
        is_current = (step_num == current_step)
        is_done = (step_num < current_step)
        is_disabled = (step_num > max_step)

        if is_current:
            num_node = html.Span(
                str(step_num),
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "width": "20px",
                    "height": "20px",
                    "borderRadius": "50%",
                    "fontSize": "11px",
                    "fontWeight": 600,
                    "backgroundColor": "var(--primary, #0f6cbd)",
                    "color": "#fff",
                    "border": "1px solid var(--primary, #0f6cbd)",
                    "flexShrink": 0,
                },
            )
        elif is_done:
            num_node = html.Span(
                "✓",
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "width": "20px",
                    "height": "20px",
                    "borderRadius": "50%",
                    "fontSize": "11px",
                    "fontWeight": 700,
                    "border": "1px solid var(--success, #107c10)",
                    "color": "var(--success, #107c10)",
                    "backgroundColor": "var(--bg-surface, #fff)",
                    "flexShrink": 0,
                },
            )
        else:
            num_node = html.Span(
                str(step_num),
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "width": "20px",
                    "height": "20px",
                    "borderRadius": "50%",
                    "fontSize": "11px",
                    "fontWeight": 600,
                    "border": "1px solid var(--border, #e0e0e0)",
                    "color": "var(--text-muted, #616161)",
                    "backgroundColor": "var(--bg-surface, #fff)",
                    "flexShrink": 0,
                },
            )

        step_style: dict[str, Any] = {
            "flex": "1 1 0",
            "height": "34px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "gap": "6px",
            "padding": "0 8px",
            "border": "none",
            "borderRight": "1px solid var(--border, #e0e0e0)" if i < 5 else "none",
            "fontSize": "12px",
            "whiteSpace": "nowrap",
            "cursor": "pointer" if not is_disabled else "not-allowed",
            "transition": "all 150ms ease",
        }
        if is_current:
            step_style["backgroundColor"] = "var(--primary-subtle, #ebf3fc)"
            step_style["color"] = "var(--text-primary, #242424)"
            step_style["fontWeight"] = "600"
            step_style["boxShadow"] = "inset 0 -2px 0 var(--primary, #0f6cbd)"
        elif is_done:
            step_style["backgroundColor"] = "transparent"
            step_style["color"] = "var(--text-primary, #242424)"
        else:
            step_style["backgroundColor"] = "transparent"
            step_style["color"] = "var(--text-muted, #616161)"
            if is_disabled:
                step_style["opacity"] = 0.5

        items.append(
            html.Button(
                [num_node, html.Span(label, style={"overflow": "hidden", "textOverflow": "ellipsis"})],
                id={"type": "admin-step-btn", "index": step_num},
                style=step_style,
                disabled=is_disabled,
            )
        )

    return html.Div(
        items,
        className="steps",
        id="admin-steps-ribbon",
        style={
            "display": "flex",
            "border": "1px solid var(--border, #e0e0e0)",
            "borderRadius": "6px",
            "backgroundColor": "var(--bg-surface, #fff)",
            "overflow": "hidden",
            "marginBottom": "12px",
            "flexWrap": "nowrap",
            "flexShrink": 0,
        },
    )


def _render_wizard_footer(step: int, state: dict[str, Any]) -> Any:
    """Footer điều hướng cố định chân trang chuẩn Screen13 /batch-runs/11 (.wfoot)."""
    if step == 1:
        next_btn = dmc.Button(
            "Tiếp theo",
            id="admin-s1-save-btn",
            rightSection=DashIconify(icon="lucide:arrow-right", width=14),
            color="primary",
            size="xs",
            radius="xl",
            style={
                "fontWeight": 600,
                "height": "30px",
                "padding": "0 16px",
                "boxShadow": "0 1px 3px rgba(0, 120, 212, 0.25)",
            },
        )
    elif step == 6:
        next_btn = dmc.Anchor(
            dmc.Button(
                "Về Trung tâm báo cáo",
                rightSection=DashIconify(icon="lucide:arrow-right", width=14),
                color="primary",
                size="xs",
                radius="xl",
                style={
                    "fontWeight": 600,
                    "height": "30px",
                    "padding": "0 16px",
                    "boxShadow": "0 1px 3px rgba(0, 120, 212, 0.25)",
                },
            ),
            href="/reports",
            underline=False,
        )
    else:
        next_btn = dmc.Button(
            "Tiếp theo",
            id="admin-next-btn",
            rightSection=DashIconify(icon="lucide:arrow-right", width=14),
            color="primary",
            size="xs",
            radius="xl",
            style={
                "fontWeight": 600,
                "height": "30px",
                "padding": "0 16px",
                "boxShadow": "0 1px 3px rgba(0, 120, 212, 0.25)",
            },
        )

    prev_btn = dmc.Button(
        "Quay lại",
        id="admin-prev-btn",
        leftSection=DashIconify(icon="lucide:arrow-left", width=14),
        variant="subtle",
        color="gray",
        size="xs",
        radius="xl",
        disabled=step <= 1 or step == 6,
        style={
            "fontWeight": 500,
            "height": "30px",
            "padding": "0 14px",
            "color": "var(--ink, #1E1E1E)",
            "display": "none" if step == 6 else "inline-flex",
        },
    )

    capsule = dmc.Paper(
        dmc.Group(
            [
                prev_btn,
                next_btn,
            ],
            gap="xs",
            align="center",
        ),
        radius="xl",
        p=3,
        withBorder=True,
        style={
            "backgroundColor": "#FFFFFF",
            "borderColor": "var(--line, #E0E0E0)",
            "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.05)",
        },
    )

    hint_text = ""
    if step == 2 and not state.get("analyzed"):
        hint_text = "Cần phân tích SQL trước khi tiếp tục"
    elif step == 5 and not state.get("dry_run_ok"):
        hint_text = "Cần chạy dry-run thành công trước khi hoàn tất"

    return dmc.Group(
        [
            html.Span(
                hint_text,
                id="admin-wmsg",
                style={"fontSize": "11px", "color": "var(--ink-soft, #616161)", "fontWeight": 500},
            ),
            capsule,
        ],
        justify="space-between",
        align="center",
        className="wfoot",
        style={
            "flexShrink": 0,
            "height": "48px",
            "padding": "0 20px",
            "borderTop": "1px solid var(--line, #E0E0E0)",
            "backgroundColor": "#FFFFFF",
            "display": "flex",
            "zIndex": 10,
        },
    )


def render_step_content(step: int, state: dict[str, Any], dry_run: dict[str, Any] | None = None) -> Any:
    """Điều hướng hiển thị nội dung từng bước của wizard."""
    if step == 1:
        return render_step1(state)
    if step == 2:
        return render_step2(state)
    if step == 3:
        return render_step3(state)
    if step == 4:
        return render_step4(state)
    if step == 5:
        return render_step5(state, dry_run)
    if step == 6:
        return render_step6(state)
    return html.Div("Bước không hợp lệ")


def render_wizard(state: dict[str, Any], dry_run: dict[str, Any] | None = None) -> Any:
    """Khung wizard chuẩn 3 phần như /batch-runs/11: Fixed Top, Scrollable Middle, Fixed Footer."""
    step = int(state.get("step") or 1)
    max_step = int(state.get("max_step") or 1)

    top_bar = dmc.Box(
        [
            dmc.Group(
                [
                    dmc.Breadcrumbs(
                        [
                            dmc.Text("ReconHub", size="xs", c="dimmed", fw=500),
                            dmc.Anchor("Quản trị báo cáo", href="/report-admin", size="xs", c="dimmed", underline=False),
                        ],
                        separator="/",
                        mb=4,
                    ),
                    dmc.Anchor(
                        dmc.Button(
                            "Đóng",
                            variant="default",
                            size="xs",
                            style={"fontWeight": 600, "height": "28px"},
                        ),
                        href="/report-admin",
                        underline=False,
                    ),
                ],
                justify="space-between",
                align="center",
            ),
            dmc.Group(
                [
                    dmc.Title("Đăng ký Report Template", order=3, size=18, fw=600, style={"lineHeight": 1.3}),
                    dmc.Text(
                        "SQL, tham số, LOV và cột hiển thị đều cấu hình động.",
                        size="xs",
                        c="dimmed",
                        style={"overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
                    ),
                ],
                gap="xs",
                align="baseline",
                mb="xs",
            ),
            _render_step_ribbon(step, max_step),
            html.Div(
                dmc.Stepper(
                    id="admin-stepper",
                    active=step - 1,
                    children=[dmc.StepperStep(label=label, description=desc) for label, desc in STEP_LABELS],
                ),
                style={"display": "none"},
            ),
        ],
        style={
            "flexShrink": 0,
            "padding": "12px 20px 10px 20px",
            "borderBottom": "1px solid var(--line, #E0E0E0)",
            "backgroundColor": "var(--surface, #FFFFFF)",
        },
    )

    middle_body = html.Div(
        [
            dmc.Paper(
                children=[
                    html.Div(
                        id="admin-step-content",
                        children=render_step_content(step, state, dry_run),
                        className="wbody",
                        style={"padding": "14px 18px"},
                    ),
                ],
                withBorder=True,
                radius="sm",
                shadow="xs",
                style={
                    "backgroundColor": "var(--bg-surface, #fff)",
                    "border": "1px solid var(--line, #E0E0E0)",
                    "maxWidth": 1250,
                    "margin": "0 auto",
                    "width": "100%",
                },
            )
        ],
        style={
            "flex": "1 1 0%",
            "minHeight": 0,
            "overflowY": "auto",
            "padding": "16px 20px",
            "backgroundColor": "var(--surface-2, #F8F9FA)",
        },
    )

    bottom_footer = _render_wizard_footer(step, state)

    return html.Div(
        [
            top_bar,
            middle_body,
            bottom_footer,
        ],
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "backgroundColor": "#FFFFFF",
        },
    )


# ─── Handlers (hàm thuần, test được; callback bọc ngoài) ───────────────────


_FIELD_LABELS: dict[str, str] = {
    "code": "Mã",
    "name": "Tên",
    "owner": "Chủ sở hữu",
    "category_code": "Nhóm báo cáo",
    "description": "Mô tả",
    "display_order": "Thứ tự",
    "timeout_sec": "Timeout",
    "preview_max_rows": "Tối đa dòng xem trước",
    "export_max_rows": "Tối đa dòng export",
    "data_source_id": "Data Source",
    "source_type": "Loại nguồn",
    "sql_text": "Câu lệnh SQL",
    "source_owner": "Chủ sở hữu nguồn",
    "source_object": "Đối tượng nguồn",
}


def _field_error_text(err: dict[str, Any]) -> str:
    """Một dòng lỗi theo trường, tiếng Việt (details.errors của service)."""
    raw_field = str(err.get("field", "") or "")
    field = _FIELD_LABELS.get(raw_field, raw_field or "Dữ liệu")
    err_type = str(err.get("type", ""))
    if err_type == "string_pattern_mismatch":
        return f"{field}: chỉ gồm chữ hoa, số và dấu gạch dưới, bắt đầu bằng chữ hoa."
    if err_type == "string_too_short":
        return f"{field}: không được để trống."
    if err_type == "string_too_long":
        return f"{field}: quá dài."
    if err_type == "missing":
        return f"{field}: bắt buộc nhập."
    if err_type in ("greater_than_equal", "greater_than"):
        return f"{field}: giá trị quá nhỏ."
    if err_type in ("less_than_equal", "less_than"):
        return f"{field}: giá trị quá lớn."
    msg = str(err.get("message", "") or "")
    return f"{field}: {msg}" if msg else f"{field}: không hợp lệ."


def _err_alert(res: Any) -> Any:
    details = getattr(res, "details", None)
    errors = details.get("errors") if isinstance(details, dict) else None
    if errors:
        lines = [_field_error_text(e) for e in errors if isinstance(e, dict)]
        if lines:
            return alert_box(
                res.message or "Có lỗi xảy ra.",
                [dmc.Text(line, size="sm") for line in lines],
                tone="crit",
            )
    return alert_box(res.message or "Có lỗi xảy ra.", tone="crit")


def handle_save_step1(
    n_clicks: int | None,
    state: dict[str, Any],
    report_code: str | None,
    report_name: str | None,
    category_code: str | None,
    owner: str | None,
    description: str | None,
    is_visible: bool | None,
    default_favorite: bool | None,
    tpl_code: str | None,
    tpl_name: str | None,
    display_order: int | None,
    timeout_sec: int | None,
    preview_max_rows: int | None,
    export_max_rows: int | None,
) -> tuple[dict[str, Any], Any]:
    """Lưu bước 1: tạo mới report+template, hoặc sửa DRAFT hiện có."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    state = dict(state)
    editing = bool(state.get("report_id") and state.get("template_id"))
    try:
        if not editing:
            rep_res = create_report(
                ctx,
                {
                    "code": (report_code or "").strip(),
                    "name": (report_name or "").strip(),
                    "category_code": category_code or "FINANCE",
                    "owner": (owner or "").strip(),
                    "description": (description or "").strip() or None,
                    "default_favorite": bool(default_favorite),
                    "is_visible": bool(is_visible) if is_visible is not None else True,
                },
            )
            if not rep_res.ok or not isinstance(rep_res.data, dict):
                return state, _err_alert(rep_res)
            report_id = int(rep_res.data["id"])
            tpl_res = create_template(
                ctx,
                report_id,
                {
                    "code": (tpl_code or "").strip(),
                    "name": (tpl_name or "").strip(),
                    "display_order": int(display_order or 10),
                    "timeout_sec": int(timeout_sec or 300),
                    "preview_max_rows": int(preview_max_rows or 100),
                    "export_max_rows": int(export_max_rows or 1000000),
                },
            )
            if not tpl_res.ok or not isinstance(tpl_res.data, dict):
                return state, _err_alert(tpl_res)
            template_id = int(tpl_res.data["id"])
            versions = tpl_res.data.get("versions") or []
            version_id = int(versions[0]["id"]) if versions else None
            state.update(
                {
                    "report_id": report_id,
                    "template_id": template_id,
                    "version_id": version_id,
                    "version_status": "DRAFT",
                    "step": 2,
                    "max_step": 2,
                    "analyzed": False,
                    "dry_run_ok": False,
                }
            )
            return state, alert_box("Đã lưu thông tin.", tone="ok")
        report_id = int(state["report_id"])
        template_id = int(state["template_id"])
        rep_res = update_report(
            ctx,
            report_id,
            {
                "name": (report_name or "").strip(),
                "category_code": category_code or "FINANCE",
                "owner": (owner or "").strip(),
                "description": (description or "").strip() or None,
                "default_favorite": bool(default_favorite),
                "is_visible": bool(is_visible) if is_visible is not None else True,
            },
        )
        if not rep_res.ok:
            return state, _err_alert(rep_res)
        tpl_res = update_template(
            ctx,
            template_id,
            {
                "name": (tpl_name or "").strip(),
                "display_order": int(display_order or 10),
            },
        )
        if not tpl_res.ok:
            return state, _err_alert(tpl_res)
        if state.get("version_id"):
            update_version_source(
                ctx,
                int(state["version_id"]),
                {
                    "timeout_sec": int(timeout_sec or 300),
                    "preview_max_rows": int(preview_max_rows or 100),
                    "export_max_rows": int(export_max_rows or 1000000),
                },
            )
        state["step"] = 2
        state["max_step"] = max(int(state.get("max_step") or 1), 2)
        return state, alert_box("Đã lưu thông tin.", tone="ok")
    except Exception as exc:  # noqa: BLE001 - service đã bọc, phòng thủ thêm
        return state, alert_box(f"Lưu bước 1 lỗi: {exc}", tone="crit")


def handle_analyze_sql(
    n_clicks: int | None,
    state: dict[str, Any],
    sql_text: str | None,
) -> tuple[dict[str, Any], Any]:
    """Bước 2 CUSTOM_SQL: validate SQL → lưu SQL → analyze → apply diff."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    state = dict(state)
    version_id = int(state["version_id"])
    detail = _version_detail(ctx, version_id)
    ds_id = detail.get("data_source_id")
    if not ds_id:
        return state, alert_box(
            "Chưa chọn Data Source.",
            "Chọn Data Source ở bước 2 trước.",
            tone="crit",
        )
    sql = (sql_text or "").strip()
    if not sql:
        return state, alert_box("Chưa nhập câu lệnh SQL.", tone="crit")
    val_res = validate_version_sql(ctx, sql, int(ds_id))
    if not val_res.ok:
        return state, _err_alert(val_res)
    upd_res = update_version_source(ctx, version_id, {"sql_text": sql})
    if not upd_res.ok:
        return state, _err_alert(upd_res)
    diff_res = analyze_version_source(ctx, version_id)
    if not diff_res.ok or not isinstance(diff_res.data, dict):
        return state, _err_alert(diff_res)
    apply_res = apply_source_diff(ctx, version_id, diff_res.data)
    if not apply_res.ok:
        return state, _err_alert(apply_res)
    diff = diff_res.data
    state["analyzed"] = True
    state["max_step"] = max(int(state.get("max_step") or 2), 3)
    return state, alert_box(
        "Đã phân tích nguồn dữ liệu.",
        f"Thêm {len(diff.get('added', []))} cột · "
        f"Mất {len(diff.get('removed', []))} cột · "
        f"Đổi kiểu {len(diff.get('type_changed', []))} cột.",
        tone="ok",
    )


def handle_analyze_object(
    n_clicks: int | None,
    state: dict[str, Any],
    data_source_id: int | None,
    source_type: str | None,
    source_owner: str | None,
    source_object: str | None,
) -> tuple[dict[str, Any], Any]:
    """Bước 2 VIEW/TABLE: lưu nguồn → analyze → apply diff."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    state = dict(state)
    version_id = int(state["version_id"])
    if not data_source_id:
        return state, alert_box("Chưa chọn Data Source.", tone="crit")
    upd_res = update_version_source(
        ctx,
        version_id,
        {
            "data_source_id": int(data_source_id),
            "source_type": source_type or "VIEW",
            "source_owner": (source_owner or "").strip() or None,
            "source_object": (source_object or "").strip() or None,
        },
    )
    if not upd_res.ok:
        return state, _err_alert(upd_res)
    diff_res = analyze_version_source(ctx, version_id)
    if not diff_res.ok or not isinstance(diff_res.data, dict):
        return state, _err_alert(diff_res)
    apply_res = apply_source_diff(ctx, version_id, diff_res.data)
    if not apply_res.ok:
        return state, _err_alert(apply_res)
    diff = diff_res.data
    state["analyzed"] = True
    state["max_step"] = max(int(state.get("max_step") or 2), 3)
    return state, alert_box(
        "Đã phân tích nguồn dữ liệu.",
        f"Thêm {len(diff.get('added', []))} cột · Mất {len(diff.get('removed', []))} cột.",
        tone="ok",
    )


def handle_param_save(
    n_clicks: int | None,
    state: dict[str, Any],
    param_id: int | None,
    code: str | None,
    label: str | None,
    data_type: str | None,
    control_type: str | None,
    required: bool | None,
    default_type: str | None,
    default_value: str | None,
    display_row: int | None,
    display_order: int | None,
    grid_span: int | None,
    filter_column: str | None,
    filter_operator: str | None,
    is_visible: bool | None,
    lov_type: str | None,
    lov_sql: str | None,
    lov_lookup_type: str | None,
    lov_static_text: str | None,
) -> tuple[dict[str, Any] | None, Any]:
    """Bước 3: tạo mới hoặc sửa tham số (kèm LOV)."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    version_id = int(state["version_id"])
    detail = _version_detail(ctx, version_id)
    lov = _lov_payload(
        lov_type,
        lov_sql,
        lov_lookup_type,
        lov_static_text,
        data_source_id=detail.get("data_source_id"),
    )
    payload = {
        "code": (code or "").strip(),
        "label": (label or "").strip(),
        "data_type": data_type or "STRING",
        "control_type": control_type or "TEXT",
        "required": bool(required),
        "default_type": default_type or "NONE",
        "default_value": (default_value or "").strip() or None,
        "display_row": int(display_row or 1),
        "display_order": int(display_order or 10),
        "grid_span": int(grid_span or 6),
        "filter_column": (filter_column or "").strip() or None,
        "filter_operator": filter_operator or None,
        "is_visible": bool(is_visible) if is_visible is not None else True,
        "lov": lov,
    }
    if param_id:
        res = update_param(ctx, version_id, int(param_id), payload)
    else:
        res = create_param(ctx, version_id, payload)
    if not res.ok or not isinstance(res.data, dict):
        return None, _err_alert(res)
    return res.data, alert_box("Đã lưu tham số.", tone="ok")


def handle_param_delete(
    n_clicks: int | None,
    state: dict[str, Any],
    param_id: int | None,
) -> tuple[bool, Any]:
    """Bước 3: xóa tham số."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id") or not param_id:
        raise PreventUpdate
    res = delete_param(ctx, int(state["version_id"]), int(param_id))
    if not res.ok:
        return False, _err_alert(res)
    return True, alert_box("Đã xóa tham số.", tone="ok")


def _layout_position(ctx: Ctx, version_id: int, param_id: int) -> tuple[int, int, list[dict[str, Any]]] | None:
    """(row, index, params của row) của một param trong layout hiện tại."""
    res = preview_layout(ctx, version_id)
    if not res.ok or not isinstance(res.data, dict):
        return None
    for row in res.data.get("rows", []):
        params = row.get("params", [])
        for idx, entry in enumerate(params):
            if int(entry.get("id") or 0) == int(param_id):
                return int(row.get("row", 1)), idx, params
    return None


def handle_param_move(
    n_clicks: int | None,
    state: dict[str, Any],
    param_id: int | None,
    direction: str,
) -> tuple[bool, Any]:
    """Bước 3: dời tham số lên/xuống (Q3 — nút thay cho kéo-thả)."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id") or not param_id:
        raise PreventUpdate
    version_id = int(state["version_id"])
    pos = _layout_position(ctx, version_id, int(param_id))
    if pos is None:
        return False, alert_box("Không tìm thấy tham số.", tone="crit")
    row_no, idx, params = pos
    layout_res = preview_layout(ctx, version_id)
    rows = layout_res.data.get("rows", []) if layout_res.ok and isinstance(layout_res.data, dict) else []
    if direction == "up":
        if idx > 0:
            to_row, to_index = row_no, idx - 1
        elif row_no > 1:
            prev = next((r for r in rows if int(r.get("row", 0)) == row_no - 1), None)
            if prev is None:
                return False, alert_box("Đã ở đầu danh sách.", tone="warn")
            to_row, to_index = row_no - 1, len(prev.get("params", []))
        else:
            return False, alert_box("Đã ở đầu danh sách.", tone="warn")
    else:
        if idx < len(params) - 1:
            to_row, to_index = row_no, idx + 1
        else:
            nxt = next((r for r in rows if int(r.get("row", 0)) == row_no + 1), None)
            if nxt is None:
                return False, alert_box("Đã ở cuối danh sách.", tone="warn")
            to_row, to_index = row_no + 1, 0
    res = move_param(ctx, version_id, int(param_id), to_row, to_index)
    if not res.ok:
        return False, _err_alert(res)
    return True, None


def handle_auto_layout(
    n_clicks: int | None,
    state: dict[str, Any],
) -> tuple[bool, Any]:
    """Bước 3: tự sắp xếp layout 12 cột."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    res = auto_layout(ctx, int(state["version_id"]))
    if not res.ok:
        return False, _err_alert(res)
    return True, alert_box("Đã tự sắp xếp layout.", tone="ok")


def handle_column_save(
    n_clicks: int | None,
    state: dict[str, Any],
    rows: list[dict[str, Any]] | None,
) -> tuple[bool, Any]:
    """Bước 4: lưu cả grid cột một lần (update_columns bulk)."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    res = update_columns(ctx, int(state["version_id"]), rows or [])
    if not res.ok:
        return False, _err_alert(res)
    return True, alert_box("Đã lưu cấu hình cột.", tone="ok")


def handle_column_move(
    n_clicks: int | None,
    state: dict[str, Any],
    column_id: int | None,
    direction: str,
) -> tuple[bool, Any]:
    """Bước 4: dời cột lên/xuống trong grid."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id") or not column_id:
        raise PreventUpdate
    version_id = int(state["version_id"])
    res = list_columns(ctx, version_id)
    if not res.ok or not isinstance(res.data, list):
        return False, _err_alert(res)
    ids = [int(c["id"]) for c in res.data]
    idx = ids.index(int(column_id)) if int(column_id) in ids else -1
    if idx < 0:
        return False, alert_box("Không tìm thấy cột.", tone="crit")
    if direction == "up":
        if idx == 0:
            return False, alert_box("Đã ở đầu danh sách.", tone="warn")
        to_index = idx - 1
    else:
        if idx == len(ids) - 1:
            return False, alert_box("Đã ở cuối danh sách.", tone="warn")
        to_index = idx + 1
    move_res = move_column(ctx, version_id, int(column_id), to_index)
    if not move_res.ok:
        return False, _err_alert(move_res)
    return True, None


def handle_refresh_columns(
    n_clicks: int | None,
    state: dict[str, Any],
) -> tuple[bool, Any]:
    """Bước 4: làm mới cột từ nguồn (analyze + apply)."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    res = refresh_columns(ctx, int(state["version_id"]))
    if not res.ok:
        return False, _err_alert(res)
    return True, alert_box("Đã làm mới cột từ nguồn.", tone="ok")


def handle_restore_order(
    n_clicks: int | None,
    state: dict[str, Any],
) -> tuple[bool, Any]:
    """Bước 4: khôi phục thứ tự cột theo nguồn."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    res = restore_column_order(ctx, int(state["version_id"]))
    if not res.ok:
        return False, _err_alert(res)
    return True, alert_box("Đã khôi phục thứ tự cột.", tone="ok")


def handle_dry_run(
    n_clicks: int | None,
    state: dict[str, Any],
    values: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, Any]:
    """Bước 5: chạy dry-run version DRAFT."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    state = dict(state)
    res = dry_run_version(ctx, int(state["version_id"]), values or {})
    if not res.ok or not isinstance(res.data, dict):
        state["dry_run_ok"] = False
        return state, None, _err_alert(res)
    state["dry_run_ok"] = True
    state["version_status"] = "DRY_RUN_OK"
    state["max_step"] = max(int(state.get("max_step") or 5), 6)
    return state, res.data, None


def handle_activate(
    n_clicks: int | None,
    state: dict[str, Any],
) -> tuple[dict[str, Any], Any]:
    """Bước 6: kích hoạt version (chỉ sau dry-run OK)."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    state = dict(state)
    if not state.get("dry_run_ok"):
        detail = _version_detail(ctx, int(state["version_id"]))
        if str(detail.get("status")) != "DRY_RUN_OK":
            return state, alert_box(
                "Chưa dry-run xong.",
                "Quay lại bước 5 và chạy dry-run trước khi kích hoạt.",
                tone="crit",
            )
    res = activate_version(ctx, int(state["version_id"]))
    if not res.ok:
        return state, _err_alert(res)
    state["version_status"] = "ACTIVE"
    return state, None


def handle_clone(
    n_clicks: int | None,
    version_id: int | None,
) -> tuple[dict[str, Any] | None, Any]:
    """Clone một version sang DRAFT mới rồi mở wizard."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not version_id:
        raise PreventUpdate
    res = clone_version(ctx, int(version_id))
    if not res.ok or not isinstance(res.data, dict):
        return None, _err_alert(res)
    new_version = res.data
    tpl_res = get_template(ctx, int(new_version["template_id"]))
    if not tpl_res.ok or not isinstance(tpl_res.data, dict):
        return None, alert_box("Không tải được template sau khi clone.", tone="crit")
    state = _state_from_version(ctx, int(new_version["template_id"]), int(new_version["id"]))
    if state is None:
        return None, alert_box("Không tải được version sau khi clone.", tone="crit")
    state["report_id"] = int(tpl_res.data["report_id"])
    return state, alert_box("Đã clone sang version DRAFT mới.", tone="ok")


def handle_archive_version(
    n_clicks: int | None,
    state: dict[str, Any],
) -> tuple[bool, Any]:
    """Lưu trữ một version."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not state.get("version_id"):
        raise PreventUpdate
    res = archive_version(ctx, int(state["version_id"]))
    if not res.ok:
        return False, _err_alert(res)
    return True, alert_box("Đã lưu trữ version.", tone="ok")


def handle_open_edit(
    n_clicks: int | None,
    template_id: int | None,
) -> tuple[dict[str, Any] | None, Any]:
    """Mở wizard sửa template ở version DRAFT mới nhất."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None or not template_id:
        raise PreventUpdate
    draft = _draft_version_of(ctx, int(template_id))
    if draft is None:
        return None, alert_box(
            "Template không có version DRAFT.",
            "Hãy Clone một version để sửa.",
            tone="crit",
        )
    tpl_res = get_template(ctx, int(template_id))
    if not tpl_res.ok or not isinstance(tpl_res.data, dict):
        return None, _err_alert(tpl_res)
    state = _state_from_version(ctx, int(template_id), int(draft["id"]))
    if state is None:
        return None, alert_box("Không tải được version.", tone="crit")
    state["report_id"] = int(tpl_res.data["report_id"])
    return state, None


def handle_next_step(
    n_clicks: int | None,
    state: dict[str, Any],
) -> tuple[dict[str, Any], Any]:
    """Nút Tiếp: kiểm tra điều kiện qua bước rồi tăng step."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    state = dict(state)
    step = int(state.get("step") or 1)
    if step >= 6:
        return state, None
    if step == 1:
        if not (state.get("report_id") and state.get("template_id") and state.get("version_id")):
            return state, alert_box(
                "Lưu bước 1 trước.",
                "Bấm “Lưu và tiếp tục” để tạo báo cáo và template.",
                tone="crit",
            )
    elif step == 2:
        if not state.get("analyzed"):
            return state, alert_box(
                "Chưa phân tích nguồn dữ liệu.",
                "Bấm “Phân tích SQL” (hoặc “Phân tích nguồn”) ở bước 2 trước.",
                tone="crit",
            )
    elif step == 3:
        if state.get("version_id"):
            val_res = validate_layout(ctx, int(state["version_id"]))
            if val_res.ok and isinstance(val_res.data, dict):
                violations = val_res.data.get("violations", [])
                if violations:
                    return state, alert_box(
                        "Layout vượt 12 cột.",
                        "Sửa lại layout tham số trước khi qua bước sau.",
                        tone="crit",
                    )
    elif step == 4:
        if state.get("version_id"):
            cols_res = list_columns(ctx, int(state["version_id"]))
            cols = cols_res.data if cols_res.ok and isinstance(cols_res.data, list) else []
            if not cols:
                return state, alert_box(
                    "Chưa có cột nào.",
                    "Quay lại bước 2 và phân tích nguồn dữ liệu trước.",
                    tone="crit",
                )
    elif step == 5:
        if not state.get("dry_run_ok"):
            return state, alert_box(
                "Chưa dry-run xong.",
                "Bấm “Chạy dry-run” ở bước 5 trước khi qua bước sau.",
                tone="crit",
            )
    state["step"] = step + 1
    state["max_step"] = max(int(state.get("max_step") or step), step + 1)
    return state, None


def handle_step_click(
    active_or_clicks: int | None,
    state: dict[str, Any],
    step: int | None = None,
) -> tuple[dict[str, Any], Any]:
    """Bấm Stepper: chỉ quay lại bước đã qua (guard n_clicks).

    Callback Dash truyền `active` (0-based) làm arg đầu, step=None;
    test truyền (n_clicks, state, step 1-based).
    """
    if active_or_clicks is None:
        raise PreventUpdate
    target = int(step) if step is not None else int(active_or_clicks) + 1
    state = dict(state)
    # Stepper bị dựng lại mỗi khi wizard render (kể cả khi step không đổi,
    # ví dụ sau khi Lưu bước 1 lỗi): `active` phát lại đúng bước hiện tại.
    # Không làm gì cả — PreventUpdate để không ghi đè alert vừa hiện
    # (callback trước đó trả alert qua output admin-alert; trả (state, None)
    # ở đây sẽ xóa alert đó và người dùng thấy như bấm không có tác dụng).
    if target == int(state.get("step") or 1):
        raise PreventUpdate
    if target <= int(state.get("max_step") or 1):
        state["step"] = target
        return state, None
    return state, alert_box(
        "Chưa tới được bước này.",
        "Hoàn thành các bước trước rồi mới qua.",
        tone="warn",
    )


# ─── Callbacks ─────────────────────────────────────────────────────────────


def _bump(state: dict[str, Any]) -> dict[str, Any]:
    """Tăng rev để wizard render lại sau thao tác không đổi step."""
    state = dict(state)
    state["rev"] = int(state.get("rev") or 0) + 1
    return state


def _state_or_no_update(old_state: dict[str, Any] | None, new_state: dict[str, Any], alert: Any) -> tuple[Any, Any]:
    """Giữ nguyên state-store khi thao tác lỗi (state không đổi).

    Tránh wizard render lại và xóa dữ liệu vừa nhập: render_step* dựng lại
    form từ state/DB nên input chưa lưu sẽ mất. Thao tác thành công luôn
    đổi state (đổi step, analyzed, _bump...) nên vẫn render lại bình
    thường.
    """
    if new_state == old_state:
        return dash.no_update, alert
    return new_state, alert


@callback(
    Output("admin-state-store", "data"),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-location", "href"),
    State("admin-state-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def handle_location(href: str | None, state: dict[str, Any] | None) -> tuple[dict[str, Any], Any]:
    """Mở wizard từ pathname (/report-admin/new, /report-admin/<id>) hoặc query: ?new=1, ?template=<id>, ?clone=<version_id>."""
    if not href:
        raise PreventUpdate
    parsed = urlparse(href)
    pathname = parsed.path.rstrip("/")
    qs = parse_qs(parsed.query)
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate

    if pathname.endswith("/new") or qs.get("new"):
        return _state_or_no_update(state, _fresh_state(), None)

    tpl_id_val: int | None = None
    parts = pathname.split("/")
    if len(parts) >= 3 and parts[-2] == "report-admin" and parts[-1].isdigit():
        tpl_id_val = int(parts[-1])
    elif qs.get("template"):
        try:
            tpl_id_val = int(qs["template"][0])
        except (TypeError, ValueError):
            tpl_id_val = None

    if tpl_id_val is not None:
        new_state, alert = handle_open_edit(1, tpl_id_val)
        if new_state is None:
            return _state_or_no_update(state, {"mode": "list"}, alert)
        return _state_or_no_update(state, new_state, alert)

    if qs.get("clone"):
        try:
            version_id = int(qs["clone"][0])
        except (TypeError, ValueError):
            raise PreventUpdate from None
        new_state, alert = handle_clone(1, version_id)
        if new_state is None:
            return _state_or_no_update(state, {"mode": "list"}, alert)
        return _state_or_no_update(state, new_state, alert)

    if pathname.endswith("/report-admin") and not (qs.get("new") or qs.get("template") or qs.get("clone")):
        current = state or {"mode": "list"}
        if current.get("mode") == "wizard":
            return {"mode": "list"}, None

    raise PreventUpdate


@callback(
    Output("admin-wizard-container", "children"),
    Input("admin-state-store", "data"),
    State("admin-dryrun-store", "data"),
)
def handle_wizard_render(
    state: dict[str, Any] | None,
    dry_run: dict[str, Any] | None,
) -> Any:
    """Render wizard từ state-store."""
    if not state or state.get("mode") != "wizard":
        return []
    return render_wizard(state, dry_run)


@callback(
    Output("admin-list-container", "style"),
    Output("admin-wizard-container", "style"),
    Input("admin-state-store", "data"),
)
def handle_mode_display(state: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ẩn/hiện danh sách và wizard theo mode."""
    if state and state.get("mode") == "wizard":
        return {"display": "none"}, {
            "display": "flex",
            "flexDirection": "column",
            "flex": "1 1 0%",
            "minHeight": 0,
            "overflow": "hidden",
            "height": "100%",
        }
    return {
        "display": "flex",
        "flexDirection": "column",
        "flex": "1 1 0%",
        "minHeight": 0,
        "overflow": "hidden",
        "padding": "8px 12px",
        "gap": "6px",
        "height": "100%",
    }, {"display": "none"}


@callback(
    Output("admin-table-container", "children"),
    Output("admin-count-text", "children"),
    Input("admin-reports-store", "data"),
    Input("admin-filter-search", "value"),
    Input("admin-filter-status", "value"),
    Input("admin-filter-category", "value"),
    Input("admin-pagination", "value"),
)
def handle_admin_filter(
    reports: list[dict[str, Any]] | None,
    search: str | None,
    status: str | None,
    category: str | None,
    page: int | None = 1,
) -> tuple[Any, str]:
    """Lọc danh sách báo cáo theo tìm kiếm, trạng thái và nhóm, kèm phân trang."""
    if reports is None:
        return render_report_list(None, loading=True), ""
    search_term = (search or "").strip()
    stat_val = "" if not status or status.upper() == "ALL" else status
    cat_val = "" if not category or category.upper() == "ALL" else category

    # Nếu đổi filter -> về trang 1; nếu bấm pagination -> dùng trang được chọn
    try:
        triggered_id = dash.callback_context.triggered_id
    except Exception:
        triggered_id = None
    current_page = 1 if triggered_id != "admin-pagination" else (page or 1)

    content = render_report_list(
        reports,
        search_term=search_term,
        status_filter=stat_val,
        category_filter=cat_val,
        page=current_page,
        page_size=10,
    )
    cnt = 0
    st = search_term.lower()
    for rep in reports:
        cat = str(rep.get("category_code") or "")
        if cat_val and cat != cat_val:
            continue
        tpls = rep.get("templates") or []
        for tpl in (tpls if tpls else [{}]):
            vers = tpl.get("versions") or []
            for ver in (vers if vers else [{}]):
                v_stat = str(ver.get("status") or "DRAFT")
                if stat_val and v_stat != stat_val:
                    continue
                if st:
                    hay = f"{rep.get('code','')} {rep.get('name','')} {tpl.get('code','')} {tpl.get('name','')}".lower()
                    if st not in hay:
                        continue
                cnt += 1
    return content, f"{cnt} mục"


@callback(
    Output("admin-reports-store", "data"),
    Input("admin-refresh-btn", "n_clicks"),
    prevent_initial_call=True,
)
def handle_admin_refresh(n_clicks: int | None) -> list[dict[str, Any]]:
    """Làm mới danh sách từ DB."""
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    return _load_reports_with_templates(ctx)


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-stepper", "active"),
    Input({"type": "admin-step-btn", "index": dash.ALL}, "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_stepper_click(
    active: int | None,
    ribbon_clicks: list[int | None] | None,
    state: dict[str, Any] | None,
) -> tuple[dict[str, Any], Any]:
    """Bấm Stepper hoặc Ribbon để chuyển/quay lại bước đã qua."""
    if not state:
        raise PreventUpdate
    ctx_trig = dash.callback_context.triggered_id
    if isinstance(ctx_trig, dict) and "index" in ctx_trig:
        if not ribbon_clicks or not any(ribbon_clicks):
            raise PreventUpdate
        target = int(ctx_trig["index"])
        return handle_step_click(target, state, step=target)
    if active is None:
        raise PreventUpdate
    return handle_step_click(active, state)


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-prev-btn", "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_prev(n_clicks: int | None, state: dict[str, Any] | None) -> tuple[dict[str, Any], Any]:
    """Nút Quay lại."""
    if not n_clicks or not state:
        raise PreventUpdate
    old_state = state
    state = dict(state)
    state["step"] = max(1, int(state.get("step") or 1) - 1)
    return _state_or_no_update(old_state, state, None)


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-next-btn", "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_next(n_clicks: int | None, state: dict[str, Any] | None) -> tuple[dict[str, Any], Any]:
    """Nút Tiếp (có guard từng bước)."""
    if not n_clicks or not state:
        raise PreventUpdate
    new_state, alert = handle_next_step(n_clicks, state)
    return _state_or_no_update(state, new_state, alert)


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-s1-save-btn", "n_clicks"),
    State("admin-state-store", "data"),
    State("admin-s1-report-code", "value"),
    State("admin-s1-report-name", "value"),
    State("admin-s1-category", "value"),
    State("admin-s1-owner", "value"),
    State("admin-s1-description", "value"),
    State("admin-s1-visible", "checked"),
    State("admin-s1-default-fav", "checked"),
    State("admin-s1-tpl-code", "value"),
    State("admin-s1-tpl-name", "value"),
    State("admin-s1-display-order", "value"),
    State("admin-s1-timeout", "value"),
    State("admin-s1-preview-max", "value"),
    State("admin-s1-export-max", "value"),
    prevent_initial_call=True,
)
def handle_s1_save(
    n_clicks: int | None,
    state: dict[str, Any] | None,
    report_code: str | None,
    report_name: str | None,
    category_code: str | None,
    owner: str | None,
    description: str | None,
    is_visible: bool | None,
    default_favorite: bool | None,
    tpl_code: str | None,
    tpl_name: str | None,
    display_order: int | None,
    timeout_sec: int | None,
    preview_max_rows: int | None,
    export_max_rows: int | None,
) -> tuple[dict[str, Any], Any]:
    """Lưu bước 1."""
    if not state:
        raise PreventUpdate
    new_state, alert = handle_save_step1(
        n_clicks,
        state,
        report_code,
        report_name,
        category_code,
        owner,
        description,
        is_visible,
        default_favorite,
        tpl_code,
        tpl_name,
        display_order,
        timeout_sec,
        preview_max_rows,
        export_max_rows,
    )
    return _state_or_no_update(state, new_state, alert)


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-s2-analyze-btn", "n_clicks"),
    State("admin-state-store", "data"),
    State("admin-s2-ds", "value"),
    State("admin-s2-source-type", "value"),
    State("admin-s2-owner", "value"),
    State("admin-s2-object", "value"),
    State("admin-s2-sql", "value"),
    State("admin-s2-timeout", "value"),
    State("admin-s2-preview-max", "value"),
    State("admin-s2-export-max", "value"),
    prevent_initial_call=True,
)
def handle_s2_analyze_sql(
    n_clicks: int | None,
    state: dict[str, Any] | None,
    data_source_id: int | None,
    source_type: str | None,
    source_owner: str | None,
    source_object: str | None,
    sql_text: str | None,
    timeout_sec: int | None,
    preview_max_rows: int | None,
    export_max_rows: int | None,
) -> tuple[dict[str, Any], Any]:
    """Phân tích SQL / Nguồn đối tượng: lưu nguồn trước rồi phân tích."""
    if not n_clicks or not state or not state.get("version_id"):
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    upd_payload: dict[str, Any] = {
        "data_source_id": int(data_source_id) if data_source_id else None,
        "source_type": source_type or "CUSTOM_SQL",
        "sql_text": (sql_text or "").strip() or None,
        "source_owner": (source_owner or "").strip() or None,
        "source_object": (source_object or "").strip() or None,
        "timeout_sec": int(timeout_sec or 300),
        "preview_max_rows": int(preview_max_rows or 100),
        "export_max_rows": int(export_max_rows or 1000000),
    }
    upd_res = update_version_source(ctx, int(state["version_id"]), upd_payload)
    if not upd_res.ok:
        return state, _err_alert(upd_res)
    if source_type in ("VIEW", "TABLE") and source_object:
        return _state_or_no_update(
            state,
            *handle_analyze_object(n_clicks, state, data_source_id, source_type, source_owner, source_object),
        )
    return _state_or_no_update(state, *handle_analyze_sql(n_clicks, state, sql_text))


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-s2-analyze-object-btn", "n_clicks"),
    State("admin-state-store", "data"),
    State("admin-s2-ds", "value"),
    State("admin-s2-source-type", "value"),
    State("admin-s2-owner", "value"),
    State("admin-s2-object", "value"),
    prevent_initial_call=True,
)
def handle_s2_analyze_object(
    n_clicks: int | None,
    state: dict[str, Any] | None,
    data_source_id: int | None,
    source_type: str | None,
    source_owner: str | None,
    source_object: str | None,
) -> tuple[dict[str, Any], Any]:
    """Phân tích nguồn VIEW/TABLE."""
    if not state:
        raise PreventUpdate
    return _state_or_no_update(
        state, *handle_analyze_object(n_clicks, state, data_source_id, source_type, source_owner, source_object)
    )


@callback(
    Output("admin-s2-object-select", "data"),
    Output("admin-s2-object-box", "style"),
    Input("admin-s2-source-type", "value"),
    Input("admin-s2-ds", "value"),
    Input("admin-s2-load-objects-btn", "n_clicks"),
    prevent_initial_call=False,
)
def handle_s2_source_type_and_objects(
    source_type: str | None,
    data_source_id: str | int | None,
    _btn_clicks: int | None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Tải danh sách Bảng/View tự động khi đổi loại nguồn hoặc data source."""
    is_object = source_type in ("VIEW", "TABLE")
    box_style = {"display": "block"} if is_object else {"display": "none"}
    if not is_object or not data_source_id:
        return [], box_style
    ctx = get_current_ctx()
    if ctx is None:
        return [], box_style
    try:
        res = list_report_objects(ctx, int(data_source_id), source_type or "TABLE")
        if res.ok and isinstance(res.data, list):
            items = [{"label": f"{o.get('name')} ({o.get('type')})", "value": str(o.get("name"))} for o in res.data]
            return items, box_style
    except Exception:
        pass
    return [], box_style


@callback(
    Output("admin-s2-object", "value"),
    Output("admin-s2-sql", "value"),
    Input("admin-s2-object-select", "value"),
    State("admin-s2-ds", "value"),
    State("admin-s2-owner", "value"),
    prevent_initial_call=True,
)
def handle_s2_object_pick(
    object_name: str | None,
    ds_id: str | int | None,
    owner: str | None,
) -> tuple[str | None, str | None]:
    """Chọn đối tượng từ danh sách → tự sinh câu SQL tương ứng và điền vào ô SQL."""
    if not object_name:
        raise PreventUpdate
    owner_str = (owner or "").strip()
    tbl_ref = f"{owner_str}.{object_name}" if owner_str else object_name

    cols: list[dict[str, Any]] = []
    if ds_id:
        try:
            cols = list_db_columns(int(ds_id), owner_str, object_name)
        except Exception:
            cols = []

    if cols:
        col_names = [str(c["name"]).lower() for c in cols]
        if len(col_names) <= 4:
            cols_str = ", ".join(col_names)
        else:
            chunks = [col_names[i : i + 4] for i in range(0, len(col_names), 4)]
            cols_str = ",\n       ".join(", ".join(chunk) for chunk in chunks)
        generated_sql = f"SELECT {cols_str}\nFROM {tbl_ref}"
    else:
        generated_sql = f"SELECT *\nFROM {tbl_ref}"

    return object_name, generated_sql


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-p-save-btn", "n_clicks"),
    State("admin-state-store", "data"),
    State("admin-p-code", "value"),
    State("admin-p-label", "value"),
    State("admin-p-data-type", "value"),
    State("admin-p-control-type", "value"),
    State("admin-p-required", "checked"),
    State("admin-p-default-type", "value"),
    State("admin-p-default-value", "value"),
    State("admin-p-row", "value"),
    State("admin-p-order", "value"),
    State("admin-p-span", "value"),
    State("admin-p-filter-col", "value"),
    State("admin-p-filter-op", "value"),
    State("admin-p-visible", "checked"),
    State("admin-p-lov-type", "value"),
    State("admin-p-lov-sql", "value"),
    State("admin-p-lov-lookup", "value"),
    State("admin-p-lov-static", "value"),
    prevent_initial_call=True,
)
def handle_p_save(
    n_clicks: int | None,
    state: dict[str, Any] | None,
    code: str | None,
    label: str | None,
    data_type: str | None,
    control_type: str | None,
    required: bool | None,
    default_type: str | None,
    default_value: str | None,
    display_row: int | None,
    display_order: int | None,
    grid_span: int | None,
    filter_column: str | None,
    filter_operator: str | None,
    is_visible: bool | None,
    lov_type: str | None,
    lov_sql: str | None,
    lov_lookup_type: str | None,
    lov_static_text: str | None,
) -> tuple[dict[str, Any], Any]:
    """Lưu tham số (tạo mới hoặc sửa)."""
    if not state:
        raise PreventUpdate
    param, alert = handle_param_save(
        n_clicks,
        state,
        state.get("editing_param_id"),
        code,
        label,
        data_type,
        control_type,
        required,
        default_type,
        default_value,
        display_row,
        display_order,
        grid_span,
        filter_column,
        filter_operator,
        is_visible,
        lov_type,
        lov_sql,
        lov_lookup_type,
        lov_static_text,
    )
    if param is None:
        return _state_or_no_update(state, state, alert)
    new_state = _bump(state)
    new_state["editing_param_id"] = None
    return new_state, alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Input("admin-p-cancel-edit-btn", "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_p_cancel_edit(n_clicks: int | None, state: dict[str, Any] | None) -> dict[str, Any]:
    """Hủy sửa tham số."""
    if not n_clicks or not state:
        raise PreventUpdate
    new_state = _bump(state)
    new_state["editing_param_id"] = None
    return new_state


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-p-autolayout-btn", "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_p_autolayout(n_clicks: int | None, state: dict[str, Any] | None) -> tuple[dict[str, Any], Any]:
    """Nút Tự sắp xếp layout."""
    if not state:
        raise PreventUpdate
    ok, alert = handle_auto_layout(n_clicks, state)
    return _bump(state), alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input({"type": "admin-param-edit", "index": dash.ALL}, "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_p_edit_click(n_clicks: list[int | None] | None, state: dict[str, Any] | None) -> tuple[dict[str, Any], Any]:
    """Bấm Sửa tham số → nạp vào form."""
    if not n_clicks or not any(n_clicks) or not state:
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    new_state = _bump(state)
    new_state["editing_param_id"] = int(triggered_id["index"])
    return new_state, None


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input({"type": "admin-param-del", "index": dash.ALL}, "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_p_del_click(n_clicks: list[int | None] | None, state: dict[str, Any] | None) -> tuple[dict[str, Any], Any]:
    """Bấm Xóa tham số."""
    if not n_clicks or not any(n_clicks) or not state:
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    clicks = max((c or 0) for c in n_clicks) if isinstance(n_clicks, list) else n_clicks
    ok, alert = handle_param_delete(clicks, state, int(triggered_id["index"]))
    return _bump(state), alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input({"type": "admin-param-up", "index": dash.ALL}, "n_clicks"),
    Input({"type": "admin-param-down", "index": dash.ALL}, "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_p_move_click(
    _up: list[int | None] | None,
    _down: list[int | None] | None,
    state: dict[str, Any] | None,
) -> tuple[dict[str, Any], Any]:
    """Nút ↑↓ dời tham số."""
    if not state:
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    direction = "up" if triggered_id.get("type") == "admin-param-up" else "down"
    ok, alert = handle_param_move(1, state, int(triggered_id["index"]), direction)
    return _bump(state), alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-col-save-btn", "n_clicks"),
    State("admin-state-store", "data"),
    State({"type": "admin-col-label", "index": dash.ALL}, "value"),
    State({"type": "admin-col-label", "index": dash.ALL}, "id"),
    State({"type": "admin-col-format", "index": dash.ALL}, "value"),
    State({"type": "admin-col-align", "index": dash.ALL}, "value"),
    State({"type": "admin-col-width", "index": dash.ALL}, "value"),
    State({"type": "admin-col-web", "index": dash.ALL}, "checked"),
    State({"type": "admin-col-excel", "index": dash.ALL}, "checked"),
    State({"type": "admin-col-total", "index": dash.ALL}, "checked"),
    prevent_initial_call=True,
)
def handle_col_save(
    n_clicks: int | None,
    state: dict[str, Any] | None,
    labels: list[str | None] | None,
    ids: list[dict[str, Any]] | None,
    formats: list[str | None] | None,
    aligns: list[str | None] | None,
    widths: list[int | None] | None,
    webs: list[bool | None] | None,
    excels: list[bool | None] | None,
    totals: list[bool | None] | None,
) -> tuple[dict[str, Any], Any]:
    """Lưu cả grid cột một lần."""
    if not state:
        raise PreventUpdate
    rows: list[dict[str, Any]] = []
    for i, pid in enumerate(ids or []):
        rows.append(
            {
                "id": int(pid["index"]),
                "label": (labels or [None] * len(ids or []))[i],
                "format_mask": (formats or [None] * len(ids or []))[i] or None,
                "alignment": (aligns or [None] * len(ids or []))[i],
                "width": (widths or [None] * len(ids or []))[i],
                "web_visible": bool((webs or [None] * len(ids or []))[i]),
                "excel_visible": bool((excels or [None] * len(ids or []))[i]),
                "is_total": bool((totals or [None] * len(ids or []))[i]),
            }
        )
    ok, alert = handle_column_save(n_clicks, state, rows)
    return _bump(state), alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input({"type": "admin-col-up", "index": dash.ALL}, "n_clicks"),
    Input({"type": "admin-col-down", "index": dash.ALL}, "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_col_move_click(
    _up: list[int | None] | None,
    _down: list[int | None] | None,
    state: dict[str, Any] | None,
) -> tuple[dict[str, Any], Any]:
    """Nút ↑↓ dời cột."""
    if not state:
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    direction = "up" if triggered_id.get("type") == "admin-col-up" else "down"
    ok, alert = handle_column_move(1, state, int(triggered_id["index"]), direction)
    return _bump(state), alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-col-refresh-btn", "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_col_refresh(n_clicks: int | None, state: dict[str, Any] | None) -> tuple[dict[str, Any], Any]:
    """Nút Làm mới cột."""
    if not state:
        raise PreventUpdate
    ok, alert = handle_refresh_columns(n_clicks, state)
    return _bump(state), alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-col-restore-btn", "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_col_restore(n_clicks: int | None, state: dict[str, Any] | None) -> tuple[dict[str, Any], Any]:
    """Nút Khôi phục thứ tự cột."""
    if not state:
        raise PreventUpdate
    ok, alert = handle_restore_order(n_clicks, state)
    return _bump(state), alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-dryrun-store", "data"),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-dryrun-btn", "n_clicks"),
    State("admin-state-store", "data"),
    State({"type": "viewer-param", "index": dash.ALL}, "value"),
    State({"type": "viewer-param", "index": dash.ALL}, "id"),
    prevent_initial_call=True,
)
def handle_dryrun_click(
    n_clicks: int | None,
    state: dict[str, Any] | None,
    param_values: list[Any] | None,
    param_ids: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, Any]:
    """Nút Chạy dry-run ở bước 5."""
    if not state:
        raise PreventUpdate
    values = _param_values_from_inputs(param_values, param_ids)
    new_state, result, alert = handle_dry_run(n_clicks, state, values)
    return _bump(new_state), result, alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input("admin-activate-btn", "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_activate_click(n_clicks: int | None, state: dict[str, Any] | None) -> tuple[dict[str, Any], Any]:
    """Nút Kích hoạt template ở bước 6."""
    if not state:
        raise PreventUpdate
    new_state, alert = handle_activate(n_clicks, state)
    if alert is None:
        return _bump(new_state), alert_box("Đã kích hoạt template.", "Version này đã ACTIVE.", tone="ok")
    return _state_or_no_update(state, new_state, alert)


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input({"type": "admin-edit", "index": dash.ALL}, "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_list_edit_click(
    n_clicks: list[int | None] | None, state: dict[str, Any] | None
) -> tuple[dict[str, Any], Any]:
    """Nút Sửa ở danh sách → mở wizard ở version DRAFT."""
    if not n_clicks or not any(n_clicks):
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    new_state, alert = handle_open_edit(1, int(triggered_id["index"]))
    if new_state is None:
        return state or {"mode": "list"}, alert
    return new_state, alert


@callback(
    Output("admin-state-store", "data", allow_duplicate=True),
    Output("admin-alert", "children", allow_duplicate=True),
    Input({"type": "admin-clone", "index": dash.ALL}, "n_clicks"),
    State("admin-state-store", "data"),
    prevent_initial_call=True,
)
def handle_list_clone_click(
    n_clicks: list[int | None] | None, state: dict[str, Any] | None
) -> tuple[dict[str, Any], Any]:
    """Nút Clone ở danh sách → clone version rồi mở wizard."""
    if not n_clicks or not any(n_clicks):
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    new_state, alert = handle_clone(1, int(triggered_id["index"]))
    if new_state is None:
        return state or {"mode": "list"}, alert
    return new_state, alert


@callback(
    Output("admin-alert", "children", allow_duplicate=True),
    Output("admin-reports-store", "data", allow_duplicate=True),
    Input({"type": "admin-archive-ver", "index": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_list_archive_click(
    n_clicks: list[int | None] | None,
) -> tuple[Any, Any]:
    """Nút Lưu trữ version ở danh sách → archive rồi tải lại danh sách."""
    if not n_clicks or not any(n_clicks):
        raise PreventUpdate
    triggered_id = dash.callback_context.triggered_id
    if not isinstance(triggered_id, dict) or "index" not in triggered_id:
        raise PreventUpdate
    ctx = get_current_ctx()
    if ctx is None:
        raise PreventUpdate
    res = archive_version(ctx, int(triggered_id["index"]))
    if not res.ok:
        return _err_alert(res), dash.no_update
    reports = _load_reports_with_templates(ctx)
    return (
        alert_box("Đã lưu trữ version.", tone="ok"),
        reports,
    )
