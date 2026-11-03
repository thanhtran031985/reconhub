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


def test_render_templates_pagination_and_admin_delete() -> None:
    # Tạo 25 mock items
    mock_items = [
        {
            "id": i,
            "template_id": f"TMPL_{i:02d}",
            "code": f"TMPL_{i:02d}",
            "name": f"Template {i}",
            "file_pattern": f"file_{i}.xlsx",
            "sheet": "Sheet1",
            "field_count": 10 + i,
            "profiles": [{"code": "P1", "name": "Profile 1", "is_default": True}],
            "version": 1,
            "owner": "admin",
            "status": "ACTIVE",
            "last_run": {"id": 100 + i, "status": "DONE", "finished_at": "2026-11-02 12:00:00"},
        }
        for i in range(1, 26)
    ]

    # Render cho Admin ở trang 1
    content_admin = render_templates_content(
        items=mock_items, loading=False, error=None, page=1, page_size=10, is_admin=True
    )
    content_str_admin = str(content_admin)
    assert "TMPL_01" in content_str_admin
    assert "TMPL_10" in content_str_admin
    assert "TMPL_11" not in content_str_admin  # Trang 1 chỉ có 10 items
    assert "Xóa template" in content_str_admin  # Admin thấy nút xóa
    assert "Hiển thị 1 – 10 trong tổng số 25" in content_str_admin

    # Render cho User thường (không phải admin)
    content_user = render_templates_content(
        items=mock_items, loading=False, error=None, page=1, page_size=10, is_admin=False
    )
    content_str_user = str(content_user)
    assert "TMPL_01" in content_str_user
    assert "Xóa template" not in content_str_user  # User không thấy nút xóa

    # Render trang 2
    content_p2 = render_templates_content(
        items=mock_items, loading=False, error=None, page=2, page_size=10, is_admin=False
    )
    content_str_p2 = str(content_p2)
    assert "TMPL_11" in content_str_p2
    assert "TMPL_01" not in content_str_p2
    assert "Hiển thị 11 – 20 trong tổng số 25" in content_str_p2
