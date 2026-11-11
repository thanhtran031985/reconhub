from __future__ import annotations

from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.services.dashboard import get_dashboard_summary
from app.services.perm import page_gate
from app.services.report_export import cancel_export
from app.services.report_run import cancel_report_run
from app.services.worker_health import WORKER_KIND_LABELS, get_queue_health
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.kpi_card import kpi_card
from app.ui.components.page_header import page_header
from app.ui.components.status_chip import status_chip
from app.ui.formatters import format_bytes
from app.ui.layout.shell import first_nav_href

try:
    dash.register_page(__name__, path="/", title="Dashboard – ReconHub")  # type: ignore[no-untyped-call]
except Exception:
    pass

MENU_CODE = "dashboard"


def format_short_dt(iso_str: str | None) -> str:
    """Định dạng ngày giờ ngắn gọn DD/MM HH:mm."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return str(iso_str)


def format_date_range(p_from: str | None, p_to: str | None) -> str:
    """Định dạng khoảng ngày giờ: 01/02 00:00 → 05/02 23:59."""
    f_str = format_short_dt(p_from)
    t_str = format_short_dt(p_to)
    if f_str == "—" and t_str == "—":
        return "—"
    return f"{f_str} → {t_str}"


def fetch_dashboard_stats(ctx: Ctx) -> dict[str, Any]:
    """Tổng hợp số liệu thống kê cho màn hình Dashboard thông qua service."""
    res = get_dashboard_summary(ctx)
    if not res.ok or not res.data:
        return {}
    return dict(res.data)


def fetch_queue_health(ctx: Ctx) -> dict[str, Any]:
    """Trạng thái hàng đợi/worker cho thẻ sức khỏe (task 62)."""
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


def render_header(total: int, unchecked: int, last_run_time: str) -> dmc.Group:
    """Header gồm tiêu đề kỳ hiện tại và nút Chạy đối soát."""
    my = datetime.now().strftime("tháng %m/%Y")
    title_text = f"{my.capitalize()}: {total} run, {unchecked} chưa kiểm tra"
    sub_text = f"Tổng quan đối soát. Run gần nhất lúc {last_run_time}."

    return page_header(
        title=title_text,
        subtitle=sub_text,
        actions=[
            dmc.Anchor(
                button_primary("Chạy đối soát", icon="lucide:play", size="xs"),
                href="/runs/new",
            ),
        ],
    )


def render_kpi_grid(stats: dict[str, Any]) -> dmc.SimpleGrid:
    """Lưới 4 thẻ KPI chỉ số theo thiết kế Screen01."""
    total = stats.get("total_runs", 0)
    done = stats.get("done_count", 0)
    failed = stats.get("failed_count", 0)
    running = stats.get("running_count", 0)
    unchecked = stats.get("unchecked_count", 0)
    my_work = stats.get("my_work", 0)
    my_unchecked = stats.get("my_unchecked", 0)
    my_failed = stats.get("my_failed", 0)
    avg_match = stats.get("avg_match_pct")
    temp_bytes = stats.get("temp_bytes", 0)

    avg_str = f"{avg_match:.1f}%".replace(".", ",") if avg_match is not None else "—"

    return dmc.SimpleGrid(
        cols={"base": 1, "sm": 2, "md": 4},
        spacing="sm",
        children=[
            kpi_card(
                label="Run trong kỳ",
                value=total,
                meta=f"{done} hoàn thành · {failed} lỗi · {running} đang chạy",
                icon="lucide:play-circle",
            ),
            kpi_card(
                label="Tỉ lệ khớp trung bình",
                value=avg_str,
                tone="ok" if avg_match and avg_match >= 98 else "primary",
                meta="Theo số nhóm so sánh",
                icon="lucide:check-circle-2",
            ),
            kpi_card(
                label="Chưa kiểm tra",
                value=unchecked,
                tone="warn" if unchecked > 0 else "primary",
                meta=f"Dữ liệu tạm {format_bytes(temp_bytes)}",
                icon="lucide:clock",
            ),
            kpi_card(
                label="Việc của tôi",
                value=my_work,
                meta=f"{my_unchecked} run chờ kiểm tra · {my_failed} run lỗi",
                icon="lucide:user-check",
            ),
        ],
    )


def _page_slice(items: list[dict[str, Any]], page: int, page_size: int) -> tuple[list[dict[str, Any]], int, int]:
    """Cắt danh sách theo trang, kẹp số trang vào khoảng hợp lệ."""
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size
    return items[start : start + page_size], total_pages, page


def _showing_text(total: int, page: int, page_size: int, noun: str) -> str:
    """Dòng 'Hiển thị x – y trong tổng số N <noun>' ở footer phân trang."""
    start_idx = (page - 1) * page_size + 1 if total > 0 else 0
    end_idx = min(page * page_size, total)
    return f"Hiển thị {start_idx} – {end_idx} trong tổng số {total} {noun}"


def _pagination_footer(
    total: int, page: int, page_size: int, noun: str, pagination_id: str, showing_id: str | None = None
) -> dmc.Group:
    """Thanh phân trang ở chân card: dòng 'Hiển thị x – y…' + Pagination."""
    total_pages = max(1, (total + page_size - 1) // page_size)
    return dmc.Group(
        justify="space-between",
        align="center",
        px="sm",
        py=6,
        style={
            "borderTop": "1px solid var(--line, #E0E0E0)",
            "backgroundColor": "var(--p2, #FAFAFA)",
            "flexShrink": 0,
            "marginTop": "auto",
        },
        children=[
            dmc.Text(
                _showing_text(total, page, page_size, noun),
                id=showing_id,
                size="xs",
                c="dimmed",
                fw=500,
            ),
            dmc.Pagination(
                id=pagination_id,
                total=total_pages,
                value=page,
                size="xs",
            ),
        ],
    )


def _diff_rate_table_content(diff_rates: list[dict[str, Any]], page: int = 1, page_size: int = 20) -> Any:
    """Phần thân bảng của card Tỉ lệ lệch theo template (chỉ phần dòng).

    Task 60: callback phân trang chỉ vẽ lại vùng này — header và footer
    phân trang nằm ngoài vùng vẽ lại nên Pagination giữ được focus.
    """
    if not diff_rates:
        return dmc.Box(
            empty_state(
                title="Chưa có dữ liệu theo template",
                description="Tỉ lệ lệch sẽ được tổng hợp khi có các lần chạy đối soát hoàn thành.",
            ),
            p="md",
        )

    shown, _total_pages, page = _page_slice(diff_rates, page, page_size)
    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--p2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "12px",
        "fontWeight": 600,
        "textAlign": "center",
    }
    # Card hẹp (4/12): chỉ giữ 3 cột; tổng nhóm/nhóm lệch đưa xuống
    # dòng mờ dưới tên template để không mất thông tin.
    headers = [
        dmc.TableTh("Template", style=th_style),
        dmc.TableTh("Số run", style=th_style),
        dmc.TableTh("Tỉ lệ lệch", style={**th_style, "minWidth": "160px"}),
    ]

    rows = []
    for item in shown:
        t_name = item.get("template_name") or item.get("template_code") or "Template"
        t_code = item.get("template_code", "")
        r_cnt = item.get("run_count", 0)
        tot_comp = item.get("total_compared", 0)
        tot_diff = item.get("total_diff", 0)
        diff_pct = item.get("diff_pct", 0.0)

        diff_str = f"{diff_pct:.1f}%".replace(".", ",")
        progress_color = "teal" if diff_pct == 0 else ("orange" if diff_pct <= 5.0 else "red")
        sub_text = (
            f"{t_code} · {f'{tot_comp:,}'.replace(',', '.')} nhóm · {f'{tot_diff:,}'.replace(',', '.')} lệch"
            if t_code
            else f"{f'{tot_comp:,}'.replace(',', '.')} nhóm · {f'{tot_diff:,}'.replace(',', '.')} lệch"
        )

        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Stack(
                            [
                                dmc.Text(t_name, fw=500, size="xs", lh=1.2),
                                dmc.Text(sub_text, c="dimmed", size="xs", lh=1.2, className="rh-code"),
                            ],
                            gap=0,
                        ),
                        style={"height": "32px"},
                    ),
                    dmc.TableTd(
                        dmc.Text(str(r_cnt), size="xs", style={"textAlign": "center"}),
                        style={"height": "32px"},
                    ),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.Progress(
                                    value=min(100.0, diff_pct),
                                    color=progress_color,
                                    size="xs",
                                    style={"flex": 1},
                                ),
                                dmc.Text(
                                    diff_str,
                                    size="xs",
                                    fw=600,
                                    c=progress_color,
                                    style={"minWidth": "42px", "textAlign": "right"},
                                ),
                            ],
                            gap="xs",
                            align="center",
                        ),
                        style={"height": "32px"},
                    ),
                ]
            )
        )

    content = dmc.TableScrollContainer(
        minWidth=300,
        # 20 dòng/trang không vừa hết ở 1366x768/1440x900 nên bảng cuộn
        # trong card; trang vẫn không cuộn, footer phân trang luôn hiện.
        style={"height": "100%", "overflow": "auto"},
        children=dmc.Table(
            [
                dmc.TableThead(dmc.TableTr(headers)),
                dmc.TableTbody(rows),
            ],
            highlightOnHover=True,
            withTableBorder=False,
            withColumnBorders=False,
            verticalSpacing=0,
            style={"fontSize": "13px"},
        ),
    )
    return content


def render_diff_rate_by_template(diff_rates: list[dict[str, Any]], page: int = 1, page_size: int = 20) -> dmc.Card:
    """Card thống kê tỉ lệ lệch theo template (PRD C1)."""
    header_group = dmc.Group(
        [
            dmc.Text("Tỉ lệ lệch theo template", fw=600, size="sm"),
            dmc.Anchor(
                button_subtle("Quản lý template", size="xs", icon="lucide:layout-template"),
                href="/templates",
            ),
        ],
        justify="space-between",
        align="center",
        p="xs",
    )
    _shown, _total_pages, page = _page_slice(diff_rates, page, page_size)
    return dmc.Card(
        [
            header_group,
            dmc.Divider(),
            html.Div(
                _diff_rate_table_content(diff_rates, page, page_size),
                id="dashboard-diff-card-body",
                style={
                    "flex": 1,
                    "minHeight": 0,
                    "overflow": "hidden",
                    "display": "flex",
                    "flexDirection": "column",
                },
            ),
            _pagination_footer(
                len(diff_rates), page, page_size, "template", "dashboard-diff-pagination", "dashboard-diff-showing"
            ),
        ],
        withBorder=True,
        padding=0,
        radius="sm",
        style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
    )


def _recent_runs_table_content(recent_items: list[dict[str, Any]], page: int = 1, page_size: int = 20) -> Any:
    """Phần thân bảng của card Run gần đây (chỉ phần dòng).

    Task 60: callback phân trang chỉ vẽ lại vùng này — header và footer
    phân trang nằm ngoài vùng vẽ lại nên Pagination giữ được focus.
    """
    if not recent_items:
        return dmc.Box(
            empty_state(
                title="Chưa có run nào",
                description="Bắt đầu chạy đối soát để theo dõi tiến độ và kết quả.",
            ),
            p="md",
        )

    shown, _total_pages, page = _page_slice(recent_items, page, page_size)
    th_style = {
        "position": "sticky",
        "top": 0,
        "backgroundColor": "var(--p2, #FAFAFA)",
        "zIndex": 1,
        "height": "32px",
        "fontSize": "12px",
        "fontWeight": 600,
        "textAlign": "center",
    }
    table_headers = [
        dmc.TableTh("Run", style=th_style),
        dmc.TableTh("Template", style=th_style),
        dmc.TableTh("Profile", style=th_style),
        dmc.TableTh("Khoảng tìm kiếm", style=th_style),
        dmc.TableTh("Trạng thái", style=th_style),
        dmc.TableTh("Kiểm tra", style=th_style),
        dmc.TableTh("Khớp", style=th_style),
    ]

    table_rows = []
    for r in shown:
        r_id = r["id"]
        # Status chip
        status_val = r.get("status", "QUEUED")
        has_diff = (
            (r.get("cnt_mismatch", 0) > 0)
            or (r.get("cnt_missing_in_db", 0) > 0)
            or (r.get("cnt_missing_in_excel", 0) > 0)
        )
        if status_val == "DONE":
            if has_diff:
                chip_node = status_chip("MISMATCH", label="Có lệch", icon="lucide:flag")
            else:
                chip_node = status_chip("MATCHED", label="Khớp", icon="lucide:check")
        elif status_val == "RUNNING":
            pct = r.get("progress_pct", 0)
            chip_node = status_chip("RUNNING", label=f"Đang chạy {pct}%", icon="lucide:loader")
        elif status_val == "FAILED":
            chip_node = status_chip("FAILED", label="Lỗi", icon="lucide:alert-triangle")
        else:
            chip_node = status_chip(status_val)

        # Checked chip
        if r.get("checked_at"):
            chk_chip = status_chip("CHECKED", label="Đã kiểm tra", icon="lucide:check")
        else:
            chk_chip = status_chip("UNCHECKED", label="Chưa kiểm tra", icon="lucide:circle")

        # Match pct
        m_pct = r.get("match_pct")
        if m_pct is not None and status_val == "DONE":
            pct_str = f"{m_pct:.1f}%".replace(".", ",")
            pct_text = dmc.Text(pct_str, size="xs", fw=500, style={"textAlign": "right"})
        else:
            pct_text = dmc.Text("—", size="xs", c="dimmed", style={"textAlign": "right"})

        table_rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(
                        dmc.Anchor(
                            f"#{r_id}",
                            href=f"/runs/{r_id}",
                            className="rh-code",
                            fw=600,
                            underline="hover",
                            size="xs",
                        ),
                        style={"height": "32px"},
                    ),
                    dmc.TableTd(r.get("template_name", "Template"), style={"height": "32px", "fontSize": "13px"}),
                    dmc.TableTd(r.get("profile_code", "—"), style={"height": "32px", "fontSize": "13px"}),
                    dmc.TableTd(
                        format_date_range(r.get("p_from"), r.get("p_to")),
                        className="rh-code",
                        style={"whiteSpace": "nowrap", "height": "32px", "fontSize": "12px"},
                    ),
                    dmc.TableTd(chip_node, style={"height": "32px"}),
                    dmc.TableTd(chk_chip, style={"height": "32px"}),
                    dmc.TableTd(pct_text, style={"height": "32px"}),
                ]
            )
        )

    table_content = dmc.TableScrollContainer(
        minWidth=520,
        # 20 dòng/trang không vừa hết ở 1366x768/1440x900 nên bảng cuộn
        # trong card; trang vẫn không cuộn, footer phân trang luôn hiện.
        style={"height": "100%", "overflow": "auto"},
        children=dmc.Table(
            [
                dmc.TableThead(dmc.TableTr(table_headers)),
                dmc.TableTbody(table_rows),
            ],
            highlightOnHover=True,
            withTableBorder=False,
            withColumnBorders=False,
            verticalSpacing=2,
            style={"fontSize": "13px"},
        ),
    )
    return table_content


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
            href = f"/runs/{item['run_id']}" if item["kind"] == "run" else "/report-runs"
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
    """Thẻ Sức khỏe hàng đợi & worker (task 62).

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
                        id="dashboard-health-refresh-btn",
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
                id="dashboard-health-card-body",
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


