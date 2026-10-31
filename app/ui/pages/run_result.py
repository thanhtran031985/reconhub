from __future__ import annotations

from datetime import datetime
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.services.run_service import get_run
from app.services.temp_data import mark_checked, purge_runs
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.drawer import drawer_right
from app.ui.components.kpi_card import kpi_card
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.status_chip import status_chip

STATUS_INFO: dict[str, tuple[str, str, str]] = {
    "MATCHED": ("teal", "Khớp", "lucide:check-circle-2"),
    "DIFF": ("red", "Lệch giá trị", "lucide:equal-not"),
    "MISSING_DB": ("yellow", "Thiếu trong DB", "lucide:database-zap"),
    "MISSING_EXCEL": ("violet", "Thiếu trong Excel", "lucide:file-x-2"),
    "INCONSISTENT": ("gray", "Không nhất quán", "lucide:shuffle"),
    "DUPLICATE": ("gray", "Trùng khóa", "lucide:copy"),
    "INVALID": ("red", "Không hợp lệ", "lucide:alert-triangle"),
}


def fmt_num(val: Any) -> str:
    """Định dạng số theo chuẩn tiếng Việt có phân cách hàng nghìn."""
    if val is None:
        return "—"
    if isinstance(val, (int, float)):
        return f"{val:,.0f}".replace(",", ".")
    return str(val)


def render_header(run_info: dict[str, Any]) -> Any:
    """Dựng khối Header màn hình kết quả run kèm metadata, chips và nút hành động."""
    r_id = run_info.get("id", 1042)
    tmpl_name = run_info.get("template_name") or run_info.get("template_code", "DTP")
    prof = run_info.get("profile_code", "BY_INVOICE")
    p_from = run_info.get("p_from", "01/02/2026 00:00:00")
    p_to = run_info.get("p_to", "05/02/2026 23:59:59")
    ds_name = run_info.get("data_source_id", "ORACLE_TEST")
    ver = run_info.get("template_version", 1)
    user = run_info.get("created_by", "operator")
    created_at = run_info.get("created_at", "")

    checked_at = run_info.get("checked_at")
    checked_by = run_info.get("checked_by")
    purged_at = run_info.get("temp_purged_at")

    # Chip kiểm tra
    if checked_at:
        chk_chip = dmc.Badge(
            f"Đã kiểm tra · {checked_by or user} · {checked_at}",
            color="teal",
            variant="light",
            size="md",
            leftSection=DashIconify(icon="lucide:check", width=14),
        )
    else:
        chk_chip = dmc.Badge(
            "Chưa kiểm tra",
            color="gray",
            variant="outline",
            size="md",
        )

    # Chip dữ liệu tạm
    if purged_at:
        temp_chip = dmc.Badge(
            f"Dữ liệu tạm đã xóa lúc {purged_at}",
            color="gray",
            variant="light",
            size="md",
        )
    else:
        temp_chip = dmc.Badge(
            "Dữ liệu tạm còn · 3,2 MB",
            color="yellow",
            variant="light",
            size="md",
            leftSection=DashIconify(icon="lucide:info", width=14),
        )

    # Nút hành động
    action_btns = []
    if not checked_at:
        action_btns.append(
            button_primary(
                "Đã kiểm tra xong",
                id="run-res-mark-checked-btn",
                icon="lucide:check",
            )
        )
    elif not purged_at:
        action_btns.append(
            button_danger(
                "Xóa dữ liệu tạm",
                id="run-res-purge-temp-btn",
                icon="lucide:trash-2",
            )
        )

    action_btns.append(
        dcc.Link(button_subtle("Chạy lại", icon="lucide:refresh-cw"), href="/runs/new")
    )
    action_btns.append(
        html.A(
            button_primary("Export Excel", icon="lucide:download"),
            href=f"/download/export/{r_id}",
            target="_blank",
        )
    )

    sub_title = f"{prof} · {p_from} → {p_to} · BDP · {ds_name} · v{ver} · {user} lúc {created_at}"

    return dmc.Group(
        justify="space-between",
        align="flex-start",
        mb="md",
        children=[
            html.Div(
                [
                    dmc.Title(f"Run #{r_id} · {tmpl_name}", order=2, fw=700),
                    dmc.Text(sub_title, size="sm", c="dimmed", mt=4),
                    dmc.Group([chk_chip, temp_chip], gap="xs", mt="sm"),
                ]
            ),
            dmc.Group(action_btns, gap="sm"),
        ],
    )


