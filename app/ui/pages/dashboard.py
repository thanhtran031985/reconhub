from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, callback, dcc, html
from sqlalchemy import desc, func, select

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.db.metadata import recon_run, recon_run_summary, recon_template
from app.services.temp_data import usage
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
    """Tổng hợp số liệu thống kê cho màn hình Dashboard."""
    engine = get_recon_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_of_month = datetime(now.year, now.month, 1)

    with engine.connect() as conn:
        # 1. Thống kê run trong tháng hiện tại
        runs_query = select(recon_run).where(recon_run.c.CREATED_AT >= start_of_month)
        all_month_runs = conn.execute(runs_query).mappings().fetchall()
        total_runs = len(all_month_runs)

        done_count = sum(1 for r in all_month_runs if r["STATUS"] == "DONE")
        failed_count = sum(1 for r in all_month_runs if r["STATUS"] == "FAILED")
        running_count = sum(1 for r in all_month_runs if r["STATUS"] in ("RUNNING", "QUEUED"))

        unchecked_count = sum(1 for r in all_month_runs if r["STATUS"] == "DONE" and r["CHECKED_AT"] is None)

        # Việc của tôi: các run của user hiện tại đang chờ kiểm tra hoặc bị lỗi
        my_unchecked = sum(
            1
            for r in all_month_runs
            if r["CREATED_BY"] == ctx.username and r["STATUS"] == "DONE" and r["CHECKED_AT"] is None
        )
        my_failed = sum(1 for r in all_month_runs if r["CREATED_BY"] == ctx.username and r["STATUS"] == "FAILED")
        my_work = my_unchecked + my_failed

        # 2. Tính tỷ lệ khớp trung bình từ recon_run_summary
        avg_match_pct: float | None = None
        sum_stmt = (
            select(
                func.sum(recon_run_summary.c.CNT_MATCHED).label("TOTAL_MATCHED"),
                func.sum(recon_run_summary.c.CNT_MISMATCH).label("TOTAL_MISMATCH"),
                func.sum(recon_run_summary.c.CNT_MISSING_IN_DB).label("TOTAL_MISSING_DB"),
                func.sum(recon_run_summary.c.CNT_MISSING_IN_EXCEL).label("TOTAL_MISSING_EXCEL"),
            )
            .select_from(
                recon_run_summary.join(recon_run, recon_run_summary.c.RUN_ID == recon_run.c.ID)
            )
            .where(recon_run.c.CREATED_AT >= start_of_month, recon_run.c.STATUS == "DONE")
        )
        sums = conn.execute(sum_stmt).mappings().first()
        if sums and sums["TOTAL_MATCHED"] is not None:
            tot_matched = sums["TOTAL_MATCHED"] or 0
            tot_diff = (
                (sums["TOTAL_MISMATCH"] or 0)
                + (sums["TOTAL_MISSING_DB"] or 0)
                + (sums["TOTAL_MISSING_EXCEL"] or 0)
            )
            tot_compared = tot_matched + tot_diff
            if tot_compared > 0:
                avg_match_pct = round((tot_matched / tot_compared) * 100, 1)

        # 3. Lấy 5 run gần đây nhất
        recent_stmt = (
            select(
                recon_run.c.ID,
                recon_run.c.PROFILE_CODE,
                recon_run.c.STATUS,
                recon_run.c.PROGRESS_PCT,
                recon_run.c.CREATED_AT,
                recon_run.c.CHECKED_AT,
                recon_run.c.CHECKED_BY,
                recon_run.c.P_FROM,
                recon_run.c.P_TO,
                recon_template.c.NAME.label("TEMPLATE_NAME"),
                recon_template.c.CODE.label("TEMPLATE_CODE"),
                recon_run_summary.c.CNT_MATCHED,
                recon_run_summary.c.CNT_MISMATCH,
                recon_run_summary.c.CNT_MISSING_IN_DB,
                recon_run_summary.c.CNT_MISSING_IN_EXCEL,
            )
            .select_from(
                recon_run.outerjoin(recon_template, recon_run.c.TEMPLATE_ID == recon_template.c.ID)
                .outerjoin(recon_run_summary, recon_run.c.ID == recon_run_summary.c.RUN_ID)
            )
            .order_by(desc(recon_run.c.CREATED_AT))
            .limit(10)
        )
        recent_rows = conn.execute(recent_stmt).mappings().fetchall()

        recent_items = []
        for r in recent_rows:
            cnt_matched = r["CNT_MATCHED"] or 0
            cnt_mismatch = r["CNT_MISMATCH"] or 0
            cnt_missing_db = r["CNT_MISSING_IN_DB"] or 0
            cnt_missing_excel = r["CNT_MISSING_IN_EXCEL"] or 0
            tot_comp = cnt_matched + cnt_mismatch + cnt_missing_db + cnt_missing_excel
            m_pct = round((cnt_matched / tot_comp) * 100, 1) if tot_comp > 0 else (100.0 if r["STATUS"] == "DONE" else None)

            recent_items.append(
                {
                    "id": int(r["ID"]),
                    "template_name": str(r["TEMPLATE_NAME"] or r["TEMPLATE_CODE"] or "Template"),
                    "profile_code": str(r["PROFILE_CODE"] or "—"),
                    "status": str(r["STATUS"]),
                    "progress_pct": int(r["PROGRESS_PCT"] or 0),
                    "created_at": r["CREATED_AT"].isoformat() if r["CREATED_AT"] else None,
                    "checked_at": r["CHECKED_AT"].isoformat() if r["CHECKED_AT"] else None,
                    "checked_by": r["CHECKED_BY"],
                    "p_from": r["P_FROM"].isoformat() if r["P_FROM"] else None,
                    "p_to": r["P_TO"].isoformat() if r["P_TO"] else None,
                    "cnt_mismatch": cnt_mismatch,
                    "cnt_missing_in_db": cnt_missing_db,
                    "cnt_missing_in_excel": cnt_missing_excel,
                    "match_pct": m_pct,
                }
            )

        # Thời gian run gần nhất
        last_run_time_str = "—"
        if recent_items and recent_items[0]["created_at"]:
            try:
                l_dt = datetime.fromisoformat(recent_items[0]["created_at"])
                last_run_time_str = l_dt.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                pass

    # Lấy thông tin dữ liệu tạm từ service usage
    temp_bytes = 0
    try:
        u_res = usage(ctx)
        if u_res.ok and u_res.data:
            temp_bytes = u_res.data.get("total_bytes", 0)
    except Exception:
        pass

    return {
        "total_runs": total_runs,
        "done_count": done_count,
        "failed_count": failed_count,
        "running_count": running_count,
        "unchecked_count": unchecked_count,
        "my_work": my_work,
        "my_unchecked": my_unchecked,
        "my_failed": my_failed,
        "avg_match_pct": avg_match_pct,
        "recent_runs": recent_items,
        "last_run_time": last_run_time_str,
        "temp_bytes": temp_bytes,
    }


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
        table_content = dmc.Box(
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

        return dmc.Stack(
            [
                header_node,
                kpis_node,
                recent_card,
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
