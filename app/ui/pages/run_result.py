from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from app.core.session import get_current_ctx
from app.schemas.run import RunRowsFilter
from app.services.dashboard import compare_runs, get_previous_run
from app.services.issue import list_reasons, upsert_issue_for_row
from app.services.run_service import export_run, get_row_detail, get_run, get_run_rows
from app.services.temp_data import mark_checked, purge_runs
from app.services.template import get_template
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_danger, button_primary, button_subtle
from app.ui.components.drawer import drawer_right
from app.ui.components.empty_state import empty_state
from app.ui.components.kpi_card import kpi_card
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.status_chip import status_chip

STATUS_INFO: dict[str, tuple[str, str, str]] = {
    "MATCHED": ("teal", "Khớp", "lucide:check-circle-2"),
    "MISMATCH": ("red", "Lệch giá trị", "lucide:equal-not"),
    "MISSING_IN_DB": ("yellow", "Thiếu trong DB", "lucide:database-zap"),
    "MISSING_IN_EXCEL": ("violet", "Thiếu trong Excel", "lucide:file-x-2"),
    "INCONSISTENT": ("gray", "Không nhất quán", "lucide:shuffle"),
    "DUPLICATE": ("gray", "Trùng khóa", "lucide:copy"),
    "INVALID": ("red", "Không hợp lệ", "lucide:alert-triangle"),
}

ISSUE_STATUS_LABELS: dict[str, str] = {
    "OPEN": "Chưa đối soát",
    "IN_PROGRESS": "Đang kiểm tra",
    "ACCEPTED": "Xác nhận đối soát",
    "RESOLVED": "Đã xử lý xong",
}


def fmt_num(val: Any) -> str:
    """Định dạng số theo chuẩn tiếng Việt có phân cách hàng nghìn."""
    if val is None or val == "":
        return "—"
    try:
        num = float(val)
        if num == 0:
            return "0"
        if num.is_integer():
            return f"{int(num):,}".replace(",", ".")
        return f"{num:,.2f}".replace(",", ".").rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return str(val)


def _strip_measure_prefix(key: str) -> str:
    """Bỏ tiền tố x__/d__/diff__ của JSON kết quả để lấy tên measure thật."""
    for prefix in ("x__", "d__", "diff__"):
        if key.startswith(prefix):
            return key[len(prefix) :]
    return key


def _pick_value(data: dict[str, Any], *keys: str) -> Any:
    """Lấy giá trị theo khóa có mặt đầu tiên, không dùng `or`.

    Giá trị 0 là số thật, không được rơi sang khóa dự phòng rồi thành None ("—").
    """
    for key in keys:
        if key in data:
            return data[key]
    return None


def _profile_main_measure(ctx: Any, run_info: dict[str, Any] | None) -> dict[str, Any] | None:
    """Lấy measure chính + trường nguồn + group_by của profile đã chạy từ config.

    Trả None khi không lấy được config; các nơi gọi sẽ tự dự phòng từ dữ
    liệu dòng đang hiển thị thay vì hardcode tên measure của mẫu DTP.
    """
    run_info = run_info or {}
    profile_code = str(run_info.get("profile_code") or "")
    template_id = run_info.get("template_id")
    template_version = run_info.get("template_version")
    if ctx is None or not template_id or not profile_code:
        return None
    try:
        tmpl_res = get_template(ctx, template_id=template_id, version=template_version)
        if not tmpl_res.ok or not tmpl_res.data:
            return None
        config = tmpl_res.data.get("config") or {}
        for prof in config.get("profiles") or []:
            if str(prof.get("code") or "") != profile_code:
                continue
            measures = prof.get("measures") or []
            if not measures:
                return None
            main_name = prof.get("main_measure")
            chosen = next((m for m in measures if m.get("name") == main_name), measures[0])
            return {
                "name": chosen.get("name"),
                "label": chosen.get("label") or chosen.get("name"),
                "field": chosen.get("field"),
                "group_by": list(prof.get("group_by") or []),
            }
    except Exception:
        return None
    return None


