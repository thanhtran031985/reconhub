from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, clientside_callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.services.perm import is_admin, page_gate
from app.services.template import (
    archive_template,
    clone_template,
    delete_template,
    list_templates,
)
from app.services.template_export_import import (
    export_template,
    export_template_sample_excel,
    export_templates_list_docx,
    export_templates_list_excel,
    export_templates_list_pdf,
    import_template,
    send_templates_list_email,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.file_drop import file_drop
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import notify_success
from app.ui.components.page_header import page_header
from app.ui.components.saved_view_toolbar import saved_view_toolbar
from app.ui.layout_cache import cached_layout
from app.ui.swr import compute_fingerprint, is_stale_user_store, should_skip_swr_update

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/templates",
        title="Danh sách Template — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "template"


def render_tabulator_toolbar() -> Any:
    """Thanh công cụ phong cách Oracle APEX Interactive Grid: Quản lý Template/Saved Views."""
    return saved_view_toolbar("tmpl", mb="xs")


def render_templates_content(
    items: list[dict[str, Any]] | None,
    loading: bool = False,
    error: str | None = None,
    search_term: str = "",
    status_filter: str = "",
    page: int = 1,
    page_size: int = 10,
    is_admin: bool = False,
) -> Any:
    """Hàm thuần dựng nội dung danh sách template dạng Tabulator Interactive Grid."""
    # 1. Trạng thái Loading
    if loading:
        return dmc.Stack(
            [dmc.Skeleton(height=40, radius="sm") for _ in range(5)],
            gap="xs",
        )

    # 2. Trạng thái Lỗi
    if error:
        return alert_box(
            title="Không thể tải danh sách template",
            message=error,
            tone="crit",
            action=button_danger("Thử lại", id={"type": "tmpl-retry-btn", "index": 0}, size="xs"),
        )

    # 3. Trạng thái không có dữ liệu
    if items is None or len(items) == 0:
        return empty_state(
            title="Chưa có template nào",
            description="Bắt đầu bằng cách đăng ký template mới hoặc import từ file JSON có sẵn.",
            action=dmc.Anchor(
                button_primary("Đăng ký template", icon="lucide:plus", size="xs"),
                href="/templates/new",
                underline=False,
            ),
        )

    # Chuẩn hóa dữ liệu truyền xuống Tabulator
    enriched_items: list[dict[str, Any]] = []
    for it in items:
        try:
            id_val = int(it.get("id") or 0)
        except Exception:
            id_val = 0
        code_val = str(it.get("code") or it.get("template_id") or (id_val if id_val > 0 else ""))
        action_index: int | str = id_val if id_val > 0 else code_val
        profiles = it.get("profiles") or []
        profiles_text = ", ".join(
            str(p.get("name") or p.get("profile_id") or p.get("code") or "") for p in profiles if isinstance(p, dict)
        )
        last_run = it.get("last_run")
        if isinstance(last_run, dict):
            lr_id = last_run.get("id", 0)
            lr_st = last_run.get("status", "")
            lr_fin = last_run.get("finished_at", "")
            last_run_text = f"#{lr_id} {lr_st} {lr_fin}".strip()
        else:
            last_run = None
            last_run_text = "Chưa chạy"

        enriched_items.append(
            {
                "id": id_val,
                "action_index": action_index,
                "code": code_val,
                "template_id": str(it.get("template_id") or code_val),
                "name": str(it.get("name") or ""),
                "file_pattern": str(it.get("file_pattern") or "—"),
                "sheet": str(it.get("sheet") or ""),
                "field_count": int(it.get("field_count") or 0),
                "profiles": profiles,
                "profiles_text": profiles_text or "—",
                "current_version": int(it.get("current_version") or it.get("version") or 1),
                "owner": str(it.get("owner") or it.get("created_by") or "—"),
                "status": str(it.get("status") or "ACTIVE"),
                "last_run": last_run,
                "last_run_text": last_run_text,
            }
        )

    return dmc.Box(
        [
            render_tabulator_toolbar(),
            html.Div(
                id="tmpl-tabulator-table",
                style={
                    "flex": 1,
                    "minHeight": "360px",
                    "width": "100%",
                },
            ),
            dcc.Store(
                id="tmpl-tabulator-ready-data",
                data={"items": enriched_items, "is_admin": bool(is_admin)},
            ),
            html.Div(id="tmpl-tabulator-dummy-output", style={"display": "none"}),
        ],
        style={
            "flex": 1,
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
        },
    )


def _build_templates_layout() -> Any:
    export_menu = dmc.Menu(
        [
            dmc.MenuTarget(
                button_subtle(
                    "Xuất danh sách",
                    id="tmpl-export-menu-btn",
                    icon="lucide:download",
                    rightSection=DashIconify(icon="lucide:chevron-down", width=12),
                    size="xs",
                )
            ),
            dmc.MenuDropdown(
                [
                    dmc.MenuItem(
                        "Xuất Excel (.xlsx)",
                        id="tmpl-export-excel-btn",
                        leftSection=DashIconify(icon="lucide:file-spreadsheet", width=14, color="#1D6F42"),
                    ),
                    dmc.MenuItem(
                        "Xuất Word (.docx)",
                        id="tmpl-export-word-btn",
                        leftSection=DashIconify(icon="lucide:file-text", width=14, color="#185ABD"),
                    ),
                    dmc.MenuItem(
                        "Xuất PDF (.pdf)",
                        id="tmpl-export-pdf-btn",
                        leftSection=DashIconify(icon="lucide:file-type-2", width=14, color="#E02424"),
                    ),
                    dmc.MenuDivider(),
                    dmc.MenuItem(
                        "Gửi qua Email...",
                        id="tmpl-export-email-btn",
                        leftSection=DashIconify(icon="lucide:mail", width=14, color="#0C8599"),
                    ),
                ]
            ),
        ],
        position="bottom-end",
        withArrow=True,
    )

    header_actions = [
        dmc.ActionIcon(
            DashIconify(icon="lucide:refresh-cw", width=14),
            id="tmpl-refresh-btn",
            variant="subtle",
            color="gray",
            size="sm",
            **{"aria-label": "Làm mới danh sách"},
        ),
        export_menu,
        button_subtle("Import JSON", id="tmpl-import-btn", icon="lucide:upload", size="xs"),
        dmc.Anchor(
            button_primary("Đăng ký template", icon="lucide:plus", size="xs"),
            href="/templates/new",
            underline=False,
        ),
    ]

    header_node = page_header(
        title="Danh sách template",
        subtitle="Cấu hình mapping cột Excel và DB, bộ lọc ngày và các profile đối soát.",
        actions=header_actions,
    )

    return dmc.Box(
        [
            dcc.Store(id="tmpl-store-list", storage_type="session"),
            dcc.Store(id="tmpl-row-action-trigger"),
            dcc.Download(id="tmpl-export-download"),
            dcc.Download(id="tmpl-sample-download"),
            dcc.Download(id="tmpl-list-download"),
            # Input ẩn giữ bộ lọc hiện tại từ header filter Tabulator để phục vụ Export / Gửi Email
            html.Div(
                [
                    dcc.Input(id="tmpl-filter-search", value="", type="hidden"),
                    dcc.Input(id="tmpl-filter-status", value="", type="hidden"),
                ],
                style={"display": "none"},
            ),
            header_node,
            html.Div(
                id="tmpl-content-container",
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
            ),
            html.Div(id="tmpl-email-toast"),
            # Modal Lưu Template / View mới cho Tabulator
            dmc.Modal(
                id="tmpl-save-view-modal",
                title=dmc.Group(
                    [
                        DashIconify(icon="lucide:layout-grid", width=18, color="var(--primary, #2563EB)"),
                        dmc.Text("Lưu Template / View mới", fw=600, size="sm"),
                    ],
                    gap="xs",
                ),
                children=dmc.Stack(
                    [
                        dmc.TextInput(
                            id="tmpl-new-view-name",
                            label="Tên Template / View",
                            placeholder="Nhập tên template (vd: Xem nhanh, Báo cáo cá nhân...)",
                            withAsterisk=True,
                            size="sm",
                        ),
                        dmc.Checkbox(
                            id="tmpl-new-view-default",
                            label="Đặt làm giao diện mặc định khi mở trang",
                            size="sm",
                        ),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Hủy",
                                    id="tmpl-cancel-save-view-btn",
                                    variant="subtle",
                                    color="gray",
                                    size="xs",
                                ),
                                dmc.Button(
                                    "Lưu Template",
                                    id="tmpl-confirm-save-view-btn",
                                    color="primary",
                                    size="xs",
                                ),
                            ],
                            justify="flex-end",
                            gap="xs",
                            mt="sm",
                        ),
                    ],
                    gap="md",
                ),
                opened=False,
                size="sm",
                centered=True,
            ),
            # Modal Xóa Template / View của Tabulator
            dmc.Modal(
                id="tmpl-delete-view-modal",
                title=dmc.Group(
                    [
                        DashIconify(icon="lucide:trash-2", width=18, color="#DC2626"),
                        dmc.Text("Xóa Template / View", fw=600, size="sm", c="#DC2626"),
                    ],
                    gap="xs",
                ),
                children=dmc.Stack(
                    [
                        dmc.Text(
                            "Bạn có chắc chắn muốn xóa Template / View này? Thao tác này không thể hoàn tác.",
                            size="sm",
                            c="dimmed",
                        ),
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Hủy",
                                    id="tmpl-cancel-delete-view-btn",
                                    variant="subtle",
                                    color="gray",
                                    size="xs",
                                ),
                                dmc.Button(
                                    "Xóa Template",
                                    id="tmpl-confirm-delete-view-btn",
                                    color="red",
                                    size="xs",
                                ),
                            ],
                            justify="flex-end",
                            gap="xs",
                            mt="sm",
                        ),
                    ],
                    gap="md",
                ),
                opened=False,
                size="sm",
                centered=True,
            ),
            # Modal Gửi email danh sách template
            dmc.Modal(
                id="tmpl-email-modal",
                title=dmc.Text("Gửi danh sách Template qua Email", fw=700, size="md"),
                opened=False,
                size="md",
                children=dmc.Stack(
                    [
                        dmc.Text(
                            "Chọn định dạng tệp đính kèm và nhập danh sách địa chỉ email nhận thư. "
                            "Hệ thống sẽ kết xuất theo đúng bộ lọc hiện tại và gửi thư qua máy chủ SMTP đã cấu hình.",
                            size="sm",
                            c="dimmed",
                        ),
                        dmc.CheckboxGroup(
                            id="tmpl-email-formats",
                            label="Định dạng tệp đính kèm",
                            description="Chọn ít nhất 1 định dạng",
                            children=dmc.Group(
                                [
                                    dmc.Checkbox(label="Excel (.xlsx)", value="XLSX"),
                                    dmc.Checkbox(label="Word (.docx)", value="DOCX"),
                                    dmc.Checkbox(label="PDF (.pdf)", value="PDF"),
                                ],
                                gap="md",
                            ),
                            value=["XLSX"],
                        ),
                        dmc.TextInput(
                            id="tmpl-email-recipients",
                            label="Người nhận (To)",
                            placeholder="vd: nguoinhan@company.com, ketoan@company.com",
                            description="Nhiều email cách nhau bằng dấu phẩy",
                            required=True,
                        ),
                        dmc.TextInput(
                            id="tmpl-email-subject",
                            label="Tiêu đề email",
                            placeholder="vd: [ReconHub] Danh sách Template đối soát",
                            required=True,
                        ),
                        dmc.Textarea(
                            id="tmpl-email-notes",
                            label="Lời nhắn kèm theo (tùy chọn)",
                            placeholder="Nhập nội dung ghi chú cho người nhận...",
                            minRows=3,
                        ),
                        html.Div(
                            [
                                dmc.Group(
                                    [
                                        DashIconify(icon="lucide:loader-2", width=14, color="#228be6"),
                                        dmc.Text(
                                            "Đang kết xuất tệp và gửi email qua SMTP...",
                                            size="xs",
                                            c="blue",
                                            fw=500,
                                        ),
                                    ],
                                    gap=6,
                                    mb=4,
                                ),
                                dmc.Progress(
                                    value=100,
                                    animated=True,
                                    striped=True,
                                    color="blue",
                                    size="sm",
                                    radius="xs",
                                ),
                            ],
                            id="tmpl-email-progress-container",
                            style={"display": "none"},
                        ),
                        html.Div(id="tmpl-email-alert"),
                        dmc.Group(
                            [
                                button_subtle("Hủy", id="tmpl-email-cancel-btn"),
                                button_primary("Gửi email", id="tmpl-email-submit-btn", icon="lucide:send"),
                            ],
                            justify="flex-end",
                            gap="sm",
                            mt="sm",
                        ),
                    ],
                    gap="sm",
                ),
            ),
            # Modal Import JSON
            dmc.Modal(
                id="tmpl-import-modal",
                title=dmc.Text("Import Template từ file JSON", fw=700, size="md"),
                opened=False,
                children=dmc.Stack(
                    [
                        file_drop(
                            id="tmpl-import-upload", label="Chọn hoặc kéo thả file JSON template", accept=".json"
                        ),
                        dmc.Switch(
                            id="tmpl-import-overwrite",
                            label="Ghi đè nếu template đã tồn tại",
                            size="sm",
                            checked=False,
                        ),
                        html.Div(id="tmpl-import-alert"),
                        dmc.Group(
                            [
                                button_subtle("Đóng", id="tmpl-import-cancel"),
                                button_primary("Import", id="tmpl-import-submit", icon="lucide:upload"),
                            ],
                            justify="flex-end",
                            gap="sm",
                            mt="md",
                        ),
                    ],
                    gap="md",
                ),
            ),
            # Modal Nhân bản (Clone)
            dmc.Modal(
                id="tmpl-clone-modal",
                title=dmc.Text("Nhân bản template", fw=700, size="md"),
                opened=False,
                children=dmc.Stack(
                    [
                        dcc.Store(id="tmpl-clone-source-id"),
                        dmc.TextInput(
                            id="tmpl-clone-target-id",
                            label="Mã template mới",
                            description="Chữ in hoa, số và gạch dưới (VD: DTP_HOA_DON_V2)",
                            required=True,
                        ),
                        dmc.TextInput(
                            id="tmpl-clone-target-name",
                            label="Tên template mới",
                            placeholder="Để trống sẽ thêm '(Bản sao)'",
                        ),
                        html.Div(id="tmpl-clone-alert"),
                        dmc.Group(
                            [
                                button_subtle("Hủy", id="tmpl-clone-cancel"),
                                button_primary("Xác nhận nhân bản", id="tmpl-clone-submit", icon="lucide:copy"),
                            ],
                            justify="flex-end",
                            gap="sm",
                            mt="md",
                        ),
                    ],
                    gap="md",
                ),
            ),
            # Modal Lưu trữ (Archive)
            modal_confirm(
                id="tmpl-archive-modal",
                title="Xác nhận lưu trữ template",
                description="Template sau khi lưu trữ sẽ chuyển sang trạng thái ARCHIVED và không thể chạy run mới. Bạn có chắc chắn muốn lưu trữ?",
                confirm_label="Lưu trữ template",
                danger=True,
            ),
            dcc.Store(id="tmpl-archive-target-id"),
            # Modal Xóa vĩnh viễn template (chỉ Admin)
            modal_confirm(
                id="tmpl-delete-modal",
                title="Xác nhận xóa vĩnh viễn template",
                description="Hành động này sẽ xóa vĩnh viễn cấu hình template và toàn bộ các phiên bản, lịch sử liên quan khỏi hệ thống. Thao tác không thể khôi phục. Bạn có chắc chắn muốn xóa?",
                confirm_label="Xóa vĩnh viễn template",
                danger=True,
            ),
            dcc.Store(id="tmpl-delete-target-id"),
        ],
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "padding": "8px 12px",
            "gap": "6px",
        },
    )


