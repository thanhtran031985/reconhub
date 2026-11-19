"""Unit tests for Mail Renderer, Validator, and Plain Text Generator."""

from __future__ import annotations

import pytest

from app.engine.mail_event_registry import get_sample_payload
from app.engine.mail_renderer import (
    clamp_int,
    compute_design_hash,
    evaluate_condition,
    render_html_email,
    render_plain_text,
    resolve_tokens,
    sanitize_color,
    validate_design,
)


@pytest.fixture
def sample_batch_design():
    return {
        "schemaVersion": 1,
        "canvasSettings": {"maxWidth": 600, "bgColor": "#f3f5f9"},
        "blocks": [
            {
                "id": 1,
                "type": "header",
                "text": "ReconHub | Kết quả chạy bộ đối soát",
                "color": "#1e3a5f",
                "bg": "#ffffff",
                "size": 20,
                "pad": 18,
                "align": "left",
                "condition": "always",
            },
            {
                "id": 2,
                "type": "text",
                "text": "Xin chào {{actor.name}},\nPhiên chạy {{batch.name}} đã kết thúc.",
                "color": "#26354a",
                "bg": "#ffffff",
                "size": 14,
                "pad": 16,
                "align": "left",
                "condition": "always",
            },
            {
                "id": 3,
                "type": "alert",
                "text": "Cảnh báo: Có {{summary.failed}} template lỗi cần kiểm tra gấp!",
                "color": "#b54708",
                "bg": "#fff4e5",
                "size": 14,
                "pad": 16,
                "align": "left",
                "condition": "errors",
            },
            {
                "id": 4,
                "type": "kpi",
                "text": "Thống kê kết quả",
                "color": "#26354a",
                "bg": "#ffffff",
                "size": 14,
                "pad": 16,
                "align": "left",
                "condition": "always",
            },
            {
                "id": 5,
                "type": "table",
                "text": "Danh sách template cần kiểm tra",
                "color": "#26354a",
                "bg": "#ffffff",
                "size": 14,
                "pad": 16,
                "align": "left",
                "limit": 5,
                "columns": ["name", "status", "detail"],
                "condition": "errors",
            },
            {
                "id": 6,
                "type": "button",
                "text": "Mở kết quả phiên chạy",
                "color": "#ffffff",
                "bg": "#2563eb",
                "size": 13,
                "pad": 14,
                "align": "center",
                "url": "links.result",
                "condition": "always",
            },
            {
                "id": 7,
                "type": "footer",
                "text": "Email tự động từ hệ thống ReconHub.",
                "color": "#64748b",
                "bg": "#ffffff",
                "size": 11,
                "pad": 14,
                "align": "left",
                "condition": "always",
            },
        ],
    }


def test_sanitize_helpers():
    assert sanitize_color("#123456") == "#123456"
    assert sanitize_color("#fff") == "#fff"
    assert sanitize_color("invalid_color", "#000000") == "#000000"
    assert sanitize_color("javascript:alert(1)", "#ffffff") == "#ffffff"

    assert clamp_int(50, 10, 32, 14) == 32
    assert clamp_int(5, 10, 32, 14) == 10
    assert clamp_int("invalid", 10, 32, 14) == 14


def test_resolve_tokens_and_xss_escape():
    ctx = {"actor.name": "<script>alert('XSS')</script>", "summary.total": 20}
    resolved = resolve_tokens("Chào {{actor.name}}, tổng số: {{summary.total}}", ctx, escape_html=True)
    assert "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;" in resolved
    assert "<script>" not in resolved
    assert "20" in resolved

    # Fallback to [token] if missing in context
    resolved_missing = resolve_tokens("Biến {{missing.var}} chưa có", ctx, escape_html=True)
    assert "[missing.var]" in resolved_missing


def test_evaluate_condition():
    ctx_errors = {"summary.failed": 2}
    ctx_no_errors = {"summary.failed": 0}

    assert evaluate_condition("always", ctx_errors) is True
    assert evaluate_condition("errors", ctx_errors) is True
    assert evaluate_condition("errors", ctx_no_errors) is False
    assert evaluate_condition("noerrors", ctx_no_errors) is True
    assert evaluate_condition("noerrors", ctx_errors) is False


