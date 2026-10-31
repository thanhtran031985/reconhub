from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from pydantic import ValidationError

from app.core.context import Role
from app.core.session import get_current_ctx
from app.schemas.template_config import TemplateConfig
from app.services.template import get_template, save_draft_template
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
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
        return html.Div("Nội dung Bước 3: Nguồn DB (Đang hoàn thiện)")
    elif active_step == 3:
        return html.Div("Nội dung Bước 4: Profile so sánh (Đang hoàn thiện)")
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
