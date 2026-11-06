"""Màn chi tiết Bộ đối soát — Bước 8 task 18 (Screen13).

/batches/<id>: thông tin bộ, kỳ thử + xem trước tham số, cảnh báo template
Archived, bảng mục (sửa inline), hộp thoại Thêm template, lưu bộ.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.context import Role
from app.core.session import get_current_ctx
from app.services.batch_def import (
    activate_batch_def,
    add_batch_def_items,
    addable_templates,
    archive_batch_def,
    get_batch_def,
    preview_params,
    remove_batch_def_item,
    update_batch_def,
    update_batch_def_item,
)
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.status_chip import status_chip

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path_template="/batches/<def_id>",
        path="/batches/1",
        title="Bộ đối soát – ReconHub",
    )
except Exception:
    pass

MENU_CODE = "batch_def"


def _can_write(ctx: Any) -> bool:
    if ctx is None:
        return False
    return Role.ADMIN in ctx.roles or Role.TEMPLATE_OWNER in ctx.roles


def _params_text(override: Any) -> str:
    if not override:
        return ""
    try:
        return json.dumps(override, ensure_ascii=False)
    except Exception:
        return ""


def render_def_items_table(
    items: list[dict[str, Any]],
    can_write: bool = False,
) -> Any:
    """Hàm thuần dựng bảng mục của bộ (sửa inline khi có quyền)."""
    if not items:
        return empty_state(
            title="Bộ chưa có template nào",
            description="Thêm template đã đăng ký vào bộ để chạy chung mỗi kỳ.",
        )
    rows = []
    for it in items:
        item_id = int(it.get("id") or 0)
        archived = str(it.get("template_status", "")) == "ARCHIVED"
        override_text = _params_text(it.get("params_override") or {})
        ds_text = f"DS #{it['data_source_id']}" if it.get("data_source_id") else "Mặc định template"
        profile = str(it.get("profile_code") or "—")
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(str(it.get("seq_no", "")), size="sm")),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Group(
                                    [
                                        dmc.Text(str(it.get("template_name", "")), fw=600, size="sm"),
                                        status_chip("ARCHIVED", label="Đã lưu trữ")
                                        if archived
                                        else dmc.Text("", size="xs"),
                                    ],
                                    gap="xs",
                                ),
                                dmc.Text(
                                    f"{it.get('template_code', '')} · Profile {profile}",
                                    size="xs",
                                    c="dimmed",
                                    className="rh-code",
                                ),
                            ],
                            gap=2,
                        )
                    ),
                    dmc.TableTd(dmc.Text(str(it.get("template_version") or "—"), size="sm")),
                    dmc.TableTd(
                        dmc.TextInput(
                            id={"type": "bdef-item-pattern", "index": item_id},
                            value=str(it.get("file_pattern", "")),
                            disabled=not can_write,
                            size="xs",
                            style={"minWidth": 140},
                        )
                    ),
                    dmc.TableTd(
                        dmc.Checkbox(
                            id={"type": "bdef-item-multi", "index": item_id},
                            checked=bool(it.get("multi_file")),
                            disabled=not can_write,
                        )
                    ),
                    dmc.TableTd(
                        dmc.Checkbox(
                            id={"type": "bdef-item-required", "index": item_id},
                            checked=bool(it.get("is_required")),
                            disabled=not can_write,
                        )
                    ),
                    dmc.TableTd(
                        dmc.NumberInput(
                            id={"type": "bdef-item-priority", "index": item_id},
                            value=int(it.get("priority") or 100),
                            min=1,
                            max=1000,
                            step=1,
                            disabled=not can_write,
                            size="xs",
                            style={"width": 90},
                        )
                    ),
                    dmc.TableTd(dmc.Text(ds_text, size="xs", c="dimmed")),
                    dmc.TableTd(
                        dmc.TextInput(
                            id={"type": "bdef-item-params", "index": item_id},
                            value=override_text,
                            placeholder="{}",
                            disabled=not can_write,
                            size="xs",
                            style={"minWidth": 160},
                        )
                    ),
                    dmc.TableTd(
                        button_danger(
                            "Gỡ",
                            id={"type": "bdef-item-remove", "index": item_id},
                            icon="lucide:x",
                            size="xs",
                        )
                        if can_write
                        else dmc.Text(""),
                    ),
                ]
            )
        )
    return dmc.Table(
        [
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh("#"),
                        dmc.TableTh("Template"),
                        dmc.TableTh("Version"),
                        dmc.TableTh("Mẫu tên file"),
                        dmc.TableTh("Gộp"),
                        dmc.TableTh("Bắt buộc"),
                        dmc.TableTh("Ưu tiên"),
                        dmc.TableTh("Data Source"),
                        dmc.TableTh("Tham số ghi đè"),
                        dmc.TableTh(""),
                    ]
                )
            ),
            dmc.TableTbody(rows),
        ],
        striped=True,
        highlightOnHover=True,
    )


def render_preview_result(preview: dict[str, Any] | None, error: str | None = None) -> Any:
    """Hàm thuần dựng bảng xem trước tham số với kỳ thử."""
    if error:
        return alert_box(title="Không xem trước được tham số", message=error, tone="crit")
    if preview is None:
        return dmc.Text("Nhập kỳ (YYYY-MM) rồi bấm Xem trước tham số.", size="sm", c="dimmed")
    items = preview.get("items") or []
    if not items:
        return empty_state(title="Bộ chưa có mục nào", description="Thêm template vào bộ trước.")
    rows = []
    for it in items:
        params = it.get("params") or {}
        errors = it.get("errors") or []
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(str(it.get("template_code", "")), className="rh-code", size="sm")),
                    dmc.TableTd(
                        dmc.Text(
                            json.dumps(params, ensure_ascii=False),
                            size="xs",
                            className="rh-code",
                            style={"whiteSpace": "pre-wrap", "wordBreak": "break-all"},
                        )
                    ),
                    dmc.TableTd(
                        dmc.Text(
                            "; ".join(str(e.get("message") or e) for e in errors),
                            size="xs",
                            c="red",
                        )
                        if errors
                        else dmc.Text("Hợp lệ", size="xs", c="teal")
                    ),
                ]
            )
        )
    return dmc.Table(
        [
            dmc.TableThead(dmc.TableTr([dmc.TableTh("Template"), dmc.TableTh("Giá trị đã tính"), dmc.TableTh("Lỗi")])),
            dmc.TableTbody(rows),
        ],
        striped=True,
    )


def render_addable_list(
    templates: list[dict[str, Any]] | None,
    error: str | None = None,
) -> Any:
    """Hàm thuần dựng danh sách template trong hộp thoại Thêm template."""
    if error:
        return alert_box(title="Không tải được danh sách template", message=error, tone="crit")
    if not templates:
        return empty_state(
            title="Không có template nào khớp",
            description="Thử thay đổi từ khóa tìm kiếm hoặc bỏ lọc.",
        )
    rows = []
    for t in templates:
        tid = int(t.get("template_id") or 0)
        addable = bool(t.get("addable"))
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Checkbox(
                            id={"type": "bdef-add-check", "index": tid},
                            disabled=not addable,
                        )
                    ),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(str(t.get("code", "")), fw=600, size="sm", className="rh-code"),
                                dmc.Text(str(t.get("name", "")), size="xs", c="dimmed"),
                            ],
                            gap=0,
                        )
                    ),
                    dmc.TableTd(status_chip(str(t.get("status", "")))),
                    dmc.TableTd(dmc.Text(str(t.get("version") or "—"), size="sm")),
                    dmc.TableTd(
                        dmc.Text(
                            str(t.get("reason") or "Thêm được"),
                            size="xs",
                            c="red" if not addable else "dimmed",
                        )
                    ),
                ]
            )
        )
    return dmc.Table(
        [
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh(""),
                        dmc.TableTh("Template"),
                        dmc.TableTh("Trạng thái"),
                        dmc.TableTh("Version"),
                        dmc.TableTh("Ghi chú"),
                    ]
                )
            ),
            dmc.TableTbody(rows),
        ],
        striped=True,
    )


def layout(def_id: str | int | None = 1, **kwargs: Any) -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return dmc.Container(
            [
                dcc.Location(id="bdef-edit-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang Bộ đối soát.", tone="crit"),
            ]
        )
    try:
        def_id_int = int(def_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return dmc.Container(alert_box("Bộ đối soát không hợp lệ.", tone="crit"))
    trial_period = datetime.now().strftime("%Y-%m")
    return dmc.Container(
        [
            dcc.Store(id="bdef-edit-store"),
            dcc.Store(id="bdef-edits-store", data={}),
            dcc.Store(id="bdef-remove-target"),
            dcc.Store(id="bdef-def-id", data=def_id_int),
            dcc.Store(id="bdef-addable-store"),
            dcc.Location(id="bdef-edit-redirect", refresh=True),
            dmc.Stack(
                [
                    dmc.Anchor(
                        dmc.Group(
                            [
                                DashIconify(icon="lucide:arrow-left", width=16),
                                dmc.Text("Quay lại danh sách bộ", size="sm"),
                            ],
                            gap="xs",
                        ),
                        href="/batches",
                        underline=False,
                    ),
                    html.Div(id="bdef-edit-header"),
                    html.Div(id="bdef-edit-alert"),
                    html.Div(id="bdef-edit-content"),
                    dmc.Paper(
                        dmc.Stack(
                            [
                                dmc.Title("Kỳ thử và xem trước tham số", order=4),
                                dmc.Group(
                                    [
                                        dmc.TextInput(
                                            id="bdef-trial-period",
                                            label="Kỳ thử (YYYY-MM)",
                                            value=trial_period,
                                            style={"width": 160},
                                        ),
                                        button_primary("Xem trước tham số", id="bdef-preview-btn", icon="lucide:eye"),
                                    ],
                                    align="flex-end",
                                    gap="sm",
                                ),
                                html.Div(id="bdef-preview-content"),
                            ],
                            gap="sm",
                        ),
                        p="md",
                        withBorder=True,
                    ),
                    dmc.Modal(
                        id="bdef-add-modal",
                        title="Thêm template vào bộ",
                        size="xl",
                        centered=True,
                        children=[
                            dmc.Stack(
                                [
                                    dmc.Group(
                                        [
                                            dmc.TextInput(
                                                id="bdef-add-search",
                                                placeholder="Tìm theo mã hoặc tên template",
                                                leftSection=DashIconify(icon="lucide:search", width=16),
                                                style={"flex": 1},
                                            ),
                                            dmc.Select(
                                                id="bdef-add-filter",
                                                data=[
                                                    {"label": "Chỉ template thêm được", "value": "addable"},
                                                    {"label": "Tất cả", "value": "all"},
                                                ],
                                                value="addable",
                                                style={"width": 220},
                                            ),
                                        ],
                                        gap="sm",
                                    ),
                                    html.Div(id="bdef-add-list"),
                                    html.Div(id="bdef-add-config"),
                                    dmc.Group(
                                        [
                                            button_subtle("Hủy", id="bdef-add-cancel"),
                                            button_primary("Thêm template", id="bdef-add-submit"),
                                        ],
                                        justify="flex-end",
                                        gap="sm",
                                    ),
                                ],
                                gap="sm",
                            )
                        ],
                    ),
                    modal_confirm(
                        id="bdef-remove-modal",
                        title="Gỡ template khỏi bộ",
                        description="Template sẽ được gỡ khỏi bộ đối soát. Các lần chạy bộ cũ không bị ảnh hưởng.",
                        confirm_label="Gỡ khỏi bộ",
                    ),
                    modal_confirm(
                        id="bdef-archive-modal",
                        title="Lưu trữ bộ đối soát",
                        description="Bộ đối soát đã lưu trữ không thể tạo lần chạy mới. Các lần chạy cũ vẫn xem được.",
                        confirm_label="Lưu trữ",
                    ),
                ],
                gap="md",
            ),
        ]
    )


@callback(
    Output("bdef-edit-store", "data"),
    Input("bdef-def-id", "data"),
)
def _load_def(def_id: int) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return {"error": "Bạn cần đăng nhập để xem bộ đối soát."}
    res = get_batch_def(ctx, def_id)
    if not res.ok:
        return {"error": res.message or "Không tìm thấy bộ đối soát."}
    return res.data


@callback(
    Output("bdef-edit-header", "children"),
    Output("bdef-edit-content", "children"),
    Input("bdef-edit-store", "data"),
)
def _render_def(store_data: Any) -> tuple[Any, Any]:
    ctx = get_current_ctx()
    can_write = _can_write(ctx)
    if store_data is None:
        return None, dmc.Stack([dmc.Skeleton(height=48, radius="md") for _ in range(4)], gap="sm")
    if isinstance(store_data, dict) and store_data.get("error"):
        return None, alert_box(title="Không thể tải bộ đối soát", message=str(store_data["error"]), tone="crit")
    items = store_data.get("items") or []
    archived = [it for it in items if str(it.get("template_status", "")) == "ARCHIVED"]
    header = dmc.Group(
        [
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.Title(f"{store_data.get('code', '')} — {store_data.get('name', '')}", order=2),
                            status_chip(str(store_data.get("status", "DRAFT"))),
                        ],
                        gap="sm",
                    ),
                    dmc.Text(
                        str(store_data.get("description") or ""),
                        size="sm",
                        c="dimmed",
                    )
                    if store_data.get("description")
                    else dmc.Text("", size="sm"),
                ],
                gap=2,
            ),
            dmc.Group(
                [
                    button_primary("Thêm template", icon="lucide:plus", id="bdef-add-open-btn")
                    if can_write
                    else dmc.Text(""),
                    button_subtle("Kích hoạt", id="bdef-activate-btn", icon="lucide:play")
                    if can_write and store_data.get("status") == "DRAFT"
                    else dmc.Text(""),
                    button_subtle("Lưu trữ", id="bdef-archive-btn", icon="lucide:archive")
                    if can_write and store_data.get("status") != "ARCHIVED"
                    else dmc.Text(""),
                ],
                gap="sm",
            ),
        ],
        justify="space-between",
        align="flex-start",
    )
    content = dmc.Stack(
        [
            alert_box(
                title="Có template đã lưu trữ trong bộ",
                message="Các mục dùng template đã lưu trữ sẽ bị bỏ qua khi tạo lần chạy bộ: "
                + ", ".join(str(it.get("template_code", "")) for it in archived)
                + ".",
                tone="warn",
            )
            if archived
            else None,
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Title("Thông tin bộ", order=4),
                        dmc.Group(
                            [
                                dmc.TextInput(
                                    id="bdef-info-code",
                                    label="Mã bộ",
                                    value=str(store_data.get("code", "")),
                                    disabled=True,
                                    style={"width": 260},
                                ),
                                dmc.TextInput(
                                    id="bdef-info-name",
                                    label="Tên bộ",
                                    value=str(store_data.get("name", "")),
                                    disabled=not can_write,
                                    style={"flex": 1},
                                ),
                                dmc.NumberInput(
                                    id="bdef-info-max-parallel",
                                    label="Song song mỗi Data Source",
                                    value=int(store_data.get("max_parallel_per_ds") or 2),
                                    min=1,
                                    max=4,
                                    step=1,
                                    disabled=not can_write,
                                    style={"width": 200},
                                ),
                            ],
                            gap="sm",
                        ),
                        dmc.Textarea(
                            id="bdef-info-desc",
                            label="Mô tả",
                            value=str(store_data.get("description") or ""),
                            disabled=not can_write,
                            autosize=True,
                            minRows=2,
                        ),
                    ],
                    gap="sm",
                ),
                p="md",
                withBorder=True,
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Title("Danh sách template trong bộ", order=4),
                                dmc.Text(f"{len(items)} mục", size="sm", c="dimmed"),
                            ],
                            justify="space-between",
                        ),
                        render_def_items_table(items, can_write=can_write),
                    ],
                    gap="sm",
                ),
                p="md",
                withBorder=True,
            ),
            dmc.Group(
                [
                    dmc.Text(id="bdef-dirty-hint", size="sm", c="dimmed"),
                    button_primary("Lưu bộ đối soát", id="bdef-save-btn", icon="lucide:save")
                    if can_write
                    else dmc.Text(""),
                ],
                justify="space-between",
            ),
        ],
        gap="md",
    )
    return header, content


@callback(
    Output("bdef-edits-store", "data"),
    Output("bdef-dirty-hint", "children"),
    Input({"type": "bdef-item-pattern", "index": ALL}, "value"),
    Input({"type": "bdef-item-multi", "index": ALL}, "checked"),
    Input({"type": "bdef-item-required", "index": ALL}, "checked"),
    Input({"type": "bdef-item-priority", "index": ALL}, "value"),
    Input({"type": "bdef-item-params", "index": ALL}, "value"),
    State("bdef-edits-store", "data"),
    State("bdef-edit-store", "data"),
    prevent_initial_call=True,
)
def _track_item_edits(
    patterns: Any, multis: Any, requireds: Any, priorities: Any, params_list: Any, edits: Any, store_data: Any
) -> tuple[Any, Any]:
    if not store_data or store_data.get("error"):
        return dash.no_update, ""
    originals = {int(it["id"]): it for it in (store_data.get("items") or [])}
    new_edits: dict[str, Any] = dict(edits or {})
    fields = [
        ("file_pattern", patterns),
        ("multi_file", multis),
        ("is_required", requireds),
        ("priority", priorities),
        ("params_override", params_list),
    ]
    # Ghép theo thứ tự hàng trong bảng (cùng thứ tự items).
    item_ids = [int(it["id"]) for it in (store_data.get("items") or [])]
    for pos, item_id in enumerate(item_ids):
        orig = originals[item_id]
        changed: dict[str, Any] = {}
        for key, values in fields:
            if values is None or pos >= len(values):
                continue
            val = values[pos]
            if key == "params_override":
                cur = _params_text(orig.get("params_override") or {})
                if (val or "") != cur:
                    changed[key] = val or ""
            elif key in ("multi_file", "is_required"):
                if bool(val) != bool(orig.get(key)):
                    changed[key] = bool(val)
            elif key == "priority":
                try:
                    if int(val or 0) != int(orig.get("priority") or 0):
                        changed[key] = int(val or 0)
                except (TypeError, ValueError):
                    pass
            else:
                if (val or "") != str(orig.get(key) or ""):
                    changed[key] = val or ""
        if changed:
            new_edits[str(item_id)] = changed
        else:
            new_edits.pop(str(item_id), None)
    hint = f"Có {len(new_edits)} mục thay đổi chưa lưu." if new_edits else ""
    return new_edits, hint


@callback(
    Output("bdef-edit-alert", "children"),
    Output("bdef-edit-store", "data", allow_duplicate=True),
    Output("bdef-edits-store", "data", allow_duplicate=True),
    Output("bdef-dirty-hint", "children", allow_duplicate=True),
    Input("bdef-save-btn", "n_clicks"),
    State("bdef-def-id", "data"),
    State("bdef-edit-store", "data"),
    State("bdef-edits-store", "data"),
    State("bdef-info-name", "value"),
    State("bdef-info-desc", "value"),
    State("bdef-info-max-parallel", "value"),
    prevent_initial_call=True,
)
def _save_def(
    _n: Any,
    def_id: int,
    store_data: Any,
    edits: Any,
    name: str | None,
    desc: str | None,
    max_parallel: Any,
) -> tuple[Any, Any, Any, Any]:
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập.", tone="crit"), dash.no_update, dash.no_update, ""
    if not store_data or store_data.get("error"):
        return alert_box("Chưa tải được bộ đối soát.", tone="crit"), dash.no_update, dash.no_update, ""
    errors: list[str] = []
    if (
        (name or "").strip() != str(store_data.get("name", ""))
        or (desc or "") != str(store_data.get("description") or "")
        or int(max_parallel or 2) != int(store_data.get("max_parallel_per_ds") or 2)
    ):
        res = update_batch_def(
            ctx,
            def_id,
            {
                "name": (name or "").strip(),
                "description": (desc or "").strip() or None,
                "max_parallel_per_ds": int(max_parallel or 2),
            },
            row_version=int(store_data.get("row_version") or 0),
        )
        if not res.ok:
            errors.append(res.message or "Không lưu được thông tin bộ.")
    for item_id_str, changed in (edits or {}).items():
        payload: dict[str, Any] = {}
        if "file_pattern" in changed:
            payload["file_pattern"] = changed["file_pattern"]
        if "multi_file" in changed:
            payload["multi_file"] = changed["multi_file"]
        if "is_required" in changed:
            payload["is_required"] = changed["is_required"]
        if "priority" in changed:
            payload["priority"] = changed["priority"]
        if "params_override" in changed:
            raw = (changed["params_override"] or "").strip()
            if raw == "":
                payload["params_override"] = {}
            else:
                try:
                    parsed = json.loads(raw)
                except Exception:
                    errors.append(f"Mục #{item_id_str}: tham số ghi đè không phải JSON hợp lệ.")
                    continue
                if not isinstance(parsed, dict):
                    errors.append(f"Mục #{item_id_str}: tham số ghi đè phải là một object JSON.")
                    continue
                payload["params_override"] = parsed
        orig = next((it for it in (store_data.get("items") or []) if int(it["id"]) == int(item_id_str)), None)
        res = update_batch_def_item(
            ctx,
            int(item_id_str),
            payload,
            row_version=int(orig["row_version"]) if orig else None,
        )
        if not res.ok:
            errors.append(res.message or f"Không lưu được mục #{item_id_str}.")
    if errors:
        return alert_box("; ".join(errors), tone="crit"), dash.no_update, dash.no_update, ""
    refreshed = get_batch_def(ctx, def_id)
    if not refreshed.ok:
        return alert_box(refreshed.message or "Không tải lại được bộ.", tone="crit"), dash.no_update, dash.no_update, ""
    return (
        alert_box("Đã lưu bộ đối soát.", tone="ok"),
        refreshed.data,
        {},
        "",
    )


@callback(
    Output("bdef-add-modal", "opened"),
    Input("bdef-add-open-btn", "n_clicks"),
    Input("bdef-add-cancel", "n_clicks"),
    State("bdef-add-modal", "opened"),
    prevent_initial_call=True,
)
def _toggle_add_modal(_open: Any, _cancel: Any, opened: bool) -> bool:
    return not opened


@callback(
    Output("bdef-add-list", "children"),
    Output("bdef-addable-store", "data"),
    Input("bdef-add-modal", "opened"),
    Input("bdef-add-search", "value"),
    Input("bdef-add-filter", "value"),
    State("bdef-def-id", "data"),
)
def _load_addable(opened: bool, search: str | None, filter_value: str | None, def_id: int) -> tuple[Any, Any]:
    if not opened:
        return None, dash.no_update
    ctx = get_current_ctx()
    if ctx is None:
        return render_addable_list(None, error="Bạn cần đăng nhập."), None
    res = addable_templates(ctx, def_id, q=(search or "").strip() or None, include_unavailable=(filter_value == "all"))
    if not res.ok:
        return render_addable_list(None, error=res.message), None
    return render_addable_list(res.data), res.data


@callback(
    Output("bdef-add-config", "children"),
    Input({"type": "bdef-add-check", "index": ALL}, "checked"),
    Input({"type": "bdef-add-check", "index": ALL}, "id"),
    State("bdef-addable-store", "data"),
)
def _render_add_config(checked_list: Any, check_ids: Any, addable: Any) -> Any:
    selected = [int(c["index"]) for c, v in zip(check_ids or [], checked_list or [], strict=False) if v]
    if not selected:
        return None
    by_id = {int(t["template_id"]): t for t in (addable or [])}
    blocks: list[Any] = [dmc.Divider(label="Cách chạy trong bộ cho các template đã chọn", labelPosition="left")]
    for tmpl_id in selected:
        t = by_id.get(tmpl_id, {})
        code = str(t.get("code", ""))
        blocks.append(
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text(f"{code} — {t.get('name', '')}", fw=600, size="sm"),
                        dmc.Group(
                            [
                                dmc.TextInput(
                                    id={"type": "bdef-add-pattern", "index": tmpl_id},
                                    label="Mẫu tên file",
                                    value=f"*{code}*",
                                    style={"flex": 1},
                                ),
                                dmc.NumberInput(
                                    id={"type": "bdef-add-priority", "index": tmpl_id},
                                    label="Ưu tiên",
                                    value=100,
                                    min=1,
                                    max=1000,
                                    step=1,
                                    style={"width": 110},
                                ),
                                dmc.Checkbox(
                                    id={"type": "bdef-add-required", "index": tmpl_id},
                                    label="Bắt buộc",
                                    checked=True,
                                ),
                                dmc.Checkbox(
                                    id={"type": "bdef-add-multi", "index": tmpl_id},
                                    label="Gộp nhiều file",
                                    checked=True,
                                ),
                            ],
                            gap="sm",
                            align="flex-end",
                        ),
                    ],
                    gap="xs",
                ),
                p="sm",
                withBorder=True,
            )
        )
    return dmc.Stack(blocks, gap="sm")


@callback(
    Output("bdef-edit-alert", "children", allow_duplicate=True),
    Output("bdef-edit-store", "data", allow_duplicate=True),
    Output("bdef-add-modal", "opened", allow_duplicate=True),
    Input("bdef-add-submit", "n_clicks"),
    State("bdef-def-id", "data"),
    State({"type": "bdef-add-check", "index": ALL}, "checked"),
    State({"type": "bdef-add-check", "index": ALL}, "id"),
    State({"type": "bdef-add-pattern", "index": ALL}, "value"),
    State({"type": "bdef-add-pattern", "index": ALL}, "id"),
    State({"type": "bdef-add-required", "index": ALL}, "checked"),
    State({"type": "bdef-add-required", "index": ALL}, "id"),
    State({"type": "bdef-add-multi", "index": ALL}, "checked"),
    State({"type": "bdef-add-multi", "index": ALL}, "id"),
    State({"type": "bdef-add-priority", "index": ALL}, "value"),
    State({"type": "bdef-add-priority", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def _submit_add_templates(
    _n: Any,
    def_id: int,
    checked_list: Any,
    check_ids: Any,
    patterns: Any,
    pattern_ids: Any,
    requireds: Any,
    required_ids: Any,
    multis: Any,
    multi_ids: Any,
    priorities: Any,
    priority_ids: Any,
) -> tuple[Any, Any, bool]:
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập.", tone="crit"), dash.no_update, True
    selected = [int(c["index"]) for c, v in zip(check_ids or [], checked_list or [], strict=False) if v]
    if not selected:
        return alert_box("Chưa chọn template nào để thêm.", tone="warn"), dash.no_update, True
    by_index: dict[str, dict[str, Any]] = {}
    for values, ids in [
        (patterns, pattern_ids),
        (requireds, required_ids),
        (multis, multi_ids),
        (priorities, priority_ids),
    ]:
        for val, ident in zip(values or [], ids or [], strict=False):
            by_index.setdefault(str(ident["index"]), {})[str(ident["type"])] = val
    # Lấy mã template để gợi ý mẫu tên file mặc định.
    addable = addable_templates(ctx, def_id, include_unavailable=True)
    code_by_id = {}
    if addable.ok:
        code_by_id = {int(t["template_id"]): str(t["code"]) for t in (addable.data or [])}
    items: list[dict[str, Any]] = []
    for tmpl_id in selected:
        cfg = by_index.get(str(tmpl_id), {})
        pattern = cfg.get("bdef-add-pattern") or f"*{code_by_id.get(tmpl_id, '')}*"
        items.append(
            {
                "template_id": tmpl_id,
                "file_pattern": pattern,
                "multi_file": bool(cfg.get("bdef-add-multi", True)),
                "is_required": bool(cfg.get("bdef-add-required", True)),
                "priority": int(cfg.get("bdef-add-priority") or 100),
                "params_override": {},
            }
        )
    res = add_batch_def_items(ctx, def_id, items)
    if not res.ok:
        return alert_box(res.message or "Không thêm được template.", tone="crit"), dash.no_update, True
    refreshed = get_batch_def(ctx, def_id)
    if not refreshed.ok:
        return alert_box(refreshed.message or "Không tải lại được bộ.", tone="crit"), dash.no_update, True
    return alert_box(f"Đã thêm {len(items)} template vào bộ.", tone="ok"), refreshed.data, False


@callback(
    Output("bdef-remove-modal", "opened"),
    Output("bdef-remove-target", "data"),
    Input({"type": "bdef-item-remove", "index": ALL}, "n_clicks"),
    Input("bdef-remove-modal-cancel", "n_clicks"),
    State("bdef-remove-modal", "opened"),
    prevent_initial_call=True,
)
def _open_remove_modal(_remove: Any, _cancel: Any, opened: bool) -> tuple[bool, Any]:
    triggered = dash.callback_context.triggered_id
    if isinstance(triggered, dict) and triggered.get("type") == "bdef-item-remove":
        return True, {"item_id": triggered["index"]}
    return False, dash.no_update


@callback(
    Output("bdef-edit-alert", "children", allow_duplicate=True),
    Output("bdef-edit-store", "data", allow_duplicate=True),
    Output("bdef-remove-modal", "opened", allow_duplicate=True),
    Input("bdef-remove-modal-confirm", "n_clicks"),
    State("bdef-remove-target", "data"),
    State("bdef-def-id", "data"),
    prevent_initial_call=True,
)
def _confirm_remove_item(_n: Any, target: Any, def_id: int) -> tuple[Any, Any, bool]:
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập.", tone="crit"), dash.no_update, False
    if not target or not target.get("item_id"):
        return dash.no_update, dash.no_update, False
    res = remove_batch_def_item(ctx, int(target["item_id"]))
    if not res.ok:
        return alert_box(res.message or "Không gỡ được template.", tone="crit"), dash.no_update, False
    refreshed = get_batch_def(ctx, def_id)
    if not refreshed.ok:
        return alert_box(refreshed.message or "Không tải lại được bộ.", tone="crit"), dash.no_update, False
    return alert_box("Đã gỡ template khỏi bộ.", tone="ok"), refreshed.data, False


@callback(
    Output("bdef-archive-modal", "opened"),
    Input("bdef-archive-btn", "n_clicks"),
    Input("bdef-archive-modal-cancel", "n_clicks"),
    State("bdef-archive-modal", "opened"),
    prevent_initial_call=True,
)
def _toggle_archive_modal(_open: Any, _cancel: Any, opened: bool) -> bool:
    return not opened


@callback(
    Output("bdef-edit-alert", "children", allow_duplicate=True),
    Output("bdef-edit-store", "data", allow_duplicate=True),
    Output("bdef-archive-modal", "opened", allow_duplicate=True),
    Input("bdef-archive-modal-confirm", "n_clicks"),
    Input("bdef-activate-btn", "n_clicks"),
    State("bdef-def-id", "data"),
    prevent_initial_call=True,
)
def _run_def_action(_confirm: Any, _activate: Any, def_id: int) -> tuple[Any, Any, bool]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập.", tone="crit"), dash.no_update, False
    if triggered == "bdef-activate-btn":
        res = activate_batch_def(ctx, def_id)
        action_name = "kích hoạt"
    else:
        res = archive_batch_def(ctx, def_id)
        action_name = "lưu trữ"
    if not res.ok:
        return alert_box(res.message or f"Không {action_name} được bộ.", tone="crit"), dash.no_update, False
    refreshed = get_batch_def(ctx, def_id)
    if not refreshed.ok:
        return alert_box(refreshed.message or "Không tải lại được bộ.", tone="crit"), dash.no_update, False
    return alert_box(f"Đã {action_name} bộ đối soát.", tone="ok"), refreshed.data, False


@callback(
    Output("bdef-preview-content", "children"),
    Input("bdef-preview-btn", "n_clicks"),
    State("bdef-def-id", "data"),
    State("bdef-trial-period", "value"),
    prevent_initial_call=True,
)
def _run_preview(_n: Any, def_id: int, period: str | None) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return render_preview_result(None, error="Bạn cần đăng nhập.")
    res = preview_params(ctx, def_id, (period or "").strip())
    if not res.ok:
        return render_preview_result(None, error=res.message)
    return render_preview_result(res.data)