def test_render_html_table_based_nested(sample_batch_design):
    ctx_error = get_sample_payload("BATCH_RUN_COMPLETED", "error")
    html_out = render_html_email(sample_batch_design, ctx_error, preheader="Thông báo kết quả")

    # Kiểm tra cấu trúc Table-based
    assert "<table" in html_out
    assert "<td" in html_out
    assert "<tr" in html_out
    assert 'width="600"' in html_out
    assert "Thông báo kết quả" in html_out  # Preheader
    assert "Nguyễn Văn A" in html_out
    assert "NGAN_HANG_B" in html_out
    assert "Mở kết quả phiên chạy" in html_out

    # Kiểm tra condition errors: alert và table xuất hiện
    assert "Cảnh báo: Có 2 template lỗi" in html_out
    assert "Danh sách template cần kiểm tra" in html_out


def test_render_html_condition_hiding(sample_batch_design):
    ctx_success = get_sample_payload("BATCH_RUN_COMPLETED", "success")
    html_out = render_html_email(sample_batch_design, ctx_success)

    # Do condition="errors", alert và table không xuất hiện trong email success
    assert "Cảnh báo: Có" not in html_out
    assert "Danh sách template cần kiểm tra" not in html_out
    assert "ReconHub | Kết quả chạy bộ đối soát" in html_out


def test_render_plain_text(sample_batch_design):
    ctx_error = get_sample_payload("BATCH_RUN_COMPLETED", "error")
    text_out = render_plain_text(sample_batch_design, ctx_error)

    assert "=== RECONHUB | KẾT QUẢ CHẠY BỘ ĐỐI SOÁT ===" in text_out
    assert "Xin chào Nguyễn Văn A" in text_out
    assert "[KẾT QUẢ] Thống kê kết quả: Tổng số: 20 | Thành công: 18 | Lỗi: 2" in text_out
    assert "[Mở kết quả phiên chạy]: /batch-runs/BR-202610-0042" in text_out


def test_validate_design_success(sample_batch_design):
    errors = validate_design(
        sample_batch_design,
        event_code="BATCH_RUN_COMPLETED",
        subject="[ReconHub] Kết quả chạy bộ {{batch.name}}",
        name="Mẫu chạy bộ chuẩn",
    )
    assert errors == []


def test_validate_design_violations(sample_batch_design):
    # Subject chứa biến không hợp lệ
    errors = validate_design(
        sample_batch_design,
        event_code="BATCH_RUN_COMPLETED",
        subject="[ReconHub] File: {{invalid.variable}}",
        name="",
    )
    assert any("Tên mẫu email không được để trống" in e for e in errors)
    assert any("invalid.variable" in e for e in errors)

    # Empty blocks
    empty_design = {"blocks": []}
    errors_empty = validate_design(empty_design, "BATCH_RUN_COMPLETED", subject="Test", name="Test")
    assert any("Cần ít nhất một component" in e for e in errors_empty)

    # Incompatible event check: table in REPORT_EXPORT_COMPLETED
    errors_incompat = validate_design(sample_batch_design, "REPORT_EXPORT_COMPLETED", subject="Test", name="Test")
    assert any("không tương thích với sự kiện Báo cáo" in e for e in errors_incompat)


def test_compute_design_hash(sample_batch_design):
    h1 = compute_design_hash(sample_batch_design)
    h2 = compute_design_hash(sample_batch_design)
    assert h1 == h2
    assert len(h1) == 64

    modified = dict(sample_batch_design)
    modified["blocks"] = list(sample_batch_design["blocks"])[:-1]
    h3 = compute_design_hash(modified)
    assert h1 != h3


def test_render_indicator_components():
    design = {
        "canvasSettings": {"bgColor": "#ffffff"},
        "blocks": [
            {
                "id": 1,
                "type": "text",
                "text": "Nội dung có chấm tròn",
                "has_indicator": True,
                "indicator_type": "dot",
                "indicator_color": "#10b981",
                "indicator_shape": "round",
            },
            {
                "id": 2,
                "type": "text",
                "text": "Nội dung có thanh viền",
                "has_indicator": True,
                "indicator_type": "bar",
                "indicator_color": "#2563eb",
            },
            {
                "id": 3,
                "type": "text",
                "text": "Nội dung có huy hiệu",
                "has_indicator": True,
                "indicator_type": "badge",
                "indicator_color": "#ef4444",
                "indicator_text": "CẢNH BÁO",
            },
            {
                "id": 4,
                "type": "indicator",
                "text": "Chỉ báo độc lập",
                "indicator_type": "dot",
                "color": "#059669",
            },
        ],
    }
    context = {}
    html_out = render_html_email(design, context)

    # Kiểm tra màu nền ngoài email là #ffffff
    assert 'bgcolor="#ffffff"' in html_out
    # Kiểm tra chấm tròn xanh lá
    assert "background-color:#10b981" in html_out
    assert "border-radius:50%" in html_out
    # Kiểm tra thanh viền xanh dương
    assert "border-left:4px solid #2563eb" in html_out
    # Kiểm tra huy hiệu màu đỏ
    assert "CẢNH BÁO" in html_out
    assert "#ef4444" in html_out
    # Kiểm tra chỉ báo độc lập
    assert "Chỉ báo độc lập" in html_out

    # Kiểm tra Plain text
    text_out = render_plain_text(design, context)
    assert "[CẢNH BÁO] Nội dung có huy hiệu" in text_out
    assert "[•] Chỉ báo độc lập" in text_out


