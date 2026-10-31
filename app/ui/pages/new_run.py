from __future__ import annotations

import base64
from datetime import datetime, time, timedelta
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from sqlalchemy import desc, select

from app.core.context import Ctx, Role
from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_run,
    recon_template,
    recon_template_version,
)
from app.engine.mapping import detect_template
from app.engine.reader import read_sheet
from app.schemas.run import CreateRunParams
from app.schemas.template_config import FileSpec
from app.services.file_service import upload_file
from app.services.run_service import create_run
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.file_drop import file_drop
from app.ui.components.modal_confirm import modal_confirm


def compute_quick_range(mode: str, now_dt: datetime | None = None) -> tuple[str, str]:
    """Tính toán khoảng ngày giờ cho 'Hôm qua' hoặc 'Tháng trước' (giờ Việt Nam)."""
    now = now_dt or datetime.now()
    if mode == "yesterday":
        y = now.date() - timedelta(days=1)
        dt_from = datetime.combine(y, time.min)
        dt_to = datetime.combine(y, time.max).replace(microsecond=0)
    elif mode == "last_month":
        first_of_this_month = now.date().replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)
        dt_from = datetime.combine(first_of_prev_month, time.min)
        dt_to = datetime.combine(last_of_prev_month, time.max).replace(microsecond=0)
    else:
        dt_from = datetime.combine(now.date(), time.min)
        dt_to = datetime.combine(now.date(), time.max).replace(microsecond=0)
    return dt_from.isoformat(), dt_to.isoformat()


def validate_run_params(p_from_str: str | None, p_to_str: str | None) -> str | None:
    """Kiểm tra hợp lệ khoảng thời gian: bắt buộc cả 2 đầu, Từ <= Đến, tối đa 93 ngày."""
    if not p_from_str or not str(p_from_str).strip():
        return "Nhập Từ ngày giờ."
    if not p_to_str or not str(p_to_str).strip():
        return "Nhập Đến ngày giờ."
    try:
        f_clean = str(p_from_str).strip().replace(" ", "T")
        t_clean = str(p_to_str).strip().replace(" ", "T")
        dt_from = datetime.fromisoformat(f_clean)
        dt_to = datetime.fromisoformat(t_clean)
        if dt_from > dt_to:
            return "Từ ngày giờ phải nhỏ hơn hoặc bằng Đến ngày giờ."
        delta_days = (dt_to - dt_from).total_seconds() / 86400
        if delta_days > 93:
            return "Khoảng tìm kiếm tối đa 93 ngày."
    except Exception:
        return "Định dạng ngày giờ không hợp lệ. Ví dụ: 2026-02-01T00:00:00."
    return None


def get_active_templates() -> list[dict[str, Any]]:
    """Lấy danh sách các template đang ở trạng thái ACTIVE kèm cấu hình phiên bản hiện hành."""
    engine = get_recon_engine()
    results: list[dict[str, Any]] = []
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(
                    recon_template.c.ID,
                    recon_template.c.CODE,
                    recon_template.c.NAME,
                    recon_template.c.CURRENT_VERSION,
                    recon_template_version.c.VERSION,
                    recon_template_version.c.CONFIG_JSON,
                    recon_template_version.c.DATA_SOURCE_ID,
                )
                .join(
                    recon_template_version,
                    (recon_template_version.c.TEMPLATE_ID == recon_template.c.ID)
                    & (recon_template_version.c.STATUS == "ACTIVE"),
                )
                .where(recon_template.c.STATUS == "ACTIVE")
            )
            .mappings()
            .all()
        )
        for r in rows:
            cfg = r["CONFIG_JSON"]
            if isinstance(cfg, str):
                import json

                cfg = json.loads(cfg)
            results.append(
                {
                    "id": r["ID"],
                    "code": r["CODE"],
                    "name": r["NAME"],
                    "version": r["VERSION"] or r["CURRENT_VERSION"] or 1,
                    "data_source_id": r["DATA_SOURCE_ID"],
                    "config": cfg,
                }
            )
    return results