def layout() -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return dmc.Box(
            [
                dcc.Location(id="templates-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang Templates.", tone="crit"),
            ],
            p="md",
        )
    return cached_layout(
        get_recon_engine(),
        ("templates",),
        _build_templates_layout,
    )


def _templates_store_payload(ctx: Any, items: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Đóng gói dữ liệu /templates kèm user_id và vân tay phục vụ SWR."""
    safe_items = items if isinstance(items, list) else []
    is_adm = is_admin(ctx) if ctx else False
    uid = getattr(ctx, "user_id", None) if ctx else None
    fp = compute_fingerprint({"is_admin": is_adm, "items": safe_items})
    return {
        "items": safe_items,
        "error": None,
        "is_admin": is_adm,
        "user_id": uid,
        "fingerprint": fp,
    }


# Callbacks xử lý danh sách template
@callback(
    Output("tmpl-store-list", "data"),
    Input("tmpl-refresh-btn", "n_clicks"),
    Input({"type": "tmpl-retry-btn", "index": ALL}, "n_clicks"),
    State("tmpl-store-list", "data"),
)
def load_templates_data(
    refresh_clicks: Any = None,
    retry_clicks: Any = None,
    cached_data: Any = None,
) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return {"items": [], "error": "Chưa đăng nhập", "is_admin": False}

    res = list_templates(ctx)
    if not res.ok:
        return {
            "items": [],
            "error": res.message,
            "is_admin": is_admin(ctx),
            "user_id": getattr(ctx, "user_id", None),
        }

    items = res.data or []
    payload = _templates_store_payload(ctx, items)
    if should_skip_swr_update(cached_data, payload.get("user_id"), payload["fingerprint"]):
        return dash.no_update
    return payload


@callback(
    Output("tmpl-content-container", "children"),
    Input("tmpl-store-list", "data"),
)
def update_templates_table(store_data: Any) -> Any:
    if not store_data:
        return render_templates_content(items=None, loading=True)

    ctx = get_current_ctx()
    uid = getattr(ctx, "user_id", None) if ctx else None
    if is_stale_user_store(store_data, uid):
        return render_templates_content(items=None, loading=True)

    items = store_data.get("items")
    error = store_data.get("error")
    is_adm = bool(store_data.get("is_admin", False))

    return render_templates_content(
        items=items,
        loading=False,
        error=error,
        is_admin=is_adm,
    )


# Clientside callbacks cho Tabulator Interactive Grid & Saved Views
clientside_callback(
    """
    function(data) {
        if (!data || !Array.isArray(data.items)) return "";
        function mountTabulator() {
            var container = document.getElementById("tmpl-tabulator-table");
            if (container && window.templatesTabulator && window.templatesTabulator.init) {
                var initFn = function() {
                    window.templatesTabulator.init("tmpl-tabulator-table", data.items, !!data.is_admin);
                };
                if (window.reconLazy && typeof window.reconLazy.ensureTabulator === "function") {
                    window.reconLazy.ensureTabulator().then(initFn).catch(function(err) {
                        console.error("[templates] Không tải được Tabulator:", err);
                    });
                } else {
                    initFn();
                }
            } else {
                setTimeout(mountTabulator, 100);
            }
        }
        setTimeout(mountTabulator, 50);
        return "";
    }
    """,
    Output("tmpl-tabulator-dummy-output", "children"),
    Input("tmpl-tabulator-ready-data", "data"),
)

clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && window.templatesTabulator) {
            window.templatesTabulator.saveCurrentView();
        }
        return "";
    }
    """,
    Output("tmpl-grid-notification", "children", allow_duplicate=True),
    Input("tmpl-btn-save-view", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) {
            return [
                window.dash_clientside.no_update,
                window.dash_clientside.no_update,
                window.dash_clientside.no_update,
                window.dash_clientside.no_update
            ];
        }
        return [true, "", null, false];
    }
    """,
    Output("tmpl-save-view-modal", "opened"),
    Output("tmpl-new-view-name", "value"),
    Output("tmpl-new-view-name", "error"),
    Output("tmpl-new-view-default", "checked"),
    Input("tmpl-btn-save-as-view", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        return false;
    }
    """,
    Output("tmpl-save-view-modal", "opened", allow_duplicate=True),
    Input("tmpl-cancel-save-view-btn", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks, name, isDefault) {
        if (!n_clicks) {
            return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        }
        var vName = (name || "").trim();
        if (!vName) {
            return [true, "Vui lòng nhập tên cho Template / View."];
        }
        if (window.templatesTabulator && window.templatesTabulator.saveNewView) {
            window.templatesTabulator.saveNewView(vName, !!isDefault);
        }
        return [false, null];
    }
    """,
    Output("tmpl-save-view-modal", "opened", allow_duplicate=True),
    Output("tmpl-new-view-name", "error", allow_duplicate=True),
    Input("tmpl-confirm-save-view-btn", "n_clicks"),
    State("tmpl-new-view-name", "value"),
    State("tmpl-new-view-default", "checked"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks, viewId) {
        if (n_clicks && window.templatesTabulator) {
            window.templatesTabulator.setDefaultView(viewId || "default");
        }
        return "";
    }
    """,
    Output("tmpl-grid-notification", "children", allow_duplicate=True),
    Input("tmpl-btn-set-default", "n_clicks"),
    State("tmpl-view-select", "value"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && window.templatesTabulator) {
            window.templatesTabulator.resetToDefault();
        }
        return "";
    }
    """,
    Output("tmpl-grid-notification", "children", allow_duplicate=True),
    Input("tmpl-btn-reset-default", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks, viewId) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var activeId = (window.templatesTabulator && window.templatesTabulator.activeViewId)
            ? window.templatesTabulator.activeViewId
            : viewId;
        if (!activeId || activeId === "default") {
            if (window.templatesTabulator && window.templatesTabulator.showStatusNotification) {
                window.templatesTabulator.showStatusNotification("Không thể xóa View mặc định hệ thống.");
            }
            return false;
        }
        return true;
    }
    """,
    Output("tmpl-delete-view-modal", "opened"),
    Input("tmpl-btn-delete-view", "n_clicks"),
    State("tmpl-view-select", "value"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        return false;
    }
    """,
    Output("tmpl-delete-view-modal", "opened", allow_duplicate=True),
    Input("tmpl-cancel-delete-view-btn", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks, viewId) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var activeId = (window.templatesTabulator && window.templatesTabulator.activeViewId)
            ? window.templatesTabulator.activeViewId
            : viewId;
        if (window.templatesTabulator && window.templatesTabulator.deleteView) {
            window.templatesTabulator.deleteView(activeId);
        }
        return false;
    }
    """,
    Output("tmpl-delete-view-modal", "opened", allow_duplicate=True),
    Input("tmpl-confirm-delete-view-btn", "n_clicks"),
    State("tmpl-view-select", "value"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(viewId) {
        if (viewId && window.templatesTabulator) {
            window.templatesTabulator.applyView(viewId);
        }
        return "";
    }
    """,
    Output("tmpl-grid-notification", "children", allow_duplicate=True),
    Input("tmpl-view-select", "value"),
    prevent_initial_call=True,
)


# Callback mở/đóng modal Import
@callback(
    Output("tmpl-import-modal", "opened"),
    Input("tmpl-import-btn", "n_clicks"),
    Input("tmpl-import-cancel", "n_clicks"),
    State("tmpl-import-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_import_modal(open_clicks: Any, close_clicks: Any, is_opened: bool) -> bool:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False
    trigger = ctx_dash.triggered[0]
    trigger_id = trigger["prop_id"].split(".")[0]
    trigger_val = trigger.get("value")
    return trigger_id == "tmpl-import-btn" and bool(trigger_val)


# Callback thực hiện Import JSON
@callback(
    Output("tmpl-import-alert", "children"),
    Output("tmpl-store-list", "data", allow_duplicate=True),
    Input("tmpl-import-submit", "n_clicks"),
    State("tmpl-import-upload", "contents"),
    State("tmpl-import-overwrite", "checked"),
    prevent_initial_call=True,
)
def handle_import_template(n_clicks: Any, contents: str | None, overwrite: bool) -> tuple[Any, Any]:
    if not contents:
        return alert_box("Lỗi", "Vui lòng chọn hoặc kéo thả file JSON cần import", tone="crit"), dash.no_update

    try:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string).decode("utf-8")
        parsed_data = json.loads(decoded)
        if not isinstance(parsed_data, dict):
            return alert_box("Lỗi", "Dữ liệu JSON phải là đối tượng cấu hình", tone="crit"), dash.no_update

        ctx = get_current_ctx()
        if ctx is None:
            return alert_box("Lỗi", "Chưa đăng nhập", tone="crit"), dash.no_update

        res = import_template(ctx, parsed_data, overwrite=overwrite)
        if not res.ok:
            return alert_box("Không thể import", res.message, tone="crit"), dash.no_update

        list_res = list_templates(ctx)
        items = list_res.data if list_res.ok and list_res.data else []
        return (
            alert_box(
                "Thành công",
                f"Đã nạp thành công template {res.data.get('code') if isinstance(res.data, dict) else ''}",
                tone="ok",
            ),
            _templates_store_payload(ctx, items),
        )
    except Exception as e:
        return alert_box("Lỗi định dạng", f"File không đúng định dạng JSON: {e}", tone="crit"), dash.no_update


# Callback mở modal Clone
@callback(
    Output("tmpl-clone-modal", "opened"),
    Output("tmpl-clone-source-id", "data"),
    Input("tmpl-row-action-trigger", "data"),
    Input("tmpl-clone-cancel", "n_clicks"),
    State("tmpl-clone-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_clone_modal(trigger_data: Any, cancel_clicks: Any, is_opened: bool) -> tuple[Any, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, None

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "tmpl-clone-cancel":
        return False, None

    if isinstance(trigger_data, dict) and trigger_data.get("action") == "clone":
        return True, trigger_data.get("id")
    raise PreventUpdate


# Callback thực hiện Clone
@callback(
    Output("tmpl-clone-alert", "children"),
    Output("tmpl-store-list", "data", allow_duplicate=True),
    Input("tmpl-clone-submit", "n_clicks"),
    State("tmpl-clone-source-id", "data"),
    State("tmpl-clone-target-id", "value"),
    State("tmpl-clone-target-name", "value"),
    prevent_initial_call=True,
)
def handle_clone_template(n_clicks: Any, source_id: Any, target_id: str | None, target_name: str | None) -> tuple[Any, Any]:
    if not source_id or not target_id:
        return alert_box("Lỗi", "Vui lòng nhập mã template mới", tone="crit"), dash.no_update

    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Lỗi", "Chưa đăng nhập", tone="crit"), dash.no_update

    try:
        src_id_int = int(source_id)
    except Exception:
        return alert_box("Lỗi", "ID template nguồn không hợp lệ", tone="crit"), dash.no_update

    new_code = target_id.strip().upper()
    new_name = target_name.strip() if target_name else new_code
    res = clone_template(ctx, src_id_int, new_code=new_code, new_name=new_name)
    if not res.ok:
        return alert_box("Không thể nhân bản", res.message, tone="crit"), dash.no_update

    list_res = list_templates(ctx)
    items = list_res.data if list_res.ok and list_res.data else []
    return (
        alert_box("Thành công", f"Đã nhân bản thành công template {target_id}", tone="ok"),
        _templates_store_payload(ctx, items),
    )


# Callback mở modal Archive
@callback(
    Output("tmpl-archive-modal", "opened"),
    Output("tmpl-archive-target-id", "data"),
    Input("tmpl-row-action-trigger", "data"),
    Input("tmpl-archive-modal-cancel", "n_clicks"),
    State("tmpl-archive-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_archive_modal(trigger_data: Any, cancel_clicks: Any, is_opened: bool) -> tuple[Any, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, None

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "tmpl-archive-modal-cancel":
        return False, None

    if isinstance(trigger_data, dict) and trigger_data.get("action") == "archive":
        return True, trigger_data.get("id")
    raise PreventUpdate


# Callback thực hiện Archive
@callback(
    Output("tmpl-archive-modal", "opened", allow_duplicate=True),
    Output("tmpl-store-list", "data", allow_duplicate=True),
    Input("tmpl-archive-modal-confirm", "n_clicks"),
    State("tmpl-archive-target-id", "data"),
    prevent_initial_call=True,
)
def handle_archive_template(n_clicks: Any, target_id: Any) -> tuple[bool, Any]:
    if target_id is not None:
        try:
            tid_int = int(target_id)
            ctx = get_current_ctx()
            if ctx:
                archive_template(ctx, tid_int)
        except Exception:
            pass

    ctx = get_current_ctx()
    res = list_templates(ctx) if ctx else None
    items = res.data if res and res.ok else []
    return False, _templates_store_payload(ctx, items)


# Callback mở modal Delete (chỉ Admin)
@callback(
    Output("tmpl-delete-modal", "opened"),
    Output("tmpl-delete-target-id", "data"),
    Input("tmpl-row-action-trigger", "data"),
    Input("tmpl-delete-modal-cancel", "n_clicks"),
    State("tmpl-delete-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_delete_modal(
    trigger_data: Any,
    cancel_clicks: Any,
    is_opened: bool,
) -> tuple[Any, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, None

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "tmpl-delete-modal-cancel":
        return False, None

    if isinstance(trigger_data, dict) and trigger_data.get("action") == "delete":
        ctx = get_current_ctx()
        if ctx and is_admin(ctx):
            return True, trigger_data.get("id")
        return False, None
    raise PreventUpdate


# Callback thực hiện Delete template
@callback(
    Output("tmpl-delete-modal", "opened", allow_duplicate=True),
    Output("tmpl-store-list", "data", allow_duplicate=True),
    Input("tmpl-delete-modal-confirm", "n_clicks"),
    State("tmpl-delete-target-id", "data"),
    prevent_initial_call=True,
)
def handle_delete_template(n_clicks: Any, target_id: Any) -> tuple[bool, Any]:
    if target_id is not None:
        try:
            ctx = get_current_ctx()
            if ctx and is_admin(ctx):
                delete_template(ctx, target_id)
        except Exception:
            pass

    ctx = get_current_ctx()
    res = list_templates(ctx) if ctx else None
    items = res.data if res and res.ok else []
    return False, _templates_store_payload(ctx, items)


# Callback thực hiện Export JSON
@callback(
    Output("tmpl-export-download", "data"),
    Input("tmpl-row-action-trigger", "data"),
    prevent_initial_call=True,
)
def handle_export_template(trigger_data: Any) -> Any:
    if not isinstance(trigger_data, dict) or trigger_data.get("action") != "export":
        raise PreventUpdate

    target_id = trigger_data.get("id")
    if target_id is not None:
        try:
            tid_int = int(target_id)
            ctx = get_current_ctx()
            if ctx:
                res = export_template(ctx, tid_int)
                if res.ok and res.data:
                    code_val = str(res.data.get("code") or "template")
                    return {
                        "content": json.dumps(res.data, ensure_ascii=False, indent=2),
                        "filename": f"{code_val}.json",
                        "type": "application/json",
                    }
        except Exception:
            pass
    return None


# Callback tải file mẫu Excel của template
@callback(
    Output("tmpl-sample-download", "data"),
    Input("tmpl-row-action-trigger", "data"),
    prevent_initial_call=True,
)
def handle_sample_excel_template(trigger_data: Any) -> Any:
    if not isinstance(trigger_data, dict) or trigger_data.get("action") != "sample":
        raise PreventUpdate

    target_id = trigger_data.get("id")
    if target_id is not None:
        try:
            tid_int = int(target_id)
            ctx = get_current_ctx()
            if ctx:
                res = export_template_sample_excel(ctx, tid_int)
                if res.ok and res.data:
                    return dcc.send_bytes(  # type: ignore[attr-defined, no-untyped-call]
                        res.data["content"],
                        filename=str(res.data.get("filename") or "template_mau.xlsx"),
                    )
        except Exception:
            pass
    return None


# Callback xuất danh sách template ra Excel, Word (.docx), hoặc PDF (.pdf)
@callback(
    Output("tmpl-list-download", "data"),
    Input("tmpl-export-excel-btn", "n_clicks"),
    Input("tmpl-export-word-btn", "n_clicks"),
    Input("tmpl-export-pdf-btn", "n_clicks"),
    State("tmpl-filter-search", "value"),
    State("tmpl-filter-status", "value"),
    prevent_initial_call=True,
)
def handle_export_templates_list(
    excel_clicks: Any,
    word_clicks: Any,
    pdf_clicks: Any,
    search_val: str | None,
    status_val: str | None,
) -> Any:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return None

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]
    ctx = get_current_ctx()
    if ctx is None:
        return None

    q = search_val or ""
    st = status_val or ""

    if trigger_id == "tmpl-export-excel-btn":
        res = export_templates_list_excel(ctx, search_term=q, status_filter=st)
        if res.ok and res.data:
            return dcc.send_bytes(  # type: ignore[attr-defined, no-untyped-call]
                res.data["content"],
                filename=str(res.data.get("filename") or "danh_sach_template.xlsx"),
            )
    elif trigger_id == "tmpl-export-word-btn":
        res = export_templates_list_docx(ctx, search_term=q, status_filter=st)
        if res.ok and res.data:
            return dcc.send_bytes(  # type: ignore[attr-defined, no-untyped-call]
                res.data["content"],
                filename=str(res.data.get("filename") or "danh_sach_template.docx"),
            )
    elif trigger_id == "tmpl-export-pdf-btn":
        res = export_templates_list_pdf(ctx, search_term=q, status_filter=st)
        if res.ok and res.data:
            return dcc.send_bytes(  # type: ignore[attr-defined, no-untyped-call]
                res.data["content"],
                filename=str(res.data.get("filename") or "danh_sach_template.pdf"),
            )

    return None


# Clientside callback kích hoạt thanh Progress bar và vô hiệu hóa nút Gửi ngay khi click
clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        return [{"display": "block", "marginTop": "8px", "marginBottom": "8px"}, true];
    }
    """,
    Output("tmpl-email-progress-container", "style", allow_duplicate=True),
    Output("tmpl-email-submit-btn", "disabled", allow_duplicate=True),
    Input("tmpl-email-submit-btn", "n_clicks"),
    prevent_initial_call=True,
)