def test_render_button_shapes_and_width():
    """Kiểm tra render nút bấm với các hình dạng bo tròn, vuông, bo góc và độ rộng."""
    design = {
        "blocks": [
            {
                "id": 1,
                "type": "button",
                "text": "Nút bo tròn",
                "button_shape": "round",
                "button_width": "auto",
                "bg": "#2563eb",
                "color": "#ffffff",
                "url": "links.login",
            },
            {
                "id": 2,
                "type": "button",
                "text": "Nút vuông toàn hàng nền trắng",
                "button_shape": "square",
                "button_width": "full",
                "bg": "#ffffff",
                "color": "#26354a",
                "url": "links.page",
            },
            {
                "id": 3,
                "type": "button",
                "text": "Nút bo góc nhẹ",
                "button_shape": "rounded",
                "button_width": "auto",
                "bg": "#059669",
                "color": "#ffffff",
                "url": "links.result",
            },
        ]
    }
    context = {"links.login": "/login", "links.page": "/users", "links.result": "/results"}
    html_out = render_html_email(design, context)

    # Nút bo tròn
    assert "border-radius:24px" in html_out
    assert "Nút bo tròn" in html_out
    assert '/login"' in html_out

    # Nút vuông toàn hàng nền trắng có viền
    assert "border-radius:0px" in html_out
    assert 'width="100%"' in html_out
    assert "border:1px solid #cbd5e1" in html_out
    assert "Nút vuông toàn hàng nền trắng" in html_out
    assert '/users"' in html_out

    # Nút bo góc nhẹ
    assert "border-radius:6px" in html_out
    assert "Nút bo góc nhẹ" in html_out


def test_validate_design_with_page_tokens_and_case_insensitive():
    """Kiểm tra validator chấp nhận token động theo page và không phân biệt hoa thường."""
    design = {
        "blocks": [
            {
                "id": 1,
                "type": "text",
                "text": "Xin chào {{user.full_name}}, tên đăng nhập của bạn là {{USER.USERNAME}} và mật khẩu khởi tạo: {{user.temp_password}}.",
            },
            {
                "id": 2,
                "type": "button",
                "text": "Đăng nhập ngay",
                "url": "links.login",
            },
        ]
    }
    # Validate với page_code = "user"
    errors = validate_design(
        design,
        event_code="USER_CREATED",
        subject="Thông tin tài khoản {{user.username}}",
        name="Mẫu tạo người dùng",
        menu_code="user",
    )
    assert errors == []


def test_render_table_scope_target_only_and_all():
    """Kiểm tra điều kiện table_scope: 'target_only' (chỉ đích danh 1 user) vs 'all' (tất cả user)."""
    design = {
        "blocks": [
            {
                "id": 1,
                "type": "table",
                "text": "Bảng thông tin user",
                "columns": ["username", "full_name", "roles"],
                "table_scope": "target_only",
            }
        ]
    }
    context = {
        "user.username": "nguyenvana",
        "username": "nguyenvana",
        "items": [
            {"username": "nguyenvana", "full_name": "Nguyễn Văn A", "roles": "Operator"},
            {"username": "tranthib", "full_name": "Trần Thị B", "roles": "Viewer"},
            {"username": "lequangc", "full_name": "Lê Quang C", "roles": "Operator"},
        ],
    }
    html_target = render_html_email(design, context)
    assert "nguyenvana" in html_target
    assert "tranthib" not in html_target
    assert "lequangc" not in html_target

    # Đổi sang scope all
    design["blocks"][0]["table_scope"] = "all"
    html_all = render_html_email(design, context)
    assert "nguyenvana" in html_all
    assert "tranthib" in html_all
    assert "lequangc" in html_all


