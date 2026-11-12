"""Trang Hàng đợi & worker (task 66) — tách card sức khỏe khỏi dashboard.

Card sức khỏe (task 62) trước đây nằm trên dashboard; từ task 66 nó thành
1 tab riêng trong sidebar (nhóm Đối soát, route /queue-health, ai cũng xem
được). Bộ ba fetch/_health_card_body/render_health_card + callback
handle_health_actions dời nguyên từ app/ui/pages/dashboard.py sang đây
(chỉ đổi tiền tố id dashboard-health-* → queue-health-* và sửa link run
kẹt — xem _health_card_body).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, callback, dcc, html

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.services.perm import page_gate
from app.services.report_export import cancel_export
from app.services.report_run import cancel_report_run
from app.services.worker_health import WORKER_KIND_LABELS, get_queue_health
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_subtle
from app.ui.components.page_header import page_header
from app.ui.components.status_chip import status_chip

try:
    dash.register_page(__name__, path="/queue-health", title="Hàng đợi & worker – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "queue_health"


def format_short_dt(iso_str: str | None) -> str:
    """Định dạng ngày giờ ngắn gọn DD/MM HH:mm.

    Bản sao y hệt của dashboard.py/history.py — cố ý trùng lặp: các
    module trang Dash KHÔNG được import lẫn nhau (Dash nạp trang theo
    tên ``pages.<mod>``; import ``app.ui.pages.dashboard`` từ một trang
    khác khiến cùng một file có 2 tên module → lỗi "duplicate paths"
    và mọi request trả 500).
    """
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return str(iso_str)


def fetch_queue_health(ctx: Ctx) -> dict[str, Any]:
    """Trạng thái hàng đợi/worker cho trang sức khỏe (task 62, dời từ dashboard ở task 66)."""
    res = get_queue_health(ctx)
    if not res.ok or not isinstance(res.data, dict):
        return {}
    return dict(res.data)


def _format_age(minutes: int) -> str:
    """Số phút kẹt → '45 phút' / '2 giờ 10 phút'."""
    if minutes < 60:
        return f"{minutes} phút"
    hours, mins = divmod(int(minutes), 60)
    return f"{hours} giờ {mins} phút" if mins else f"{hours} giờ"


def _health_card_body(health: dict[str, Any], note: str | None = None, note_tone: str = "ok") -> Any:
    """Nội dung thẻ Sức khỏe hàng đợi & worker (task 62).

    Badge tổng + từng dòng trạng thái mỗi luồng worker, 4 con số hàng
    đợi, danh sách mục kẹt + nút Hủy (chỉ khi có quyền hủy).
    """
    if not health:
        return alert_box(message="Không tải được trạng thái hàng đợi.", tone="crit")
    children: list[Any] = []
    if note:
        children.append(alert_box(message=note, tone=note_tone))

    worker = health.get("worker") or {}
    status = str(worker.get("status", "down"))
    if status == "running":
        badge = status_chip("RUNNING", label="Đang chạy", icon="lucide:activity")
    elif status == "partial":
        badge = status_chip("LOCKED", label="Chạy một phần", icon="lucide:alert-triangle")
    else:
        badge = status_chip("FAILED", label="Không phản hồi", icon="lucide:alert-circle")
    kind_lines: list[Any] = []
    for kind in ("recon", "export"):
        info = (worker.get("workers") or {}).get(kind, {})
        label = WORKER_KIND_LABELS.get(kind, kind)
        last_seen = info.get("last_seen")
        if info.get("alive"):
            state = "Đang chạy"
            seen_txt = f"thấy lần cuối {format_short_dt(str(last_seen))}"
        elif last_seen:
            state = "Không phản hồi"
            seen_txt = f"thấy lần cuối {format_short_dt(str(last_seen))}"
        else:
            state = "Chưa từng chạy"
            seen_txt = ""
        line = f"Worker {label}: {state}" + (f" · {seen_txt}" if seen_txt else "")
        kind_lines.append(dmc.Text(line, size="sm"))
    children.append(dmc.Group([badge, *kind_lines], gap="lg", align="center"))

    exports = health.get("exports") or {}
    runs = health.get("runs") or {}
    children.append(
        dmc.Group(
            [
                dmc.Text(f"Export đang chờ: {int(exports.get('QUEUED', 0))}", size="sm"),
                dmc.Text(f"Export đang chạy: {int(exports.get('RUNNING', 0))}", size="sm"),
                dmc.Text(f"Run đang chờ: {int(runs.get('QUEUED', 0))}", size="sm"),
                dmc.Text(f"Run đang chạy: {int(runs.get('RUNNING', 0))}", size="sm"),
                dmc.Text(
                    f"Song song tối đa: {int(health.get('max_concurrent', 10))}",
                    size="sm",
                    c="dimmed",
                ),
            ],
            gap="lg",
        )
    )

    stuck = health.get("stuck") or []
    if not stuck:
        children.append(dmc.Text("Không có mục kẹt.", size="sm", c="dimmed"))
    else:
        rows: list[Any] = []
        for item in stuck:
            kind_label = "Export" if item["kind"] == "export" else "Run"
            # Task 66: cả 2 kind đều về /report-runs. Trước đây run gắn
            # /runs/<run_id> nhưng trang đó chỉ đọc run đối soát theo lô
            # (RECON_RUN) nên run báo cáo (RECON_REPORT_RUN, vd #37) báo
            # "Không tìm thấy dữ liệu lần chạy"; /report-runs mới là nơi
            # run đó tồn tại (kèm đủ thao tác Xóa/Xuất lại/Chạy lại).
            href = "/report-runs"
            status_node: Any = status_chip(str(item["status"]))
            if item.get("stale_heartbeat"):
                status_node = dmc.Group(
                    [status_node, dmc.Text("quá hạn heartbeat", size="xs", c="red")],
                    gap="xs",
                )
            action: Any = (
                button_subtle(
                    "Hủy",
                    id={"type": "health-cancel", "kind": item["kind"], "id": item["id"]},
                    icon="lucide:x",
                    size="xs",
                    color="red",
                )
                if item.get("can_cancel")
                else dmc.Text("—", size="xs", c="dimmed")
            )
            rows.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(dmc.Text(kind_label, size="xs"), style={"height": "32px"}),
                        dmc.TableTd(
                            dmc.Anchor(
                                f"#{item['id']} · {item['report_name']}",
                                href=href,
                                size="xs",
                                underline="hover",
                            ),
                            style={"height": "32px", "fontSize": "13px"},
                        ),
                        dmc.TableTd(
                            dmc.Text(str(item["created_by"]), size="xs"),
                            style={"height": "32px"},
                        ),
                        dmc.TableTd(
                            dmc.Text(
                                format_short_dt(str(item["created_at"])),
                                size="xs",
                                className="rh-code",
                            ),
                            style={"height": "32px", "whiteSpace": "nowrap"},
                        ),
                        dmc.TableTd(
                            dmc.Text(_format_age(int(item["age_minutes"])), size="xs"),
                            style={"height": "32px"},
                        ),
                        dmc.TableTd(status_node, style={"height": "32px"}),
                        dmc.TableTd(action, style={"height": "32px"}),
                    ]
                )
            )
        children.append(
            dmc.TableScrollContainer(
                minWidth=520,
                style={"maxHeight": 132, "overflow": "auto"},
                children=dmc.Table(
                    [
                        dmc.TableThead(
                            dmc.TableTr(
                                [
                                    dmc.TableTh("Loại"),
                                    dmc.TableTh("Mục"),
                                    dmc.TableTh("Người tạo"),
                                    dmc.TableTh("Tạo lúc"),
                                    dmc.TableTh("Kẹt bao lâu"),
                                    dmc.TableTh("Trạng thái"),
                                    dmc.TableTh(""),
                                ]
                            )
                        ),
                        dmc.TableTbody(rows),
                    ],
                    highlightOnHover=True,
                    withTableBorder=False,
                    withColumnBorders=False,
                    verticalSpacing=2,
                    style={"fontSize": "13px"},
                ),
            )
        )
    return dmc.Stack(children, gap="xs", p="sm")


def render_health_card(health: dict[str, Any]) -> dmc.Card:
    """Thẻ Sức khỏe hàng đợi & worker (task 62, dời sang trang riêng ở task 66).

    Theo pattern task 60: header tĩnh, callback chỉ cập nhật body
    (không vẽ lại cả card).
    """
    header_group = dmc.Group(
        [
            dmc.Text("Sức khỏe hàng đợi & worker", fw=600, size="sm"),
            dmc.Group(
                [
                    button_subtle(
                        "Làm mới",
                        id="queue-health-refresh-btn",
                        size="xs",
                        icon="lucide:refresh-cw",
                    ),
                    dmc.Anchor(
                        button_subtle("Xem lịch sử", size="xs", icon="lucide:history"),
                        href="/report-runs",
                    ),
                ],
                gap="xs",
            ),
        ],
        justify="space-between",
        align="center",
        p="xs",
    )
    return dmc.Card(
        [
            header_group,
            dmc.Divider(),
            html.Div(
                _health_card_body(health),
                id="queue-health-card-body",
                style={
                    "flex": 1,
                    "minHeight": 0,
                    "maxHeight": 220,
                    "overflow": "auto",
                    "display": "flex",
                    "flexDirection": "column",
                },
            ),
        ],
        withBorder=True,
        padding=0,
        radius="sm",
        style={"flexShrink": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
    )


def layout(**kwargs: Any) -> Any:
    """Giao diện chính màn hình Hàng đợi & worker (task 66)."""
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập để xem thông tin Hàng đợi & worker.", tone="crit")
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="queue-health-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền xem trang Hàng đợi & worker.", tone="crit"),
            ]
        )
    return dmc.Box(
        [
            page_header(
                title="Hàng đợi & worker",
                subtitle="Trạng thái worker và các mục kẹt trong hàng đợi export/báo cáo. Làm mới bằng tay; Hủy theo đúng quyền của từng mục.",
            ),
            render_health_card(fetch_queue_health(ctx)),
        ],
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "padding": "12px 16px",
            "gap": "10px",
        },
    )


@callback(
    Output("queue-health-card-body", "children"),
    Input("queue-health-refresh-btn", "n_clicks"),
    Input({"type": "health-cancel", "kind": ALL, "id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_health_actions(refresh_clicks: int | None, cancel_clicks: list[int | None] | None) -> Any:
    """Làm mới thẻ sức khỏe hoặc hủy 1 mục kẹt (task 62, dời từ dashboard ở task 66).

    Một callback duy nhất cho cả nút Làm mới lẫn các nút Hủy (tránh 2
    callback cùng ghi 1 Output — bài học task 52). Guard chặn re-fire
    khi body vẽ lại (nút Hủy mới tạo có n_clicks=None/0) và khi trigger
    không phải nút bấm (skill dash_callback_safety).
    """
    ctx = get_current_ctx()
    if ctx is None:
        return dash.no_update
    triggered = dash.callback_context.triggered_id
    if triggered is None:
        return dash.no_update
    note: str | None = None
    note_tone = "ok"
    if isinstance(triggered, dict) and triggered.get("type") == "health-cancel":
        triggered_list = dash.callback_context.triggered
        value = triggered_list[0]["value"] if triggered_list else None
        if not value:
            return dash.no_update
        kind = str(triggered.get("kind") or "")
        try:
            item_id = int(triggered.get("id"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return dash.no_update
        if kind == "export":
            res = cancel_export(ctx, item_id)
            label = "export"
        elif kind == "run":
            res = cancel_report_run(ctx, item_id)
            label = "run"
        else:
            return dash.no_update
        if res.ok:
            note = f"Đã hủy {label} #{item_id}."
        else:
            note = res.message or "Không hủy được."
            note_tone = "crit"
    elif triggered == "queue-health-refresh-btn":
        if not refresh_clicks:
            return dash.no_update
    else:
        return dash.no_update
    return _health_card_body(fetch_queue_health(ctx), note=note, note_tone=note_tone)