def _resolve_grid_measures(
    ctx: Any, run_info: dict[str, Any] | None, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Lấy measure chính để hiển thị ở lưới kết quả.

    Lưới trước đây hardcode TOTAL_AMOUNT (measure chính của mẫu DTP), nên
    template nào đặt tên measure khác (ví dụ BILL_VTOS dùng TOTAL_TONG_TIEN)
    sẽ tra sai khóa trong EXCEL_JSON/DB_JSON/DIFF_JSON và hiện toàn "—",
    trong khi drawer chi tiết tự suy khóa từ JSON nên vẫn hiện đủ số.
    Thứ tự: (1) measure chính trong config của profile đã chạy, (2) measure
    đầu tiên suy từ khóa JSON của các dòng đang hiển thị, (3) TOTAL_AMOUNT
    để giữ hành vi cũ khi không suy ra được gì.
    """
    fallback = [{"name": "TOTAL_AMOUNT", "label": "Tổng tiền", "type": "number"}]
    main = _profile_main_measure(ctx, run_info)
    if main:
        return [{"name": main["name"], "label": main["label"], "type": "number"}]
    for row in rows or []:
        for key in ("excel", "db", "diff"):
            data = row.get(key) or {}
            if isinstance(data, dict) and data:
                first_name = _strip_measure_prefix(next(iter(data.keys())))
                return [{"name": first_name, "label": first_name, "type": "number"}]
    return fallback


def fmt_size(bytes_val: int | None) -> str:
    """Định dạng dung lượng file theo chuẩn KB/MB."""
    if not bytes_val or bytes_val <= 0:
        return ""
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:,.0f} KB".replace(",", ".")
    return f"{bytes_val / (1024 * 1024):,.1f} MB".replace(",", ".")


def render_header(run_info: dict[str, Any]) -> Any:
    """Dựng khối Header màn hình kết quả run kèm metadata, chips và nút hành động."""
    r_id = run_info.get("id", 0)
    tmpl_name = run_info.get("template_name") or run_info.get("template_code", "Template đối soát")
    prof = run_info.get("profile_code", "Mặc định")
    p_from = run_info.get("p_from", "")
    p_to = run_info.get("p_to", "")
    ds_name = run_info.get("data_source_id", "Oracle")
    ver = run_info.get("template_version", 1)
    user = run_info.get("created_by", "operator")
    created_at = run_info.get("created_at", "")
    file_size = run_info.get("file_size")

    params_raw = run_info.get("params_json") or {}
    params_dict = json.loads(params_raw) if isinstance(params_raw, str) else params_raw
    p_org = params_dict.get("p_org") if isinstance(params_dict, dict) else None
    org_str = f" · {p_org}" if p_org else ""

    checked_at = run_info.get("checked_at")
    checked_by = run_info.get("checked_by")
    purged_at = run_info.get("temp_purged_at")

    if checked_at:
        chk_chip = dmc.Badge(
            f"Đã kiểm tra · {checked_by or user} · {checked_at}",
            color="teal",
            variant="light",
            size="xs",
            leftSection=DashIconify(icon="lucide:check", width=14),
        )
    else:
        chk_chip = dmc.Badge(
            "Chưa kiểm tra",
            color="gray",
            variant="outline",
            size="xs",
        )

    size_str = f" · {fmt_size(file_size)}" if file_size else ""
    if purged_at:
        temp_chip = dmc.Badge(
            f"Dữ liệu tạm đã xóa lúc {purged_at}",
            color="gray",
            variant="light",
            size="xs",
        )
    else:
        temp_chip = dmc.Badge(
            f"Dữ liệu tạm còn{size_str}",
            color="yellow",
            variant="light",
            size="xs",
            leftSection=DashIconify(icon="lucide:info", width=14),
        )

    action_btns = []
    # Cả hai nút luôn tồn tại trong layout để Dash callback không bị thiếu Input ID
    action_btns.append(
        button_primary(
            "Đã kiểm tra xong",
            id="run-res-mark-checked-btn",
            icon="lucide:check",
            size="xs",
            style={} if not checked_at else {"display": "none"},
        )
    )
    action_btns.append(
        button_danger(
            "Xóa dữ liệu tạm",
            id="run-res-purge-temp-btn",
            icon="lucide:trash-2",
            size="xs",
            style={} if (checked_at and not purged_at) else {"display": "none"},
        )
    )

    action_btns.append(button_subtle("So với run trước", id="run-res-compare-btn", icon="lucide:git-compare", size="xs"))
    action_btns.append(dcc.Link(button_subtle("Chạy lại", icon="lucide:refresh-cw", size="xs"), href="/runs/new"))
    action_btns.append(
        button_primary(
            "Export Excel",
            id="run-res-export-btn",
            icon="lucide:download",
            size="xs",
        )
    )

    sub_title = f"{prof} · {p_from} → {p_to}{org_str} · Nguồn: #{ds_name} · v{ver} · {user} lúc {created_at}"

    return dmc.Group(
        justify="space-between",
        align="flex-start",
        mb="md",
        children=[
            html.Div(
                [
                    dmc.Title(f"Run #{r_id} · {tmpl_name}", order=2, fw=700),
                    dmc.Text(sub_title, size="xs", c="dimmed", mt=4),
                ]
            ),
            dmc.Stack(
                [
                    dmc.Group(action_btns, gap="xs", justify="flex-end"),
                    dmc.Group([chk_chip, temp_chip], gap="xs", justify="flex-end"),
                ],
                gap="xs",
                align="flex-end",
            ),
        ],
    )


def render_kpi_cards(summary: dict[str, Any], main_measure_name: str | None = None) -> Any:
    """Dựng 4 KPI Cards: Control total file, Tổng tiền Excel, Tổng tiền DB, Chênh lệch từ số liệu thật.

    Ưu tiên đúng measure chính của profile đã chạy; trước đây lấy TOTAL_AMOUNT
    rồi mới rơi sang measure đầu tiên trong dict, nên profile có measure đầu
    không phải tiền (ví dụ số lượng) sẽ hiện KPI sai chỉ tiêu.
    """
    measure_totals = summary.get("MEASURE_TOTALS_JSON") or {}
    if isinstance(measure_totals, str):
        try:
            measure_totals = json.loads(measure_totals)
        except Exception:
            measure_totals = {}

    if main_measure_name and measure_totals.get(main_measure_name):
        m_data = measure_totals[main_measure_name]
    else:
        m_data = measure_totals.get("TOTAL_AMOUNT") or (next(iter(measure_totals.values())) if measure_totals else {})

    xl_val = m_data.get("excel") if m_data.get("excel") is not None else summary.get("EXCEL_TOTAL_AMOUNT")
    db_val = m_data.get("db") if m_data.get("db") is not None else summary.get("DB_TOTAL_AMOUNT")
    diff_val = m_data.get("diff") if m_data.get("diff") is not None else summary.get("DIFF_TOTAL_AMOUNT")

    xl_total = fmt_num(xl_val)
    db_total = fmt_num(db_val)

    diff_num = float(diff_val) if diff_val is not None else 0.0
    if diff_num < 0:
        diff_str = f"−{fmt_num(abs(diff_num))}"
    else:
        diff_str = fmt_num(diff_num)
    diff_tone = "crit" if diff_num != 0 else "ok"

    xl_rows = summary.get("EXCEL_ROWS_READ", 0) or 0
    xl_out = summary.get("EXCEL_ROWS_OUT_OF_RANGE", 0) or 0
    db_rows = summary.get("DB_ROWS", summary.get("DB_ROWS_READ", 0)) or 0

    c_mismatch = summary.get("CNT_MISMATCH", summary.get("CNT_DIFF", 0)) or 0
    c_mis_db = summary.get("CNT_MISSING_IN_DB", summary.get("CNT_MISSING_DB", 0)) or 0
    c_mis_xl = summary.get("CNT_MISSING_IN_EXCEL", summary.get("CNT_MISSING_EXCEL", 0)) or 0
    c_incon = summary.get("CNT_INCONSISTENT", 0) or 0
    c_dup = summary.get("CNT_DUPLICATE", 0) or 0
    c_inv = summary.get("EXCEL_ROWS_INVALID", summary.get("CNT_INVALID", 0)) or 0
    total_issues = c_mismatch + c_mis_db + c_mis_xl + c_incon + c_dup + c_inv

    ct_file = summary.get("CONTROL_TOTAL_FILE", summary.get("EXCEL_TOTAL_AMOUNT"))
    ct_ok = summary.get("CONTROL_TOTAL_OK", "Y" if summary.get("CONTROL_TOTAL_DIFF", 0) == 0 else "N")

    if ct_file is not None:
        ct_val = fmt_num(ct_file)
        ct_tone = "ok" if ct_ok == "Y" else "warn"
        ct_meta = 'Tổng dòng chi tiết khớp với dòng "Tổng tiền"' if ct_ok == "Y" else "Lệch so với tổng dòng chi tiết"
        ct_icon = "lucide:check-circle-2" if ct_ok == "Y" else "lucide:alert-triangle"
    else:
        ct_val = "Không áp dụng"
        ct_tone = "primary"
        ct_meta = "File không cấu hình dòng control total"
        ct_icon = "lucide:info"

    return dmc.SimpleGrid(
        cols={"base": 1, "sm": 2, "md": 4},
        spacing="md",
        mb="lg",
        children=[
            kpi_card(
                label="Control total file",
                value=ct_val,
                tone=ct_tone,
                meta=ct_meta,
                icon=ct_icon,
            ),
            kpi_card(
                label="Tổng tiền Excel (trong khoảng)",
                value=xl_total,
                tone="primary",
                meta=f"{xl_rows:,} dòng · {xl_out:,} dòng ngoài khoảng".replace(",", "."),
                icon="lucide:file-spreadsheet",
            ),
            kpi_card(
                label="Tổng tiền DB",
                value=db_total,
                tone="primary",
                meta=f"{db_rows:,} bản ghi".replace(",", "."),
                icon="lucide:database",
            ),
            kpi_card(
                label="Chênh lệch",
                value=diff_str,
                tone=diff_tone,
                meta=f"{total_issues:,} nhóm không khớp".replace(",", "."),
                icon="lucide:scale",
            ),
        ],
    )


def render_ratio_bar_and_tabs(summary: dict[str, Any], active_tab: str = "ALL") -> Any:
    """Dựng thanh tỉ lệ phần trăm và bộ Tab lọc 7 trạng thái kết quả từ cơ sở dữ liệu."""
    c_matched = summary.get("CNT_MATCHED", 0) or 0
    c_mismatch = summary.get("CNT_MISMATCH", summary.get("CNT_DIFF", 0)) or 0
    c_mis_db = summary.get("CNT_MISSING_IN_DB", summary.get("CNT_MISSING_DB", 0)) or 0
    c_mis_xl = summary.get("CNT_MISSING_IN_EXCEL", summary.get("CNT_MISSING_EXCEL", 0)) or 0
    c_incon = summary.get("CNT_INCONSISTENT", 0) or 0
    c_dup = summary.get("CNT_DUPLICATE", 0) or 0
    c_inv = summary.get("EXCEL_ROWS_INVALID", summary.get("CNT_INVALID", 0)) or 0

    total_issues = c_mismatch + c_mis_db + c_mis_xl + c_incon + c_dup + c_inv
    total_all = c_matched + total_issues or 1

    pct_matched = (c_matched / total_all) * 100
    pct_mismatch = (c_mismatch / total_all) * 100
    pct_mis_db = (c_mis_db / total_all) * 100
    pct_mis_xl = (c_mis_xl / total_all) * 100

    ratio_bar = html.Div(
        style={
            "height": 10,
            "borderRadius": 5,
            "display": "flex",
            "overflow": "hidden",
            "marginBottom": 16,
            "background": "var(--surface-2, rgba(255,255,255,0.06))",
        },
        children=[
            html.Div(style={"width": f"{pct_matched:.1f}%", "background": "var(--ok, #16a34a)"}),
            html.Div(style={"width": f"{pct_mismatch:.1f}%", "background": "var(--crit, #dc2626)"}),
            html.Div(style={"width": f"{pct_mis_db:.1f}%", "background": "var(--warn, #f59e0b)"}),
            html.Div(style={"width": f"{pct_mis_xl:.1f}%", "background": "var(--purple, #a855f7)"}),
        ],
    )

    tab_defs = [
        ("ALL", "Tất cả chênh lệch", total_issues, "red"),
        ("MATCHED", "Khớp", c_matched, "teal"),
        ("MISMATCH", "Lệch giá trị", c_mismatch, "red"),
        ("MISSING_IN_DB", "Thiếu trong DB", c_mis_db, "yellow"),
        ("MISSING_IN_EXCEL", "Thiếu trong Excel", c_mis_xl, "violet"),
        ("INCONSISTENT", "Không nhất quán", c_incon, "gray"),
        ("DUPLICATE", "Trùng khóa", c_dup, "gray"),
        ("INVALID", "Không hợp lệ", c_inv, "red"),
    ]

    tab_buttons = []
    for code, label, count, color in tab_defs:
        is_active = code == active_tab
        tab_buttons.append(
            dmc.Button(
                [
                    html.Span(label, style={"marginRight": 6}),
                    dmc.Badge(
                        f"{count:,}".replace(",", "."),
                        color=color,
                        variant="filled" if is_active else "light",
                        size="xs",
                    ),
                ],
                id={"type": "run-res-tab-btn", "index": code},
                variant="filled" if is_active else "subtle",
                color="primary" if is_active else "gray",
                size="xs",
            )
        )

    return html.Div(
        [
            ratio_bar,
            dmc.Group(tab_buttons, gap="xs", mb="md", style={"flexWrap": "wrap"}),
        ]
    )


def build_grid_headers(measures: list[dict[str, Any]], only_diff_cols: bool = False) -> dmc.TableThead:
    """Sinh 2 tầng header chuẩn DMC: Tầng 1 gồm Key, Trạng thái, Trạng thái đối soát, và Colspan từng Measure; Tầng 2 gồm Excel, DB, Chênh."""
    top_ths = [
        dmc.TableTh(
            "Số hóa đơn / Khóa",
            tableProps={"rowSpan": 2},
            style={"verticalAlign": "middle", "minWidth": "220px", "whiteSpace": "nowrap", "textAlign": "center"},
        ),
        dmc.TableTh(
            "Trạng thái",
            tableProps={"rowSpan": 2},
            style={"verticalAlign": "middle", "minWidth": "120px", "whiteSpace": "nowrap", "textAlign": "center"},
        ),
        dmc.TableTh(
            "Đối soát & Xử lý",
            tableProps={"rowSpan": 2},
            style={"verticalAlign": "middle", "minWidth": "160px", "whiteSpace": "nowrap", "textAlign": "center"},
        ),
    ]
    sub_ths = []

    for m in measures:
        lbl = m.get("label", m.get("name", "Measure"))
        top_ths.append(
            dmc.TableTh(
                lbl,
                tableProps={"colSpan": 3},
                style={
                    "textAlign": "center",
                    "whiteSpace": "nowrap",
                    "borderLeft": "1px solid var(--line, rgba(255,255,255,0.1))",
                },
            )
        )
        sub_ths.extend(
            [
                dmc.TableTh(
                    "Excel",
                    style={
                        "minWidth": "110px",
                        "textAlign": "right",
                        "whiteSpace": "nowrap",
                        "borderLeft": "1px solid var(--line, rgba(255,255,255,0.1))",
                    },
                ),
                dmc.TableTh(
                    "DB",
                    style={"minWidth": "110px", "textAlign": "right", "whiteSpace": "nowrap"},
                ),
                dmc.TableTh(
                    "Chênh",
                    style={"minWidth": "110px", "textAlign": "right", "whiteSpace": "nowrap"},
                ),
            ]
        )

    return dmc.TableThead([dmc.TableTr(top_ths), dmc.TableTr(sub_ths)])


def render_result_grid(
    measures: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    total_count: int | None = None,
    current_page: int = 1,
    page_size: int = 50,
    search_query: str = "",
    only_diff_cols: bool = False,
    can_edit: bool = False,
    selected_row_nos: list[int] | None = None,
    **kwargs: Any,
) -> Any:
    """Dựng bảng dữ liệu kết quả đối soát kèm phân trang, tìm kiếm và trạng thái xử lý theo chuẩn giao diện History."""
    total_rows = total_count if total_count is not None else len(rows)

    table_rows = []
    for r in rows:
        key_val = str(r.get("key_text") or r.get("key") or "—")
        st = str(r.get("status", "MATCHED"))
        row_no = r.get("row_no", 1)

        iss_st = r.get("issue_status")
        iss_label = ISSUE_STATUS_LABELS.get(iss_st or "OPEN", "Chưa đối soát")
        iss_color = (
            "gray" if not iss_st or iss_st == "OPEN" else ("teal" if iss_st in ("ACCEPTED", "RESOLVED") else "blue")
        )
        issue_badge = dmc.Badge(
            iss_label,
            color=iss_color,
            variant="light",
            size="xs",
            leftSection=DashIconify(
                icon="lucide:check-circle" if iss_st in ("ACCEPTED", "RESOLVED") else "lucide:clock", width=12
            ),
        )

        tds: list[Any] = [
            dmc.TableTd(
                dmc.Text(key_val, fw=600, className="mono rh-code", size="xs"),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle", "cursor": "pointer"},
            ),
            dmc.TableTd(
                status_chip(st, size="xs"),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle", "cursor": "pointer"},
            ),
            dmc.TableTd(
                dmc.Tooltip(
                    label="Bấm để xem chi tiết & xử lý đối soát",
                    children=issue_badge,
                    position="top",
                    withArrow=True,
                ),
                style={"whiteSpace": "nowrap", "verticalAlign": "middle", "cursor": "pointer"},
            ),
        ]

        xl_dict = r.get("excel") or {}
        db_dict = r.get("db") or {}
        df_dict = r.get("diff") or {}

        for m in measures:
            m_name = m.get("name", "TOTAL_AMOUNT")
            val_xl = _pick_value(xl_dict, m_name, f"x__{m_name}")
            val_db = _pick_value(db_dict, m_name, f"d__{m_name}")
            val_df = _pick_value(df_dict, m_name, f"diff__{m_name}")

            diff_num = (
                float(val_df)
                if val_df is not None and str(val_df).replace("-", "").replace(".", "").isdigit()
                else None
            )
            has_diff = diff_num is not None and diff_num != 0
            diff_cls = "rh-diff" if has_diff else ""
            diff_style = (
                {"backgroundColor": "rgba(239, 68, 68, 0.12)", "color": "var(--crit, #f87171)", "fontWeight": 600}
                if has_diff
                else {}
            )

            tds.append(
                dmc.TableTd(
                    dmc.Text(fmt_num(val_xl), size="xs", style={"textAlign": "right"}),
                    style={
                        "textAlign": "right",
                        "whiteSpace": "nowrap",
                        "verticalAlign": "middle",
                        "borderLeft": "1px solid var(--line, rgba(255,255,255,0.1))",
                    },
                )
            )
            tds.append(
                dmc.TableTd(
                    dmc.Text(fmt_num(val_db), size="xs", style={"textAlign": "right"}),
                    style={"textAlign": "right", "whiteSpace": "nowrap", "verticalAlign": "middle"},
                )
            )
            tds.append(
                dmc.TableTd(
                    dmc.Text(
                        fmt_num(val_df) if val_df is not None and has_diff else ("—" if not has_diff else fmt_num(val_df)),
                        size="xs",
                        style={"textAlign": "right", **diff_style},
                    ),
                    className=diff_cls,
                    style={"textAlign": "right", "whiteSpace": "nowrap", "verticalAlign": "middle", **diff_style},
                )
            )

        table_rows.append(
            html.Tr(
                tds,
                id={"type": "run-res-row", "index": row_no},
                n_clicks=0,
                className="mantine-Table-tr run-res-row",
                style={"cursor": "pointer"},
            )
        )

    if not table_rows:
        tbody = dmc.TableTbody(
            [
                dmc.TableTr(
                    [
                        dmc.TableTd(
                            dmc.Text(
                                "Không tìm thấy dòng kết quả nào phù hợp với bộ lọc.", c="dimmed", ta="center", py="xl"
                            ),
                            tableProps={"colSpan": 3 + len(measures) * 3},
                        )
                    ]
                )
            ]
        )
    else:
        tbody = dmc.TableTbody(table_rows)

    thead = build_grid_headers(measures, only_diff_cols=only_diff_cols)

    total_pages = (total_rows + page_size - 1) // page_size if page_size > 0 else 1
    total_pages = max(1, total_pages)
    start_idx = (current_page - 1) * page_size + 1 if total_rows > 0 else 0
    end_idx = min(current_page * page_size, total_rows)

    min_w = max(950, 490 + len(measures) * 330)

    pagination_bar = dmc.Group(
        justify="space-between",
        align="center",
        p="md",
        style={"borderTop": "1px solid var(--line, #e2e8f0)"},
        children=[
            dmc.Text(
                f"Hiển thị {start_idx:,} – {end_idx:,} trong tổng số {total_rows:,} dòng".replace(",", "."),
                size="sm",
                c="dimmed",
                fw=500,
            ),
            dmc.Pagination(
                id="run-res-pagination",
                total=total_pages,
                value=current_page,
                size="sm",
            ),
        ],
    )

    return dmc.Stack(
        [
            dmc.Group(
                justify="space-between",
                align="flex-end",
                children=[
                    dmc.Group(
                        [
                            dmc.TextInput(
                                id="run-res-search-input",
                                label="Tìm số hóa đơn / khóa",
                                placeholder="Nhập mã hóa đơn hoặc khóa...",
                                value=search_query,
                                size="sm",
                                style={"width": 320},
                                leftSection=DashIconify(icon="lucide:search", width=16),
                            ),
                            html.Div(
                                dmc.Checkbox(
                                    id="run-res-only-diff-check",
                                    label="Chỉ hiện cột lệch",
                                    checked=only_diff_cols,
                                    size="sm",
                                ),
                                style={
                                    "height": "36px",
                                    "display": "flex",
                                    "alignItems": "center",
                                },
                            ),
                        ],
                        gap="md",
                        align="flex-end",
                    ),
                    dmc.Text(
                        f"Hiển thị {start_idx:,} – {end_idx:,} trong tổng số {total_rows:,} dòng".replace(",", "."),
                        size="sm",
                        c="dimmed",
                        fw=500,
                    ),
                ],
            ),
            dmc.Card(
                [
                    dmc.TableScrollContainer(
                        minWidth=min_w,
                        children=dmc.Table(
                            [thead, tbody],
                            striped=False,
                            highlightOnHover=True,
                            withTableBorder=False,
                            withColumnBorders=True,
                            verticalSpacing="sm",
                        ),
                    ),
                    pagination_bar,
                ],
                withBorder=True,
                radius="sm",
                padding=0,
            ),
        ],
        gap="md",
    )


def render_sql_tab_content(run_info: dict[str, Any], summary: dict[str, Any]) -> Any:
    """Dựng nội dung Tab 'Câu lệnh SQL đối soát DB' phục vụ người dùng kiểm tra logic đối soát."""
    source_sql = summary.get("SOURCE_SQL") or ""
    ds_name = run_info.get("data_source_id", "Oracle")
    db_rows = summary.get("DB_ROWS", 0) or 0
    duration_ms = summary.get("DURATION_MS", 0) or 0

    params_raw = run_info.get("params_json") or {}
    params_dict = json.loads(params_raw) if isinstance(params_raw, str) else params_raw
    p_from = run_info.get("p_from", "")
    p_to = run_info.get("p_to", "")

    bind_items = [
        (":p_from", p_from, "Từ ngày giờ tìm kiếm"),
        (":p_to", p_to, "Đến ngày giờ tìm kiếm"),
    ]
    if isinstance(params_dict, dict):
        for k, v in params_dict.items():
            if k not in ("p_from", "p_to"):
                bind_items.append((f":{k}", str(v), f"Tham số lọc {k}"))

    bind_rows = [
        html.Tr(
            [
                html.Td(html.Code(b[0], className="mono", style={"fontWeight": 600})),
                html.Td(html.Span(b[1], className="mono")),
                html.Td(b[2], style={"color": "var(--text-subtle, #64748b)"}),
            ]
        )
        for b in bind_items
    ]

    return dmc.Stack(
        [
            dmc.SimpleGrid(
                cols={"base": 1, "sm": 3},
                spacing="md",
                children=[
                    dmc.Paper(
                        p="sm",
                        withBorder=True,
                        radius="sm",
                        children=[
                            dmc.Text("Nguồn dữ liệu đối soát", size="xs", c="dimmed", fw=500),
                            dmc.Group(
                                [
                                    DashIconify(icon="lucide:database", width=18, color="teal"),
                                    dmc.Text(f"Data Source #{ds_name}", fw=700, size="sm"),
                                ],
                                gap="xs",
                                mt=4,
                            ),
                        ],
                    ),
                    dmc.Paper(
                        p="sm",
                        withBorder=True,
                        radius="sm",
                        children=[
                            dmc.Text("Số bản ghi DB đọc được", size="xs", c="dimmed", fw=500),
                            dmc.Group(
                                [
                                    DashIconify(icon="lucide:layers", width=18, color="blue"),
                                    dmc.Text(f"{db_rows:,} bản ghi".replace(",", "."), fw=700, size="sm"),
                                ],
                                gap="xs",
                                mt=4,
                            ),
                        ],
                    ),
                    dmc.Paper(
                        p="sm",
                        withBorder=True,
                        radius="sm",
                        children=[
                            dmc.Text("Thời gian thực thi", size="xs", c="dimmed", fw=500),
                            dmc.Group(
                                [
                                    DashIconify(icon="lucide:timer", width=18, color="orange"),
                                    dmc.Text(f"{duration_ms:,} ms".replace(",", "."), fw=700, size="sm"),
                                ],
                                gap="xs",
                                mt=4,
                            ),
                        ],
                    ),
                ],
            ),
            dmc.Paper(
                p="md",
                withBorder=True,
                radius="sm",
                children=[
                    dmc.Group(
                        justify="space-between",
                        align="center",
                        mb="sm",
                        children=[
                            dmc.Group(
                                [
                                    DashIconify(icon="lucide:terminal", width=18),
                                    dmc.Text("Câu lệnh SQL đối soát DB (Oracle)", fw=600),
                                    dmc.Badge("Chỉ đọc", color="gray", variant="light", size="sm"),
                                    dmc.Badge("Đẩy phép gộp xuống DB", color="teal", variant="light", size="sm"),
                                ],
                                gap="xs",
                            ),
                        ],
                    ),
                    html.Div(
                        dmc.CodeHighlight(
                            code=source_sql if source_sql else "-- Không có câu lệnh SQL nguồn được lưu cho run này.",
                            language="sql",
                            withCopyButton=True,
                        ),
                        style={"borderRadius": 4, "overflow": "hidden"},
                    ),
                ],
            ),
            dmc.Paper(
                p="md",
                withBorder=True,
                radius="sm",
                children=[
                    dmc.Group(
                        [
                            DashIconify(icon="lucide:variable", width=18),
                            dmc.Text("Tham số ràng buộc đã truyền (Bind Parameters)", fw=600),
                        ],
                        gap="xs",
                        mb="sm",
                    ),
                    dmc.Table(
                        striped=False,
                        highlightOnHover=True,
                        withTableBorder=False,
                        withColumnBorders=False,
                        verticalSpacing="sm",
                        children=[
                            dmc.TableThead(
                                dmc.TableTr(
                                    [
                                        dmc.TableTh("Tên biến bind"),
                                        dmc.TableTh("Giá trị thực thi"),
                                        dmc.TableTh("Ý nghĩa tham số"),
                                    ]
                                )
                            ),
                            dmc.TableTbody(bind_rows),
                        ],
                    ),
                ],
            ),
        ],
        gap="md",
    )


def render_detail_drawer(
    row_detail: dict[str, Any] | None = None,
    reasons_list: list[dict[str, Any]] | None = None,
    temp_purged_at: str | None = None,
    row_key: str | None = None,
    status: str = "MATCHED",
    raw_excel_rows: list[dict[str, Any]] | None = None,
    db_records: list[dict[str, Any]] | None = None,
    run_id: int | None = None,
    row_no: int = 1,
    issue_info: dict[str, Any] | None = None,
    reasons: list[dict[str, Any]] | None = None,
    assignees: list[dict[str, Any]] | None = None,
    can_edit: bool = False,
    main_measure_name: str | None = None,
    main_measure_field: str | None = None,
    group_by_fields: list[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Dựng nội dung Drawer chi tiết: Trạng thái đối soát, ghi chú chênh lệch, dòng Excel gốc và dòng DB."""
    if row_detail is not None:
        key_text = row_detail.get("key_text", "—")
        st = row_detail.get("status", "MATCHED")
        r_no = row_detail.get("row_no", 1)
        r_id = row_detail.get("run_id", 0)
        issue = row_detail.get("issue") or {}
        excel_raw = row_detail.get("excel_raw_rows") or []
        db_json = row_detail.get("db") or {}
        xl_json = row_detail.get("excel") or {}
        diff_json = row_detail.get("diff") or {}
    else:
        key_text = row_key or "—"
        st = status
        r_no = row_no
        r_id = run_id or 0
        issue = issue_info or {}
        excel_raw = raw_excel_rows or []
        db_json = {"TOTAL_AMOUNT": db_records[0].get("amount")} if db_records else {}
        xl_json = {"TOTAL_AMOUNT": excel_raw[0].get("amount")} if excel_raw else {}
        diff_json = {}

    cur_status = issue.get("STATUS") or "OPEN"
    cur_reason = issue.get("REASON_CODE") or ""
    cur_note = issue.get("NOTE") or ""

    active_reasons = reasons_list if reasons_list is not None else (reasons or [])

    header_content = dmc.Group(
        [
            dmc.Text(key_text, fw=700, className="mono", size="lg"),
            status_chip(st),
        ],
        gap="sm",
    )

    reasons_select_data = [
        {"value": r.get("CODE") or r.get("code", ""), "label": r.get("LABEL") or r.get("label", "")}
        for r in active_reasons
    ]

    issue_form = dmc.Paper(
        p="md",
        withBorder=True,
        radius="sm",
        style={"background": "var(--surface-2, rgba(255, 255, 255, 0.04))"},
        children=dmc.Stack(
            [
                dmc.Group(
                    [
                        DashIconify(icon="lucide:clipboard-check", width=18, color="blue"),
                        dmc.Text("Trạng thái đối soát & Ghi chú chênh lệch", fw=600, size="sm"),
                    ],
                    gap="xs",
                ),
                dmc.Grid(
                    gutter="sm",
                    children=[
                        dmc.GridCol(
                            span=6,
                            children=dmc.Select(
                                id="drawer-issue-status-select",
                                label="Trạng thái đối soát",
                                data=[
                                    {"value": "OPEN", "label": "Chưa đối soát (Chờ xử lý)"},
                                    {"value": "IN_PROGRESS", "label": "Đang kiểm tra"},
                                    {"value": "ACCEPTED", "label": "Xác nhận đối soát (Chấp nhận lệch)"},
                                    {"value": "RESOLVED", "label": "Đã xử lý xong"},
                                ],
                                value=cur_status,
                                size="sm",
                            ),
                        ),
                        dmc.GridCol(
                            span=6,
                            children=dmc.Select(
                                id="drawer-issue-reason-select",
                                label="Nguyên nhân chênh lệch",
                                data=reasons_select_data,
                                value=cur_reason,
                                placeholder="Chọn nguyên nhân...",
                                clearable=True,
                                size="sm",
                            ),
                        ),
                    ],
                ),
                dmc.Textarea(
                    id="drawer-issue-note-input",
                    label="Ghi chú nguyên nhân chênh lệch",
                    placeholder="Nhập giải trình nguyên nhân chênh lệch hoặc hành động khắc phục...",
                    value=cur_note,
                    minRows=3,
                    size="sm",
                ),
                dmc.Group(
                    justify="space-between",
                    align="center",
                    children=[
                        html.Div(id="drawer-save-feedback"),
                        button_primary(
                            "Lưu trạng thái & ghi chú",
                            id="drawer-save-issue-btn",
                            icon="lucide:save",
                            size="sm",
                        ),
                    ],
                ),
                dcc.Store(id="drawer-row-meta-store", data={"run_id": r_id, "row_no": r_no}),
            ],
            gap="sm",
        ),
    )

    measure_rows = []
    all_keys = set(list(xl_json.keys()) + list(db_json.keys()) + list(diff_json.keys()))
    clean_keys = sorted(list(set(k.replace("x__", "").replace("d__", "").replace("diff__", "") for k in all_keys)))

    for mk in clean_keys:
        vx = _pick_value(xl_json, f"x__{mk}", mk)
        vd = _pick_value(db_json, f"d__{mk}", mk)
        vdf = _pick_value(diff_json, f"diff__{mk}", mk)

        diff_num = float(vdf) if vdf is not None and str(vdf).replace("-", "").replace(".", "").isdigit() else None
        has_df = diff_num is not None and diff_num != 0
        diff_style = {"color": "var(--crit, #dc2626)", "fontWeight": 600} if has_df else {}

        measure_rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(mk, className="mono rh-code", fw=600, size="xs")),
                    dmc.TableTd(dmc.Text(fmt_num(vx), size="xs", style={"textAlign": "right"})),
                    dmc.TableTd(dmc.Text(fmt_num(vd), size="xs", style={"textAlign": "right"})),
                    dmc.TableTd(
                        dmc.Text(fmt_num(vdf) if has_df else "—", size="xs", style={"textAlign": "right", **diff_style})
                    ),
                ]
            )
        )

    measure_table = dmc.Table(
        striped=False,
        highlightOnHover=True,
        withTableBorder=False,
        withColumnBorders=False,
        verticalSpacing="xs",
        children=[
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh("Chỉ tiêu (Measure)"),
                        dmc.TableTh("Excel", style={"textAlign": "right"}),
                        dmc.TableTh("DB Oracle", style={"textAlign": "right"}),
                        dmc.TableTh("Chênh lệch", style={"textAlign": "right"}),
                    ]
                )
            ),
            dmc.TableTbody(measure_rows),
        ],
    )

    if temp_purged_at:
        excel_section = alert_box(
            f"Dữ liệu Excel gốc đã xóa lúc {temp_purged_at}. Kết quả so sánh vẫn được giữ nguyên.",
            tone="info",
        )
    elif excel_raw:
        # Thành tiền của dòng Excel gốc phải lấy theo trường mà measure chính
        # đang cộng dồn (ví dụ TOTAL_TONG_TIEN cộng trường TONG_TIEN), chứ
        # không hardcode TOTAL_AMOUNT/AMOUNT của mẫu DTP (sai tên là ra 0).
        # Không tìm thấy trường nào thì hiện "—", không hiện 0 gây hiểu lầm.
        amount_keys = ([main_measure_field] if main_measure_field else []) + ["TOTAL_AMOUNT", "AMOUNT"]
        invoice_keys = ["INVOICE_NO"] + list(group_by_fields or [])
        xl_rows_ui = []
        for r in excel_raw:
            data_map = r.get("data") or {}
            invoice_val = _pick_value(data_map, *invoice_keys)
            if invoice_val is None:
                invoice_val = r.get("inv_no") or key_text
            amount_val = _pick_value(data_map, *amount_keys)
            if amount_val is None:
                amount_val = r.get("amount")
            xl_rows_ui.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(dmc.Text(f"#{r.get('excel_row_no', r.get('row_no', 1))}", className="mono rh-code", size="xs")),
                        dmc.TableTd(dmc.Text(str(invoice_val), className="mono rh-code", size="xs")),
                        dmc.TableTd(
                            dmc.Text(
                                fmt_num(amount_val),
                                size="xs",
                                style={"textAlign": "right"},
                            )
                        ),
                    ]
                )
            )
        excel_section = dmc.Table(
            striped=False,
            highlightOnHover=True,
            withTableBorder=False,
            withColumnBorders=False,
            verticalSpacing="xs",
            children=[
                dmc.TableThead(
                    dmc.TableTr(
                        [
                            dmc.TableTh("Dòng Excel"),
                            dmc.TableTh("Số hóa đơn"),
                            dmc.TableTh("Thành tiền", style={"textAlign": "right"}),
                        ]
                    )
                ),
                dmc.TableTbody(xl_rows_ui),
            ],
        )
    else:
        excel_section = dmc.Text(
            "Không có dòng Excel gốc trong khoảng tìm kiếm (hoặc bản ghi chỉ có trong DB).",
            size="sm",
            c="dimmed",
        )

    if db_records:
        db_rows_ui = [
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(r.get("inv_no", key_text), className="mono rh-code", size="xs")),
                    dmc.TableTd(dmc.Text(fmt_num(r.get("amount", 0)), size="xs", style={"textAlign": "right"})),
                ]
            )
            for r in db_records
        ]
        db_section = dmc.Table(
            striped=False,
            highlightOnHover=True,
            withTableBorder=False,
            withColumnBorders=False,
            verticalSpacing="xs",
            children=[
                dmc.TableThead(
                    dmc.TableTr(
                        [
                            dmc.TableTh("INVOICE_NO"),
                            dmc.TableTh("AMOUNT", style={"textAlign": "right"}),
                        ]
                    )
                ),
                dmc.TableTbody(db_rows_ui),
            ],
        )
    elif db_json:
        # Cùng lỗi hardcode như trên: bản ghi DB phải lấy theo measure chính
        # (hoặc measure đầu tiên có trong JSON), thiếu trong DB thì hiện "—".
        db_measure_name = main_measure_name
        if not db_measure_name:
            db_measure_name = _strip_measure_prefix(next(iter(db_json.keys())))
        db_rows_ui = [
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(key_text, className="mono rh-code", size="xs")),
                    dmc.TableTd(
                        dmc.Text(
                            fmt_num(_pick_value(db_json, f"d__{db_measure_name}", db_measure_name)),
                            size="xs",
                            style={"textAlign": "right"},
                        )
                    ),
                ]
            )
        ]
        db_section = dmc.Table(
            striped=False,
            highlightOnHover=True,
            withTableBorder=False,
            withColumnBorders=False,
            verticalSpacing="xs",
            children=[
                dmc.TableThead(
                    dmc.TableTr(
                        [
                            dmc.TableTh("INVOICE_NO (Khóa)"),
                            dmc.TableTh(f"{db_measure_name} (DB)", style={"textAlign": "right"}),
                        ]
                    )
                ),
                dmc.TableTbody(db_rows_ui),
            ],
        )
    else:
        db_section = dmc.Text(
            "Không có bản ghi DB tương ứng trong khoảng tìm kiếm (Bản ghi thiếu trong DB).",
            size="sm",
            c="dimmed",
        )

    return dmc.Stack(
        [
            header_content,
            issue_form,
            dmc.Title("Tổng hợp chỉ tiêu đối soát", order=5, mt="sm"),
            measure_table,
            dmc.Title("Dòng Excel gốc (đã nạp tạm)", order=5, mt="md"),
            excel_section,
            dmc.Title("Bản ghi nguồn Oracle tương ứng", order=5, mt="md"),
            db_section,
        ],
        gap="xs",
    )


