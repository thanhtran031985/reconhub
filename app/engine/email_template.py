"""Engine for email templates: token parsing, rendering, and built-in defaults.

Pure functions without DB dependencies.
"""

from __future__ import annotations

import re
from typing import Any

# Pattern to capture {{ token_name }} with optional surrounding whitespace
TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

SUPPORTED_EMAIL_FUNCTIONS: list[dict[str, Any]] = [
    {
        "code": "GENERAL_EXPORT",
        "label": "Mẫu mặc định chung (Fallback)",
        "description": "Mẫu dùng chung cho mọi chức năng xuất dữ liệu khi chưa có mẫu riêng (User, Menu, Template...)",
        "icon": "lucide:layers",
        "is_fallback": True,
    },
    {
        "code": "TEMPLATE_LIST_EXPORT",
        "label": "Xuất danh sách Template",
        "description": "Mẫu email gửi kèm danh sách mẫu đối soát định dạng Excel, Word, PDF",
        "icon": "lucide:file-spreadsheet",
        "is_fallback": False,
    },
    {
        "code": "USER_LIST_EXPORT",
        "label": "Xuất danh sách Người dùng",
        "description": "Mẫu email gửi kèm danh sách tài khoản người dùng hệ thống",
        "icon": "lucide:users",
        "is_fallback": False,
    },
    {
        "code": "MENU_LIST_EXPORT",
        "label": "Xuất danh mục Menu & Quyền",
        "description": "Mẫu email gửi kèm cây menu và ma trận phân quyền",
        "icon": "lucide:menu",
        "is_fallback": False,
    },
    {
        "code": "DATA_SOURCE_EXPORT",
        "label": "Xuất danh sách Data Sources",
        "description": "Mẫu email gửi kèm danh sách kết nối cơ sở dữ liệu",
        "icon": "lucide:database",
        "is_fallback": False,
    },
    {
        "code": "RUN_RESULT_EXPORT",
        "label": "Xuất kết quả đối soát",
        "description": "Mẫu email gửi kèm kết quả chi tiết của phiên chạy đối soát",
        "icon": "lucide:check-circle-2",
        "is_fallback": False,
    },
    {
        "code": "REPORT_EXPORT",
        "label": "Xuất báo cáo tổng hợp",
        "description": "Email gửi báo cáo định kỳ hoặc báo cáo theo biểu mẫu",
        "icon": "lucide:bar-chart-3",
        "is_fallback": False,
    },
]


def get_email_function_meta(function_code: str) -> dict[str, Any] | None:
    """Find metadata for a supported function code."""
    for fn in SUPPORTED_EMAIL_FUNCTIONS:
        if fn["code"] == function_code:
            return fn
    return None


def format_token_value(key: str, val: Any) -> str:
    """Format a context value into HTML-safe string for replacement."""
    if val is None:
        return ""
    if key == "files_list" and isinstance(val, (list, tuple)):
        if not val:
            return "<em>Không có tệp đính kèm</em>"
        items = "".join(f"<li>{item}</li>" for item in val)
        return f"<ul style='margin: 8px 0; padding-left: 20px;'>{items}</ul>"
    if isinstance(val, (list, tuple)):
        return ", ".join(str(item) for item in val)
    return str(val)


def render_email_subject(pattern: str, context: dict[str, Any]) -> str:
    """Render subject line by replacing {{token}} with context values."""
    if not pattern:
        return ""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            val = context[key]
            if isinstance(val, (list, tuple)):
                return ", ".join(str(item) for item in val)
            return str(val) if val is not None else ""
        return match.group(0)

    return TOKEN_PATTERN.sub(_replace, pattern).strip()


def render_email_body(template_html: str, context: dict[str, Any]) -> str:
    """Render HTML body by replacing {{token}} with context values."""
    if not template_html:
        return ""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return format_token_value(key, context[key])
        return match.group(0)

    return TOKEN_PATTERN.sub(_replace, template_html)