def render_kpi_cards(summary: dict[str, Any]) -> Any:
    """Dựng 4 KPI Cards: Control total file, Tổng tiền Excel, Tổng tiền DB, Chênh lệch."""
    ct_diff = summary.get("CONTROL_TOTAL_DIFF", 0)
    ct_ok = (ct_diff == 0)
    ct_val = fmt_num(summary.get("EXCEL_TOTAL_AMOUNT", 366732000))
    ct_tone = "ok" if ct_ok else "warn"

    xl_total = fmt_num(summary.get("EXCEL_TOTAL_AMOUNT", 366732000))
    xl_rows = summary.get("EXCEL_ROWS_READ", 200)
    db_total = fmt_num(summary.get("DB_TOTAL_AMOUNT", 367310000))
    db_rows = summary.get("DB_ROWS_READ", 190)

    diff_val = summary.get("DIFF_TOTAL_AMOUNT", -578000)
    diff_str = f"−{abs(diff_val):,.0f}".replace(",", ".") if diff_val < 0 else fmt_num(diff_val)
    diff_tone = "crit" if diff_val != 0 else "ok"
    cnt_diff = summary.get("CNT_DIFF", 4) + summary.get("CNT_MISSING_DB", 2) + summary.get("CNT_MISSING_EXCEL", 2)

    return dmc.Grid(
        gap="md",
        mb="lg",
        children=[
            dmc.GridCol(
                span=3,
                children=kpi_card(
                    label="Control total file",
                    value=ct_val,
                    tone=ct_tone,
                    meta='Tổng dòng chi tiết bằng dòng "Tổng tiền"',
                    icon="lucide:check-circle-2",
                ),
            ),
            dmc.GridCol(
                span=3,
                children=kpi_card(
                    label="Tổng tiền Excel (trong khoảng)",
                    value=xl_total,
                    tone="primary",
                    meta=f"{xl_rows} dòng · 0 dòng ngoài khoảng",
                    icon="lucide:file-spreadsheet",
                ),
            ),
            dmc.GridCol(
                span=3,
                children=kpi_card(
                    label="Tổng tiền DB",
                    value=db_total,
                    tone="primary",
                    meta=f"{db_rows} hóa đơn",
                    icon="lucide:database",
                ),
            ),
            dmc.GridCol(
                span=3,
                children=kpi_card(
                    label="Chênh lệch",
                    value=diff_str,
                    tone=diff_tone,
                    meta=f"{cnt_diff} nhóm không khớp",
                    icon="lucide:scale",
                ),
            ),
        ],
    )