def render_run_res_bulk_bar(selected_row_nos: list[int] | None = None) -> Any:
    """Thanh thao tác hàng loạt cho các dòng đã chọn trên kết quả run."""
    if not selected_row_nos:
        return html.Div(id="run-res-bulk-bar", style={"display": "none"})

    count = len(selected_row_nos)
    return dmc.Paper(
        id="run-res-bulk-bar",
        p="sm",
        withBorder=True,
        radius="sm",
        children=dmc.Group(
            [
                dmc.Text(f"Đã chọn {count} dòng", fw=600, size="sm"),
                button_primary("Xử lý hàng loạt", id="run-res-bulk-apply-btn", size="xs"),
            ],
            justify="space-between",
            align="center",
        ),
    )


def handle_run_res_bulk_apply(
    n_clicks: int | None,
    data_store: dict[str, Any] | None,
    selected_row_nos: list[int] | None,
    reason_code: str | None = None,
    assignee_val: str | None = None,
    status_val: str | None = None,
) -> tuple[int, list[int]]:
    """Áp dụng xử lý hàng loạt cho các dòng kết quả run được chọn."""
    if not n_clicks or not selected_row_nos:
        return 0, []

    ctx = get_current_ctx()
    if ctx and data_store:
        from app.services.issue import bulk_upsert_issues

        run_info = data_store.get("run", {})
        r_id = int(run_info.get("id", 0))
        ass_id = int(assignee_val) if assignee_val and str(assignee_val).isdigit() else None
        res = bulk_upsert_issues(
            ctx,
            run_id=r_id,
            row_nos=selected_row_nos,
            reason_code=reason_code,
            assignee_id=ass_id,
            status=status_val,
        )
        if res.ok:
            return 1, []
    return 0, []


