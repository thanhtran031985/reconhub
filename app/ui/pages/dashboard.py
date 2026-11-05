from __future__ import annotations

from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, callback, dcc, html

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.services.dashboard import get_dashboard_summary
from app.services.perm import page_gate
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.kpi_card import kpi_card
from app.ui.components.status_chip import status_chip
from app.ui.formatters import format_bytes

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


def render_header(total: int, unchecked: int, last_run_time: str) -> dmc.Group:
    """Header gồm tiêu đề kỳ hiện tại và nút Chạy đối soát."""
    my = datetime.now().strftime("tháng %m/%Y")
    title_text = f"{my.capitalize()}: {total} run, {unchecked} chưa kiểm tra"
    sub_text = f"Tổng quan đối soát. Run gần nhất lúc {last_run_time}."

    return dmc.Group(
        [
            dmc.Stack(
                [
                    dmc.Title(title_text, order=1, id="dashboard-title"),
                    dmc.Text(sub_text, c="dimmed", size="sm", id="dashboard-sub"),
                ],
                gap=4,
            ),
            dmc.Anchor(
                button_primary("Chạy đối soát", icon="lucide:play"),
                href="/runs/new",
            ),
        ],
        justify="space-between",
        align="flex-start",
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
        spacing="md",
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


def render_diff_rate_by_template(diff_rates: list[dict[str, Any]]) -> dmc.Card:
    """Card thống kê tỉ lệ lệch theo template (PRD C1)."""
    header_group = dmc.Group(
        [
            dmc.Text("Tỉ lệ lệch theo template", fw=600, size="md"),
            dmc.Anchor(
                button_subtle("Quản lý template", size="xs", icon="lucide:layout-template"),
                href="/templates",
            ),
        ],
        justify="space-between",
        align="center",
        p="md",
    )

    if not diff_rates:
        content: Any = dmc.Box(
            empty_state(
                title="Chưa có dữ liệu theo template",
                description="Tỉ lệ lệch sẽ được tổng hợp khi có các lần chạy đối soát hoàn thành.",
            ),
            p="xl",
        )
    else:
        headers = [
            dmc.TableTh("Template"),
            dmc.TableTh("Số run", style={"textAlign": "center"}),
            dmc.TableTh("Tổng nhóm so sánh", style={"textAlign": "right"}),
            dmc.TableTh("Nhóm lệch", style={"textAlign": "right"}),
            dmc.TableTh("Tỉ lệ lệch", style={"minWidth": "200px"}),
        ]

        rows = []
        for item in diff_rates:
            t_name = item.get("template_name") or item.get("template_code") or "Template"
            t_code = item.get("template_code", "")
            r_cnt = item.get("run_count", 0)
            tot_comp = item.get("total_compared", 0)
            tot_diff = item.get("total_diff", 0)
            diff_pct = item.get("diff_pct", 0.0)

            diff_str = f"{diff_pct:.1f}%".replace(".", ",")
            progress_color = "teal" if diff_pct == 0 else ("orange" if diff_pct <= 5.0 else "red")

            rows.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(
                            dmc.Stack(
                                [
                                    dmc.Text(t_name, fw=500, size="sm"),
                                    dmc.Text(t_code, c="dimmed", size="xs", className="rh-code"),
                                ],
                                gap=2,
                            )
                        ),
                        dmc.TableTd(
                            dmc.Text(str(r_cnt), size="sm", style={"textAlign": "center"}),
                        ),
                        dmc.TableTd(
                            dmc.Text(
                                f"{tot_comp:,}".replace(",", "."),
                                size="sm",
                                style={"textAlign": "right"},
                            ),
                        ),
                        dmc.TableTd(
                            dmc.Text(
                                f"{tot_diff:,}".replace(",", "."),
                                size="sm",
                                c="red" if tot_diff > 0 else "dimmed",
                                fw=600 if tot_diff > 0 else 400,
                                style={"textAlign": "right"},
                            ),
                        ),
                        dmc.TableTd(
                            dmc.Group(
                                [
                                    dmc.Progress(
                                        value=min(100.0, diff_pct),
                                        color=progress_color,
                                        size="sm",
                                        style={"flex": 1},
                                    ),
                                    dmc.Text(
                                        diff_str,
                                        size="xs",
                                        fw=600,
                                        c=progress_color,
                                        style={"minWidth": "48px", "textAlign": "right"},
                                    ),
                                ],
                                gap="xs",
                                align="center",
                            )
                        ),
                    ]
                )
            )

        content = dmc.Table(
            [
                dmc.TableThead(dmc.TableTr(headers)),
                dmc.TableTbody(rows),
            ],
            highlightOnHover=True,
            withTableBorder=False,
            withColumnBorders=False,
        )

    return dmc.Card(
        [
            header_group,
            dmc.Divider(),
            html.Div(content, style={"overflowX": "auto"}),
        ],
        withBorder=True,
        padding=0,
        radius="sm",
    )