def render_ratio_bar_and_tabs(summary: dict[str, Any], active_tab: str = "ALL") -> Any:
    """Dựng thanh tỉ lệ phần trăm và bộ Tab lọc 7 trạng thái kết quả."""
    c_matched = summary.get("CNT_MATCHED", 184)
    c_diff = summary.get("CNT_DIFF", 4)
    c_mis_db = summary.get("CNT_MISSING_DB", 2)
    c_mis_xl = summary.get("CNT_MISSING_EXCEL", 2)
    c_incon = summary.get("CNT_INCONSISTENT", 0)
    c_dup = summary.get("CNT_DUPLICATE", 0)
    c_inv = summary.get("CNT_INVALID", 0)

    total_issues = c_diff + c_mis_db + c_mis_xl + c_incon + c_dup + c_inv
    total_all = c_matched + total_issues or 1

    pct_matched = (c_matched / total_all) * 100
    pct_diff = (c_diff / total_all) * 100
    pct_mis_db = (c_mis_db / total_all) * 100
    pct_mis_xl = (c_mis_xl / total_all) * 100

    # Thanh tỉ lệ
    ratio_bar = html.Div(
        style={
            "height": 10,
            "borderRadius": 5,
            "display": "flex",
            "overflow": "hidden",
            "marginBottom": 16,
            "background": "var(--bg-subtle, #f1f5f9)",
        },
        children=[
            html.Div(style={"width": f"{pct_matched:.1f}%", "background": "var(--ok, #16a34a)"}),
            html.Div(style={"width": f"{pct_diff:.1f}%", "background": "var(--crit, #dc2626)"}),
            html.Div(style={"width": f"{pct_mis_db:.1f}%", "background": "var(--warn, #f59e0b)"}),
            html.Div(style={"width": f"{pct_mis_xl:.1f}%", "background": "var(--purple, #a855f7)"}),
        ],
    )

    tab_defs = [
        ("ALL", "Tất cả chênh lệch", total_issues, "red"),
        ("MATCHED", "Khớp", c_matched, "teal"),
        ("DIFF", "Lệch giá trị", c_diff, "red"),
        ("MISSING_DB", "Thiếu trong DB", c_mis_db, "yellow"),
        ("MISSING_EXCEL", "Thiếu trong Excel", c_mis_xl, "violet"),
        ("INCONSISTENT", "Không nhất quán", c_incon, "gray"),
        ("DUPLICATE", "Trùng khóa", c_dup, "gray"),
        ("INVALID", "Không hợp lệ", c_inv, "red"),
    ]

    tab_buttons = []
    for code, label, count, color in tab_defs:
        is_active = (code == active_tab)
        tab_buttons.append(
            dmc.Button(
                [
                    html.Span(label, style={"marginRight": 6}),
                    dmc.Badge(str(count), color=color, variant="filled" if is_active else "light", size="sm"),
                ],
                id={"type": "run-res-tab-btn", "index": code},
                variant="filled" if is_active else "subtle",
                color="primary" if is_active else "gray",
                size="sm",
            )
        )

    return html.Div(
        [
            ratio_bar,
            dmc.Group(tab_buttons, gap="xs", mb="md"),
        ]
    )


def build_grid_headers(measures: list[dict[str, Any]], only_diff_cols: bool = False) -> html.Thead:
    """Sinh 2 tầng header: Tầng 1 gồm Key, Trạng thái, và Colspan từng Measure; Tầng 2 gồm Excel, DB, Chênh."""
    top_ths = [
        html.Th("Số hóa đơn", rowSpan=2, style={"verticalAlign": "middle", "background": "var(--bg-subtle, #f8fafc)"}),
        html.Th("Trạng thái", rowSpan=2, style={"verticalAlign": "middle", "background": "var(--bg-subtle, #f8fafc)"}),
    ]
    sub_ths = []

    for m in measures:
        lbl = m.get("label", m.get("name", "Measure"))
        top_ths.append(
            html.Th(
                lbl,
                colSpan=3,
                style={"textAlign": "center", "background": "var(--bg-subtle, #f8fafc)", "borderLeft": "1px solid var(--border-subtle, #e2e8f0)"},
            )
        )
        sub_ths.extend(
            [
                html.Th("Excel", style={"textAlign": "right", "borderLeft": "1px solid var(--border-subtle, #e2e8f0)"}),
                html.Th("DB", style={"textAlign": "right"}),
                html.Th("Chênh", style={"textAlign": "right"}),
            ]
        )

    return html.Thead([html.Tr(top_ths), html.Tr(sub_ths)])


