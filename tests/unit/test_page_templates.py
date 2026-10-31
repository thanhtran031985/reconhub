from __future__ import annotations

from app.ui.pages.templates import (
    layout,
    render_templates_content,
)


def test_templates_layout_renders() -> None:
    page_layout = layout()
    assert page_layout is not None


def test_render_templates_table_data_state() -> None:
    mock_items = [
        {
            "template_id": "DTP_HOA_DON",
            "name": "DTP Hóa đơn tác nghiệp",
            "file_pattern": "dtp_*.xlsx",
            "field_count": 14,
            "profiles": [
                {"profile_id": "P01", "name": "Theo số HĐ", "is_default": True},
                {"profile_id": "P02", "name": "Theo ngày + điểm bán", "is_default": False},
            ],
            "version": 1,
            "created_by": "admin",
            "status": "ACTIVE",
        }
    ]

    content = render_templates_content(items=mock_items, loading=False, error=None)
    assert content is not None
    # Kiểm tra có chứa mã template và các profile
    content_str = str(content)
    assert "DTP_HOA_DON" in content_str
    assert "DTP Hóa đơn tác nghiệp" in content_str
    assert "Hoạt động" in content_str or "ACTIVE" in content_str or "Đang dùng" in content_str


def test_render_templates_empty_state() -> None:
    content = render_templates_content(items=[], loading=False, error=None)
    content_str = str(content)
    assert "Chưa có template nào" in content_str


def test_render_templates_error_state() -> None:
    content = render_templates_content(items=None, loading=False, error="Lỗi kết nối cơ sở dữ liệu")
    content_str = str(content)
    assert "Lỗi kết nối cơ sở dữ liệu" in content_str
    assert "Thử lại" in content_str
