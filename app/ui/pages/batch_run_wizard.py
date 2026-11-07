"""Wizard chạy bộ đối soát — Bước 9 task 18 (Screen13).

`/batch-runs/new?def=<id>` tạo lần chạy bộ (bước 1) và `/batch-runs/<id>`
chạy các bước 2–5. Trạng thái lưu ở DB (lần chạy DRAFT), tải lại trang
không mất công việc. Stepper chỉ hiển thị, bước hiện tại lưu ở dcc.Store
(không callback vào Stepper để tránh phát lại như lỗi wizard báo cáo).
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
)
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
    """Lý do chưa được sang bước tham số/kiểm tra (file chưa ghép xong,
    mục bắt buộc thiếu file)."""
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
    if status in ("DONE", "PARTIAL"):
        actions.append(
            dmc.Anchor(
                button_primary("Xem kết quả", icon="lucide:bar-chart-3", size="sm"),
                href=f"/batch-runs/{run['id']}/result",
                underline=False,
            )
        )
    if status in ("DRAFT", "RUNNING"):
        actions.append(button_danger("Hủy lần chạy", id="brw-cancel-btn", size="sm"))
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            dmc.Group(
                                [
                                    dmc.Title(f"Lần chạy bộ #{run['id']}", order=2),
                                    run_status_badge(status),
                                ],
                                gap="sm",
                            ),
                            dmc.Text(
                                f"{run.get('def_code', '')} — {run.get('def_name', '')} · Kỳ {run.get('period', '')} · "
                                f"{run.get('name', '')}",
                                size="sm",
                                c="dimmed",
                            ),
                            dmc.Text(
                                f"Người tạo {run.get('created_by', '')} · "
                                f"{(run.get('created_at') or '')[:16].replace('T', ' ')} · "
                                f"{run.get('cnt_items', 0)} mục",
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                        gap=2,
                    ),
                    dmc.Group(actions, gap="sm") if actions else dmc.Text(""),
                ],
                justify="space-between",
                align="flex-start",
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
        gap="sm",
    )


def render_step1_summary(run: dict[str, Any]) -> Any:
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("Bộ và kỳ đã chọn", fw=600),
                dmc.Table(
                    [
                        dmc.TableTbody(
                            [
                                dmc.TableTr(
                                    [
                                        dmc.TableTd("Bộ đối soát"),
                                        dmc.TableTd(f"{run.get('def_code', '')} — {run.get('def_name', '')}"),
                                    ]
                                ),
                                dmc.TableTr([dmc.TableTd("Kỳ"), dmc.TableTd(str(run.get("period", "")))]),
                                dmc.TableTr([dmc.TableTd("Tên lần chạy"), dmc.TableTd(str(run.get("name", "")))]),
                                dmc.TableTr(
                                    [
                                        dmc.TableTd("Khoảng ngày"),
                                        dmc.TableTd(
                                            f"{(run.get('period_from') or '')[:10]} đến {(run.get('period_to') or '')[:10]}"
                                        ),
                                    ]
                                ),
                            ]
                        )
                    ]
                ),
                dmc.Text(
                    "Muốn chạy bộ hoặc kỳ khác, tạo lần chạy bộ mới từ trang danh sách bộ.",
                    size="sm",
                    c="dimmed",
                ),
            ],
            gap="sm",
        ),
        p="md",
        withBorder=True,
    )


def render_step2(run: dict[str, Any]) -> Any:
    items = run.get("items") or []
    unresolved = _unresolved_files(run)
    item_options = [
        {"label": f"{i.get('template_code')} — {i.get('template_name')}", "value": str(i["id"])}
        for i in items
        if str(i.get("status")) != "SKIPPED"
    ]

    unmatched_block: Any = dmc.Text("")
    if unresolved:
        rows = []
        for f in unresolved:
            candidates = f.get("candidate_item_ids") or []
            rows.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(dmc.Text(str(f.get("original_name")), className="rh-code", size="sm")),
                        dmc.TableTd(
                            dmc.Badge(
                                "Khớp nhiều mục" if f.get("match_state") == "AMBIGUOUS" else "Không khớp",
                                color="yellow" if f.get("match_state") == "AMBIGUOUS" else "red",
                                variant="light",
                                size="sm",
                            )
                        ),
                        dmc.TableTd(
                            dmc.Select(
                                id={"type": "brw-assign-select", "index": int(f["id"])},
                                data=item_options,
                                placeholder="Chọn mục để ghép tay",
                                value=str(candidates[0]) if len(candidates) == 1 else None,
                                style={"minWidth": 220},
                            )
                        ),
                        dmc.TableTd(
                            dmc.Group(
                                [
                                    button_primary(
                                        "Ghép", id={"type": "brw-assign-btn", "index": int(f["id"])}, size="xs"
                                    ),
                                    button_subtle(
                                        "Bỏ file", id={"type": "brw-ignore-btn", "index": int(f["id"])}, size="xs"
                                    ),
                                ],
                                gap="xs",
                            )
                        ),
                    ]
                )
            )
        unmatched_block = dmc.Paper(
            dmc.Stack(
                [
                    dmc.Text("File chưa ghép được", fw=600),
                    dmc.Text(
                        "Chọn mục để ghép tay, hoặc bỏ file. Chỉ sang bước tiếp khi không còn file chưa xử lý.",
                        size="sm",
                        c="dimmed",
                    ),
                    dmc.Table(
                        [
                            dmc.TableThead(
                                dmc.TableTr(
                                    [
                                        dmc.TableTh("File", style={"textAlign": "center"}),
                                        dmc.TableTh("Trạng thái", style={"textAlign": "center"}),
                                        dmc.TableTh("Ghép vào mục", style={"textAlign": "center"}),
                                        dmc.TableTh("Thao tác", style={"textAlign": "center"}),
                                    ]
                                )
                            ),
                            dmc.TableTbody(rows),
                        ],
                        striped=True,
                    ),
                ],
                gap="sm",
            ),
            p="md",
            withBorder=True,
        )

    match_rows = []
    for item in items:
        files = _matched_files(item)
        file_cell: Any = dmc.Text("—", size="sm", c="dimmed")
        if files:
            file_cell = dmc.Stack(
                [
                    dmc.Group(
                        [
                            dmc.Text(str(f.get("original_name")), className="rh-code", size="sm"),
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:x", width=14),
                                id={"type": "brw-remove-file-btn", "index": int(f["id"])},
                                variant="subtle",
                                color="gray",
                                size="xs",
                                **{"aria-label": f"Bỏ file {f.get('original_name')}"},
                            ),
                        ],
                        gap="xs",
                    )
                    for f in files
                ],
                gap=2,
            )
        skip_cell: Any = dmc.Text("")
        if str(item.get("status")) != "SKIPPED" and str(item.get("is_required")) == "Y" and not files:
            skip_cell = button_subtle(
                "Bỏ qua tháng này", id={"type": "brw-skip-btn", "index": int(item["id"])}, size="xs"
            )
        elif str(item.get("status")) == "SKIPPED" and item.get("skip_reason") == "USER_SKIP":
            skip_cell = button_subtle(
                "Bỏ qua tháng này ✓", id={"type": "brw-skip-btn", "index": int(item["id"])}, size="xs"
            )
        match_rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(str(item.get("template_code")), className="rh-code", fw=600, size="sm"),
                                dmc.Text(str(item.get("template_name") or ""), size="xs", c="dimmed"),
                            ],
                            gap=0,
                        )
                    ),
                    dmc.TableTd(file_cell),
                    dmc.TableTd(dmc.Text(item_match_text(item), size="sm")),
                    dmc.TableTd(skip_cell),
                ]
            )
        )

    return dmc.Stack(
        [
            dcc.Upload(
                id="brw-upload",
                multiple=True,
                children=dmc.Paper(
                    dmc.Stack(
                        [
                            DashIconify(icon="lucide:upload-cloud", width=28),
                            dmc.Text("Kéo thả file Excel hoặc .zip vào đây, hoặc bấm để chọn", size="sm"),
                            dmc.Text(
                                "Tối đa 200 file mỗi lần chạy, mỗi file ≤ 50 MB, .zip ≤ 200 MB.",
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                        gap="xs",
                        align="center",
                    ),
                    p="xl",
                    withBorder=True,
                    style={"textAlign": "center", "cursor": "pointer"},
                ),
            ),
            html.Div(id="brw-upload-alert"),
            unmatched_block,
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Bảng ghép file", fw=600),
                        dmc.Table(
                            [
                                dmc.TableThead(
                                    dmc.TableTr(
                                        [
                                            dmc.TableTh("Template", style={"textAlign": "center"}),
                                            dmc.TableTh("File đã ghép", style={"textAlign": "center"}),
                                            dmc.TableTh("Trạng thái", style={"textAlign": "center"}),
                                            dmc.TableTh("Thao tác", style={"textAlign": "center"}),
                                        ]
                                    )
                                ),
                                dmc.TableTbody(match_rows),
                            ],
                            striped=True,
                            highlightOnHover=True,
                        ),
                    ],
                    gap="sm",
                ),
                p="md",
                withBorder=True,
            ),
        ],
        gap="md",
    )


def render_step3(run: dict[str, Any]) -> Any:
    blocks: list[Any] = []
    for item in run.get("items") or []:
        if str(item.get("status")) == "SKIPPED":
            continue
        files = _matched_files(item)
        if not files:
            continue
        resolved = item.get("params_resolved") or {}
        overrides = item.get("params_run_override") or {}
        rows = []
        for name, value in resolved.items():
            is_overridden = name in overrides
            rows.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(dmc.Text(name, className="rh-code", size="sm", fw=600 if is_overridden else 400)),
                        dmc.TableTd(
                            dmc.TextInput(
                                id={"type": "brw-param-input", "index": f"{item['id']}:{name}"},
                                value=format_param_value(overrides.get(name, value)),
                                style={"minWidth": 220},
                            )
                        ),
                        dmc.TableTd(
                            dmc.Text(
                                format_param_value(value),
                                size="sm",
                                c="dimmed",
                                className="rh-code",
                            )
                        ),
                        dmc.TableTd(
                            dmc.Badge("Đã sửa", color="violet", variant="light", size="sm")
                            if is_overridden
                            else dmc.Text("")
                        ),
                        dmc.TableTd(
                            button_subtle(
                                "Về mặc định",
                                id={"type": "brw-param-reset-btn", "index": f"{item['id']}:{name}"},
                                size="xs",
                            )
                            if is_overridden
                            else dmc.Text("")
                        ),
                    ]
                )
            )
        blocks.append(
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Text(
                                    f"{item.get('template_code')} — {item.get('template_name')}",
                                    fw=600,
                                ),
                                dmc.Text(f"{len(files)} file", size="xs", c="dimmed"),
                            ],
                            gap="sm",
                        ),
                        dmc.Table(
                            [
                                dmc.TableThead(
                                    dmc.TableTr(
                                        [
                                            dmc.TableTh("Tham số", style={"textAlign": "center"}),
                                            dmc.TableTh("Giá trị chạy", style={"textAlign": "center"}),
                                            dmc.TableTh("Giá trị đã tính", style={"textAlign": "center"}),
                                            dmc.TableTh("Trạng thái", style={"textAlign": "center"}),
                                            dmc.TableTh("Thao tác", style={"textAlign": "center"}),
                                        ]
                                    )
                                ),
                                dmc.TableTbody(rows),
                            ],
                            striped=True,
                        ),
                    ],
                    gap="sm",
                ),
                p="md",
                withBorder=True,
            )
        )
    if not blocks:
        return empty_state(
            title="Chưa có mục nào có file",
            description="Tải file ở bước 2 trước, rồi quay lại soát tham số.",
        )
    return dmc.Stack(
        [
            dmc.Text(
                "Sửa ô giá trị rồi bấm Lưu tham số. Ô đã sửa tô tím. Giá trị đã tính là giá trị theo bộ và công thức kỳ.",
                size="sm",
                c="dimmed",
            ),
            *blocks,
            dmc.Group(
                [button_primary("Lưu tham số", icon="lucide:save", id="brw-save-params-btn")],
                justify="flex-end",
            ),
        ],
        gap="md",
    )


def render_step4(run: dict[str, Any]) -> Any:
    items = [i for i in (run.get("items") or []) if str(i.get("status")) != "SKIPPED"]
    counts = {"READY": 0, "WARN": 0, "ERROR": 0, "PENDING": 0}
    for i in items:
        if str(i.get("status")) in counts:
            counts[str(i.get("status"))] += 1
    runnable = runnable_items(run)
    rows = []
    for item in items:
        status = str(item.get("status"))
        pre = item.get("precheck") or {}
        checks = pre.get("checks") or []
        check_list: Any = dmc.Text("Chưa kiểm tra.", size="sm", c="dimmed")
        if checks:
            check_list = dmc.Stack(
                [
                    dmc.Group(
                        [
                            DashIconify(
                                icon="lucide:check" if c.get("level") == "ok" else "lucide:alert-triangle",
                                width=14,
                            ),
                            dmc.Text(str(c.get("message")), size="sm"),
                        ],
                        gap="xs",
                    )
                    for c in checks
                ],
                gap=2,
            )
        replace_cell: Any = dmc.Text("")
        if status == "ERROR":
            replace_cell = dcc.Upload(
                id={"type": "brw-replace-upload", "index": int(item["id"])},
                multiple=True,
                children=button_subtle("Thay file", size="xs"),
            )
        badge: Any = item_status_badge(status)
        if status == "PENDING" and _matched_files(item):
            badge = dmc.Badge("Chờ kiểm tra", color="blue", variant="light", size="sm")
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Text(str(item.get("template_code")), className="rh-code", fw=600, size="sm"),
                    ),
                    dmc.TableTd(badge),
                    dmc.TableTd(check_list),
                    dmc.TableTd(replace_cell),
                ]
            )
        )
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Paper(
                        dmc.Stack(
                            [
                                dmc.Text("Sẵn sàng", size="xs", c="dimmed"),
                                dmc.Text(str(counts["READY"]), fw=700, size="xl"),
                            ]
                        ),
                        p="sm",
                        withBorder=True,
                    ),
                    dmc.Paper(
                        dmc.Stack(
                            [
                                dmc.Text("Cảnh báo", size="xs", c="dimmed"),
                                dmc.Text(str(counts["WARN"]), fw=700, size="xl"),
                            ]
                        ),
                        p="sm",
                        withBorder=True,
                    ),
                    dmc.Paper(
                        dmc.Stack(
                            [dmc.Text("Lỗi", size="xs", c="dimmed"), dmc.Text(str(counts["ERROR"]), fw=700, size="xl")]
                        ),
                        p="sm",
                        withBorder=True,
                    ),
                    dmc.Paper(
                        dmc.Stack(
                            [
                                dmc.Text("Bỏ qua", size="xs", c="dimmed"),
                                dmc.Text(str(run.get("cnt_skipped", 0)), fw=700, size="xl"),
                            ]
                        ),
                        p="sm",
                        withBorder=True,
                    ),
                ],
                gap="sm",
            ),
            dmc.Group(
                [
                    button_primary("Kiểm tra trước", icon="lucide:clipboard-check", id="brw-precheck-btn"),
                    dmc.Checkbox(
                        id="brw-include-warn",
                        label="Chạy cả mục có cảnh báo",
                        checked=True,
                    ),
                ],
                gap="md",
            ),
            dmc.Text(
                "Mục lỗi có nút Thay file: thay file của riêng mục đó rồi kiểm tra lại.",
                size="sm",
                c="dimmed",
            ),
            dmc.Paper(
                dmc.Table(
                    [
                        dmc.TableThead(
                            dmc.TableTr(
                                [
                                    dmc.TableTh("Template", style={"textAlign": "center"}),
                                    dmc.TableTh("Trạng thái", style={"textAlign": "center"}),
                                    dmc.TableTh("Kết quả kiểm tra", style={"textAlign": "center"}),
                                    dmc.TableTh("Thao tác", style={"textAlign": "center"}),
                                ]
                            )
                        ),
                        dmc.TableTbody(rows),
                    ],
                    striped=True,
                    highlightOnHover=True,
                ),
                p="md",
                withBorder=True,
            ),
            dmc.Group(
                [
                    button_primary(
                        f"Chạy {len(runnable)} template",
                        icon="lucide:play",
                        id="brw-start-btn",
                        disabled=len(runnable) == 0,
                    ),
                    dmc.Text(
                        "Chưa có mục nào sẵn sàng chạy, bấm Kiểm tra trước."
                        if len(runnable) == 0
                        else "Mục lỗi và mục chưa kiểm tra sẽ không chạy.",
                        size="sm",
                        c="dimmed",
                    ),
                ],
                gap="md",
            ),
        ],
        gap="md",
    )


def render_step5(run: dict[str, Any]) -> Any:
    items = run.get("items") or []
    counts = {"QUEUED": 0, "RUNNING": 0, "DONE": 0, "FAILED": 0, "NOT_RUN": 0}
    for i in items:
        if str(i.get("status")) in counts:
            counts[str(i.get("status"))] += 1
    runnable_total = sum(counts.values())
    finished = counts["DONE"] + counts["FAILED"] + counts["NOT_RUN"]
    pct = round(finished / runnable_total * 100) if runnable_total else 0
    status = str(run.get("status", "DRAFT"))
    rows = []
    for item in items:
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(str(item.get("template_code")), className="rh-code", fw=600, size="sm")),
                    dmc.TableTd(item_status_badge(str(item.get("status")))),
                    dmc.TableTd(
                        dmc.Anchor(
                            f"Run #{item['current_run_id']}",
                            href=f"/runs/{item['current_run_id']}",
                            size="sm",
                        )
                        if item.get("current_run_id")
                        else dmc.Text("—", size="sm", c="dimmed")
                    ),
                    dmc.TableTd(dmc.Text(f"Lần {item.get('attempt_no', 1)}", size="sm")),
                ]
            )
        )
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Paper(
                        dmc.Stack(
                            [
                                dmc.Text("Xếp hàng", size="xs", c="dimmed"),
                                dmc.Text(str(counts["QUEUED"]), fw=700, size="xl"),
                            ]
                        ),
                        p="sm",
                        withBorder=True,
                    ),
                    dmc.Paper(
                        dmc.Stack(
                            [
                                dmc.Text("Đang chạy", size="xs", c="dimmed"),
                                dmc.Text(str(counts["RUNNING"]), fw=700, size="xl"),
                            ]
                        ),
                        p="sm",
                        withBorder=True,
                    ),
                    dmc.Paper(
                        dmc.Stack(
                            [
                                dmc.Text("Đã xong", size="xs", c="dimmed"),
                                dmc.Text(str(counts["DONE"]), fw=700, size="xl"),
                            ]
                        ),
                        p="sm",
                        withBorder=True,
                    ),
                    dmc.Paper(
                        dmc.Stack(
                            [dmc.Text("Lỗi", size="xs", c="dimmed"), dmc.Text(str(counts["FAILED"]), fw=700, size="xl")]
                        ),
                        p="sm",
                        withBorder=True,
                    ),
                ],
                gap="sm",
            ),
            dmc.Progress(value=pct, size="lg", color="blue", striped=True, animated=status == "RUNNING"),
            dmc.Text(f"Tiến độ tổng: {finished}/{runnable_total} mục đã kết thúc ({pct}%).", size="sm"),
            dmc.Anchor(
                button_primary("Xem kết quả", icon="lucide:bar-chart-3", id="brw-goto-result-btn"),
                href=f"/batch-runs/{run['id']}/result",
                underline=False,
            )
            if status in ("DONE", "PARTIAL")
            else dmc.Text(
                "Người dùng có thể rời trang, tiến độ đọc từ DB và tự cập nhật mỗi 2 giây.",
                size="sm",
                c="dimmed",
            ),
            dmc.Paper(
                dmc.Table(
                    [
                        dmc.TableThead(
                            dmc.TableTr(
                                [
                                    dmc.TableTh("Template", style={"textAlign": "center"}),
                                    dmc.TableTh("Trạng thái", style={"textAlign": "center"}),
                                    dmc.TableTh("Run con", style={"textAlign": "center"}),
                                    dmc.TableTh("Lần chạy", style={"textAlign": "center"}),
                                ]
                            )
                        ),
                        dmc.TableTbody(rows),
                    ],
                    striped=True,
                    highlightOnHover=True,
                ),
                p="md",
                withBorder=True,
            ),
        ],
        gap="md",
    )


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
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text("Khởi tạo lần chạy mới", fw=600),
                dmc.Text(
                    "Chọn bộ đối soát đang hoạt động và kỳ tháng, hệ thống tạo lần chạy bộ ở trạng thái Nháp.",
                    size="sm",
                    c="dimmed",
                ),
                dmc.Select(
                    id="brw-new-def",
                    label="Bộ đối soát",
                    data=options,
                    value=str(preselected_def) if preselected_def else None,
                    placeholder="Chọn bộ đối soát",
                    required=True,
                    searchable=True,
                ),
                dmc.TextInput(
                    id="brw-new-period",
                    label="Kỳ (tháng)",
                    value=current_month_period(),
                    placeholder="YYYY-MM, VD: 2026-02",
                    description="Tháng YYYY-MM. p_from mặc định là ngày 1, p_to là ngày cuối tháng.",
                    required=True,
                ),
                dmc.TextInput(
                    id="brw-new-name",
                    label="Tên lần chạy (không bắt buộc)",
                    placeholder="Để trống sẽ lấy tên Tháng M/YYYY",
                ),
                dmc.Group(
                    [
                        button_primary("Tạo lần chạy bộ", icon="lucide:arrow-right", id="brw-new-submit"),
                        dmc.Anchor(
                            button_subtle("Về danh sách bộ"),
                            href="/batches",
                            underline=False,
                        ),
                    ],
                    gap="sm",
                    mt="xs",
                ),
            ],
            gap="sm",
        ),
        p="md",
        withBorder=True,
        radius="sm",
    )


def render_recent_runs(runs: list[dict[str, Any]]) -> Any:
    if not runs:
        return dmc.Text("Chưa có lần chạy bộ nào.", size="sm", c="dimmed")
    rows = []
    for r in runs:
        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Anchor(
                            f"#{r['id']} {r.get('name', '')}",
                            href=f"/batch-runs/{r['id']}",
                            size="sm",
                        )
                    ),
                    dmc.TableTd(dmc.Text(f"{r.get('def_code', '')}", className="rh-code", size="sm")),
                    dmc.TableTd(dmc.Text(str(r.get("period", "")), size="sm")),
                    dmc.TableTd(run_status_badge(str(r.get("status", "DRAFT")))),
                    dmc.TableTd(dmc.Text(str(r.get("created_by", "")), size="sm")),
                ]
            )
        )
    return dmc.Table(
        [
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh("Lần chạy", style={"textAlign": "center"}),
                        dmc.TableTh("Bộ", style={"textAlign": "center"}),
                        dmc.TableTh("Kỳ", style={"textAlign": "center"}),
                        dmc.TableTh("Trạng thái", style={"textAlign": "center"}),
                        dmc.TableTh("Người tạo", style={"textAlign": "center"}),
                    ]
                )
            ),
            dmc.TableTbody(rows),
        ],
        striped=True,
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
        size="sm",
        children=[dmc.StepperStep(label=label) for label in STEP_LABELS],
    )


def layout(run_id: str | int | None = None, **kwargs: Any) -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return dmc.Container(
            [
                dcc.Location(id="brw-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang Chạy bộ đối soát.", tone="crit"),
            ]
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
                        "padding": "12px 20px 8px 20px",
                        "borderBottom": "1px solid var(--mantine-color-default-border)",
                        "backgroundColor": "var(--mantine-color-body)",
                    },
                ),
                html.Div(
                    [
                        alert_box(defs_error, tone="crit") if defs_error else dmc.Text(""),
                        dmc.SimpleGrid(
                            cols={"base": 1, "md": 2},
                            spacing="md",
                            children=[
                                render_new_run_form(defs, preselected_id),
                                dmc.Paper(
                                    dmc.Stack(
                                        [
                                            dmc.Text("Lần chạy gần đây", fw=600),
                                            render_recent_runs(recent),
                                        ],
                                        gap="sm",
                                    ),
                                    p="md",
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
                        "padding": "16px 20px",
                    },
                ),
            ],
            style={
                "height": "100%",
                "minHeight": 0,
                "display": "flex",
                "flexDirection": "column",
                "overflow": "hidden",
                "backgroundColor": "var(--mantine-color-body)",
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
                    html.Div(id="brw-stepper"),
                ],
                style={
                    "flexShrink": 0,
                    "padding": "12px 20px 8px 20px",
                    "borderBottom": "1px solid var(--mantine-color-default-border)",
                    "backgroundColor": "var(--mantine-color-body)",
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
                    "padding": "16px 20px",
                },
            ),
            # Fixed Footer Nav
            dmc.Group(
                [
                    button_subtle("Quay lại", id="brw-prev-btn", size="sm"),
                    button_primary("Tiếp tục", id="brw-next-btn", size="sm"),
                ],
                justify="space-between",
                align="center",
                style={
                    "flexShrink": 0,
                    "height": "48px",
                    "padding": "0 20px",
                    "borderTop": "1px solid var(--mantine-color-default-border)",
                    "backgroundColor": "var(--mantine-color-body)",
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
                                    button_subtle("Hủy", id="brw-prod-cancel", size="sm"),
                                    button_primary("Xác nhận chạy", id="brw-prod-confirm", size="sm"),
                                ],
                                justify="flex-end",
                                gap="sm",
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
            "backgroundColor": "var(--mantine-color-body)",
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
    return data, str(data.get("status")) != "RUNNING"


@callback(
    Output("brw-header", "children"),
    Output("brw-stepper", "children"),
    Output("brw-content", "children"),
    Input("brw-store", "data"),
    Input("brw-step", "data"),
)
def _render_wizard(store_data: Any, step_data: Any) -> tuple[Any, Any, Any]:
    if store_data is None:
        return (
            dmc.Skeleton(height=48, radius="md"),
            dmc.Skeleton(height=48, radius="md"),
            dmc.Stack([dmc.Skeleton(height=48, radius="md") for _ in range(5)], gap="sm"),
        )
    if isinstance(store_data, dict) and store_data.get("error"):
        return (
            alert_box(title="Không thể tải lần chạy bộ", message=str(store_data["error"]), tone="crit"),
            dmc.Text(""),
            dmc.Text(""),
        )
    status = str(store_data.get("status", "DRAFT"))
    if step_data is None:
        step = 5 if status == "RUNNING" else 2
    else:
        step = int(step_data)
    step = min(max(step, 1), 5)
    return render_wizard_header(store_data), _stepper(step), render_step_content(step, store_data)


@callback(
    Output("brw-step", "data", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input("brw-prev-btn", "n_clicks"),
    Input("brw-next-btn", "n_clicks"),
    State("brw-step", "data"),
    State("brw-store", "data"),
    prevent_initial_call=True,
)
def _navigate(_prev: Any, _next: Any, step_data: Any, store_data: Any) -> tuple[Any, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update
    triggered = ctx_dash.triggered_id
    if triggered == "brw-prev-btn" and not _prev:
        return dash.no_update, dash.no_update
    if triggered == "brw-next-btn" and not _next:
        return dash.no_update, dash.no_update
    if not isinstance(store_data, dict) or store_data.get("error"):
        return dash.no_update, dash.no_update
    status = str(store_data.get("status", "DRAFT"))
    step = int(step_data) if step_data is not None else (5 if status == "RUNNING" else 2)
    if triggered == "brw-prev-btn":
        return max(step - 1, 1), dash.no_update
    if step in (2, 3):
        blockers = wizard_blockers(store_data)
        if blockers:
            return step, notify_warning("; ".join(blockers), title="Chưa thể tiếp tục")
    return min(step + 1, 5), dash.no_update


@callback(
    Output("brw-notifications", "children", allow_duplicate=True),
    Output("brw-redirect", "href"),
    Input("brw-new-submit", "n_clicks"),
    State("brw-new-def", "value"),
    State("brw-new-period", "value"),
    State("brw-new-name", "value"),
    prevent_initial_call=True,
)
def _create_run(_n: Any, def_val: Any, period: Any, name: Any) -> tuple[Any, Any]:
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
    res = create_batch_run(ctx, int(def_val), period_str, (name or "").strip() or None)
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
    index = str(triggered["index"])
    if ":" not in index:
        return dash.no_update, dash.no_update
    item_id_s, param_name = index.split(":", 1)
    res = set_param_override(ctx, int(item_id_s), param_name, None)
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
    Input("brw-start-btn", "n_clicks"),
    State("brw-include-warn", "checked"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _start_run(_n: Any, include_warn: Any, run_id: Any) -> tuple[Any, Any, bool, Any, Any]:
    if not _n:
        return dash.no_update, dash.no_update, False, dash.no_update, dash.no_update
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update, False, dash.no_update, dash.no_update
    res = start(ctx, int(run_id), include_warn=bool(include_warn), confirm_prod=False)
    if not res.ok:
        if res.code == "PROD_CONFIRM_REQUIRED":
            details = res.details or {}
            prod_ds = details.get("prod_data_sources") or []
            body = dmc.Stack(
                [
                    dmc.Text(
                        "Lần chạy bộ dùng Data Source thuộc môi trường PROD. Xác nhận một lần cho cả lần chạy:",
                        size="sm",
                    ),
                    dmc.List([dmc.ListItem(str(name)) for name in prod_ds]),
                ],
                gap="sm",
            )
            return dash.no_update, dash.no_update, True, body, dash.no_update
        return (
            dash.no_update,
            dash.no_update,
            False,
            dash.no_update,
            notify_error(res.message or "Không chạy được lần chạy bộ."),
        )
    return _load_run_data(int(run_id)), 5, False, dash.no_update, notify_success("Đã bắt đầu chạy các template.")


@callback(
    Output("brw-store", "data", allow_duplicate=True),
    Output("brw-step", "data", allow_duplicate=True),
    Output("brw-prod-modal", "opened", allow_duplicate=True),
    Output("brw-notifications", "children", allow_duplicate=True),
    Input("brw-prod-confirm", "n_clicks"),
    Input("brw-prod-cancel", "n_clicks"),
    State("brw-include-warn", "checked"),
    State("brw-run-id", "data"),
    prevent_initial_call=True,
)
def _confirm_prod_start(_confirm: Any, _cancel: Any, include_warn: Any, run_id: Any) -> tuple[Any, Any, bool, Any]:
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update, False, dash.no_update
    triggered = ctx_dash.triggered_id
    if triggered == "brw-prod-cancel":
        return dash.no_update, dash.no_update, False, dash.no_update
    if triggered == "brw-prod-confirm" and not _confirm:
        return dash.no_update, dash.no_update, False, dash.no_update
    ctx = get_current_ctx()
    if ctx is None or run_id is None:
        return dash.no_update, dash.no_update, False, dash.no_update
    res = start(ctx, int(run_id), include_warn=bool(include_warn), confirm_prod=True)
    if not res.ok:
        return (
            dash.no_update,
            dash.no_update,
            False,
            notify_error(res.message or "Không chạy được lần chạy bộ."),
        )
    return _load_run_data(int(run_id)), 5, False, notify_success("Đã bắt đầu chạy các template.")


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
