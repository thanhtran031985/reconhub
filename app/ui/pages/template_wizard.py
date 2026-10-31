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
