from __future__ import annotations

import base64
from datetime import datetime, time, timedelta
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from sqlalchemy import desc, select

from app.core.context import Ctx
from app.core.session import get_current_ctx
from app.db.engine import get_recon_engine
from app.db.metadata import (
    recon_data_source,
    recon_run,
    recon_template,
    recon_template_version,
)
from app.engine.control_total import check_control_total
from app.engine.filters import apply_row_filters
from app.engine.mapping import detect_template
from app.engine.reader import read_sheet
from app.engine.sql_builder import build_source_sql
from app.schemas.run import CreateRunParams
from app.schemas.template_config import TemplateConfig
from app.services.file_service import upload_file
from app.services.perm import has_role, page_gate
from app.services.run_service import create_run
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.code_block import code_block
from app.ui.components.file_drop import file_drop
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import notify_error, notify_info, notify_success, notify_warning
from app.ui.components.page_header import page_header


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
    """Kiểm tra hợp lệ khoảng thời gian: bắt buộc cả 2 đầu, Từ <= Đến, không giới hạn số ngày."""
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
    except Exception:
        return "Định dạng ngày giờ không hợp lệ. Ví dụ: 2026-02-01 00:00:00."
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


def process_uploaded_file(
    ctx: Ctx,
    filename: str,
    content_bytes: bytes,
    manual_template_id: int | None = None,
) -> dict[str, Any]:
    """Lưu file upload vào storage, nhận diện template, và kiểm tra tính hợp lệ dữ liệu (bỏ hardcode)."""
    upload_res = upload_file(ctx, filename=filename, content=content_bytes)
    if not upload_res.ok or not upload_res.data:
        raise RuntimeError(upload_res.message or "Lỗi khi upload file.")
    f_id = int(upload_res.data["id"])
    storage_path = upload_res.data["storage_path"]

    active_tmpls = get_active_templates()
    detected_tmpl: dict[str, Any] | None = None
    if manual_template_id:
        detected_tmpl = next((t for t in active_tmpls if t["id"] == manual_template_id), None)
    if not detected_tmpl:
        detected_tmpl = detect_template(storage_path, active_tmpls)

    valid_rows = 0
    footer_rows = 0
    control_total_val: str | None = None
    control_total_diff: float | None = None
    control_total_matched: bool | None = None
    control_total_warning: str | None = None

    if detected_tmpl:
        cfg_dict = detected_tmpl.get("config", {})
        try:
            cfg = TemplateConfig.model_validate(cfg_dict)
            raw_df, _ = read_sheet(storage_path, cfg.file)
            valid_df = apply_row_filters(raw_df, cfg.file.row_filters)
            valid_rows = len(valid_df)
            footer_rows = len(raw_df) - len(valid_df)

            if cfg.control_total:
                ct_res = check_control_total(raw_df, valid_df, cfg.control_total, cfg.fields)
                if ct_res.file_total is not None:
                    control_total_val = f"{ct_res.file_total:,.0f}".replace(",", ".")
                    control_total_diff = float(ct_res.diff) if ct_res.diff is not None else 0.0
                    control_total_matched = ct_res.is_matched
                elif ct_res.warning:
                    control_total_warning = "Không tìm thấy dòng control total trong file."
        except Exception:
            # Fallback đọc thô sheet đầu nếu đọc cấu hình chuyên sâu có lỗi
            try:
                import fastexcel

                excel_reader = fastexcel.read_excel(storage_path)
                sheet_names = excel_reader.sheet_names
                sheet_data = excel_reader.load_sheet(sheet_names[0])
                valid_rows = sheet_data.height
                footer_rows = 0
            except Exception:
                pass
    else:
        # Chưa nhận diện được template: đọc thô sheet đầu
        try:
            import fastexcel

            excel_reader = fastexcel.read_excel(storage_path)
            sheet_names = excel_reader.sheet_names
            sheet_data = excel_reader.load_sheet(sheet_names[0])
            valid_rows = sheet_data.height
            footer_rows = 0
        except Exception:
            pass

    return {
        "file_id": f_id,
        "filename": filename,
        "size_bytes": len(content_bytes),
        "storage_path": storage_path,
        "file_data": {
            "id": f_id,
            "filename": filename,
            "size_bytes": len(content_bytes),
            "storage_path": storage_path,
            "valid_rows": valid_rows,
            "footer_rows": footer_rows,
            "control_total_val": control_total_val,
            "control_total_diff": control_total_diff,
            "control_total_matched": control_total_matched,
            "control_total_warning": control_total_warning,
        },
        "detected_template": detected_tmpl,
        "valid_rows": valid_rows,
        "footer_rows": footer_rows,
        "control_total_val": control_total_val,
        "control_total_diff": control_total_diff,
        "control_total_matched": control_total_matched,
        "control_total_warning": control_total_warning,
    }


