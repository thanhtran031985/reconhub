from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from pydantic import ValidationError

from app.core.context import Role
from app.core.session import get_current_ctx
from app.engine.catalog import list_tables
from app.engine.inspect import inspect_sample
from app.engine.reader import read_sheet
from app.engine.sql_guard import check_sql
from app.schemas.template_config import FileSpec, TemplateConfig
from app.services.data_source import options_data_sources
from app.services.diagram import generate_all_diagrams
from app.services.file_service import upload_file
from app.services.run_service import dry_run as service_dry_run
from app.services.template import activate_version, describe_source, get_template, save_draft_template
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.code_block import code_block
from app.ui.components.file_drop import file_drop
from app.ui.components.kpi_card import kpi_card


def render_step_1(
    config: dict[str, Any],
    preview_rows: list[dict[str, Any]] | None = None,
    sample_data: dict[str, Any] | None = None,
) -> Any:
    """Dựng giao diện Bước 1: File mẫu & cấu trúc file."""
    file_spec = config.get("file", {})
    sheet_val = file_spec.get("sheet", "")
    header_row_val = file_spec.get("header_row", 1)
    data_start_row_val = file_spec.get("data_start_row", 2)
    detect_headers = file_spec.get("detect_by_headers", [])

    # Xử lý thông tin khi đã tải file lên
    uploaded_filename = sample_data.get("filename") if sample_data else None
    if sample_data:
        sheet_val = sample_data.get("sheet") or sheet_val
        if sample_data.get("preview_rows"):
            preview_rows = sample_data["preview_rows"]

    sample_preview = preview_rows or []

    preview_headers = [c for c in list(sample_preview[0].keys()) if c != "__row_no"] if sample_preview else []
    th_cells = [
        html.Th(
            h,
            style={
                "padding": "8px 12px",
                "fontSize": "13px",
                "textAlign": "right"
                if any(k in h.lower() for k in ("stt", "lượng", "tiền", "số"))
                and not any(k in h.lower() for k in ("hóa đơn", "giao dịch", "pin"))
                else "left",
            },
        )
        for h in preview_headers
    ]
    tb_rows = []
    for r in sample_preview:
        td_cells = [
            html.Td(
                html.Span(
                    str(r.get(h, "")),
                    className="mono" if any(k in h.lower() for k in ("mã", "hóa đơn", "pin", "ngày")) else "",
                ),
                style={
                    "padding": "8px 12px",
                    "fontSize": "13px",
                    "textAlign": "right"
                    if any(k in h.lower() for k in ("stt", "lượng", "tiền", "số"))
                    and not any(k in h.lower() for k in ("hóa đơn", "giao dịch", "pin"))
                    else "left",
                },
            )
            for h in preview_headers
        ]
        tb_rows.append(html.Tr(td_cells, style={"borderBottom": "1px solid var(--border-subtle, #e2e8f0)"}))

    # Panel Hệ thống phát hiện
    if sample_data:
        tot_cols = sample_data.get("total_cols", len(preview_headers))
        tot_rows = sample_data.get("total_rows", len(sample_preview))
        detection_alerts: list[Any] = [
            alert_box(f"{tot_cols} cột, {tot_rows} dòng dữ liệu.", tone="ok"),
        ]

        cand_totals = sample_data.get("candidate_total_rows", [])
        if cand_totals:
            for tr in cand_totals[:2]:
                val_parts = [f"{k} = {v}" for k, v in tr.get("values", {}).items()]
                val_str = f" ({', '.join(val_parts)})" if val_parts else ""
                detection_alerts.extend(
                    [
                        html.Div(style={"height": 8}),
                        alert_box(
                            f"Dòng {tr.get('row_no')} là dòng tổng ({tr.get('label_col')} = '{tr.get('label_val')}'). "
                            f"Đề xuất loại khỏi dữ liệu và dùng làm control total.{val_str}",
                            tone="warn",
                        ),
                    ]
                )

        cols_inspect = sample_data.get("columns", [])
        cand_keys = [c for c in cols_inspect if c.get("is_candidate_key")]
        if cand_keys:
            ck = cand_keys[0]
            detection_alerts.extend(
                [
                    html.Div(style={"height": 8}),
                    alert_box(
                        f"'{ck.get('name')}' có {ck.get('unique_count')} giá trị khác nhau trên {tot_rows} dòng: đề xuất so ở mức gộp theo {ck.get('name')}.",
                        tone="info",
                    ),
                ]
            )

        special_cols = [c for c in cols_inspect if c.get("has_leading_zero") or c.get("has_mixed_types")]
        if special_cols:
            sc = special_cols[0]
            reason = "lẫn số và chuỗi" if sc.get("has_mixed_types") else "có số 0 ở đầu"
            detection_alerts.extend(
                [
                    html.Div(style={"height": 8}),
                    alert_box(
                        f"'{sc.get('name')}' {reason}: đọc dạng Text để không mất dữ liệu.",
                        tone="info",
                    ),
                ]
            )

        detection_alerts.append(
            dmc.Checkbox(
                id="wizard-apply-suggestions",
                label="Áp dụng các đề xuất",
                checked=True,
                mt="md",
            )
        )
    else:
        detection_alerts = [
            alert_box(
                "Chưa có file mẫu được tải lên. Kéo thả file Excel hoặc CSV vào khung bên trái để hệ thống tự động phát hiện số dòng, cột và gợi ý cấu trúc.",
                tone="info",
            ),
        ]

    file_label = uploaded_filename or "Kéo thả file Excel hoặc CSV vào đây"
    file_hint = (
        f"Đã nạp file {uploaded_filename} — Kéo thả file khác để thay thế (tối đa 50MB)"
        if uploaded_filename
        else "Hỗ trợ định dạng .xlsx, .xls, .csv (tối đa 50MB)"
    )

    return html.Div(
        [
            # Hàng trên: 2 cột
            dmc.Grid(
                gutter="lg",
                children=[
                    # Cột 1: File mẫu & cấu trúc
                    dmc.GridCol(
                        span=6,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                dmc.Title("Thông tin & File mẫu", order=4, mb="sm"),
                                dmc.Grid(
                                    gutter="sm",
                                    mb="sm",
                                    children=[
                                        dmc.GridCol(
                                            span=6,
                                            children=dmc.TextInput(
                                                id="wizard-input-code",
                                                label="Mã template *",
                                                value=config.get("template_code", "NEW_TEMPLATE"),
                                                placeholder="VD: DTP_HOA_DON_2026",
                                                className="mono",
                                                required=True,
                                            ),
                                        ),
                                        dmc.GridCol(
                                            span=6,
                                            children=dmc.TextInput(
                                                id="wizard-input-name",
                                                label="Tên template *",
                                                value=config.get("name", "Template mới"),
                                                placeholder="VD: Đối soát hóa đơn DTP",
                                                required=True,
                                            ),
                                        ),
                                    ],
                                ),
                                file_drop(
                                    id="wizard-file-drop",
                                    label=file_label,
                                    hint=file_hint,
                                ),
                                dmc.Grid(
                                    gutter="sm",
                                    mt="md",
                                    children=[
                                        dmc.GridCol(
                                            span=6,
                                            children=dmc.TextInput(
                                                id="wizard-input-sheet",
                                                label="Sheet",
                                                value=sheet_val,
                                            ),
                                        ),
                                        dmc.GridCol(
                                            span=3,
                                            children=dmc.NumberInput(
                                                id="wizard-input-header-row",
                                                label="Dòng header",
                                                value=header_row_val,
                                                min=1,
                                            ),
                                        ),
                                        dmc.GridCol(
                                            span=3,
                                            children=dmc.NumberInput(
                                                id="wizard-input-data-row",
                                                label="Dữ liệu từ dòng",
                                                value=data_start_row_val,
                                                min=1,
                                            ),
                                        ),
                                    ],
                                ),
                                dmc.Text("Header bắt buộc để nhận diện file", size="xs", fw=600, mt="md", mb=6),
                                dmc.Group(
                                    [dmc.Badge(h, variant="light", color="gray", radius="sm") for h in detect_headers]
                                    if detect_headers
                                    else [
                                        dmc.Badge(
                                            "Chưa có header nhận diện (tự động điền khi tải file)",
                                            variant="light",
                                            color="gray",
                                            radius="sm",
                                        )
                                    ],
                                    gap=6,
                                ),
                            ],
                        ),
                    ),
                    # Cột 2: Hệ thống phát hiện
                    dmc.GridCol(
                        span=6,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                dmc.Title("Hệ thống phát hiện", order=4, mb="sm"),
                                *detection_alerts,
                            ],
                        ),
                    ),
                ],
            ),
            # Hàng dưới: Xem trước 5 dòng
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                mt="lg",
                children=[
                    dmc.Title("Xem trước 5 dòng", order=4, mb="sm"),
                    html.Div(
                        dmc.Table(
                            striped=True,
                            children=[
                                html.Thead(html.Tr(th_cells, style={"background": "var(--bg-subtle, #f8fafc)"})),
                                html.Tbody(tb_rows),
                            ],
                        )
                        if tb_rows
                        else dmc.Alert(
                            "Chưa có file mẫu được tải lên. Kéo thả file Excel hoặc CSV ở trên để xem trước 5 dòng đầu tiên và tự động nhận diện cấu trúc.",
                            title="Chưa có dữ liệu xem trước",
                            color="gray",
                            variant="light",
                        ),
                        style={"overflowX": "auto"},
                    ),
                ],
            ),
        ]
    )


def render_step_2(
    config: dict[str, Any],
    errors: dict[str, str] | None = None,
) -> Any:
    """Dựng giao diện Bước 2: Định nghĩa & Ánh xạ trường."""
    fields_list = config.get("fields", [])
    derived_list = config.get("derived", [])

    rows: list[Any] = []
    # Fields
    for idx, f in enumerate(fields_list):
        f_name = f.get("name", "")
        f_label = f.get("label", "")
        f_excel = f.get("excel", "")
        f_type = f.get("type", "text")
        norms = f.get("norm", [])
        norm_badges = []
        for n in norms:
            n_str = list(n.keys())[0] if isinstance(n, dict) else str(n)
            norm_badges.append(dmc.Badge(n_str, size="xs", variant="light", color="gray"))

        is_used = bool(f_excel)
        err_key = f"fields.{idx}.name"
        has_err = bool(errors and err_key in errors)

        sample_v = f.get("sample_value") or (f.get("sample_values")[0] if f.get("sample_values") else "—")
        tr = html.Tr(
            [
                html.Td(
                    dmc.Checkbox(
                        id={"type": "wizard-field-use", "index": idx},
                        checked=is_used,
                        size="xs",
                    ),
                    style={"padding": "8px 10px"},
                ),
                html.Td(html.B(f_excel or f_name), style={"padding": "8px 10px"}),
                html.Td(
                    dmc.TextInput(
                        id={"type": "wizard-field-name", "index": idx},
                        value=f_name,
                        size="xs",
                        className="mono",
                        style={"width": 150},
                        error=errors[err_key] if has_err and errors else None,
                    ),
                    style={"padding": "8px 10px"},
                ),
                html.Td(
                    dmc.TextInput(
                        id={"type": "wizard-field-label", "index": idx},
                        value=f_label,
                        size="xs",
                        style={"width": 150},
                    ),
                    style={"padding": "8px 10px"},
                ),
                html.Td(
                    dmc.Select(
                        id={"type": "wizard-field-type", "index": idx},
                        value=f_type,
                        size="xs",
                        data=[
                            {"label": "text", "value": "text"},
                            {"label": "number", "value": "number"},
                            {"label": "date", "value": "date"},
                            {"label": "datetime", "value": "datetime"},
                        ],
                        style={"width": 110},
                    ),
                    style={"padding": "8px 10px"},
                ),
                html.Td(dmc.Group(norm_badges, gap=4), style={"padding": "8px 10px"}),
                html.Td(
                    html.Span(
                        str(sample_v),
                        className="mono",
                        style={"color": "var(--text-muted, #94a3b8)"} if sample_v == "—" else {},
                    ),
                    style={"padding": "8px 10px"},
                ),
            ],
            style={"opacity": 1.0 if is_used else 0.5, "borderBottom": "1px solid var(--border-subtle, #e2e8f0)"},
        )
        rows.append(tr)

    # Derived fields
    for d_idx, d in enumerate(derived_list):
        d_name = d.get("name", "")
        d_label = d.get("label", "")
        d_type = d.get("type", "date")
        expr_str = f"derived: {d.get('expr', {}).get('fn', '')}"
        tr = html.Tr(
            [
                html.Td(dmc.Checkbox(checked=True, size="xs"), style={"padding": "8px 10px"}),
                html.Td(html.B(expr_str), style={"padding": "8px 10px"}),
                html.Td(
                    dmc.TextInput(
                        id={"type": "wizard-derived-name", "index": d_idx},
                        value=d_name,
                        size="xs",
                        className="mono",
                        style={"width": 150},
                    ),
                    style={"padding": "8px 10px"},
                ),
                html.Td(
                    dmc.TextInput(
                        id={"type": "wizard-derived-label", "index": d_idx},
                        value=d_label,
                        size="xs",
                        style={"width": 150},
                    ),
                    style={"padding": "8px 10px"},
                ),
                html.Td(
                    dmc.Select(
                        id={"type": "wizard-derived-type", "index": d_idx},
                        value=d_type,
                        size="xs",
                        data=[
                            {"label": "text", "value": "text"},
                            {"label": "number", "value": "number"},
                            {"label": "date", "value": "date"},
                            {"label": "datetime", "value": "datetime"},
                        ],
                        style={"width": 110},
                    ),
                    style={"padding": "8px 10px"},
                ),
                html.Td(
                    dmc.Badge("derived", size="xs", variant="light", color="purple"), style={"padding": "8px 10px"}
                ),
                html.Td(html.Span("2026-02-01", className="mono"), style={"padding": "8px 10px"}),
            ],
            style={"borderBottom": "1px solid var(--border-subtle, #e2e8f0)"},
        )
        rows.append(tr)

    return dmc.Paper(
        withBorder=True,
        p="md",
        radius="sm",
        children=[
            dmc.Group(
                justify="space-between",
                mb="md",
                children=[
                    dmc.Title("Cột Excel → Trường logic", order=4),
                    dmc.Group(
                        [
                            button_subtle("Gợi ý lại", id="wizard-re-suggest-btn", icon="lucide:sparkles", size="sm"),
                            button_subtle(
                                "Trường dẫn xuất", id="wizard-add-derived-btn", icon="lucide:plus", size="sm"
                            ),
                        ],
                        gap="sm",
                    ),
                ],
            ),
            html.Div(
                dmc.Table(
                    striped=True,
                    children=[
                        html.Thead(
                            html.Tr(
                                [
                                    html.Th("Dùng", style={"padding": "8px 10px"}),
                                    html.Th("Cột Excel", style={"padding": "8px 10px"}),
                                    html.Th("Trường logic", style={"padding": "8px 10px"}),
                                    html.Th("Nhãn", style={"padding": "8px 10px"}),
                                    html.Th("Kiểu", style={"padding": "8px 10px"}),
                                    html.Th("Chuẩn hóa", style={"padding": "8px 10px"}),
                                    html.Th("Giá trị mẫu", style={"padding": "8px 10px"}),
                                ],
                                style={"background": "var(--bg-subtle, #f8fafc)"},
                            )
                        ),
                        html.Tbody(rows),
                    ],
                ),
                style={"overflowX": "auto"},
            ),
        ],
    )


def _resolve_ds_id_and_schema(ctx: Any, ds_name: str | None) -> tuple[int | None, str]:
    """Tìm ID và Default Schema của Data Source dựa trên tên."""
    if ctx is None:
        return None, "DATARAW"
    try:
        opts_res = options_data_sources(ctx, purpose="SOURCE")
        if opts_res.ok and opts_res.data:
            if ds_name:
                for opt in opts_res.data:
                    if opt.name == ds_name:
                        return opt.id, (opt.default_schema or "DATARAW").upper()
            first = opts_res.data[0]
            return first.id, (first.default_schema or "DATARAW").upper()
    except Exception:
        pass
    return None, "DATARAW"


def _fetch_table_options(ds_id: int | None, schema: str) -> list[dict[str, str]]:
    """Lấy danh sách bảng/view từ catalog cho Data Source."""
    if ds_id is None:
        return []
    try:
        tables = list_tables(ds_id, schema=schema)
        return [
            {
                "label": f"{t['schema']}.{t['name']} ({t['type']})",
                "value": f"{t['schema']}.{t['name']}",
            }
            for t in tables
        ]
    except Exception:
        return []


