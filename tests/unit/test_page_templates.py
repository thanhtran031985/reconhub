from __future__ import annotations

import io
from datetime import datetime

import openpyxl
import pytest

from app.engine.template_sample import build_template_sample_excel
from app.schemas.template_config import FieldSpec, TemplateConfig
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


def _sample_config() -> TemplateConfig:
    return TemplateConfig.model_validate(
        {
            "file": {"sheet": "Sheet1", "header_row": 1, "data_start_row": 2},
            "fields": [
                {"name": "INVOICE_NO", "label": "Số HĐ", "excel": "Số hóa đơn", "db": "INV_NO", "type": "text"},
                {"name": "AMOUNT", "label": "Tiền", "excel": "Thành tiền", "db": "AMT", "type": "number"},
                {"name": "INV_DATE", "label": "Ngày", "excel": "Ngày HĐ", "type": "date"},
                {"name": "CREATED_AT", "label": "Giờ", "excel": "Giờ tạo", "type": "datetime"},
                {"name": "DB_ONLY", "label": "Chỉ DB", "db": "COL_X", "type": "text"},
                {"name": "ALIAS_ONLY", "label": "Alias", "excel_aliases": ["Cột phụ"], "type": "text"},
            ],
            "db_source": {
                "kind": "table",
                "table": "T",
                "filters": [
                    {"param": "p_from", "column": "D", "op": ">="},
                    {"param": "p_to", "column": "D", "op": "<="},
                ],
                "params": [
                    {"name": "p_from", "type": "datetime", "source": "user", "label": "Từ"},
                    {"name": "p_to", "type": "datetime", "source": "user", "label": "Đến"},
                ],
            },
            "profiles": [
                {
                    "code": "P1",
                    "name": "P1",
                    "is_default": True,
                    "group_by": ["INVOICE_NO"],
                    "measures": [{"name": "M1", "label": "M1", "agg": "sum", "field": "AMOUNT"}],
                }
            ],
        }
    )


def test_template_sample_excel_header_and_five_example_rows() -> None:
    content = build_template_sample_excel(_sample_config())
    workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    sheet = workbook.active
    assert sheet is not None
    assert sheet.title == "Sheet1"
    rows = list(sheet.iter_rows(values_only=True))
    assert len(rows) == 6  # 1 header + 5 dòng ví dụ
    assert rows[0] == ("Số hóa đơn", "Thành tiền", "Ngày HĐ", "Giờ tạo", "Cột phụ")
    assert "COL_X" not in rows[0]
    assert rows[1] == ("Ví dụ 1", 1000, datetime(2026, 2, 1), datetime(2026, 2, 1, 9, 0), "Ví dụ 1")
    assert rows[5] == ("Ví dụ 5", 5000, datetime(2026, 2, 5), datetime(2026, 2, 5, 9, 0), "Ví dụ 5")


def test_template_sample_excel_without_excel_columns_raises() -> None:
    config = _sample_config().model_copy(
        update={"fields": [FieldSpec(name="DB_ONLY", label="Chỉ DB", db="COL_X", type="text")]}
    )
    with pytest.raises(ValueError, match="không có cột Excel"):
        build_template_sample_excel(config)


def test_render_templates_actions_first_and_headers_centered() -> None:
    content = render_templates_content(
        items=[
            {
                "id": 1,
                "code": "TMPL_01",
                "name": "Template 1",
                "file_pattern": "f.xlsx",
                "field_count": 3,
                "profiles": [],
                "version": 1,
                "owner": "admin",
                "status": "ACTIVE",
                "last_run": None,
            }
        ],
        loading=False,
        error=None,
    )
    table = content.children[0].children
    thead_tr = table.children[0].children
    headers = thead_tr.children
    assert [h.children for h in headers] == [
        "Thao tác",
        "Mã template",
        "Tên & Nhận diện file",
        "Số trường",
        "Profiles",
        "Phiên bản",
        "Chủ sở hữu",
        "Trạng thái",
        "Run gần nhất",
    ]
    assert all(h.style.get("textAlign") == "center" for h in headers)

    first_row = table.children[1].children[0]
    first_cell_str = str(first_row.children[0])
    assert "Sửa" in first_cell_str
    assert "Sơ đồ" in first_cell_str
    assert "Tải file mẫu Excel" in first_cell_str
    assert "TMPL_01" in str(first_row.children[1])