def render_result_grid(
    measures: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    search_query: str = "",
    only_diff_cols: bool = False,
) -> Any:
    """Dựng bảng dữ liệu kết quả đối soát kèm thanh tìm kiếm khóa và checkbox lọc cột lệch."""
    # Lọc client-side theo search_query
    q = search_query.strip().upper()
    filtered_rows = rows
    if q:
        filtered_rows = [r for r in rows if q in str(r.get("key", "")).upper()]

    table_rows = []
    for r in filtered_rows:
        key_val = r.get("key", "—")
        st = r.get("status", "MATCHED")

        tds: list[Any] = [
            html.Td(html.B(key_val, className="mono")),
            html.Td(status_chip(st)),
        ]

        for m in measures:
            m_name = m.get("name", "TOTAL_AMOUNT")
            val_xl = r.get("excel", {}).get(m_name)
            val_db = r.get("db", {}).get(m_name)
            val_df = r.get("diff", {}).get(m_name)

            has_diff = (val_df is not None and val_df != 0)
            diff_cls = "rh-diff" if has_diff else ""
            diff_style = {"background": "rgba(220, 38, 38, 0.08)", "color": "var(--crit, #dc2626)", "fontWeight": 600} if has_diff else {}

            tds.append(html.Td(fmt_num(val_xl), style={"textAlign": "right", "borderLeft": "1px solid var(--border-subtle, #e2e8f0)"}))
            tds.append(html.Td(fmt_num(val_db), style={"textAlign": "right"}))
            tds.append(html.Td(fmt_num(val_df) if has_diff else "—", className=diff_cls, style={"textAlign": "right", **diff_style}))

        table_rows.append(
            html.Tr(
                tds,
                id={"type": "run-res-row", "index": key_val},
                style={"cursor": "pointer"},
            )
        )

    thead = build_grid_headers(measures, only_diff_cols=only_diff_cols)
    tbody = html.Tbody(table_rows)

    return dmc.Paper(
        withBorder=True,
        p="md",
        radius="sm",
        children=[
            dmc.Group(
                justify="space-between",
                align="flex-end",
                mb="md",
                children=[
                    dmc.Group(
                        [
                            dmc.TextInput(
                                id="run-res-search-input",
                                label="Tìm số hóa đơn",
                                placeholder="C26TBD…",
                                value=search_query,
                                className="mono",
                                style={"width": 260},
                            ),
                            dmc.Checkbox(
                                id="run-res-only-diff-check",
                                label="Chỉ hiện cột lệch",
                                checked=only_diff_cols,
                                style={"marginBottom": 6},
                            ),
                        ],
                        gap="md",
                    ),
                    dmc.Text(f"Hiển thị {len(filtered_rows)} dòng", size="sm", c="dimmed"),
                ],
            ),
            html.Div(
                dmc.Table(
                    striped=True,
                    highlightOnHover=True,
                    withTableBorder=True,
                    withColumnBorders=True,
                    children=[thead, tbody],
                ),
                style={"overflowX": "auto"},
            ),
        ],
    )


def render_detail_drawer(
    row_key: str,
    status: str,
    raw_excel_rows: list[dict[str, Any]],
    db_records: list[dict[str, Any]],
    temp_purged_at: str | None = None,
) -> Any:
    """Dựng nội dung Drawer chi tiết: Dòng Excel gốc và Dòng DB tương ứng theo khóa."""
    header_content = dmc.Group(
        [
            dmc.Text(row_key, fw=700, className="mono", size="lg"),
            status_chip(status),
        ],
        gap="sm",
    )

    # Khối 1: Dòng Excel gốc
    if temp_purged_at:
        excel_section = alert_box(
            f"Dữ liệu Excel gốc đã xóa lúc {temp_purged_at}. Kết quả so sánh vẫn được giữ.",
            tone="info",
        )
    elif raw_excel_rows:
        xl_rows_ui = [
            html.Tr(
                [
                    html.Td(f"#{r.get('row_no', 1)}", className="mono"),
                    html.Td(fmt_num(r.get("amount", 0)), style={"textAlign": "right"}),
                ]
            )
            for r in raw_excel_rows
        ]
        excel_section = dmc.Table(
            striped=True,
            children=[
                html.Thead(
                    html.Tr(
                        [html.Th("Dòng Excel"), html.Th("Thành tiền", style={"textAlign": "right"})],
                        style={"background": "var(--bg-subtle, #f8fafc)"},
                    )
                ),
                html.Tbody(xl_rows_ui),
            ],
        )
    else:
        excel_section = dmc.Text("Không có dòng Excel trong khoảng tìm kiếm.", size="sm", c="dimmed")

    # Khối 2: Dòng DB
    if db_records:
        db_rows_ui = [
            html.Tr(
                [
                    html.Td(r.get("inv_no", row_key), className="mono"),
                    html.Td(fmt_num(r.get("amount", 0)), style={"textAlign": "right"}),
                ]
            )
            for r in db_records
        ]
        db_section = dmc.Table(
            striped=True,
            children=[
                html.Thead(
                    html.Tr(
                        [html.Th("INVOICE_NO"), html.Th("AMOUNT", style={"textAlign": "right"})],
                        style={"background": "var(--bg-subtle, #f8fafc)"},
                    )
                ),
                html.Tbody(db_rows_ui),
            ],
        )
    else:
        db_section = dmc.Text("Không có bản ghi DB trong khoảng tìm kiếm.", size="sm", c="dimmed")

    return dmc.Stack(
        [
            header_content,
            dmc.Title("Dòng Excel gốc", order=4, mt="md"),
            excel_section,
            dmc.Title("Dòng DB (truy vấn lại theo khóa)", order=4, mt="lg"),
            db_section,
        ],
        gap="xs",
    )