# Callback hợp nhất điều khiển mở/đóng và gửi email danh sách template
@callback(
    Output("tmpl-email-modal", "opened"),
    Output("tmpl-email-subject", "value"),
    Output("tmpl-email-recipients", "value"),
    Output("tmpl-email-alert", "children"),
    Output("tmpl-email-toast", "children"),
    Output("tmpl-email-progress-container", "style", allow_duplicate=True),
    Output("tmpl-email-submit-btn", "disabled", allow_duplicate=True),
    Input("tmpl-export-email-btn", "n_clicks"),
    Input("tmpl-email-cancel-btn", "n_clicks"),
    Input("tmpl-email-submit-btn", "n_clicks"),
    State("tmpl-email-modal", "opened"),
    State("tmpl-email-recipients", "value"),
    State("tmpl-email-formats", "value"),
    State("tmpl-email-subject", "value"),
    State("tmpl-email-notes", "value"),
    State("tmpl-filter-search", "value"),
    State("tmpl-filter-status", "value"),
    prevent_initial_call=True,
)
def handle_email_modal_actions(
    export_clicks: Any,
    cancel_clicks: Any,
    submit_clicks: Any,
    is_opened: bool,
    recipients_val: str | None,
    formats_val: list[str] | None,
    subject_val: str | None,
    notes_val: str | None,
    search_val: str | None,
    status_val: str | None,
) -> tuple[Any, Any, Any, Any, Any, dict[str, str], bool]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        raise PreventUpdate

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]

    # 1. Bấm mở Modal từ menu "Gửi qua Email..."
    if trigger_id == "tmpl-export-email-btn":
        today_str = datetime.now().strftime("%d/%m/%Y")
        default_subject = f"[ReconHub] Danh sách Template đối soát — {today_str}"
        return True, default_subject, "", None, dash.no_update, {"display": "none"}, False

    # 2. Bấm nút Hủy
    if trigger_id == "tmpl-email-cancel-btn":
        return False, dash.no_update, dash.no_update, None, dash.no_update, {"display": "none"}, False

    # 3. Bấm nút Gửi email
    if trigger_id == "tmpl-email-submit-btn":
        ctx = get_current_ctx()
        if ctx is None:
            return (
                True,
                dash.no_update,
                dash.no_update,
                alert_box("Lỗi xác thực", "Chưa đăng nhập.", tone="crit"),
                dash.no_update,
                {"display": "none"},
                False,
            )

        recipients_raw = (recipients_val or "").strip()
        if not recipients_raw:
            return (
                True,
                dash.no_update,
                dash.no_update,
                alert_box("Thiếu thông tin", "Vui lòng nhập ít nhất một địa chỉ email người nhận.", tone="crit"),
                dash.no_update,
                {"display": "none"},
                False,
            )

        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
        formats = formats_val or []
        if not formats:
            return (
                True,
                dash.no_update,
                dash.no_update,
                alert_box("Thiếu thông tin", "Vui lòng chọn ít nhất một định dạng tệp đính kèm.", tone="crit"),
                dash.no_update,
                {"display": "none"},
                False,
            )

        res = send_templates_list_email(
            ctx=ctx,
            to_emails=recipients,
            format_types=formats,
            search_term=search_val or "",
            status_filter=status_val or "",
            custom_subject=(subject_val or "").strip(),
            notes=(notes_val or "").strip(),
        )

        if not res.ok:
            return (
                True,
                dash.no_update,
                dash.no_update,
                alert_box("Gửi email thất bại", res.message or "Lỗi không xác định khi gửi email.", tone="crit"),
                dash.no_update,
                {"display": "none"},
                False,
            )

        recipients_str = ", ".join(res.data.get("to_emails", [])) if res.data else recipients_raw
        return (
            False,
            dash.no_update,
            dash.no_update,
            None,
            notify_success(f"Đã gửi email danh sách template thành công tới: {recipients_str}"),
            {"display": "none"},
            False,
        )

    raise PreventUpdate