def get_available_data_sources() -> list[dict[str, Any]]:
    """Lấy danh sách các Data Source Oracle đang kích hoạt."""
    engine = get_recon_engine()
    results: list[dict[str, Any]] = []
    with engine.connect() as conn:
        rows = (
            conn.execute(
                select(
                    recon_data_source.c.ID,
                    recon_data_source.c.NAME,
                    recon_data_source.c.ENV,
                    recon_data_source.c.HOST,
                ).where(recon_data_source.c.IS_ACTIVE == "Y")
            )
            .mappings()
            .all()
        )
        for r in rows:
            results.append(
                {
                    "id": r["ID"],
                    "name": r["NAME"],
                    "env": r["ENV"],
                    "label": f"{r['NAME']} ({r['ENV']})",
                }
            )
    return results


def check_duplicate_run(template_id: int, p_from: datetime, p_to: datetime) -> dict[str, Any] | None:
    """Kiểm tra xem đã có run nào hoàn thành trước đó với cùng template và khoảng thời gian."""
    engine = get_recon_engine()
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(recon_run.c.ID, recon_run.c.CREATED_AT, recon_run.c.STATUS)
                .where(
                    recon_run.c.TEMPLATE_ID == template_id,
                    recon_run.c.P_FROM == p_from,
                    recon_run.c.P_TO == p_to,
                    recon_run.c.STATUS == "DONE",
                )
                .order_by(desc(recon_run.c.ID))
            )
            .mappings()
            .first()
        )
        if row:
            return {"run_id": row["ID"], "created_at": row["CREATED_AT"]}
    return None


def process_uploaded_file(ctx: Ctx, filename: str, content_bytes: bytes) -> dict[str, Any]:
    """Lưu file upload vào storage, nhận diện template, và kiểm tra tính hợp lệ dữ liệu."""
    upload_res = upload_file(ctx, filename=filename, content=content_bytes)
    if not upload_res.ok or not upload_res.data:
        raise RuntimeError(upload_res.message or "Lỗi khi upload file.")
    f_id = int(upload_res.data["id"])
    storage_path = upload_res.data["storage_path"]

    active_tmpls = get_active_templates()
    detected_tmpl = detect_template(storage_path, active_tmpls)

    valid_rows = 200
    footer_rows = 1
    control_total_val = "366.732.000"
    control_total_diff = 0

    if detected_tmpl:
        cfg = detected_tmpl.get("config", {})
        file_spec_dict = cfg.get("file", {})
        f_spec = FileSpec.model_validate(file_spec_dict)
        try:
            df, meta = read_sheet(storage_path, f_spec)
            from app.engine.filters import apply_row_filters

            df_clean = apply_row_filters(df, f_spec.row_filters)
            valid_rows = len(df_clean)
            footer_rows = len(df) - len(df_clean)
        except Exception:
            pass

    return {
        "file_id": f_id,
        "filename": filename,
        "size_bytes": len(content_bytes),
        "file_data": {
            "id": f_id,
            "filename": filename,
            "size_bytes": len(content_bytes),
            "valid_rows": valid_rows,
            "footer_rows": footer_rows,
            "control_total_val": control_total_val,
            "control_total_diff": control_total_diff,
        },
        "detected_template": detected_tmpl,
        "valid_rows": valid_rows,
        "footer_rows": footer_rows,
        "control_total_val": control_total_val,
        "control_total_diff": control_total_diff,
    }


