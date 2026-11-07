"""Wizard chạy bộ đối soát — Bước 9 task 18 (Screen13).

`/batch-runs/new?def=<id>` tạo lần chạy bộ (bước 1) và `/batch-runs/<id>`
chạy các bước 2–5. Trạng thái lưu ở DB (lần chạy DRAFT), tải lại trang
không mất công việc. Stepper chỉ hiển thị, bước hiện tại lưu ở dcc.Store.
Phong cách Fluent Compact + Master–Detail theo designs/components/Screen13-BatchRun.
"""

from __future__ import annotations

import base64
import re
from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.batch_run import (
    add_files,
    assign_file,
    cancel,
    create_batch_run,
    get_batch_run,
    ignore_file,
    list_active_defs,
    list_batch_runs,
    precheck,
    replace_files,
    set_param_override,
    skip_item,
    start,
    update_batch_run_data_source,
)
from app.services.data_source import options_data_sources
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import (
    notify_error,
    notify_info,
    notify_success,
    notify_warning,
)
from app.ui.components.page_header import page_header
from app.ui.components.status_chip import item_status_badge, run_status_badge

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path_template="/batch-runs/<run_id>",
        path="/batch-runs",
        title="Chạy bộ đối soát — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "batch_run"
STEP_LABELS = ["Chọn bộ và kỳ", "Tải và ghép file", "Tham số", "Kiểm tra trước", "Thực thi"]
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def current_month_period() -> str:
    return datetime.now().strftime("%Y-%m")


def format_param_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _matched_files(item: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in (item.get("files") or []) if f.get("match_state") == "MATCHED"]


def _unresolved_files(run: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in (run.get("files") or []) if f.get("match_state") in ("AMBIGUOUS", "UNMATCHED")]


def _ignored_files(run: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in (run.get("files") or []) if f.get("match_state") == "IGNORED"]


def item_match_text(item: dict[str, Any]) -> str:
    """Trạng thái ghép file của một mục (theo Screen13 bước 2)."""
    if str(item.get("status")) == "SKIPPED":
        reason = item.get("skip_reason")
        if reason == "TEMPLATE_ARCHIVED":
            return "Bỏ qua: template đã lưu trữ"
        if reason == "USER_SKIP":
            return "Bỏ qua tháng này"
        if reason == "NO_FILE":
            return "Bỏ qua: không có file"
        return "Bỏ qua"
    files = _matched_files(item)
    if not files:
        return "Thiếu file bắt buộc" if str(item.get("is_required")) == "Y" else "Tùy chọn sẽ bỏ qua"
    if len(files) > 1 and str(item.get("multi_file")) != "Y":
        return "Chỉ nhận 1 file"
    if len(files) > 1:
        return f"Gộp {len(files)} file"
    return "Đã ghép"


def wizard_blockers(run: dict[str, Any]) -> list[str]:
    """Lý do chưa được sang bước tham số/kiểm tra."""
    blockers: list[str] = []
    for f in _unresolved_files(run):
        state = "khớp nhiều mục" if f.get("match_state") == "AMBIGUOUS" else "không khớp mục nào"
        blockers.append(f"File {f.get('original_name')} {state}, cần chọn tay hoặc bỏ file.")
    for item in run.get("items") or []:
        if str(item.get("status")) == "SKIPPED":
            continue
        if str(item.get("is_required")) == "Y" and not _matched_files(item):
            blockers.append(f"Mục {item.get('template_code')} bắt buộc nhưng chưa có file.")
        if len(_matched_files(item)) > 1 and str(item.get("multi_file")) != "Y":
            blockers.append(f"Mục {item.get('template_code')} chỉ nhận 1 file, cần bỏ bớt file.")
    return blockers


def runnable_items(run: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for i in (run.get("items") or []) if str(i.get("status")) in ("READY", "WARN")]


