"""Mail Renderer & Compiler for Mail Template Studio.

Biên dịch Design JSON thành Table-based HTML tương thích sâu với Microsoft Outlook và Gmail,
sinh phiên bản Plain Text, kiểm tra an toàn (Sanitization) và xác thực tính hợp lệ (Validation).
Module hàm thuần (pure engine), không phụ thuộc vào database hay UI.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any

from app.engine.mail_token_inspector import COLUMN_LABELS, get_all_valid_tokens_set

RENDERER_VERSION = "1.0.0"

# Whitelist các kiểu font an toàn cho email clients
SAFE_FONT_STACK = "Segoe UI, Arial, Tahoma, Helvetica, sans-serif"

# Whitelist thuộc tính căn lề
VALID_ALIGNS = {"left", "center", "right"}

# Whitelist các condition type
VALID_CONDITIONS = {"always", "errors", "noerrors", "target_only", "all_users", "batch_users"}

# Token regex
TOKEN_REGEX = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def sanitize_color(val: Any, default: str = "#000000") -> str:
    """Xác thực mã màu hex an toàn."""
    if not isinstance(val, str):
        return default
    val_str = str(val).strip()
    if re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", val_str):
        return val_str
    return default


def clamp_int(val: Any, min_val: int, max_val: int, default: int) -> int:
    """Giới hạn giá trị số nguyên trong khoảng cho phép."""
    try:
        n = int(val)
        return max(min_val, min(max_val, n))
    except (ValueError, TypeError):
        return default


def evaluate_condition(condition: str | dict[str, Any], context: dict[str, Any]) -> bool:
    """Đánh giá điều kiện hiển thị của component.

    - "always": Luôn hiển thị.
    - "errors": Hiển thị khi summary.failed > 0.
    - "noerrors": Hiển thị khi summary.failed == 0.
    - Hoặc object dict {"type": "...", "field": "...", "operator": "...", "value": ...}
    """
    if isinstance(condition, str):
        cond_str = condition.strip().lower()
        if cond_str == "errors":
            failed = context.get("summary.failed", 0)
            try:
                return int(failed) > 0
            except (ValueError, TypeError):
                return False
        elif cond_str == "noerrors":
            failed = context.get("summary.failed", 0)
            try:
                return int(failed) == 0
            except (ValueError, TypeError):
                return True
        elif cond_str in ("target_only", "single_user"):
            is_bulk = int(context.get("items_count") or 0) > 1 or len(context.get("batch.items") or []) > 1
            has_target = bool(context.get("user.username") or context.get("username") or context.get("template.code"))
            return has_target and not is_bulk
        elif cond_str in ("all_users", "batch_users"):
            is_bulk = int(context.get("items_count") or 0) > 1 or len(context.get("items") or []) > 1 or len(context.get("batch.items") or []) > 1
            return is_bulk
        return True

    if isinstance(condition, dict):
        cond_type = condition.get("type", "always")
        if cond_type == "always":
            return True
        field = condition.get("field", "")
        op = condition.get("operator", "==")
        val = condition.get("value")
        actual = context.get(field)
        if op == ">":
            return actual is not None and actual > val
        elif op == ">=":
            return actual is not None and actual >= val
        elif op == "<":
            return actual is not None and actual < val
        elif op == "<=":
            return actual is not None and actual <= val
        elif op == "==":
            return actual == val
        elif op == "!=":
            return actual != val

    return True


def resolve_tokens(text: str, context: dict[str, Any], escape_html: bool = True) -> str:
    """Thay thế {{ variable }} bằng giá trị trong context an toàn."""
    if not text:
        return ""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        val = context.get(key)
        if val is None:
            return f"[{key}]" if escape_html else f"[{key}]"
        if isinstance(val, (list, tuple)):
            s = ", ".join(str(item) for item in val)
        else:
            s = str(val)
        return html.escape(s) if escape_html else s

    return TOKEN_REGEX.sub(_replace, text)


def compute_design_hash(design: dict[str, Any]) -> str:
    """Tính SHA256 checksum của Design JSON để phát hiện thay đổi."""
    raw = json.dumps(design, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_text_variables(
    text: str,
    event_code: str,
    menu_code: str | None = None,
) -> list[str]:
    """Kiểm tra xem chuỗi có chứa biến nào không thuộc schema của event hoặc page không.

    So khớp không phân biệt hoa thường (case-insensitive).
    Trả về danh sách các biến vi phạm.
    """
    allowed = get_all_valid_tokens_set(menu_code, event_code)
    allowed_lower = {k.lower() for k in allowed}
    for k in list(allowed):
        if "." in k:
            allowed_lower.add(k.split(".", 1)[1].lower())

    # Trích xuất các token {{ var }}
    used = TOKEN_REGEX.findall(text)
    invalid = [k for k in used if k.lower() not in allowed_lower]
    return list(dict.fromkeys(invalid))


def validate_design(
    design: dict[str, Any],
    event_code: str,
    subject: str = "",
    name: str = "",
    menu_code: str | None = None,
) -> list[str]:
    """Kiểm tra toàn diện tính hợp lệ của template trước khi lưu hoặc kích hoạt.

    Trả về danh sách các lỗi phát hiện được.
    """
    errors: list[str] = []

    if name is not None and not name.strip():
        errors.append("Tên mẫu email không được để trống.")

    if subject is not None and not subject.strip():
        errors.append("Tiêu đề email (Subject) không được để trống.")

    # Kiểm tra biến trong Subject
    if subject:
        invalid_sub_vars = validate_text_variables(subject, event_code, menu_code)
        if invalid_sub_vars:
            errors.append(f"Tiêu đề chứa biến không thuộc sự kiện: {', '.join(invalid_sub_vars)}")

    blocks = design.get("blocks", [])
    if not blocks:
        errors.append("Cần ít nhất một component trong thiết kế email.")

    allowed_vars = get_all_valid_tokens_set(menu_code, event_code)
    allowed_lower = {k.lower() for k in allowed_vars}
    for k in list(allowed_vars):
        if "." in k:
            allowed_lower.add(k.split(".", 1)[1].lower())

    for i, b in enumerate(blocks, start=1):
        b_type = b.get("type", "")
        b_text = b.get("text", "")

        # Kiểm tra biến trong text của từng block
        if b_text:
            invalid_block_vars = validate_text_variables(b_text, event_code, menu_code)
            if invalid_block_vars:
                errors.append(f"Khối #{i} ({b_type}) chứa biến không thuộc sự kiện: {', '.join(invalid_block_vars)}")

        # Kiểm tra cấu hình khối Table
        if b_type == "table":
            if event_code == "REPORT_EXPORT_COMPLETED":
                errors.append(f"Khối #{i} (table) không tương thích với sự kiện Báo cáo.")
            cols = b.get("columns", [])
            if not cols:
                errors.append(f"Khối #{i} (Bảng dữ liệu) cần ít nhất một cột hiển thị.")

        # Kiểm tra URL nút bấm an toàn
        if b_type == "button":
            url_target = b.get("url", "")
            if not url_target:
                errors.append(f"Khối #{i} (Nút liên kết) chưa chọn đích đến an toàn.")
            elif (
                not url_target.startswith("links.")
                and not url_target.startswith("/")
                and url_target.lower() not in allowed_lower
            ):
                errors.append(
                    f"Khối #{i} (Nút liên kết) sử dụng URL '{url_target}' không an toàn. Chỉ được dùng token thuộc nhóm 'links.*' hoặc đường dẫn nội bộ."
                )

    return list(dict.fromkeys(errors))


_FALLBACK_COL_MAP = {
    "name": "Tên",
    "status": "Trạng thái",
    "detail": "Chi tiết",
    "filename": "Tệp tin",
    "rows": "Số dòng",
    "roles": "Vai trò",
}


def _resolve_col_label(c_name: str) -> str:
    up_name = c_name.upper()
    if up_name in COLUMN_LABELS:
        return COLUMN_LABELS[up_name]
    return _FALLBACK_COL_MAP.get(c_name.lower(), c_name.replace("_", " ").title())


def _render_block_html(block: dict[str, Any], context: dict[str, Any]) -> str:
    """Biên dịch từng component đơn lẻ sang bảng HTML lồng nhau."""
    b_type = block.get("type", "text")
    raw_text = block.get("text", "")
    text_content = resolve_tokens(raw_text, context, escape_html=True).replace("\n", "<br>")

    color = sanitize_color(block.get("color"), "#26354a")
    bg = sanitize_color(block.get("bg"), "#ffffff")
    size = clamp_int(block.get("size"), 10, 32, 14)
    pad_top = clamp_int(block.get("pad_top", block.get("pad", 16)), 0, 60, 16)
    pad_bottom = clamp_int(block.get("pad_bottom", block.get("pad", 16)), 0, 60, 16)
    pad_left = clamp_int(block.get("pad_left", 24), 0, 60, 24)
    pad_right = clamp_int(block.get("pad_right", 24), 0, 60, 24)
    align = block.get("align", "left")
    if align not in VALID_ALIGNS:
        align = "left"

    if b_type == "divider":
        return f"""<tr>
  <td style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg};">
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
      <tr><td style="border-top:1px solid #dce3ed; font-size:1px; line-height:1px;">&nbsp;</td></tr>
    </table>
  </td>