def render_recent_runs_card(recent_items: list[dict[str, Any]]) -> dmc.Card:
    """Card danh sách các lần chạy gần đây nhất."""
    header_group = dmc.Group(
        [
            dmc.Text("Run gần đây", fw=600, size="md"),
            dmc.Anchor(
                button_subtle("Xem lịch sử", size="xs", icon="lucide:history"),
                href="/history",
            ),
        ],
        justify="space-between",
        align="center",
        p="md",
    )

    if not recent_items:
        table_content: Any = dmc.Box(
            empty_state(
                title="Chưa có run nào",
                description="Bắt đầu chạy đối soát để theo dõi tiến độ và kết quả.",
            ),
            p="xl",
        )
    else:
        table_headers = [
            dmc.TableTh("Run"),
            dmc.TableTh("Template"),
            dmc.TableTh("Profile"),
            dmc.TableTh("Khoảng tìm kiếm"),
            dmc.TableTh("Trạng thái"),
            dmc.TableTh("Kiểm tra"),
            dmc.TableTh("Khớp", style={"textAlign": "right"}),
        ]

        table_rows = []
        for r in recent_items:
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
                pct_text = dmc.Text(pct_str, size="sm", fw=500, style={"textAlign": "right"})
            else:
                pct_text = dmc.Text("—", size="sm", c="dimmed", style={"textAlign": "right"})

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
                            )
                        ),
                        dmc.TableTd(r.get("template_name", "Template")),
                        dmc.TableTd(r.get("profile_code", "—")),
                        dmc.TableTd(
                            format_date_range(r.get("p_from"), r.get("p_to")),
                            className="rh-code",
                            style={"whiteSpace": "nowrap"},
                        ),
                        dmc.TableTd(chip_node),
                        dmc.TableTd(chk_chip),
                        dmc.TableTd(pct_text),
                    ]
                )
            )

        table_content = dmc.Table(
            [
                dmc.TableThead(dmc.TableTr(table_headers)),
                dmc.TableTbody(table_rows),
            ],
            highlightOnHover=True,
            withTableBorder=False,
            withColumnBorders=False,
        )

    return dmc.Card(
        [
            header_group,
            dmc.Divider(),
            html.Div(table_content, style={"overflowX": "auto"}),
        ],
        withBorder=True,
        padding=0,
        radius="sm",
    )


def layout() -> html.Div:
    """Giao diện chính màn hình Dashboard."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="dashboard-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập Dashboard.", tone="crit"),
            ]
        )
    return html.Div(
        [
            dcc.Store(id="dashboard-refresh-trigger", data=0),
            dcc.Loading(
                id="dashboard-loading",
                type="circle",
                children=html.Div(id="dashboard-content-container"),
            ),
        ]
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
            return dmc.Stack(
                [
                    render_header(total=0, unchecked=0, last_run_time="—"),
                    empty_state(
                        title="Chưa có run nào trong kỳ",
                        description="Upload một file và chạy đối soát theo template đã đăng ký.",
                        action=dmc.Anchor(
                            button_primary("Chạy đối soát", icon="lucide:play"),
                            href="/runs/new",
                        ),
                    ),
                ],
                gap="lg",
                p="lg",
            )

        header_node = render_header(total, unchecked, last_time)
        kpis_node = render_kpi_grid(stats)
        recent_card = render_recent_runs_card(recent_items)
        diff_card = render_diff_rate_by_template(diff_rates)

        return dmc.Stack(
            [
                header_node,
                kpis_node,
                recent_card,
                diff_card,
            ],
            gap="lg",
            p="lg",
        )

    except Exception as e:
        return alert_box(
            f"Không tải được số liệu tổng hợp. Lỗi: {e!s}",
            tone="crit",
            action=button_subtle("Thử lại", id="dashboard-retry-btn", size="sm"),
        )