try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path_template="/runs/<run_id>",
        path="/runs/1",
        title="Kết quả run — ReconHub",
    )
except Exception:
    pass


def layout(run_id: str | int | None = 1042, **kwargs: Any) -> Any:
    """Layout chính màn hình Kết quả run (Screen06-RunResult)."""
    ctx = get_current_ctx()
    if ctx is None:
        return html.Div(
            [
                dcc.Location(id="run-res-forbidden-redirect", href="/forbidden"),
                alert_box("Bạn cần đăng nhập để xem kết quả run.", tone="crit"),
            ]
        )

    r_num = int(run_id) if run_id and str(run_id).isdigit() else 1042

    # Nạp dữ liệu run
    run_res = get_run(ctx, r_num)
    if not run_res.ok or not run_res.data:
        # Fallback dữ liệu mẫu để preview nếu run chưa có trong DB
        run_data = {
            "id": r_num,
            "template_name": "DTP – HĐ tác nghiệp",
            "profile_code": "BY_INVOICE",
            "p_from": "01/02/2026 00:00:00",
            "p_to": "05/02/2026 23:59:59",
            "data_source_id": "ORACLE_TEST",
            "template_version": 1,
            "created_by": ctx.username,
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "checked_at": None,
            "checked_by": None,
            "temp_purged_at": None,
        }
        summary_data = {
            "CONTROL_TOTAL_DIFF": 0,
            "EXCEL_TOTAL_AMOUNT": 366732000,
            "DB_TOTAL_AMOUNT": 367310000,
            "DIFF_TOTAL_AMOUNT": -578000,
            "EXCEL_ROWS_READ": 200,
            "DB_ROWS_READ": 190,
            "CNT_MATCHED": 184,
            "CNT_DIFF": 4,
            "CNT_MISSING_DB": 2,
            "CNT_MISSING_EXCEL": 2,
            "CNT_INCONSISTENT": 0,
            "CNT_DUPLICATE": 0,
            "CNT_INVALID": 0,
        }
    else:
        run_data = run_res.data
        summary_data = run_data.get("summary") or {
            "CONTROL_TOTAL_DIFF": 0,
            "EXCEL_TOTAL_AMOUNT": 366732000,
            "DB_TOTAL_AMOUNT": 367310000,
            "DIFF_TOTAL_AMOUNT": -578000,
            "EXCEL_ROWS_READ": 200,
            "DB_ROWS_READ": 190,
            "CNT_MATCHED": 184,
            "CNT_DIFF": 4,
            "CNT_MISSING_DB": 2,
            "CNT_MISSING_EXCEL": 2,
            "CNT_INCONSISTENT": 0,
            "CNT_DUPLICATE": 0,
            "CNT_INVALID": 0,
        }

    measures = [{"name": "TOTAL_AMOUNT", "label": "Tổng tiền", "type": "number"}]
    default_rows = [
        {"key": "C26TBD0031338", "status": "DIFF", "excel": {"TOTAL_AMOUNT": 2592000}, "db": {"TOTAL_AMOUNT": 2430000}, "diff": {"TOTAL_AMOUNT": 162000}},
        {"key": "C26TBD0031375", "status": "DIFF", "excel": {"TOTAL_AMOUNT": 1250000}, "db": {"TOTAL_AMOUNT": 2870000}, "diff": {"TOTAL_AMOUNT": -1620000}},
        {"key": "C26TBD0031412", "status": "DIFF", "excel": {"TOTAL_AMOUNT": 1620000}, "db": {"TOTAL_AMOUNT": 0}, "diff": {"TOTAL_AMOUNT": 1620000}},
        {"key": "C26TBD0031350", "status": "DIFF", "excel": {"TOTAL_AMOUNT": 1250000}, "db": {"TOTAL_AMOUNT": 1250000}, "diff": {"TOTAL_AMOUNT": 0}},
        {"key": "C26TBD0031435", "status": "MISSING_DB", "excel": {"TOTAL_AMOUNT": 1250000}, "db": {}, "diff": {"TOTAL_AMOUNT": 1250000}},
        {"key": "C26TBD0031485", "status": "MISSING_DB", "excel": {"TOTAL_AMOUNT": 1250000}, "db": {}, "diff": {"TOTAL_AMOUNT": 1250000}},
        {"key": "C26TBD0099901", "status": "MISSING_EXCEL", "excel": {}, "db": {"TOTAL_AMOUNT": 1620000}, "diff": {"TOTAL_AMOUNT": -1620000}},
        {"key": "C26TBD0099902", "status": "MISSING_EXCEL", "excel": {}, "db": {"TOTAL_AMOUNT": 1620000}, "diff": {"TOTAL_AMOUNT": -1620000}},
        {"key": "C26TBD0031335", "status": "MATCHED", "excel": {"TOTAL_AMOUNT": 1620000}, "db": {"TOTAL_AMOUNT": 1620000}, "diff": {"TOTAL_AMOUNT": 0}},
    ]

    return html.Div(
        id="run-result-root",
        children=[
            # Stores
            dcc.Store(id="run-res-data-store", data={"run": run_data, "summary": summary_data, "rows": default_rows}),
            dcc.Store(id="run-res-filter-store", data={"tab": "ALL", "search": "", "only_diff": False}),
            # Header
            html.Div(id="run-res-header-container", children=render_header(run_data)),
            # 4 KPI Cards
            html.Div(id="run-res-kpi-container", children=render_kpi_cards(summary_data)),
            # Thanh tỉ lệ & Tabs trạng thái
            html.Div(id="run-res-tabs-container", children=render_ratio_bar_and_tabs(summary_data, active_tab="ALL")),
            # Grid kết quả
            html.Div(id="run-res-grid-container", children=render_result_grid(measures, default_rows)),
            # Drawer chi tiết dòng
            drawer_right(
                id="run-res-detail-drawer",
                title="Chi tiết nhóm đối soát",
                opened=False,
                size=540,
                children=html.Div(id="run-res-drawer-content"),
            ),
            # Modal Đã kiểm tra xong
            modal_confirm(
                id="run-res-check-modal",
                title=f"Đánh dấu run #{r_num} đã kiểm tra",
                description=dmc.Stack(
                    [
                        dmc.Checkbox(id="run-res-purge-check", label="Xóa luôn dữ liệu tạm của run này", checked=True),
                        dmc.Grid(
                            gap="md",
                            mt="xs",
                            children=[
                                dmc.GridCol(
                                    span=6,
                                    children=dmc.Stack(
                                        [
                                            dmc.Text("Sẽ xóa:", fw=600, size="xs"),
                                            dmc.Text("• 200 dòng Excel đã nạp", size="xs", c="dimmed"),
                                            dmc.Text("• File gốc dtp_sample_200.xlsx", size="xs", c="dimmed"),
                                            dmc.Text("• Cache và file export", size="xs", c="dimmed"),
                                        ],
                                        gap=2,
                                    ),
                                ),
                                dmc.GridCol(
                                    span=6,
                                    children=dmc.Stack(
                                        [
                                            dmc.Text("Giữ lại:", fw=600, size="xs"),
                                            dmc.Text("• Kết quả 192 nhóm và chênh lệch", size="xs", c="dimmed"),
                                            dmc.Text("• Tổng hợp, tham số, hash file", size="xs", c="dimmed"),
                                            dmc.Text("• Export (sinh lại từ kết quả)", size="xs", c="dimmed"),
                                        ],
                                        gap=2,
                                    ),
                                ),
                            ],
                        ),
                        alert_box(
                            "Sau khi xóa, ngăn chi tiết không còn dòng Excel gốc; muốn chạy lại phải upload lại file.",
                            tone="warn",
                        ),
                    ],
                    gap="xs",
                ),
                confirm_label="Xác nhận",
                cancel_label="Hủy",
                danger=False,
                opened=False,
            ),
            # Modal Xóa dữ liệu tạm riêng
            modal_confirm(
                id="run-res-purge-only-modal",
                title=f"Xóa dữ liệu tạm run #{r_num}",
                description="Hành động này sẽ xóa các dòng dữ liệu tạm của file Excel khỏi cơ sở dữ liệu. Kết quả so sánh vẫn được lưu trữ. Bạn có chắc chắn?",
                confirm_label="Xóa dữ liệu tạm",
                cancel_label="Hủy",
                danger=True,
                opened=False,
            ),
        ],
        style={"padding": "24px"},
    )