</tr>"""

    if b_type == "spacer":
        h = max(8, pad_top)
        return f"""<tr>
  <td height="{h}" style="font-size:1px; line-height:{h}px; background-color:{bg};">&nbsp;</td>
</tr>"""

    if b_type == "header":
        return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg};">
    <div style="font-size:{size}px; font-weight:700; color:{color}; line-height:1.3; font-family:{SAFE_FONT_STACK};">
      {text_content}
    </div>
  </td>
</tr>"""

    if b_type == "footer":
        return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg}; border-top:1px solid #e5eaf1;">
    <div style="font-size:{size}px; color:{color}; line-height:1.5; font-family:{SAFE_FONT_STACK};">
      {text_content}
    </div>
  </td>
</tr>"""

    if b_type == "button":
        btn_bg = sanitize_color(block.get("bg"), "#2563eb")
        btn_color = sanitize_color(block.get("color"), "#ffffff")
        url_token = block.get("url", "links.result")
        raw_target = context.get(url_token, "#")
        # Đảm bảo liên kết có đầy đủ scheme và host, không bao giờ bị dạng http:///login
        if isinstance(raw_target, str) and raw_target.startswith("/"):
            try:
                from app.services.smtp_settings import build_app_url

                raw_target = build_app_url(raw_target)
            except Exception:
                raw_target = f"http://127.0.0.1:8050{raw_target}"
        safe_url = html.escape(str(raw_target))

        # Hình dạng button (shape): rounded (6px), round/pill (24px), square (0px)
        b_shape = block.get("button_shape", "rounded")
        if b_shape == "round":
            radius_px = "24px"
        elif b_shape == "square":
            radius_px = "0px"
        else:
            radius_px = "6px"

        # Độ rộng button (width): auto vs full
        b_width = block.get("button_width", "auto")
        tbl_width = "100%" if b_width == "full" else "auto"
        a_display = "block" if b_width == "full" else "inline-block"

        # Nếu nền màu trắng hoặc quá sáng: tự động bổ sung viền
        border_css = "border:1px solid #cbd5e1;" if btn_bg.lower() in ("#ffffff", "#fff") else ""

        return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:#ffffff;">
    <table border="0" cellpadding="0" cellspacing="0" width="{tbl_width}" align="{align}" style="{tbl_width and f'width:{tbl_width};' or ''}">
      <tr>
        <td align="center" bgcolor="{btn_bg}" style="border-radius:{radius_px}; {border_css} background-color:{btn_bg}; padding:10px 22px;">
          <a href="{safe_url}" target="_blank" style="color:{btn_color}; font-size:{size}px; font-weight:600; text-decoration:none; display:{a_display}; font-family:{SAFE_FONT_STACK};">
            {text_content}
          </a>
        </td>
      </tr>
    </table>
  </td>
</tr>"""

    if b_type == "alert":
        alert_bg = sanitize_color(block.get("bg"), "#fff4e5")
        alert_color = sanitize_color(block.get("color"), "#b54708")
        border_col = sanitize_color(block.get("border_color"), alert_color)
        return f"""<tr>
  <td style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:transparent;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" bgcolor="{alert_bg}" style="background-color:{alert_bg}; border-radius:6px; border-left:4px solid {border_col};">
      <tr>
        <td style="padding:12px 16px; font-size:{size}px; color:{alert_color}; line-height:1.5; font-family:{SAFE_FONT_STACK};">
          {text_content}
        </td>
      </tr>
    </table>
  </td>
</tr>"""

    if b_type == "kpi":
        # Render 3 thẻ KPI linh hoạt không hardcode cố định
        lbl1 = str(block.get("kpi1_label") or "Tổng số")
        val1 = (
            context.get("summary.total")
            or context.get("summary_total")
            or context.get("items_count")
            or context.get("total")
            or 0
        )

        lbl2 = str(block.get("kpi2_label") or "Thành công")
        val2 = (
            context.get("summary.success")
            or context.get("summary_success")
            or context.get("success_count")
            or 0
        )

        lbl3 = str(block.get("kpi3_label") or "Có lỗi")
        val3 = (
            context.get("summary.failed")
            or context.get("summary_failed")
            or context.get("failed_count")
            or context.get("errors_count")
            or 0
        )

        return f"""<tr>
  <td style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg};">
    <div style="font-size:{size}px; font-weight:600; color:{color}; margin-bottom:12px; font-family:{SAFE_FONT_STACK};">
      {text_content}
    </div>
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
      <tr>
        <td width="32%" bgcolor="#f3f6fa" style="padding:12px; border-radius:6px; text-align:center;">
          <div style="font-size:11px; color:#64748b; font-family:{SAFE_FONT_STACK};">{lbl1}</div>
          <div style="font-size:22px; font-weight:700; color:#1e3a5f; margin-top:4px; font-family:{SAFE_FONT_STACK};">{val1}</div>
        </td>
        <td width="2%">&nbsp;</td>
        <td width="32%" bgcolor="#ecfdf5" style="padding:12px; border-radius:6px; text-align:center;">
          <div style="font-size:11px; color:#065f46; font-family:{SAFE_FONT_STACK};">{lbl2}</div>
          <div style="font-size:22px; font-weight:700; color:#047857; margin-top:4px; font-family:{SAFE_FONT_STACK};">{val2}</div>
        </td>
        <td width="2%">&nbsp;</td>
        <td width="32%" bgcolor="#fef2f2" style="padding:12px; border-radius:6px; text-align:center;">
          <div style="font-size:11px; color:#991b1b; font-family:{SAFE_FONT_STACK};">{lbl3}</div>
          <div style="font-size:22px; font-weight:700; color:#b91c1c; margin-top:4px; font-family:{SAFE_FONT_STACK};">{val3}</div>
        </td>
      </tr>
    </table>
  </td>
</tr>"""

    if b_type == "table":
        cols = block.get("columns", ["name", "status", "detail"])
        limit = clamp_int(block.get("limit"), 1, 20, 5)

        # Lấy dữ liệu danh sách động không hardcode batch.items
        raw_items = (
            context.get(block.get("data_key", ""))
            or context.get("items")
            or context.get("batch.items")
            or context.get("rows")
            or context.get("data")
            or context.get("files_list")
            or []
        )
        if isinstance(raw_items, (list, tuple)) and raw_items and isinstance(raw_items[0], str):
            items: list[dict[str, Any]] = [
                {"name": str(s), "status": "Đính kèm", "detail": "Hoàn tất"} for s in raw_items
            ]
        elif isinstance(raw_items, list):
            items = raw_items
        else:
            items = []

        table_scope = block.get("table_scope", "all")
        if table_scope in ("target_only", "single_user"):
            target_uname = context.get("user.username") or context.get("username")
            if target_uname:
                matched = [
                    it
                    for it in items
                    if isinstance(it, dict) and str(it.get("username", "")).lower() == str(target_uname).lower()
                ]
                if matched:
                    items = matched
                else:
                    synth_row = {c: str(context.get(f"user.{c}") or context.get(c, "")) for c in cols}
                    if not any(synth_row.values()) and target_uname:
                        synth_row["username"] = str(target_uname)
                    items = [synth_row]
            elif items:
                items = items[:1]

        headers_html = "".join(
            f'<th align="left" bgcolor="#f2f5f9" style="padding:8px 10px; font-size:11px; font-weight:600; color:#475569; font-family:{SAFE_FONT_STACK};">{_resolve_col_label(c)}</th>'
            for c in cols
        )

        rows_html = ""
        sliced_items = items[:limit]
        if not sliced_items:
            rows_html = f'<tr><td colspan="{len(cols)}" style="padding:12px 10px; font-size:12px; color:#64748b; text-align:center; font-family:{SAFE_FONT_STACK};">Không có dữ liệu mục cần kiểm tra.</td></tr>'
        else:
            for item in sliced_items:
                tds = "".join(
                    f'<td style="padding:8px 10px; font-size:12px; color:#1e293b; border-bottom:1px solid #e5eaf1; font-family:{SAFE_FONT_STACK};">{html.escape(str(item.get(c, "")))}</td>'
                    for c in cols
                )
                rows_html += f"<tr>{tds}</tr>"

        return f"""<tr>
  <td style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg};">
    <div style="font-size:{size}px; font-weight:600; color:{color}; margin-bottom:8px; font-family:{SAFE_FONT_STACK};">
      {text_content}
    </div>
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse; width:100%;">
      <thead><tr>{headers_html}</tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </td>
</tr>"""

    if b_type == "info":
        custom_items = block.get("items")
        if isinstance(custom_items, list) and custom_items:
            item_rows: list[str] = []
            for itm in custom_items:
                if isinstance(itm, dict):
                    k_txt = resolve_tokens(str(itm.get("key", "")), context)
                    v_txt = resolve_tokens(str(itm.get("value", "")), context)
                    item_rows.append(f"<tr><td><strong>{k_txt}:</strong> {v_txt}</td></tr>")
            info_table_content = "\n".join(item_rows)
        else:
            info_table_content = f"""<tr><td><strong>Kỳ đối soát:</strong> {html.escape(str(context.get("batch.period", "—")))}</td></tr>
      <tr><td><strong>Người thực hiện:</strong> {html.escape(str(context.get("actor.name", "—")))}</td></tr>
      <tr><td><strong>Mã phiên chạy:</strong> {html.escape(str(context.get("batch.run_code", "—")))}</td></tr>"""

        return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg};">
    <div style="font-size:{size}px; font-weight:600; color:{color}; margin-bottom:6px; font-family:{SAFE_FONT_STACK};">
      {text_content}
    </div>
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-size:12px; color:#475569; line-height:1.8; font-family:{SAFE_FONT_STACK};">
      {info_table_content}
    </table>
  </td>
