from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from pydantic import ValidationError

from app.core.context import Role
from app.core.session import get_current_ctx
from app.schemas.template_config import TemplateConfig
from app.services.template import get_template, save_draft_template
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.code_block import code_block
from app.ui.components.file_drop import file_drop


def render_step_1(
    config: dict[str, Any],
    preview_rows: list[dict[str, Any]] | None = None,
) -> Any:
    """Dựng giao diện Bước 1: File mẫu & cấu trúc file."""
    file_spec = config.get("file", {})
    sheet_val = file_spec.get("sheet", "BÁO CÁO DTP")
    header_row_val = file_spec.get("header_row", 1)
    data_start_row_val = file_spec.get("data_start_row", 2)
    detect_headers = file_spec.get("detect_by_headers", ["Số hóa đơn", "Ngày lập hóa đơn", "Thành tiền"])

    # 5 dòng mẫu mặc định nếu chưa có file upload thực tế
    sample_preview = preview_rows or [
        {
            "STT": "1",
            "Điểm thu phí": "BDP-SMP",
            "Mã giao dịch": "PAYMENTGW-GMDBDP-10456c031199",
            "Số hóa đơn": "C26TBD0031335",
            "Trạng thái": "HĐ Gốc",
            "Ngày lập hóa đơn": "01/02/2026 00:00:00",
            "Số PIN": "BDP2600130495",
            "Mã dịch vụ": "NR",
            "Dịch vụ": "Phí nâng container rỗng thường",
            "Số lượng": "1",
            "Thành tiền": "1620000",
        },
        {
            "STT": "2",
            "Điểm thu phí": "BD5-SMP",
            "Mã giao dịch": "2062699179",
            "Số hóa đơn": "C26TBD0031336",
            "Trạng thái": "HĐ Gốc",
            "Ngày lập hóa đơn": "01/02/2026 01:07:13",
            "Số PIN": "BDP2600126062",
            "Mã dịch vụ": "NH",
            "Dịch vụ": "Phí nâng hàng container thường",
            "Số lượng": "1",
            "Thành tiền": "1458000",
        },
        {
            "STT": "3",
            "Điểm thu phí": "BD6-SMP",
            "Mã giao dịch": "2062699216",
            "Số hóa đơn": "C26TBD0031337",
            "Trạng thái": "HĐ Gốc",
            "Ngày lập hóa đơn": "01/02/2026 02:14:26",
            "Số PIN": "BDP2600136463",
            "Mã dịch vụ": "NR",
            "Dịch vụ": "Phí nâng container rỗng lạnh",
            "Số lượng": "1",
            "Thành tiền": "2592000",
        },
        {
            "STT": "4",
            "Điểm thu phí": "SDC-SMP",
            "Mã giao dịch": "2062699253",
            "Số hóa đơn": "C26TBD0031338",
            "Trạng thái": "HĐ Gốc",
            "Ngày lập hóa đơn": "01/02/2026 03:21:39",
            "Số PIN": "BDP2600144597",
            "Mã dịch vụ": "NR",
            "Dịch vụ": "Phí nâng container rỗng lạnh",
            "Số lượng": "1",
            "Thành tiền": "2592000",
        },
        {
            "STT": "5",
            "Điểm thu phí": "BDP-SMP",
            "Mã giao dịch": "2062699290",
            "Số hóa đơn": "C26TBD0031339",
            "Trạng thái": "HĐ Gốc",
            "Ngày lập hóa đơn": "01/02/2026 04:28:52",
            "Số PIN": "BDP2600144118",
            "Mã dịch vụ": "NR",
            "Dịch vụ": "Phí nâng container rỗng lạnh",
            "Số lượng": "1",
            "Thành tiền": "2592000",
        },
    ]

    preview_headers = list(sample_preview[0].keys())
    th_cells = [
        html.Th(
            h,
            style={
                "padding": "8px 12px",
                "fontSize": "13px",
                "textAlign": "right" if h in ("STT", "Số lượng", "Thành tiền") else "left",
            },
        )
        for h in preview_headers
    ]
    tb_rows = []
    for r in sample_preview:
        td_cells = [
            html.Td(
                html.Span(
                    r.get(h, ""),
                    className="mono" if h in ("Mã giao dịch", "Số hóa đơn", "Số PIN") else "",
                ),
                style={
                    "padding": "8px 12px",
                    "fontSize": "13px",
                    "textAlign": "right" if h in ("STT", "Số lượng", "Thành tiền") else "left",
                },
            )
            for h in preview_headers
        ]
        tb_rows.append(html.Tr(td_cells, style={"borderBottom": "1px solid var(--border-subtle, #e2e8f0)"}))

    return html.Div(
        [
            # Hàng trên: 2 cột
            dmc.Grid(
                gap="lg",
                children=[
                    # Cột 1: File mẫu & cấu trúc
                    dmc.GridCol(
                        span=6,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                dmc.Title("File mẫu", order=4, mb="sm"),
                                file_drop(
                                    id="wizard-file-drop",
                                    label="dtp_sample_200.xlsx",
                                    hint="Kéo thả file khác để thay thế (tối đa 50MB)",
                                ),
                                dmc.Grid(
                                    gap="sm",
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
                                    [dmc.Badge(h, variant="light", color="gray", radius="sm") for h in detect_headers],
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
                                alert_box("19 cột, 200 dòng dữ liệu.", tone="ok"),
                                html.Div(style={"height": 8}),
                                alert_box(
                                    "Dòng cuối là dòng tổng (Dịch vụ = 'Tổng tiền', Thành tiền = 366.732.000). "
                                    "Đề xuất loại khỏi dữ liệu và dùng làm control total.",
                                    tone="warn",
                                ),
                                html.Div(style={"height": 8}),
                                alert_box(
                                    "'Số hóa đơn' có 190 giá trị khác nhau trên 200 dòng: đề xuất so ở mức gộp theo hóa đơn.",
                                    tone="info",
                                ),
                                html.Div(style={"height": 8}),
                                alert_box(
                                    "'Mã giao dịch' lẫn số và chuỗi (PAYMENTGW-…): đọc dạng Text để không mất dữ liệu.",
                                    tone="info",
                                ),
                                dmc.Checkbox(
                                    id="wizard-apply-suggestions",
                                    label="Áp dụng các đề xuất",
                                    checked=True,
                                    mt="md",
                                ),
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

        tr = html.Tr(
            [
                html.Td(dmc.Checkbox(checked=is_used, size="xs"), style={"padding": "8px 10px"}),
                html.Td(html.B(f_excel or f_name), style={"padding": "8px 10px"}),
                html.Td(
                    dmc.TextInput(
                        value=f_name,
                        size="xs",
                        className="mono",
                        style={"width": 150},
                        error=errors[err_key] if has_err and errors else None,
                    ),
                    style={"padding": "8px 10px"},
                ),
                html.Td(
                    dmc.TextInput(value=f_label, size="xs", style={"width": 150}),
                    style={"padding": "8px 10px"},
                ),
                html.Td(
                    dmc.Select(
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
                html.Td(html.Span("—", className="mono", style={"color": "dimmed"}), style={"padding": "8px 10px"}),
            ],
            style={"opacity": 1.0 if is_used else 0.5, "borderBottom": "1px solid var(--border-subtle, #e2e8f0)"},
        )
        rows.append(tr)

    # Derived fields
    for d in derived_list:
        d_name = d.get("name", "")
        d_label = d.get("label", "")
        d_type = d.get("type", "date")
        expr_str = f"derived: {d.get('expr', {}).get('fn', '')}"
        tr = html.Tr(
            [
                html.Td(dmc.Checkbox(checked=True, size="xs"), style={"padding": "8px 10px"}),
                html.Td(html.B(expr_str), style={"padding": "8px 10px"}),
                html.Td(
                    dmc.TextInput(value=d_name, size="xs", className="mono", style={"width": 150}),
                    style={"padding": "8px 10px"},
                ),
                html.Td(
                    dmc.TextInput(value=d_label, size="xs", style={"width": 150}),
                    style={"padding": "8px 10px"},
                ),
                html.Td(
                    dmc.Select(
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
                html.Td(dmc.Badge("derived", size="xs", variant="light", color="purple"), style={"padding": "8px 10px"}),
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
                            button_subtle("Trường dẫn xuất", id="wizard-add-derived-btn", icon="lucide:plus", size="sm"),
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


def render_step_3(
    config: dict[str, Any],
    _errors: dict[str, str] | None = None,
) -> Any:
    """Dựng giao diện Bước 3: Nguồn dữ liệu DB & Điều kiện lọc."""
    db_spec = config.get("db_source", {})
    source_id = db_spec.get("source_id", "ORACLE_TEST")
    mode_val = db_spec.get("kind", "table")
    table_name = db_spec.get("table", "RECON_SRC.SRC_FACT_INVOICE_DTP")
    pushdown = db_spec.get("pushdown_aggregate", True)

    generated_sql = (
        'SELECT "INVOICE_NO", "INVOICE_DATE", "COLLECT_POINT", "TXN_ID", "PIN_NO",\n'
        '       "SERVICE_CODE", "QUANTITY", "AMOUNT", "INVOICE_STATUS"\n'
        'FROM   "RECON_SRC"."SRC_FACT_INVOICE_DTP"\n'
        "WHERE  \"INVOICE_DATE\" >= :p_from\n"
        "AND    \"INVOICE_DATE\" <= :p_to\n"
        'AND    "ORG_CODE" = :p_org'
    )

    db_cols_chips = [
        ("INVOICE_NO", "VARCHAR2(30)"),
        ("INVOICE_DATE", "DATE"),
        ("COLLECT_POINT", "VARCHAR2(20)"),
        ("TXN_ID", "VARCHAR2(80)"),
        ("PIN_NO", "VARCHAR2(30)"),
        ("SERVICE_CODE", "VARCHAR2(10)"),
        ("QUANTITY", "NUMBER(12,2)"),
        ("AMOUNT", "NUMBER(18,2)"),
        ("INVOICE_STATUS", "VARCHAR2(20)"),
        ("ORG_CODE", "VARCHAR2(10)"),
    ]

    # Mapping rows
    mapping_rows = []
    fields = config.get("fields", [])
    for f in fields:
        f_name = f.get("name", "")
        db_col = f.get("db")
        if db_col:
            status_badge = dmc.Badge("Đã map", size="xs", variant="light", color="green")
            col_type = "VARCHAR2" if "NO" in db_col or "ID" in db_col or "CODE" in db_col else ("DATE" if "DATE" in db_col else "NUMBER")
        else:
            status_badge = dmc.Badge("Chỉ có ở Excel", size="xs", variant="light", color="yellow")
            col_type = "—"

        mapping_rows.append(
            html.Tr(
                [
                    html.Td(html.Span(f_name, className="mono"), style={"padding": "8px 10px"}),
                    html.Td(
                        dmc.Select(
                            value=db_col or "— Không có —",
                            size="xs",
                            className="mono",
                            data=[{"label": c[0], "value": c[0]} for c in db_cols_chips] + [{"label": "— Không có —", "value": "— Không có —"}],
                            style={"width": 170},
                        ),
                        style={"padding": "8px 10px"},
                    ),
                    html.Td(html.Span(col_type, className="mono"), style={"padding": "8px 10px"}),
                    html.Td(status_badge, style={"padding": "8px 10px"}),
                ],
                style={"borderBottom": "1px solid var(--border-subtle, #e2e8f0)"},
            )
        )

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
                                data=[{"label": f"{source_id} (DEV) – chỉ đọc", "value": source_id}],
                                value=source_id,
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
                gap="md",
                mb="md",
                children=[
                    # Cột trái: Bảng/View nguồn
                    dmc.GridCol(
                        span=5,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                dmc.Title("Bảng/View nguồn", order=4, mb="sm"),
                                dmc.TextInput(
                                    id="wizard-input-table",
                                    label="Bảng/View *",
                                    value=table_name,
                                    className="mono",
                                    description="Gõ để tìm trong schema mặc định hoặc nhập SCHEMA.TÊN_BẢNG. Đã tải 10 cột.",
                                ),
                                dmc.Text("Cột bảng nguồn", size="xs", fw=600, mt="md", mb=6),
                                dmc.Group(
                                    [
                                        dmc.Badge(f"{col} ({t})", size="xs", variant="light", color="gray", radius="sm")
                                        for col, t in db_cols_chips
                                    ],
                                    gap=4,
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
                                dmc.Table(
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
                                                ],
                                                style={"background": "var(--bg-subtle, #f8fafc)"},
                                            )
                                        ),
                                        html.Tbody(
                                            [
                                                html.Tr(
                                                    [
                                                        html.Td([html.B("Từ ngày giờ "), html.Span("p_from *", className="mono")]),
                                                        html.Td(dmc.Select(value="INVOICE_DATE", data=["INVOICE_DATE"], size="xs", className="mono")),
                                                        html.Td(html.Span(">=", className="mono")),
                                                        html.Td("Ngày giờ"),
                                                        html.Td("Hôm qua 00:00:00"),
                                                    ]
                                                ),
                                                html.Tr(
                                                    [
                                                        html.Td([html.B("Đến ngày giờ "), html.Span("p_to *", className="mono")]),
                                                        html.Td(dmc.Select(value="INVOICE_DATE", data=["INVOICE_DATE"], size="xs", className="mono")),
                                                        html.Td(html.Span("<=", className="mono")),
                                                        html.Td("Ngày giờ"),
                                                        html.Td("Hôm qua 23:59:59"),
                                                    ]
                                                ),
                                                html.Tr(
                                                    [
                                                        html.Td([html.B("Đơn vị "), html.Span("p_org *", className="mono")]),
                                                        html.Td(dmc.Select(value="ORG_CODE", data=["ORG_CODE"], size="xs", className="mono")),
                                                        html.Td(html.Span("=", className="mono")),
                                                        html.Td("—"),
                                                        html.Td(dmc.TextInput(value="BDP", size="xs", className="mono", style={"width": 80})),
                                                    ]
                                                ),
                                            ]
                                        ),
                                    ],
                                ),
                                button_subtle("Thêm tham số lọc", id="wizard-add-param-btn", icon="lucide:plus", size="xs", mt="xs"),
                                dmc.Title("Điều kiện cố định", order=5, mt="md", mb="xs"),
                                dmc.Group(
                                    [
                                        html.Span("INVOICE_STATUS", className="mono"),
                                        html.Span("="),
                                        dmc.TextInput(value="ORIGINAL", size="xs", className="mono", style={"width": 160}),
                                        button_subtle("Thêm điều kiện", id="wizard-add-filter-btn", icon="lucide:plus", size="xs"),
                                    ],
                                    gap="sm",
                                ),
                            ],
                        ),
                    ),
                ],
            ),
            # Card 3: Câu SELECT sinh ra (chỉ đọc)
            dmc.Paper(
                withBorder=True,
                p="md",
                radius="sm",
                mb="md",
                children=[
                    dmc.Title("Câu SELECT sinh ra (chỉ đọc)", order=4, mb="xs"),
                    code_block(generated_sql, language="sql"),
                ],
            ),
            # Card 4: Cột DB -> Trường logic & Lọc Excel theo cùng khoảng
            dmc.Grid(
                gap="md",
                children=[
                    dmc.GridCol(
                        span=7,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                dmc.Title("Cột DB → Trường logic", order=4, mb="sm"),
                                dmc.Table(
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
                                        html.Tbody(mapping_rows),
                                    ],
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
                                    "Cùng khoảng áp cho DB (cột INVOICE_DATE) và Excel.",
                                    tone="info",
                                ),
                                html.Div(style={"height": 12}),
                                dmc.Select(
                                    id="wizard-excel-time-field",
                                    label="Trường thời gian lọc Excel",
                                    data=[{"label": "INV_DATETIME", "value": "INV_DATETIME"}, {"label": "Không lọc Excel", "value": "NONE"}],
                                    value="INV_DATETIME",
                                    mb="sm",
                                ),
                                dmc.Select(
                                    id="wizard-excel-suggest-range",
                                    label="Gợi ý khi chạy",
                                    data=[{"label": "Hôm qua", "value": "yesterday"}, {"label": "Tháng trước", "value": "last_month"}, {"label": "Để trống", "value": "none"}],
                                    value="yesterday",
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        ]
    )


def render_step_4(
    config: dict[str, Any],
    _selected_profile_code: str | None = None,
) -> Any:
    """Dựng giao diện Bước 4: Hồ sơ đối soát (Profile so sánh) & Measures."""
    profiles = config.get("profiles", [])
    active_prof = profiles[0] if profiles else {
        "code": "BY_INVOICE",
        "name": "Theo số hóa đơn",
        "group_by": ["INVOICE_NO"],
        "measures": [],
    }

    # Danh sách trường có sẵn (cả fields và derived)
    avail_fields = [f.get("name") for f in config.get("fields", []) if f.get("name")]
    avail_fields += [d.get("name") for d in config.get("derived", []) if d.get("name")]
    if not avail_fields:
        avail_fields = ["INVOICE_NO", "INV_DATE", "POINT", "TXN_ID", "PIN", "SERVICE_CODE", "STATUS", "QTY", "AMOUNT"]

    # Nhóm Group by chips
    group_by_cols = active_prof.get("group_by", ["INVOICE_NO"])
    group_by_chips = [
        dmc.Badge(
            g,
            size="sm",
            variant="filled",
            color="primary",
            leftSection=DashIconify(icon="lucide:key", width=14),
            radius="sm",
        )
        for g in group_by_cols
    ]

    # Bảng Measures
    measures = active_prof.get("measures", [
        {"name": "TOTAL_AMOUNT", "label": "Tổng tiền", "agg": "sum", "field": "AMOUNT", "compare": "abs_tol", "tolerance": 1, "round": 0},
        {"name": "TOTAL_QTY", "label": "Số lượng", "agg": "sum", "field": "QTY", "compare": "exact", "round": 0},
        {"name": "INV_DATE", "label": "Ngày HĐ", "agg": "first_distinct", "field": "INV_DATE", "compare": "exact"},
        {"name": "LINE_CNT", "label": "Số dòng", "agg": "count", "field": "*", "compare": "display_only"},
    ])

    measure_rows = []
    for m in measures:
        if not isinstance(m, dict):
            continue
        m_name = m.get("name", "")
        m_label = m.get("label", "")
        m_agg = m.get("agg", "sum")
        m_field = m.get("field", "")
        m_cmp = m.get("compare", "exact")
        m_tol = str(m.get("tolerance", "—"))
        m_round = str(m.get("round", "—"))
        is_main = m_name == active_prof.get("main_measure", "TOTAL_AMOUNT")

        measure_rows.append(
            html.Tr(
                [
                    html.Td(html.Span(m_name, className="mono"), style={"padding": "8px 10px"}),
                    html.Td(m_label, style={"padding": "8px 10px"}),
                    html.Td(dmc.Badge(m_agg, size="xs", variant="light", color="blue"), style={"padding": "8px 10px"}),
                    html.Td(html.Span(m_field, className="mono"), style={"padding": "8px 10px"}),
                    html.Td(m_cmp, style={"padding": "8px 10px"}),
                    html.Td(m_tol, style={"padding": "8px 10px", "textAlign": "right"}),
                    html.Td(m_round, style={"padding": "8px 10px", "textAlign": "right"}),
                    html.Td(
                        dmc.Badge("Chính", size="xs", variant="filled", color="info") if is_main else "",
                        style={"padding": "8px 10px"},
                    ),
                ],
                style={"borderBottom": "1px solid var(--border-subtle, #e2e8f0)"},
            )
        )

    # Generated Grouped SQL
    grouped_sql = (
        'SELECT UPPER(TRIM(src."INVOICE_NO"))            AS "K__INVOICE_NO",\n'
        '       SUM(src."AMOUNT")                        AS "M__TOTAL_AMOUNT",\n'
        '       SUM(src."QUANTITY")                      AS "M__TOTAL_QTY",\n'
        '       MIN(TRUNC(src."INVOICE_DATE"))           AS "M__INV_DATE",\n'
        '       COUNT(DISTINCT TRUNC(src."INVOICE_DATE")) AS "N__INV_DATE",\n'
        '       COUNT(*)                                 AS "M__LINE_CNT"\n'
        "FROM  ( <Câu SELECT sinh ra ở bước 3> ) src\n"
        'GROUP BY UPPER(TRIM(src."INVOICE_NO"))'
    )

    # Tab items cho profile
    tab_list = [
        dmc.TabsTab(p.get("name", p.get("code", "Profile")), value=p.get("code", "BY_INVOICE"))
        for p in profiles
    ]
    if not tab_list:
        tab_list = [dmc.TabsTab("Theo số hóa đơn (mặc định)", value="BY_INVOICE")]

    return html.Div(
        [
            # Profile tabs
            dmc.Tabs(
                id="wizard-profile-tabs",
                value=active_prof.get("code", "BY_INVOICE"),
                mb="md",
                children=[
                    dmc.TabsList(
                        [
                            *tab_list,
                            button_subtle("Thêm profile", id="wizard-add-profile-btn", icon="lucide:plus", size="xs"),
                        ]
                    )
                ],
            ),
            # Layout 2 cột: Cột trái Trường có sẵn (260px) vs Cột phải Cấu hình profile
            dmc.Grid(
                gap="md",
                children=[
                    # Cột trái: Trường có sẵn
                    dmc.GridCol(
                        span=3,
                        children=dmc.Paper(
                            withBorder=True,
                            p="md",
                            radius="sm",
                            children=[
                                dmc.Title("Trường có sẵn", order=4, mb="sm"),
                                html.Div(
                                    [
                                        dmc.Group(
                                            justify="space-between",
                                            py=4,
                                            children=[
                                                html.Span(f, className="mono", style={"fontSize": "13px"}),
                                                dmc.Group(
                                                    [
                                                        dmc.ActionIcon(
                                                            DashIconify(icon="lucide:key", width=14),
                                                            size="xs",
                                                            variant="subtle",
                                                            **{"aria-label": f"Thêm {f} vào Group by"},
                                                        ),
                                                        dmc.ActionIcon(
                                                            DashIconify(icon="lucide:sigma", width=14),
                                                            size="xs",
                                                            variant="subtle",
                                                            **{"aria-label": f"Thêm measure từ {f}"},
                                                        ),
                                                    ],
                                                    gap=2,
                                                ),
                                            ],
                                            style={"borderBottom": "1px solid var(--border-subtle, #f1f5f9)"},
                                        )
                                        for f in avail_fields
                                    ]
                                ),
                            ],
                        ),
                    ),
                    # Cột phải: Group by, Measures & SQL gộp
                    dmc.GridCol(
                        span=9,
                        children=html.Div(
                            [
                                # Card 1: Group by
                                dmc.Paper(
                                    withBorder=True,
                                    p="md",
                                    radius="sm",
                                    mb="md",
                                    children=[
                                        dmc.Title("Group by (khóa so sánh)", order=4, mb="xs"),
                                        dmc.Group(group_by_chips, gap="xs", mb="xs"),
                                        alert_box("200 dòng Excel → 190 nhóm theo (INVOICE_NO).", tone="info"),
                                    ],
                                ),
                                # Card 2: Measures và quy tắc so sánh
                                dmc.Paper(
                                    withBorder=True,
                                    p="md",
                                    radius="sm",
                                    mb="md",
                                    children=[
                                        dmc.Title("Measures và quy tắc so sánh", order=4, mb="sm"),
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
                                                            html.Th("Sai số", style={"textAlign": "right"}),
                                                            html.Th("Làm tròn", style={"textAlign": "right"}),
                                                            html.Th(""),
                                                        ],
                                                        style={"background": "var(--bg-subtle, #f8fafc)"},
                                                    )
                                                ),
                                                html.Tbody(measure_rows),
                                            ],
                                        ),
                                        dmc.Grid(
                                            gap="md",
                                            mt="md",
                                            children=[
                                                dmc.GridCol(
                                                    span=6,
                                                    children=dmc.TextInput(
                                                        id="wizard-profile-filter",
                                                        label="Bộ lọc profile (áp cả hai phía)",
                                                        placeholder="Ví dụ STATUS = ORIGINAL",
                                                        className="mono",
                                                    ),
                                                ),
                                                dmc.GridCol(
                                                    span=6,
                                                    children=dmc.Select(
                                                        id="wizard-drilldown-select",
                                                        label="Drill-down tới",
                                                        data=[{"label": "Chi tiết dòng", "value": "BY_LINE"}, {"label": "Không phân rã", "value": "NONE"}],
                                                        value="BY_LINE",
                                                    ),
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                # Card 3: SQL gộp sinh tự động (chỉ đọc)
                                dmc.Paper(
                                    withBorder=True,
                                    p="md",
                                    radius="sm",
                                    children=[
                                        dmc.Title("SQL gộp sinh tự động (chỉ đọc)", order=4, mb="xs"),
                                        code_block(grouped_sql, language="sql"),
                                    ],
                                ),
                            ]
                        ),
                    ),
                ],
            ),
        ]
    )

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


def build_default_config() -> dict[str, Any]:
    """Tạo cấu hình template mặc định rỗng để khởi tạo wizard mới."""
    return {
        "schema_version": 1,
        "file": {
            "sheet": "Sheet1",
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
                "code": "BY_DEFAULT",
                "name": "Mặc định",
                "is_default": True,
                "aggregate": True,
                "group_by": [],
                "measures": [],
                "filters": [],
            }
        ],
    }


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
    if template_id and str(template_id).isdigit():
        t_id_num = int(template_id)
        tmpl_res = get_template(ctx, t_id_num)
        if tmpl_res.ok and tmpl_res.data:
            tmpl_data = tmpl_res.data
            initial_config = tmpl_data.config.model_dump(mode="json")
            loaded_version = tmpl_data.active_version or 1

    t_code = initial_config.get("template_code", "NEW_TEMPLATE")
    ds_name = initial_config.get("db_source", {}).get("source_id", "—")
    tb_name = initial_config.get("db_source", {}).get("table", "—")
    subtitle_text = f"Bản nháp v{loaded_version} · Data Source {ds_name} · Bảng {tb_name}"

    return html.Div(
        id="wizard-page-root",
        children=[
            # Stores
            dcc.Store(id="wizard-config-store", data=initial_config),
            dcc.Store(
                id="wizard-meta-store",
                data={
                    "template_id": t_id_num,
                    "version": loaded_version,
                    "current_step": 1,
                    "is_dirty": False,
                    "last_saved_at": None,
                },
            ),
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
                                f"Đăng ký template: {t_code}",
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
    State("wizard-config-store", "data"),
)
def handle_render_step_content(active_step: int, config_data: dict[str, Any] | None) -> Any:
    """Hiển thị nội dung tương ứng theo bước hiện tại trên Stepper."""
    cfg = config_data or {}
    if active_step == 0:
        return render_step_1(cfg)
    elif active_step == 1:
        return render_step_2(cfg)
    elif active_step == 2:
        return render_step_3(cfg)
    elif active_step == 3:
        return render_step_4(cfg)
    elif active_step == 4:
        return html.Div("Nội dung Bước 5: Dry-run (Đang hoàn thiện)")
    return html.Div("Bước không xác định")


@callback(
    Output("wizard-stepper-box", "style"),
    Output("wizard-step-content", "style"),
    Output("wizard-diagram-content", "style"),
    Output("wizard-footer-nav", "style"),
    Input("wizard-view-tabs", "value"),
)
def handle_switch_tabs(tab_value: str | None) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    """Chuyển đổi giữa tab Cấu hình template và tab Sơ đồ diễn giải."""
    if tab_value == "diagram":
        return (
            {"display": "none"},
            {"display": "none"},
            {"display": "block"},
            {"display": "none"},
        )
    return (
        {"display": "block"},
        {"display": "block"},
        {"display": "none"},
        {"display": "flex"},
    )


@callback(
    Output("wizard-stepper", "active"),
    Output("wizard-prev-btn", "disabled"),
    Output("wizard-next-btn", "children"),
    Output("wizard-meta-store", "data", allow_duplicate=True),
    Input("wizard-next-btn", "n_clicks"),
    Input("wizard-prev-btn", "n_clicks"),
    State("wizard-stepper", "active"),
    State("wizard-meta-store", "data"),
    prevent_initial_call=True,
)
def handle_step_navigation(
    next_clicks: int | None,
    prev_clicks: int | None,
    current_active: int,
    meta: dict[str, Any] | None,
) -> Any:
    """Xử lý nút Tiếp và Quay lại trên Stepper 5 bước."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return current_active, current_active == 0, "Tiếp", meta or {}

    trigger = ctx_dash.triggered[0]["prop_id"]
    new_step = current_active
    if "wizard-next-btn" in trigger:
        if current_active < 4:
            new_step = current_active + 1
    elif "wizard-prev-btn" in trigger:
        if current_active > 0:
            new_step = current_active - 1

    next_btn_text = "Lưu & kích hoạt" if new_step == 4 else "Tiếp"
    updated_meta = {**(meta or {}), "current_step": new_step + 1}
    return new_step, (new_step == 0), next_btn_text, updated_meta


@callback(
    Output("wizard-header-subtitle", "children"),
    Output("wizard-meta-store", "data", allow_duplicate=True),
    Output("wizard-notification-container", "children"),
    Input("wizard-save-draft-btn", "n_clicks"),
    Input("wizard-autosave-interval", "n_intervals"),
    State("wizard-config-store", "data"),
    State("wizard-meta-store", "data"),
    prevent_initial_call=True,
)
def handle_save_or_autosave_draft(
    save_clicks: int | None,
    _interval: int | None,
    config_data: dict[str, Any] | None,
    meta_data: dict[str, Any] | None,
) -> Any:
    """Lưu nháp thủ công hoặc tự động qua timer định kỳ."""
    ctx = get_current_ctx()
    if ctx is None or not config_data:
        return dash.no_update, dash.no_update, dash.no_update

    ctx_dash = dash.callback_context
    triggered_id = ctx_dash.triggered[0]["prop_id"] if ctx_dash.triggered else ""
    is_manual = "wizard-save-draft-btn" in triggered_id

    is_dirty = meta_data.get("is_dirty", False) if meta_data else False
    if not is_manual and not is_dirty:
        # Nếu là autosave và không dirty thì bỏ qua
        return dash.no_update, dash.no_update, dash.no_update

    template_cfg, errors = form_state_to_config(config_data)
    if template_cfg is None:
        if is_manual:
            err_box = alert_box(f"Cấu hình chưa hợp lệ để lưu nháp: {errors}", tone="crit")
            return dash.no_update, dash.no_update, err_box
        return dash.no_update, dash.no_update, dash.no_update

    t_id = meta_data.get("template_id") if meta_data else None
    res = save_draft_template(
        ctx,
        code=template_cfg.template_code if hasattr(template_cfg, "template_code") else "TEMPLATE",
        name=template_cfg.name if hasattr(template_cfg, "name") else "Template",
        config=template_cfg,
        description=getattr(template_cfg, "description", None),
        row_version=meta_data.get("row_version") if meta_data else None,
    )
    if not res.ok:
        if is_manual:
            return dash.no_update, dash.no_update, alert_box(res.message, tone="crit")
        return dash.no_update, dash.no_update, dash.no_update

    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
    saved_meta = {
        **(meta_data or {}),
        "template_id": res.data.get("id") if res.data else t_id,
        "version": res.data.get("version", 1) if res.data else 1,
        "row_version": res.data.get("row_version") if res.data else None,
        "is_dirty": False,
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