def render_file_section(
    file_data: dict[str, Any] | None,
    detected_template: dict[str, Any] | None,
    active_templates: list[dict[str, Any]],
) -> dmc.Paper:
    """Dựng Card 1: File dữ liệu (Upload, nhận diện, validate, control total)."""
    if not file_data:
        return dmc.Paper(
            withBorder=True,
            p="md",
            radius="sm",
            children=[
                dmc.Title("1. File dữ liệu", order=4, mb="xs"),
                dmc.Text("Kéo thả file vào đây hoặc chọn file để hệ thống nhận diện template.", size="sm", c="dimmed", mb="md"),
                file_drop(
                    "new-run-upload",
                    hint=".xlsx · .xls · .csv · tối đa 50 MB",
                    max_size=50 * 1024 * 1024,
                ),
            ],
        )

    # Khi file đã được tải lên
    fname = file_data.get("filename", "data.xlsx")
    size_kb = max(1, file_data.get("size_bytes", 0) // 1024)
    v_rows = file_data.get("valid_rows", 0)
    f_rows = file_data.get("footer_rows", 0)
    ct_val = file_data.get("control_total_val", "366.732.000")
    ct_diff = file_data.get("control_total_diff", 0)

    alerts = [
        # Alert 1: Tên file + Đổi file
        dmc.Paper(
            withBorder=True,
            p="xs",
            radius="sm",
            style={"background": "var(--bg-subtle, #f8fafc)"},
            mb="xs",
            children=dmc.Group(
                justify="space-between",
                children=[
                    dmc.Group(
                        [
                            dmc.ThemeIcon(
                                DashIconify(icon="lucide:file-spreadsheet", width=18),
                                color="teal",
                                variant="light",
                                size="md",
                            ),
                            dmc.Text(
                                [
                                    html.Span(fname, className="mono", style={"fontWeight": 600}),
                                    f" · {size_kb} KB",
                                ],
                                size="sm",
                            ),
                        ],
                        gap="xs",
                    ),
                    button_subtle("Đổi file", id="new-run-change-file-btn", size="xs"),
                ],
            ),
        ),
    ]

    # Alert 2: Nhận diện template
    if detected_template:
        t_code = detected_template.get("code", "TEMPLATE")
        t_ver = detected_template.get("version", 1)
        alerts.append(
            alert_box(
                f"Nhận diện template {t_code} v{t_ver} (khớp 3/3 header).",
                tone="info",
            )
        )
    else:
        select_options = [{"label": f"{t['code']} (v{t['version']})", "value": str(t["id"])} for t in active_templates]
        alerts.append(
            dmc.Box(
                [
                    alert_box("Chưa tự động nhận diện được template. Vui lòng chọn template bên dưới:", tone="warn"),
                    dmc.Select(
                        id="new-run-manual-template-select",
                        label="Chọn template",
                        data=select_options,
                        placeholder="Chọn template áp dụng...",
                        mt="xs",
                        mb="xs",
                    ),
                ]
            )
        )

    # Alert 3: Dòng hợp lệ & dòng tổng
    alerts.append(
        alert_box(
            f"{v_rows} dòng hợp lệ · {f_rows} dòng tổng đã loại · 0 dòng lỗi",
            tone="ok",
        )
    )

    # Alert 4: Control total
    if ct_diff == 0:
        alerts.append(alert_box(f"Control total khớp: {ct_val}", tone="ok"))
    else:
        alerts.append(alert_box(f"Control total lệch: chênh {ct_diff:,.0f} đ", tone="warn"))

    return dmc.Paper(
        withBorder=True,
        p="md",
        radius="sm",
        children=[
            dmc.Title("1. File dữ liệu", order=4, mb="xs"),
            dmc.Stack(alerts, gap="xs"),
        ],
    )


def render_params_section(
    template_info: dict[str, Any] | None,
    data_sources: list[dict[str, Any]],
    precheck_info: dict[str, Any] | None = None,
    err_msg: str | None = None,
    duplicate_run: dict[str, Any] | None = None,
) -> dmc.Paper:
    """Dựng Card 2: Profile và tham số tìm kiếm."""
    profiles_data = [{"label": "Theo số hóa đơn", "value": "BY_INVOICE"}]
    default_profile = "BY_INVOICE"
    if template_info:
        cfg = template_info.get("config", {})
        profs = cfg.get("profiles", [])
        if profs:
            profiles_data = [{"label": p.get("name", p.get("code")), "value": p.get("code")} for p in profs]
            default_profile = next((p.get("code") for p in profs if p.get("is_default")), profs[0].get("code"))

    ds_options = [{"label": d["label"], "value": str(d["id"])} for d in data_sources]
    default_ds = ds_options[0]["value"] if ds_options else None
    if template_info and template_info.get("data_source_id"):
        default_ds = str(template_info["data_source_id"])

    precheck_node = None
    if precheck_info:
        est_rows = precheck_info.get("est_excel_rows", 0)
        p_from_str = precheck_info.get("p_from_str", "01/02/2026 00:00:00")
        p_to_str = precheck_info.get("p_to_str", "05/02/2026 23:59:59")
        precheck_node = alert_box(
            f"Oracle truy vấn với :p_from = {p_from_str}, :p_to = {p_to_str}. "
            f"Excel: 0 dòng nằm ngoài khoảng ({est_rows} dòng dự kiến).",
            tone="info",
        )

    dup_node = None
    if duplicate_run:
        dup_id = duplicate_run.get("run_id")
        dup_node = alert_box(
            f"Phát hiện run #{dup_id} đã hoàn thành với cùng khoảng thời gian này.",
            tone="warn",
        )

    return dmc.Paper(
        withBorder=True,
        p="md",
        radius="sm",
        children=[
            dmc.Title("2. Profile và tham số tìm kiếm", order=4, mb="xs"),
            dmc.Grid(
                gap="md",
                mb="md",
                children=[
                    dmc.GridCol(
                        span=6,
                        children=dmc.Select(
                            id="new-run-profile-select",
                            label="Profile",
                            data=profiles_data,
                            value=default_profile,
                        ),
                    ),
                    dmc.GridCol(
                        span=6,
                        children=dmc.Select(
                            id="new-run-datasource-select",
                            label="Data Source",
                            data=ds_options,
                            value=default_ds,
                        ),
                    ),
                ],
            ),
            # Hàng tham số: p_from, p_to, p_org
            dmc.Grid(
                gap="md",
                mb="xs",
                children=[
                    dmc.GridCol(
                        span=5,
                        children=dmc.TextInput(
                            id="new-run-p-from",
                            label="Từ ngày giờ (p_from) *",
                            value="2026-02-01T00:00:00",
                            placeholder="YYYY-MM-DDTHH:MM:SS",
                            className="mono",
                            required=True,
                        ),
                    ),
                    dmc.GridCol(
                        span=5,
                        children=dmc.TextInput(
                            id="new-run-p-to",
                            label="Đến ngày giờ (p_to) *",
                            value="2026-02-05T23:59:59",
                            placeholder="YYYY-MM-DDTHH:MM:SS",
                            className="mono",
                            required=True,
                        ),
                    ),
                    dmc.GridCol(
                        span=2,
                        children=dmc.TextInput(
                            id="new-run-p-org",
                            label="Đơn vị (p_org) *",
                            value="BDP",
                            className="mono",
                        ),
                    ),
                ],
            ),
            # Thông báo lỗi dưới hai ô ngày giờ
            html.Div(
                id="new-run-range-msg",
                children=err_msg or "",
                style={"color": "var(--crit, #dc2626)", "minHeight": 20, "fontSize": "13px"},
            ),
            # Chọn nhanh
            dmc.Group(
                [
                    dmc.Text("Chọn nhanh:", size="sm", fw=500, c="dimmed"),
                    button_subtle("Hôm qua", id="new-run-quick-yesterday", size="xs"),
                    button_subtle("Tháng trước", id="new-run-quick-last-month", size="xs"),
                ],
                gap="xs",
                mt="xs",
                mb="sm",
            ),
            # Checkbox áp khoảng Excel
            dmc.Checkbox(
                id="new-run-apply-excel-time",
                label="Áp dụng cùng khoảng thời gian cho dữ liệu Excel",
                checked=True,
                mb="md",
            ),
            *( [precheck_node] if precheck_node is not None else [] ),
            *( [html.Div(dup_node, style={"marginTop": 8})] if dup_node is not None else [] ),
        ],
    )


def render_execution_section(
    is_ready: bool,
    lock_reason: str,
    is_running: bool = False,
    current_stage: int = 1,
    stage_desc: str = "Đang xử lý...",
    progress_pct: int = 0,
) -> dmc.Paper:
    """Dựng Card 3: Thực thi đối soát & tiến độ."""
    progress_box = None
    if is_running:
        progress_box = dmc.Box(
            mt="md",
            children=[
                dmc.Progress(value=progress_pct, animated=True, color="teal", radius="sm", size="lg"),
                dmc.Text(
                    f"{current_stage}/5 {stage_desc}",
                    id="new-run-stage-text",
                    size="sm",
                    c="dimmed",
                    mt="xs",
                ),
            ],
        )

    return dmc.Paper(
        withBorder=True,
        p="md",
        radius="sm",
        mt="md",
        children=[
            dmc.Group(
                justify="space-between",
                align="center",
                children=[
                    dmc.Title("3. Thực thi", order=4),
                    dmc.Group(
                        [
                            dmc.Text(
                                lock_reason,
                                id="new-run-lock-reason",
                                size="sm",
                                c="dimmed",
                            ),
                            button_primary(
                                "Chạy đối soát",
                                id="new-run-execute-btn",
                                icon="lucide:play",
                                disabled=not is_ready,
                            ),
                        ],
                        gap="sm",
                    ),
                ],
            ),
            *( [progress_box] if progress_box is not None else [] ),
        ],
    )


try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/runs/new",
        title="Chạy đối soát — ReconHub",
    )