</tr>"""

    if b_type == "indicator":
        ind_type = block.get("indicator_type", "dot")
        ind_color = sanitize_color(block.get("color"), "#2563eb")
        ind_bg = sanitize_color(block.get("bg"), "#eff6ff")
        ind_shape = block.get("indicator_shape", "round")
        ind_radius = "50%" if ind_shape == "round" else ("4px" if ind_shape == "rounded" else "0px")
        border_color = sanitize_color(block.get("border_color"), ind_color)

        if ind_type == "bar":
            return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:#ffffff;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
      <tr>
        <td style="border-left:4px solid {ind_color}; background-color:{ind_bg}; padding:8px 12px; font-size:{size}px; color:{ind_color}; font-weight:600; font-family:{SAFE_FONT_STACK};">
          {text_content}
        </td>
      </tr>
    </table>
  </td>
</tr>"""
        elif ind_type == "badge":
            return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:#ffffff;">
    <span style="display:inline-block; padding:4px 12px; border-radius:{ind_radius}; background-color:{ind_bg}; color:{ind_color}; border:1px solid {border_color}; font-size:{size}px; font-weight:600; font-family:{SAFE_FONT_STACK};">
      {text_content}
    </span>
  </td>
</tr>"""
        else:  # dot
            return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg}; font-size:{size}px; color:{color}; line-height:1.6; font-family:{SAFE_FONT_STACK};">
    <span style="display:inline-block; width:10px; height:10px; border-radius:{ind_radius}; background-color:{ind_color}; margin-right:8px; vertical-align:middle;"></span>{text_content}
  </td>
</tr>"""

    # Mặc định là khối text (hỗ trợ indicator gắn trước nếu có)
    has_indicator = bool(block.get("has_indicator", False))
    if has_indicator:
        ind_type = block.get("indicator_type", "dot")
        ind_color = sanitize_color(block.get("indicator_color"), "#2563eb")
        ind_shape = block.get("indicator_shape", "round")
        ind_radius = "50%" if ind_shape == "round" else ("4px" if ind_shape == "rounded" else "0px")
        ind_label = resolve_tokens(block.get("indicator_text", ""), context, escape_html=True)

        if ind_type == "bar":
            return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg};">
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
      <tr>
        <td style="border-left:4px solid {ind_color}; padding-left:12px; font-size:{size}px; color:{color}; line-height:1.6; font-family:{SAFE_FONT_STACK};">
          {text_content}
        </td>
      </tr>
    </table>
  </td>