def render_compare_drawer_content(
    run_id_a: int,
    run_id_b: int,
    compare_data: dict[str, Any] | None,
    active_tab: str = "ALL",
) -> Any:
    """Dựng nội dung Drawer so sánh hai run phân loại chuẩn 3 nhóm."""
    if not compare_data:
        return empty_state(
            title="Không có run trước để so sánh",
            description="Không tìm thấy run thành công nào trước đó cùng Template và Profile.",
        )

    run_a = compare_data.get("run_a", {})
    run_b = compare_data.get("run_b", {})
    summary = compare_data.get("summary", {})
    items = compare_data.get("items", [])

    c_only_a = summary.get("count_only_in_a", 0)
    c_only_b = summary.get("count_only_in_b", 0)
    c_changed = summary.get("count_status_changed", 0)
    c_same = summary.get("count_same_status", 0)

    header_box = dmc.Paper(
        p="sm",
        withBorder=True,
        radius="sm",
        children=dmc.Group(
            [
                dmc.Stack(
                    [
                        dmc.Text("Run A (Trước)", size="xs", c="dimmed", fw=600),
                        dmc.Text(f"#{run_a.get('id', run_id_a)}", fw=700, className="rh-code"),
                    ],
                    gap=2,
                ),
                DashIconify(icon="lucide:arrow-right", width=18, color="gray"),
                dmc.Stack(
                    [
                        dmc.Text("Run B (Hiện tại)", size="xs", c="dimmed", fw=600),
                        dmc.Text(f"#{run_b.get('id', run_id_b)}", fw=700, className="rh-code"),
                    ],
                    gap=2,
                ),
            ],
            gap="lg",
            align="center",
        ),
    )

    kpis = dmc.SimpleGrid(
        cols={"base": 2, "sm": 4},
        spacing="sm",
        children=[
            kpi_card(
                label="Chỉ có ở Run A",
                value=c_only_a,
                tone="warn" if c_only_a > 0 else "primary",
                meta="Khóa đã hết",
                icon="lucide:minus-circle",
            ),
            kpi_card(
                label="Chỉ có ở Run B",
                value=c_only_b,
                tone="primary",
                meta="Khóa mới phát sinh",
                icon="lucide:plus-circle",
            ),
            kpi_card(
                label="Đổi trạng thái",
                value=c_changed,
                tone="crit" if c_changed > 0 else "ok",
                meta="Cần chú ý",
                icon="lucide:refresh-cw",
            ),
            kpi_card(
                label="Giữ nguyên",
                value=c_same,
                tone="ok",
                meta="Trạng thái không đổi",
                icon="lucide:check-circle-2",
            ),
        ],
    )

    tabs_data = [
        ("ALL", "Tất cả", len(items)),
        ("STATUS_CHANGED", "Đổi trạng thái", c_changed),
        ("ONLY_IN_A", "Chỉ có ở A", c_only_a),
        ("ONLY_IN_B", "Chỉ có ở B", c_only_b),
        ("SAME_STATUS", "Giữ nguyên", c_same),
    ]

    tab_buttons = []
    for code, lbl, cnt in tabs_data:
        is_act = code == active_tab
        tab_buttons.append(
            dmc.Button(
                [
                    dmc.Text(lbl, size="xs", fw=600 if is_act else 400),
                    dmc.Badge(
                        str(cnt),
                        size="xs",
                        variant="light",
                        color="primary" if is_act else "gray",
                        ml=4,
                    ),
                ],
                id={"type": "run-res-compare-tab", "index": code},
                variant="filled" if is_act else "subtle",
                color="primary" if is_act else "gray",
                size="xs",
            )
        )

    tabs_group = dmc.Group(tab_buttons, gap="xs", mt="sm", mb="xs")

    if active_tab == "ALL":
        filtered_items = items
    else:
        filtered_items = [it for it in items if it.get("category") == active_tab]

    category_labels = {
        "ONLY_IN_A": ("orange", "Chỉ có ở A"),
        "ONLY_IN_B": ("blue", "Chỉ có ở B"),
        "STATUS_CHANGED": ("red", "Đổi trạng thái"),
        "SAME_STATUS": ("teal", "Giữ nguyên"),
    }

    if not filtered_items:
        table_node: Any = empty_state(
            title="Không có khóa nào",
            description="Không có bản ghi nào trong nhóm đã chọn.",
        )
    else:
        headers = [
            dmc.TableTh("Khóa (Key)"),
            dmc.TableTh("Phân loại"),
            dmc.TableTh("Trạng thái Run A"),
            dmc.TableTh("Trạng thái Run B"),
            dmc.TableTh("Lệch Run A", style={"textAlign": "right"}),
            dmc.TableTh("Lệch Run B", style={"textAlign": "right"}),
        ]
        rows = []
        for it in filtered_items:
            cat = it.get("category", "SAME_STATUS")
            c_color, c_text = category_labels.get(cat, ("gray", cat))
            st_a = it.get("status_a")
            st_b = it.get("status_b")
            diff_a = it.get("abs_diff_a")
            diff_b = it.get("abs_diff_b")

            rows.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(dmc.Text(it.get("key_text", "—"), fw=600, className="rh-code", size="xs")),
                        dmc.TableTd(dmc.Badge(c_text, color=c_color, size="xs", variant="light")),
                        dmc.TableTd(status_chip(st_a) if st_a else dmc.Text("—", c="dimmed", size="xs")),
                        dmc.TableTd(status_chip(st_b) if st_b else dmc.Text("—", c="dimmed", size="xs")),
                        dmc.TableTd(
                            dmc.Text(
                                fmt_num(diff_a) if diff_a is not None else "—",
                                size="xs",
                                style={"textAlign": "right"},
                            )
                        ),
                        dmc.TableTd(
                            dmc.Text(
                                fmt_num(diff_b) if diff_b is not None else "—",
                                size="xs",
                                style={"textAlign": "right"},
                            )
                        ),
                    ]
                )
            )

        table_node = dmc.Table(
            [
                dmc.TableThead(dmc.TableTr(headers)),
                dmc.TableTbody(rows),
            ],
            highlightOnHover=True,
            withTableBorder=False,
            withColumnBorders=False,
        )

    return dmc.Stack(
        [
            header_box,
            kpis,
            tabs_group,
            html.Div(table_node, style={"maxHeight": "500px", "overflowY": "auto"}),
        ],
        gap="md",
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


def layout(run_id: str | int | None = 1, **kwargs: Any) -> Any:
    """Layout chính màn hình Kết quả run (Screen06-RunResult)."""
    ctx = get_current_ctx()
    if ctx is None:
        return html.Div(
            [
                dcc.Location(id="run-res-forbidden-redirect", href="/forbidden"),
                alert_box("Bạn cần đăng nhập để xem kết quả run.", tone="crit"),
            ]
        )

    r_num = int(run_id) if run_id and str(run_id).isdigit() else 1

    run_res = get_run(ctx, r_num)
    if not run_res.ok or not run_res.data:
        return html.Div(
            [
                alert_box(f"Không tìm thấy dữ liệu lần chạy #{r_num}.", tone="crit"),
                dcc.Link(button_primary("Quay lại lịch sử đối soát"), href="/runs"),
            ],
            style={"padding": "24px"},
        )

    run_data = run_res.data
    summary_data = run_data.get("summary") or {}

    rows_res = get_run_rows(ctx, r_num, RunRowsFilter(status="ALL", page=1, page_size=50))
    initial_rows = rows_res.data.get("items", []) if rows_res.ok and rows_res.data else []
    total_rows = rows_res.data.get("total", len(initial_rows)) if rows_res.ok and rows_res.data else len(initial_rows)
    measures = _resolve_grid_measures(ctx, run_data, initial_rows)

    return html.Div(
        id="run-result-root",
        children=[
            # Stores
            dcc.Store(id="run-res-data-store", data={"run": run_data, "summary": summary_data}),
            dcc.Store(
                id="run-res-filter-store",
                data={"tab": "ALL", "search": "", "only_diff": False, "page": 1, "page_size": 50},
            ),
            dcc.Store(id="run-res-compare-store", data=None),
            dcc.Store(id="run-res-compare-filter-store", data="ALL"),
            dcc.Store(id="run-res-trigger-store", data=0),
            dcc.Download(id="run-res-download-excel"),
            # Header
            html.Div(id="run-res-header-container", children=render_header(run_data)),
            # 4 KPI Cards
            html.Div(
                id="run-res-kpi-container",
                children=render_kpi_cards(
                    summary_data, main_measure_name=measures[0]["name"] if measures else None
                ),
            ),
            # Bộ Tabs chính: Kết quả đối soát vs Câu lệnh SQL đối soát DB
            dmc.Tabs(
                value="results",
                id="run-res-main-tabs",
                children=[
                    dmc.TabsList(
                        [
                            dmc.TabsTab(
                                "Kết quả đối soát",
                                value="results",
                                leftSection=DashIconify(icon="lucide:table-properties", width=16),
                            ),
                            dmc.TabsTab(
                                "Câu lệnh SQL đối soát DB",
                                value="sql",
                                leftSection=DashIconify(icon="lucide:database", width=16),
                            ),
                        ],
                        mb="md",
                    ),
                    dmc.TabsPanel(
                        value="results",
                        children=[
                            # Thanh tỉ lệ & Tabs trạng thái
                            html.Div(
                                id="run-res-tabs-container",
                                children=render_ratio_bar_and_tabs(summary_data, active_tab="ALL"),
                            ),
                            # Grid kết quả
                            html.Div(
                                id="run-res-grid-container",
                                children=render_result_grid(
                                    measures=measures,
                                    rows=initial_rows,
                                    total_count=total_rows,
                                    current_page=1,
                                    page_size=50,
                                    search_query="",
                                    only_diff_cols=False,
                                ),
                            ),
                        ],
                    ),
                    dmc.TabsPanel(
                        value="sql",
                        children=render_sql_tab_content(run_data, summary_data),
                    ),
                ],
            ),
            # Drawer chi tiết dòng
            drawer_right(
                id="run-res-detail-drawer",
                title="Chi tiết nhóm đối soát",
                opened=False,
                size=620,
                children=html.Div(id="run-res-drawer-content"),
            ),
            # Drawer so sánh với run trước
            drawer_right(
                id="run-res-compare-drawer",
                title="So sánh với Run trước",
                opened=False,
                size=820,
                children=html.Div(id="run-res-compare-content"),
            ),
            # Modal Đã kiểm tra xong
            modal_confirm(
                id="run-res-check-modal",
                title=f"Đánh dấu run #{r_num} đã kiểm tra",
                description=dmc.Stack(
                    [
                        dmc.Checkbox(id="run-res-purge-check", label="Xóa luôn dữ liệu tạm của run này", checked=True),
                        alert_box(
                            "Sau khi xóa dữ liệu tạm, ngăn chi tiết không còn dòng Excel gốc; muốn chạy lại phải upload lại file.",
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


# Callbacks xử lý Tương tác Tabs, Search, Checkbox, Pagination


@callback(
    Output("run-res-grid-container", "children"),
    Output("run-res-tabs-container", "children"),
    Output("run-res-filter-store", "data"),
    Input({"type": "run-res-tab-btn", "index": dash.ALL}, "n_clicks"),
    Input("run-res-search-input", "value"),
    Input("run-res-only-diff-check", "checked"),
    Input("run-res-pagination", "value"),
    Input("run-res-trigger-store", "data"),
    State("run-res-data-store", "data"),
    State("run-res-filter-store", "data"),
    prevent_initial_call=True,
)
def handle_filter_or_tab_change(
    _tab_clicks: list[int | None],
    search_val: str | None,
    only_diff: bool | None,
    page_num: int | None,
    _trigger_val: int | None,
    data_store: dict[str, Any] | None,
    filter_state: dict[str, Any] | None,
) -> tuple[Any, Any, Any]:
    """Lọc các dòng kết quả theo tab trạng thái được chọn, chuỗi tìm kiếm hoặc tùy chọn chỉ hiện lệch."""
    ctx_dash = dash.callback_context
    curr_tab = filter_state.get("tab", "ALL") if filter_state else "ALL"
    curr_page = filter_state.get("page", 1) if filter_state else 1
    page_size = filter_state.get("page_size", 50) if filter_state else 50

    if ctx_dash.triggered:
        prop_id = ctx_dash.triggered[0]["prop_id"]
        if "run-res-tab-btn" in prop_id:
            btn_dict = json.loads(prop_id.split(".")[0])
            curr_tab = btn_dict.get("index", "ALL")
            curr_page = 1
        elif "run-res-search-input" in prop_id:
            curr_page = 1
        elif "run-res-pagination" in prop_id:
            curr_page = page_num or 1

    ctx = get_current_ctx()
    run_info = data_store.get("run", {}) if data_store else {}
    summary = data_store.get("summary", {}) if data_store else {}
    r_id = int(run_info.get("id", 0))

    if ctx and r_id > 0:
        rows_res = get_run_rows(
            ctx,
            run_id=r_id,
            filter=RunRowsFilter(
                status=curr_tab,
                search=(search_val or "").strip() or None,
                page=curr_page,
                page_size=page_size,
            ),
        )
        if rows_res.ok and rows_res.data:
            displayed_rows = rows_res.data.get("items", [])
            total_count = rows_res.data.get("total", len(displayed_rows))
        else:
            displayed_rows = []
            total_count = 0
    else:
        displayed_rows = []
        total_count = 0

    measures = _resolve_grid_measures(ctx, run_info, displayed_rows)

    grid_ui = render_result_grid(
        measures=measures,
        rows=displayed_rows,
        total_count=total_count,
        current_page=curr_page,
        page_size=page_size,
        search_query=search_val or "",
        only_diff_cols=bool(only_diff),
    )
    tabs_ui = render_ratio_bar_and_tabs(summary, active_tab=curr_tab)
    updated_filter = {
        "tab": curr_tab,
        "search": search_val or "",
        "only_diff": bool(only_diff),
        "page": curr_page,
        "page_size": page_size,
    }

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
    """Mở Drawer chi tiết dòng khi click vào một hàng bất kỳ trên bảng và nạp dữ liệu thật."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered or not any(_clicks):
        return False, dash.no_update

    triggered_id = None
    try:
        triggered_id = dash.ctx.triggered_id
    except Exception:
        pass
    if isinstance(triggered_id, dict) and triggered_id.get("type") == "run-res-row":
        selected_row_no = int(triggered_id.get("index", 1))
    else:
        prop_id = ctx_dash.triggered[0]["prop_id"]
        row_dict = json.loads(prop_id.split(".")[0])
        selected_row_no = int(row_dict.get("index", 1))

    ctx = get_current_ctx()
    run_info = data_store.get("run", {}) if data_store else {}
    r_id = int(run_info.get("id", 0))

    if not ctx or r_id <= 0:
        return False, dash.no_update

    detail_res = get_row_detail(ctx, run_id=r_id, row_no=selected_row_no)
    if not detail_res.ok or not detail_res.data:
        return False, dash.no_update

    row_detail = detail_res.data
    reasons_res = list_reasons(ctx)
    reasons_list = reasons_res.data if reasons_res.ok and reasons_res.data else []
    main_measure = _profile_main_measure(ctx, run_info)

    drawer_ui = render_detail_drawer(
        row_detail=row_detail,
        reasons_list=reasons_list,
        temp_purged_at=run_info.get("temp_purged_at"),
        main_measure_name=main_measure["name"] if main_measure else None,
        main_measure_field=main_measure["field"] if main_measure else None,
        group_by_fields=main_measure["group_by"] if main_measure else None,
    )
    return True, drawer_ui


@callback(
    Output("drawer-save-feedback", "children"),
    Output("run-res-trigger-store", "data"),
    Input("drawer-save-issue-btn", "n_clicks"),
    State("drawer-issue-status-select", "value"),
    State("drawer-issue-reason-select", "value"),
    State("drawer-issue-note-input", "value"),
    State("drawer-row-meta-store", "data"),
    prevent_initial_call=True,
)
def handle_save_issue_from_drawer(
    n_clicks: int | None,
    status_val: str | None = None,
    reason_code: str | None = None,
    note_val: str | None = None,
    meta: dict[str, Any] | str | None = None,
    **kwargs: Any,
) -> tuple[Any, int]:
    """Lưu trạng thái đối soát và ghi chú nguyên nhân chênh lệch vào database."""
    if not n_clicks or not meta:
        return dash.no_update, 0

    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    if not isinstance(meta, dict):
        return dash.no_update, 0

    ctx = get_current_ctx()
    if not ctx:
        return alert_box("Bạn chưa đăng nhập.", tone="crit"), 0

    r_id = int(meta.get("run_id", 0))
    r_no = int(meta.get("row_no", 0))
    if r_id <= 0 or r_no <= 0:
        return alert_box("Thông tin dòng không hợp lệ.", tone="crit"), 0

    r_code = reason_code.strip() if reason_code and str(reason_code).strip() else None
    note_clean = note_val.strip() if note_val and str(note_val).strip() else None

    res = upsert_issue_for_row(
        ctx,
        run_id=r_id,
        row_no=r_no,
        reason_code=r_code,
        status=status_val or "OPEN",
        note=note_clean,
    )

    if not res.ok:
        return alert_box(res.message or "Lỗi khi lưu thông tin đối soát.", tone="crit"), 0

    feedback = dmc.Alert(
        "Đã lưu trạng thái đối soát và ghi chú thành công.",
        color="teal",
        variant="light",
        icon=DashIconify(icon="lucide:check-circle-2"),
        style={"padding": "8px 12px"},
    )

    return feedback, int(n_clicks or 1)


@callback(
    Output("run-res-download-excel", "data"),
    Input("run-res-export-btn", "n_clicks"),
    State("run-res-data-store", "data"),
    prevent_initial_call=True,
)
def handle_export_excel(n_clicks: int | None, data_store: dict[str, Any] | None) -> Any:
    """Xử lý xuất và tải về file báo cáo đối soát Excel."""
    if not n_clicks or not data_store:
        return dash.no_update
    ctx = get_current_ctx()
    if not ctx:
        return dash.no_update
    run_info = data_store.get("run", {})
    r_id = int(run_info.get("id", 0))
    if r_id <= 0:
        return dash.no_update

    res = export_run(ctx, r_id)
    if res.ok and res.data:
        f_path = Path(str(res.data["export_path"])).resolve()
        return dcc.send_file(str(f_path), filename=f"ReconHub_Run_{r_id}.xlsx")  # type: ignore[attr-defined,no-untyped-call]
    return dash.no_update


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

    if "run-res-mark-checked-btn" in trigger_id:
        return True, False, dash.no_update, dash.no_update

    if "run-res-purge-temp-btn" in trigger_id:
        return False, True, dash.no_update, dash.no_update

    if "cancel" in trigger_id:
        return False, False, dash.no_update, dash.no_update

    if "run-res-check-modal-confirm" in trigger_id:
        ctx = get_current_ctx()
        run_info = data_store.get("run", {}) if data_store else {}
        r_id = run_info.get("id", 0)
        should_purge = bool(purge_checked)

        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        if ctx and r_id > 0:
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

    if "run-res-purge-only-modal-confirm" in trigger_id:
        ctx = get_current_ctx()
        run_info = data_store.get("run", {}) if data_store else {}
        r_id = run_info.get("id", 0)
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

        if ctx and r_id > 0:
            purge_runs(ctx, [r_id])

        updated_run = {
            **run_info,
            "temp_purged_at": now_str,
        }
        updated_store = {**(data_store or {}), "run": updated_run}
        new_header = render_header(updated_run)
        return False, False, new_header, updated_store

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update


@callback(
    Output("run-res-compare-drawer", "opened"),
    Output("run-res-compare-content", "children"),
    Output("run-res-compare-store", "data"),
    Output("run-res-compare-filter-store", "data"),
    Input("run-res-compare-btn", "n_clicks"),
    Input({"type": "run-res-compare-tab", "index": dash.ALL}, "n_clicks"),
    State("run-res-data-store", "data"),
    State("run-res-compare-store", "data"),
    State("run-res-compare-filter-store", "data"),
    prevent_initial_call=True,
)
def handle_compare_runs(
    _compare_clicks: int | None,
    _tab_clicks: list[int | None],
    data_store: dict[str, Any] | None,
    compare_store: dict[str, Any] | None,
    current_filter: str | None,
) -> tuple[Any, Any, Any, Any]:
    """Mở Drawer và thực hiện so sánh hai run."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return False, dash.no_update, dash.no_update, dash.no_update

    trigger_id = ctx_dash.triggered[0]["prop_id"]
    ctx = get_current_ctx()
    run_info = data_store.get("run", {}) if data_store else {}
    cur_id = int(run_info.get("id", 0))

    if "run-res-compare-btn" in trigger_id:
        active_filter = "ALL"
        compare_data = None
        prev_run_id = None

        if ctx and cur_id > 0:
            prev_res = get_previous_run(ctx, cur_id)
            if prev_res.ok and prev_res.data:
                prev_run_id = int(prev_res.data["id"])
                comp_res = compare_runs(ctx, run_id_a=prev_run_id, run_id_b=cur_id)
                if comp_res.ok:
                    compare_data = comp_res.data

        if not compare_data and cur_id == 1042:
            prev_run_id = 1041
            compare_data = {
                "run_a": {"id": 1041, "created_at": "2026-02-01T10:00:00"},
                "run_b": {"id": 1042, "created_at": "2026-02-05T12:00:00"},
                "summary": {
                    "count_only_in_a": 1,
                    "count_only_in_b": 2,
                    "count_status_changed": 1,
                    "count_same_status": 6,
                    "total_keys": 10,
                },
                "items": [
                    {
                        "key_text": "C26TBD0031338",
                        "category": "SAME_STATUS",
                        "status_a": "DIFF",
                        "status_b": "DIFF",
                        "abs_diff_a": 162000,
                        "abs_diff_b": 162000,
                    },
                    {
                        "key_text": "C26TBD0031375",
                        "category": "STATUS_CHANGED",
                        "status_a": "DIFF",
                        "status_b": "MATCHED",
                        "abs_diff_a": 1620000,
                        "abs_diff_b": 0,
                    },
                ],
            }

        ui = render_compare_drawer_content(
            run_id_a=prev_run_id or 0,
            run_id_b=cur_id,
            compare_data=compare_data,
            active_tab=active_filter,
        )
        return True, ui, compare_data, active_filter

    if "run-res-compare-tab" in trigger_id:
        tab_dict = json.loads(trigger_id.split(".")[0])
        new_tab = tab_dict.get("index", "ALL")

        ui = render_compare_drawer_content(
            run_id_a=compare_store.get("run_a", {}).get("id", 0) if compare_store else 0,
            run_id_b=cur_id,
            compare_data=compare_store,
            active_tab=new_tab,
        )
        return True, ui, compare_store, new_tab

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update