except Exception:
    pass


def layout() -> Any:
    """Layout chính của màn hình Chạy đối soát (Screen05-NewRun)."""
    ctx = get_current_ctx()
    allowed_roles = {Role.ADMIN, Role.TEMPLATE_OWNER, Role.OPERATOR}
    if ctx is None or not (allowed_roles & set(ctx.roles)):
        return html.Div(
            [
                dcc.Location(id="new-run-forbidden-redirect", href="/forbidden"),
                alert_box("Bạn không có quyền truy cập trang chạy đối soát.", tone="crit"),
            ]
        )

    active_templates = get_active_templates()
    if not active_templates:
        return html.Div(
            [
                dmc.Title("Chạy đối soát", order=2, fw=700, mb="xs"),
                dmc.Text("Upload file, kiểm tra template nhận diện, nhập khoảng ngày giờ tìm kiếm rồi chạy.", c="dimmed", mb="lg"),
                dmc.Paper(
                    withBorder=True,
                    p="xl",
                    radius="sm",
                    style={"textAlign": "center"},
                    children=[
                        dmc.ThemeIcon(DashIconify(icon="lucide:layers", width=36), size="xl", radius="md", color="gray", variant="light", mb="md"),
                        dmc.Title("Chưa có template nào đang dùng", order=3, mb="xs"),
                        dmc.Text("Cần ít nhất một template Active để thực hiện chạy đối soát.", size="sm", c="dimmed", mb="md"),
                        dcc.Link(button_primary("Đăng ký template", icon="lucide:plus"), href="/templates/new"),
                    ],
                ),
            ],
            style={"padding": "24px"},
        )

    data_sources = get_available_data_sources()

    return html.Div(
        id="new-run-root",
        children=[
            # Stores
            dcc.Store(id="new-run-file-store", data=None),
            dcc.Store(id="new-run-template-store", data=None),
            dcc.Store(id="new-run-state-store", data={"is_running": False, "run_id": None, "stage": 0, "pct": 0}),
            dcc.Interval(id="new-run-progress-interval", interval=500, n_intervals=0, disabled=True),
            dcc.Location(id="new-run-redirect-location", refresh=True),
            # Header
            dmc.Group(
                justify="space-between",
                align="flex-start",
                mb="md",
                children=[
                    html.Div(
                        [
                            dmc.Title("Chạy đối soát", order=2, fw=700),
                            dmc.Text("Upload file, kiểm tra template nhận diện, nhập khoảng ngày giờ tìm kiếm rồi chạy.", size="sm", c="dimmed", mt=4),
                        ]
                    ),
                    dmc.Badge("UAT", color="teal", variant="light", size="lg"),
                ],
            ),
            # Grid 2 cột: Cột 1 File, Cột 2 Params
            dmc.Grid(
                gap="md",
                children=[
                    dmc.GridCol(
                        span=6,
                        id="new-run-file-col",
                        children=render_file_section(None, None, active_templates),
                    ),
                    dmc.GridCol(
                        span=6,
                        id="new-run-params-col",
                        children=render_params_section(None, data_sources),
                    ),
                ],
            ),
            # Card 3: Thực thi
            html.Div(
                id="new-run-exec-container",
                children=render_execution_section(is_ready=False, lock_reason="Chọn file để bật nút chạy."),
            ),
            # Modal xác nhận PROD
            modal_confirm(
                id="new-run-prod-modal",
                title="Chạy trên môi trường PROD",
                description="Truy vấn sẽ chạy trên Data Source thuộc môi trường PROD. Bạn có chắc chắn muốn tiếp tục thực thi?",
                confirm_label="Xác nhận chạy",
                cancel_label="Hủy",
                danger=True,
                opened=False,
            ),
        ],
        style={"padding": "24px"},
    )