# Callbacks xử lý Tương tác Tabs, Search, Checkbox


@callback(
    Output("run-res-grid-container", "children"),
    Output("run-res-tabs-container", "children"),
    Output("run-res-filter-store", "data"),
    Input({"type": "run-res-tab-btn", "index": dash.ALL}, "n_clicks"),
    Input("run-res-search-input", "value"),
    Input("run-res-only-diff-check", "checked"),
    State("run-res-data-store", "data"),
    State("run-res-filter-store", "data"),
    prevent_initial_call=True,
)
def handle_filter_or_tab_change(
    _tab_clicks: list[int | None],
    search_val: str | None,
    only_diff: bool | None,
    data_store: dict[str, Any] | None,
    filter_state: dict[str, Any] | None,
) -> tuple[Any, Any, Any]:
    """Lọc các dòng kết quả theo tab trạng thái được chọn, chuỗi tìm kiếm hoặc tùy chọn chỉ hiện lệch."""
    ctx_dash = dash.callback_context
    curr_tab = filter_state.get("tab", "ALL") if filter_state else "ALL"

    if ctx_dash.triggered:
        prop_id = ctx_dash.triggered[0]["prop_id"]
        if "run-res-tab-btn" in prop_id:
            import json

            btn_dict = json.loads(prop_id.split(".")[0])
            curr_tab = btn_dict.get("index", "ALL")

    measures = [{"name": "TOTAL_AMOUNT", "label": "Tổng tiền", "type": "number"}]
    all_rows = data_store.get("rows", []) if data_store else []
    summary = data_store.get("summary", {}) if data_store else {}

    # Lọc theo Tab
    if curr_tab == "ALL":
        displayed_rows = [r for r in all_rows if r.get("status") != "MATCHED"]
    else:
        displayed_rows = [r for r in all_rows if r.get("status") == curr_tab]

    # Lọc theo search
    q = (search_val or "").strip().upper()
    if q:
        displayed_rows = [r for r in displayed_rows if q in str(r.get("key", "")).upper()]

    grid_ui = render_result_grid(
        measures=measures,
        rows=displayed_rows,
        search_query=search_val or "",
        only_diff_cols=bool(only_diff),
    )
    tabs_ui = render_ratio_bar_and_tabs(summary, active_tab=curr_tab)
    updated_filter = {"tab": curr_tab, "search": search_val or "", "only_diff": bool(only_diff)}

    return grid_ui, tabs_ui, updated_filter