def decode_uploads(contents: Any, filenames: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Giải mã dcc.Upload contents thành danh sách {filename, content}."""
    files: list[dict[str, Any]] = []
    errors: list[str] = []
    if contents is None:
        return files, errors
    contents_list = contents if isinstance(contents, list) else [contents]
    names_list = filenames if isinstance(filenames, list) else [filenames]
    for content, name in zip(contents_list, names_list, strict=False):
        try:
            _, payload = str(content).split(",", 1)
            files.append({"filename": str(name), "content": base64.b64decode(payload)})
        except Exception:
            errors.append(f"Không đọc được file {name}.")
    return files, errors


def render_wizard_header(run: dict[str, Any]) -> Any:
    archived = [i for i in (run.get("items") or []) if i.get("skip_reason") == "TEMPLATE_ARCHIVED"]
    status = str(run.get("status", "DRAFT"))
    actions: list[Any] = []
    if status == "DRAFT":
        actions.append(button_subtle("Lưu nháp", icon="lucide:save", id="brw-save-draft-btn", size="xs"))
        actions.append(button_danger("Hủy lần chạy", id="brw-cancel-btn", size="xs"))
    elif status == "RUNNING":
        actions.append(button_danger("Hủy lần chạy", id="brw-cancel-btn", size="xs"))

    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Group(
                        [
                            dmc.Title(f"Lần chạy bộ #{run['id']}: {run.get('name') or run.get('def_name')}", order=4),
                            run_status_badge(status),
                            dmc.Text(
                                f"{run.get('def_code', '')} · Kỳ {run.get('period', '')} · {run.get('cnt_items', 0)} mục",
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                        gap="xs",
                        align="center",
                    ),
                    dmc.Group(actions, gap="xs") if actions else dmc.Text(""),
                ],
                justify="space-between",
                align="center",
            ),
            alert_box(
                title="Có template đã lưu trữ trong bộ",
                message="Các mục sau sẽ bị bỏ qua khi chạy: "
                + ", ".join(str(i.get("template_code")) for i in archived)
                + ".",
                tone="warn",
            )
            if archived
            else dmc.Text(""),
        ],
        gap=4,
    )


def _get_active_source_ds_options() -> list[dict[str, Any]]:
    ctx = get_current_ctx()
    if ctx is None:
        return []
    res = options_data_sources(ctx, purpose="SOURCE")
    if not res.ok or not res.data:
        return []
    return [{"label": f"{d.name} ({d.env})", "value": str(d.id)} for d in res.data]


def render_step1_summary(run: dict[str, Any], ds_options: list[dict[str, Any]] | None = None) -> Any:
    p_from = (run.get("period_from") or "")[:10]
    p_to = (run.get("period_to") or "")[:10]
    is_draft = str(run.get("status", "DRAFT")) == "DRAFT"
    current_ds_id = run.get("data_source_id")
    ds_name = run.get("data_source_name") or "Mặc định"
    ds_env = run.get("data_source_env") or ""
    ds_display = f"{ds_name} ({ds_env})" if ds_env else ds_name

    if ds_options is None:
        ds_options = _get_active_source_ds_options()

    ds_row_cell: Any
    if is_draft and ds_options:
        ds_row_cell = dmc.Group(
            [
                dmc.Select(
                    id="brw-step1-ds-select",
                    data=ds_options,
                    value=str(current_ds_id) if current_ds_id else (ds_options[0]["value"] if ds_options else None),
                    size="xs",
                    w=220,
                    styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "11px"}},
                ),
                button_subtle("Đổi Data Source", id="brw-step1-save-ds-btn", size="xs"),
            ],
            gap="xs",
        )
    else:
        ds_row_cell = dmc.Group(
            [
                dmc.Badge(ds_display, color="blue", variant="light", size="xs"),
                dmc.Text(f"DS #{current_ds_id}" if current_ds_id else "", size="xs", className="rh-code", c="dimmed"),
            ],
            gap="xs",
        )

    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Title("Bộ đối soát và kỳ đã chọn", order=5),
                dmc.Table(
                    dmc.TableTbody(
                        [
                            dmc.TableTr([dmc.TableTd(dmc.Text("Bộ đối soát", fw=600, size="xs")), dmc.TableTd(dmc.Text(f"{run.get('def_code', '')} — {run.get('def_name', '')}", size="xs"))]),
                            dmc.TableTr([dmc.TableTd(dmc.Text("Kỳ đối soát", fw=600, size="xs")), dmc.TableTd(dmc.Text(str(run.get("period", "")), size="xs", className="rh-code"))]),
                            dmc.TableTr([dmc.TableTd(dmc.Text("Data Source nguồn", fw=600, size="xs")), dmc.TableTd(ds_row_cell)]),
                            dmc.TableTr([dmc.TableTd(dmc.Text("Tên lần chạy", fw=600, size="xs")), dmc.TableTd(dmc.Text(str(run.get("name", "")), size="xs"))]),
                            dmc.TableTr([dmc.TableTd(dmc.Text("Khoảng ngày giờ", fw=600, size="xs")), dmc.TableTd(dmc.Text(f"{p_from} 00:00:00 đến {p_to} 23:59:59 (giờ VN)", size="xs"))]),
                        ]
                    ),
                    style={"fontSize": "12px", "maxWidth": "650px"},
                ),
                dmc.Text(
                    "Bấm 'Tiếp tục' bên dưới để tải và ghép file cho lần chạy bộ này.",
                    size="xs",
                    c="dimmed",
                ),
            ],
            gap="xs",
        ),
        p="sm",
        withBorder=True,
        radius="sm",
    )


def render_step2(run: dict[str, Any], filter_mode: str = "all") -> Any:
    items = run.get("items") or []
    unresolved = _unresolved_files(run)
    ignored = _ignored_files(run)
    total_matched_files = sum(len(_matched_files(i)) for i in items)
    matched_items_count = sum(1 for i in items if _matched_files(i))

    item_options = [
        {"label": f"{i.get('template_code')} — {i.get('template_name')}", "value": str(i["id"])}
        for i in items
        if str(i.get("status")) != "SKIPPED"
    ]

    # Các khối sự cố
    issue_cards: list[Any] = []
    if unresolved:
        rows_un = []
        for f in unresolved:
            fid = int(f["id"])
            candidates = f.get("candidate_item_ids") or []
            is_amb = f.get("match_state") == "AMBIGUOUS"
            rows_un.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(dmc.Text(str(f.get("original_name")), className="rh-code", size="xs")),
                        dmc.TableTd(
                            dmc.Badge(
                                "Khớp nhiều mục" if is_amb else "Không khớp",
                                color="yellow" if is_amb else "red",
                                variant="light",
                                size="xs",
                            )
                        ),
                        dmc.TableTd(
                            dmc.Select(
                                id={"type": "brw-assign-select", "index": fid},
                                data=item_options,
                                placeholder="Chọn template đúng...",
                                value=str(candidates[0]) if len(candidates) == 1 else None,
                                size="xs",
                                style={"minWidth": 220},
                                styles={"input": {"height": "26px", "minHeight": "26px", "fontSize": "11px"}},
                            )
                        ),
                        dmc.TableTd(
                            dmc.Group(
                                [
                                    button_primary("Ghép", id={"type": "brw-assign-btn", "index": fid}, size="xs"),
                                    button_subtle("Bỏ file", id={"type": "brw-ignore-btn", "index": fid}, size="xs"),
                                ],
                                gap=4,
                            )
                        ),
                    ]
                )
            )
        issue_cards.append(
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Title("File chưa ghép được", order=5),
                                dmc.Text(f"({len(unresolved)} file cần xử lý)", size="xs", c="dimmed"),
                            ],
                            gap="xs",
                        ),
                        dmc.Table(
                            [
                                dmc.TableThead(
                                    dmc.TableTr(
                                        [
                                            dmc.TableTh("File", style={"fontSize": "11px"}),
                                            dmc.TableTh("Tình trạng", style={"fontSize": "11px"}),
                                            dmc.TableTh("Ghép vào template", style={"fontSize": "11px"}),
                                            dmc.TableTh("Thao tác", style={"fontSize": "11px"}),
                                        ]
                                    )
                                ),
                                dmc.TableTbody(rows_un),
                            ],
                            striped=True,
                            style={"fontSize": "11px"},
                        ),
                    ],
                    gap="xs",
                ),
                p="xs",
                withBorder=True,
                radius="sm",
            )
        )

    if ignored:
        issue_cards.append(
            dmc.Text(
                f"Đã bỏ {len(ignored)} file: {', '.join(str(f.get('original_name')) for f in ignored)}",
                size="xs",
                c="dimmed",
            )
        )

    # Bảng ghép file vào template
    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--surface-2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "11px",
        "fontWeight": 600,
        "textAlign": "center",
        "whiteSpace": "nowrap",
        "borderBottom": "1px solid var(--line, #E0E0E0)",
    }

    match_rows = []
    for idx, item in enumerate(items, start=1):
        files = _matched_files(item)
        is_missing = str(item.get("is_required")) == "Y" and not files
        is_too_many = len(files) > 1 and str(item.get("multi_file")) != "Y"
        needs_work = is_missing or is_too_many or str(item.get("status")) == "SKIPPED"

        if filter_mode == "problem" and not needs_work:
            continue

        file_cell: Any = dmc.Text("—", size="xs", c="dimmed", ta="center")
        if files:
            file_cell = dmc.Group(
                [
                    dmc.Badge(
                        [
                            html.Span(str(f.get("original_name")), style={"marginRight": "4px"}),
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:x", width=12),
                                id={"type": "brw-remove-file-btn", "index": int(f["id"])},
                                variant="transparent",
                                color="gray",
                                size="xs",
                                **{"aria-label": f"Bỏ file {f.get('original_name')}"},
                            ),
                        ],
                        variant="light",
                        color="blue",
                        size="sm",
                        styles={"root": {"paddingRight": 4, "textTransform": "none"}},
                    )
                    for f in files
                ],
                gap=4,
            )

        status_text = item_match_text(item)
        status_color = "gray"
        if "Đã ghép" in status_text or "Gộp" in status_text:
            status_color = "teal"
        elif "Thiếu file" in status_text or "Chỉ nhận 1 file" in status_text:
            status_color = "red"

        skip_cell: Any = dmc.Text("")
        if str(item.get("status")) == "SKIPPED" and item.get("skip_reason") == "USER_SKIP":
            skip_cell = button_subtle(
                "Hoàn tác ✓", id={"type": "brw-skip-btn", "index": int(item["id"])}, size="xs"
            )
        elif str(item.get("status")) != "SKIPPED" and item.get("skip_reason") != "TEMPLATE_ARCHIVED":
            skip_cell = button_subtle(
                "Bỏ qua tháng này", id={"type": "brw-skip-btn", "index": int(item["id"])}, size="xs"
            )

        match_rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(str(item.get("seq_no") or idx), size="xs", ta="center")),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(str(item.get("template_name") or ""), fw=600, size="xs"),
                                dmc.Text(
                                    f"{item.get('template_code')}{' · nhận nhiều file' if item.get('multi_file') == 'Y' else ''}",
                                    size="xs",
                                    className="rh-code",
                                    c="dimmed",
                                ),
                            ],
                            gap=2,
                        )
                    ),
                    dmc.TableTd(dmc.Text(str(item.get("file_pattern") or "—"), size="xs", className="rh-code", ta="center")),
                    dmc.TableTd(file_cell),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.Badge(status_text, color=status_color, variant="light", size="xs"),
                                skip_cell,
                            ],
                            gap="xs",
                            justify="center",
                        )
                    ),
                ]
            )
        )

    return dmc.Stack(
        [
            # Dropzone
            dcc.Upload(
                id="brw-upload",
                multiple=True,
                children=dmc.Paper(
                    dmc.Stack(
                        [
                            DashIconify(icon="lucide:upload-cloud", width=26, color="var(--primary)"),
                            dmc.Text("Kéo thả tất cả file vào đây hoặc bấm để chọn file", fw=600, size="xs"),
                            dmc.Text(
                                ".xlsx · .xls · .csv · .zip · nhiều file cùng lúc · tối đa 50 MB mỗi file. Một hệ thống có nhiều file sẽ được gộp.",
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                        gap=4,
                        align="center",
                    ),
                    p="sm",
                    withBorder=True,
                    radius="sm",
                    style={"textAlign": "center", "cursor": "pointer", "backgroundColor": "var(--surface-2, #FAFAFA)", "borderStyle": "dashed"},
                ),
            ),
            dmc.Group(
                [
                    dmc.Text(
                        f"Đã tải {total_matched_files} file · {matched_items_count}/{len(items)} template đã có file",
                        size="xs",
                        fw=600,
                        c="dimmed",
                    ),
                ],
                justify="space-between",
            ),
            html.Div(id="brw-upload-alert"),
            *issue_cards,

            # Bảng ghép file
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Title("Ghép file vào template", order=5),
                                dmc.Select(
                                    id="brw-match-filter",
                                    data=[
                                        {"label": "Tất cả template", "value": "all"},
                                        {"label": "Chỉ template cần xử lý", "value": "problem"},
                                    ],
                                    value=filter_mode,
                                    size="xs",
                                    w=180,
                                    styles={"input": {"height": "26px", "minHeight": "26px", "fontSize": "11px"}},
                                ),
                            ],
                            justify="space-between",
                            align="center",
                        ),
                        dmc.TableScrollContainer(
                            minWidth=820,
                            children=dmc.Table(
                                [
                                    dmc.TableThead(
                                        dmc.TableTr(
                                            [
                                                dmc.TableTh("#", style={**th_style, "width": "40px"}),
                                                dmc.TableTh("Template / hệ thống", style={**th_style, "minWidth": "220px", "textAlign": "left"}),
                                                dmc.TableTh("Mẫu tên file", style={**th_style, "width": "140px"}),
                                                dmc.TableTh("File đã ghép", style={**th_style, "minWidth": "240px", "textAlign": "left"}),
                                                dmc.TableTh("Trạng thái", style={**th_style, "width": "180px"}),
                                            ]
                                        )
                                    ),
                                    dmc.TableTbody(match_rows),
                                ],
                                striped=False,
                                highlightOnHover=True,
                                verticalSpacing=4,
                                style={"fontSize": "12px"},
                            ),
                        ),
                    ],
                    gap="xs",
                ),
                p="xs",
                withBorder=True,
                radius="sm",
            ),
        ],
        gap="xs",
    )


def render_step3(run: dict[str, Any]) -> Any:
    items = run.get("items") or []
    period = str(run.get("period", ""))
    active_items = [i for i in items if str(i.get("status")) != "SKIPPED" and _matched_files(i)]

    if not active_items:
        return empty_state(
            title="Chưa có mục nào có file",
            description="Tải và ghép file ở bước 2 trước, rồi quay lại soát tham số.",
        )

    rows = []
    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--surface-2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "11px",
        "fontWeight": 600,
        "textAlign": "center",
        "whiteSpace": "nowrap",
        "borderBottom": "1px solid var(--line, #E0E0E0)",
    }

    for idx, item in enumerate(active_items, start=1):
        item_id = int(item["id"])
        tmpl_code = str(item.get("template_code", ""))
        tmpl_name = str(item.get("template_name") or "")
        files = _matched_files(item)

        resolved = item.get("params_resolved") or {}
        overrides = item.get("params_run_override") or {}

        # p_from & p_to
        from_val = str(overrides.get("p_from") or resolved.get("p_from") or "")
        to_val = str(overrides.get("p_to") or resolved.get("p_to") or "")
        from_date = from_val[:10] if len(from_val) >= 10 else None
        to_date = to_val[:10] if len(to_val) >= 10 else None

        # Tham số khác
        other_params = {k: v for k, v in resolved.items() if k not in ("p_from", "p_to")}
        other_cells: list[Any] = []
        for pk, pv in other_params.items():
            ov_val = overrides.get(pk, pv)
            is_ed = pk in overrides
            other_cells.append(
                dmc.Group(
                    [
                        dmc.Text(pk, className="rh-code", size="xs", c="dimmed", style={"minWidth": 60}),
                        dmc.TextInput(
                            id={"type": "brw-param-input", "index": f"{item_id}:{pk}"},
                            value=format_param_value(ov_val),
                            size="xs",
                            style={"flex": 1},
                            styles={"input": {
                                "height": "26px",
                                "fontSize": "11px",
                                "fontFamily": "var(--mono)",
                                "borderColor": "var(--purple)" if is_ed else None,
                                "backgroundColor": "var(--purple-soft)" if is_ed else None,
                            }},
                        ),
                    ],
                    gap=4,
                )
            )

        has_override = bool(overrides)

        tmpl_header = [dmc.Text(tmpl_name, fw=600, size="xs")]
        if has_override:
            tmpl_header.append(dmc.Badge("Đã sửa", color="violet", variant="light", size="xs"))

        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(str(item.get("seq_no") or idx), size="xs", ta="center"), style={"verticalAlign": "middle"}),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Group(tmpl_header, gap=6),
                                dmc.Text(f"{tmpl_code} · {len(files)} file", size="xs", className="rh-code", c="dimmed"),
                            ],
                            gap=2,
                        ),
                        style={"verticalAlign": "middle"},
                    ),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.DatePickerInput(
                                    id={"type": "brw-param-input", "index": f"{item_id}:p_from"},
                                    value=from_date,
                                    valueFormat="YYYY-MM-DD",
                                    placeholder="YYYY-MM-DD",
                                    size="xs",
                                    styles={"input": {
                                        "height": "26px",
                                        "minHeight": "26px",
                                        "fontSize": "11px",
                                        "fontFamily": "var(--mono)",
                                        "borderColor": "var(--purple)" if "p_from" in overrides else None,
                                        "backgroundColor": "var(--purple-soft)" if "p_from" in overrides else None,
                                    }},
                                ),
                                dmc.Text(f"= {from_date} 00:00:00" if from_date else "—", size="xs", c="teal", className="rh-code"),
                            ],
                            gap=2,
                        ),
                        style={"verticalAlign": "middle", "minWidth": 150},
                    ),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.DatePickerInput(
                                    id={"type": "brw-param-input", "index": f"{item_id}:p_to"},
                                    value=to_date,
                                    valueFormat="YYYY-MM-DD",
                                    placeholder="YYYY-MM-DD",
                                    size="xs",
                                    styles={"input": {
                                        "height": "26px",
                                        "minHeight": "26px",
                                        "fontSize": "11px",
                                        "fontFamily": "var(--mono)",
                                        "borderColor": "var(--purple)" if "p_to" in overrides else None,
                                        "backgroundColor": "var(--purple-soft)" if "p_to" in overrides else None,
                                    }},
                                ),
                                dmc.Text(f"= {to_date} 23:59:59" if to_date else "—", size="xs", c="teal", className="rh-code"),
                            ],
                            gap=2,
                        ),
                        style={"verticalAlign": "middle", "minWidth": 150},
                    ),
                    dmc.TableTd(
                        dmc.Stack(other_cells, gap=4) if other_cells else dmc.Text("—", size="xs", c="dimmed", ta="center"),
                        style={"verticalAlign": "middle", "minWidth": 180},
                    ),
                    dmc.TableTd(
                        button_subtle(
                            "Về mặc định",
                            id={"type": "brw-param-reset-btn", "index": str(item_id)},
                            size="xs",
                        )
                        if has_override
                        else dmc.Text(""),
                        style={"verticalAlign": "middle", "textAlign": "center"},
                    ),
                ]
            )
        )

    return dmc.Stack(
        [
            alert_box(
                title="Giá trị tham số theo kỳ",
                message=f"Giá trị đã tính theo kỳ {period}. Sửa ô nào thì chỉ áp dụng cho lần chạy này (tô tím), không đổi cấu hình bộ hay template.",
                tone="info",
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Title("Soát và sửa tham số lần chạy", order=5),
                                button_primary("Lưu tham số", icon="lucide:save", id="brw-save-params-btn", size="xs"),
                            ],
                            justify="space-between",
                            align="center",
                        ),
                        dmc.TableScrollContainer(
                            minWidth=850,
                            children=dmc.Table(
                                [
                                    dmc.TableThead(
                                        dmc.TableTr(
                                            [
                                                dmc.TableTh("#", style={**th_style, "width": "40px"}),
                                                dmc.TableTh("Template", style={**th_style, "minWidth": "180px", "textAlign": "left"}),
                                                dmc.TableTh("Từ ngày (p_from)", style={**th_style, "minWidth": "150px"}),
                                                dmc.TableTh("Đến ngày (p_to)", style={**th_style, "minWidth": "150px"}),
                                                dmc.TableTh("Tham số khác", style={**th_style, "minWidth": "180px"}),
                                                dmc.TableTh("", style={**th_style, "width": "90px"}),
                                            ]
                                        )
                                    ),
                                    dmc.TableTbody(rows),
                                ],
                                striped=False,
                                highlightOnHover=True,
                                verticalSpacing=4,
                                style={"fontSize": "12px"},
                            ),
                        ),
                    ],
                    gap="xs",
                ),
                p="xs",
                withBorder=True,
                radius="sm",
            ),
        ],
        gap="xs",
    )


def render_step4(run: dict[str, Any], include_warn: bool = True) -> Any:
    items = [i for i in (run.get("items") or []) if str(i.get("status")) != "SKIPPED"]
    counts = {"READY": 0, "WARN": 0, "ERROR": 0, "PENDING": 0}
    for i in items:
        st = str(i.get("status"))
        if st in counts:
            counts[st] += 1
    skipped_count = int(run.get("cnt_skipped", 0))

    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--surface-2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "11px",
        "fontWeight": 600,
        "textAlign": "center",
        "whiteSpace": "nowrap",
        "borderBottom": "1px solid var(--line, #E0E0E0)",
    }

    rows = []
    for idx, item in enumerate(items, start=1):
        status = str(item.get("status"))
        pre = item.get("precheck") or {}
        files = _matched_files(item)
        file_count = len(files)
        rows_read = pre.get("rows_read", 0)

        # Control total
        ct = pre.get("control_total") or {}
        ct_matched = ct.get("matched")
        if file_count == 0:
            ct_chip = dmc.Text("—", size="xs", c="dimmed", ta="center")
        elif ct_matched is True:
            ct_chip = dmc.Badge("Khớp", color="teal", variant="light", size="xs")
        elif ct_matched is False:
            ct_chip = dmc.Badge("Lệch", color="yellow", variant="light", size="xs")
        else:
            ct_chip = dmc.Badge("Khớp", color="teal", variant="light", size="xs")

        # DS kết nối
        ds_chip = dmc.Badge(f"DS #{item.get('data_source_id')}", color="teal", variant="light", size="xs")

        # Status badge
        badge = item_status_badge(status)
        if status == "PENDING" and files:
            badge = dmc.Badge("Chờ kiểm tra", color="blue", variant="light", size="xs")

        # Ghi chú lỗi/cảnh báo
        checks = pre.get("checks") or []
        notes = [str(c.get("message")) for c in checks if c.get("level") in ("warn", "error")]
        note_text = "; ".join(notes) if notes else ("Sẵn sàng" if status == "READY" else "—")

        # Thao tác
        replace_cell: Any = dmc.Text("")
        if status == "ERROR":
            replace_cell = dcc.Upload(
                id={"type": "brw-replace-upload", "index": int(item["id"])},
                multiple=True,
                children=button_subtle("Thay file", size="xs"),
            )

        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(str(item.get("seq_no") or idx), size="xs", ta="center")),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(str(item.get("template_name") or ""), fw=600, size="xs"),
                                dmc.Group(
                                    [
                                        dmc.Text(str(item.get("template_code")), size="xs", className="rh-code", c="dimmed"),
                                        dmc.Anchor(
                                            f"Run #{item['current_run_id']}",
                                            href=f"/runs/{item['current_run_id']}",
                                            size="xs",
                                            className="rh-code",
                                        )
                                        if item.get("current_run_id")
                                        else None,
                                    ],
                                    gap="xs",
                                ),
                            ],
                            gap=2,
                        )
                    ),
                    dmc.TableTd(dmc.Text(str(file_count) if file_count else "—", size="xs", ta="center")),
                    dmc.TableTd(dmc.Text(f"{rows_read:,}".replace(",", ".") if rows_read else "—", size="xs", ta="center")),
                    dmc.TableTd(dmc.Group([ct_chip], justify="center")),
                    dmc.TableTd(dmc.Group([ds_chip], justify="center")),
                    dmc.TableTd(dmc.Group([badge], justify="center")),
                    dmc.TableTd(dmc.Text(note_text, size="xs", c="red" if status == "ERROR" else ("orange" if status == "WARN" else "dimmed"))),
                    dmc.TableTd(replace_cell, style={"textAlign": "center"}),
                ]
            )
        )

    return dmc.Stack(
        [
            # 4 KPI cards
            dmc.SimpleGrid(
                cols={"base": 2, "sm": 4},
                spacing="xs",
                children=[
                    dmc.Paper(
                        dmc.Stack([dmc.Text("Sẵn sàng", size="xs", c="dimmed"), dmc.Text(str(counts["READY"]), fw=700, size="lg", c="teal")], gap=2),
                        p="xs", withBorder=True, radius="sm",
                    ),
                    dmc.Paper(
                        dmc.Stack([dmc.Text("Cảnh báo", size="xs", c="dimmed"), dmc.Text(str(counts["WARN"]), fw=700, size="lg", c="orange")], gap=2),
                        p="xs", withBorder=True, radius="sm",
                    ),
                    dmc.Paper(
                        dmc.Stack([dmc.Text("Lỗi", size="xs", c="dimmed"), dmc.Text(str(counts["ERROR"]), fw=700, size="lg", c="red")], gap=2),
                        p="xs", withBorder=True, radius="sm",
                    ),
                    dmc.Paper(
                        dmc.Stack([dmc.Text("Bỏ qua", size="xs", c="dimmed"), dmc.Text(str(skipped_count), fw=700, size="lg", c="gray")], gap=2),
                        p="xs", withBorder=True, radius="sm",
                    ),
                ],
            ),

            # Toolbar precheck
            dmc.Group(
                [
                    dmc.Group(
                        [
                            button_primary("Kiểm tra trước", icon="lucide:clipboard-check", id="brw-precheck-btn", size="xs"),
                            dmc.Checkbox(
                                id="brw-include-warn",
                                label="Chạy cả template có cảnh báo",
                                checked=include_warn,
                                size="xs",
                            ),
                        ],
                        gap="sm",
                    ),
                    dmc.Text(
                        "Mục lỗi có nút Thay file để thay file riêng mục đó và kiểm tra lại.",
                        size="xs",
                        c="dimmed",
                    ),
                ],
                justify="space-between",
                align="center",
            ),

            # Bảng Precheck
            dmc.Paper(
                dmc.TableScrollContainer(
                    minWidth=850,
                    children=dmc.Table(
                        [
                            dmc.TableThead(
                                dmc.TableTr(
                                    [
                                        dmc.TableTh("#", style={**th_style, "width": "40px"}),
                                        dmc.TableTh("Template", style={**th_style, "minWidth": "180px", "textAlign": "left"}),
                                        dmc.TableTh("File", style={**th_style, "width": "50px"}),
                                        dmc.TableTh("Dòng đọc", style={**th_style, "width": "80px"}),
                                        dmc.TableTh("Control total", style={**th_style, "width": "100px"}),
                                        dmc.TableTh("Kết nối", style={**th_style, "width": "90px"}),
                                        dmc.TableTh("Trạng thái", style={**th_style, "width": "100px"}),
                                        dmc.TableTh("Ghi chú", style={**th_style, "minWidth": "180px", "textAlign": "left"}),
                                        dmc.TableTh("", style={**th_style, "width": "80px"}),
                                    ]
                                )
                            ),
                            dmc.TableTbody(rows),
                        ],
                        striped=False,
                        highlightOnHover=True,
                        verticalSpacing=4,
                        style={"fontSize": "12px"},
                    ),
                ),
                p="xs",
                withBorder=True,
                radius="sm",
            ),
        ],
        gap="xs",
    )


def render_step5(run: dict[str, Any]) -> Any:
    items = run.get("items") or []
    counts = {"QUEUED": 0, "RUNNING": 0, "DONE": 0, "FAILED": 0, "NOT_RUN": 0}
    for i in items:
        st = str(i.get("status"))
        if st in counts:
            counts[st] += 1

    runnable = runnable_items(run)
    runnable_total = len(runnable)
    finished = counts["DONE"] + counts["FAILED"] + counts["NOT_RUN"]
    status = str(run.get("status", "DRAFT"))
    if status in ("DONE", "PARTIAL"):
        pct = 100
    elif status == "DRAFT":
        pct = 0
    else:
        active_items = [it for it in items if str(it.get("status")) != "SKIPPED"]
        if active_items:
            pct_list = []
            for it in active_items:
                st = str(it.get("status"))
                if st in ("DONE", "FAILED", "NOT_RUN"):
                    pct_list.append(100)
                elif st == "RUNNING":
                    pct_list.append(max(int(it.get("progress_pct") or 50), 20))
                elif st == "QUEUED":
                    pct_list.append(15)
                else:
                    pct_list.append(0)
            pct = round(sum(pct_list) / len(active_items))
        else:
            pct = 100
    par = run.get("max_parallel_per_ds", 2)
    default_ds_name = run.get("data_source_name") or "Data Source nguồn"

    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--surface-2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "11px",
        "fontWeight": 600,
        "textAlign": "center",
        "whiteSpace": "nowrap",
        "borderBottom": "1px solid var(--line, #E0E0E0)",
    }

    # Review câu lệnh SQL nguồn của các template
    accordion_items = []
    for it in items:
        sql_code = str(it.get("source_sql") or "-- Chưa có câu lệnh SQL nguồn").strip()
        binds = it.get("source_binds") or {}
        bind_str = ", ".join(f":{k} = {v}" for k, v in binds.items()) if binds else "Không có bind param"
        ds_badge_text = f"{it.get('data_source_name') or 'DS #' + str(it.get('data_source_id') or '?')} ({it.get('data_source_env', '')})"
        accordion_items.append(
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        dmc.Group(
                            [
                                dmc.Text(f"{it.get('template_code')} — {it.get('template_name')}", fw=600, size="xs"),
                                dmc.Badge(ds_badge_text, size="xs", variant="light", color="blue"),
                                item_status_badge(str(it.get("status"))),
                            ],
                            gap="xs",
                        )
                    ),
                    dmc.AccordionPanel(
                        dmc.Stack(
                            [
                                dmc.Text(f"Tham số bind: {bind_str}", size="xs", className="rh-code", c="dimmed"),
                                dmc.Code(sql_code, block=True, style={"fontSize": "11px", "maxHeight": "200px", "overflow": "auto"}),
                            ],
                            gap=4,
                        )
                    ),
                ],
                value=str(it.get("id")),
            )
        )

    sql_review_card = dmc.Paper(
        dmc.Stack(
            [
                dmc.Group(
                    [
                        DashIconify(icon="lucide:database", width=16, color="var(--primary)"),
                        dmc.Title("Xem trước câu lệnh SQL nguồn của các template", order=5),
                        dmc.Text(f"({len(items)} template sẽ query trên {default_ds_name})", size="xs", c="dimmed"),
                    ],
                    gap="xs",
                ),
                dmc.Accordion(accordion_items, chevronPosition="right"),
            ],
            gap="xs",
        ),
        p="xs",
        withBorder=True,
        radius="sm",
    )

    rows = []
    for idx, item in enumerate(items, start=1):
        item_st = str(item.get("status"))
        stage_text = "Chờ xếp hàng"
        pct_val = 0
        if item_st == "DONE":
            stage_text = "Hoàn thành đối soát"
            pct_val = 100
        elif item_st == "FAILED":
            stage_text = item.get("error_msg") or "Lỗi khi chạy"
            pct_val = 100
        elif item_st == "RUNNING":
            item_prog = item.get("progress_pct") or 50
            stage_text = f"Đang đọc Excel & truy vấn DB... ({item_prog}%)"
            pct_val = max(int(item_prog), 20)
        elif item_st == "QUEUED":
            stage_text = "Đang trong hàng đợi"
            pct_val = 15
        elif item_st == "SKIPPED":
            stage_text = "Đã bỏ qua tháng này"
            pct_val = 0
        elif item_st == "NOT_RUN":
            stage_text = "Không chạy (chưa sẵn sàng)"
            pct_val = 0

        prog_color = "teal" if item_st == "DONE" else ("red" if item_st == "FAILED" else "blue")
        ds_cell_text = f"{item.get('data_source_name') or 'DS #' + str(item.get('data_source_id') or '—')} ({item.get('data_source_env', '')})"

        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(str(item.get("seq_no") or idx), size="xs", ta="center")),
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(str(item.get("template_name") or ""), fw=600, size="xs"),
                                dmc.Group(
                                    [
                                        dmc.Text(str(item.get("template_code")), size="xs", className="rh-code", c="dimmed"),
                                        dmc.Anchor(
                                            f"Run #{item['current_run_id']}",
                                            href=f"/runs/{item['current_run_id']}",
                                            size="xs",
                                            className="rh-code",
                                        )
                                        if item.get("current_run_id")
                                        else None,
                                    ],
                                    gap="xs",
                                ),
                            ],
                            gap=2,
                        )
                    ),
                    dmc.TableTd(dmc.Text(ds_cell_text, size="xs", className="rh-code", ta="center")),
                    dmc.TableTd(dmc.Text(stage_text, size="xs")),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.Progress(
                                    value=pct_val,
                                    color=prog_color,
                                    size="sm",
                                    radius="xs",
                                    striped=item_st == "RUNNING",
                                    animated=item_st == "RUNNING",
                                    style={"flex": 1},
                                ),
                                dmc.Text(f"{pct_val}%", size="xs", c="dimmed", style={"minWidth": "32px", "textAlign": "right"}),
                            ],
                            gap=6,
                        ),
                        style={"minWidth": 160},
                    ),
                    dmc.TableTd(dmc.Group([item_status_badge(item_st)], justify="center")),
                ]
            )
        )

    stack_children: list[Any] = [
        # 4 KPI cards
        dmc.SimpleGrid(
            cols={"base": 2, "sm": 4},
            spacing="xs",
            children=[
                dmc.Paper(
                    dmc.Stack([dmc.Text("Xếp hàng", size="xs", c="dimmed"), dmc.Text(str(counts["QUEUED"]), fw=700, size="lg", c="gray")], gap=2),
                    p="xs", withBorder=True, radius="sm",
                ),
                dmc.Paper(
                    dmc.Stack([dmc.Text("Đang chạy", size="xs", c="dimmed"), dmc.Text(str(counts["RUNNING"]), fw=700, size="lg", c="blue")], gap=2),
                    p="xs", withBorder=True, radius="sm",
                ),
                dmc.Paper(
                    dmc.Stack([dmc.Text("Đã xong", size="xs", c="dimmed"), dmc.Text(str(counts["DONE"]), fw=700, size="lg", c="teal")], gap=2),
                    p="xs", withBorder=True, radius="sm",
                ),
                dmc.Paper(
                    dmc.Stack([dmc.Text("Lỗi", size="xs", c="dimmed"), dmc.Text(str(counts["FAILED"]), fw=700, size="lg", c="red")], gap=2),
                    p="xs", withBorder=True, radius="sm",
                ),
            ],
        ),

        # Card tiến độ tổng
        dmc.Paper(
            dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.Title("Tiến độ tổng", order=5),
                            dmc.Text(f"{finished}/{runnable_total} template · {pct}%", size="xs", fw=600),
                        ],
                        justify="space-between",
                    ),
                    dmc.Progress(value=pct, size="md", color="blue", radius="xs", striped=status == "RUNNING", animated=status == "RUNNING"),
                    dmc.Text(
                        f"Tối đa {par} run song song mỗi Data Source. Tiến độ tự cập nhật mỗi 2 giây.",
                        size="xs",
                        c="dimmed",
                    ),
                ],
                gap=4,
            ),
            p="xs",
            withBorder=True,
            radius="sm",
        ),

        # Review câu lệnh SQL
        sql_review_card,

        # Bảng danh sách mục đang chạy
        dmc.Paper(
            dmc.TableScrollContainer(
                minWidth=800,
                children=dmc.Table(
                    [
                        dmc.TableThead(
                            dmc.TableTr(
                                [
                                    dmc.TableTh("#", style={**th_style, "width": "40px"}),
                                    dmc.TableTh("Template", style={**th_style, "minWidth": "180px", "textAlign": "left"}),
                                    dmc.TableTh("Data Source", style={**th_style, "width": "140px"}),
                                    dmc.TableTh("Bước thực hiện", style={**th_style, "width": "180px"}),
                                    dmc.TableTh("Tiến độ", style={**th_style, "minWidth": "160px"}),
                                    dmc.TableTh("Trạng thái", style={**th_style, "width": "120px"}),
                                ]
                            )
                        ),
                        dmc.TableTbody(rows),
                    ],
                    striped=False,
                    highlightOnHover=True,
                    verticalSpacing=4,
                    style={"fontSize": "12px"},
                ),
            ),
            p="xs",
            withBorder=True,
            radius="sm",
        ),
    ]

    return dmc.Stack(stack_children, gap="xs")


def render_step_content(step: int, run: dict[str, Any]) -> Any:
    if step == 1:
        return render_step1_summary(run)
    if step == 2:
        return render_step2(run)
    if step == 3:
        return render_step3(run)
    if step == 4:
        return render_step4(run)
    return render_step5(run)


def render_new_run_form(defs: list[dict[str, Any]], preselected_def: int | None) -> Any:
    options = [{"label": f"{d.get('code')} — {d.get('name')}", "value": str(d["id"])} for d in defs]
    ds_options = _get_active_source_ds_options()
    current_p = current_month_period()
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Title("Chọn bộ và kỳ", order=5),
                dmc.Select(
                    id="brw-new-def",
                    label="Bộ đối soát *",
                    data=options,
                    value=str(preselected_def) if preselected_def else (options[0]["value"] if options else None),
                    placeholder="Chọn bộ đối soát",
                    required=True,
                    size="xs",
                    styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                ),
                dmc.Select(
                    id="brw-new-data-source",
                    label="Data Source nguồn *",
                    data=ds_options,
                    value=ds_options[0]["value"] if ds_options else None,
                    placeholder="Chọn Data Source",
                    required=True,
                    size="xs",
                    description="Mặc định chọn Data Source đang hoạt động. Các bước sau sẽ query và so sánh ở Data Source này.",
                    styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                ),
                dmc.SimpleGrid(
                    cols=2,
                    spacing="xs",
                    children=[
                        dmc.TextInput(
                            id="brw-new-period",
                            label="Kỳ đối soát *",
                            value=current_p,
                            placeholder="YYYY-MM",
                            required=True,
                            size="xs",
                            styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                        ),
                        dmc.TextInput(
                            id="brw-new-name",
                            label="Tên lần chạy",
                            placeholder=f"Tháng {current_p[5:7]}/{current_p[:4]}",
                            size="xs",
                            styles={"input": {"height": "28px", "minHeight": "28px", "fontSize": "12px"}},
                        ),
                    ],
                ),
                dmc.Text(
                    f"Mặc định mọi template: p_from = 01/{current_p[5:7]}/{current_p[:4]} 00:00:00, p_to = ngày cuối 23:59:59.",
                    size="xs",
                    c="dimmed",
                ),
                dmc.Group(
                    [
                        button_primary("Khởi tạo lần chạy", icon="lucide:arrow-right", id="brw-new-submit", size="xs"),
                        dmc.Anchor(
                            button_subtle("Về danh sách bộ", size="xs"),
                            href="/batches",
                            underline=False,
                        ),
                    ],
                    gap="xs",
                    mt="xs",
                ),
            ],
            gap="xs",
        ),
        p="sm",
        withBorder=True,
        radius="sm",
    )


def render_recent_runs(runs: list[dict[str, Any]]) -> Any:
    if not runs:
        return dmc.Text("Chưa có lần chạy bộ nào.", size="xs", c="dimmed")
    rows = []
    th_rc = {"textAlign": "center", "fontSize": "11px", "fontWeight": 600}
    for r in runs:
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Anchor(
                            f"#{r['id']} {r.get('name', '')}",
                            href=f"/batch-runs/{r['id']}",
                            size="xs",
                        )
                    ),
                    dmc.TableTd(dmc.Text(f"{r.get('def_code', '')}", className="rh-code", size="xs", ta="center")),
                    dmc.TableTd(dmc.Text(str(r.get("period", "")), size="xs", ta="center")),
                    dmc.TableTd(dmc.Group([run_status_badge(str(r.get("status", "DRAFT")))], justify="center")),
                    dmc.TableTd(dmc.Text(str(r.get("created_by", "")), size="xs", ta="center")),
                ]
            )
        )
    return dmc.Table(
        [
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh("Lần chạy", style=th_rc),
                        dmc.TableTh("Bộ", style=th_rc),
                        dmc.TableTh("Kỳ", style=th_rc),
                        dmc.TableTh("Trạng thái", style=th_rc),
                        dmc.TableTh("Người tạo", style=th_rc),
                    ]
                )
            ),
            dmc.TableTbody(rows),
        ],
        striped=True,
        style={"fontSize": "11px"},
    )


def _load_run_data(run_id: int) -> Any:
    ctx = get_current_ctx()
    if ctx is None:
        return {"error": "Bạn cần đăng nhập để xem lần chạy bộ."}
    res = get_batch_run(ctx, run_id)
    if not res.ok:
        return {"error": res.message or "Không tải được lần chạy bộ."}
    return res.data


def _stepper(step: int) -> Any:
    return dmc.Stepper(
        active=step - 1,
        size="xs",
        children=[dmc.StepperStep(label=label) for label in STEP_LABELS],
    )


def layout(run_id: str | int | None = None, **kwargs: Any) -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return dmc.Box(
            [
                dcc.Location(id="brw-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang Chạy bộ đối soát.", tone="crit"),
            ],
            p="md",
        )

    if run_id is None or str(run_id) == "new":
        defs: list[dict[str, Any]] = []
        defs_error: str | None = None
        recent: list[dict[str, Any]] = []
        if ctx is not None:
            res = list_active_defs(ctx)
            if res.ok and res.data:
                defs = res.data
            else:
                defs_error = res.message or "Không tải được danh sách bộ đối soát."
            res_runs = list_batch_runs(ctx, page=1, page_size=5)
            if res_runs.ok and res_runs.data:
                recent = res_runs.data.get("items", [])
        preselected = kwargs.get("def")
        preselected_id = int(preselected) if preselected and str(preselected).isdigit() else None
        return html.Div(
            [
                dcc.Location(id="brw-redirect", refresh=True),
                html.Div(id="brw-notifications"),
                page_header(
                    title="Chạy bộ đối soát",
                    subtitle="Một lần tải lên cho nhiều hệ thống. Mỗi template tạo một run riêng, lỗi ở một template không chặn các template khác.",
                ),
                dmc.Box(
                    _stepper(1),
                    style={
                        "flexShrink": 0,
                        "padding": "8px 14px",
                        "borderBottom": "1px solid var(--line, #E0E0E0)",
                        "backgroundColor": "var(--surface, #FFFFFF)",
                    },
                ),
                html.Div(
                    [
                        alert_box(defs_error, tone="crit") if defs_error else dmc.Text(""),
                        dmc.SimpleGrid(
                            cols={"base": 1, "md": 2},
                            spacing="sm",
                            children=[
                                render_new_run_form(defs, preselected_id),
                                dmc.Paper(
                                    dmc.Stack(
                                        [
                                            dmc.Title("Lần chạy gần đây của bộ", order=5),
                                            render_recent_runs(recent),
                                        ],
                                        gap="xs",
                                    ),
                                    p="sm",
                                    withBorder=True,
                                    radius="sm",
                                ),
                            ],
                        ),
                    ],
                    style={
                        "flex": "1 1 0%",
                        "minHeight": 0,
                        "overflowY": "auto",
                        "padding": "10px 14px",
                    },
                ),
            ],
            style={
                "height": "100%",
                "minHeight": 0,
                "display": "flex",
                "flexDirection": "column",
                "overflow": "hidden",
            },
        )

    run_id_int = int(run_id) if str(run_id).isdigit() else 0
    return html.Div(
        [
            dcc.Store(id="brw-run-id", data=run_id_int),
            dcc.Store(id="brw-store"),
            dcc.Store(id="brw-step"),
            dcc.Store(id="brw-refresh-trigger", data=0),
            dcc.Location(id="brw-redirect", refresh=True),
            html.Div(id="brw-notifications"),
            dcc.Interval(id="brw-interval", interval=2000, disabled=True),

            # Fixed Top: Header & Stepper
            dmc.Box(
                [
                    html.Div(id="brw-header"),
                    html.Div(id="brw-stepper", style={"marginTop": "6px"}),
                ],
                style={
                    "flexShrink": 0,
                    "padding": "8px 14px 6px",
                    "borderBottom": "1px solid var(--line, #E0E0E0)",
                    "backgroundColor": "var(--surface, #FFFFFF)",
                },
            ),

            # Middle Scrollable Body
            html.Div(
                [
                    html.Div(id="brw-alert"),
                    html.Div(id="brw-content"),
                ],
                style={
                    "flex": "1 1 0%",
                    "minHeight": 0,
                    "overflowY": "auto",
                    "padding": "10px 14px",
                },
            ),

            # Fixed Footer Nav: White background, pill capsule buttons with icons (Fluent Compact)
            dmc.Group(
                [
                    dmc.Group(
                        [
                            html.Span(id="brw-footer-why", style={"fontSize": "11px", "color": "var(--ink-soft, #616161)"}),
                            dmc.Box(
                                dmc.Checkbox(
                                    id="brw-include-warn",
                                    label="Chạy cả template có cảnh báo",
                                    checked=True,
                                    size="xs",
                                    styles={"label": {"fontSize": "11px", "cursor": "pointer"}},
                                ),
                                id="brw-footer-warn-wrapper",
                                style={"display": "none"},
                            ),
                        ],
                        gap="md",
                        align="center",
                    ),
                    dmc.Paper(
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Quay lại",
                                    id="brw-prev-btn",
                                    leftSection=DashIconify(icon="lucide:arrow-left", width=14),
                                    variant="subtle",
                                    color="gray",
                                    size="xs",
                                    radius="xl",
                                    style={
                                        "fontWeight": 500,
                                        "height": "30px",
                                        "padding": "0 14px",
                                        "color": "var(--ink, #1E1E1E)",
                                    },
                                ),
                                dmc.Button(
                                    "Tiếp tục",
                                    id="brw-next-btn",
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
                    ),
                ],
                justify="space-between",
                align="center",
                style={
                    "flexShrink": 0,
                    "height": "48px",
                    "padding": "0 16px",
                    "borderTop": "1px solid var(--line, #E0E0E0)",
                    "backgroundColor": "#FFFFFF",
                    "display": "flex",
                },
            ),
            modal_confirm(
                id="brw-cancel-modal",
                title="Hủy lần chạy bộ",
                description="Lần chạy bộ đang chạy sẽ dừng ở bước kiểm tra tiếp theo. Run con đã xong vẫn giữ kết quả.",
                confirm_label="Hủy lần chạy",
            ),
            dmc.Modal(
                id="brw-prod-modal",
                title="Xác nhận chạy trên Data Source PROD",
                opened=False,
                centered=True,
                children=[
                    dmc.Stack(
                        [
                            html.Div(id="brw-prod-body"),
                            dmc.Group(
                                [
                                    button_subtle("Hủy", id="brw-prod-cancel", size="xs"),
                                    button_primary("Xác nhận chạy", id="brw-prod-confirm", size="xs"),
                                ],
                                justify="flex-end",
                                gap="xs",
                            ),
                        ],
                        gap="sm",
                    )
                ],
            ),
        ],
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
        },
    )


@callback(
    Output("brw-store", "data"),
    Output("brw-interval", "disabled"),
    Input("brw-run-id", "data"),
    Input("brw-refresh-trigger", "data"),
    Input("brw-interval", "n_intervals"),
)
def _load_run(run_id: Any, _refresh: Any, _tick: Any) -> tuple[Any, bool]:
    if run_id is None or int(run_id) <= 0:
        return dash.no_update, True
    data = _load_run_data(int(run_id))
    if isinstance(data, dict) and data.get("error"):
        return data, True
    status = str(data.get("status", ""))
    return data, status not in ("RUNNING", "QUEUED")


@callback(
    Output("brw-header", "children"),
    Output("brw-stepper", "children"),
    Output("brw-content", "children"),
    Output("brw-footer-why", "children"),
    Output("brw-footer-warn-wrapper", "style"),
    Output("brw-next-btn", "children"),
    Output("brw-next-btn", "disabled"),
    Output("brw-prev-btn", "style"),
    Input("brw-store", "data"),
    Input("brw-step", "data"),
)
def _render_wizard(store_data: Any, step_data: Any) -> tuple[Any, Any, Any, str, dict[str, Any], str, bool, dict[str, Any]]:
    if store_data is None:
        return (
            dmc.Skeleton(height=36, radius="sm"),
            dmc.Skeleton(height=36, radius="sm"),
            dmc.Stack([dmc.Skeleton(height=36, radius="sm") for _ in range(5)], gap="xs"),
            "",
            {"display": "none"},
            "Tiếp tục",
            False,
            {"display": "none"},
        )
    if isinstance(store_data, dict) and store_data.get("error"):
        return (
            alert_box(title="Không thể tải lần chạy bộ", message=str(store_data["error"]), tone="crit"),
            dmc.Text(""),
            dmc.Text(""),
            "",
            {"display": "none"},
            "Tiếp tục",
            False,
            {"display": "none"},
        )

    status = str(store_data.get("status", "DRAFT"))
    if step_data is None:
        step = 5 if status == "RUNNING" else 2
    else:
        step = int(step_data)
    step = min(max(step, 1), 5)

    why = ""
    next_label = "Tiếp tục"
    next_disabled = False
    warn_style = {"display": "none"}

    if step == 2:
        blockers = wizard_blockers(store_data)
        if blockers:
            why = f"Còn {len(blockers)} mục cần xử lý."
    elif step == 4:
        next_label = "Tiếp tục"
        runnable = runnable_items(store_data)
        if not runnable:
            why = "Chưa kiểm tra trước hoặc có mục lỗi."
        else:
            why = f"{len(runnable)} template sẵn sàng."
    elif step == 5:
        if status == "DRAFT":
            runnable = runnable_items(store_data)
            next_label = f"Chạy {len(runnable)} template"
            next_disabled = len(runnable) == 0
            default_ds = store_data.get("data_source_name") or ""
            ds_env = store_data.get("data_source_env") or ""
            ds_label = f"{default_ds} ({ds_env})" if ds_env else default_ds
            if runnable:
                why = f"Sẵn sàng chạy {len(runnable)} template trên {ds_label}." if ds_label else f"Sẵn sàng chạy {len(runnable)} template."
            else:
                why = "Chưa có template nào sẵn sàng chạy."
            warn_style = {"display": "inline-flex"}
        elif status in ("DONE", "PARTIAL"):
            next_label = "Xem kết quả"
            why = "Đã hoàn thành lần chạy bộ."
        else:
            next_label = "Xem kết quả"
            why = "Đang chạy các template..."

    base_prev_style = {"fontWeight": 500, "height": "30px", "padding": "0 14px", "color": "var(--ink, #1E1E1E)"}
    prev_style = {**base_prev_style, "display": "none"} if (step == 1 or (step == 5 and status != "DRAFT")) else {**base_prev_style, "display": "inline-flex"}

    return (
        render_wizard_header(store_data),
        _stepper(step),
        render_step_content(step, store_data),
        why,
        warn_style,
        next_label,
        next_disabled,
        prev_style,
    )


@callback(
    Output("brw-step", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Output("brw-redirect", "href", allow_duplicate=True),
    Input("brw-prev-btn", "n_clicks"),
    Input("brw-next-btn", "n_clicks"),
    State("brw-step", "data"),
    State("brw-store", "data"),
    prevent_initial_call=True,
)
def _navigate(_prev: Any, _next: Any, step_data: Any, store_data: Any) -> tuple[Any, Any, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update, dash.no_update
    triggered = ctx_dash.triggered_id
    if triggered == "brw-prev-btn" and not _prev:
        return dash.no_update, dash.no_update, dash.no_update
    if triggered == "brw-next-btn" and not _next:
        return dash.no_update, dash.no_update, dash.no_update
    if not isinstance(store_data, dict) or store_data.get("error"):
        return dash.no_update, dash.no_update, dash.no_update

    status = str(store_data.get("status", "DRAFT"))
    step = int(step_data) if step_data is not None else (5 if status == "RUNNING" else 2)

    if triggered == "brw-prev-btn":
        return max(step - 1, 1), dash.no_update, dash.no_update

    if step in (2, 3):
        blockers = wizard_blockers(store_data)
        if blockers:
            return step, notify_warning("; ".join(blockers), title="Chưa thể tiếp tục"), dash.no_update

    if step == 4:
        return 5, dash.no_update, dash.no_update

    if step == 5:
        if status == "DRAFT":
            # Khi DRAFT ở bước 5, bấm Chạy template do callback _start_run xử lý
            return dash.no_update, dash.no_update, dash.no_update
        # Bấm ở bước 5 khi đã xong -> chuyển trang kết quả
        return dash.no_update, dash.no_update, f"/batch-runs/{store_data['id']}/result"

    return min(step + 1, 5), dash.no_update, dash.no_update


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input("brw-step1-save-ds-btn", "n_clicks"),
    State("brw-step1-ds-select", "value"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _update_run_ds(_n: Any, ds_val: Any, run_id: Any) -> tuple[Any, Any]:
    if not _n or not ds_val or not run_id:
        return dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None:
        return dash.no_update, notify_error("Bạn cần đăng nhập.")
    res = update_batch_run_data_source(ctx, int(run_id), int(ds_val))
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không đổi Data Source được.")
    return _load_run_data(int(run_id)), notify_success("Đã cập nhật Data Source cho lần chạy bộ.")


@callback(
    Output("brw-notifications", "children", allow_duplicate=True),
    Output("brw-redirect", "href"),
    Input("brw-new-submit", "n_clicks"),
    State("brw-new-def", "value"),
    State("brw-new-data-source", "value"),
    State("brw-new-period", "value"),
    State("brw-new-name", "value"),
    prevent_initial_call=True,
)
def _create_run(_n: Any, def_val: Any, ds_val: Any, period: Any, name: Any) -> tuple[Any, Any]:
    if not _n:
        return dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None:
        return notify_error("Bạn cần đăng nhập để thực hiện."), dash.no_update
    if not def_val:
        return notify_warning("Chọn bộ đối soát trước."), dash.no_update
    period_str = (period or "").strip()
    if not PERIOD_RE.match(period_str):
        return notify_warning("Kỳ phải đúng dạng YYYY-MM, ví dụ: 2026-02."), dash.no_update
    data_source_id = int(ds_val) if ds_val else None
    res = create_batch_run(ctx, int(def_val), period_str, (name or "").strip() or None, data_source_id=data_source_id)
    if not res.ok:
        return notify_error(res.message or "Không tạo được lần chạy bộ."), dash.no_update
    data = res.data or {}
    return notify_success("Tạo lần chạy bộ thành công."), f"/batch-runs/{data.get('id')}"


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Output("brw-upload", "contents"),
    Input("brw-upload", "contents"),
    State("brw-upload", "filename"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _upload_files(contents: Any, filenames: Any, run_id: Any) -> tuple[Any, Any, Any]:
    if not contents:
        return dash.no_update, dash.no_update, None
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, notify_error("Bạn cần đăng nhập."), None
    files, errors = decode_uploads(contents, filenames)
    if not files:
        return dash.no_update, notify_warning("; ".join(errors) or "Không có file nào."), None
    res = add_files(ctx, int(run_id), files)
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không tải được file."), None
    data = res.data or {}
    skipped = data.get("skipped") or []
    warnings = data.get("warnings") or []
    notes: list[str] = []
    if skipped:
        notes.append(f"Bỏ qua {len(skipped)} file trùng tên/nội dung.")
    notes.extend(str(w) for w in warnings)
    notes.extend(errors)
    if notes:
        notif = notify_warning(" ".join(notes), title="Cảnh báo tải file")
    else:
        notif = notify_success(f"Đã tải {len(files)} file thành công.")
    return _load_run_data(int(run_id)), notif, None


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input({"type": "brw-assign-btn", "index": ALL}, "n_clicks"),
    State({"type": "brw-assign-select", "index": ALL}, "value"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _assign_file(_n: Any, select_values: Any, run_id: Any) -> tuple[Any, Any]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or not any(c for c in (_n or []) if c) or ctx is None or run_id is None:
        return dash.no_update, dash.no_update
    file_id = int(triggered["index"])
    selected: str | None = None
    states = dash.callback_context.states_list or []
    for group in states:
        entries = group if isinstance(group, list) else [group]
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id") == {"type": "brw-assign-select", "index": file_id}:
                selected = entry.get("value")
    if not selected:
        return dash.no_update, notify_warning("Chọn mục để ghép tay trước.")
    res = assign_file(ctx, file_id, int(selected))
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không ghép được file.")
    return _load_run_data(int(run_id)), notify_success("Đã ghép file thành công.")


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input({"type": "brw-ignore-btn", "index": ALL}, "n_clicks"),
    Input({"type": "brw-remove-file-btn", "index": ALL}, "n_clicks"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _ignore_file(_n1: Any, _n2: Any, run_id: Any) -> tuple[Any, Any]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or ctx is None or run_id is None:
        return dash.no_update, dash.no_update
    if not any(c for c in (_n1 or []) if c) and not any(c for c in (_n2 or []) if c):
        return dash.no_update, dash.no_update
    res = ignore_file(ctx, int(triggered["index"]))
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không bỏ được file.")
    return _load_run_data(int(run_id)), notify_success("Đã bỏ file.")


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input({"type": "brw-skip-btn", "index": ALL}, "n_clicks"),
    State("brw-store", "data"),
    prevent_initial_call=True,
)
def _toggle_skip(_n: Any, store_data: Any) -> tuple[Any, Any]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or not any(c for c in (_n or []) if c) or ctx is None or not isinstance(store_data, dict):
        return dash.no_update, dash.no_update
    item_id = int(triggered["index"])
    item = next((i for i in (store_data.get("items") or []) if int(i["id"]) == item_id), None)
    if item is None:
        return dash.no_update, dash.no_update
    skipped = not (str(item.get("status")) == "SKIPPED" and item.get("skip_reason") == "USER_SKIP")
    res = skip_item(ctx, item_id, skipped)
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không cập nhật được mục.")
    msg = "Đã bỏ qua mục này." if skipped else "Đã khôi phục mục này."
    return _load_run_data(int(store_data["id"])), notify_success(msg)


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input("brw-save-params-btn", "n_clicks"),
    State({"type": "brw-param-input", "index": ALL}, "value"),
    State("brw-store", "data"),
    prevent_initial_call=True,
)
def _save_params(_n: Any, values: Any, store_data: Any) -> tuple[Any, Any]:
    if not _n:
        return dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None or not isinstance(store_data, dict):
        return dash.no_update, dash.no_update
    states = dash.callback_context.states_list or []
    entries: list[dict[str, Any]] = []
    for group in states:
        group_entries = group if isinstance(group, list) else [group]
        for entry in group_entries:
            if isinstance(entry, dict) and isinstance(entry.get("id"), dict):
                entries.append(entry)
    items_by_id = {int(i["id"]): i for i in (store_data.get("items") or [])}
    changed = 0
    for entry in entries:
        index = str(entry.get("id", {}).get("index", ""))
        if ":" not in index:
            continue
        item_id_s, param_name = index.split(":", 1)
        item = items_by_id.get(int(item_id_s))
        if item is None:
            continue
        resolved = (item.get("params_resolved") or {}).get(param_name)
        overrides = item.get("params_run_override") or {}
        new_value = (entry.get("value") or "").strip()
        if param_name == "p_from" and len(new_value) == 10 and new_value.count("-") == 2:
            new_value = f"{new_value} 00:00:00"
        elif param_name == "p_to" and len(new_value) == 10 and new_value.count("-") == 2:
            new_value = f"{new_value} 23:59:59"
        resolved_str = format_param_value(resolved)
        if new_value == resolved_str:
            if param_name in overrides:
                res = set_param_override(ctx, int(item_id_s), param_name, None)
                if not res.ok:
                    return dash.no_update, notify_error(res.message or "Không lưu được tham số.")
                changed += 1
            continue
        if new_value == format_param_value(overrides.get(param_name)):
            continue
        res = set_param_override(ctx, int(item_id_s), param_name, new_value)
        if not res.ok:
            return dash.no_update, notify_error(res.message or "Không lưu được tham số.")
        changed += 1
    if changed == 0:
        return dash.no_update, notify_info("Không có tham số nào thay đổi.")
    return _load_run_data(int(store_data["id"])), notify_success(f"Đã lưu {changed} tham số.")


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input({"type": "brw-param-reset-btn", "index": ALL}, "n_clicks"),
    State("brw-store", "data"),
    prevent_initial_call=True,
)
def _reset_param(_n: Any, store_data: Any) -> tuple[Any, Any]:
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or ctx is None or not isinstance(store_data, dict):
        return dash.no_update, dash.no_update
    idx_str = str(triggered["index"])
    # Reset toàn bộ override của item_id
    if ":" in idx_str:
        item_id_s, param_name = idx_str.split(":", 1)
        res = set_param_override(ctx, int(item_id_s), param_name, None)
    else:
        item_id = int(idx_str)
        item = next((i for i in (store_data.get("items") or []) if int(i["id"]) == item_id), None)
        if item:
            for pk in list((item.get("params_run_override") or {}).keys()):
                set_param_override(ctx, item_id, pk, None)
        res = type("Res", (), {"ok": True, "message": ""})()
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không về mặc định được.")
    return _load_run_data(int(store_data["id"])), notify_success("Đã đặt lại tham số về mặc định.")


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input("brw-precheck-btn", "n_clicks"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _run_precheck(_n: Any, run_id: Any) -> tuple[Any, Any]:
    if not _n:
        return dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update
    res = precheck(ctx, int(run_id))
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không kiểm tra trước được.")
    return _load_run_data(int(run_id)), notify_success("Đã kiểm tra trước xong.")


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input({"type": "brw-replace-upload", "index": ALL}, "contents"),
    State({"type": "brw-replace-upload", "index": ALL}, "filename"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _replace_item_files(contents: Any, filenames: Any, run_id: Any) -> tuple[Any, Any]:
    if not contents:
        return dash.no_update, dash.no_update
    triggered = dash.callback_context.triggered_id
    ctx = get_current_ctx()
    if not isinstance(triggered, dict) or ctx is None or run_id is None:
        return dash.no_update, dash.no_update
    item_id = int(triggered["index"])
    contents_list = contents if isinstance(contents, list) else [contents]
    names_list = filenames if isinstance(filenames, list) else [filenames]
    idx = 0
    states = dash.callback_context.inputs_list or []
    for group in states:
        group_entries = group if isinstance(group, list) else [group]
        for pos, entry in enumerate(group_entries):
            if isinstance(entry, dict) and entry.get("id") == {"type": "brw-replace-upload", "index": item_id}:
                idx = pos
    target_contents = contents_list[idx] if idx < len(contents_list) else None
    target_names = names_list[idx] if idx < len(names_list) else None
    files, errors = decode_uploads(target_contents, target_names)
    if not files:
        return dash.no_update, notify_warning("; ".join(errors) or "Không có file nào.")
    res = replace_files(ctx, item_id, files)
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không thay được file.")
    return _load_run_data(int(run_id)), notify_success("Đã thay file và kiểm tra lại mục.")


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-step", "data", allow_duplicate=True),
    Output("brw-prod-modal", "opened"),
    Output("brw-prod-body", "children"),
    Output("brw-notifications", "children", allow_duplicate=True),
    Output("brw-interval", "disabled", allow_duplicate=True),
    Input("brw-start-btn", "n_clicks"),
    State("brw-include-warn", "checked"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _start_run(_n: Any, include_warn: Any, run_id: Any) -> tuple[Any, Any, bool, Any, Any, Any]:
    if not _n:
        return dash.no_update, dash.no_update, False, dash.no_update, dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update, False, dash.no_update, dash.no_update, dash.no_update
    res = start(ctx, int(run_id), include_warn=bool(include_warn), confirm_prod=False)
    if not res.ok:
        if res.code == "PROD_CONFIRM_REQUIRED":
            details = res.details or {}
            prod_ds = details.get("prod_data_sources") or []
            body = dmc.Stack(
                [
                    dmc.Text(
                        "Lần chạy bộ dùng Data Source thuộc môi trường PROD. Xác nhận một lần cho cả lần chạy:",
                        size="xs",
                    ),
                    dmc.List([dmc.ListItem(str(name)) for name in prod_ds]),
                ],
                gap="xs",
            )
            return dash.no_update, dash.no_update, True, body, dash.no_update, dash.no_update
        return (
            dash.no_update,
            dash.no_update,
            False,
            dash.no_update,
            notify_error(res.message or "Không chạy được lần chạy bộ."),
            dash.no_update,
        )
    return _load_run_data(int(run_id)), 5, False, dash.no_update, notify_success("Đã bắt đầu chạy các template."), False


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-step", "data", allow_duplicate=True),
    Output("brw-prod-modal", "opened", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Output("brw-interval", "disabled", allow_duplicate=True),
    Input("brw-prod-confirm", "n_clicks"),
    Input("brw-prod-cancel", "n_clicks"),
    State("brw-include-warn", "checked"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _confirm_prod_start(_confirm: Any, _cancel: Any, include_warn: Any, run_id: Any) -> tuple[Any, Any, bool, Any, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update, False, dash.no_update, dash.no_update
    triggered = ctx_dash.triggered_id
    if triggered == "brw-prod-cancel":
        return dash.no_update, dash.no_update, False, dash.no_update, dash.no_update
    if triggered == "brw-prod-confirm" and not _confirm:
        return dash.no_update, dash.no_update, False, dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update, False, dash.no_update, dash.no_update
    res = start(ctx, int(run_id), include_warn=bool(include_warn), confirm_prod=True)
    if not res.ok:
        return (
            dash.no_update,
            dash.no_update,
            False,
            notify_error(res.message or "Không chạy được lần chạy bộ."),
            dash.no_update,
        )
    return _load_run_data(int(run_id)), 5, False, notify_success("Đã bắt đầu chạy các template."), False


@callback(
    Output("brw-cancel-modal", "opened"),
    Input("brw-cancel-btn", "n_clicks"),
    Input("brw-cancel-modal-cancel", "n_clicks"),
    State("brw-cancel-modal", "opened"),
    prevent_initial_call=True,
)
def _toggle_cancel_modal(_open: Any, _cancel: Any, opened: bool) -> bool:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False
    triggered = ctx_dash.triggered_id
    if triggered == "brw-cancel-modal-cancel":
        return False
    if triggered == "brw-cancel-btn" and bool(_open):
        return True
    return False


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Output("brw-cancel-modal", "opened", allow_duplicate=True),
    Input("brw-cancel-modal-confirm", "n_clicks"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _do_cancel(_n: Any, run_id: Any) -> tuple[Any, Any, bool]:
    if not _n:
        return dash.no_update, dash.no_update, False
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update, False
    res = cancel(ctx, int(run_id))
    if not res.ok:
        return dash.no_update, notify_error(res.message or "Không hủy được lần chạy bộ."), False
    return _load_run_data(int(run_id)), notify_success("Đã hủy lần chạy bộ."), False
