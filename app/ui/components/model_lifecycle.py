"""UI helpers cho Validation Navigation, Concurrency (STALE_DATA) và Publish Modal (Task 107 Bước 5)."""

from __future__ import annotations

from typing import Any

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify

from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.status_chip import status_chip


def resolve_validation_issue_selection(bundle: dict[str, Any], issue: dict[str, Any]) -> dict[str, Any] | None:
    """Ánh xạ issue của validate_model sang selection dict cho Explorer/Canvas/Properties."""
    ttype = str(issue.get("target_type") or "").lower()
    raw_id = issue.get("target_id")
    tid = int(raw_id) if raw_id is not None else None
    tables = list(bundle.get("tables") or [])
    rels = list(bundle.get("relationships") or [])
    measures = list(bundle.get("measures") or [])
    policies = list(bundle.get("rls_policies") or [])

    if ttype == "table" and tid is not None:
        if any(int(t["id"]) == tid for t in tables):
            return {"kind": "table", "id": tid}
    elif ttype == "relationship" and tid is not None:
        if any(int(r["id"]) == tid for r in rels):
            return {"kind": "relationship", "id": tid}
    elif ttype == "field" and tid is not None:
        for tbl in tables:
            if any(int(f["id"]) == tid for f in (tbl.get("fields") or [])):
                return {"kind": "field", "id": tid, "table_id": int(tbl["id"])}
    elif ttype == "measure" and tid is not None:
        if any(int(m["id"]) == tid for m in measures):
            return {"kind": "measure", "id": tid}
    elif ttype == "rls" and tid is not None:
        pol = next((p for p in policies if int(p["id"]) == tid), None)
        if pol and pol.get("table_id") is not None:
            return {"kind": "table", "id": int(pol["table_id"])}
    return None


def render_validation_drawer_body(bundle: dict[str, Any], val_data: dict[str, Any]) -> Any:
    """Dựng nội dung Drawer Kiểm tra mô hình với aria-live='polite' và điều hướng tới phần tử lỗi."""
    status = str(val_data.get("status") or "VALID").upper()
    summary = val_data.get("summary") or {}
    err_cnt = int(summary.get("error_count") or 0)
    warn_cnt = int(summary.get("warning_count") or 0)
    issues = list(val_data.get("issues") or [])
    breaking = list(val_data.get("breaking_changes") or [])

    tone = "crit" if err_cnt > 0 else ("warn" if warn_cnt > 0 else "ok")
    title = (
        f"Phát hiện {err_cnt} lỗi bắt buộc và {warn_cnt} cảnh báo"
        if err_cnt > 0
        else (f"Mô hình hợp lệ kèm {warn_cnt} cảnh báo" if warn_cnt > 0 else "Mô hình hợp lệ — Sẵn sàng phát hành")
    )
    msg = (
        "Bấm vào từng vấn đề bên dưới để định vị bảng, cột, quan hệ hoặc measure cần chỉnh sửa."
        if issues
        else "Không có lỗi cấu trúc hoặc dữ liệu mẫu."
    )

    issue_rows: list[Any] = []
    for idx, iss in enumerate(issues):
        sev = str(iss.get("severity") or "WARNING").upper()
        sev_color = "crit" if sev == "ERROR" else "warn"
        sev_icon = "lucide:x-circle" if sev == "ERROR" else "lucide:alert-triangle"
        sel = resolve_validation_issue_selection(bundle, iss)
        target_label = "Nhấn để mở" if sel is not None else "Toàn mô hình"

        issue_rows.append(
            html.Button(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Group(
                                    [
                                        DashIconify(icon=sev_icon, width=14),
                                        dmc.Badge(sev, size="xs", color=sev_color, variant="light"),
                                        dmc.Badge(str(iss.get("code") or "CHECK"), size="xs", variant="outline", className="rh-code"),
                                    ],
                                    gap=4,
                                ),
                                dmc.Text(target_label, size="xs", c="dimmed"),
                            ],
                            justify="space-between",
                        ),
                        dmc.Text(str(iss.get("message") or ""), size="xs", fw=500, style={"textAlign": "left"}),
                    ],
                    gap=4,
                ),
                id={"type": "rms-val-issue-btn", "idx": idx},
                className="rms-val-issue-btn",
                disabled=(sel is None),
                **{"aria-label": f"Đi tới vấn đề {iss.get('code') or idx}"},  # type: ignore[arg-type]
            )
        )

    breaking_nodes: list[Any] = []
    if breaking:
        breaking_nodes.append(
            alert_box(
                title=f"{len(breaking)} thay đổi có thể ảnh hưởng báo cáo đang chạy",
                message=dmc.Stack(
                    [dmc.Text(f"• {b.get('message') or b.get('change_type')}", size="xs") for b in breaking],
                    gap=2,
                ),
                tone="warn",
            )
        )

    return html.Div(
        dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.Text("Trạng thái kiểm tra", size="xs", fw=600, c="dimmed"),
                        status_chip(status, size="sm"),
                    ],
                    justify="space-between",
                ),
                alert_box(title=title, message=msg, tone=tone),
                *breaking_nodes,
                dmc.Divider(label=f"Danh sách vấn đề ({len(issues)})", labelPosition="left"),
                dmc.Stack(
                    issue_rows
                    if issue_rows
                    else [dmc.Text("Không ghi nhận lỗi hoặc cảnh báo nào.", size="xs", c="dimmed")],
                    gap="xs",
                ),
            ],
            gap="sm",
        ),
        id="rms-validate-live",
        **{"aria-live": "polite"},  # type: ignore[arg-type]
    )