def get_builtin_default_template(function_code: str) -> dict[str, Any]:
    """Return default template dictionary for a given function code."""
    if function_code == "GENERAL_EXPORT":
        available_tokens = [
            {"token": "{{module_name}}", "label": "Tên phân hệ / chức năng", "example": "Mẫu đối soát / Người dùng / Menu"},
            {"token": "{{user_name}}", "label": "Tài khoản người gửi", "example": "admin"},
            {"token": "{{created_at}}", "label": "Thời điểm gửi", "example": "18/11/2026 10:30"},
            {"token": "{{items_count}}", "label": "Số lượng bản ghi", "example": "20"},
            {"token": "{{notes}}", "label": "Ghi chú bổ sung", "example": "Dữ liệu kết xuất từ hệ thống ReconHub."},
            {"token": "{{files_list}}", "label": "Danh sách file đính kèm", "example": "export_data.xlsx, .pdf"},
        ]
        mock_context = {
            "module_name": "Dữ liệu hệ thống",
            "user_name": "admin",
            "created_at": "18/11/2026 10:30",
            "items_count": 20,
            "notes": "<p>Dữ liệu kết xuất chính thức từ hệ thống ReconHub.</p>",
            "files_list": ["du_lieu_xuat.xlsx", "du_lieu_xuat.pdf"],
        }
        subject_pattern = "ReconHub - Danh sách {{module_name}} [{{items_count}} bản ghi]"
        body_html = """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #212529; max-width: 680px; margin: 0 auto; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; background: #ffffff;">
    <div style="background: linear-gradient(135deg, #1971c2 0%, #1864ab 100%); color: #ffffff; padding: 20px 24px;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 600;">ReconHub - Hệ thống đối soát dữ liệu</h2>
        <p style="margin: 4px 0 0; font-size: 13px; opacity: 0.9;">Kết xuất dữ liệu: {{module_name}}</p>
    </div>
    <div style="padding: 24px;">
        <p style="margin-top: 0;">Kính gửi anh/chị,</p>
        <p>Hệ thống trân trọng gửi kèm danh sách <b>{{items_count}}</b> bản ghi thuộc phân hệ <b>{{module_name}}</b> được trích xuất từ hệ thống ReconHub.</p>
        <div style="background: #f8f9fa; border-left: 4px solid #1971c2; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
            <p style="margin: 0; font-size: 13px;"><b>Người xuất:</b> {{user_name}}</p>
            <p style="margin: 4px 0 0; font-size: 13px;"><b>Thời điểm xuất:</b> {{created_at}}</p>
        </div>
        <div style="margin: 16px 0;">
            <p style="margin: 0 0 6px; font-weight: 600; font-size: 13px;">Tập tin đính kèm:</p>
            {{files_list}}
        </div>
        <div style="margin: 16px 0; font-size: 13px; color: #495057;">
            {{notes}}
        </div>
        <p style="margin-bottom: 0; font-size: 12px; color: #868e96; border-top: 1px solid #eee; padding-top: 16px;">
            Email này được gửi tự động từ hệ thống ReconHub. Vui lòng không trả lời trực tiếp email này.
        </p>
    </div>
</div>"""
        return {
            "template_code": "TMPL_GENERAL_DEFAULT",
            "name": "Mẫu mặc định chung (Fallback)",
            "function_code": "GENERAL_EXPORT",
            "subject_pattern": subject_pattern,
            "body_html": body_html,
            "available_tokens": available_tokens,
            "mock_context": mock_context,
            "is_default": "Y",
        }

    if function_code == "USER_LIST_EXPORT":
        available_tokens = [
            {"token": "{{user_name}}", "label": "Tài khoản người gửi", "example": "admin"},
            {"token": "{{created_at}}", "label": "Thời điểm gửi", "example": "18/11/2026 10:30"},
            {"token": "{{items_count}}", "label": "Số lượng người dùng", "example": "8"},
            {"token": "{{notes}}", "label": "Ghi chú bổ sung", "example": "Danh sách người dùng đang hoạt động."},
            {"token": "{{files_list}}", "label": "Danh sách file đính kèm", "example": "danh_sach_nguoi_dung.xlsx"},
        ]
        mock_context = {
            "user_name": "admin",
            "created_at": "18/11/2026 10:30",
            "items_count": 8,
            "notes": "<p>Danh sách tài khoản người dùng hệ thống ReconHub.</p>",
            "files_list": ["danh_sach_nguoi_dung.xlsx"],
        }
        subject_pattern = "ReconHub - Danh sách người dùng hệ thống [{{items_count}} tài khoản]"
        body_html = """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #212529; max-width: 680px; margin: 0 auto; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; background: #ffffff;">
    <div style="background: linear-gradient(135deg, #0c8599 0%, #0b7285 100%); color: #ffffff; padding: 20px 24px;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 600;">ReconHub - Quản trị Người dùng</h2>
        <p style="margin: 4px 0 0; font-size: 13px; opacity: 0.9;">Danh sách tài khoản người dùng</p>
    </div>
    <div style="padding: 24px;">
        <p style="margin-top: 0;">Kính gửi anh/chị,</p>
        <p>Hệ thống trân trọng gửi danh sách <b>{{items_count}}</b> tài khoản người dùng xuất bởi <b>{{user_name}}</b> lúc {{created_at}}.</p>
        <div style="margin: 16px 0;">{{files_list}}</div>
        <div style="margin: 16px 0; font-size: 13px; color: #495057;">{{notes}}</div>
    </div>
</div>"""
        return {
            "template_code": "TMPL_USER_DEFAULT",
            "name": "Mẫu xuất danh sách Người dùng",
            "function_code": "USER_LIST_EXPORT",
            "subject_pattern": subject_pattern,
            "body_html": body_html,
            "available_tokens": available_tokens,
            "mock_context": mock_context,
            "is_default": "Y",
        }

    if function_code == "MENU_LIST_EXPORT":
        available_tokens = [
            {"token": "{{user_name}}", "label": "Tài khoản người gửi", "example": "admin"},
            {"token": "{{created_at}}", "label": "Thời điểm gửi", "example": "18/11/2026 10:30"},
            {"token": "{{items_count}}", "label": "Số lượng menu", "example": "16"},
            {"token": "{{notes}}", "label": "Ghi chú bổ sung", "example": "Cấu trúc menu hệ thống."},
            {"token": "{{files_list}}", "label": "Danh sách file đính kèm", "example": "danh_muc_menu.xlsx"},
        ]
        mock_context = {
            "user_name": "admin",
            "created_at": "18/11/2026 10:30",
            "items_count": 16,
            "notes": "<p>Cây danh mục menu và phân quyền hệ thống ReconHub.</p>",
            "files_list": ["danh_muc_menu.xlsx"],
        }
        subject_pattern = "ReconHub - Danh mục Menu & Phân quyền [{{items_count}} mục]"
        body_html = """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #212529; max-width: 680px; margin: 0 auto; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; background: #ffffff;">
    <div style="background: linear-gradient(135deg, #495057 0%, #343a40 100%); color: #ffffff; padding: 20px 24px;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 600;">ReconHub - Danh mục Menu & Phân quyền</h2>
    </div>
    <div style="padding: 24px;">
        <p>Hệ thống trân trọng gửi danh mục <b>{{items_count}}</b> chức năng menu xuất bởi <b>{{user_name}}</b> lúc {{created_at}}.</p>
        <div style="margin: 16px 0;">{{files_list}}</div>
        <div style="margin: 16px 0; font-size: 13px; color: #495057;">{{notes}}</div>
    </div>
</div>"""
        return {
            "template_code": "TMPL_MENU_DEFAULT",
            "name": "Mẫu xuất danh mục Menu",
            "function_code": "MENU_LIST_EXPORT",
            "subject_pattern": subject_pattern,
            "body_html": body_html,
            "available_tokens": available_tokens,
            "mock_context": mock_context,
            "is_default": "Y",
        }

    if function_code == "DATA_SOURCE_EXPORT":
        available_tokens = [
            {"token": "{{user_name}}", "label": "Tài khoản người gửi", "example": "admin"},
            {"token": "{{created_at}}", "label": "Thời điểm gửi", "example": "18/11/2026 10:30"},
            {"token": "{{items_count}}", "label": "Số lượng nguồn dữ liệu", "example": "4"},
            {"token": "{{notes}}", "label": "Ghi chú bổ sung", "example": "Danh sách kết nối cơ sở dữ liệu."},
            {"token": "{{files_list}}", "label": "Danh sách file đính kèm", "example": "data_sources.xlsx"},
        ]
        mock_context = {
            "user_name": "admin",
            "created_at": "18/11/2026 10:30",
            "items_count": 4,
            "notes": "<p>Danh sách kết nối nguồn dữ liệu Oracle / Data Sources.</p>",
            "files_list": ["data_sources.xlsx"],
        }
        subject_pattern = "ReconHub - Danh sách Data Sources [{{items_count}} nguồn]"
        body_html = """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #212529; max-width: 680px; margin: 0 auto; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; background: #ffffff;">
    <div style="background: linear-gradient(135deg, #e67700 0%, #d9480f 100%); color: #ffffff; padding: 20px 24px;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 600;">ReconHub - Nguồn dữ liệu Data Sources</h2>
    </div>
    <div style="padding: 24px;">
        <p>Hệ thống gửi danh sách <b>{{items_count}}</b> nguồn kết nối xuất bởi <b>{{user_name}}</b> lúc {{created_at}}.</p>
        <div style="margin: 16px 0;">{{files_list}}</div>
        <div style="margin: 16px 0; font-size: 13px; color: #495057;">{{notes}}</div>
    </div>
</div>"""
        return {
            "template_code": "TMPL_DATASOURCE_DEFAULT",
            "name": "Mẫu xuất Data Sources",
            "function_code": "DATA_SOURCE_EXPORT",
            "subject_pattern": subject_pattern,
            "body_html": body_html,
            "available_tokens": available_tokens,
            "mock_context": mock_context,
            "is_default": "Y",
        }

    if function_code == "TEMPLATE_LIST_EXPORT":
        available_tokens = [
            {"token": "{{user_name}}", "label": "Tài khoản người gửi", "example": "admin"},
            {"token": "{{created_at}}", "label": "Thời điểm gửi", "example": "18/11/2026 10:30"},
            {"token": "{{items_count}}", "label": "Số lượng template", "example": "12"},
            {"token": "{{notes}}", "label": "Ghi chú bổ sung", "example": "Danh sách cấu hình đã phê duyệt."},
            {"token": "{{files_list}}", "label": "Danh sách file đính kèm", "example": "templates_export.xlsx, .docx, .pdf"},
        ]
        mock_context = {
            "user_name": "admin",
            "created_at": "18/11/2026 10:30",
            "items_count": 12,
            "notes": "<p>Danh sách cấu hình mẫu đối soát đang hoạt động.</p>",
            "files_list": ["templates_export.xlsx", "templates_export.docx", "templates_export.pdf"],
        }
        subject_pattern = "ReconHub - Danh sách cấu hình template [{{items_count}} template]"
        body_html = """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #212529; max-width: 680px; margin: 0 auto; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; background: #ffffff;">
    <div style="background: linear-gradient(135deg, #1971c2 0%, #1864ab 100%); color: #ffffff; padding: 20px 24px;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 600;">ReconHub - Hệ thống đối soát dữ liệu</h2>
        <p style="margin: 4px 0 0; font-size: 13px; opacity: 0.9;">Xuất danh mục cấu hình template</p>
    </div>
    <div style="padding: 24px;">
        <p style="margin-top: 0;">Kính gửi anh/chị,</p>
        <p>Hệ thống trân trọng gửi kèm danh sách <b>{{items_count}}</b> mẫu đối soát đã được trích xuất từ hệ thống ReconHub.</p>
        <div style="background: #f8f9fa; border-left: 4px solid #1971c2; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
            <p style="margin: 0; font-size: 13px;"><b>Người xuất:</b> {{user_name}}</p>
            <p style="margin: 4px 0 0; font-size: 13px;"><b>Thời điểm xuất:</b> {{created_at}}</p>
        </div>
        <div style="margin: 16px 0;">
            <p style="margin: 0 0 6px; font-weight: 600; font-size: 13px;">Tập tin đính kèm:</p>
            {{files_list}}
        </div>
        <div style="margin: 16px 0; font-size: 13px; color: #495057;">
            {{notes}}
        </div>
        <p style="margin-bottom: 0; font-size: 12px; color: #868e96; border-top: 1px solid #eee; padding-top: 16px;">
            Email này được gửi tự động từ hệ thống ReconHub. Vui lòng không trả lời trực tiếp email này.
        </p>
    </div>
</div>"""
        return {
            "template_code": "TMPL_LIST_DEFAULT",
            "name": "Mẫu mặc định: Xuất danh sách Template",
            "function_code": "TEMPLATE_LIST_EXPORT",
            "subject_pattern": subject_pattern,
            "body_html": body_html,
            "available_tokens": available_tokens,
            "mock_context": mock_context,
            "is_default": "Y",
        }

    if function_code == "RUN_RESULT_EXPORT":
        available_tokens = [
            {"token": "{{run_id}}", "label": "Mã lần chạy đối soát", "example": "RUN-20261118-001"},
            {"token": "{{template_name}}", "label": "Tên template", "example": "Đối soát hóa đơn DTP"},
            {"token": "{{user_name}}", "label": "Người thực hiện", "example": "admin"},
            {"token": "{{status}}", "label": "Trạng thái", "example": "DONE"},
            {"token": "{{total_rows}}", "label": "Tổng số dòng", "example": "1,500"},
            {"token": "{{match_count}}", "label": "Số dòng khớp", "example": "1,480"},
            {"token": "{{mismatch_count}}", "label": "Số dòng lệch", "example": "20"},
            {"token": "{{created_at}}", "label": "Thời điểm xuất", "example": "18/11/2026 10:30"},
            {"token": "{{notes}}", "label": "Ghi chú", "example": "Kết quả đối soát định kỳ."},
            {"token": "{{files_list}}", "label": "Danh sách file đính kèm", "example": "run_result.xlsx"},
        ]
        mock_context = {
            "run_id": "RUN-20261118-001",
            "template_name": "Đối soát hóa đơn DTP",
            "user_name": "admin",
            "status": "DONE",
            "total_rows": "1,500",
            "match_count": "1,480",
            "mismatch_count": "20",
            "created_at": "18/11/2026 10:30",
            "notes": "<p>Đối soát tự động hàng ngày.</p>",
            "files_list": ["ket_qua_doi_soat_RUN-20261118-001.xlsx"],
        }
        subject_pattern = "ReconHub - Kết quả đối soát {{template_name}} [{{run_id}}]"
        body_html = """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #212529; max-width: 680px; margin: 0 auto; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; background: #ffffff;">
    <div style="background: linear-gradient(135deg, #2b8a3e 0%, #237032 100%); color: #ffffff; padding: 20px 24px;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 600;">ReconHub - Kết quả đối soát</h2>
        <p style="margin: 4px 0 0; font-size: 13px; opacity: 0.9;">Mã phiên: {{run_id}}</p>
    </div>
    <div style="padding: 24px;">
        <p style="margin-top: 0;">Kính gửi anh/chị,</p>
        <p>Hệ thống gửi báo cáo kết quả đối soát mẫu <b>{{template_name}}</b> thực hiện bởi <b>{{user_name}}</b> vào lúc {{created_at}}.</p>
        <div style="background: #f8f9fa; border-left: 4px solid #2b8a3e; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
            <p style="margin: 0; font-size: 13px;"><b>Trạng thái:</b> {{status}}</p>
            <p style="margin: 4px 0 0; font-size: 13px;"><b>Tổng số dòng:</b> {{total_rows}} (Khớp: {{match_count}}, Lệch: {{mismatch_count}})</p>
        </div>
        <div style="margin: 16px 0;">
            <p style="margin: 0 0 6px; font-weight: 600; font-size: 13px;">Tập tin kết quả đính kèm:</p>
            {{files_list}}
        </div>
        <div style="margin: 16px 0; font-size: 13px; color: #495057;">
            {{notes}}
        </div>
    </div>
</div>"""
        return {
            "template_code": "TMPL_RUN_DEFAULT",
            "name": "Mẫu mặc định: Kết quả đối soát",
            "function_code": "RUN_RESULT_EXPORT",
            "subject_pattern": subject_pattern,
            "body_html": body_html,
            "available_tokens": available_tokens,
            "mock_context": mock_context,
            "is_default": "Y",
        }

    if function_code == "REPORT_EXPORT":
        available_tokens = [
            {"token": "{{report_name}}", "label": "Tên báo cáo", "example": "Báo cáo tổng hợp chênh lệch"},
            {"token": "{{user_name}}", "label": "Người xuất", "example": "admin"},
            {"token": "{{period}}", "label": "Kỳ báo cáo", "example": "Tháng 11/2026"},
            {"token": "{{created_at}}", "label": "Thời điểm xuất", "example": "18/11/2026 10:30"},
            {"token": "{{notes}}", "label": "Ghi chú", "example": "Báo cáo nộp lãnh đạo phòng."},
            {"token": "{{files_list}}", "label": "Danh sách file đính kèm", "example": "bao_cao_thang_11.xlsx"},
        ]
        mock_context = {
            "report_name": "Báo cáo tổng hợp chênh lệch",
            "user_name": "admin",
            "period": "Tháng 11/2026",
            "created_at": "18/11/2026 10:30",
            "notes": "<p>Báo cáo định kỳ hàng tháng.</p>",
            "files_list": ["bao_cao_thang_11.xlsx"],
        }
        subject_pattern = "ReconHub - {{report_name}} [{{period}}]"
        body_html = """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #212529; max-width: 680px; margin: 0 auto; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; background: #ffffff;">
    <div style="background: linear-gradient(135deg, #7048e8 0%, #5f3dc4 100%); color: #ffffff; padding: 20px 24px;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 600;">ReconHub - Báo cáo tổng hợp</h2>
        <p style="margin: 4px 0 0; font-size: 13px; opacity: 0.9;">{{report_name}}</p>
    </div>
    <div style="padding: 24px;">
        <p style="margin-top: 0;">Kính gửi anh/chị,</p>
        <p>Hệ thống trân trọng gửi báo cáo <b>{{report_name}}</b> kỳ <b>{{period}}</b> xuất bởi <b>{{user_name}}</b> lúc {{created_at}}.</p>
        <div style="margin: 16px 0;">
            <p style="margin: 0 0 6px; font-weight: 600; font-size: 13px;">Tập tin đính kèm:</p>
            {{files_list}}
        </div>
        <div style="margin: 16px 0; font-size: 13px; color: #495057;">
            {{notes}}
        </div>
    </div>
</div>"""
        return {
            "template_code": "TMPL_REPORT_DEFAULT",
            "name": "Mẫu mặc định: Báo cáo tổng hợp",
            "function_code": "REPORT_EXPORT",
            "subject_pattern": subject_pattern,
            "body_html": body_html,
            "available_tokens": available_tokens,
            "mock_context": mock_context,
            "is_default": "Y",
        }

    # Fallback generic
    return {
        "template_code": f"TMPL_{function_code}_DEFAULT",
        "name": f"Mẫu mặc định ({function_code})",
        "function_code": function_code,
        "subject_pattern": "ReconHub - Thông báo hệ thống [{{user_name}}]",
        "body_html": "<p>Kính gửi anh/chị,</p><p>Hệ thống ReconHub gửi thông báo.</p><p>{{notes}}</p><p>{{files_list}}</p>",
        "available_tokens": [
            {"token": "{{user_name}}", "label": "Người gửi", "example": "admin"},
            {"token": "{{created_at}}", "label": "Thời điểm", "example": "18/11/2026"},
            {"token": "{{notes}}", "label": "Ghi chú", "example": "Thông báo"},
            {"token": "{{files_list}}", "label": "File đính kèm", "example": "file.xlsx"},
        ],
        "mock_context": {
            "user_name": "admin",
            "created_at": "18/11/2026",
            "notes": "Thông báo hệ thống",
            "files_list": ["tep_tin.xlsx"],
        },
        "is_default": "Y",
    }