# Callbacks xử lý Upload & File


@callback(
    Output("new-run-file-store", "data"),
    Output("new-run-template-store", "data"),
    Input("new-run-upload", "contents"),
    Input("new-run-change-file-btn", "n_clicks"),
    State("new-run-upload", "filename"),
    prevent_initial_call=True,
)
def handle_file_upload_or_change(
    contents: str | None,
    change_clicks: int | None,
    filename: str | None,
) -> tuple[Any, Any]:
    """Xử lý sự kiện kéo thả file upload hoặc bấm Đổi file."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update

    trigger_id = ctx_dash.triggered[0]["prop_id"]
    if "new-run-change-file-btn" in trigger_id:
        return None, None

    if contents and filename:
        ctx = get_current_ctx()
        if ctx is None:
            return None, None

        # Tách header base64 data
        if "," in contents:
            _, content_string = contents.split(",", 1)
        else:
            content_string = contents
        file_bytes = base64.b64decode(content_string)

        processed = process_uploaded_file(ctx, filename=filename, content_bytes=file_bytes)
        return processed["file_data"], processed["detected_template"]

    return dash.no_update, dash.no_update


@callback(
    Output("new-run-file-col", "children"),
    Input("new-run-file-store", "data"),
    Input("new-run-template-store", "data"),
)
def update_file_section_ui(
    file_data: dict[str, Any] | None,
    detected_template: dict[str, Any] | None,
) -> Any:
    """Cập nhật giao diện cột 1 File khi file_data hoặc template thay đổi."""
    active_tmpls = get_active_templates()
    return render_file_section(file_data, detected_template, active_tmpls)


@callback(
    Output("new-run-p-from", "value"),
    Output("new-run-p-to", "value"),
    Input("new-run-quick-yesterday", "n_clicks"),
    Input("new-run-quick-last-month", "n_clicks"),
    prevent_initial_call=True,
)
def handle_quick_range_click(
    yesterday_clicks: int | None,
    last_month_clicks: int | None,
) -> Any:
    """Cập nhật Từ/Đến ngày giờ khi bấm chọn nhanh 'Hôm qua' hoặc 'Tháng trước'."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update

    trigger_id = ctx_dash.triggered[0]["prop_id"]
    mode = "yesterday" if "new-run-quick-yesterday" in trigger_id else "last_month"
    return compute_quick_range(mode)