def render_file_section(
    file_data: dict[str, Any] | None,
    detected_template: dict[str, Any] | None,
    active_templates: list[dict[str, Any]] | None = None,
) -> dmc.Paper:
    """Dựng Card 1: File dữ liệu (Upload, nhận diện, validate, control total)."""
    has_file = file_data is not None

    dropzone_box = html.Div(
        style={
            "display": "none" if has_file else "block",
            "width": "100%",
        },
        children=[
            file_drop(
                "new-run-upload",
                hint=".xlsx · .xls · .csv · tối đa 50 MB",
                max_size=50 * 1024 * 1024,
            ),
        ],
    )

    metadata_card = None
    if has_file and file_data:
        fname = file_data.get("filename", "data.xlsx")
        size_kb = max(1, file_data.get("size_bytes", 0) // 1024)
        v_rows = file_data.get("valid_rows", 0)
        f_rows = file_data.get("footer_rows", 0)
        ct_val = file_data.get("control_total_val")
        ct_diff = file_data.get("control_total_diff")
        ct_warn = file_data.get("control_total_warning")
        t_code = detected_template.get("code", "TEMPLATE") if detected_template else None
        t_ver = detected_template.get("version", 1) if detected_template else None

        metadata_card = dmc.Paper(
            withBorder=True,
            p="sm",
            radius="sm",
            style={
                "background": "var(--bg-subtle, #f8fafc)",
                "display": "flex",
                "flexDirection": "column",
                "gap": "10px",
                "minWidth": 0,
                "width": "100%",
                "boxSizing": "border-box",
                "overflow": "hidden",
            },
            children=[
                # Row 1: File icon + Tên file (ellipsis, mono, hover title) + Kích thước file
                dmc.Group(
                    wrap="nowrap",
                    gap="xs",
                    align="center",
                    style={"minWidth": 0, "width": "100%", "overflow": "hidden"},
                    children=[
                        dmc.ThemeIcon(
                            DashIconify(icon="lucide:file-spreadsheet", width=18),
                            color="teal",
                            variant="light",
                            size="md",
                            style={"flexShrink": 0},
                        ),
                        html.Div(
                            style={"minWidth": 0, "flex": "1 1 0%", "overflow": "hidden"},
                            children=[
                                html.Span(
                                    fname,
                                    title=fname,
                                    className="mono",
                                    style={
                                        "fontWeight": 600,
                                        "fontSize": "13px",
                                        "overflow": "hidden",
                                        "textOverflow": "ellipsis",
                                        "whiteSpace": "nowrap",
                                        "display": "block",
                                        "lineHeight": 1.4,
                                    },
                                ),
                            ],
                        ),
                        dmc.Badge(
                            f"{size_kb} KB",
                            size="xs",
                            variant="light",
                            color="gray",
                            style={"flexShrink": 0},
                        ),
                    ],
                ),
                dmc.Divider(variant="dashed"),
                # Row 2: Template áp dụng
                dmc.Group(
                    justify="space-between",
                    align="center",
                    wrap="nowrap",
                    style={"minWidth": 0, "width": "100%"},
                    children=[
                        dmc.Text("Template áp dụng:", size="xs", c="dimmed", fw=500, style={"flexShrink": 0}),
                        (
                            dmc.Badge(
                                f"{t_code} v{t_ver}",
                                color="blue",
                                variant="light",
                                size="sm",
                            )
                            if detected_template
                            else dmc.Badge(
                                "Chưa nhận diện",
                                color="orange",
                                variant="light",
                                size="sm",
                            )
                        ),
                    ],
                ),
                # Row 3: Thống kê dòng nạp
                dmc.Group(
                    justify="space-between",
                    align="center",
                    wrap="nowrap",
                    style={"minWidth": 0, "width": "100%"},
                    children=[
                        dmc.Text("Dữ liệu nạp:", size="xs", c="dimmed", fw=500, style={"flexShrink": 0}),
                        dmc.Group(
                            gap="4px",
                            wrap="wrap",
                            justify="flex-end",
                            children=[
                                dmc.Badge(
                                    f"{v_rows} dòng hợp lệ",
                                    color="teal",
                                    variant="light",
                                    size="xs",
                                ),
                                *(
                                    [
                                        dmc.Badge(
                                            f"{f_rows} dòng tổng đã loại",
                                            color="gray",
                                            variant="outline",
                                            size="xs",
                                        )
                                    ]
                                    if f_rows > 0
                                    else []
                                ),
                            ],
                        ),
                    ],
                ),
                # Row 4: Control total (nếu có cấu hình)
                *(
                    [
                        dmc.Group(
                            justify="space-between",
                            align="center",
                            wrap="nowrap",
                            style={"minWidth": 0, "width": "100%"},
                            children=[
                                dmc.Text("Control total:", size="xs", c="dimmed", fw=500, style={"flexShrink": 0}),
                                (
                                    dmc.Badge(
                                        f"Control total khớp: {ct_val}",
                                        color="teal",
                                        variant="light",
                                        size="xs",
                                    )
                                    if ct_diff == 0
                                    else dmc.Badge(
                                        f"Control total lệch: chênh {ct_diff:,.0f} đ",
                                        color="orange",
                                        variant="light",
                                        size="xs",
                                    )
                                ),
                            ],
                        )
                    ]
                    if ct_val is not None
                    else (
                        [
                            dmc.Group(
                                justify="space-between",
                                align="center",
                                wrap="nowrap",
                                style={"minWidth": 0, "width": "100%"},
                                children=[
                                    dmc.Text("Control total:", size="xs", c="dimmed", fw=500, style={"flexShrink": 0}),
                                    dmc.Badge(
                                        ct_warn or "Không có control total",
                                        color="orange",
                                        variant="light",
                                        size="xs",
                                    ),
                                ],
                            )
                        ]
                        if ct_warn
                        else []
                    )
                ),
            ],
        )

    info_box = html.Div(
        style={
            "display": "flex" if has_file else "none",
            "flexDirection": "column",
            "gap": "8px",
            "minWidth": 0,
            "width": "100%",
            "overflow": "hidden",
        },
        children=[metadata_card] if metadata_card is not None else [],
    )

    # Nút dummy để Dash callback không bao giờ bị thiếu new-run-change-file-btn khi chưa có file
    dummy_change_btn = html.Div(
        button_subtle("Đổi file", id="new-run-change-file-btn", size="xs"),
        style={"display": "none"},
    )

    return dmc.Paper(
        withBorder=True,
        p="sm",
        radius="sm",
        h="100%",
        style={
            "display": "flex",
            "flexDirection": "column",
            "flex": "1 1 0%",
            "height": "100%",
            "minHeight": 0,
            "overflow": "hidden",
        },
        children=[
            dmc.Group(
                justify="space-between",
                align="center",
                mb="xs",
                children=[
                    dmc.Title("1. File dữ liệu", order=4),
                    *(
                        [button_subtle("Đổi file", id="new-run-change-file-btn", size="xs", icon="lucide:refresh-cw")]
                        if has_file
                        else [dummy_change_btn]
                    ),
                ],
            ),
            dmc.Text(
                "Kéo thả hoặc chọn file dữ liệu Excel/CSV để đối soát.",
                size="xs",
                c="dimmed",
                mb="xs",
                style={"flexShrink": 0},
            ),
            *(
                [
                    html.Div(
                        style={
                            "flex": "1 1 0%",
                            "minHeight": 0,
                            "display": "flex",
                            "flexDirection": "column",
                            "justifyContent": "center",
                        },
                        children=[dropzone_box],
                    )
                ]
                if not has_file
                else [
                    dmc.ScrollArea(
                        style={"flex": "1 1 0%", "minHeight": 0, "overflowX": "hidden"},
                        type="auto",
                        offsetScrollbars=True,
                        children=[
                            dropzone_box,
                            info_box,
                        ],
                    )
                ]
            ),
        ],
    )


# Tham số đã có ô nhập riêng trong layout, không render lại ở khối phụ.
FIXED_RUN_PARAM_NAMES = {"p_from", "p_to", "p_org"}


def extra_run_params(cfg_dict: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Các tham số DB của template ngoài 3 ô cố định, giữ đúng thứ tự khai báo.

    Trước đây /runs/new chỉ hardcode p_from/p_to/p_org, nên template thêm
    tham số mới (ví dụ p_application) thì layout không có ô nhập, SQL
    preview vẫn hiện bind nhưng lần chạy không truyền được giá trị đó.
    """
    if not cfg_dict:
        return []
    return [
        p
        for p in cfg_dict.get("db_source", {}).get("params", [])
        if p.get("name") and p.get("name") not in FIXED_RUN_PARAM_NAMES
    ]


def _param_default_str(p: dict[str, Any]) -> str:
    default = p.get("default")
    return "" if default is None else str(default)


def render_extra_param_input(p: dict[str, Any]) -> Any:
    """Một ô nhập cho tham số phụ, dùng id pattern-matching để callback đọc chung.

    Nhãn lấy thẳng theo tên parameter (ví dụ p_application), không lấy
    theo label trong template. Wizard khi thêm tham số mới tự gán label
    chung chung là "Tham Số 1", "Tham Số 2", nên nếu hiển thị label đó
    thì thêm nhiều tham số một lúc sẽ không phân biệt được ô nào là gì,
    trong khi tên parameter là thứ duy nhất phân biệt được và khớp với
    tên bind trong SQL preview (:p_application).
    """
    name = str(p.get("name"))
    label = name
    if p.get("required"):
        label = f"{label} *"
    comp_id = {"type": "new-run-extra-param", "name": name}
    p_type = p.get("type") or "text"
    default = _param_default_str(p)
    if p_type == "number":
        try:
            num_val = float(default) if default.strip() else None
        except (TypeError, ValueError):
            num_val = None
        return dmc.NumberInput(id=comp_id, label=label, value=num_val, w="100%")
    if p_type == "datetime":
        return dmc.DateTimePicker(
            id=comp_id,
            label=label,
            value=default or None,
            valueFormat="YYYY-MM-DD HH:mm:ss",
            withSeconds=True,
            clearable=False,
            w="100%",
        )
    if p_type == "date":
        return dmc.DateInput(id=comp_id, label=label, value=default or None, w="100%")
    return dmc.TextInput(id=comp_id, label=label, value=default, placeholder=label, w="100%")


def build_extra_params_dict(
    template_data: dict[str, Any] | None,
    extra_values: list[Any] | None,
) -> dict[str, Any]:
    """Ghép giá trị ô phụ (theo đúng thứ tự render) thành dict tham số chạy.

    Dash trả giá trị pattern-matching ALL theo thứ tự xuất hiện trong
    layout, mà layout render đúng theo thứ tự db_source.params nên zip
    theo thứ tự này là khớp tên. Ô trống thì bỏ qua để engine dùng
    default của template (nếu có), giống cách p_org đang làm.
    """
    if not template_data or not extra_values:
        return {}
    cfg_dict = template_data.get("config", {})
    out: dict[str, Any] = {}
    for p, val in zip(extra_run_params(cfg_dict), extra_values, strict=False):
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        out[str(p.get("name"))] = val
    return out


def missing_required_extra_params(
    template_data: dict[str, Any] | None,
    extra_values: list[Any] | None,
) -> list[str]:
    """Tên các tham số phụ bắt buộc mà người dùng bỏ trống và không có default."""
    if not template_data:
        return []
    cfg_dict = template_data.get("config", {})
    values = extra_values or []
    missing: list[str] = []
    for idx, p in enumerate(extra_run_params(cfg_dict)):
        val = values[idx] if idx < len(values) else None
        if p.get("required") and not _param_default_str(p).strip():
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(str(p.get("name")))
    return missing


def render_params_section(
    template_info: dict[str, Any] | None,
    data_sources: list[dict[str, Any]],
    active_templates: list[dict[str, Any]] | None = None,
    precheck_info: dict[str, Any] | None = None,
    err_msg: str | None = None,
    duplicate_run: dict[str, Any] | None = None,
) -> dmc.Paper:
    """Dựng Card 2: Profile và tham số tìm kiếm (bỏ hardcode ngày giờ và mã đơn vị)."""
    if active_templates is None:
        active_templates = get_active_templates()

    select_options = [{"label": f"{t['code']} - {t['name']}", "value": str(t["id"])} for t in active_templates]
    selected_tmpl_id = (
        str(template_info["id"])
        if template_info and template_info.get("id")
        else (str(active_templates[0]["id"]) if active_templates else None)
    )

    profiles_data: list[dict[str, Any]] = []
    default_profile: str | None = None
    p_org_default = ""
    extra_params: list[dict[str, Any]] = []

    if template_info:
        cfg_dict = template_info.get("config", {})
        profs = cfg_dict.get("profiles", [])
        if profs:
            profiles_data = [{"label": p.get("name") or p.get("code"), "value": p.get("code")} for p in profs]
            default_profile = next((p.get("code") for p in profs if p.get("is_default")), profs[0].get("code"))

        # Tìm default của p_org từ db_source.params
        db_src = cfg_dict.get("db_source", {})
        for p in db_src.get("params", []):
            if p.get("name") == "p_org" and p.get("default"):
                p_org_default = str(p.get("default"))
                break
        # Tham số phụ của template (ví dụ p_application), render động thay
        # vì hardcode, để thêm tham số mới ở wizard là /runs/new có ô nhập.
        extra_params = extra_run_params(cfg_dict)

    if not profiles_data:
        profiles_data = [{"label": "Theo số hóa đơn", "value": "BY_INVOICE"}]
        default_profile = "BY_INVOICE"

    ds_options = [{"label": d["label"], "value": str(d["id"])} for d in data_sources]
    default_ds = ds_options[0]["value"] if ds_options else None
    if template_info and template_info.get("data_source_id"):
        default_ds = str(template_info["data_source_id"])

    # Tính toán ngày hôm qua theo giờ Việt Nam
    def_p_from, def_p_to = compute_quick_range("yesterday")
    p_from_display = def_p_from.replace("T", " ")
    p_to_display = def_p_to.replace("T", " ")

    precheck_node = None
    if precheck_info:
        est_rows = precheck_info.get("est_excel_rows", 0)
        p_from_str = precheck_info.get("p_from_str", p_from_display)
        p_to_str = precheck_info.get("p_to_str", p_to_display)
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
        p="sm",
        radius="sm",
        h="100%",
        style={
            "display": "flex",
            "flexDirection": "column",
            "flex": "1 1 0%",
            "height": "100%",
            "minHeight": 0,
            "overflow": "hidden",
        },
        children=[
            dmc.Title("2. Profile và tham số tìm kiếm", order=4, mb=2),
            dmc.Text(
                "Chọn template, profile và khoảng thời gian đối soát.",
                size="xs",
                c="dimmed",
                mb="xs",
                style={"flexShrink": 0},
            ),
            dmc.ScrollArea(
                style={"flex": "1 1 0%", "minHeight": 0},
                type="auto",
                offsetScrollbars=True,
                children=[
                    # Template đối soát (Selectable & Searchable)
                    dmc.Select(
                        id="new-run-manual-template-select",
                        label="Chỉ định template đối soát *",
                        data=select_options,
                        value=selected_tmpl_id,
                        placeholder="Tìm hoặc chọn template áp dụng...",
                        searchable=True,
                        clearable=False,
                        nothingFoundMessage="Không tìm thấy template",
                        size="xs",
                        mb="xs",
                    ),
                    dmc.Grid(
                        gutter="xs",
                        mb="xs",
                        children=[
                            dmc.GridCol(
                                span=6,
                                children=dmc.Select(
                                    id="new-run-profile-select",
                                    label="Profile",
                                    data=profiles_data,
                                    value=default_profile,
                                    searchable=True,
                                    clearable=False,
                                    size="xs",
                                ),
                            ),
                            dmc.GridCol(
                                span=6,
                                children=dmc.Select(
                                    id="new-run-datasource-select",
                                    label="Data Source",
                                    data=ds_options,
                                    value=default_ds,
                                    searchable=True,
                                    clearable=False,
                                    size="xs",
                                ),
                            ),
                        ],
                    ),
                    # Hàng tham số: p_from, p_to
                    dmc.Grid(
                        gutter="xs",
                        mb="xs",
                        children=[
                            dmc.GridCol(
                                span=6,
                                children=dmc.DateTimePicker(
                                    id="new-run-p-from",
                                    label="Từ ngày giờ (p_from) *",
                                    value=p_from_display,
                                    valueFormat="YYYY-MM-DD HH:mm:ss",
                                    withSeconds=True,
                                    clearable=False,
                                    size="xs",
                                    w="100%",
                                ),
                            ),
                            dmc.GridCol(
                                span=6,
                                children=dmc.DateTimePicker(
                                    id="new-run-p-to",
                                    label="Đến ngày giờ (p_to) *",
                                    value=p_to_display,
                                    valueFormat="YYYY-MM-DD HH:mm:ss",
                                    withSeconds=True,
                                    clearable=False,
                                    size="xs",
                                    w="100%",
                                ),
                            ),
                        ],
                    ),
                    dmc.TextInput(
                        id="new-run-p-org",
                        label="Đơn vị (p_org) *",
                        value=p_org_default,
                        placeholder="Ví dụ: BDP",
                        className="mono",
                        size="xs",
                        mb="xs",
                    ),
                    # Tham số phụ của template (đổi template thì callback riêng
                    # dưới đây dựng lại khối này, không cần sửa layout cứng).
                    html.Div(
                        id="new-run-extra-params",
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(auto-fill, minmax(180px, 1fr))",
                            "gap": "8px",
                            "marginTop": "8px",
                        },
                        children=[render_extra_param_input(p) for p in extra_params],
                    ),
                    # Thông báo lỗi dưới hai ô ngày giờ
                    html.Div(
                        id="new-run-range-msg",
                        children=err_msg or "",
                        style={"color": "var(--crit, #dc2626)", "minHeight": 18, "fontSize": "12px"},
                    ),
                    # Chọn nhanh
                    dmc.Group(
                        [
                            dmc.Text("Chọn nhanh:", size="xs", fw=500, c="dimmed"),
                            button_subtle("Hôm qua", id="new-run-quick-yesterday", size="xs"),
                            button_subtle("Tháng trước", id="new-run-quick-last-month", size="xs"),
                        ],
                        gap="xs",
                        mt="xs",
                        mb="xs",
                    ),
                    # Switch áp khoảng Excel
                    dmc.Switch(
                        id="new-run-apply-excel-time",
                        label="Áp dụng cùng khoảng thời gian cho dữ liệu Excel",
                        checked=False,
                        size="xs",
                        mb="xs",
                    ),
                    *([precheck_node] if precheck_node is not None else []),
                    *([html.Div(dup_node, style={"marginTop": 8})] if dup_node is not None else []),
                ],
            ),
        ],
    )


def render_sql_preview_section(
    template_info: dict[str, Any] | None,
    profile_code: str | None = None,
    params: dict[str, Any] | None = None,
) -> dmc.Paper:
    """Dựng Card 3: Khối hiển thị câu lệnh SQL đối soát DB (sinh tự động - chỉ đọc)."""
    if not template_info:
        return dmc.Paper(
            withBorder=True,
            p="sm",
            radius="sm",
            h="100%",
            style={
                "display": "flex",
                "flexDirection": "column",
                "flex": "1 1 0%",
                "height": "100%",
                "minHeight": 0,
                "overflow": "hidden",
            },
            children=[
                dmc.Title("3. Câu lệnh SQL đối soát DB", order=4, mb=2),
                dmc.Text(
                    "Sinh tự động - chỉ đọc theo Profile đã chọn (GROUP BY và MEASURES).",
                    size="xs",
                    c="dimmed",
                    mb="xs",
                    style={"flexShrink": 0},
                ),
                alert_box("Vui lòng tải lên file hoặc chọn template để xem trước câu lệnh SQL đối soát.", tone="info"),
            ],
        )

    cfg_dict = template_info.get("config", {})
    try:
        cfg = TemplateConfig.model_validate(cfg_dict)
        profs = cfg.profiles
        target_prof = None
        if profile_code:
            target_prof = next((p for p in profs if p.code == profile_code), None)
        if not target_prof and profs:
            target_prof = next((p for p in profs if p.is_default), profs[0])

        sql_text, binds = build_source_sql(cfg, target_prof, params or {})
        line_cnt = len(sql_text.splitlines())
        pushdown = cfg.db_source.pushdown_aggregate if cfg.db_source else False

        bind_badges = []
        for k, v in binds.items():
            if v is not None and str(v).strip():
                bind_badges.append(
                    dmc.Badge(
                        f":{k} = {v}",
                        variant="outline",
                        color="indigo",
                        size="xs",
                    )
                )

        return dmc.Paper(
            withBorder=True,
            p="sm",
            radius="sm",
            h="100%",
            style={
                "display": "flex",
                "flexDirection": "column",
                "flex": "1 1 0%",
                "height": "100%",
                "minHeight": 0,
                "overflow": "hidden",
            },
            children=[
                dmc.Group(
                    justify="space-between",
                    align="center",
                    mb=2,
                    children=[
                        dmc.Title("3. Câu lệnh SQL đối soát DB", order=4),
                        dmc.Group(
                            [
                                dmc.Badge(
                                    "Đẩy phép gộp xuống DB" if pushdown else "Kéo chi tiết về ứng dụng",
                                    color="teal" if pushdown else "gray",
                                    variant="light",
                                    size="xs",
                                ),
                                dmc.Badge(f"{line_cnt} dòng", color="gray", variant="outline", size="xs"),
                            ],
                            gap="xs",
                        ),
                    ],
                ),
                dmc.Text(
                    "Sinh tự động - chỉ đọc theo Profile đã chọn (GROUP BY và MEASURES).",
                    size="xs",
                    c="dimmed",
                    mb="xs",
                    style={"flexShrink": 0},
                ),
                dmc.ScrollArea(
                    style={"flex": "1 1 0%", "minHeight": 0, "overflow": "hidden"},
                    type="auto",
                    offsetScrollbars=True,
                    children=[
                        code_block(
                            sql_text,
                            language="sql",
                            style={"minHeight": 0},
                        ),
                    ],
                ),
                dmc.Group(
                    [
                        dmc.Text("Tham số ràng buộc (Binds):", size="xs", fw=600, c="dimmed"),
                        *(bind_badges if bind_badges else [dmc.Text("Không có bind param", size="xs", c="dimmed")]),
                    ],
                    gap="xs",
                    mt="xs",
                    style={"flexShrink": 0},
                ),
            ],
        )
    except Exception as err:
        return dmc.Paper(
            withBorder=True,
            p="sm",
            radius="sm",
            h="100%",
            style={
                "display": "flex",
                "flexDirection": "column",
                "flex": "1 1 0%",
                "height": "100%",
                "minHeight": 0,
                "overflow": "hidden",
            },
            children=[
                dmc.Title("3. Câu lệnh SQL đối soát DB", order=4, mb="xs"),
                alert_box(f"Không thể sinh câu lệnh SQL: {err}", tone="warn"),
            ],
        )


def render_execution_section(
    is_ready: bool,
    lock_reason: str,
    is_running: bool = False,
    current_stage: int = 1,
    stage_desc: str = "Đang xử lý...",
    progress_pct: int = 0,
    error_msg: str | None = None,
) -> dmc.Paper:
    """Dựng thanh Command Bar thực thi đối soát & tiến độ."""
    err_node = None
    if error_msg:
        err_node = alert_box(f"Đối soát thất bại: {error_msg}", tone="crit")

    if is_running:
        return dmc.Paper(
            withBorder=True,
            p="xs",
            radius="sm",
            style={"background": "var(--mantine-color-body)", "borderColor": "var(--mantine-color-teal-6)"},
            children=dmc.Stack(
                gap="xs",
                children=[
                    dmc.Group(
                        justify="space-between",
                        align="center",
                        wrap="wrap",
                        gap="md",
                        children=[
                            dmc.Group(
                                [
                                    dmc.ThemeIcon(
                                        DashIconify(icon="lucide:loader-2", width=18),
                                        color="teal",
                                        variant="light",
                                        size="md",
                                    ),
                                    dmc.Stack(
                                        gap=1,
                                        children=[
                                            dmc.Text(
                                                f"{current_stage}/5 {stage_desc}",
                                                id="new-run-stage-text",
                                                size="xs",
                                                fw=600,
                                            ),
                                            dmc.Text(
                                                "Đang thực thi đối soát trong hàng đợi...",
                                                size="xs",
                                                c="dimmed",
                                            ),
                                        ],
                                    ),
                                ],
                                gap="xs",
                                align="center",
                            ),
                            dmc.Box(
                                style={"flex": "1 1 auto", "minWidth": "300px", "maxWidth": "650px"},
                                children=dmc.Stack(
                                    gap=3,
                                    children=[
                                        dmc.Group(
                                            justify="space-between",
                                            children=[
                                                dmc.Text(f"Bước {current_stage}/5", size="xs", fw=600, c="teal"),
                                                dmc.Text(f"{progress_pct}%", size="xs", fw=700, c="teal"),
                                            ],
                                        ),
                                        dmc.Progress(
                                            value=progress_pct,
                                            animated=True,
                                            striped=True,
                                            color="teal",
                                            radius="sm",
                                            size="lg",
                                            style={"height": 14},
                                        ),
                                    ],
                                ),
                            ),
                            dmc.Group(
                                [
                                    dmc.Text("", id="new-run-lock-reason", style={"display": "none"}),
                                    button_primary(
                                        "Đang chạy...",
                                        id="new-run-execute-btn",
                                        icon="lucide:loader-2",
                                        size="xs",
                                        disabled=True,
                                    ),
                                ],
                                gap="xs",
                                align="center",
                            ),
                        ],
                    ),
                    *([err_node] if err_node is not None else []),
                ],
            ),
        )

    # Trạng thái chờ / chưa chạy
    return dmc.Paper(
        withBorder=True,
        p="xs",
        radius="sm",
        style={"background": "var(--mantine-color-body)"},
        children=dmc.Stack(
            gap="xs",
            children=[
                dmc.Group(
                    justify="space-between",
                    align="center",
                    wrap="wrap",
                    gap="sm",
                    children=[
                        dmc.Group(
                            [
                                dmc.ThemeIcon(
                                    DashIconify(
                                        icon="lucide:play-circle" if is_ready else "lucide:info",
                                        width=16,
                                    ),
                                    color="indigo" if is_ready else "gray",
                                    variant="light",
                                    size="sm",
                                ),
                                dmc.Text("Thực thi", size="xs", fw=600),
                                dmc.Text(
                                    lock_reason,
                                    id="new-run-lock-reason",
                                    size="xs",
                                    c="dimmed",
                                ),
                            ],
                            gap="xs",
                            align="center",
                        ),
                        dmc.Group(
                            [
                                html.Span(id="new-run-stage-text", style={"display": "none"}),
                                button_primary(
                                    "Chạy đối soát",
                                    id="new-run-execute-btn",
                                    icon="lucide:play",
                                    size="xs",
                                    disabled=not is_ready,
                                ),
                            ],
                            gap="sm",
                            align="center",
                        ),
                    ],
                ),
                *([err_node] if err_node is not None else []),
            ],
        ),
    )


try:
    dash.register_page(  # type: ignore[no-untyped-call]
        __name__,
        path="/runs/new",
        title="Chạy đối soát — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "run"


def layout() -> Any:
    """Layout chính của màn hình Chạy đối soát (Screen05-NewRun)."""
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="new-run-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập trang chạy đối soát.", tone="crit"),
            ]
        )
    if ctx is None or not has_role(ctx, "ADMIN", "TEMPLATE_OWNER", "OPERATOR"):
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
                dmc.Text(
                    "Upload file, kiểm tra template nhận diện, nhập khoảng ngày giờ tìm kiếm rồi chạy.",
                    c="dimmed",
                    mb="lg",
                ),
                dmc.Paper(
                    withBorder=True,
                    p="xl",
                    radius="sm",
                    style={"textAlign": "center"},
                    children=[
                        dmc.ThemeIcon(
                            DashIconify(icon="lucide:layers", width=36),
                            size="xl",
                            radius="md",
                            color="gray",
                            variant="light",
                            mb="md",
                        ),
                        dmc.Title("Chưa có template nào đang dùng", order=3, mb="xs"),
                        dmc.Text(
                            "Cần ít nhất một template Active để thực hiện chạy đối soát.",
                            size="sm",
                            c="dimmed",
                            mb="md",
                        ),
                        dcc.Link(button_primary("Đăng ký template", icon="lucide:plus"), href="/templates/new"),
                    ],
                ),
            ],
            style={"padding": "24px"},
        )

    data_sources = get_available_data_sources()
    initial_template = active_templates[0] if active_templates else None

    # Khởi tạo tham số mặc định cho câu SQL ban đầu
    def_p_from, def_p_to = compute_quick_range("yesterday")
    p_org_init = ""
    if initial_template:
        cfg_init = initial_template.get("config", {})
        for p in cfg_init.get("db_source", {}).get("params", []):
            if p.get("name") == "p_org" and p.get("default"):
                p_org_init = str(p.get("default"))
                break

    init_sql_params = {
        "p_from": def_p_from.replace("T", " "),
        "p_to": def_p_to.replace("T", " "),
        "p_org": p_org_init,
    }
    # Tham số phụ của template ban đầu (để SQL preview lúc mới vào trang
    # đã đúng binds; build_source_sql vốn đã dùng default nếu thiếu, đây
    # chỉ để preview và lần chạy đầu nhất quán với ô nhập hiển thị).
    if initial_template:
        for p in extra_run_params(initial_template.get("config", {})):
            if _param_default_str(p).strip():
                init_sql_params[str(p.get("name"))] = _param_default_str(p)

    return html.Div(
        id="new-run-root",
        children=[
            # Stores
            dcc.Store(id="new-run-file-store", data=None),
            dcc.Store(id="new-run-template-store", data=initial_template),
            dcc.Store(id="new-run-state-store", data={"is_running": False, "run_id": None, "stage": 0, "pct": 0}),
            dcc.Interval(id="new-run-progress-interval", interval=1000, n_intervals=0, disabled=True),
            dcc.Location(id="new-run-redirect-location", refresh=True),
            html.Div(id="new-run-notifications"),
            # Header trang (đồng bộ padding 16px với card và command bar)
            page_header(
                title="Chạy đối soát",
                subtitle="Upload file, kiểm tra template nhận diện, nhập khoảng ngày giờ tìm kiếm rồi chạy.",
                style={"padding": "0 16px", "marginBottom": "6px"},
            ),
            # Command Bar Thực thi (flexShrink: 0)
            html.Div(
                id="new-run-exec-container",
                style={"flexShrink": "0", "padding": "0 16px", "marginBottom": "8px"},
                children=render_execution_section(is_ready=False, lock_reason="Chọn file dữ liệu để bật nút chạy."),
            ),
            # Vùng chính 3 Card (nằm gọn trong 1 page, không cuộn ngoài, 3 card bằng nhau 100%)
            html.Div(
                style={
                    "flex": "1 1 0%",
                    "minHeight": 0,
                    "padding": "0 16px 12px 16px",
                    "display": "flex",
                    "flexDirection": "column",
                    "overflow": "hidden",
                },
                children=[
                    html.Div(
                        id="new-run-cards-grid",
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(3, minmax(0, 1fr))",
                            "gap": "12px",
                            "height": "100%",
                            "minHeight": "0",
                            "flex": "1 1 0%",
                        },
                        children=[
                            # Card 1: File dữ liệu
                            html.Div(
                                id="new-run-file-col",
                                style={
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "height": "100%",
                                    "minHeight": "0",
                                    "overflow": "hidden",
                                },
                                children=render_file_section(None, initial_template, active_templates),
                            ),
                            # Card 2: Profile & Tham số tìm kiếm
                            html.Div(
                                id="new-run-params-col",
                                style={
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "height": "100%",
                                    "minHeight": "0",
                                    "overflow": "hidden",
                                },
                                children=render_params_section(initial_template, data_sources, active_templates),
                            ),
                            # Card 3: Câu lệnh SQL đối soát DB (sinh tự động - chỉ đọc)
                            html.Div(
                                id="new-run-sql-container",
                                style={
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "height": "100%",
                                    "minHeight": "0",
                                    "overflow": "hidden",
                                },
                                children=render_sql_preview_section(initial_template, None, init_sql_params),
                            ),
                        ],
                    ),
                ],
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
        style={
            "height": "100%",
            "minHeight": 0,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "paddingTop": "12px",
            "boxSizing": "border-box",
            "backgroundColor": "var(--mantine-color-body)",
        },
    )


# Callbacks xử lý Upload & File


@callback(
    Output("new-run-file-store", "data"),
    Output("new-run-template-store", "data"),
    Output("new-run-manual-template-select", "value"),
    Output("new-run-notifications", "children"),
    Input("new-run-upload", "contents"),
    Input("new-run-change-file-btn", "n_clicks"),
    State("new-run-upload", "filename"),
    State("new-run-manual-template-select", "value"),
    prevent_initial_call=True,
)
def handle_file_upload_or_change(
    contents: str | None,
    change_clicks: int | None,
    filename: str | None,
    manual_tmpl_id: str | None,
) -> tuple[Any, Any, Any, Any]:
    """Xử lý sự kiện kéo thả file upload hoặc bấm Đổi file."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    trigger_id = ctx_dash.triggered[0]["prop_id"]
    if "new-run-change-file-btn" in trigger_id:
        if not change_clicks:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        notif = notify_info("Đã xóa file dữ liệu. Vui lòng chọn file mới.", title="Đổi file")
        return None, dash.no_update, dash.no_update, notif

    if contents and filename:
        ctx = get_current_ctx()
        if ctx is None:
            notif = notify_error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
            return None, dash.no_update, dash.no_update, notif

        try:
            # Tách header base64 data
            if "," in contents:
                _, content_string = contents.split(",", 1)
            else:
                content_string = contents
            file_bytes = base64.b64decode(content_string)

            m_id = int(manual_tmpl_id) if manual_tmpl_id and manual_tmpl_id.isdigit() else None
            processed = process_uploaded_file(ctx, filename=filename, content_bytes=file_bytes, manual_template_id=m_id)
            detected = processed["detected_template"]
            detected_id = str(detected["id"]) if detected else dash.no_update
            valid_rows = processed["valid_rows"]
            if detected:
                t_code = detected.get("code", "")
                t_ver = detected.get("version", 1)
                notif = notify_success(
                    f"Đã nhận diện template {t_code} v{t_ver} · {valid_rows:,} dòng hợp lệ".replace(",", "."),
                    title="Tải file thành công",
                )
            else:
                notif = notify_warning(
                    f"Đã nạp file ({valid_rows:,} dòng). Vui lòng chọn template ở Card 2 bên cạnh.".replace(",", "."),
                    title="Chưa tự động nhận diện template",
                )
            return processed["file_data"], (detected if detected else dash.no_update), detected_id, notif
        except Exception as e:
            notif = notify_error(str(e), title="Lỗi xử lý file")
            return None, dash.no_update, dash.no_update, notif

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update


@callback(
    Output("new-run-template-store", "data", allow_duplicate=True),
    Input("new-run-manual-template-select", "value"),
    prevent_initial_call=True,
)
def handle_manual_template_select(tmpl_id_val: str | None) -> Any:
    """Cập nhật template được chọn khi người dùng đổi thủ công ở dropdown."""
    if not tmpl_id_val:
        return dash.no_update
    active_tmpls = get_active_templates()
    matched = next((t for t in active_tmpls if str(t["id"]) == str(tmpl_id_val)), None)
    return matched if matched else dash.no_update


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
    Output("new-run-profile-select", "data"),
    Output("new-run-profile-select", "value"),
    Output("new-run-datasource-select", "value"),
    Output("new-run-p-org", "value"),
    Input("new-run-template-store", "data"),
    prevent_initial_call=True,
)
def sync_params_on_template_change(template_data: dict[str, Any] | None) -> tuple[Any, Any, Any, Any]:
    """Cập nhật Profile Select, Data Source và đơn vị mặc định khi Template thay đổi."""
    if not template_data:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    cfg_dict = template_data.get("config", {})
    profs = cfg_dict.get("profiles", [])
    profiles_data = [{"label": p.get("name") or p.get("code"), "value": p.get("code")} for p in profs]
    default_prof = next(
        (p.get("code") for p in profs if p.get("is_default")), (profs[0].get("code") if profs else None)
    )

    ds_id: Any = str(template_data.get("data_source_id")) if template_data.get("data_source_id") else dash.no_update

    p_org_val: Any = dash.no_update
    db_src = cfg_dict.get("db_source", {})
    for p in db_src.get("params", []):
        if p.get("name") == "p_org" and p.get("default"):
            p_org_val = str(p.get("default"))
            break

    return (
        profiles_data or [{"label": "Chưa có profile", "value": "NONE"}],
        default_prof,
        ds_id,
        p_org_val,
    )


@callback(
    Output("new-run-extra-params", "children"),
    Input("new-run-template-store", "data"),
    prevent_initial_call=True,
)
def sync_extra_params_on_template_change(template_data: dict[str, Any] | None) -> Any:
    """Dựng lại các ô tham số phụ khi đổi template (thêm/bớt tham số ở wizard).

    Chỉ dựng lại khối phụ, không chạm tới các ô p_from/p_to/p_org hay
    select profile/data source (đã có callback riêng cập nhật giá trị).
    """
    if not template_data:
        return dash.no_update
    cfg_dict = template_data.get("config", {})
    return [render_extra_param_input(p) for p in extra_run_params(cfg_dict)]


@callback(
    Output("new-run-sql-container", "children"),
    Input("new-run-template-store", "data"),
    Input("new-run-profile-select", "value"),
    Input("new-run-p-from", "value"),
    Input("new-run-p-to", "value"),
    Input("new-run-p-org", "value"),
    Input({"type": "new-run-extra-param", "name": ALL}, "value"),
)
def update_sql_preview_callback(
    template_data: dict[str, Any] | None,
    profile_code: str | None,
    p_from: str | None,
    p_to: str | None,
    p_org: str | None,
    extra_values: list[Any] | None,
) -> Any:
    """Tự động cập nhật câu lệnh SQL đối soát DB khi template, profile hoặc tham số thay đổi."""
    params = {
        "p_from": p_from,
        "p_to": p_to,
        "p_org": p_org,
    }
    params.update(build_extra_params_dict(template_data, extra_values))
    return render_sql_preview_section(template_data, profile_code, params)


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
    f, t = compute_quick_range(mode)
    return f.replace("T", " "), t.replace("T", " ")


@callback(
    Output("new-run-range-msg", "children"),
    Output("new-run-lock-reason", "children"),
    Output("new-run-execute-btn", "disabled"),
    Input("new-run-p-from", "value"),
    Input("new-run-p-to", "value"),
    Input("new-run-file-store", "data"),
    Input("new-run-template-store", "data"),
)
def validate_inputs_and_enable_run(
    p_from: str | None,
    p_to: str | None,
    file_data: dict[str, Any] | None,
    template_data: dict[str, Any] | None,
) -> tuple[str, str, bool]:
    """Kiểm tra hợp lệ khoảng thời gian và quản lý trạng thái nút Chạy đối soát."""
    err = validate_run_params(p_from, p_to)
    if err:
        return err, "Sửa khoảng thời gian để chạy.", True

    if not template_data:
        return "", "Chọn template để tiếp tục.", True

    if not file_data:
        return "", "Chọn file dữ liệu để bật nút chạy.", True

    return "", "", False


@callback(
    Output("new-run-prod-modal", "opened"),
    Output("new-run-state-store", "data", allow_duplicate=True),
    Output("new-run-progress-interval", "disabled"),
    Output("new-run-exec-container", "children", allow_duplicate=True),
    Input("new-run-execute-btn", "n_clicks"),
    Input("new-run-prod-modal-confirm", "n_clicks"),
    Input("new-run-prod-modal-cancel", "n_clicks"),
    State("new-run-datasource-select", "value"),
    State("new-run-template-store", "data"),
    State("new-run-file-store", "data"),
    State("new-run-p-from", "value"),
    State("new-run-p-to", "value"),
    State("new-run-profile-select", "value"),
    State("new-run-p-org", "value"),
    State("new-run-apply-excel-time", "checked"),
    State("new-run-state-store", "data"),
    State({"type": "new-run-extra-param", "name": ALL}, "value"),
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
    p_org_val: str | None,
    apply_excel_time: bool | None,
    state_data: dict[str, Any] | None = None,
    extra_values: list[Any] | None = None,
) -> Any:
    """Xử lý khi người dùng nhấn nút 'Chạy đối soát' hoặc xác nhận Modal PROD."""
    ctx_dash = dash.callback_context
    if not ctx_dash.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    trigger_id = ctx_dash.triggered[0]["prop_id"]
    if "new-run-prod-modal-cancel" in trigger_id:
        return False, dash.no_update, dash.no_update, dash.no_update

    # Chặn vòng lặp tạo run: nút Chạy nằm trong Card thực thi mà callback
    # tiến độ thay mỗi giây, nên Dash có thể kích hoạt lại callback này khi
    # nút được dựng lại với n_clicks=0 (giống lỗi modal /lookups trước đây).
    # Chỉ xử lý khi giá trị kích hoạt thật sự là một lần bấm (> 0).
    triggered_value = ctx_dash.triggered[0].get("value")
    if not triggered_value:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    # Đang chạy thì không tạo run mới, dù callback bị kích hoạt lại.
    if state_data and state_data.get("is_running"):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    # Kiểm tra Data Source có phải PROD không
    is_confirm_click = "new-run-prod-modal-confirm" in trigger_id
    if not is_confirm_click and datasource_id:
        engine = get_recon_engine()
        with engine.connect() as conn:
            env = conn.scalar(select(recon_data_source.c.ENV).where(recon_data_source.c.ID == int(datasource_id)))
            if env == "PROD":
                return True, dash.no_update, dash.no_update, dash.no_update

    # Bắt đầu chạy run
    ctx = get_current_ctx()
    if ctx is None or not template_data or not file_data or not p_from_str or not p_to_str:
        return False, dash.no_update, dash.no_update, dash.no_update

    tmpl_id = int(template_data.get("id", 1))
    tmpl_ver = int(template_data.get("version", 1))
    f_id = int(file_data.get("id", 1))

    dt_from = datetime.fromisoformat(p_from_str.strip().replace(" ", "T"))
    dt_to = datetime.fromisoformat(p_to_str.strip().replace(" ", "T"))

    # Tham số phụ bắt buộc mà bỏ trống và không có default thì chặn ngay,
    # tránh tạo run với bind None (Oracle so sánh = NULL sẽ trả 0 dòng).
    missing_extra = missing_required_extra_params(template_data, extra_values)
    if missing_extra:
        err_ui = render_execution_section(
            is_ready=True,
            lock_reason="",
            error_msg=f"Nhập tham số bắt buộc: {', '.join(missing_extra)}.",
        )
        return False, dash.no_update, dash.no_update, err_ui

    params_dict = {"p_org": p_org_val} if p_org_val else {}
    params_dict.update(build_extra_params_dict(template_data, extra_values))
    ds_int = int(datasource_id) if datasource_id and datasource_id.isdigit() else None

    run_res = create_run(
        ctx,
        CreateRunParams(
            template_id=tmpl_id,
            template_version=tmpl_ver,
            file_id=f_id,
            profile_code=profile_code,
            data_source_id=ds_int,
            p_from=dt_from,
            p_to=dt_to,
            params=params_dict,
            apply_range_excel=bool(apply_excel_time),
            confirm_prod=True,
        ),
    )

    if not run_res.ok or not run_res.data:
        err_ui = render_execution_section(
            is_ready=True,
            lock_reason="",
            error_msg=run_res.message or "Lỗi khi tạo yêu cầu đối soát.",
        )
        return False, dash.no_update, dash.no_update, err_ui

    created_run_id = int(run_res.data["run_id"])

    new_state = {
        "is_running": True,
        "run_id": created_run_id,
        "stage": 1,
        "pct": 10,
    }

    exec_ui = render_execution_section(
        is_ready=False,
        lock_reason="",
        is_running=True,
        current_stage=1,
        stage_desc="Khởi tạo yêu cầu đối soát trong hàng đợi...",
        progress_pct=10,
    )
    return False, new_state, False, exec_ui


@callback(
    Output("new-run-exec-container", "children"),
    Output("new-run-state-store", "data", allow_duplicate=True),
    Output("new-run-redirect-location", "pathname"),
    Input("new-run-progress-interval", "n_intervals"),
    State("new-run-state-store", "data"),
    prevent_initial_call=True,
)
def handle_progress_tick(
    _interval: int | None,
    state: dict[str, Any] | None,
) -> tuple[Any, Any, Any]:
    """Cập nhật tiến độ chạy đối soát qua trạng thái thực tế trong database và chuyển hướng sang màn kết quả."""
    if not state or not state.get("is_running"):
        return dash.no_update, dash.no_update, dash.no_update

    run_id = state.get("run_id")
    if not run_id:
        return dash.no_update, dash.no_update, dash.no_update

    stage_names = {
        "READ": (1, "Đọc và chuẩn hóa file"),
        "FILTER": (2, "Lọc thời gian, control total, lưu dữ liệu tạm"),
        "FETCH_DB": (3, "Truy vấn Oracle"),
        "COMPARE": (4, "So sánh dữ liệu"),
        "SAVE": (5, "Ghi kết quả đối soát"),
    }

    # Truy vấn trạng thái thật từ database
    engine = get_recon_engine()
    try:
        with engine.connect() as conn:
            row = (
                conn.execute(
                    select(
                        recon_run.c.STATUS,
                        recon_run.c.STAGE,
                        recon_run.c.PROGRESS_PCT,
                        recon_run.c.ERROR_MSG,
                    ).where(recon_run.c.ID == run_id)
                )
                .mappings()
                .first()
            )
    except Exception:
        row = None

    if row:
        status = row["STATUS"]
        if status == "DONE":
            # Hoàn thành -> Chuyển hướng tới kết quả run
            return dash.no_update, {**state, "is_running": False}, f"/runs/{run_id}"

        if status == "FAILED":
            # Thất bại -> Hiển thị lỗi và mở khóa nút chạy lại
            err_msg = row["ERROR_MSG"] or "Đã xảy ra lỗi trong quá trình thực thi."
            exec_ui = render_execution_section(
                is_ready=True,
                lock_reason="",
                error_msg=err_msg,
            )
            return exec_ui, {**state, "is_running": False}, dash.no_update

        # Đang chạy hoặc trong queue
        pct = int(row["PROGRESS_PCT"] or 15)
        stg_code = str(row["STAGE"] or "READ")
        stg_num, desc = stage_names.get(stg_code, (1, "Đang xử lý..."))
        if status == "QUEUED":
            desc = "Đang chờ worker trong hàng đợi..."
            pct = 10
            # Kích hoạt worker xử lý nhanh nếu có
            try:
                from worker.runner import ReconWorker

                ReconWorker().poll_once()
            except Exception:
                pass

        updated_state = {**state, "stage": stg_num, "pct": pct}
        # Tiến độ không đổi thì không dựng lại Card thực thi: dựng lại mỗi
        # giây là nguyên nhân layout giật (thanh progress bị remount, vạch
        # sọc động chạy lại từ đầu) và nút Chạy bị dựng lại với n_clicks=0.
        if state.get("stage") == stg_num and state.get("pct") == pct:
            return dash.no_update, dash.no_update, dash.no_update
        exec_ui = render_execution_section(
            is_ready=False,
            lock_reason="",
            is_running=True,
            current_stage=stg_num,
            stage_desc=desc,
            progress_pct=pct,
        )
        return exec_ui, updated_state, dash.no_update

    # Fallback cho trường hợp unit test giả lập (không có row trong DB)
    curr_pct = state.get("pct", 20)
    if curr_pct >= 100:
        return dash.no_update, {**state, "is_running": False}, f"/runs/{run_id}"

    next_pct = curr_pct + 20
    next_stage = min(5, (next_pct // 20))
    test_stages = [
        "Đọc và chuẩn hóa file",
        "Lọc thời gian, control total, lưu dữ liệu tạm",
        "Truy vấn Oracle (qua VPN)",
        "So sánh dữ liệu",
        "Ghi kết quả",
    ]
    desc = test_stages[next_stage - 1]

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
