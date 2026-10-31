from __future__ import annotations

import base64
import json
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.template import (
    archive_template,
    clone_template,
    list_templates,
)
from app.services.template_export_import import (
    export_template,
    import_template,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.file_drop import file_drop
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.status_chip import status_chip

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/templates",
        title="Danh sách Template — ReconHub",
    )
except Exception:
    pass


def render_templates_content(
    items: list[dict[str, Any]] | None,
    loading: bool = False,
    error: str | None = None,
    search_term: str = "",
    status_filter: str = "",
) -> Any:
    """Hàm thuần dựng nội dung danh sách template theo 4 trạng thái."""
    # 1. Trạng thái Loading
    if loading:
        return dmc.Stack(
            [dmc.Skeleton(height=48, radius="md") for _ in range(5)],
            gap="sm",
        )

    # 2. Trạng thái Lỗi
    if error:
        return alert_box(
            title="Không thể tải danh sách template",
            message=error,
            tone="crit",
            action=button_danger("Thử lại", id="tmpl-retry-btn", size="xs"),
        )

    # 3. Trạng thái không có dữ liệu
    if items is None or len(items) == 0:
        return empty_state(
            title="Chưa có template nào",
            description="Bắt đầu bằng cách đăng ký template mới hoặc import từ file JSON có sẵn.",
            action=dmc.Anchor(
                button_primary("Đăng ký template", icon="lucide:plus"), href="/templates/new", underline=False
            ),
        )

    # Lọc theo tìm kiếm và trạng thái
    filtered = items
    if search_term:
        term = search_term.lower()
        filtered = [
            it
            for it in filtered
            if term in str(it.get("template_id", "")).lower()
            or term in str(it.get("name", "")).lower()
            or term in str(it.get("file_pattern", "")).lower()
        ]

    if status_filter:
        filtered = [it for it in filtered if it.get("status") == status_filter]

    if len(filtered) == 0:
        return empty_state(
            title="Không có dòng khớp bộ lọc",
            description="Hãy thử thay đổi từ khóa tìm kiếm hoặc bỏ bộ lọc trạng thái.",
        )

    # 4. Trạng thái có dữ liệu: Dựng bảng
    rows = []
    for it in filtered:
        # Chuyển đổi an toàn id sang int
        try:
            id_val = int(it.get("id") or 0)
        except Exception:
            id_val = 0
        tid = it.get("code") or it.get("template_id") or str(id_val)
        action_index = id_val if id_val > 0 else tid
        tname = it.get("name", "")
        fpattern = it.get("file_pattern") or "—"
        fcount = it.get("field_count", 0)
        profiles = it.get("profiles", [])
        version = it.get("current_version") or it.get("version", 1)
        owner = it.get("owner") or it.get("created_by") or "—"
        status = it.get("status", "ACTIVE")

        # Profiles badges
        profile_badges = []
        for p in profiles:
            p_name = p.get("name") or p.get("profile_id", "")
            is_def = p.get("is_default", False)
            if is_def:
                profile_badges.append(
                    dmc.Badge(
                        p_name,
                        color="primary",
                        variant="filled",
                        size="xs",
                        leftSection=DashIconify(icon="lucide:key", width=12),
                    )
                )
            else:
                profile_badges.append(
                    dmc.Badge(
                        p_name,
                        color="gray",
                        variant="light",
                        size="xs",
                    )
                )

        row = html.Tr(
            [
                html.Td(
                    dmc.Text(tid, ff="monospace", fw=600, size="sm"),
                ),
                html.Td(
                    dmc.Stack(
                        [
                            dmc.Text(tname, fw=600, size="sm"),
                            dmc.Text(fpattern, size="xs", c="dimmed", ff="monospace"),
                        ],
                        gap=2,
                    )
                ),
                html.Td(
                    dmc.Badge(f"{fcount} trường", variant="light", color="gray", size="sm"),
                ),
                html.Td(
                    dmc.Group(profile_badges, gap=4),
                ),
                html.Td(
                    dmc.Badge(f"v{version}", variant="outline", color="gray", size="xs"),
                ),
                html.Td(
                    dmc.Text(f"@{owner}", size="sm", c="dimmed"),
                ),
                html.Td(
                    status_chip(status),
                ),
                html.Td(
                    dmc.Group(
                        [
                            dmc.Anchor(
                                button_subtle("Sửa", icon="lucide:edit-3", size="xs"),
                                href=f"/templates/{tid}/edit",
                                underline=False,
                            ),
                            dmc.Anchor(
                                button_subtle("Sơ đồ", icon="lucide:workflow", size="xs"),
                                href=f"/templates/{tid}/diagram",
                                underline=False,
                            ),
                            dmc.Menu(
                                [
                                    dmc.MenuTarget(
                                        dmc.ActionIcon(
                                            DashIconify(icon="lucide:more-vertical", width=16),
                                            variant="subtle",
                                            color="gray",
                                            size="sm",
                                        )
                                    ),
                                    dmc.MenuDropdown(
                                        [
                                            dmc.MenuItem(
                                                "Nhân bản",
                                                id={"type": "tmpl-action-clone", "index": action_index},
                                                leftSection=DashIconify(icon="lucide:copy", width=14),
                                            ),
                                            dmc.MenuItem(
                                                "Export JSON",
                                                id={"type": "tmpl-action-export", "index": action_index},
                                                leftSection=DashIconify(icon="lucide:download", width=14),
                                            ),
                                            dmc.MenuDivider(),
                                            dmc.MenuItem(
                                                "Lưu trữ",
                                                id={"type": "tmpl-action-archive", "index": action_index},
                                                color="red",
                                                leftSection=DashIconify(icon="lucide:archive", width=14),
                                            ),
                                        ]
                                    ),
                                ],
                                position="bottom-end",
                                withArrow=True,
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
        withColumnBorders=False,
        children=[
            html.Thead(
                html.Tr(
                    [
                        html.Th("Mã template"),
                        html.Th("Tên & Nhận diện file"),
                        html.Th("Số trường"),
                        html.Th("Profiles"),
                        html.Th("Phiên bản"),
                        html.Th("Chủ sở hữu"),
                        html.Th("Trạng thái"),
                        html.Th("Thao tác"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
    )

    return dmc.Paper(table, withBorder=True, radius="md", p=0)


def layout() -> Any:
    return dmc.Container(
        [
            dcc.Store(id="tmpl-store-list"),
            dcc.Download(id="tmpl-export-download"),
            dmc.Stack(
                [
                    # Thanh tiêu đề và nút hành động trên cùng
                    dmc.Group(
                        [
                            dmc.Stack(
                                [
                                    dmc.Title("Danh sách template", order=2),
                                    dmc.Text(
                                        "Cấu hình mapping cột Excel và DB, bộ lọc ngày và các profile đối soát.",
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
                                        id="tmpl-refresh-btn",
                                        variant="subtle",
                                        color="gray",
                                        size="lg",
                                    ),
                                    button_subtle("Import JSON", id="tmpl-import-btn", icon="lucide:upload"),
                                    dmc.Anchor(
                                        button_primary("Đăng ký template", icon="lucide:plus"),
                                        href="/templates/new",
                                        underline=False,
                                    ),
                                ],
                                gap="sm",
                            ),
                        ],
                        justify="space-between",
                        align="flex-start",
                    ),
                    # Thanh lọc tìm kiếm và trạng thái
                    dmc.Paper(
                        dmc.Group(
                            [
                                dmc.TextInput(
                                    id="tmpl-filter-search",
                                    placeholder="Tìm kiếm theo mã, tên hoặc mẫu file...",
                                    leftSection=DashIconify(icon="lucide:search", width=16),
                                    style={"flex": 1},
                                ),
                                dmc.Select(
                                    id="tmpl-filter-status",
                                    placeholder="Tất cả trạng thái",
                                    data=[
                                        {"value": "", "label": "Tất cả trạng thái"},
                                        {"value": "ACTIVE", "label": "Đang dùng (ACTIVE)"},
                                        {"value": "DRAFT", "label": "Bản nháp (DRAFT)"},
                                        {"value": "ARCHIVED", "label": "Đã lưu trữ (ARCHIVED)"},
                                    ],
                                    value="",
                                    w=200,
                                ),
                            ],
                            gap="md",
                        ),
                        withBorder=True,
                        p="sm",
                        radius="md",
                    ),
                    # Khối nội dung danh sách template
                    html.Div(id="tmpl-content-container"),
                ],
                gap="lg",
                py="xl",
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
        ],
        size="xl",
    )


# Callbacks xử lý danh sách template
@callback(
    Output("tmpl-store-list", "data"),
    Input("tmpl-refresh-btn", "n_clicks"),
    Input("tmpl-retry-btn", "n_clicks"),
    Input("tmpl-import-submit", "n_clicks"),
    Input("tmpl-clone-submit", "n_clicks"),
    Input("tmpl-archive-modal-confirm", "n_clicks"),
)
def load_templates_data(*args: Any) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return {"items": [], "error": "Chưa đăng nhập"}

    res = list_templates(ctx)
    if not res.ok:
        return {"items": [], "error": res.message}

    items = res.data or []
    return {"items": items, "error": None}


@callback(
    Output("tmpl-content-container", "children"),
    Input("tmpl-store-list", "data"),
    Input("tmpl-filter-search", "value"),
    Input("tmpl-filter-status", "value"),
)
def update_templates_table(store_data: Any, search_val: str | None, status_val: str | None) -> Any:
    if not store_data:
        return render_templates_content(items=None, loading=True)

    items = store_data.get("items")
    error = store_data.get("error")

    return render_templates_content(
        items=items,
        loading=False,
        error=error,
        search_term=search_val or "",
        status_filter=status_val or "",
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
    return not is_opened


# Callback thực hiện Import JSON
@callback(
    Output("tmpl-import-alert", "children"),
    Input("tmpl-import-submit", "n_clicks"),
    State("tmpl-import-upload", "contents"),
    State("tmpl-import-overwrite", "checked"),
    prevent_initial_call=True,
)
def handle_import_template(n_clicks: Any, contents: str | None, overwrite: bool) -> Any:
    if not contents:
        return alert_box("Lỗi", "Vui lòng chọn hoặc kéo thả file JSON cần import", tone="crit")

    try:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string).decode("utf-8")
        parsed_data = json.loads(decoded)
        if not isinstance(parsed_data, dict):
            return alert_box("Lỗi", "Dữ liệu JSON phải là đối tượng cấu hình", tone="crit")

        ctx = get_current_ctx()
        if ctx is None:
            return alert_box("Lỗi", "Chưa đăng nhập", tone="crit")

        res = import_template(ctx, parsed_data, overwrite=overwrite)
        if not res.ok:
            return alert_box("Không thể import", res.message, tone="crit")

        return alert_box(
            "Thành công",
            f"Đã nạp thành công template {res.data.get('code') if isinstance(res.data, dict) else ''}",
            tone="ok",
        )
    except Exception as e:
        return alert_box("Lỗi định dạng", f"File không đúng định dạng JSON: {e}", tone="crit")


# Callback mở modal Clone
@callback(
    Output("tmpl-clone-modal", "opened"),
    Output("tmpl-clone-source-id", "data"),
    Input({"type": "tmpl-action-clone", "index": ALL}, "n_clicks"),
    Input("tmpl-clone-cancel", "n_clicks"),
    State("tmpl-clone-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_clone_modal(clone_clicks: list[Any], cancel_clicks: Any, is_opened: bool) -> tuple[bool, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, None

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]
    if "tmpl-clone-cancel" in trigger_id:
        return False, None

    try:
        parsed = json.loads(trigger_id)
        source_id = parsed.get("index")
        return True, source_id
    except Exception:
        return False, None


# Callback thực hiện Clone
@callback(
    Output("tmpl-clone-alert", "children"),
    Input("tmpl-clone-submit", "n_clicks"),
    State("tmpl-clone-source-id", "data"),
    State("tmpl-clone-target-id", "value"),
    State("tmpl-clone-target-name", "value"),
    prevent_initial_call=True,
)
def handle_clone_template(n_clicks: Any, source_id: Any, target_id: str | None, target_name: str | None) -> Any:
    if not source_id or not target_id:
        return alert_box("Lỗi", "Vui lòng nhập mã template mới", tone="crit")

    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Lỗi", "Chưa đăng nhập", tone="crit")

    try:
        src_id_int = int(source_id)
    except Exception:
        return alert_box("Lỗi", "ID template nguồn không hợp lệ", tone="crit")

    new_code = target_id.strip().upper()
    new_name = target_name.strip() if target_name else new_code
    res = clone_template(ctx, src_id_int, new_code=new_code, new_name=new_name)
    if not res.ok:
        return alert_box("Không thể nhân bản", res.message, tone="crit")

    return alert_box("Thành công", f"Đã nhân bản thành công template {target_id}", tone="ok")


# Callback mở modal Archive
@callback(
    Output("tmpl-archive-modal", "opened"),
    Output("tmpl-archive-target-id", "data"),
    Input({"type": "tmpl-action-archive", "index": ALL}, "n_clicks"),
    Input("tmpl-archive-modal-cancel", "n_clicks"),
    State("tmpl-archive-modal", "opened"),
    prevent_initial_call=True,
)
def toggle_archive_modal(archive_clicks: list[Any], cancel_clicks: Any, is_opened: bool) -> tuple[bool, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, None

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]
    if "tmpl-archive-modal-cancel" in trigger_id:
        return False, None

    try:
        parsed = json.loads(trigger_id)
        target_id = parsed.get("index")
        return True, target_id
    except Exception:
        return False, None


# Callback thực hiện Archive
@callback(
    Output("tmpl-archive-modal", "opened", allow_duplicate=True),
    Input("tmpl-archive-modal-confirm", "n_clicks"),
    State("tmpl-archive-target-id", "data"),
    prevent_initial_call=True,
)
def handle_archive_template(n_clicks: Any, target_id: Any) -> bool:
    if target_id is not None:
        try:
            tid_int = int(target_id)
            ctx = get_current_ctx()
            if ctx:
                archive_template(ctx, tid_int)
        except Exception:
            pass
    return False


# Callback thực hiện Export JSON
@callback(
    Output("tmpl-export-download", "data"),
    Input({"type": "tmpl-action-export", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_export_template(export_clicks: list[Any]) -> Any:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return None

    trigger_id = ctx_dash.triggered[0]["prop_id"].split(".")[0]
    try:
        parsed = json.loads(trigger_id)
        target_id = parsed.get("index")
        if target_id is not None:
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