</tr>"""
        elif ind_type == "badge":
            badge_label = ind_label or "THÔNG BÁO"
            badge_html = f"""<span style="display:inline-block; padding:2px 8px; border-radius:{ind_radius}; background-color:{ind_color}1a; color:{ind_color}; border:1px solid {ind_color}; font-size:11px; font-weight:700; margin-right:8px; vertical-align:middle; font-family:{SAFE_FONT_STACK};">{badge_label}</span>"""
            return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg}; font-size:{size}px; color:{color}; line-height:1.6; font-family:{SAFE_FONT_STACK};">
    {badge_html}{text_content}
  </td>
</tr>"""
        else:  # dot
            dot_html = f"""<span style="display:inline-block; width:10px; height:10px; border-radius:{ind_radius}; background-color:{ind_color}; margin-right:8px; vertical-align:middle;"></span>"""
            return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg}; font-size:{size}px; color:{color}; line-height:1.6; font-family:{SAFE_FONT_STACK};">
    {dot_html}{text_content}
  </td>
</tr>"""

    return f"""<tr>
  <td align="{align}" style="padding:{pad_top}px {pad_right}px {pad_bottom}px {pad_left}px; background-color:{bg}; font-size:{size}px; color:{color}; line-height:1.6; font-family:{SAFE_FONT_STACK};">
    {text_content}
  </td>