def _auto_match_db_columns(
    fields: list[dict[str, Any]],
    db_cols_chips: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Tự động ánh xạ trường logic với cột DB dựa trên tên và quy tắc tương đồng."""
    col_names = [c[0] for c in db_cols_chips]
    col_names_upper = {c[0].upper(): c[0] for c in db_cols_chips}

    synonyms: dict[str, list[str]] = {
        "INVOICE_NO": ["INVOICE_NO", "INVOICENO", "BILL_NO", "BILLNO", "INV_NO", "SERIAL_NO"],
        "INV_DATETIME": ["INVOICE_DATE", "INV_DATE", "BILL_DATE", "TRANSACTION_DATE", "TXN_DATE", "DATE_VALUE"],
        "INV_DATE": ["INVOICE_DATE", "INV_DATE", "BILL_DATE", "DATE_VALUE", "TRANSACTION_DATE"],
        "AMOUNT": ["AMOUNT", "TOTAL_AMOUNT", "BILL_AMOUNT", "NET_AMOUNT", "AMT"],
        "QTY": ["QUANTITY", "QTY", "TOTAL_QTY", "COUNT"],
        "STATUS": ["INVOICE_STATUS", "STATUS", "BILL_STATUS"],
        "TXN_ID": ["TXN_ID", "TRANSACTION_ID", "TRANS_ID"],
        "PIN": ["PIN_NO", "PIN", "PIN_CODE"],
        "POINT": ["COLLECT_POINT", "POINT", "ORG_CODE", "BRANCH_CODE"],
        "SERVICE_CODE": ["SERVICE_CODE", "SRV_CODE", "SERVICE_ID"],
    }

    updated_fields: list[dict[str, Any]] = []
    for f in fields:
        f_copy = dict(f)
        current_db = f_copy.get("db")
        if current_db and current_db in col_names:
            updated_fields.append(f_copy)
            continue

        matched_col = None
        f_name_u = (f_copy.get("name") or "").upper()
        f_excel_u = (f_copy.get("excel") or "").upper()

        if f_name_u in col_names_upper:
            matched_col = col_names_upper[f_name_u]
        elif f_excel_u in col_names_upper:
            matched_col = col_names_upper[f_excel_u]
        elif f_name_u in synonyms:
            for syn in synonyms[f_name_u]:
                if syn.upper() in col_names_upper:
                    matched_col = col_names_upper[syn.upper()]
                    break

        if matched_col:
            f_copy["db"] = matched_col

        updated_fields.append(f_copy)
    return updated_fields


def _render_columns_chips(db_cols_chips: list[tuple[str, str]]) -> Any:
    """Hiển thị nhóm chip các cột bảng nguồn."""
    if not db_cols_chips:
        return html.Div(alert_box("Chưa có thông tin cột nguồn. Hãy chọn bảng hoặc kiểm tra SQL.", tone="info"))
    return html.Div(
        [
            dmc.Group(
                [
                    dmc.Text("Cột bảng nguồn", size="xs", fw=600),
                    dmc.Badge(f"{len(db_cols_chips)} cột", size="xs", variant="light", color="primary"),
                ],
                justify="space-between",
                mb=6,
            ),
            html.Div(
                dmc.Group(
                    [
                        dmc.Badge(
                            f"{col} ({t})",
                            size="xs",
                            variant="light",
                            color="gray",
                            radius="sm",
                            className="mono",
                        )
                        for col, t in db_cols_chips
                    ],
                    gap=4,
                ),
                style={"maxHeight": "170px", "overflowY": "auto", "padding": "4px"},
            ),
        ]
    )


def _render_db_mapping_table(
    fields: list[dict[str, Any]],
    db_cols_chips: list[tuple[str, str]],
) -> Any:
    """Hiển thị bảng ánh xạ Cột DB -> Trường logic."""
    col_names = [c[0] for c in db_cols_chips]
    type_lookup = {c[0]: c[1] for c in db_cols_chips}

    mapping_options = [{"label": c, "value": c} for c in col_names] + [
        {"label": "— Không có —", "value": "— Không có —"}
    ]

    rows = []
    for f in fields:
        f_name = f.get("name", "")
        f_label = f.get("label", f_name)
        db_col = f.get("db")
        if db_col and db_col in type_lookup:
            status_badge = dmc.Badge("Đã map", size="xs", variant="light", color="green")
            col_type = type_lookup.get(db_col, "VARCHAR2")
        elif db_col:
            status_badge = dmc.Badge("Đã map", size="xs", variant="light", color="green")
            col_type = type_lookup.get(db_col, "VARCHAR2")
        else:
            status_badge = dmc.Badge("Chỉ có ở Excel", size="xs", variant="light", color="yellow")
            col_type = "—"

        rows.append(
            html.Tr(
                [
                    html.Td(
                        [
                            html.Span(f_name, className="mono", style={"fontWeight": 600}),
                            html.Span(
                                f" ({f_label})",
                                style={"color": "var(--text-muted, #64748b)", "fontSize": "11px"},
                            )
                            if f_label and f_label != f_name
                            else None,
                        ],
                        style={"padding": "8px 10px"},
                    ),
                    html.Td(
                        dmc.Select(
                            id={"type": "wizard-db-mapping-col", "index": f_name},
                            value=db_col or "— Không có —",
                            size="xs",
                            className="mono",
                            data=mapping_options,
                            searchable=True,
                            clearable=False,
                            style={"width": 190},
                        ),
                        style={"padding": "8px 10px"},
                    ),
                    html.Td(html.Span(col_type, className="mono"), style={"padding": "8px 10px"}),
                    html.Td(status_badge, style={"padding": "8px 10px"}),
                ],
                style={"borderBottom": "1px solid var(--border-subtle, #e2e8f0)"},
            )
        )

    return dmc.Table(
        striped=True,
        children=[
            html.Thead(
                html.Tr(
                    [
                        html.Th("Trường logic"),
                        html.Th("Cột DB"),
                        html.Th("Kiểu DB"),
                        html.Th("Trạng thái"),
                    ],
                    style={"background": "var(--bg-subtle, #f8fafc)"},
                )
            ),
            html.Tbody(rows),
        ],
    )


def _render_filter_params_table(
    db_cols_chips: list[tuple[str, str]],
    p_from_col: str = "",
    p_to_col: str = "",
    p_org_col: str = "",
    p_org_default: str = "",
    extra_filters: list[dict[str, Any]] | None = None,
) -> Any:
    """Hiển thị bảng tham số lọc Từ ngày giờ, Đến ngày giờ, Đơn vị và các tham số bổ sung."""
    col_names = [c[0] for c in db_cols_chips] if db_cols_chips else []

    date_cols = [c[0] for c in db_cols_chips if "DATE" in c[1].upper() or "TIME" in c[1].upper()]
    if not date_cols:
        date_cols = col_names

    sel_p_from = p_from_col if p_from_col in col_names else None
    sel_p_to = p_to_col if p_to_col in col_names else None
    sel_p_org = p_org_col if p_org_col in col_names else None

    col_select_data = [{"label": c, "value": c} for c in col_names]
    op_select_data = [
        {"label": "=", "value": "="},
        {"label": "!=", "value": "!="},
        {"label": ">=", "value": ">="},
        {"label": "<=", "value": "<="},
        {"label": "IN", "value": "in"},
        {"label": "LIKE", "value": "like"},
    ]

    base_rows = [
        html.Tr(
            [
                html.Td([html.B("Từ ngày giờ "), html.Span("p_from *", className="mono")]),
                html.Td(
                    dmc.Select(
                        id="wizard-filter-p-from-col",
                        value=sel_p_from,
                        data=col_select_data,
                        searchable=True,
                        size="xs",
                        className="mono",
                        style={"width": 160},
                    )
                ),
                html.Td(html.Span(">=", className="mono")),
                html.Td("Ngày giờ"),
                html.Td("Hôm qua 00:00:00"),
                html.Td(""),
            ]
        ),
        html.Tr(
            [
                html.Td([html.B("Đến ngày giờ "), html.Span("p_to *", className="mono")]),
                html.Td(
                    dmc.Select(
                        id="wizard-filter-p-to-col",
                        value=sel_p_to,
                        data=col_select_data,
                        searchable=True,
                        size="xs",
                        className="mono",
                        style={"width": 160},
                    )
                ),
                html.Td(html.Span("<=", className="mono")),
                html.Td("Ngày giờ"),
                html.Td("Hôm qua 23:59:59"),
                html.Td(""),
            ]
        ),
        html.Tr(
            [
                html.Td([html.B("Đơn vị "), html.Span("p_org *", className="mono")]),
                html.Td(
                    dmc.Select(
                        id="wizard-filter-p-org-col",
                        value=sel_p_org,
                        data=col_select_data,
                        searchable=True,
                        size="xs",
                        className="mono",
                        style={"width": 160},
                    )
                ),
                html.Td(html.Span("=", className="mono")),
                html.Td("—"),
                html.Td(
                    dmc.TextInput(
                        id="wizard-filter-p-org-val",
                        value=p_org_default,
                        size="xs",
                        className="mono",
                        style={"width": 80},
                    )
                ),
                html.Td(""),
            ]
        ),
    ]

    extra_rows = []
    if extra_filters:
        for idx, flt in enumerate(extra_filters):
            p_name = flt.get("param", f"p_param_{idx + 1}")
            p_col = flt.get("column") or (col_names[0] if col_names else "")
            p_op = flt.get("op", "=")
            p_def = flt.get("default", "")

            extra_rows.append(
                html.Tr(
                    [
                        html.Td(
                            dmc.TextInput(
                                id={"type": "wizard-extra-param-name", "index": idx},
                                value=p_name,
                                placeholder="tên :biến",
                                size="xs",
                                className="mono",
                                style={"width": 120},
                            )
                        ),
                        html.Td(
                            dmc.Select(
                                id={"type": "wizard-extra-param-col", "index": idx},
                                value=p_col if p_col in col_names else (col_names[0] if col_names else None),
                                data=col_select_data,
                                searchable=True,
                                size="xs",
                                className="mono",
                                style={"width": 160},
                            )
                        ),
                        html.Td(
                            dmc.Select(
                                id={"type": "wizard-extra-param-op", "index": idx},
                                value=p_op,
                                data=op_select_data,
                                size="xs",
                                className="mono",
                                style={"width": 75},
                            )
                        ),
                        html.Td("—"),
                        html.Td(
                            dmc.TextInput(
                                id={"type": "wizard-extra-param-val", "index": idx},
                                value=p_def,
                                placeholder="Mặc định",
                                size="xs",
                                className="mono",
                                style={"width": 90},
                            )
                        ),
                        html.Td(
                            dmc.ActionIcon(
                                DashIconify(icon="lucide:trash-2", width=14),
                                id={"type": "wizard-extra-param-del", "index": idx},
                                color="red",
                                variant="subtle",
                                size="sm",
                            )
                        ),
                    ]
                )
            )

    return dmc.Table(
        striped=True,
        children=[
            html.Thead(
                html.Tr(
                    [
                        html.Th("Tham số (nhập khi chạy)"),
                        html.Th("Cột DB"),
                        html.Th("Phép"),
                        html.Th("So theo"),
                        html.Th("Mặc định"),
                        html.Th("", style={"width": 36}),
                    ],
                    style={"background": "var(--bg-subtle, #f8fafc)"},
                )
            ),
            html.Tbody(base_rows + extra_rows),
        ],
    )


def _render_generated_sql(
    table_name: str | None,
    fields: list[dict[str, Any]],
    p_from_col: str = "",
    p_to_col: str = "",
    p_org_col: str = "",
    extra_filters: list[dict[str, Any]] | None = None,
) -> str:
    """Sinh câu truy vấn SELECT mẫu để xem trước."""
    db_cols = [f["db"] for f in fields if f.get("db")]
    if not table_name or not db_cols:
        return "-- Chưa chọn bảng nguồn hoặc chưa map cột DB, chưa sinh được câu SELECT."

    quoted_cols = [f'"{c}"' for c in db_cols]
    select_str = ",\n       ".join(quoted_cols)

    tbl = table_name
    parts = tbl.split(".")
    if len(parts) == 2:
        from_str = f'"{parts[0]}"."{parts[1]}"'
    else:
        from_str = f'"{tbl}"'

    where_clauses: list[str] = []
    if p_from_col:
        where_clauses.append(f'"{p_from_col}" >= :p_from')
    if p_to_col:
        where_clauses.append(f'"{p_to_col}" <= :p_to')
    if p_org_col:
        where_clauses.append(f'"{p_org_col}" = :p_org')

    if extra_filters:
        for flt in extra_filters:
            col = flt.get("column")
            param = flt.get("param")
            op = flt.get("op", "=").upper()
            if col and param:
                where_clauses.append(f'"{col}" {op} :{param}')

    if not where_clauses:
        return f"SELECT {select_str}\nFROM   {from_str}"
    where_str = "\nAND    ".join(where_clauses)
    return f"SELECT {select_str}\nFROM   {from_str}\nWHERE  {where_str}"


def render_step_3(
    config: dict[str, Any],
    _errors: dict[str, str] | None = None,
) -> Any:
    """Dựng giao diện Bước 3: Nguồn dữ liệu DB & Điều kiện lọc."""
    db_spec = config.get("db_source", {})
    source_id = db_spec.get("source_id", "")
    mode_val = db_spec.get("kind", "table")
    table_name = db_spec.get("table", "")
    sql_val = db_spec.get("sql") or ""
    pushdown = db_spec.get("pushdown_aggregate", True)

    # Nạp danh sách Data Sources đang hoạt động từ DB
    ctx = get_current_ctx()
    ds_options: list[dict[str, str]] = []
    if ctx is not None:
        try:
            opts_res = options_data_sources(ctx, purpose="SOURCE")
            if opts_res.ok and opts_res.data:
                for opt in opts_res.data:
                    ds_options.append(
                        {
                            "label": f"{opt.name} ({opt.env}) – chỉ đọc",
                            "value": opt.name,
                        }
                    )
        except Exception:
            pass

    selected_ds = source_id if source_id in [o["value"] for o in ds_options] else None

    if selected_ds is None:
        ds_id, default_schema, table_options = None, "", []
    else:
        ds_id, default_schema = _resolve_ds_id_and_schema(ctx, selected_ds)
        table_options = _fetch_table_options(ds_id, default_schema)

    # Không tự chọn bảng: người dùng phải chọn bảng/view thật trong danh sách.

    if table_name and not any(t["value"] == table_name for t in table_options):
        table_options.insert(0, {"label": f"{table_name} (Hiện tại)", "value": table_name})

    # Cột bảng nguồn: lấy từ cache _columns nếu có, hoặc fetch trực tiếp
    db_cols_chips = db_spec.get("_columns")
    fields = config.get("fields", [])
    if not db_cols_chips and ctx is not None and ds_id is not None:
        try:
            if mode_val == "sql" and sql_val:
                reg_p = ["p_from", "p_to", "p_org"]
                for flt in db_spec.get("filters", []):
                    if flt.get("param") and flt.get("param") not in reg_p:
                        reg_p.append(flt.get("param"))
                for ef in db_spec.get("extra_filters", []):
                    if ef.get("param") and ef.get("param") not in reg_p:
                        reg_p.append(ef.get("param"))
                desc_res = describe_source(
                    ctx, data_source_id=ds_id, sql=sql_val, schema=default_schema, allowed_params=reg_p
                )
            else:
                desc_res = describe_source(ctx, data_source_id=ds_id, table_name=table_name, schema=default_schema)
            if desc_res.ok and desc_res.data:
                db_cols_chips = [(str(c["name"]), str(c.get("data_type", "VARCHAR2"))) for c in desc_res.data]
                db_spec["_columns"] = db_cols_chips
        except Exception:
            pass

    if not db_cols_chips:
        db_cols_chips = []

    # Tự động match các trường nếu chưa map
    if fields and not any(f.get("db") for f in fields):
        fields = _auto_match_db_columns(fields, db_cols_chips)
        config["fields"] = fields

    # Filter params
    filters = db_spec.get("filters", [])
    extra_filters = db_spec.get("extra_filters", [])
    p_from_col = ""
    p_to_col = ""
    p_org_col = ""
    p_org_default = ""
    for flt in filters:
        if flt.get("param") == "p_from":
            p_from_col = flt.get("column", p_from_col)
        elif flt.get("param") == "p_to":
            p_to_col = flt.get("column", p_to_col)
        elif flt.get("param") == "p_org":
            p_org_col = flt.get("column", p_org_col)

    for p in db_spec.get("params", []):
        if p.get("name") == "p_org" and p.get("default"):
            p_org_default = str(p.get("default"))

    generated_sql = _render_generated_sql(table_name, fields, p_from_col, p_to_col, p_org_col, extra_filters)

    table_box_style = {"display": "block"} if mode_val == "table" else {"display": "none"}
    sql_box_style = {"display": "block"} if mode_val == "sql" else {"display": "none"}
    gen_sql_card_style = {"display": "block"} if mode_val == "table" else {"display": "none"}

    return html.Div(
        [
            # Card 1: Nguồn dữ liệu DB + Cách khai báo + Đẩy phép gộp
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                mb="md",
                children=[
                    dmc.Title("Nguồn dữ liệu DB", order=4, mb="sm"),
                    dmc.Group(
                        align="flex-end",
                        gap="lg",
                        children=[
                            dmc.Select(
                                id="wizard-input-ds",
                                label="Data Source (nguồn đối soát)",
                                data=ds_options,
                                value=selected_ds,
                                style={"width": 280},
                            ),
                            html.Div(
                                [
                                    dmc.Text("Cách khai báo", size="sm", fw=500, mb=4),
                                    dmc.SegmentedControl(
                                        id="wizard-db-mode",
                                        value=mode_val,
                                        data=[
                                            {"label": "Bảng/View", "value": "table"},
                                            {"label": "SQL tự viết", "value": "sql"},
                                        ],
                                        radius="sm",
                                    ),
                                ]
                            ),
                            dmc.Checkbox(
                                id="wizard-input-pushdown",
                                label="Đẩy phép gộp (SUM, COUNT) xuống DB",
                                checked=pushdown,
                                mb=6,
                            ),
                        ],
                    ),
                ],
            ),
            # Card 2: Bảng/View nguồn vs Điều kiện lọc
            dmc.Grid(
                gutter="md",
                mb="md",
                children=[
                    # Cột trái: Bảng/View nguồn HOẶC SQL tự viết
                    dmc.GridCol(
                        span=5,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                # Khối chế độ Bảng/View
                                html.Div(
                                    id="wizard-table-mode-box",
                                    style=table_box_style,
                                    children=[
                                        dmc.Group(
                                            [
                                                dmc.Title("Bảng/View nguồn", order=4),
                                                button_subtle(
                                                    "Tải lại cột",
                                                    id="wizard-fetch-table-cols-btn",
                                                    icon="lucide:refresh-cw",
                                                    size="xs",
                                                ),
                                            ],
                                            justify="space-between",
                                            align="center",
                                            mb="xs",
                                        ),
                                        dmc.Select(
                                            id="wizard-input-table",
                                            label="Bảng/View *",
                                            value=table_name,
                                            data=table_options,
                                            searchable=True,
                                            clearable=True,
                                            nothingFoundMessage="Không tìm thấy bảng/view",
                                            className="mono",
                                            description=f"Chọn trong schema {default_schema} ({len(table_options)} bảng/view).",
                                            mb="xs",
                                        ),
                                        html.Div(id="wizard-table-alert"),
                                    ],
                                ),
                                # Khối chế độ SQL tự viết
                                html.Div(
                                    id="wizard-sql-mode-box",
                                    style=sql_box_style,
                                    children=[
                                        dmc.Title("Câu lệnh SQL nguồn", order=4, mb="xs"),
                                        dmc.Textarea(
                                            id="wizard-sql-input",
                                            label="Câu lệnh SQL nguồn chi tiết *",
                                            value=sql_val,
                                            minRows=7,
                                            autosize=True,
                                            className="mono",
                                            description="Hỗ trợ các tham số ràng buộc :p_from, :p_to, :p_org.",
                                            mb="sm",
                                        ),
                                        dmc.Group(
                                            [
                                                button_primary(
                                                    "Kiểm tra & lấy cột",
                                                    id="wizard-check-sql-btn",
                                                    icon="lucide:check-circle",
                                                    size="xs",
                                                ),
                                            ],
                                            justify="flex-end",
                                            mb="xs",
                                        ),
                                        html.Div(id="wizard-sql-validate-alert"),
                                    ],
                                ),
                                # Nhóm chip hiển thị cột chung
                                html.Div(
                                    id="wizard-db-columns-container",
                                    children=_render_columns_chips(db_cols_chips),
                                    style={"marginTop": 12},
                                ),
                            ],
                        ),
                    ),
                    # Cột phải: Điều kiện lọc theo tham số & cố định
                    dmc.GridCol(
                        span=7,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                dmc.Title("Điều kiện lọc theo tham số", order=4, mb="sm"),
                                html.Div(
                                    id="wizard-db-filters-container",
                                    children=_render_filter_params_table(
                                        db_cols_chips, p_from_col, p_to_col, p_org_col, p_org_default, extra_filters
                                    ),
                                ),
                                button_subtle(
                                    "Thêm tham số lọc",
                                    id="wizard-add-param-btn",
                                    icon="lucide:plus",
                                    size="xs",
                                    mt="xs",
                                ),
                            ],
                        ),
                    ),
                ],
            ),
            # Card 3: Câu SELECT sinh ra (chỉ đọc)
            html.Div(
                id="wizard-card-generated-sql",
                style=gen_sql_card_style,
                children=dmc.Paper(
                    withBorder=True,
                    p="md",
                    radius="sm",
                    mb="md",
                    children=[
                        dmc.Title("Câu SELECT sinh ra (chỉ đọc)", order=4, mb="xs"),
                        html.Div(
                            id="wizard-generated-sql-container",
                            children=code_block(generated_sql, language="sql"),
                        ),
                    ],
                ),
            ),
            # Card 4: Cột DB -> Trường logic & Lọc Excel theo cùng khoảng
            dmc.Grid(
                gutter="md",
                children=[
                    dmc.GridCol(
                        span=7,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                dmc.Title("Cột DB → Trường logic", order=4, mb="sm"),
                                html.Div(
                                    id="wizard-db-mapping-container",
                                    children=_render_db_mapping_table(fields, db_cols_chips),
                                ),
                            ],
                        ),
                    ),
                    dmc.GridCol(
                        span=5,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                dmc.Title("Lọc dữ liệu Excel theo cùng khoảng", order=4, mb="sm"),
                                alert_box(
                                    "Từ/Đến ngày giờ do người dùng nhập khi chạy, không lấy từ file. "
                                    "Cùng khoảng áp cho DB (cột lọc Từ/Đến) và Excel.",
                                    tone="info",
                                ),
                                html.Div(style={"height": 12}),
                                dmc.Select(
                                    id="wizard-excel-time-field",
                                    label="Trường thời gian lọc Excel",
                                    data=[
                                        {"label": f.get("name", ""), "value": f.get("name", "")}
                                        for f in fields
                                        if f.get("type") in ("date", "datetime")
                                    ]
                                    + [{"label": "Không lọc Excel", "value": "NONE"}],
                                    value=(
                                        (config.get("time_filter") or {}).get("excel_field")
                                        if config.get("time_filter")
                                        else "NONE"
                                    ),
                                    mb="sm",
                                ),
                                dmc.Select(
                                    id="wizard-excel-suggest-range",
                                    label="Gợi ý khi chạy",
                                    data=[
                                        {"label": "Hôm qua", "value": "yesterday"},
                                        {"label": "Tháng trước", "value": "last_month"},
                                        {"label": "Để trống", "value": "none"},
                                    ],
                                    value=next(
                                        (
                                            p.get("suggest", "yesterday")
                                            for p in db_spec.get("params", [])
                                            if p.get("name") == "p_from" and p.get("suggest")
                                        ),
                                        "yesterday",
                                    ),
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        ]
    )


def _mapped_fields_info(config: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Trường có sẵn ở Bước 4: chỉ những trường so sánh được cả hai phía.

    Trường thường phải có cả cột Excel đang dùng và cột DB đã map ở Bước 3
    (db khác rỗng, không phải sentinel "— Không có —"). Trường dẫn xuất
    không có cột DB trực tiếp, nhưng được tính lại ở cả hai phía từ các
    trường đã map, nên chỉ giữ lại khi mọi tham số là tên trường của nó
    đều nằm trong tập trường đã map.
    """
    cfg = config or {}
    mapped_names: set[str] = set()
    info: list[dict[str, Any]] = []
    for f in cfg.get("fields", []) or []:
        if not isinstance(f, dict):
            continue
        name = f.get("name", "")
        db_col = f.get("db")
        if name and f.get("excel") and db_col and str(db_col).strip() not in ("", "— Không có —"):
            mapped_names.add(name)
            info.append(
                {
                    "name": name,
                    "label": f.get("label", name),
                    "type": f.get("type", "text"),
                    "excel": f.get("excel"),
                    "db": str(db_col).strip(),
                }
            )
    for d in cfg.get("derived", []) or []:
        if not isinstance(d, dict):
            continue
        name = d.get("name", "")
        if not name:
            continue
        expr = d.get("expr") or {}
        args = expr.get("args") if isinstance(expr, dict) else []
        arg_names = [a for a in (args or []) if isinstance(a, str)]
        # Tham số là tên trường có trong config thì phải đã map; tham số
        # dạng tên trường (CHỮ_HOA) nhưng không có trong config cũng coi
        # là chưa map, vì derived không tính được từ trường đã map. Hằng
        # số / chuỗi khác thì bỏ qua.
        field_names = {f.get("name") for f in cfg.get("fields", []) or [] if isinstance(f, dict)}
        field_args = []
        for a in arg_names:
            if a in field_names:
                field_args.append(a)
            elif a and all(c.isupper() or c.isdigit() or c == "_" for c in a):
                field_args.append(a)
        if all(a in mapped_names for a in field_args):
            # Cột DB của trường nguồn đã map, để cột trái Bước 4 hiển
            # thị được "dẫn xuất từ đâu, tính trên cột DB nào".
            source_db: list[str] = []
            for src in field_args:
                src_rec = next(
                    (f for f in cfg.get("fields", []) or [] if isinstance(f, dict) and f.get("name") == src),
                    None,
                )
                if src_rec and src_rec.get("db") and str(src_rec["db"]).strip() not in ("", "— Không có —"):
                    if str(src_rec["db"]).strip() not in source_db:
                        source_db.append(str(src_rec["db"]).strip())
            info.append(
                {
                    "name": name,
                    "label": d.get("label", name),
                    "type": d.get("type", "date"),
                    "excel": None,
                    "db": None,
                    "derived_from": field_args,
                    "source_db": source_db,
                }
            )
    return info


def _build_default_profiles_from_fields(
    fields: list[dict[str, Any]],
    derived: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Profile trống để người dùng tự chọn Group by và Measures.

    Trước đây hàm này tự đoán Group by = INVOICE_NO (hoặc trường đầu tiên)
    và tự sinh TOTAL_AMOUNT/TOTAL_QTY/M_INV_DATE/LINE_CNT theo tên trường,
    nên bấm qua Bước 4 là đã có sẵn một profile mà người dùng chưa chọn gì.
    Giờ chỉ trả về profile rỗng; validate Bước 4 sẽ chặn Tiếp cho đến khi
    người dùng chọn Group by và ít nhất một measure.
    """
    return [
        {
            "code": "PROFILE_1",
            "name": "Profile 1",
            "is_default": True,
            "aggregate": True,
            "group_by": [],
            "measures": [],
            "filters": [],
            "main_measure": None,
            "drilldown_to": None,
        }
    ]


def _calculate_grain_info(
    group_by: list[str],
    sample_data: dict[str, Any] | None,
    total_rows_fallback: int = 200,
) -> tuple[int, int, str]:
    """Tính toán số dòng Excel và số nhóm theo group_by.

    Không có dữ liệu mẫu hoặc không khớp được cột thì trả về 0 nhóm kèm
    mô tả "chưa tính được", không tự điền 190 nhóm / 95% tổng dòng như trước.
    """
    if not sample_data:
        return 0, 0, "Chưa có dữ liệu mẫu để tính số nhóm."
    total_rows = sample_data.get("total_rows", 0) or 0

    groups_count = 0
    if "columns" in sample_data:
        cols = sample_data["columns"]
        matched_unique = []
        for g in group_by:
            for c in cols:
                c_name = c.get("name", "")
                c_suggest = c.get("suggested_field_name", "")
                if g.upper() in (c_name.upper(), c_suggest.upper()):
                    matched_unique.append(c.get("unique_count", 0))
                    break
        if matched_unique:
            if len(matched_unique) == 1:
                groups_count = matched_unique[0]
            else:
                import math

                prod = math.prod(max(1, u) for u in matched_unique)
                groups_count = min(total_rows, prod)

    if groups_count <= 0:
        return total_rows, 0, "Chưa tính được số nhóm từ dữ liệu mẫu."

    pct = (groups_count / total_rows * 100) if total_rows > 0 else 0
    if pct >= 80:
        desc = "Khóa so sánh chi tiết (ở mức hóa đơn/giao dịch), số nhóm gần bằng số dòng."
    elif pct <= 20:
        desc = "Khóa so sánh tổng hợp (ở mức đơn vị/ngày), số nhóm ít."
    else:
        desc = "Khóa so sánh có độ phân giải cân bằng."

    return total_rows, groups_count, desc


def _render_profile_grouped_sql(
    config: dict[str, Any],
    group_by: list[str],
    measures: list[dict[str, Any]],
) -> str:
    """Sinh câu SQL truy vấn gộp cho Bước 4 dựa trên group_by và measures."""
    if not group_by:
        return "-- Chưa chọn Group by, chưa sinh được SQL gộp."
    fields_map = {f.get("name"): f for f in config.get("fields", [])}
    unmapped = [
        g
        for g in group_by
        if g not in {d.get("name") for d in config.get("derived", [])} and not fields_map.get(g, {}).get("db")
    ]
    unmapped += [
        m.get("field")
        for m in measures
        if m.get("field")
        and m.get("field") != "*"
        and m.get("field") not in {d.get("name") for d in config.get("derived", [])}
        and not fields_map.get(m.get("field"), {}).get("db")
    ]
    warn_prefix = (
        f"-- Cảnh báo: trường {', '.join(sorted(set(unmapped)))} chưa map cột DB, SQL này chưa chạy được.\n"
        if unmapped
        else ""
    )

    outer_selects: list[str] = []
    group_by_exprs: list[str] = []
    for g in group_by:
        f_info = fields_map.get(g, {})
        db_col = f_info.get("db", g)
        f_type = f_info.get("type", "text")
        if f_type == "text":
            expr = f'UPPER(TRIM(src."{db_col}"))'
        elif f_type in ("date", "datetime"):
            expr = f'TRUNC(src."{db_col}")'
        else:
            expr = f'src."{db_col}"'
        outer_selects.append(f'{expr} AS "K__{g}"')
        group_by_exprs.append(expr)

    for m in measures:
        agg = m.get("agg", "sum")
        m_name = m.get("name", "M")
        f_name = m.get("field", "")
        f_info = fields_map.get(f_name, {})
        db_col = f_info.get("db", f_name)

        if agg == "sum":
            outer_selects.append(f'SUM(src."{db_col}") AS "M__{m_name}"')
        elif agg == "count":
            if f_name and f_name != "*":
                outer_selects.append(f'COUNT(src."{db_col}") AS "M__{m_name}"')
            else:
                outer_selects.append(f'COUNT(*) AS "M__{m_name}"')
        elif agg == "count_distinct":
            outer_selects.append(f'COUNT(DISTINCT src."{db_col}") AS "M__{m_name}"')
        elif agg == "min":
            outer_selects.append(f'MIN(src."{db_col}") AS "M__{m_name}"')
        elif agg == "max":
            outer_selects.append(f'MAX(src."{db_col}") AS "M__{m_name}"')
        elif agg == "first_distinct":
            outer_selects.append(f'MIN(TRUNC(src."{db_col}")) AS "M__{m_name}"')
            outer_selects.append(f'COUNT(DISTINCT TRUNC(src."{db_col}")) AS "N__{m_name}"')

    outer_select_str = ",\n       ".join(outer_selects)
    group_by_str = ",\n         ".join(group_by_exprs)

    return (
        f"{warn_prefix}"
        f"SELECT {outer_select_str}\n"
        f"FROM   (\n"
        f"    <Câu SELECT sinh ra ở bước 3 với :p_from, :p_to, :p_org>\n"
        f") src\n"
        f"GROUP BY\n"
        f"         {group_by_str}"
    )


def _render_measures_table(
    measures: list[dict[str, Any]],
    avail_field_names: list[str],
    main_measure: str | None = None,
) -> Any:
    """Dựng bảng cấu hình Measures chi tiết và tương tác."""
    agg_options = [
        {"label": "sum (Cộng tổng)", "value": "sum"},
        {"label": "count (Đếm số dòng)", "value": "count"},
        {"label": "count_distinct (Đếm giá trị khác)", "value": "count_distinct"},
        {"label": "min (Nhỏ nhất)", "value": "min"},
        {"label": "max (Lớn nhất)", "value": "max"},
        {"label": "first_distinct (Thuộc tính duy nhất)", "value": "first_distinct"},
    ]

    field_options = [{"label": "* (Tất cả dòng)", "value": "*"}] + [{"label": f, "value": f} for f in avail_field_names]

    compare_options = [
        {"label": "exact (Bằng tuyệt đối)", "value": "exact"},
        {"label": "abs_tol (Sai số tuyệt đối)", "value": "abs_tol"},
        {"label": "pct_tol (Sai số phần trăm %)", "value": "pct_tol"},
        {"label": "display_only (Chỉ hiển thị)", "value": "display_only"},
    ]

    rows = []
    for i, m in enumerate(measures):
        if not isinstance(m, dict):
            continue
        m_name = m.get("name", f"M_{i + 1}")
        m_label = m.get("label", "")
        m_agg = m.get("agg", "sum")
        m_field = m.get("field", "*")
        m_cmp = m.get("compare", "exact")
        m_tol = m.get("tolerance")
        m_round = m.get("round", 0)
        is_main = bool(main_measure) and m_name == main_measure
        has_tol = m_cmp in ("abs_tol", "pct_tol")

        main_badge_or_btn = (
            dmc.Badge("Chính", size="xs", variant="filled", color="primary")
            if is_main
            else dmc.Tooltip(
                label="Đặt làm measure chính",
                children=dmc.ActionIcon(
                    DashIconify(icon="lucide:star", width=14),
                    id={"type": "wizard-m-main-btn", "index": i},
                    variant="subtle",
                    color="gray",
                ),
            )
        )

        del_btn = (
            dmc.Tooltip(
                label="Xóa measure",
                children=dmc.ActionIcon(
                    DashIconify(icon="lucide:trash-2", width=14),
                    id={"type": "wizard-m-delete-btn", "index": i},
                    variant="subtle",
                    color="red",
                ),
            )
            if len(measures) > 1
            else None
        )

        rows.append(
            html.Tr(
                [
                    html.Td(
                        dmc.TextInput(
                            id={"type": "wizard-m-name", "index": i},
                            value=m_name,
                            size="xs",
                            className="mono",
                            style={"width": 130},
                        ),
                        style={"padding": "6px 8px"},
                    ),
                    html.Td(
                        dmc.TextInput(
                            id={"type": "wizard-m-label", "index": i},
                            value=m_label,
                            size="xs",
                            style={"width": 120},
                        ),
                        style={"padding": "6px 8px"},
                    ),
                    html.Td(
                        dmc.Select(
                            id={"type": "wizard-m-agg", "index": i},
                            value=m_agg,
                            data=agg_options,
                            size="xs",
                            style={"width": 140},
                        ),
                        style={"padding": "6px 8px"},
                    ),
                    html.Td(
                        dmc.Select(
                            id={"type": "wizard-m-field", "index": i},
                            value=m_field,
                            data=field_options,
                            searchable=True,
                            size="xs",
                            className="mono",
                            style={"width": 125},
                        ),
                        style={"padding": "6px 8px"},
                    ),
                    html.Td(
                        dmc.Select(
                            id={"type": "wizard-m-cmp", "index": i},
                            value=m_cmp,
                            data=compare_options,
                            size="xs",
                            style={"width": 145},
                        ),
                        style={"padding": "6px 8px"},
                    ),
                    html.Td(
                        dmc.NumberInput(
                            id={"type": "wizard-m-tol", "index": i},
                            value=m_tol if has_tol else None,
                            disabled=not has_tol,
                            min=0,
                            step=0.1,
                            size="xs",
                            style={"width": 85},
                        ),
                        style={"padding": "6px 8px"},
                    ),
                    html.Td(
                        dmc.NumberInput(
                            id={"type": "wizard-m-rnd", "index": i},
                            value=m_round,
                            min=0,
                            max=6,
                            size="xs",
                            style={"width": 70},
                        ),
                        style={"padding": "6px 8px"},
                    ),
                    html.Td(main_badge_or_btn, style={"padding": "6px 8px", "textAlign": "center"}),
                    html.Td(del_btn, style={"padding": "6px 8px", "textAlign": "center"}),
                ],
                style={"borderBottom": "1px solid var(--border-subtle, #e2e8f0)"},
            )
        )

    return html.Div(
        dmc.Table(
            striped=True,
            children=[
                html.Thead(
                    html.Tr(
                        [
                            html.Th("Tên"),
                            html.Th("Nhãn"),
                            html.Th("Hàm"),
                            html.Th("Trường"),
                            html.Th("So sánh"),
                            html.Th("Sai số"),
                            html.Th("Làm tròn"),
                            html.Th("Chính", style={"textAlign": "center"}),
                            html.Th("", style={"textAlign": "center"}),
                        ],
                        style={"background": "var(--bg-subtle, #f8fafc)"},
                    )
                ),
                html.Tbody(rows),
            ],
        ),
        style={"overflowX": "auto"},
    )


def _render_step_4_left_fields(
    avail_fields_info: list[dict[str, Any]],
    current_group_by: list[str],
    current_measure_fields: list[str] | None = None,
) -> Any:
    """Dựng danh sách trường có sẵn ở cột trái Bước 4.

    Mỗi trường thành 2 dòng: dòng 1 là tên + nhãn + kiểu + nút chìa
    khóa / sigma (id giữ nguyên), dòng 2 là mapping Excel → DB để
    người dùng theo dõi được trường này map sang cột DB nào. Trường
    dẫn xuất không có cột DB trực tiếp nên dòng 2 ghi nguồn dẫn xuất
    và cột DB của trường nguồn. Nút chìa khóa / sigma tô đậm khi
    trường đang được dùng ở profile đang xem.
    """
    measure_fields = set(current_measure_fields or [])
    rows = []
    for f in avail_fields_info:
        f_name = f.get("name", "")
        f_label = f.get("label", f_name)
        f_type = f.get("type", "text")
        is_key = f_name in current_group_by
        is_measure = f_name in measure_fields

        derived_from = f.get("derived_from") or []
        if derived_from:
            source_db = f.get("source_db") or []
            mapping_line = f"Dẫn xuất từ: {', '.join(derived_from)}" + (
                f" → DB: {', '.join(source_db)}" if source_db else ""
            )
        else:
            mapping_line = f"Excel: {f.get('excel') or '—'} → DB: {f.get('db') or '—'}"

        rows.append(
            html.Div(
                [
                    dmc.Group(
                        justify="space-between",
                        children=[
                            html.Div(
                                [
                                    html.Span(f_name, className="mono", style={"fontSize": "13px", "fontWeight": 600}),
                                    html.Span(
                                        f" ({f_label})",
                                        style={"color": "var(--text-muted, #64748b)", "fontSize": "11px"},
                                    )
                                    if f_label != f_name
                                    else None,
                                ]
                            ),
                            dmc.Group(
                                [
                                    dmc.Badge(
                                        "Dẫn xuất" if derived_from else f_type,
                                        size="xs",
                                        variant="light",
                                        color="violet" if derived_from else "gray",
                                    ),
                                    dmc.Tooltip(
                                        label=f"Bật/Tắt {f_name} vào Group by",
                                        children=dmc.ActionIcon(
                                            DashIconify(icon="lucide:key", width=14),
                                            id={"type": "wizard-field-key-btn", "index": f_name},
                                            size="xs",
                                            variant="filled" if is_key else "subtle",
                                            color="primary" if is_key else "gray",
                                        ),
                                    ),
                                    dmc.Tooltip(
                                        label=f"Thêm measure từ {f_name}",
                                        children=dmc.ActionIcon(
                                            DashIconify(icon="lucide:sigma", width=14),
                                            id={"type": "wizard-field-sigma-btn", "index": f_name},
                                            size="xs",
                                            variant="filled" if is_measure else "subtle",
                                            color="blue",
                                        ),
                                    ),
                                ],
                                gap=4,
                            ),
                        ],
                    ),
                    html.Div(
                        mapping_line,
                        className="mono",
                        style={"color": "var(--text-muted, #64748b)", "fontSize": "11px", "marginTop": "2px"},
                    ),
                ],
                style={
                    "borderBottom": "1px solid var(--border-subtle, #f1f5f9)",
                    "paddingTop": "4px",
                    "paddingBottom": "4px",
                },
            )
        )
    if not rows:
        return html.Div(
            alert_box(
                "Chưa có trường nào đã map cột DB ở Bước 3. Quay lại Bước 3, chọn Cột DB cho các trường muốn so sánh rồi mới chọn Group by / Measure ở đây.",
                tone="info",
            )
        )
    return html.Div(rows)


def _render_step_4_right_panel(
    active_prof: dict[str, Any],
    avail_field_names: list[str],
    config: dict[str, Any],
    sample_data: dict[str, Any] | None = None,
) -> Any:
    """Dựng toàn bộ nội dung cột phải Bước 4 (Thông tin Profile, Group by, Measures, SQL gộp)."""
    group_by = active_prof.get("group_by", [])
    measures = active_prof.get("measures", [])
    main_m = active_prof.get("main_measure")

    prof_name = active_prof.get("name", "")
    prof_code = active_prof.get("code", "")
    is_default = active_prof.get("is_default", False)
    all_profiles = config.get("profiles", [])
    can_delete = len(all_profiles) > 1

    # Group by chips
    group_by_chips = [
        dmc.Badge(
            g,
            size="sm",
            variant="filled",
            color="primary",
            leftSection=DashIconify(icon="lucide:key", width=14),
            radius="sm",
        )
        for g in group_by
    ]

    # Grain info
    tot_rows, groups_cnt, grain_desc = _calculate_grain_info(group_by, sample_data)
    grain_desc_str = f"({', '.join(group_by)})" if group_by else "(chưa chọn khóa)"
    grain_alert = alert_box(
        f"{grain_desc}"
        if groups_cnt == 0
        else f"{tot_rows:,} dòng Excel → {groups_cnt:,} nhóm theo {grain_desc_str}. {grain_desc}",
        tone="info",
    )

    # Generated Grouped SQL
    grouped_sql = _render_profile_grouped_sql(config, group_by, measures)

    drilldown_opts = [
        {"label": p.get("name") or p.get("code", ""), "value": p.get("code", "")}
        for p in all_profiles
        if p.get("code") != prof_code and p.get("code")
    ] + [
        {"label": "Không phân rã", "value": "NONE"},
    ]

    return html.Div(
        [
            # Card 0: Thông tin Profile (Tên, Mã code, Xóa)
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                mb="md",
                children=[
                    dmc.Group(
                        justify="space-between",
                        align="center",
                        mb="xs",
                        children=[
                            dmc.Group(
                                [
                                    dmc.Title("Thông tin Profile", order=4),
                                    dmc.Badge("Mặc định", color="blue", variant="light", size="sm")
                                    if is_default
                                    else None,
                                ],
                                gap="xs",
                            ),
                            button_subtle(
                                "Xóa profile",
                                id="wizard-delete-profile-btn",
                                icon="lucide:trash-2",
                                color="red",
                                size="xs",
                                disabled=not can_delete,
                            ),
                        ],
                    ),
                    dmc.Grid(
                        gutter="sm",
                        children=[
                            dmc.GridCol(
                                span=6,
                                children=dmc.TextInput(
                                    id="wizard-profile-name-input",
                                    label="Tên Profile *",
                                    value=prof_name,
                                    placeholder="VD: Theo số hóa đơn",
                                    debounce=500,
                                    required=True,
                                ),
                            ),
                            dmc.GridCol(
                                span=6,
                                children=dmc.TextInput(
                                    id="wizard-profile-code-input",
                                    label="Mã Profile (code) *",
                                    value=prof_code,
                                    placeholder="VD: BY_INVOICE",
                                    className="mono",
                                    debounce=500,
                                    required=True,
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            # Card 1: Group by
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                mb="md",
                children=[
                    dmc.Title("Group by (khóa so sánh)", order=4, mb="xs"),
                    dmc.Text(
                        "Cả hai phía được gộp theo các trường này, và các trường này cũng là khóa để ghép (join) Excel với DB.",
                        size="xs",
                        c="dimmed",
                        mb="sm",
                    ),
                    dmc.MultiSelect(
                        id="wizard-groupby-select",
                        label="Chọn các trường gộp",
                        data=[{"label": f, "value": f} for f in avail_field_names],
                        value=group_by,
                        searchable=True,
                        clearable=False,
                        mb="xs",
                    ),
                    html.Div(
                        id="wizard-groupby-chips-container",
                        children=dmc.Group(group_by_chips, gap="xs", mb="xs"),
                    ),
                    html.Div(id="wizard-grain-alert-container", children=grain_alert),
                ],
            ),
            # Card 2: Measures và quy tắc so sánh
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                mb="md",
                children=[
                    dmc.Group(
                        [
                            html.Div(
                                [
                                    dmc.Title("Measures và quy tắc so sánh", order=4),
                                    dmc.Text(
                                        "Mỗi measure gồm một hàm gộp và một trường. Quy tắc so sánh riêng cho từng measure.",
                                        size="xs",
                                        c="dimmed",
                                    ),
                                ]
                            ),
                            button_primary(
                                "Thêm measure",
                                id="wizard-add-measure-btn",
                                icon="lucide:plus",
                                size="xs",
                            ),
                        ],
                        justify="space-between",
                        align="flex-start",
                        mb="sm",
                    ),
                    html.Div(
                        id="wizard-measures-container",
                        children=_render_measures_table(measures, avail_field_names, main_m),
                        # Bảng measures rộng; cột phải thu từ 9 xuống 8
                        # nên cho cuộn ngang trong card thay vì tràn ra.
                        style={"overflowX": "auto"},
                    ),
                    dmc.Grid(
                        gutter="md",
                        mt="md",
                        children=[
                            dmc.GridCol(
                                span=6,
                                children=dmc.TextInput(
                                    id="wizard-profile-filter",
                                    label="Bộ lọc profile (áp cả hai phía)",
                                    placeholder="Ví dụ STATUS = 'ORIGINAL'",
                                    value=active_prof.get("filters_expr", ""),
                                    className="mono",
                                ),
                            ),
                            dmc.GridCol(
                                span=6,
                                children=dmc.Select(
                                    id="wizard-drilldown-select",
                                    label="Drill-down tới",
                                    data=drilldown_opts,
                                    value=active_prof.get("drilldown_to") or "NONE",
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            # Card 3: SQL gộp sinh tự động
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                children=[
                    dmc.Title("SQL gộp sinh tự động (chỉ đọc)", order=4, mb="xs"),
                    dmc.Text(
                        "Cho thấy ứng dụng sẽ bọc câu SQL ở Bước 3 thành truy vấn gộp như thế nào. Cập nhật ngay khi thay đổi Group by và Measures.",
                        size="xs",
                        c="dimmed",
                        mb="xs",
                    ),
                    html.Div(
                        id="wizard-grouped-sql-container",
                        children=code_block(grouped_sql, language="sql"),
                    ),
                ],
            ),
        ]
    )


def render_step_4(
    config: dict[str, Any],
    sample_data: dict[str, Any] | None = None,
    active_profile_code: str | None = None,
) -> Any:
    """Dựng giao diện Bước 4: Hồ sơ đối soát (Profile so sánh) & Measures."""
    profiles = config.get("profiles", [])
    if not profiles or (len(profiles) == 1 and profiles[0].get("code") == "BY_DEFAULT"):
        profiles = _build_default_profiles_from_fields(config.get("fields", []), config.get("derived", []))
        config["profiles"] = profiles

    active_prof = None
    if active_profile_code:
        active_prof = next((p for p in profiles if p.get("code") == active_profile_code), None)
    if not active_prof:
        active_prof = profiles[0]

    current_prof_code = active_prof.get("code", "BY_INVOICE")

    # Danh sách trường có sẵn: chỉ trường đã map cột DB ở Bước 3 (xem
    # _mapped_fields_info), không phải mọi trường ở Bước 2.
    avail_fields_info = _mapped_fields_info(config)

    avail_field_names = [f["name"] for f in avail_fields_info]

    # Tab items cho profile
    tab_list = [
        dmc.TabsTab(p.get("name", p.get("code", "Profile")), value=p.get("code", "BY_INVOICE")) for p in profiles
    ]

    return html.Div(
        [
            # Profile tabs
            dmc.Tabs(
                id="wizard-profile-tabs",
                value=current_prof_code,
                mb="md",
                children=[
                    dmc.TabsList(
                        id="wizard-profile-tabs-list",
                        children=[
                            *tab_list,
                            button_subtle("Thêm profile", id="wizard-add-profile-btn", icon="lucide:plus", size="xs"),
                        ],
                    )
                ],
            ),
            # Layout 2 cột: Cột trái Trường có sẵn vs Cột phải Cấu hình profile
            dmc.Grid(
                gutter="md",
                children=[
                    # Cột trái: Trường có sẵn, dính ở đầu trang và cuộn
                    # riêng để vẫn nhìn thấy khi cuộn cột phải xuống SQL.
                    dmc.GridCol(
                        span=4,
                        style={"position": "sticky", "top": 16, "alignSelf": "flex-start"},
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            style={"maxHeight": "calc(100vh - 32px)", "overflowY": "auto"},
                            children=[
                                dmc.Title("Trường có sẵn", order=4, mb="xs"),
                                dmc.Text(
                                    "Chỉ các trường đã map cột DB ở Bước 3 (trường dẫn xuất tính từ trường đã map cũng được tính). Dòng dưới mỗi trường là mapping Excel → DB. Chìa khóa / sigma tô đậm khi trường đang dùng ở profile đang xem.",
                                    size="xs",
                                    c="dimmed",
                                    mb="sm",
                                ),
                                html.Div(
                                    id="wizard-step4-left-fields",
                                    children=_render_step_4_left_fields(
                                        avail_fields_info,
                                        active_prof.get("group_by", []),
                                        [
                                            m.get("field")
                                            for m in active_prof.get("measures", [])
                                            if isinstance(m, dict)
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    ),
                    # Cột phải: Group by, Measures & SQL gộp
                    dmc.GridCol(
                        span=8,
                        children=html.Div(
                            id="wizard-step4-right-content",
                            children=_render_step_4_right_panel(active_prof, avail_field_names, config, sample_data),
                        ),
                    ),
                ],
            ),
        ]
    )


def validate_dry_run_params(p_from_str: Any, p_to_str: Any) -> str | None:
    """Kiểm tra hợp lệ khoảng thời gian: p_from và p_to phải có định dạng hợp lệ và p_from <= p_to."""
    if not p_from_str or not p_to_str:
        return "Vui lòng nhập đầy đủ Từ ngày giờ và Đến ngày giờ."
    try:
        f_clean = str(p_from_str).strip().replace(" ", "T")
        t_clean = str(p_to_str).strip().replace(" ", "T")
        dt_from = datetime.fromisoformat(f_clean)
        dt_to = datetime.fromisoformat(t_clean)
        if dt_from > dt_to:
            return "Đến ngày giờ phải lớn hơn hoặc bằng Từ ngày giờ."
    except Exception:
        return "Định dạng ngày giờ không hợp lệ. Ví dụ: 2026-02-01 00:00:00."
    return None


def render_step_5(
    config: dict[str, Any],
    dry_run_data: dict[str, Any] | None = None,
) -> Any:
    """Dựng giao diện Bước 5: Dry-run trên file mẫu & Kích hoạt."""
    summary = dry_run_data.get("summary", {}) if dry_run_data else {}
    grain_warnings = dry_run_data.get("grain_warnings", []) if dry_run_data else []
    has_dry_run = bool(dry_run_data and dry_run_data.get("dry_run_ok"))
    dry_error = (dry_run_data or {}).get("error")
    dry_message = (dry_run_data or {}).get("message")
    # Timeline trạng thái: lấy từ store nên sống qua lần render lại Bước 5.
    # Nếu chỉ hiện lỗi qua ô lỗi riêng, render lại sẽ dựng lại ô đó trống
    # và lỗi biến mất, đúng như lỗi người dùng vừa gặp ở bước dry-run thật.
    stage_order = [s for s, _ in DRY_RUN_STAGES]
    failed_idx = (
        stage_order.index((dry_run_data or {}).get("stage")) if (dry_run_data or {}).get("stage") in stage_order else -1
    )
    timeline_badges = []
    for idx, (_stage, label) in enumerate(DRY_RUN_STAGES):
        if has_dry_run:
            badge_color, badge_text = "green", f"✓ {label}"
        elif failed_idx >= 0 and idx < failed_idx:
            badge_color, badge_text = "green", f"✓ {label}"
        elif failed_idx >= 0 and idx == failed_idx:
            badge_color, badge_text = "red", f"✗ {label}"
        else:
            badge_color, badge_text = "gray", f"○ {label}"
        timeline_badges.append(dmc.Badge(badge_text, size="sm", variant="light", color=badge_color))
    timeline = dmc.Paper(
        withBorder=True,
        p="sm",
        radius="sm",
        mb="md",
        children=[
            dmc.Text("Tiến trình Dry-run", fw=600, size="sm", mb="xs"),
            dmc.Group(timeline_badges, gap="xs"),
            (
                alert_box(f"Lỗi ở {(dry_run_data or {}).get('stage_label', 'Dry-run')}: {dry_error}", tone="crit")
                if dry_error
                else alert_box(dry_message, tone="ok")
                if dry_message
                else dmc.Text(
                    "Chưa bấm 'Chạy thử'. Chạy thử truy vấn Oracle thật nên có thể mất vài chục giây, đừng bấm lại liên tục, chờ kết quả hiện ở dưới.",
                    size="xs",
                    c="dimmed",
                )
            ),
        ],
    )

    if "CONTROL_TOTAL_DIFF" in summary:
        ct_diff = summary.get("CONTROL_TOTAL_DIFF", 0)
        ct_ok = ct_diff == 0
        ct_val = "Khớp" if ct_ok else f"Lệch ({ct_diff:,.0f} đ)"
        ct_tone = "ok" if ct_ok else "warn"
        ct_meta = "Chênh lệch control total theo kết quả Dry-run thật."
    else:
        ct_val = "Chưa chạy"
        ct_tone = "primary"
        ct_meta = "Chưa chạy Dry-run, chưa có số liệu thật."
    excel_groups = summary.get("EXCEL_GROUPS", "—")
    db_groups = summary.get("DB_GROUPS", "—")
    cnt_matched = summary.get("CNT_MATCHED", "—")
    duration_val = f"{summary['DURATION_SECONDS']:.1f} giây" if "DURATION_SECONDS" in summary else "—"

    warning_alerts = [alert_box(w, tone="warn") for w in grain_warnings]

    p_from_val = (dry_run_data.get("p_from") if dry_run_data else None) or None
    p_to_val = (dry_run_data.get("p_to") if dry_run_data else None) or None
    p_org_default_val = ""
    for p in (config or {}).get("db_source", {}).get("params", []) or []:
        if isinstance(p, dict) and p.get("name") == "p_org" and p.get("default"):
            p_org_default_val = str(p.get("default"))
            break
    p_org_val = (dry_run_data.get("p_org") if dry_run_data else None) or p_org_default_val
    p_org_required_val = _p_org_required(config)

    return html.Div(
        [
            timeline,
            # Card 1: Form tham số dry-run
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                mb="md",
                children=[
                    dmc.Title("Dry-run trên file mẫu", order=4, mb="xs"),
                    dmc.Text(
                        "Chạy thử nghiệm trên file mẫu và nguồn DB Oracle để xác thực kết quả đối soát trước khi kích hoạt.",
                        size="sm",
                        c="dimmed",
                        mb="md",
                    ),
                    dmc.Grid(
                        gutter="md",
                        children=[
                            dmc.GridCol(
                                span=4,
                                children=dmc.DateTimePicker(
                                    id="wizard-dry-p-from",
                                    label="Từ ngày giờ *",
                                    value=p_from_val,
                                    valueFormat="YYYY-MM-DD HH:mm:ss",
                                    withSeconds=True,
                                    clearable=False,
                                    w="100%",
                                    required=True,
                                ),
                            ),
                            dmc.GridCol(
                                span=4,
                                children=dmc.DateTimePicker(
                                    id="wizard-dry-p-to",
                                    label="Đến ngày giờ *",
                                    value=p_to_val,
                                    valueFormat="YYYY-MM-DD HH:mm:ss",
                                    withSeconds=True,
                                    clearable=False,
                                    w="100%",
                                    required=True,
                                ),
                            ),
                            dmc.GridCol(
                                span=4,
                                children=dmc.TextInput(
                                    id="wizard-dry-p-org",
                                    label="Mã đơn vị (p_org) *" if p_org_required_val else "Mã đơn vị (p_org)",
                                    value=p_org_val,
                                    placeholder="Bắt buộc vì SQL dùng :p_org, ví dụ BDP"
                                    if p_org_required_val
                                    else "Để trống nếu không lọc",
                                    className="mono",
                                ),
                            ),
                        ],
                    ),
                    dmc.Group(
                        [
                            button_primary("Chạy thử", id="wizard-run-dry-btn"),
                        ],
                        mt="md",
                    ),
                    dcc.Loading(
                        children=dmc.Box(
                            id="wizard-dry-run-error",
                            children=(
                                alert_box(
                                    f"Lỗi ở {(dry_run_data or {}).get('stage_label', 'Dry-run')}: {dry_error}",
                                    tone="crit",
                                )
                                if dry_error
                                else alert_box(dry_message, tone="ok")
                                if dry_message
                                else None
                            ),
                            mt="sm",
                        ),
                        type="dots",
                    ),
                ],
            ),
            # Alert phạm vi dữ liệu
            alert_box(
                "Dry-run chạy thật trên file mẫu đã tải và nguồn DB, không ghi lịch sử chạy. "
                "Chưa bấm 'Chạy thử' thì các KPI dưới đây chưa có số liệu thật.",
                tone="info",
            ),
            *([html.Div(warning_alerts, style={"marginTop": 12})] if warning_alerts else []),
            # Card 2: 4 KPI Cards kết quả Dry-run
            dmc.Grid(
                gutter="md",
                mt="md",
                children=[
                    dmc.GridCol(
                        span=3,
                        children=kpi_card(
                            label="Control total",
                            value=ct_val,
                            tone=ct_tone,
                            meta=ct_meta,
                            icon="lucide:check-circle-2",
                        ),
                    ),
                    dmc.GridCol(
                        span=3,
                        children=kpi_card(
                            label="Nhóm Excel / DB",
                            value=f"{excel_groups} / {db_groups}",
                            tone="primary",
                            meta="Theo kết quả Dry-run thật." if has_dry_run else "Chưa chạy Dry-run.",
                            icon="lucide:layers",
                        ),
                    ),
                    dmc.GridCol(
                        span=3,
                        children=kpi_card(
                            label="Khớp",
                            value=str(cnt_matched),
                            tone="ok",
                            meta="Theo kết quả Dry-run thật." if has_dry_run else "Chưa chạy Dry-run.",
                            icon="lucide:check-check",
                        ),
                    ),
                    dmc.GridCol(
                        span=3,
                        children=kpi_card(
                            label="Thời gian",
                            value=duration_val,
                            tone="primary",
                            meta="Theo kết quả Dry-run thật." if has_dry_run else "Chưa chạy Dry-run.",
                            icon="lucide:clock",
                        ),
                    ),
                ],
            ),
            # Card 3: Sẵn sàng kích hoạt
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                mt="md",
                children=[
                    dmc.Group(
                        [
                            dmc.ThemeIcon(
                                DashIconify(icon="lucide:badge-check", width=22),
                                color="teal",
                                variant="light",
                                size="lg",
                                radius="md",
                            ),
                            dmc.Stack(
                                [
                                    dmc.Text(
                                        "Sẵn sàng kích hoạt phiên bản" if has_dry_run else "Chưa sẵn sàng kích hoạt",
                                        fw=600,
                                        size="sm",
                                    ),
                                    dmc.Text(
                                        "Dry-run thật đã thành công. Nhấn nút 'Lưu & kích hoạt' bên dưới "
                                        "để ban hành phiên bản này."
                                        if has_dry_run
                                        else "Cần bấm 'Chạy thử' và chờ Dry-run thật thành công trước khi "
                                        "kích hoạt. Nút 'Lưu & kích hoạt' sẽ báo lý do nếu chưa đạt.",
                                        size="xs",
                                        c="dimmed",
                                    ),
                                ],
                                gap=2,
                            ),
                        ],
                        gap="md",
                    )
                ],
            ),
        ]
    )


def render_diagrams_tab(config: dict[str, Any]) -> Any:
    """Dựng giao diện tab Sơ đồ diễn giải (Screen04-TemplateDiagram) với 5 sơ đồ Mermaid."""
    try:
        cfg_obj = TemplateConfig.model_validate(config)
        diagrams = generate_all_diagrams(cfg_obj)
    except Exception:
        cfg_obj = TemplateConfig.model_validate(build_default_config())
        diagrams = generate_all_diagrams(cfg_obj)

    diagram_cards = [
        (
            "1. Quy trình tổng quan 6 giai đoạn",
            "Luồng xử lý xuyên suốt từ tập tin Excel thô, qua chuẩn hóa, tính phái sinh, đối soát DB đến kết quả.",
            diagrams["pipeline"],
            "copy-diag-pipeline",
        ),
        (
            "2. Chuẩn hóa & Ánh xạ trường logic",
            "Quy tắc làm sạch chuỗi, ép kiểu dữ liệu và chuyển đổi cột Excel sang các trường logic dùng chung.",
            diagrams["normalization"],
            "copy-diag-norm",
        ),
        (
            "3. Truy vấn DB & Điều kiện lọc thời gian",
            "Mệnh đề SELECT, bind parameter (:p_from, :p_to) và các điều kiện lọc tĩnh áp dụng cho nguồn Oracle.",
            diagrams["db_query"],
            "copy-diag-db",
        ),
        (
            "4. Phân cấp Profile & Nhóm đối soát",
            "Cấu trúc nhóm Group by và các hàm tổng hợp Measure (SUM, COUNT) định nghĩa cho từng Profile.",
            diagrams["profiles"],
            "copy-diag-prof",
        ),
        (
            "5. Quy tắc Kiểm soát tổng (Control Total)",
            "Công thức so khớp tổng đối soát nhanh cấp tập tin trước khi đi sâu vào so sánh từng nhóm chi tiết.",
            diagrams["control_total"],
            "copy-diag-ct",
        ),
    ]

    cards_ui = []
    for title, desc, mermaid_code, _copy_id in diagram_cards:
        cards_ui.append(
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                mb="lg",
                children=[
                    dmc.Group(
                        justify="space-between",
                        align="flex-start",
                        mb="xs",
                        children=[
                            html.Div(
                                [
                                    dmc.Title(title, order=4),
                                    dmc.Text(desc, size="sm", c="dimmed", mt=2),
                                ]
                            ),
                            dcc.Clipboard(
                                content=mermaid_code,
                                title="Sao chép mã Mermaid",
                                style={
                                    "display": "inline-block",
                                    "padding": "6px 12px",
                                    "fontSize": "13px",
                                    "cursor": "pointer",
                                    "border": "1px solid var(--border-subtle, #e2e8f0)",
                                    "borderRadius": "4px",
                                    "background": "var(--bg-surface, #ffffff)",
                                },
                            ),
                        ],
                    ),
                    html.Div(
                        html.Pre(mermaid_code, className="mermaid", style={"margin": "16px 0", "textAlign": "center"}),
                        style={
                            "background": "var(--bg-subtle, #f8fafc)",
                            "borderRadius": "6px",
                            "padding": "16px",
                            "overflowX": "auto",
                        },
                    ),
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                [
                                    dmc.AccordionControl("Xem mã nguồn Mermaid"),
                                    dmc.AccordionPanel(code_block(mermaid_code, language="text")),
                                ],
                                value="code",
                            )
                        ],
                        styles={"item": {"border": "none"}},
                    ),
                ],
            )
        )

    return html.Div(cards_ui)


try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path_template="/templates/<template_id>/edit",
        path="/templates/new",
        title="Đăng ký template — ReconHub",
    )
except Exception:
    pass


def map_validation_errors(exc: ValidationError) -> dict[str, str]:
    """Chuyển đổi lỗi Pydantic ValidationError thành dictionary ánh xạ path -> thông báo tiếng Việt."""
    error_map: dict[str, str] = {}
    for err in exc.errors():
        loc_parts = [str(p) for p in err.get("loc", [])]
        path_key = ".".join(loc_parts)
        msg = err.get("msg", "Giá trị không hợp lệ")
        # Chuẩn hóa một số thông báo phổ biến
        if "Field required" in msg:
            msg = "Trường này là bắt buộc"
        elif "string_pattern_mismatch" in msg:
            msg = "Định dạng không đúng quy tắc"
        error_map[path_key] = msg
    return error_map


def config_to_form_state(cfg: TemplateConfig) -> dict[str, Any]:
    """Chuyển đổi cấu hình TemplateConfig thành dictionary state cho form wizard."""
    return cfg.model_dump(mode="json")


def form_state_to_config(form_data: dict[str, Any]) -> tuple[TemplateConfig | None, dict[str, str]]:
    """Chuyển đổi dictionary state thành TemplateConfig Pydantic model có kiểm tra validation."""
    try:
        cfg = TemplateConfig.model_validate(form_data)
        return cfg, {}
    except ValidationError as exc:
        return None, map_validation_errors(exc)
    except Exception as exc:
        return None, {"_root": f"Lỗi không xác định: {exc}"}


def _lookup_ds_name_by_id(ds_id: int) -> str | None:
    try:
        from sqlalchemy import select

        from app.db.engine import get_recon_engine
        from app.db.metadata import recon_data_source

        engine = get_recon_engine()
        with engine.connect() as conn:
            row = conn.execute(select(recon_data_source.c.NAME).where(recon_data_source.c.ID == ds_id)).scalar()
            return str(row) if row else None
    except Exception:
        return None


def _load_sample_file_data(file_id: int | None) -> dict[str, Any] | None:
    if not file_id:
        return None
    try:
        from sqlalchemy import select

        from app.db.engine import get_recon_engine
        from app.db.metadata import recon_file
        from app.engine.inspect import inspect_sample
        from app.engine.reader import read_sheet
        from app.schemas.template_config import FileSpec

        engine = get_recon_engine()
        with engine.connect() as conn:
            row = conn.execute(select(recon_file).where(recon_file.c.ID == file_id)).mappings().first()
            if not row:
                return None
            storage_path_str = row["STORAGE_PATH"]
            original_name = str(row["ORIGINAL_NAME"])
            if storage_path_str and Path(storage_path_str).exists():
                sp = Path(storage_path_str)
                inspect_res = inspect_sample(sp)
                preview_rows: list[dict[str, Any]] = []
                try:
                    spec = FileSpec(sheet=inspect_res.sheet, header_row=1, data_start_row=2)
                    raw_df, _ = read_sheet(sp, spec)
                    df_head = raw_df.head(5)
                    cols = [c for c in df_head.columns if c != "__row_no"]
                    preview_rows = df_head.select(cols).to_dicts()
                except Exception:
                    dummy_row: dict[str, Any] = {}
                    for c in inspect_res.columns:
                        dummy_row[c.name] = c.sample_values[0] if c.sample_values else ""
                    preview_rows = [dummy_row] if dummy_row else []

                return {
                    "filename": original_name,
                    "storage_path": str(sp),
                    "file_id": file_id,
                    "sheet": inspect_res.sheet,
                    "sheets": inspect_res.sheets,
                    "total_rows": inspect_res.total_rows,
                    "total_cols": inspect_res.total_cols,
                    "candidate_total_rows": [tr.model_dump() for tr in inspect_res.candidate_total_rows],
                    "columns": [c.model_dump() for c in inspect_res.columns],
                    "preview_rows": preview_rows,
                }
            else:
                return {
                    "filename": original_name,
                    "storage_path": storage_path_str,
                    "file_id": file_id,
                    "sheet": "",
                    "sheets": [],
                    "total_rows": 0,
                    "total_cols": 0,
                    "candidate_total_rows": [],
                    "columns": [],
                    "preview_rows": [],
                }
    except Exception:
        return None


def build_default_config() -> dict[str, Any]:
    """Tạo cấu hình template mặc định để khởi tạo wizard mới."""
    return {
        "schema_version": 1,
        "file": {
            "sheet": "",
            "header_row": 1,
            "data_start_row": 2,
            "skip_footer_rows": 0,
            "detect_by_headers": [],
            "row_filters": {"drop_if": [], "keep_if": []},
            "thousand_sep": ",",
            "decimal_sep": ".",
        },
        "fields": [],
        "derived": [],
        "db_source": {
            "kind": "table",
            "table": "",
            "filters": [
                {"param": "p_from", "column": "", "op": ">=", "cast": "none"},
                {"param": "p_to", "column": "", "op": "<=", "cast": "none"},
            ],
            "static_where": [],
            "sql": None,
            "params": [
                {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ ngày giờ", "required": True},
                {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến ngày giờ", "required": True},
            ],
            "pushdown_aggregate": True,
        },
        "time_filter": None,
        "control_total": None,
        "profiles": [
            {
                "code": "PROFILE_1",
                "name": "Profile 1",
                "is_default": True,
                "aggregate": True,
                "group_by": [],
                "measures": [],
                "filters": [],
                "main_measure": None,
            }
        ],
    }


def _config_hash(cfg: dict[str, Any] | None) -> str:
    """Hash cấu hình để biết Dry-run có còn khớp với cấu hình hiện tại không."""
    try:
        raw = json.dumps(cfg or {}, sort_keys=True, default=str)
    except Exception:
        raw = str(cfg)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_wizard_step(
    cfg: dict[str, Any] | None,
    step_index: int,
    sample_data: dict[str, Any] | None = None,
) -> list[str]:
    """Validate từng bước wizard, trả về danh sách lỗi (rỗng là đạt).

    Chỉ kiểm tra những gì bước đó phải có, để lỗi lộ ngay khi bấm Tiếp
    thay vì dồn đến bước kích hoạt. Không tự chèn giá trị mặc định.
    """
    cfg = cfg or {}
    errors: list[str] = []
    if step_index == 0:
        code = (cfg.get("template_code") or "").strip()
        name = (cfg.get("name") or cfg.get("template_name") or "").strip()
        if not code or code == "NEW_TEMPLATE":
            errors.append("Bước 1: chưa nhập mã template.")
        if not name:
            errors.append("Bước 1: chưa nhập tên template.")
        if not cfg.get("fields"):
            errors.append("Bước 1: chưa tải file mẫu, chưa có trường nào.")
    elif step_index == 1:
        fields = cfg.get("fields", []) or []
        if not fields:
            errors.append("Bước 2: chưa có trường nào.")
        seen: set[str] = set()
        for f in fields:
            fname = (f.get("name") or "").strip()
            if not fname:
                errors.append("Bước 2: có trường chưa nhập tên trường logic.")
            elif fname in seen:
                errors.append(f"Bước 2: trùng tên trường logic '{fname}'.")
            else:
                seen.add(fname)
        if fields and not any(f.get("excel") for f in fields):
            errors.append("Bước 2: chưa tick Dùng cho trường nào.")
    elif step_index == 2:
        db_spec = cfg.get("db_source", {}) or {}
        if not db_spec.get("source_id"):
            errors.append("Bước 3: chưa chọn Data Source.")
        if db_spec.get("kind", "table") == "table":
            if not db_spec.get("table"):
                errors.append("Bước 3: chưa chọn bảng/view nguồn.")
            filters = {f.get("param"): f.get("column") for f in db_spec.get("filters", []) if isinstance(f, dict)}
            if not filters.get("p_from"):
                errors.append("Bước 3: chưa chọn cột DB cho Từ ngày giờ (p_from).")
            if not filters.get("p_to"):
                errors.append("Bước 3: chưa chọn cột DB cho Đến ngày giờ (p_to).")
        else:
            if not db_spec.get("sql"):
                errors.append("Bước 3: chưa nhập câu lệnh SQL nguồn.")
            else:
                sql_text = str(db_spec.get("sql") or "")
                if ":p_from" not in sql_text:
                    errors.append("Bước 3: SQL nguồn bắt buộc phải dùng :p_from.")
                if ":p_to" not in sql_text:
                    errors.append("Bước 3: SQL nguồn bắt buộc phải dùng :p_to.")
    elif step_index == 3:
        profiles = cfg.get("profiles", []) or []
        if not profiles:
            errors.append("Bước 4: chưa có profile nào.")
        mapped = {f["name"] for f in _mapped_fields_info(cfg)}
        for prof in profiles:
            if not prof.get("group_by"):
                errors.append(f"Bước 4: profile '{prof.get('code', '')}' chưa chọn Group by.")
            if not prof.get("measures"):
                errors.append(f"Bước 4: profile '{prof.get('code', '')}' chưa có measure nào.")
            for g in prof.get("group_by", []) or []:
                if g not in mapped:
                    errors.append(
                        f"Bước 4: Group by '{g}' của profile '{prof.get('code', '')}' chưa map cột DB ở Bước 3."
                    )
            for m in prof.get("measures", []) or []:
                mf = (m or {}).get("field")
                if mf and mf != "*" and mf not in mapped:
                    errors.append(
                        f"Bước 4: measure '{(m or {}).get('name', '')}' dùng trường '{mf}' chưa map cột DB ở Bước 3."
                    )
    return errors


def layout(template_id: str | int | None = None, **kwargs: Any) -> Any:
    """Layout chính màn hình Wizard Đăng ký & Sửa Template (Screen03 & Screen04)."""
    ctx = get_current_ctx()
    allowed_roles = {Role.ADMIN, Role.TEMPLATE_OWNER}
    if ctx is None or not (allowed_roles & set(ctx.roles)):
        return html.Div(
            [
                dcc.Location(id="wizard-forbidden-redirect", href="/forbidden"),
                alert_box("Bạn không có quyền truy cập trang đăng ký hoặc sửa template.", tone="crit"),
            ]
        )

    # Nạp cấu hình nếu có template_id
    initial_config = build_default_config()
    loaded_version = 1
    t_id_num: int | None = None
    t_code = "NEW_TEMPLATE"
    t_name = ""
    row_ver = 1
    is_editing = False
    initial_sample_data: dict[str, Any] | None = None
    sample_file_id_val: int | None = None

    if template_id and str(template_id).strip().lower() != "new":
        tmpl_res = get_template(ctx, template_id)
        if tmpl_res.ok and tmpl_res.data:
            tmpl_data = tmpl_res.data
            t_id_num = tmpl_data.get("id")
            t_code = tmpl_data.get("code") or str(template_id).strip().upper()
            t_name = tmpl_data.get("name") or ""
            row_ver = tmpl_data.get("row_version") or 1
            loaded_version = tmpl_data.get("current_version") or 1
            is_editing = True
            sample_file_id_val = tmpl_data.get("sample_file_id")
            if sample_file_id_val:
                initial_sample_data = _load_sample_file_data(sample_file_id_val)

            saved_cfg = tmpl_data.get("config")
            if isinstance(saved_cfg, dict):
                initial_config = dict(saved_cfg)
            initial_config["template_code"] = t_code
            initial_config["template_name"] = t_name
            initial_config["name"] = t_name

            # Bổ sung tên data source nếu có
            ds_id = tmpl_data.get("data_source_id")
            if ds_id and not initial_config.get("db_source", {}).get("source_id"):
                ds_name_found = _lookup_ds_name_by_id(ds_id)
                if ds_name_found:
                    initial_config.setdefault("db_source", {})["source_id"] = ds_name_found

    t_code = initial_config.get("template_code") or t_code
    ds_name = initial_config.get("db_source", {}).get("source_id", "—")
    tb_name = initial_config.get("db_source", {}).get("table", "—")
    subtitle_text = f"Bản nháp v{loaded_version} · Data Source {ds_name} · Bảng {tb_name}"
    header_title_text = f"Sửa template: {t_code}" if is_editing else f"Đăng ký template: {t_code}"
    initial_active_prof_code = (
        initial_config.get("profiles", [{}])[0].get("code", "PROFILE_1")
        if initial_config.get("profiles")
        else "PROFILE_1"
    )

    return html.Div(
        id="wizard-page-root",
        children=[
            # Stores
            dcc.Store(id="wizard-config-store", data=initial_config),
            dcc.Store(
                id="wizard-meta-store",
                data={
                    "template_id": t_id_num,
                    "template_code": t_code,
                    "template_name": t_name,
                    "row_version": row_ver,
                    "version": loaded_version,
                    "is_editing": is_editing,
                    "current_step": 1,
                    "is_dirty": False,
                    "last_saved_config_hash": _config_hash(initial_config) if is_editing else None,
                    "last_saved_at": None,
                    "sample_file_id": sample_file_id_val,
                },
            ),
            dcc.Store(id="wizard-dry-run-store", data=None),
            dcc.Store(id="wizard-sample-file-store", data=initial_sample_data),
            dcc.Store(id="wizard-active-profile-store", data=initial_active_prof_code),
            dcc.Location(id="wizard-redirect-location", refresh=True),
            dcc.Interval(id="wizard-autosave-interval", interval=15000, n_intervals=0),
            # Header
            dmc.Group(
                justify="space-between",
                align="flex-start",
                mb="md",
                children=[
                    html.Div(
                        [
                            dmc.Title(
                                header_title_text,
                                id="wizard-header-title",
                                order=2,
                                fw=700,
                            ),
                            dmc.Text(
                                subtitle_text,
                                id="wizard-header-subtitle",
                                size="sm",
                                c="dimmed",
                                mt=4,
                            ),
                        ]
                    ),
                    dmc.SegmentedControl(
                        id="wizard-view-tabs",
                        value="config",
                        data=[
                            {"label": "Cấu hình template", "value": "config"},
                            {"label": "Sơ đồ diễn giải", "value": "diagram"},
                        ],
                        radius="sm",
                    ),
                ],
            ),
            # Stepper 5 bước (hiển thị khi ở tab Cấu hình)
            html.Div(
                id="wizard-stepper-box",
                children=dmc.Stepper(
                    id="wizard-stepper",
                    active=0,
                    mb="lg",
                    children=[
                        dmc.StepperStep(label="File mẫu", description="Upload & cấu trúc"),
                        dmc.StepperStep(label="Định nghĩa trường", description="Chuẩn hóa & ánh xạ"),
                        dmc.StepperStep(label="Nguồn DB", description="Oracle & điều kiện lọc"),
                        dmc.StepperStep(label="Profile so sánh", description="Group by & measures"),
                        dmc.StepperStep(label="Dry-run", description="Chạy thử & kích hoạt"),
                    ],
                ),
            ),
            # Content container: Step content hoặc Diagram content
            html.Div(id="wizard-step-content", children=html.Div("Đang tải dữ liệu...")),
            html.Div(id="wizard-diagram-content", style={"display": "none"}),
            # Error alert container
            dmc.Box(id="wizard-error-alert-container", mt="md"),
            # Footer Navigation
            dmc.Group(
                id="wizard-footer-nav",
                justify="space-between",
                mt="xl",
                children=[
                    button_subtle("Quay lại", id="wizard-prev-btn", disabled=True),
                    dmc.Group(
                        [
                            button_subtle("Lưu nháp", id="wizard-save-draft-btn"),
                            button_primary("Tiếp", id="wizard-next-btn"),
                        ],
                        gap="sm",
                    ),
                ],
            ),
            # Notification container
            html.Div(id="wizard-notification-container"),
        ],
        style={"padding": "24px"},
    )


# Callbacks cơ bản cho Bước 1


@callback(
    Output("wizard-step-content", "children"),
    Input("wizard-stepper", "active"),
    Input("wizard-dry-run-store", "data"),
    Input("wizard-sample-file-store", "data"),
    State("wizard-config-store", "data"),
)
def handle_render_step_content(
    active_step: int,
    dry_run_data: dict[str, Any] | None,
    sample_file_data: dict[str, Any] | None,
    config_data: dict[str, Any] | None,
) -> Any:
    """Hiển thị nội dung tương ứng theo bước hiện tại trên Stepper."""
    cfg = config_data or {}
    if active_step == 0:
        return render_step_1(cfg, sample_data=sample_file_data)
    elif active_step == 1:
        return render_step_2(cfg)
    elif active_step == 2:
        return render_step_3(cfg)
    elif active_step == 3:
        return render_step_4(cfg, sample_data=sample_file_data)
    elif active_step == 4:
        return render_step_5(cfg, dry_run_data=dry_run_data)
    return html.Div("Bước không xác định")


@callback(
    Output("wizard-sample-file-store", "data"),
    Output("wizard-config-store", "data", allow_duplicate=True),
    Output("wizard-error-alert-container", "children", allow_duplicate=True),
    Output("wizard-notification-container", "children", allow_duplicate=True),
    Input("wizard-file-drop", "contents"),
    State("wizard-file-drop", "filename"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_wizard_file_upload(
    contents: str | None,
    filename: str | None,
    current_config: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any]:
    """Xử lý kéo thả upload file mẫu ở Bước 1, phân tích cấu trúc và gợi ý trường."""
    if not contents or not filename:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    ctx = get_current_ctx()
    if ctx is None:
        err = alert_box("Phiên làm việc đã hết hạn hoặc bạn chưa đăng nhập.", tone="crit")
        return dash.no_update, dash.no_update, err, dash.no_update

    # 1. Tách chuỗi base64 và giải mã
    if "," in contents:
        _, content_str = contents.split(",", 1)
    else:
        content_str = contents
    try:
        content_bytes = base64.b64decode(content_str)
    except Exception as exc:
        err = alert_box(f"Không thể giải mã dữ liệu file: {exc}", tone="crit")
        return dash.no_update, dash.no_update, err, dash.no_update

    # 2. Upload và lưu vào RECON_STORAGE
    upload_res = upload_file(ctx, filename=filename, content=content_bytes)
    if not upload_res.ok or not upload_res.data:
        err = alert_box(upload_res.message or "Lỗi khi lưu trữ file tải lên.", tone="crit")
        return dash.no_update, dash.no_update, err, dash.no_update

    storage_path = Path(upload_res.data["storage_path"])

    # 3. Phân tích cấu trúc file (inspect)
    try:
        inspect_res = inspect_sample(storage_path)
    except Exception as exc:
        err = alert_box(f"Lỗi khi đọc và phân tích cấu trúc file: {exc}", tone="crit")
        return dash.no_update, dash.no_update, err, dash.no_update

    # 4. Đọc 5 dòng xem trước
    preview_rows: list[dict[str, Any]] = []
    try:
        spec = FileSpec(sheet=inspect_res.sheet, header_row=1, data_start_row=2)
        raw_df, _ = read_sheet(storage_path, spec)
        df_head = raw_df.head(5)
        cols = [c for c in df_head.columns if c != "__row_no"]
        preview_rows = df_head.select(cols).to_dicts()
    except Exception:
        dummy_row: dict[str, Any] = {}
        for c in inspect_res.columns:
            dummy_row[c.name] = c.sample_values[0] if c.sample_values else ""
        preview_rows = [dummy_row]

    # 5. Cập nhật cấu hình config
    cfg = dict(current_config or build_default_config())
    cfg.setdefault("file", {})
    cfg["file"]["sheet"] = inspect_res.sheet
    cfg["file"]["header_row"] = 1
    cfg["file"]["data_start_row"] = 2

    # Lấy các cột ứng viên làm header nhận diện file
    cand_keys = [c.name for c in inspect_res.columns if c.is_candidate_key]
    if cand_keys:
        cfg["file"]["detect_by_headers"] = cand_keys[:3]
    else:
        cfg["file"]["detect_by_headers"] = [c.name for c in inspect_res.columns[:3]]

    # Gợi ý danh sách trường logic ở Bước 2. Upload lại không xóa sạch
    # sửa tay: giữ lại tên/nhãn/kiểu/norm/db của trường cũ khớp theo cột Excel,
    # và giữ lại profile cũ nếu group_by/measure vẫn còn trường đó.
    old_fields_by_excel = {
        f.get("excel"): f for f in (current_config or {}).get("fields", []) if isinstance(f, dict) and f.get("excel")
    }
    suggested_fields = []
    for col in inspect_res.columns:
        norm_rules: list[str] = []
        if col.suggested_type == "text":
            norm_rules.append("strip")
        elif col.suggested_type == "number":
            norm_rules.append("round_2")

        sample_v = col.sample_values[0] if col.sample_values else "—"
        new_field = {
            "name": col.suggested_field_name,
            "label": col.name,
            "excel": col.name,
            "excel_aliases": [],
            "db": col.suggested_field_name,
            "type": col.suggested_type,
            "format": None,
            "norm": norm_rules,
            "required": False,
            "sample_value": sample_v,
        }
        old_field = old_fields_by_excel.get(col.name)
        if old_field:
            for key in ("name", "label", "type", "norm", "db"):
                if old_field.get(key) is not None:
                    new_field[key] = old_field[key]
        suggested_fields.append(new_field)
    cfg["fields"] = suggested_fields
    old_profiles = (current_config or {}).get("profiles", []) or []
    new_field_names = {f.get("name") for f in suggested_fields}
    profiles_kept = False
    if old_profiles:
        profiles_kept = True
        for prof in old_profiles:
            if not prof.get("group_by") or not all(g in new_field_names for g in prof.get("group_by", [])):
                profiles_kept = False
            for m in prof.get("measures", []):
                if m.get("field") and m.get("field") not in new_field_names:
                    profiles_kept = False
    cfg["profiles"] = (
        old_profiles if profiles_kept else _build_default_profiles_from_fields(suggested_fields, cfg.get("derived", []))
    )

    if inspect_res.candidate_total_rows:
        cfg["file"]["skip_footer_rows"] = len(inspect_res.candidate_total_rows)

    sample_file_data = {
        "filename": filename,
        "storage_path": str(storage_path),
        "file_id": upload_res.data.get("id"),
        "sheet": inspect_res.sheet,
        "sheets": inspect_res.sheets,
        "total_rows": inspect_res.total_rows,
        "total_cols": inspect_res.total_cols,
        "candidate_total_rows": [tr.model_dump() for tr in inspect_res.candidate_total_rows],
        "columns": [c.model_dump() for c in inspect_res.columns],
        "preview_rows": preview_rows,
    }

    success_notif = alert_box(
        f"Đã nạp file '{filename}' thành công: {inspect_res.total_cols} cột, {inspect_res.total_rows} dòng.",
        tone="ok",
    )
    return sample_file_data, cfg, None, success_notif


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Output("wizard-meta-store", "data", allow_duplicate=True),
    Output("wizard-header-title", "children"),
    Input("wizard-input-code", "value"),
    Input("wizard-input-name", "value"),
    State("wizard-config-store", "data"),
    State("wizard-meta-store", "data"),
    prevent_initial_call=True,
)
def handle_template_code_name_change(
    code_val: str | None,
    name_val: str | None,
    current_cfg: dict[str, Any] | None,
    current_meta: dict[str, Any] | None,
) -> tuple[Any, Any, Any]:
    """Cập nhật mã và tên template từ Bước 1 vào config và meta store."""
    cfg = dict(current_cfg or {})
    meta = dict(current_meta or {})
    title: Any = dash.no_update
    is_edit = meta.get("is_editing", False)
    if code_val:
        c_clean = code_val.strip().upper()
        cfg["template_code"] = c_clean
        meta["template_code"] = c_clean
        title = f"Sửa template: {c_clean}" if is_edit else f"Đăng ký template: {c_clean}"
    if name_val:
        cfg["name"] = name_val.strip()
        cfg["template_name"] = name_val.strip()
        meta["template_name"] = name_val.strip()
    return cfg, meta, title


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Output("wizard-sample-file-store", "data", allow_duplicate=True),
    Output("wizard-error-alert-container", "children", allow_duplicate=True),
    Input("wizard-input-sheet", "value"),
    Input("wizard-input-header-row", "value"),
    Input("wizard-input-data-row", "value"),
    Input("wizard-apply-suggestions", "checked"),
    State("wizard-config-store", "data"),
    State("wizard-sample-file-store", "data"),
    prevent_initial_call=True,
)
def handle_step1_file_params_change(
    sheet_val: str | None,
    header_row_val: int | None,
    data_row_val: int | None,
    apply_suggestions: bool | None,
    current_config: dict[str, Any] | None,
    sample_data: dict[str, Any] | None,
) -> tuple[Any, Any, Any]:
    """Đồng bộ Sheet / Dòng header / Dữ liệu từ dòng ở Bước 1 vào config.

    Trước đây các ô này không có callback nên sửa không ăn, upload lại
    còn ghi đè về header_row=1, data_start_row=2. Nay đổi sheet/header/
    dòng thì đọc lại 5 dòng xem trước từ file mẫu đã upload (nếu có).
    """
    if not current_config:
        return dash.no_update, dash.no_update, dash.no_update
    cfg = dict(current_config)
    file_spec = dict(cfg.get("file", {}))
    old_sheet = file_spec.get("sheet", "")
    old_header = file_spec.get("header_row", 1)
    old_data = file_spec.get("data_start_row", 2)
    old_apply = file_spec.get("apply_suggestions", True)
    new_sheet = sheet_val if sheet_val is not None else old_sheet
    new_header = header_row_val if header_row_val is not None else old_header
    new_data = data_row_val if data_row_val is not None else old_data
    new_apply = True if apply_suggestions is None else bool(apply_suggestions)
    if new_sheet == old_sheet and new_header == old_header and new_data == old_data and new_apply == old_apply:
        return dash.no_update, dash.no_update, dash.no_update
    if new_header < 1 or new_data <= new_header:
        err = alert_box(
            "Dữ liệu từ dòng phải lớn hơn Dòng header và cả hai phải >= 1.",
            tone="crit",
        )
        return dash.no_update, dash.no_update, err
    file_spec["sheet"] = new_sheet
    file_spec["header_row"] = new_header
    file_spec["data_start_row"] = new_data
    file_spec["apply_suggestions"] = new_apply
    # Áp / gỡ các chuẩn hóa tự động (strip cho text, round_2 cho number).
    if new_apply != old_apply:
        for f in cfg.get("fields", []):
            norms = [n for n in (f.get("norm") or []) if n not in ("strip", "round_2")]
            if new_apply:
                if f.get("type") == "text":
                    norms.append("strip")
                elif f.get("type") == "number":
                    norms.append("round_2")
            f["norm"] = norms
        sample = sample_data or {}
        cand = sample.get("candidate_total_rows") or []
        file_spec["skip_footer_rows"] = len(cand) if new_apply else 0
    cfg["file"] = file_spec
    if not sample_data or not sample_data.get("storage_path"):
        return cfg, dash.no_update, dash.no_update
    try:
        spec = FileSpec(sheet=new_sheet, header_row=new_header, data_start_row=new_data)
        raw_df, _ = read_sheet(Path(sample_data["storage_path"]), spec)
        cols = [c for c in raw_df.head(5).columns if c != "__row_no"]
        new_sample = dict(sample_data)
        new_sample["sheet"] = new_sheet
        new_sample["preview_rows"] = raw_df.head(5).select(cols).to_dicts()
        return cfg, new_sample, dash.no_update
    except Exception as exc:
        err = alert_box(f"Không đọc được sheet/dòng đã chọn: {exc}", tone="crit")
        return dash.no_update, dash.no_update, err


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input({"type": "wizard-field-name", "index": dash.ALL}, "value"),
    Input({"type": "wizard-field-label", "index": dash.ALL}, "value"),
    Input({"type": "wizard-field-type", "index": dash.ALL}, "value"),
    Input({"type": "wizard-field-use", "index": dash.ALL}, "checked"),
    Input({"type": "wizard-derived-name", "index": dash.ALL}, "value"),
    Input({"type": "wizard-derived-label", "index": dash.ALL}, "value"),
    Input({"type": "wizard-derived-type", "index": dash.ALL}, "value"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_step2_field_edits(
    names: list[str | None],
    labels: list[str | None],
    types: list[str | None],
    uses: list[bool | None],
    derived_names: list[str | None],
    derived_labels: list[str | None],
    derived_types: list[str | None],
    current_config: dict[str, Any] | None,
) -> Any:
    """Đồng bộ các ô sửa ở Bước 2 vào config.

    Trước đây các ô này không có id/callback nên sửa rồi bấm Tiếp là
    mất. Đổi tên trường còn đổi theo group_by / measure field để
    profile ở Bước 4 không trỏ tới tên cũ.
    """
    if not current_config:
        return dash.no_update
    cfg = dict(current_config)
    fields = list(cfg.get("fields", []))
    changed = False
    old_names: dict[int, str] = {}
    for idx, f in enumerate(fields):
        if idx >= len(names):
            break
        old_names[idx] = f.get("name", "")
        new_name = (names[idx] or "").strip()
        new_label = labels[idx] if idx < len(labels) else f.get("label")
        new_type = types[idx] if idx < len(types) else f.get("type")
        new_use = uses[idx] if idx < len(uses) else bool(f.get("excel"))
        if new_name and f.get("name") != new_name:
            f["name"] = new_name
            changed = True
        if new_label is not None and f.get("label") != new_label:
            f["label"] = new_label
            changed = True
        if new_type and f.get("type") != new_type:
            f["type"] = new_type
            changed = True
        if new_use is False and f.get("excel"):
            f["_unused_excel"] = f.get("excel")
            f["excel"] = None
            changed = True
        elif new_use is True and not f.get("excel") and f.get("_unused_excel"):
            f["excel"] = f.pop("_unused_excel")
            changed = True
    if changed:
        # Đổi tên trường thì đổi theo các tham chiếu ở profile.
        rename_map = {
            old: fields[idx].get("name")
            for idx, old in old_names.items()
            if old and fields[idx].get("name") and old != fields[idx].get("name")
        }
        if rename_map:
            for prof in cfg.get("profiles", []):
                prof["group_by"] = [rename_map.get(g, g) for g in prof.get("group_by", [])]
                for m in prof.get("measures", []):
                    if m.get("field") in rename_map:
                        m["field"] = rename_map[m["field"]]
                if prof.get("main_measure") in rename_map:
                    prof["main_measure"] = rename_map[prof["main_measure"]]
        cfg["fields"] = fields
    derived = list(cfg.get("derived", []))
    for idx, d in enumerate(derived):
        if idx >= len(derived_names):
            break
        new_name = (derived_names[idx] or "").strip()
        new_label = derived_labels[idx] if idx < len(derived_labels) else d.get("label")
        new_type = derived_types[idx] if idx < len(derived_types) else d.get("type")
        if new_name and d.get("name") != new_name:
            d["name"] = new_name
            changed = True
        if new_label is not None and d.get("label") != new_label:
            d["label"] = new_label
            changed = True
        if new_type and d.get("type") != new_type:
            d["type"] = new_type
            changed = True
    if changed:
        cfg["derived"] = derived
        return cfg
    return dash.no_update


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input("wizard-excel-time-field", "value"),
    Input("wizard-excel-suggest-range", "value"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_step3_time_filter_change(
    time_field: str | None,
    suggest_range: str | None,
    current_config: dict[str, Any] | None,
) -> Any:
    """Đồng bộ 2 select ở Bước 3 (trước đây là ô chết) vào config."""
    if not current_config:
        return dash.no_update
    cfg = dict(current_config)
    if time_field in (None, "NONE"):
        cfg["time_filter"] = None
    else:
        tf = dict(cfg.get("time_filter") or {})
        tf["excel_field"] = time_field
        tf.setdefault("granularity", "datetime")
        cfg["time_filter"] = tf
    if suggest_range:
        db_spec = cfg.setdefault("db_source", {})
        params = list(db_spec.get("params", []))
        for p in params:
            if p.get("name") in ("p_from", "p_to"):
                p["suggest"] = suggest_range
        db_spec["params"] = params
    return cfg


# Không dùng callback đánh dấu is_dirty nữa: callback đó ghi đè wizard-meta-store
# bằng snapshot meta cũ, có thể về sau cả bản meta mà autosave vừa ghi
# (row_version mới) và khiến lần lưu sau bị STALE_DATA. Thay vào đó,
# autosave tự so hash config hiện tại với hash lần lưu gần nhất trong meta;
# meta chỉ còn được ghi bởi các callback lưu/điều hướng, đều giữ nguyên
# row_version hoặc ghi row_version mới, nên không bị revert.


@callback(
    Output("wizard-table-mode-box", "style"),
    Output("wizard-sql-mode-box", "style"),
    Output("wizard-card-generated-sql", "style"),
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input("wizard-db-mode", "value"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_switch_db_mode(mode_val: str | None, current_config: dict[str, Any] | None) -> Any:
    """Chuyển đổi giao diện giữa chế độ Bảng/View và SQL tự viết."""
    if not mode_val:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    cfg = dict(current_config or {})
    cfg.setdefault("db_source", {})
    cfg["db_source"]["kind"] = mode_val
    table_style = {"display": "block"} if mode_val == "table" else {"display": "none"}
    sql_style = {"display": "block"} if mode_val == "sql" else {"display": "none"}
    gen_sql_style = {"display": "block"} if mode_val == "table" else {"display": "none"}
    return table_style, sql_style, gen_sql_style, cfg


@callback(
    Output("wizard-input-table", "data"),
    Output("wizard-input-table", "value"),
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input("wizard-input-ds", "value"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_change_data_source(ds_name: str | None, current_config: dict[str, Any] | None) -> Any:
    """Cập nhật Data Source và tải lại danh sách bảng/view tương ứng."""
    if not ds_name:
        return dash.no_update, dash.no_update, dash.no_update
    cfg = dict(current_config or {})
    cfg.setdefault("db_source", {})
    cfg["db_source"]["source_id"] = ds_name

    ctx = get_current_ctx()
    ds_id, schema = _resolve_ds_id_and_schema(ctx, ds_name)
    table_options = _fetch_table_options(ds_id, schema)

    current_table = cfg["db_source"].get("table")
    new_table_val = None
    if current_table and any(t["value"] == current_table for t in table_options):
        new_table_val = current_table
    else:
        new_table_val = None
        cfg["db_source"]["table"] = ""

    return table_options, new_table_val, cfg


@callback(
    Output("wizard-db-columns-container", "children", allow_duplicate=True),
    Output("wizard-db-mapping-container", "children", allow_duplicate=True),
    Output("wizard-db-filters-container", "children", allow_duplicate=True),
    Output("wizard-generated-sql-container", "children", allow_duplicate=True),
    Output("wizard-table-alert", "children"),
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input("wizard-input-table", "value"),
    Input("wizard-fetch-table-cols-btn", "n_clicks"),
    State("wizard-input-ds", "value"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_select_or_fetch_table(
    table_val: str | None,
    _fetch_clicks: int | None,
    ds_name: str | None,
    current_config: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """Tải cấu trúc cột khi chọn bảng/view và tự động ánh xạ trường."""
    if not table_val:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    ctx = get_current_ctx()
    if ctx is None:
        err = alert_box("Phiên làm việc đã hết hạn hoặc bạn chưa đăng nhập.", tone="crit")
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, err, dash.no_update

    ds_id, schema = _resolve_ds_id_and_schema(ctx, ds_name)
    if ds_id is None:
        err = alert_box("Không tìm thấy kết nối Data Source phù hợp.", tone="crit")
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, err, dash.no_update

    cfg = dict(current_config or {})
    cfg.setdefault("db_source", {})
    cfg["db_source"]["table"] = table_val
    if ds_name:
        cfg["db_source"]["source_id"] = ds_name

    res = describe_source(ctx, data_source_id=ds_id, table_name=table_val, schema=schema)
    if not res.ok or not res.data:
        err_msg = res.message or f"Không thể lấy danh sách cột của bảng '{table_val}'."
        err = alert_box(err_msg, tone="crit")
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, err, cfg

    raw_cols = res.data
    db_cols_chips = [(str(c["name"]), str(c.get("data_type", "VARCHAR2"))) for c in raw_cols]

    cfg["db_source"]["_columns"] = db_cols_chips

    fields = cfg.get("fields", [])
    updated_fields = _auto_match_db_columns(fields, db_cols_chips)
    cfg["fields"] = updated_fields

    chips_ui = _render_columns_chips(db_cols_chips)
    mapping_ui = _render_db_mapping_table(updated_fields, db_cols_chips)

    p_from_col = ""
    p_to_col = ""
    p_org_col = ""
    p_org_default = ""
    extra_filters = cfg.get("db_source", {}).get("extra_filters", [])
    for flt in cfg.get("db_source", {}).get("filters", []):
        if flt.get("param") == "p_from":
            p_from_col = flt.get("column", p_from_col)
        elif flt.get("param") == "p_to":
            p_to_col = flt.get("column", p_to_col)
        elif flt.get("param") == "p_org":
            p_org_col = flt.get("column", p_org_col)
    for p in cfg.get("db_source", {}).get("params", []):
        if p.get("name") == "p_org" and p.get("default"):
            p_org_default = str(p.get("default"))

    filters_ui = _render_filter_params_table(
        db_cols_chips, p_from_col, p_to_col, p_org_col, p_org_default, extra_filters
    )
    gen_sql_str = _render_generated_sql(table_val, updated_fields, p_from_col, p_to_col, p_org_col, extra_filters)
    gen_sql_ui = code_block(gen_sql_str, language="sql")
    succ_alert = alert_box(f"Đã tải thành công {len(db_cols_chips)} cột từ bảng '{table_val}'.", tone="ok")

    return chips_ui, mapping_ui, filters_ui, gen_sql_ui, succ_alert, cfg


@callback(
    Output("wizard-sql-validate-alert", "children"),
    Output("wizard-db-columns-container", "children", allow_duplicate=True),
    Output("wizard-db-mapping-container", "children", allow_duplicate=True),
    Output("wizard-db-filters-container", "children", allow_duplicate=True),
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input("wizard-check-sql-btn", "n_clicks"),
    State("wizard-sql-input", "value"),
    State("wizard-input-ds", "value"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_check_custom_sql(
    n_clicks: int | None,
    sql_val: str | None,
    ds_name: str | None,
    current_config: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any]:
    """Kiểm tra độ an toàn và trích xuất cột từ câu lệnh SQL tự viết."""
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    if not sql_val or not sql_val.strip():
        err = alert_box("Vui lòng nhập câu lệnh SQL cần kiểm tra.", tone="crit")
        return err, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    # Thu thập danh sách các biến bind được phép từ toàn bộ các tham số lọc đã đăng ký
    cfg = dict(current_config or {})
    db_spec = cfg.setdefault("db_source", {})
    registered_params = ["p_from", "p_to", "p_org"]
    for flt in db_spec.get("filters", []):
        p_name = flt.get("param")
        if p_name and p_name not in registered_params:
            registered_params.append(p_name)
    for p in db_spec.get("params", []):
        p_name = p.get("name")
        if p_name and p_name not in registered_params:
            registered_params.append(p_name)
    for ef in db_spec.get("extra_filters", []):
        p_name = ef.get("param")
        if p_name and p_name not in registered_params:
            registered_params.append(p_name)

    # SQL Guard check
    is_safe, err_msg = check_sql(sql_val, allowed_params=registered_params)
    if not is_safe:
        err = alert_box(f"Câu lệnh SQL không hợp lệ: {err_msg}", tone="crit")
        return err, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    ctx = get_current_ctx()
    if ctx is None:
        err = alert_box("Phiên làm việc đã hết hạn hoặc bạn chưa đăng nhập.", tone="crit")
        return err, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    ds_id, schema = _resolve_ds_id_and_schema(ctx, ds_name)
    if ds_id is None:
        err = alert_box("Không tìm thấy kết nối Data Source phù hợp.", tone="crit")
        return err, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    res = describe_source(ctx, data_source_id=ds_id, sql=sql_val, schema=schema, allowed_params=registered_params)
    if not res.ok or not res.data:
        err_msg = res.message or "Lỗi khi phân tích cấu trúc cột từ câu lệnh SQL."
        err = alert_box(err_msg, tone="crit")
        return err, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    raw_cols = res.data
    db_cols_chips = [(str(c["name"]), str(c.get("data_type", "VARCHAR2"))) for c in raw_cols]

    cfg = dict(current_config or {})
    cfg.setdefault("db_source", {})
    cfg["db_source"]["sql"] = sql_val
    cfg["db_source"]["_columns"] = db_cols_chips

    fields = cfg.get("fields", [])
    updated_fields = _auto_match_db_columns(fields, db_cols_chips)
    cfg["fields"] = updated_fields

    chips_ui = _render_columns_chips(db_cols_chips)
    mapping_ui = _render_db_mapping_table(updated_fields, db_cols_chips)

    p_from_col = ""
    p_to_col = ""
    p_org_col = ""
    p_org_default = ""
    for flt in db_spec.get("filters", []):
        if flt.get("param") == "p_from":
            p_from_col = flt.get("column", p_from_col)
        elif flt.get("param") == "p_to":
            p_to_col = flt.get("column", p_to_col)
        elif flt.get("param") == "p_org":
            p_org_col = flt.get("column", p_org_col)
    for p in db_spec.get("params", []):
        if p.get("name") == "p_org" and p.get("default"):
            p_org_default = str(p.get("default"))

    extra_filters = db_spec.get("extra_filters", [])
    filters_ui = _render_filter_params_table(
        db_cols_chips, p_from_col, p_to_col, p_org_col, p_org_default, extra_filters
    )
    succ_alert = alert_box(f"Câu lệnh SQL hợp lệ. Đã phát hiện {len(db_cols_chips)} cột kết quả.", tone="ok")

    return succ_alert, chips_ui, mapping_ui, filters_ui, cfg


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input("wizard-sql-input", "value"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_sql_input_change(sql_val: str | None, current_config: dict[str, Any] | None) -> Any:
    """Đồng bộ câu lệnh SQL tự viết vào wizard-config-store khi người dùng chỉnh sửa."""
    if sql_val is None or not current_config:
        return dash.no_update
    cfg = dict(current_config)
    cfg.setdefault("db_source", {})
    cfg["db_source"]["sql"] = sql_val
    return cfg


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Output("wizard-generated-sql-container", "children", allow_duplicate=True),
    Input("wizard-filter-p-from-col", "value"),
    Input("wizard-filter-p-to-col", "value"),
    Input("wizard-filter-p-org-col", "value"),
    Input("wizard-filter-p-org-val", "value"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_change_filter_cols(
    p_from: str | None,
    p_to: str | None,
    p_org_col: str | None,
    p_org_val: str | None,
    current_config: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Cập nhật các cột dùng cho tham số lọc p_from, p_to, p_org và đồng bộ SQL sinh ra."""
    if not current_config:
        return dash.no_update, dash.no_update
    cfg = dict(current_config)
    db_spec = cfg.setdefault("db_source", {})

    filters = list(db_spec.get("filters", []))
    found_from = found_to = found_org = False
    for flt in filters:
        if flt.get("param") == "p_from":
            flt["column"] = p_from or ""
            found_from = True
        elif flt.get("param") == "p_to":
            flt["column"] = p_to or ""
            found_to = True
        elif flt.get("param") == "p_org":
            flt["column"] = p_org_col or ""
            found_org = True

    if not found_from:
        filters.append({"param": "p_from", "column": p_from or "", "op": ">=", "cast": "none"})
    if not found_to:
        filters.append({"param": "p_to", "column": p_to or "", "op": "<=", "cast": "none"})
    if not found_org and p_org_col:
        filters.append({"param": "p_org", "column": p_org_col, "op": "=", "cast": "none"})

    db_spec["filters"] = filters

    params = list(db_spec.get("params", []))
    found_org_param = False
    for p in params:
        if p.get("name") == "p_org":
            p["default"] = p_org_val or ""
            found_org_param = True
    if not found_org_param:
        params.append(
            {
                "name": "p_org",
                "type": "text",
                "source": "default",
                "default": p_org_val or "",
                "label": "Đơn vị",
                "required": True,
            }
        )
    db_spec["params"] = params

    _sync_db_source_filters_and_params(cfg)

    table_name = db_spec.get("table", "")
    fields = cfg.get("fields", [])
    extra_filters = db_spec.get("extra_filters", [])
    gen_sql = _render_generated_sql(table_name, fields, p_from or "", p_to or "", p_org_col or "", extra_filters)
    gen_sql_ui = code_block(gen_sql, language="sql")

    return cfg, gen_sql_ui


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input("wizard-input-pushdown", "checked"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_change_pushdown(checked: bool | None, current_config: dict[str, Any] | None) -> Any:
    """Cập nhật cờ đẩy phép gộp xuống DB."""
    if checked is None or not current_config:
        return dash.no_update
    cfg = dict(current_config)
    cfg.setdefault("db_source", {})
    cfg["db_source"]["pushdown_aggregate"] = bool(checked)
    return cfg


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input({"type": "wizard-db-mapping-col", "index": dash.ALL}, "value"),
    State({"type": "wizard-db-mapping-col", "index": dash.ALL}, "id"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_change_db_mapping(
    values: list[str | None],
    ids: list[dict[str, str]],
    current_config: dict[str, Any] | None,
) -> Any:
    """Cập nhật lựa chọn Cột DB cho từng trường logic."""
    if not current_config or not values or not ids:
        return dash.no_update

    cfg = dict(current_config)
    fields = list(cfg.get("fields", []))
    field_map = {f.get("name"): f for f in fields}

    changed = False
    for comp_id, val in zip(ids, values, strict=False):
        f_name = comp_id.get("index")
        if f_name in field_map:
            db_val = None if (not val or val == "— Không có —") else val
            if field_map[f_name].get("db") != db_val:
                field_map[f_name]["db"] = db_val
                changed = True

    if changed:
        cfg["fields"] = fields
        return cfg
    return dash.no_update


@callback(
    Output("wizard-stepper-box", "style"),
    Output("wizard-step-content", "style"),
    Output("wizard-diagram-content", "style"),
    Output("wizard-footer-nav", "style"),
    Output("wizard-diagram-content", "children"),
    Input("wizard-view-tabs", "value"),
    State("wizard-config-store", "data"),
)
def handle_switch_tabs(
    tab_value: str | None,
    config_data: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str], Any]:
    """Chuyển đổi giữa tab Cấu hình template và tab Sơ đồ diễn giải."""
    if tab_value == "diagram":
        diagram_ui = render_diagrams_tab(config_data or {})
        return (
            {"display": "none"},
            {"display": "none"},
            {"display": "block"},
            {"display": "none"},
            diagram_ui,
        )
    return (
        {"display": "block"},
        {"display": "block"},
        {"display": "none"},
        {"display": "flex"},
        dash.no_update,
    )


@callback(
    Output("wizard-stepper", "active"),
    Output("wizard-prev-btn", "disabled"),
    Output("wizard-next-btn", "children"),
    Output("wizard-meta-store", "data", allow_duplicate=True),
    Output("wizard-redirect-location", "href"),
    Output("wizard-error-alert-container", "children", allow_duplicate=True),
    Input("wizard-next-btn", "n_clicks"),
    Input("wizard-prev-btn", "n_clicks"),
    State("wizard-stepper", "active"),
    State("wizard-meta-store", "data"),
    State("wizard-config-store", "data"),
    State("wizard-sample-file-store", "data"),
    State("wizard-dry-run-store", "data"),
    prevent_initial_call=True,
)
def handle_step_navigation(
    next_clicks: int | None,
    prev_clicks: int | None,
    current_active: int,
    meta: dict[str, Any] | None,
    config_data: dict[str, Any] | None,
    sample_data: dict[str, Any] | None = None,
    dry_run_data: dict[str, Any] | None = None,
) -> Any:
    """Xử lý nút Tiếp và Quay lại trên Stepper 5 bước và kích hoạt template."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return current_active, current_active == 0, "Tiếp", meta or {}, dash.no_update, dash.no_update

    trigger = ctx_dash.triggered[0]["prop_id"]
    if "wizard-next-btn" in trigger:
        # Validate bước hiện tại trước khi đi tiếp / kích hoạt.
        step_errors = validate_wizard_step(config_data, current_active, sample_data)
        if current_active == 4 and not (dry_run_data or {}).get("dry_run_ok"):
            last_err = (dry_run_data or {}).get("error")
            last_stage = (dry_run_data or {}).get("stage_label")
            if last_err:
                step_errors.append(
                    f"Bước 5: chưa chạy Dry-run thật thành công, chưa thể kích hoạt. "
                    f"Lỗi Dry-run gần nhất ở {last_stage}: {last_err}. "
                    f"Bấm 'Chạy thử' lại và xem lỗi ở timeline Tiến trình Dry-run ở trên."
                )
            else:
                step_errors.append(
                    "Bước 5: chưa chạy Dry-run thật thành công, chưa thể kích hoạt. "
                    "Bấm 'Chạy thử' và chờ kết quả thật trước."
                )
        elif current_active == 4 and (dry_run_data or {}).get("config_hash") != _config_hash(config_data):
            step_errors.append(
                "Bước 5: cấu hình đã thay đổi sau lần Dry-run gần nhất, cần bấm 'Chạy thử' lại trước khi kích hoạt."
            )
        if step_errors:
            err_box = alert_box(" · ".join(step_errors), tone="crit")
            next_text = "Lưu & kích hoạt" if current_active == 4 else "Tiếp"
            return current_active, current_active == 0, next_text, meta or {}, dash.no_update, err_box
        if current_active == 4:
            # Xử lý Kích hoạt template
            ctx = get_current_ctx()
            if ctx is None:
                err_box = alert_box("Phiên làm việc đã hết hạn hoặc bạn chưa đăng nhập.", tone="crit")
                return 4, False, "Lưu & kích hoạt", meta or {}, dash.no_update, err_box

            cfg_dict = dict(config_data or {})

            # 1. Không tự chèn bảng/cột lọc: thiếu thì validate ở bước kích hoạt sẽ báo lỗi.
            db_src = dict(cfg_dict.get("db_source") or {})
            cfg_dict["db_source"] = db_src

            # 2. Đảm bảo các fields có db mapping
            fields = list(cfg_dict.get("fields") or [])
            for f in fields:
                if isinstance(f, dict) and not f.get("db"):
                    f["db"] = f.get("name")
            cfg_dict["fields"] = fields

            # 3. Đảm bảo profiles có ít nhất 1 profile hợp lệ
            profs = list(cfg_dict.get("profiles") or [])
            if not profs or (len(profs) == 1 and (not profs[0].get("group_by") or not profs[0].get("measures"))):
                cfg_dict["profiles"] = _build_default_profiles_from_fields(fields, cfg_dict.get("derived", []))
                profs = cfg_dict["profiles"]

            # Xóa drilldown_to nếu trỏ tới profile không tồn tại
            valid_p_codes = {p.get("code") for p in profs if isinstance(p, dict)}
            for p in profs:
                if isinstance(p, dict) and p.get("drilldown_to") and p["drilldown_to"] not in valid_p_codes:
                    p["drilldown_to"] = None

            template_cfg, errors = form_state_to_config(cfg_dict)
            if template_cfg is None:
                err_box = alert_box(f"Không thể kích hoạt vì cấu hình chưa hợp lệ: {errors}", tone="crit")
                return 4, False, "Lưu & kích hoạt", meta or {}, dash.no_update, err_box

            # Không lưu nháp lại ở đây: save_draft_template luôn reset DRY_RUN_OK
            # về "N", lưu lại sẽ xóa cờ Dry-run vừa đạt. Dry-run thật đã lưu
            # nháp và cập nhật meta (template_id/version/row_version) trước đó,
            # nên kích hoạt đúng version đó. Nếu chưa có meta đó thì báo lỗi
            # thay vì lưu lại và kích hoạt bằng override.
            t_id = (meta or {}).get("template_id")
            ver = (meta or {}).get("version", 1)
            if not t_id:
                err_box = alert_box(
                    "Chưa có bản nháp đã lưu từ lần Dry-run gần nhất, bấm 'Chạy thử' lại trước khi kích hoạt.",
                    tone="crit",
                )
                return 4, False, "Lưu & kích hoạt", meta or {}, dash.no_update, err_box

            act_res = activate_version(ctx, template_id=t_id, version=ver, dry_run_override=False)
            if not act_res.ok:
                err_box = alert_box(f"Lỗi khi kích hoạt template: {act_res.message}", tone="crit")
                return 4, False, "Lưu & kích hoạt", meta or {}, dash.no_update, err_box
            return 4, False, "Lưu & kích hoạt", meta or {}, "/templates", None

        new_step = current_active + 1
    elif "wizard-prev-btn" in trigger:
        new_step = max(0, current_active - 1)
    else:
        new_step = current_active

    next_btn_text = "Lưu & kích hoạt" if new_step == 4 else "Tiếp"
    updated_meta = {**(meta or {}), "current_step": new_step + 1}
    return new_step, (new_step == 0), next_btn_text, updated_meta, dash.no_update, None


DRY_RUN_STAGES = [
    ("validate", "1. Kiểm tra cấu hình"),
    ("save", "2. Lưu bản nháp"),
    ("dry_run", "3. Chạy đối soát thật"),
    ("done", "4. Sẵn sàng kích hoạt"),
]


def _p_org_required(config: dict[str, Any] | None) -> bool:
    """p_org có bắt buộc cho lần chạy này không?

    Bắt buộc khi SQL tùy biến dùng :p_org, hoặc bảng lọc có filter p_org
    (không skip_if_empty), hoặc param p_org khai báo required=True.
    Nếu bắt buộc mà lần chạy không truyền p_org, SQL sẽ bị check_sql
    chặn với SQL_NOT_ALLOWED, dù p_org đã khai báo ở Bước 3.
    """
    db_spec = (config or {}).get("db_source", {}) or {}
    if db_spec.get("kind") == "sql" and ":p_org" in (db_spec.get("sql") or ""):
        return True
    for flt in db_spec.get("filters", []) or []:
        if isinstance(flt, dict) and flt.get("param") == "p_org" and flt.get("column") and not flt.get("skip_if_empty"):
            return True
    for p in db_spec.get("params", []) or []:
        if isinstance(p, dict) and p.get("name") == "p_org" and p.get("required"):
            return True
    return False


def _dry_run_store(
    stage: str,
    error: str | None,
    p_from: Any,
    p_to: Any,
    p_org: Any,
    config: dict[str, Any] | None,
    summary: dict[str, Any] | None = None,
    grain_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Gói kết quả Dry-run vào store, kèm bước đã dừng và lỗi đầy đủ.

    Store là nơi duy nhất sống qua lần render lại Bước 5: callback render
    chạy lại mỗi khi store đổi và dựng lại cả ô lỗi, nên lỗi chỉ trả qua
    ô lỗi riêng sẽ bị render lại xóa mất. Ghi lỗi vào store thì render
    lại vẫn hiện đúng lỗi ở đúng bước.
    """
    stage_label = dict(DRY_RUN_STAGES).get(stage, stage)
    return {
        "dry_run_ok": stage == "done" and not error,
        "stage": stage,
        "stage_label": stage_label,
        "error": error,
        "message": None
        if error
        else "Dry-run thật hoàn tất thành công. Toàn bộ chỉ số đã được cập nhật từ kết quả thật.",
        "p_from": str(p_from) if p_from else None,
        "p_to": str(p_to) if p_to else None,
        "p_org": p_org or "",
        "summary": summary or {},
        "grain_warnings": grain_warnings or [],
        "config_hash": _config_hash(config),
    }


@callback(
    Output("wizard-dry-run-error", "children"),
    Output("wizard-dry-run-store", "data"),
    Output("wizard-meta-store", "data", allow_duplicate=True),
    Input("wizard-run-dry-btn", "n_clicks"),
    State("wizard-dry-p-from", "value"),
    State("wizard-dry-p-to", "value"),
    State("wizard-dry-p-org", "value"),
    State("wizard-config-store", "data"),
    State("wizard-meta-store", "data"),
    State("wizard-sample-file-store", "data"),
    prevent_initial_call=True,
)
def handle_run_dry_run(
    n_clicks: int | None,
    p_from: str | None,
    p_to: str | None,
    _p_org: str | None,
    _config: dict[str, Any] | None,
    _meta: dict[str, Any] | None,
    _sample: dict[str, Any] | None = None,
) -> tuple[Any, Any, Any]:
    """Chạy Dry-run thật trên file mẫu qua service, không dùng số mẫu."""
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update

    err = validate_dry_run_params(p_from, p_to)
    if err:
        store = _dry_run_store("validate", err, p_from, p_to, _p_org, _config)
        return alert_box(f"Lỗi ở 1. Kiểm tra cấu hình: {err}", tone="crit"), store, dash.no_update
    step_errors: list[str] = []
    for step_idx in range(4):
        step_errors.extend(validate_wizard_step(_config, step_idx, _sample))
    if step_errors:
        msg = " · ".join(step_errors)
        store = _dry_run_store("validate", msg, p_from, p_to, _p_org, _config)
        return alert_box(f"Lỗi ở 1. Kiểm tra cấu hình: {msg}", tone="crit"), store, dash.no_update

    # p_org: ưu tiên giá trị nhập ở Bước 5, sau đó là Mặc định ở Bước 3.
    # Nếu p_org bắt buộc mà cả hai đều trống thì chặn ngay ở bước kiểm tra,
    # thay vì để pipeline báo SQL_NOT_ALLOWED khó hiểu ở bước 3.
    p_org_input = str(_p_org).strip() if _p_org else ""
    p_org_default = ""
    for p in ((_config or {}).get("db_source", {}) or {}).get("params", []) or []:
        if isinstance(p, dict) and p.get("name") == "p_org" and p.get("default"):
            p_org_default = str(p.get("default")).strip()
            break
    _p_org = p_org_input or p_org_default or None
    if _p_org_required(_config) and not _p_org:
        msg = (
            "SQL / bảng lọc dùng :p_org nhưng chưa có Mã đơn vị: nhập Mã đơn vị ở Bước 5 "
            "(ví dụ BDP), hoặc đặt Mặc định cho p_org ở Bước 3, rồi bấm Chạy thử lại. "
            "Để trống ở Bước 5 chỉ được khi SQL không dùng :p_org."
        )
        store = _dry_run_store("validate", msg, p_from, p_to, _p_org, _config)
        return alert_box(f"Lỗi ở 1. Kiểm tra cấu hình: {msg}", tone="crit"), store, dash.no_update

    ctx = get_current_ctx()
    if ctx is None:
        msg = "Phiên làm việc đã hết hạn hoặc bạn chưa đăng nhập."
        store = _dry_run_store("validate", msg, p_from, p_to, _p_org, _config)
        return alert_box(f"Lỗi ở 1. Kiểm tra cấu hình: {msg}", tone="crit"), store, dash.no_update
    template_cfg, cfg_errors = form_state_to_config(_config or {})
    if template_cfg is None:
        msg = f"Cấu hình chưa hợp lệ để chạy thử: {cfg_errors}"
        store = _dry_run_store("save", msg, p_from, p_to, _p_org, _config)
        return alert_box(f"Lỗi ở 2. Lưu bản nháp: {msg}", tone="crit"), store, dash.no_update
    code_to_save = (
        ((_meta or {}).get("template_code") or (_config or {}).get("template_code") or "NEW_TEMPLATE").strip().upper()
    )
    name_to_save = (
        (_meta or {}).get("template_name") or (_config or {}).get("name") or f"Template {code_to_save}"
    ).strip()
    ds_name = (_config or {}).get("db_source", {}).get("source_id")
    ds_id = _resolve_ds_id_and_schema(ctx, ds_name)[0] if ds_name else None
    s_file_id = (_sample or {}).get("file_id") or (_meta or {}).get("sample_file_id")
    if not s_file_id:
        msg = "Chưa có file mẫu để chạy thử. Tải file mẫu ở Bước 1 trước."
        store = _dry_run_store("save", msg, p_from, p_to, _p_org, _config)
        return alert_box(f"Lỗi ở 2. Lưu bản nháp: {msg}", tone="crit"), store, dash.no_update
    save_res = save_draft_template(
        ctx,
        code=code_to_save,
        name=name_to_save,
        config=template_cfg,
        description=getattr(template_cfg, "description", None),
        data_source_id=ds_id,
        row_version=(_meta or {}).get("row_version"),
        sample_file_id=s_file_id,
    )
    retried_stale = False
    if (not save_res.ok) and save_res.code == "STALE_DATA" and (_meta or {}).get("template_id"):
        # Meta trong trình duyệt có thể lệch row_version so với DB (ví dụ
        # autosave vừa lưu xong nhưng meta chưa kịp cập nhật). Đọc lại
        # row_version hiện tại từ DB và thử lưu lại một lần, thay vì bắt
        # người dùng tải lại trang. Nếu lần hai vẫn STALE thì báo lỗi thật.
        fresh = get_template(ctx, (_meta or {}).get("template_id"))
        if fresh.ok and fresh.data and fresh.data.get("row_version"):
            save_res = save_draft_template(
                ctx,
                code=code_to_save,
                name=name_to_save,
                config=template_cfg,
                description=getattr(template_cfg, "description", None),
                data_source_id=ds_id,
                row_version=fresh.data.get("row_version"),
                sample_file_id=s_file_id,
            )
            retried_stale = save_res.ok
    if not save_res.ok or not save_res.data:
        msg = f"Lỗi khi lưu bản nháp trước khi chạy thử: {save_res.message or save_res.code}"
        if save_res.code:
            msg += f" (mã: {save_res.code})"
        store = _dry_run_store("save", msg, p_from, p_to, _p_org, _config)
        return alert_box(f"Lỗi ở 2. Lưu bản nháp: {msg}", tone="crit"), store, dash.no_update
    t_id = save_res.data.get("id", (_meta or {}).get("template_id"))
    ver = save_res.data.get("current_version", save_res.data.get("version", 1))
    dt_from = datetime.fromisoformat(str(p_from).strip().replace(" ", "T"))
    dt_to = datetime.fromisoformat(str(p_to).strip().replace(" ", "T"))
    profiles = (_config or {}).get("profiles", []) or []
    default_profile = next((p for p in profiles if p.get("is_default")), profiles[0] if profiles else {})
    dry_res = service_dry_run(
        ctx,
        template_id=t_id,
        version=ver,
        file_id=s_file_id,
        p_from=dt_from,
        p_to=dt_to,
        profile_code=default_profile.get("code"),
        p_org=_p_org,
    )
    if not dry_res.ok or not dry_res.data:
        msg = f"Dry-run thất bại: {dry_res.message or dry_res.code}"
        if dry_res.code:
            msg += f" (mã: {dry_res.code})"
        if dry_res.details:
            msg += f" Chi tiết: {dry_res.details}"
        store = _dry_run_store("dry_run", msg, p_from, p_to, _p_org, _config)
        return alert_box(f"Lỗi ở 3. Chạy đối soát thật: {msg}", tone="crit"), store, dash.no_update
    dry_data = dry_res.data
    result = _dry_run_store(
        "done",
        None,
        p_from,
        p_to,
        _p_org,
        _config,
        summary=dry_data.get("summary", {}),
        grain_warnings=dry_data.get("grain_warnings", []),
    )
    saved_meta = {
        **(_meta or {}),
        "template_id": t_id,
        "template_code": code_to_save,
        "template_name": name_to_save,
        "version": ver,
        "row_version": save_res.data.get("row_version") if save_res.data else (_meta or {}).get("row_version"),
        "sample_file_id": s_file_id,
        "is_dirty": False,
        "last_saved_config_hash": _config_hash(_config),
    }
    return (
        alert_box(
            "Dry-run thật hoàn tất thành công. Toàn bộ chỉ số đã được cập nhật từ kết quả thật."
            + (" (Đã đồng bộ lại row_version trước khi lưu.)" if retried_stale else ""),
            tone="ok",
        ),
        result,
        saved_meta,
    )


@callback(
    Output("wizard-header-subtitle", "children"),
    Output("wizard-meta-store", "data", allow_duplicate=True),
    Output("wizard-notification-container", "children"),
    Input("wizard-save-draft-btn", "n_clicks"),
    Input("wizard-autosave-interval", "n_intervals"),
    State("wizard-config-store", "data"),
    State("wizard-meta-store", "data"),
    State("wizard-sample-file-store", "data"),
    prevent_initial_call=True,
)
def handle_save_or_autosave_draft(
    save_clicks: int | None,
    _interval: int | None,
    config_data: dict[str, Any] | None,
    meta_data: dict[str, Any] | None,
    sample_data: dict[str, Any] | None = None,
) -> Any:
    """Lưu nháp thủ công hoặc tự động qua timer định kỳ."""
    ctx = get_current_ctx()
    if ctx is None or not config_data:
        return dash.no_update, dash.no_update, dash.no_update

    ctx_dash = dash.callback_context
    triggered_id = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""
    is_manual = "wizard-save-draft-btn" in triggered_id

    # Autosave chỉ lưu khi config khác lần lưu gần nhất (so hash), không
    # dùng cờ is_dirty nữa để tránh callback khác ghi đè meta cũ.
    if not is_manual and (meta_data or {}).get("last_saved_config_hash") == _config_hash(config_data):
        return dash.no_update, dash.no_update, dash.no_update

    template_cfg, errors = form_state_to_config(config_data)
    if template_cfg is None:
        if is_manual:
            err_box = alert_box(f"Cấu hình chưa hợp lệ để lưu nháp: {errors}", tone="crit")
            return dash.no_update, dash.no_update, err_box
        return dash.no_update, dash.no_update, dash.no_update

    t_id = meta_data.get("template_id") if meta_data else None
    code_to_save = (
        ((meta_data or {}).get("template_code") or (config_data or {}).get("template_code") or "NEW_TEMPLATE")
        .strip()
        .upper()
    )

    name_to_save = (
        (meta_data or {}).get("template_name") or (config_data or {}).get("name") or f"Template {code_to_save}"
    ).strip()

    ds_name = (config_data or {}).get("db_source", {}).get("source_id")
    ds_id = None
    if ds_name:
        ds_id, _ = _resolve_ds_id_and_schema(ctx, ds_name)

    sample_file_id_val = (sample_data or {}).get("file_id") or (meta_data or {}).get("sample_file_id")

    res = save_draft_template(
        ctx,
        code=code_to_save,
        name=name_to_save,
        config=template_cfg,
        description=getattr(template_cfg, "description", None),
        data_source_id=ds_id,
        row_version=meta_data.get("row_version") if meta_data else None,
        sample_file_id=sample_file_id_val,
    )
    if not res.ok:
        if is_manual:
            return dash.no_update, dash.no_update, alert_box(res.message, tone="crit")
        return dash.no_update, dash.no_update, dash.no_update

    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
    saved_meta = {
        **(meta_data or {}),
        "template_id": res.data.get("id") if res.data else t_id,
        "template_code": code_to_save,
        "template_name": name_to_save,
        "version": res.data.get("current_version", res.data.get("version", 1)) if res.data else 1,
        "row_version": res.data.get("row_version") if res.data else None,
        "sample_file_id": sample_file_id_val,
        "is_dirty": False,
        "last_saved_config_hash": _config_hash(config_data),
        "last_saved_at": now_str,
    }
    sub_title = (
        f"Bản nháp v{saved_meta['version']} · tự lưu lúc {now_str} · "
        f"Data Source {config_data.get('db_source', {}).get('source_id', '—')} · "
        f"Bảng {config_data.get('db_source', {}).get('table', '—')}"
    )

    notif = None
    if is_manual:
        notif = alert_box(f"Đã lưu bản nháp v{saved_meta['version']} thành công lúc {now_str}.", tone="ok")

    return sub_title, saved_meta, notif


@callback(
    Output("wizard-step4-right-content", "children", allow_duplicate=True),
    Output("wizard-config-store", "data", allow_duplicate=True),
    Output("wizard-active-profile-store", "data", allow_duplicate=True),
    Output("wizard-step4-left-fields", "children", allow_duplicate=True),
    Output("wizard-profile-tabs-list", "children", allow_duplicate=True),
    Output("wizard-profile-tabs", "value", allow_duplicate=True),
    Input("wizard-profile-tabs", "value"),
    Input("wizard-add-profile-btn", "n_clicks"),
    Input("wizard-delete-profile-btn", "n_clicks"),
    Input("wizard-profile-name-input", "value"),
    Input("wizard-profile-code-input", "value"),
    Input("wizard-groupby-select", "value"),
    Input("wizard-add-measure-btn", "n_clicks"),
    Input({"type": "wizard-field-key-btn", "index": dash.ALL}, "n_clicks"),
    Input({"type": "wizard-field-sigma-btn", "index": dash.ALL}, "n_clicks"),
    Input({"type": "wizard-m-delete-btn", "index": dash.ALL}, "n_clicks"),
    Input({"type": "wizard-m-main-btn", "index": dash.ALL}, "n_clicks"),
    State("wizard-config-store", "data"),
    State("wizard-active-profile-store", "data"),
    State("wizard-sample-file-store", "data"),
    prevent_initial_call=True,
)
def handle_step4_interaction(
    tab_val: str | None,
    _add_prof_clicks: int | None,
    _del_prof_clicks: int | None,
    prof_name_val: str | None,
    prof_code_val: str | None,
    groupby_select_vals: list[str] | None,
    _add_m_clicks: int | None,
    _key_clicks: list[int | None],
    _sigma_clicks: list[int | None],
    _del_m_clicks: list[int | None],
    _main_m_clicks: list[int | None],
    current_config: dict[str, Any] | None,
    active_prof_code: str | None,
    sample_data: dict[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """Xử lý tương tác thêm/sửa/xóa Profile, Group by và Measures ở Bước 4."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered or not current_config:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    triggered_prop = ctx_dash.triggered[0]["prop_id"]
    cfg = dict(current_config)
    profiles = list(cfg.get("profiles", []))
    if not profiles or (len(profiles) == 1 and profiles[0].get("code") == "BY_DEFAULT"):
        profiles = _build_default_profiles_from_fields(cfg.get("fields", []), cfg.get("derived", []))
        cfg["profiles"] = profiles

    active_code = active_prof_code or profiles[0].get("code", "PROFILE_1")
    active_idx = 0
    for idx, p in enumerate(profiles):
        if p.get("code") == active_code:
            active_idx = idx
            break
    active_prof = dict(profiles[active_idx])

    # Danh sách các trường có sẵn: chỉ trường đã map cột DB ở Bước 3.
    avail_fields_info = _mapped_fields_info(cfg)
    avail_field_names = [f["name"] for f in avail_fields_info]

    new_tab_value: Any = dash.no_update

    # 1. Chuyển tab Profile
    if "wizard-profile-tabs.value" in triggered_prop:
        if tab_val:
            active_code = tab_val
            for idx, p in enumerate(profiles):
                if p.get("code") == active_code:
                    active_idx = idx
                    active_prof = dict(p)
                    break

    # 2. Đổi tên Profile
    elif "wizard-profile-name-input" in triggered_prop:
        if prof_name_val is not None:
            active_prof["name"] = prof_name_val
            profiles[active_idx] = active_prof
            cfg["profiles"] = profiles
            tab_list = [
                dmc.TabsTab(p.get("name") or p.get("code", "Profile"), value=p.get("code", "PROFILE_1"))
                for p in profiles
            ]
            tabs_list_ui = [
                *tab_list,
                button_subtle("Thêm profile", id="wizard-add-profile-btn", icon="lucide:plus", size="xs"),
            ]
            return (
                dash.no_update,
                cfg,
                dash.no_update,
                dash.no_update,
                tabs_list_ui,
                dash.no_update,
            )

    # 3. Đổi mã Profile (code)
    elif "wizard-profile-code-input" in triggered_prop:
        if prof_code_val is not None:
            norm_code = prof_code_val.strip().upper()
            if norm_code and norm_code != active_code:
                old_code = active_code
                for p in profiles:
                    if p.get("drilldown_to") == old_code:
                        p["drilldown_to"] = norm_code
                active_prof["code"] = norm_code
                profiles[active_idx] = active_prof
                cfg["profiles"] = profiles
                tab_list = [
                    dmc.TabsTab(p.get("name") or p.get("code", "Profile"), value=p.get("code", "PROFILE_1"))
                    for p in profiles
                ]
                tabs_list_ui = [
                    *tab_list,
                    button_subtle("Thêm profile", id="wizard-add-profile-btn", icon="lucide:plus", size="xs"),
                ]
                return (
                    dash.no_update,
                    cfg,
                    norm_code,
                    dash.no_update,
                    tabs_list_ui,
                    norm_code,
                )

    # 4. Xóa Profile
    elif "wizard-delete-profile-btn" in triggered_prop:
        if len(profiles) > 1:
            profiles.pop(active_idx)
            if not any(p.get("is_default") for p in profiles):
                profiles[0]["is_default"] = True
            active_idx = max(0, min(active_idx, len(profiles) - 1))
            active_prof = dict(profiles[active_idx])
            active_code = str(active_prof.get("code"))
            new_tab_value = active_code

    # 5. Thêm Profile mới
    elif "wizard-add-profile-btn" in triggered_prop:
        new_num = len(profiles) + 1
        new_code = f"PROFILE_{new_num}"
        existing_codes = {p.get("code") for p in profiles}
        while new_code in existing_codes:
            new_num += 1
            new_code = f"PROFILE_{new_num}"
        new_name = f"Profile {new_num}"
        # Không tự lấy trường đầu tiên làm Group by: profile mới phải để
        # người dùng chọn khóa, giống như profile mặc định giờ là rỗng.
        g_cols: list[str] = []

        new_prof = {
            "code": new_code,
            "name": new_name,
            "is_default": False,
            "aggregate": True,
            "group_by": g_cols,
            "measures": list(active_prof.get("measures", [])),
            "filters": [],
            "main_measure": active_prof.get("main_measure"),
            "drilldown_to": None,
        }
        profiles.append(new_prof)
        active_code = new_code
        active_idx = len(profiles) - 1
        active_prof = new_prof
        new_tab_value = new_code

    # 3. Chọn Group by qua MultiSelect
    elif "wizard-groupby-select" in triggered_prop:
        if groupby_select_vals:
            active_prof["group_by"] = groupby_select_vals

    # 4. Bật/Tắt trường vào Group by từ cột trái
    elif "wizard-field-key-btn" in triggered_prop:
        try:
            import json

            prop_data = json.loads(triggered_prop.split(".")[0])
            f_name = prop_data.get("index")
            grp = list(active_prof.get("group_by", []))
            if f_name in grp:
                if len(grp) > 1:
                    grp.remove(f_name)
            else:
                grp.append(f_name)
            active_prof["group_by"] = grp
        except Exception:
            pass

    # 5. Thêm Measure từ trường (biểu tượng sigma)
    elif "wizard-field-sigma-btn" in triggered_prop:
        try:
            import json

            prop_data = json.loads(triggered_prop.split(".")[0])
            f_name = prop_data.get("index")
            f_meta = next((f for f in avail_fields_info if f["name"] == f_name), None)
            f_type = f_meta.get("type", "text") if f_meta else "text"
            measures = list(active_prof.get("measures", []))

            if f_type == "number":
                new_m = {
                    "name": f"TOTAL_{f_name}",
                    "label": f"Tổng {f_meta.get('label', f_name) if f_meta else f_name}",
                    "agg": "sum",
                    "field": f_name,
                    "compare": "abs_tol",
                    "tolerance": 1,
                    "round": 0,
                }
            elif f_type in ("date", "datetime"):
                new_m = {
                    "name": f_name,
                    "label": f_meta.get("label", f_name) if f_meta else f_name,
                    "agg": "first_distinct",
                    "field": f_name,
                    "compare": "exact",
                }
            else:
                new_m = {
                    "name": f"{f_name}_CNT",
                    "label": f"Số {f_meta.get('label', f_name) if f_meta else f_name}",
                    "agg": "count_distinct",
                    "field": f_name,
                    "compare": "exact",
                }
            measures.append(new_m)
            active_prof["measures"] = measures
        except Exception:
            pass

    # 6. Thêm Measure rỗng từ nút "+ Thêm measure"
    elif "wizard-add-measure-btn" in triggered_prop:
        measures = list(active_prof.get("measures", []))
        idx_new = len(measures) + 1
        num_field = next(
            (f["name"] for f in avail_fields_info if f.get("type") == "number"),
            avail_field_names[0] if avail_field_names else "*",
        )
        measures.append(
            {
                "name": f"MEASURE_{idx_new}",
                "label": f"Chỉ số {idx_new}",
                "agg": "sum",
                "field": num_field,
                "compare": "exact",
                "round": 0,
            }
        )
        active_prof["measures"] = measures

    # 7. Xóa Measure
    elif "wizard-m-delete-btn" in triggered_prop:
        try:
            import json

            prop_data = json.loads(triggered_prop.split(".")[0])
            del_idx = int(prop_data.get("index", 0))
            measures = list(active_prof.get("measures", []))
            if len(measures) > 1 and 0 <= del_idx < len(measures):
                deleted_m = measures.pop(del_idx)
                if deleted_m.get("name") == active_prof.get("main_measure"):
                    active_prof["main_measure"] = measures[0]["name"] if measures else None
                active_prof["measures"] = measures
        except Exception:
            pass

    # 8. Đặt làm Measure chính
    elif "wizard-m-main-btn" in triggered_prop:
        try:
            import json

            prop_data = json.loads(triggered_prop.split(".")[0])
            main_idx = int(prop_data.get("index", 0))
            measures = active_prof.get("measures", [])
            if 0 <= main_idx < len(measures):
                active_prof["main_measure"] = measures[main_idx].get("name")
        except Exception:
            pass

    profiles[active_idx] = active_prof
    cfg["profiles"] = profiles

    right_ui = _render_step_4_right_panel(active_prof, avail_field_names, cfg, sample_data)
    left_ui = _render_step_4_left_fields(
        avail_fields_info,
        active_prof.get("group_by", []),
        [m.get("field") for m in active_prof.get("measures", []) if isinstance(m, dict)],
    )

    tab_list = [
        dmc.TabsTab(p.get("name", p.get("code", "Profile")), value=p.get("code", "BY_INVOICE")) for p in profiles
    ]
    tabs_list_ui = [
        *tab_list,
        button_subtle("Thêm profile", id="wizard-add-profile-btn", icon="lucide:plus", size="xs"),
    ]

    return right_ui, cfg, active_code, left_ui, tabs_list_ui, new_tab_value


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Output("wizard-grouped-sql-container", "children", allow_duplicate=True),
    Input({"type": "wizard-m-name", "index": dash.ALL}, "value"),
    Input({"type": "wizard-m-label", "index": dash.ALL}, "value"),
    Input({"type": "wizard-m-agg", "index": dash.ALL}, "value"),
    Input({"type": "wizard-m-field", "index": dash.ALL}, "value"),
    Input({"type": "wizard-m-cmp", "index": dash.ALL}, "value"),
    Input({"type": "wizard-m-tol", "index": dash.ALL}, "value"),
    Input({"type": "wizard-m-rnd", "index": dash.ALL}, "value"),
    Input("wizard-profile-filter", "value"),
    Input("wizard-drilldown-select", "value"),
    State("wizard-config-store", "data"),
    State("wizard-active-profile-store", "data"),
    prevent_initial_call=True,
)
def handle_step4_measure_edits(
    m_names: list[str | None],
    m_labels: list[str | None],
    m_aggs: list[str | None],
    m_fields: list[str | None],
    m_cmps: list[str | None],
    m_tols: list[float | int | None],
    m_rnds: list[int | None],
    prof_filter: str | None,
    drilldown_val: str | None,
    current_config: dict[str, Any] | None,
    active_prof_code: str | None,
) -> tuple[Any, Any]:
    """Cập nhật các giá trị sửa đổi trong bảng Measures và sinh lại SQL gộp."""
    if not current_config:
        return dash.no_update, dash.no_update

    cfg = dict(current_config)
    profiles = list(cfg.get("profiles", []))
    if not profiles:
        return dash.no_update, dash.no_update

    active_code = active_prof_code or profiles[0].get("code", "BY_INVOICE")
    active_idx = 0
    for idx, p in enumerate(profiles):
        if p.get("code") == active_code:
            active_idx = idx
            break
    active_prof = dict(profiles[active_idx])

    measures = list(active_prof.get("measures", []))
    num_m = min(len(measures), len(m_names))
    for i in range(num_m):
        m = dict(measures[i])
        if i < len(m_names) and m_names[i]:
            m["name"] = m_names[i]
        if i < len(m_labels) and m_labels[i] is not None:
            m["label"] = m_labels[i]
        if i < len(m_aggs) and m_aggs[i]:
            m["agg"] = m_aggs[i]
        if i < len(m_fields):
            f_val = m_fields[i]
            if not f_val or f_val == "*" or m.get("agg") == "count":
                m["field"] = None
            else:
                m["field"] = f_val
        if i < len(m_cmps) and m_cmps[i]:
            m["compare"] = m_cmps[i]
        if i < len(m_tols):
            tol_val = m_tols[i]
            m["tolerance"] = tol_val
        if i < len(m_rnds):
            rnd_val = m_rnds[i]
            m["round"] = rnd_val
        measures[i] = m

    active_prof["measures"] = measures
    if prof_filter is not None:
        active_prof["filters_expr"] = prof_filter
    if drilldown_val in ("NONE", "", None):
        active_prof["drilldown_to"] = None
    elif drilldown_val:
        active_prof["drilldown_to"] = drilldown_val

    profiles[active_idx] = active_prof
    cfg["profiles"] = profiles

    updated_sql = _render_profile_grouped_sql(cfg, active_prof.get("group_by", ["INVOICE_NO"]), measures)
    sql_ui = code_block(updated_sql, language="sql")

    return cfg, sql_ui


def _sync_db_source_filters_and_params(cfg: dict[str, Any]) -> None:
    """Đồng bộ filters và params tổng thể từ p_from, p_to, p_org và extra_filters."""
    db_spec = cfg.setdefault("db_source", {})
    p_from_col = ""
    p_to_col = ""
    p_org_col = ""
    p_org_default = ""

    for flt in db_spec.get("filters", []):
        if flt.get("param") == "p_from":
            p_from_col = flt.get("column", p_from_col)
        elif flt.get("param") == "p_to":
            p_to_col = flt.get("column", p_to_col)
        elif flt.get("param") == "p_org":
            p_org_col = flt.get("column", p_org_col)

    for p in db_spec.get("params", []):
        if p.get("name") == "p_org" and p.get("default"):
            p_org_default = str(p.get("default"))

    existing_suggest = {
        p.get("name"): p.get("suggest")
        for p in db_spec.get("params", [])
        if p.get("name") in ("p_from", "p_to") and p.get("suggest")
    }

    all_filters: list[dict[str, Any]] = [
        {"param": "p_from", "column": p_from_col, "op": ">=", "cast": "none"},
        {"param": "p_to", "column": p_to_col, "op": "<=", "cast": "none"},
        {"param": "p_org", "column": p_org_col, "op": "=", "cast": "none"},
    ]
    all_params: list[dict[str, Any]] = [
        {
            "name": "p_from",
            "type": "datetime",
            "source": "user",
            "label": "Từ ngày giờ",
            "required": True,
            "suggest": existing_suggest.get("p_from", "yesterday"),
        },
        {
            "name": "p_to",
            "type": "datetime",
            "source": "user",
            "label": "Đến ngày giờ",
            "required": True,
            "suggest": existing_suggest.get("p_to", "yesterday"),
        },
        {
            "name": "p_org",
            "type": "text",
            "source": "default",
            "default": p_org_default,
            "label": "Đơn vị",
            "required": True,
        },
    ]

    for ef in db_spec.get("extra_filters", []):
        p_name = ef.get("param")
        if p_name and p_name not in [f["param"] for f in all_filters]:
            all_filters.append(
                {
                    "param": p_name,
                    "column": ef.get("column", ""),
                    "op": ef.get("op", "="),
                    "cast": "none",
                    "skip_if_empty": True,
                }
            )
            all_params.append(
                {
                    "name": p_name,
                    "type": "text",
                    "source": "user",
                    "default": ef.get("default", ""),
                    "label": ef.get("label", p_name),
                    "required": False,
                }
            )

    db_spec["filters"] = all_filters
    db_spec["params"] = all_params


@callback(
    Output("wizard-db-filters-container", "children", allow_duplicate=True),
    Output("wizard-generated-sql-container", "children", allow_duplicate=True),
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input("wizard-add-param-btn", "n_clicks"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_add_filter_param(n_clicks: int | None, current_config: dict[str, Any] | None) -> Any:
    """Thêm một dòng tham số lọc mới vào bảng điều kiện lọc theo tham số."""
    if not n_clicks or not current_config:
        return dash.no_update, dash.no_update, dash.no_update

    cfg = dict(current_config)
    db_spec = cfg.setdefault("db_source", {})
    extra_filters = list(db_spec.get("extra_filters", []))

    db_cols_chips = db_spec.get("_columns") or []
    col_names = [c[0] for c in db_cols_chips] if db_cols_chips else ["INVOICE_STATUS"]
    default_col = "INVOICE_STATUS" if "INVOICE_STATUS" in col_names else (col_names[0] if col_names else "STATUS")

    new_idx = len(extra_filters) + 1
    new_param = {
        "param": f"p_param_{new_idx}",
        "column": default_col,
        "op": "=",
        "default": "",
        "label": f"Tham số {new_idx}",
    }
    extra_filters.append(new_param)
    db_spec["extra_filters"] = extra_filters

    _sync_db_source_filters_and_params(cfg)

    p_from_col = ""
    p_to_col = ""
    p_org_col = ""
    p_org_default = ""
    for flt in db_spec.get("filters", []):
        if flt.get("param") == "p_from":
            p_from_col = flt.get("column", p_from_col)
        elif flt.get("param") == "p_to":
            p_to_col = flt.get("column", p_to_col)
        elif flt.get("param") == "p_org":
            p_org_col = flt.get("column", p_org_col)
    for p in db_spec.get("params", []):
        if p.get("name") == "p_org" and p.get("default"):
            p_org_default = str(p.get("default"))

    table_name = db_spec.get("table", "")
    fields = cfg.get("fields", [])
    gen_sql = _render_generated_sql(table_name, fields, p_from_col, p_to_col, p_org_col, extra_filters)

    rendered_table = _render_filter_params_table(
        db_cols_chips, p_from_col, p_to_col, p_org_col, p_org_default, extra_filters
    )
    rendered_sql = code_block(gen_sql, language="sql")
    return rendered_table, rendered_sql, cfg


@callback(
    Output("wizard-db-filters-container", "children", allow_duplicate=True),
    Output("wizard-generated-sql-container", "children", allow_duplicate=True),
    Output("wizard-config-store", "data", allow_duplicate=True),
    Input({"type": "wizard-extra-param-del", "index": dash.ALL}, "n_clicks"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_delete_filter_param(n_clicks_list: list[int | None], current_config: dict[str, Any] | None) -> Any:
    """Xóa một dòng tham số lọc bổ sung."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered or not current_config:
        return dash.no_update, dash.no_update, dash.no_update

    # Chỉ xử lý khi có nút xóa thực sự được bấm (n_clicks > 0)
    if not any(bool(n and n > 0) for n in n_clicks_list):
        return dash.no_update, dash.no_update, dash.no_update

    trig = ctx_dash.triggered[0]
    trig_val = trig.get("value")
    if not trig_val or trig_val <= 0:
        return dash.no_update, dash.no_update, dash.no_update

    triggered = trig["prop_id"]
    import json

    try:
        trig_dict = json.loads(triggered.split(".")[0])
        del_index = trig_dict.get("index")
    except Exception:
        return dash.no_update, dash.no_update, dash.no_update

    if del_index is None:
        return dash.no_update, dash.no_update, dash.no_update

    cfg = dict(current_config)
    db_spec = cfg.setdefault("db_source", {})
    extra_filters = list(db_spec.get("extra_filters", []))
    if 0 <= del_index < len(extra_filters):
        extra_filters.pop(del_index)
    db_spec["extra_filters"] = extra_filters

    _sync_db_source_filters_and_params(cfg)

    db_cols_chips = db_spec.get("_columns") or []
    p_from_col = ""
    p_to_col = ""
    p_org_col = ""
    p_org_default = ""
    for flt in db_spec.get("filters", []):
        if flt.get("param") == "p_from":
            p_from_col = flt.get("column", p_from_col)
        elif flt.get("param") == "p_to":
            p_to_col = flt.get("column", p_to_col)
        elif flt.get("param") == "p_org":
            p_org_col = flt.get("column", p_org_col)
    for p in db_spec.get("params", []):
        if p.get("name") == "p_org" and p.get("default"):
            p_org_default = str(p.get("default"))

    table_name = db_spec.get("table", "")
    fields = cfg.get("fields", [])
    gen_sql = _render_generated_sql(table_name, fields, p_from_col, p_to_col, p_org_col, extra_filters)

    rendered_table = _render_filter_params_table(
        db_cols_chips, p_from_col, p_to_col, p_org_col, p_org_default, extra_filters
    )
    rendered_sql = code_block(gen_sql, language="sql")
    return rendered_table, rendered_sql, cfg


@callback(
    Output("wizard-config-store", "data", allow_duplicate=True),
    Output("wizard-generated-sql-container", "children", allow_duplicate=True),
    Input({"type": "wizard-extra-param-name", "index": dash.ALL}, "value"),
    Input({"type": "wizard-extra-param-col", "index": dash.ALL}, "value"),
    Input({"type": "wizard-extra-param-op", "index": dash.ALL}, "value"),
    Input({"type": "wizard-extra-param-val", "index": dash.ALL}, "value"),
    State("wizard-config-store", "data"),
    prevent_initial_call=True,
)
def handle_change_extra_filter_values(
    names: list[str | None],
    cols: list[str | None],
    ops: list[str | None],
    vals: list[str | None],
    current_config: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Cập nhật giá trị các trường của tham số lọc bổ sung khi người dùng chỉnh sửa."""
    if not current_config or not names:
        return dash.no_update, dash.no_update

    cfg = dict(current_config)
    db_spec = cfg.setdefault("db_source", {})
    extra_filters = list(db_spec.get("extra_filters", []))

    for idx, (p_name, p_col, p_op, p_val) in enumerate(zip(names, cols, ops, vals, strict=False)):
        if idx < len(extra_filters):
            clean_param = str(p_name or f"p_param_{idx + 1}").strip().lstrip(":")
            extra_filters[idx]["param"] = clean_param
            extra_filters[idx]["column"] = p_col or ""
            extra_filters[idx]["op"] = p_op or "="
            extra_filters[idx]["default"] = p_val or ""

    db_spec["extra_filters"] = extra_filters
    _sync_db_source_filters_and_params(cfg)

    table_name = db_spec.get("table", "")
    fields = cfg.get("fields", [])
    p_from_col = ""
    p_to_col = ""
    p_org_col = ""
    for flt in db_spec.get("filters", []):
        if flt.get("param") == "p_from":
            p_from_col = flt.get("column", p_from_col)
        elif flt.get("param") == "p_to":
            p_to_col = flt.get("column", p_to_col)
        elif flt.get("param") == "p_org":
            p_org_col = flt.get("column", p_org_col)

    gen_sql = _render_generated_sql(table_name, fields, p_from_col, p_to_col, p_org_col, extra_filters)
    return cfg, code_block(gen_sql, language="sql")