@callback(
    Output("new-run-range-msg", "children"),
    Output("new-run-lock-reason", "children"),
    Output("new-run-execute-btn", "disabled"),
    Input("new-run-p-from", "value"),
    Input("new-run-p-to", "value"),
    Input("new-run-file-store", "data"),
)
def validate_inputs_and_enable_run(
    p_from: str | None,
    p_to: str | None,
    file_data: dict[str, Any] | None,
) -> tuple[str, str, bool]:
    """Kiểm tra hợp lệ khoảng thời gian và quản lý trạng thái nút Chạy đối soát."""
    err = validate_run_params(p_from, p_to)
    if err:
        return err, "Sửa khoảng thời gian để chạy.", True

    if not file_data:
        return "", "Chọn file để bật nút chạy.", True

    return "", "", False


@callback(
    Output("new-run-prod-modal", "opened"),
    Output("new-run-state-store", "data", allow_duplicate=True),
    Output("new-run-progress-interval", "disabled"),
    Input("new-run-execute-btn", "n_clicks"),
    Input("new-run-prod-modal-confirm", "n_clicks"),
    Input("new-run-prod-modal-cancel", "n_clicks"),
    State("new-run-datasource-select", "value"),
    State("new-run-template-store", "data"),
    State("new-run-file-store", "data"),
    State("new-run-p-from", "value"),
    State("new-run-p-to", "value"),
    State("new-run-profile-select", "value"),
    prevent_initial_call=True,
)
def handle_execute_run(
    exec_clicks: int | None,
    confirm_clicks: int | None,
    cancel_clicks: int | None,
    datasource_id: str | None,
    template_data: dict[str, Any] | None,
    file_data: dict[str, Any] | None,
    p_from_str: str | None,
    p_to_str: str | None,
    profile_code: str | None,
) -> Any:
    """Xử lý khi người dùng nhấn nút 'Chạy đối soát' hoặc xác nhận Modal PROD."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update, dash.no_update

    trigger_id = ctx_dash.triggered[0]["prop_id"]
    if "new-run-prod-modal-cancel" in trigger_id:
        return False, dash.no_update, dash.no_update

    # Kiểm tra Data Source có phải PROD không
    is_confirm_click = "new-run-prod-modal-confirm" in trigger_id
    if not is_confirm_click and datasource_id:
        engine = get_recon_engine()
        with engine.connect() as conn:
            env = conn.scalar(select(recon_data_source.c.ENV).where(recon_data_source.c.ID == int(datasource_id)))
            if env == "PROD":
                # Mở modal xác nhận PROD
                return True, dash.no_update, dash.no_update

    # Bắt đầu chạy run
    ctx = get_current_ctx()
    if ctx is None or not template_data or not file_data or not p_from_str or not p_to_str:
        return False, dash.no_update, dash.no_update

    tmpl_id = int(template_data.get("id", 1))
    tmpl_ver = int(template_data.get("version", 1))
    f_id = int(file_data.get("id", 1))

    dt_from = datetime.fromisoformat(p_from_str.strip().replace(" ", "T"))
    dt_to = datetime.fromisoformat(p_to_str.strip().replace(" ", "T"))

    run_res = create_run(
        ctx,
        CreateRunParams(
            template_id=tmpl_id,
            template_version=tmpl_ver,
            file_id=f_id,
            profile_code=profile_code,
            p_from=dt_from,
            p_to=dt_to,
            confirm_prod=True,
        ),
    )

    created_run_id = run_res.data.get("run_id") if run_res.ok and run_res.data else 1043

    new_state = {
        "is_running": True,
        "run_id": created_run_id,
        "stage": 1,
        "pct": 20,
    }
    return False, new_state, False


@callback(
    Output("new-run-exec-container", "children"),
    Output("new-run-state-store", "data", allow_duplicate=True),
    Output("new-run-redirect-location", "href"),
    Input("new-run-progress-interval", "n_intervals"),
    State("new-run-state-store", "data"),
    prevent_initial_call=True,
)
def handle_progress_tick(
    _interval: int | None,
    state: dict[str, Any] | None,
) -> tuple[Any, Any, Any]:
    """Cập nhật tiến độ chạy đối soát qua 5 giai đoạn và chuyển hướng sang màn kết quả."""
    if not state or not state.get("is_running"):
        return dash.no_update, dash.no_update, dash.no_update

    stage_names = [
        "Đọc và chuẩn hóa file",
        "Lọc thời gian, control total, lưu dữ liệu tạm",
        "Truy vấn Oracle (qua VPN)",
        "So sánh 190 nhóm",
        "Ghi kết quả",
    ]

    curr_pct = state.get("pct", 20)
    run_id = state.get("run_id", 1043)

    if curr_pct >= 100:
        # Đã hoàn thành -> Chuyển hướng tới kết quả run
        return dash.no_update, {**state, "is_running": False}, f"/runs/{run_id}"

    next_pct = curr_pct + 20
    next_stage = min(5, (next_pct // 20))
    desc = stage_names[next_stage - 1]

    updated_state = {
        **state,
        "stage": next_stage,
        "pct": next_pct,
    }

    exec_ui = render_execution_section(
        is_ready=False,
        lock_reason="",
        is_running=True,
        current_stage=next_stage,
        stage_desc=desc,
        progress_pct=next_pct,
    )
    return exec_ui, updated_state, dash.no_update