def render_recent_runs_card(recent_items: list[dict[str, Any]], page: int = 1, page_size: int = 20) -> dmc.Card:
    """Card danh sách các lần chạy gần đây nhất."""
    header_group = dmc.Group(
        [
            dmc.Text("Run gần đây", fw=600, size="sm"),
            dmc.Anchor(
                button_subtle("Xem lịch sử", size="xs", icon="lucide:history"),
                href="/history",
            ),
        ],
        justify="space-between",
        align="center",
        p="xs",
    )
    _shown, _total_pages, page = _page_slice(recent_items, page, page_size)
    return dmc.Card(
        [
            header_group,
            dmc.Divider(),
            html.Div(
                _recent_runs_table_content(recent_items, page, page_size),
                id="dashboard-recent-card-body",
                style={
                    "flex": 1,
                    "minHeight": 0,
                    "overflow": "hidden",
                    "display": "flex",
                    "flexDirection": "column",
                },
            ),
            _pagination_footer(
                len(recent_items), page, page_size, "run", "dashboard-recent-pagination", "dashboard-recent-showing"
            ),
        ],
        withBorder=True,
        padding=0,
        radius="sm",
        style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
    )


def layout() -> Any:
    """Giao diện chính màn hình Dashboard."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        if gate == "/suspended":
            # Q2 (task 20): trang chủ bị ẩn thì về menu đầu tiên người
            # dùng có, thay vì trang "Chức năng tạm ngưng".
            first = first_nav_href(ctx)
            if first:
                return html.Div(
                    [
                        dcc.Location(id="dashboard-forbidden-redirect", href=first),
                        alert_box("Dashboard đang tạm ẩn, bạn được chuyển tới mục đầu tiên.", tone="warn"),
                    ]
                )
        return html.Div(
            [
                dcc.Location(id="dashboard-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập Dashboard.", tone="crit"),
            ]
        )
    return dmc.Box(
        [
            dcc.Store(id="dashboard-refresh-trigger", data=0),
            # Task 60: bỏ dcc.Loading quanh nội dung — spinner hiện cả khi
            # bấm phân trang vì callback phân trang ghi vào vùng trong
            # Loading (dữ liệu đã nằm trong store, không có server
            # round-trip). Lúc mở trang, vùng nội dung hiện trạng thái tải
            # nhỏ; render_dashboard thay bằng nội dung thật khi xong.
            html.Div(
                id="dashboard-content-container",
                children=dmc.Group(
                    [
                        dmc.Loader(size="sm"),
                        dmc.Text("Đang tải dashboard…", size="sm", c="dimmed"),
                    ],
                    justify="center",
                    align="center",
                    style={"flex": 1, "minHeight": 0},
                ),
                style={"flex": 1, "minHeight": 0, "display": "flex", "flexDirection": "column"},
            ),
        ],
        style={"height": "100%", "minHeight": 0, "display": "flex", "flexDirection": "column", "overflow": "hidden"},
    )


@callback(
    Output("dashboard-content-container", "children"),
    Input("dashboard-refresh-trigger", "data"),
)
def render_dashboard(_refresh: int) -> Any:
    """Dựng nội dung toàn bộ màn hình Dashboard theo 4 trạng thái."""
    ctx = get_current_ctx()
    if ctx is None:
        return alert_box("Bạn cần đăng nhập để xem thông tin Dashboard.", tone="crit")

    try:
        stats = fetch_dashboard_stats(ctx)
        total = stats.get("total_runs", 0)
        unchecked = stats.get("unchecked_count", 0)
        last_time = stats.get("last_run_time", "—")
        recent_items = stats.get("recent_runs", [])
        diff_rates = stats.get("diff_rate_by_template", [])

        # Kiểm tra trạng thái rỗng
        if total == 0:
            return dmc.Box(
                [
                    render_header(total=0, unchecked=0, last_run_time="—"),
                    empty_state(
                        title="Chưa có run nào trong kỳ",
                        description="Upload một file và chạy đối soát theo template đã đăng ký.",
                        action=dmc.Anchor(
                            button_primary("Chạy đối soát", icon="lucide:play", size="xs"),
                            href="/runs/new",
                        ),
                    ),
                    # Task 62 (D7): thẻ sức khỏe vẫn hiện cả khi chưa có
                    # run — đúng lúc cần biết worker có chạy không.
                    render_health_card(fetch_queue_health(ctx)),
                ],
                style={
                    "height": "100%",
                    "display": "flex",
                    "flexDirection": "column",
                    "padding": "12px 16px",
                    "gap": "10px",
                },
            )

        header_node = render_header(total, unchecked, last_time)
        kpis_node = render_kpi_grid(stats)

        return dmc.Box(
            [
                dcc.Store(id="dashboard-recent-store", data=recent_items),
                dcc.Store(id="dashboard-diff-store", data=diff_rates),
                header_node,
                kpis_node,
                # Hàng 2 card dùng Group flex thay cho dmc.Grid: Grid của
                # Mantine v8 có root display:block nên inner không kéo giãn
                # theo chiều cao, card không sát đáy; Group flex thì cột
                # stretch đúng chiều cao hàng ở mọi độ phân giải.
                dmc.Group(
                    [
                        html.Div(
                            html.Div(
                                render_recent_runs_card(recent_items),
                                id="dashboard-recent-card",
                                style={"height": "100%", "display": "flex", "flexDirection": "column", "minHeight": 0},
                            ),
                            style={
                                "flex": "8 1 0",
                                "minWidth": 560,
                                # Cột không được cao hơn hàng (Group wrap
                                # làm line cao theo nội dung): chặn ở 100%
                                # để 20 dòng cuộn trong card thay vì tràn.
                                "maxHeight": "100%",
                                "display": "flex",
                                "flexDirection": "column",
                                "minHeight": 0,
                            },
                        ),
                        html.Div(
                            html.Div(
                                render_diff_rate_by_template(diff_rates),
                                id="dashboard-diff-card",
                                style={"height": "100%", "display": "flex", "flexDirection": "column", "minHeight": 0},
                            ),
                            style={
                                "flex": "4 1 0",
                                "minWidth": 320,
                                # Như cột Run gần đây: chặn ở 100% chiều
                                # cao hàng để bảng cuộn trong card.
                                "maxHeight": "100%",
                                "display": "flex",
                                "flexDirection": "column",
                                "minHeight": 0,
                            },
                        ),
                    ],
                    gap="sm",
                    wrap="wrap",
                    align="stretch",
                    # auto thay vì hidden: ở cỡ chuẩn nội dung vừa khít
                    # nên không cuộn; màn hẹp xếp dọc thì cuộn trong Group.
                    style={"flex": 1, "minHeight": 0, "overflow": "auto"},
                ),
                # Task 62: thẻ sức khỏe hàng đợi & worker — hàng riêng
                # dưới 2 card (Group flex:1 co lại vừa khung, thẻ cố
                # định chiều cao theo nội dung, danh sách kẹt cuộn trong).
                render_health_card(fetch_queue_health(ctx)),
            ],
            style={
                # Cao bằng đúng vùng nội dung của shell (100vh - header 44px
                # - padding trên 44px của AppShellMain) để hàng card kéo
                # sát đáy ở mọi độ phân giải; đo kiểm chứng 1366x768/1440x900.
                "height": "calc(100vh - 88px)",
                "minHeight": 0,
                "display": "flex",
                "flexDirection": "column",
                "overflow": "hidden",
                "padding": "12px 16px",
                "gap": "10px",
            },
        )

    except Exception as e:
        return alert_box(
            f"Không tải được số liệu tổng hợp. Lỗi: {e!s}",
            tone="crit",
            action=button_subtle("Thử lại", id="dashboard-retry-btn", size="sm"),
        )


@callback(
    # Task 60: chỉ vẽ lại thân bảng + dòng "Hiển thị x–y" + tổng số trang
    # của Pagination (prop, không trả lại component). Header, footer và
    # node Pagination nằm ngoài vùng vẽ lại nên giữ được focus.
    Output("dashboard-recent-card-body", "children"),
    Output("dashboard-recent-showing", "children"),
    Output("dashboard-recent-pagination", "total"),
    Input("dashboard-recent-pagination", "value"),
    State("dashboard-recent-store", "data"),
    prevent_initial_call=True,
)
def _update_recent_card(page: int | None, items: list[dict[str, Any]] | None) -> tuple[Any, str, int]:
    """Chuyển trang card Run gần đây (cắt 20 dòng/trang phía client)."""
    items = items or []
    _shown, total_pages, clamped = _page_slice(items, page or 1, 20)
    return (
        _recent_runs_table_content(items, page=clamped),
        _showing_text(len(items), clamped, 20, "run"),
        total_pages,
    )


@callback(
    # Task 60: như card Run gần đây — chỉ vẽ lại thân bảng + dòng hiển
    # thị + tổng số trang; Pagination không bị hủy/vẽ lại.
    Output("dashboard-diff-card-body", "children"),
    Output("dashboard-diff-showing", "children"),
    Output("dashboard-diff-pagination", "total"),
    Input("dashboard-diff-pagination", "value"),
    State("dashboard-diff-store", "data"),
    prevent_initial_call=True,
)
def _update_diff_card(page: int | None, rates: list[dict[str, Any]] | None) -> tuple[Any, str, int]:
    """Chuyển trang card Tỉ lệ lệch theo template (cắt 20 dòng/trang phía client)."""
    rates = rates or []
    _shown, total_pages, clamped = _page_slice(rates, page or 1, 20)
    return (
        _diff_rate_table_content(rates, page=clamped),
        _showing_text(len(rates), clamped, 20, "template"),
        total_pages,
    )


@callback(
    Output("dashboard-health-card-body", "children"),
    Input("dashboard-health-refresh-btn", "n_clicks"),
    Input({"type": "health-cancel", "kind": ALL, "id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_health_actions(refresh_clicks: int | None, cancel_clicks: list[int | None] | None) -> Any:
    """Làm mới thẻ sức khỏe hoặc hủy 1 mục kẹt (task 62).

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
    elif triggered == "dashboard-health-refresh-btn":
        if not refresh_clicks:
            return dash.no_update
    else:
        return dash.no_update
    return _health_card_body(fetch_queue_health(ctx), note=note, note_tone=note_tone)