def render_stale_conflict_body(message: str, server_row_version: int | None = None) -> Any:
    """Dựng nội dung hộp thoại xung đột phiên bản STALE_DATA khi Lưu nháp."""
    ver_note = f" (Phiên bản hiện tại trên máy chủ: #{server_row_version})" if server_row_version is not None else ""
    return dmc.Stack(
        [
            alert_box(
                title="Bản nháp đã thay đổi từ phiên làm việc khác",
                message=f"{message}{ver_note}",
                tone="warn",
            ),
            dmc.Text(
                "Chọn 'Tải lại bản mới' để đồng bộ trạng thái mới nhất từ máy chủ, "
                "hoặc chọn 'Giữ phiên bản đang sửa' nếu muốn giữ lại vị trí vừa sắp xếp trên Canvas.",
                size="xs",
                c="dimmed",
            ),
        ],
        gap="sm",
    )


def render_publish_modal_body(bundle: dict[str, Any], preview: dict[str, Any] | None) -> Any:
    """Dựng nội dung Modal Phát hành gồm Validation Summary, Diff, Impact Analysis và Change Note."""
    ver = bundle.get("version") or {}
    ver_no = int(ver.get("version_no") or 1)
    model = bundle.get("model") or {}

    if preview is None:
        return dmc.Stack(
            [
                html.Div(id="rms-pub-modal-alert"),
                dmc.Text("Đang chuẩn bị thông tin kiểm tra và ảnh hưởng...", size="xs", c="dimmed"),
                dmc.Textarea(
                    id="rms-pub-change-note",
                    label="Ghi chú phát hành (Change Note)",
                    placeholder="VD: Bổ sung bảng chiều Khách hàng và chỉ số Tổng doanh thu",
                    withAsterisk=True,
                    minRows=2,
                    size="xs",
                    value="",
                ),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="rms-pub-cancel-btn", size="xs"),
                        button_primary(
                            f"Xác nhận phát hành v{ver_no}",
                            id="rms-pub-confirm-btn",
                            icon="lucide:upload-cloud",
                            size="xs",
                            disabled=True,
                        ),
                    ],
                    justify="flex-end",
                    gap="xs",
                ),
            ],
            gap="sm",
        )

    val = preview.get("validation") or {}
    summary = val.get("summary") or {}
    err_cnt = int(summary.get("error_count") or 0)
    warn_cnt = int(summary.get("warning_count") or 0)
    can_publish = bool(preview.get("can_publish"))

    val_tone = "crit" if err_cnt > 0 else ("warn" if warn_cnt > 0 else "ok")
    val_msg = (
        f"Có {err_cnt} lỗi ERROR chưa xử lý — vui lòng kiểm tra model trước khi phát hành."
        if err_cnt > 0
        else (f"Đạt điều kiện phát hành (có {warn_cnt} cảnh báo)." if warn_cnt > 0 else "Kiểm tra mô hình đạt 100%.")
    )

    diff = preview.get("diff")
    diff_section: Any
    if diff is None:
        diff_section = dmc.Text(
            f"Phát hành lần đầu cho mô hình {model.get('code') or ''} (chưa có phiên bản ACTIVE trước đó).",
            size="xs",
            c="dimmed",
        )
    else:
        brks = list(diff.get("breaking_changes") or [])
        non_brks = list(diff.get("non_breaking_changes") or [])
        diff_items: list[Any] = []
        for b in brks:
            diff_items.append(
                dmc.Group(
                    [
                        dmc.Badge("BREAKING", color="crit", size="xs", variant="light"),
                        dmc.Text(str(b.get("message") or b.get("change_type")), size="xs", style={"flex": 1}),
                    ],
                    gap=6,
                )
            )
        for nb in non_brks:
            diff_items.append(
                dmc.Group(
                    [
                        dmc.Badge("MỞ RỘNG", color="teal", size="xs", variant="light"),
                        dmc.Text(str(nb.get("message") or nb.get("change_type")), size="xs", style={"flex": 1}),
                    ],
                    gap=6,
                )
            )
        diff_section = (
            dmc.Stack(diff_items, gap=4)
            if diff_items
            else dmc.Text("Không có thay đổi cấu trúc so với phiên bản ACTIVE hiện tại.", size="xs", c="dimmed")
        )

    impact = preview.get("impact") or {}
    rpts = list(impact.get("reports") or [])
    vis = list(impact.get("visuals") or [])
    exps = list(impact.get("scheduled_exports") or [])
    impact_text = (
        f"{len(rpts)} báo cáo · {len(vis)} visual · {len(exps)} lịch xuất chịu ảnh hưởng."
        if (rpts or vis or exps)
        else "Chưa có báo cáo hay lịch xuất nào tham chiếu tới mô hình này."
    )

    return dmc.Stack(
        [
            html.Div(id="rms-pub-modal-alert"),
            alert_box(
                title=f"Kiểm tra trước phát hành v{ver_no}",
                message=val_msg,
                tone=val_tone,
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Thay đổi so với bản ACTIVE", size="xs", fw=700),
                        diff_section,
                    ],
                    gap=6,
                ),
                withBorder=True,
                p="xs",
                radius="sm",
            ),
            dmc.Paper(
                dmc.Stack(
                    [
                        dmc.Text("Phân tích ảnh hưởng (Impact Analysis)", size="xs", fw=700),
                        dmc.Text(impact_text, size="xs", c="dimmed"),
                    ],
                    gap=4,
                ),
                withBorder=True,
                p="xs",
                radius="sm",
            ),
            dmc.Textarea(
                id="rms-pub-change-note",
                label="Ghi chú phát hành (Change Note)",
                placeholder="VD: Hoàn thiện Star Schema FACT_SALES và bộ chỉ số doanh thu v1",
                withAsterisk=True,
                minRows=2,
                size="xs",
                value="",
            ),
            dmc.Group(
                [
                    button_subtle("Hủy", id="rms-pub-cancel-btn", size="xs"),
                    button_primary(
                        f"Xác nhận phát hành v{ver_no}",
                        id="rms-pub-confirm-btn",
                        icon="lucide:upload-cloud",
                        size="xs",
                        disabled=not can_publish,
                        **{"aria-label": f"Xác nhận phát hành phiên bản v{ver_no}"},  # type: ignore[arg-type]
                    ),
                ],
                justify="flex-end",
                gap="xs",
                mt="xs",
            ),
        ],
        gap="sm",
    )


__all__ = [
    "render_publish_modal_body",
    "render_stale_conflict_body",
    "render_validation_drawer_body",
    "resolve_validation_issue_selection",
]