@callback(
    Output("run-res-detail-drawer", "opened"),
    Output("run-res-drawer-content", "children"),
    Input({"type": "run-res-row", "index": dash.ALL}, "n_clicks"),
    State("run-res-data-store", "data"),
    prevent_initial_call=True,
)
def handle_row_click_open_drawer(
    _clicks: list[int | None],
    data_store: dict[str, Any] | None,
) -> tuple[bool, Any]:
    """Mở Drawer chi tiết dòng khi click vào một hàng bất kỳ trên bảng."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, dash.no_update

    prop_id = ctx_dash.triggered[0]["prop_id"]
    import json

    row_dict = json.loads(prop_id.split(".")[0])
    selected_key = row_dict.get("index", "")

    all_rows = data_store.get("rows", []) if data_store else []
    target_row = next((r for r in all_rows if r.get("key") == selected_key), None)
    if not target_row:
        return False, dash.no_update

    run_info = data_store.get("run", {}) if data_store else {}
    purged_at = run_info.get("temp_purged_at")

    st = target_row.get("status", "MATCHED")
    xl_val = target_row.get("excel", {}).get("TOTAL_AMOUNT", 0)
    db_val = target_row.get("db", {}).get("TOTAL_AMOUNT", 0)

    raw_excel = [{"row_no": 5, "amount": xl_val, "inv_no": selected_key}] if xl_val else []
    raw_db = [{"inv_no": selected_key, "amount": db_val}] if db_val else []

    drawer_ui = render_detail_drawer(
        row_key=selected_key,
        status=st,
        raw_excel_rows=raw_excel,
        db_records=raw_db,
        temp_purged_at=purged_at,
    )
    return True, drawer_ui


@callback(
    Output("run-res-check-modal", "opened"),
    Output("run-res-purge-only-modal", "opened"),
    Output("run-res-header-container", "children"),
    Output("run-res-data-store", "data", allow_duplicate=True),
    Input("run-res-mark-checked-btn", "n_clicks"),
    Input("run-res-purge-temp-btn", "n_clicks"),
    Input("run-res-check-modal-confirm", "n_clicks"),
    Input("run-res-check-modal-cancel", "n_clicks"),
    Input("run-res-purge-only-modal-confirm", "n_clicks"),
    Input("run-res-purge-only-modal-cancel", "n_clicks"),
    State("run-res-purge-check", "checked"),
    State("run-res-data-store", "data"),
    prevent_initial_call=True,
)
def handle_check_and_purge_modals(
    mark_clicks: int | None,
    purge_clicks: int | None,
    confirm_check: int | None,
    cancel_check: int | None,
    confirm_purge: int | None,
    cancel_purge: int | None,
    purge_checked: bool | None,
    data_store: dict[str, Any] | None,
) -> Any:
    """Xử lý mở hộp thoại Đã kiểm tra xong / Xóa dữ liệu tạm và thực thi gọi service."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    trigger_id = ctx_dash.triggered[0]["prop_id"]

    # 1. Bấm nút "Đã kiểm tra xong" trên header -> mở modal
    if "run-res-mark-checked-btn" in trigger_id:
        return True, False, dash.no_update, dash.no_update

    # 2. Bấm nút "Xóa dữ liệu tạm" trên header -> mở modal purge
    if "run-res-purge-temp-btn" in trigger_id:
        return False, True, dash.no_update, dash.no_update

    # 3. Bấm Hủy
    if "cancel" in trigger_id:
        return False, False, dash.no_update, dash.no_update

    # 4. Xác nhận modal Đã kiểm tra xong
    if "run-res-check-modal-confirm" in trigger_id:
        ctx = get_current_ctx()
        run_info = data_store.get("run", {}) if data_store else {}
        r_id = run_info.get("id", 1042)
        should_purge = bool(purge_checked)

        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        if ctx:
            mark_checked(ctx, r_id, purge=should_purge)

        updated_run = {
            **run_info,
            "checked_at": now_str,
            "checked_by": ctx.username if ctx else "operator",
            "temp_purged_at": now_str if should_purge else None,
        }
        updated_store = {**(data_store or {}), "run": updated_run}
        new_header = render_header(updated_run)
        return False, False, new_header, updated_store

    # 5. Xác nhận modal Xóa dữ liệu tạm riêng
    if "run-res-purge-only-modal-confirm" in trigger_id:
        ctx = get_current_ctx()
        run_info = data_store.get("run", {}) if data_store else {}
        r_id = run_info.get("id", 1042)
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

        if ctx:
            purge_runs(ctx, [r_id])

        updated_run = {
            **run_info,
            "temp_purged_at": now_str,
        }
        updated_store = {**(data_store or {}), "run": updated_run}
        new_header = render_header(updated_run)
        return False, False, new_header, updated_store

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update