</tr>"""


def render_html_email(
    design: dict[str, Any],
    context: dict[str, Any],
    preheader: str = "",
) -> str:
    """Biên dịch Design JSON thành Table-based HTML hoàn chỉnh tương thích Outlook & Gmail."""
    canvas = design.get("canvasSettings", {})
    max_width = clamp_int(canvas.get("maxWidth"), 480, 800, 600)
    bg_color = sanitize_color(canvas.get("bgColor"), "#f3f5f9")
    blocks = design.get("blocks", [])

    # Preheader ẩn
    preheader_html = ""
    if preheader:
        resolved_pre = resolve_tokens(preheader, context, escape_html=True)
        preheader_html = f"""<div style="display:none; font-size:1px; color:#333333; line-height:1px; max-height:0px; max-width:0px; opacity:0; overflow:hidden;">
  {resolved_pre}
</div>"""

    # Render từng block thỏa mãn condition
    rendered_blocks = []
    for b in blocks:
        cond = b.get("condition", "always")
        if evaluate_condition(cond, context):
            rendered_blocks.append(_render_block_html(b, context))

    body_content = "\n".join(rendered_blocks)

    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ReconHub Notification</title>
</head>
<body style="margin:0; padding:0; background-color:{bg_color}; font-family:{SAFE_FONT_STACK}; -webkit-font-smoothing:antialiased;">
  {preheader_html}
  <table border="0" cellpadding="0" cellspacing="0" width="100%" bgcolor="{bg_color}" style="background-color:{bg_color};">
    <tr>
      <td align="center" style="padding:20px 0;">
        <!-- Container chính tối đa {max_width}px -->
        <table border="0" cellpadding="0" cellspacing="0" width="{max_width}" style="max-width:{max_width}px; width:100%; background-color:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
          {body_content}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_plain_text(design: dict[str, Any], context: dict[str, Any]) -> str:
    """Sinh phiên bản Plain Text từ Design JSON."""
    blocks = design.get("blocks", [])
    lines: list[str] = []

    for b in blocks:
        cond = b.get("condition", "always")
        if not evaluate_condition(cond, context):
            continue

        b_type = b.get("type", "text")
        raw_text = b.get("text", "")
        t = resolve_tokens(raw_text, context, escape_html=False)

        if b_type == "header":
            lines.append(f"=== {t.upper()} ===")
        elif b_type == "divider":
            lines.append("-" * 40)
        elif b_type == "spacer":
            lines.append("")
        elif b_type == "button":
            url_token = b.get("url", "links.result")
            url = context.get(url_token, "")
            lines.append(f"[{t}]: {url}")
        elif b_type == "kpi":
            lbl1 = str(b.get("kpi1_label") or "Tổng số")
            val1 = (
                context.get("summary.total")
                or context.get("summary_total")
                or context.get("items_count")
                or context.get("total")
                or 0
            )
            lbl2 = str(b.get("kpi2_label") or "Thành công")
            val2 = (
                context.get("summary.success")
                or context.get("summary_success")
                or context.get("success_count")
                or 0
            )
            lbl3 = str(b.get("kpi3_label") or "Lỗi")
            val3 = (
                context.get("summary.failed")
                or context.get("summary_failed")
                or context.get("failed_count")
                or context.get("errors_count")
                or 0
            )
            lines.append(f"[KẾT QUẢ] {t}: {lbl1}: {val1} | {lbl2}: {val2} | {lbl3}: {val3}")
        elif b_type == "table":
            lines.append(f"[{t}]")
            cols = b.get("columns", ["name", "status", "detail"])
            limit = clamp_int(b.get("limit"), 1, 20, 5)
            raw_items = (
                context.get(b.get("data_key", ""))
                or context.get("items")
                or context.get("batch.items")
                or context.get("rows")
                or context.get("data")
                or context.get("files_list")
                or []
            )
            if isinstance(raw_items, (list, tuple)) and raw_items and isinstance(raw_items[0], str):
                items = [{"name": str(s), "status": "Đính kèm", "detail": "Hoàn tất"} for s in raw_items]
            elif isinstance(raw_items, list):
                items = raw_items
            else:
                items = []

            table_scope = b.get("table_scope", "all")
            if table_scope in ("target_only", "single_user"):
                target_uname = context.get("user.username") or context.get("username")
                if target_uname:
                    matched = [
                        it
                        for it in items
                        if isinstance(it, dict) and str(it.get("username", "")).lower() == str(target_uname).lower()
                    ]
                    if matched:
                        items = matched
                    else:
                        synth_row = {c: str(context.get(f"user.{c}") or context.get(c, "")) for c in cols}
                        if not any(synth_row.values()) and target_uname:
                            synth_row["username"] = str(target_uname)
                        items = [synth_row]
                elif items:
                    items = items[:1]

            for item in items[:limit]:
                row_str = " | ".join(f"{_resolve_col_label(c)}: {item.get(c, '')}" for c in cols)
                lines.append(f"  * {row_str}")
        elif b_type == "indicator":
            lines.append(f"[•] {t}")
        else:
            if b.get("has_indicator"):
                ind_label = b.get("indicator_text", "")
                if ind_label:
                    lines.append(f"[{ind_label}] {t}")
                else:
                    lines.append(f"• {t}")
            else:
                lines.append(t)

    return "\n\n".join(line for line in lines if line.strip())
