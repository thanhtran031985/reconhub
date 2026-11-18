from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
import pytest

from app.engine.template_sample import build_template_preview_excel
from app.schemas.errors import ServiceError
from app.schemas.template_config import FileSpec
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


def _write_uploaded_sample_file(path: Path) -> Path:
    """File mẫu đã tải lên: header + 7 dòng thật, gồm mã có số 0 ở đầu."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Sheet1"
    sheet.append(["Số hóa đơn", "Thành tiền", "Ngày HĐ"])
    for i in range(1, 8):
        sheet.append([f"0012{i}", str(1000 * i), f"2026-02-0{i}"])
    workbook.save(path)
    return path


def test_template_preview_excel_uses_uploaded_data_not_examples(tmp_path: Path) -> None:
    source = _write_uploaded_sample_file(tmp_path / "uploaded.xlsx")
    content = build_template_preview_excel(source, FileSpec(sheet="Sheet1", header_row=1, data_start_row=2))
    workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    sheet = workbook.active
    assert sheet is not None
    assert sheet.title == "Sheet1"
    rows = list(sheet.iter_rows(values_only=True))
    assert len(rows) == 6  # 1 header + đúng 5 dòng đầu của file đã tải lên
    assert rows[0] == ("Số hóa đơn", "Thành tiền", "Ngày HĐ")
    assert rows[1] == ("00121", "1000", "2026-02-01")
    assert rows[5] == ("00125", "5000", "2026-02-05")
    assert "Ví dụ 1" not in str(rows)
    assert "00126" not in str(rows)  # Dòng thứ 6 của file gốc không nằm trong file tải về


def test_template_preview_excel_respects_header_and_data_rows(tmp_path: Path) -> None:
    source = tmp_path / "titled.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Sheet1"
    sheet.append(["Tiêu đề file"])
    sheet.append(["Mã", "Tiền"])
    sheet.append(["A1", "10"])
    sheet.append(["A2", "20"])
    workbook.save(source)
    content = build_template_preview_excel(source, FileSpec(sheet="Sheet1", header_row=2, data_start_row=3))
    rows = list(openpyxl.load_workbook(io.BytesIO(content), data_only=True).active.iter_rows(values_only=True))
    assert rows == [("Mã", "Tiền"), ("A1", "10"), ("A2", "20")]


def test_template_preview_excel_missing_sheet_raises(tmp_path: Path) -> None:
    source = _write_uploaded_sample_file(tmp_path / "uploaded.xlsx")
    with pytest.raises(ServiceError):
        build_template_preview_excel(source, FileSpec(sheet="Không có", header_row=1, data_start_row=2))


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


def test_templates_table_no_horizontal_scroll() -> None:
    """Kiểm tra bảng template không dùng TableScrollContainer ép minWidth và không cuộn ngang."""
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
    # content.children[0] là dmc.Box bọc bảng
    box_wrapper = content.children[0]
    assert box_wrapper.style.get("overflowX") == "hidden"
    assert box_wrapper.style.get("overflowY") == "auto"

    table = box_wrapper.children
    assert table.style.get("width") == "100%"
    assert table.style.get("tableLayout") == "fixed"


def test_templates_export_menu_in_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra menu xuất danh sách (Excel, Word, PDF) xuất hiện trên header trang."""
    monkeypatch.setattr("app.ui.pages.templates.page_gate", lambda ctx, menu: None)
    page_layout = layout()
    layout_str = str(page_layout)
    assert "tmpl-export-menu-btn" in layout_str
    assert "Xuất danh sách" in layout_str
    assert "tmpl-export-excel-btn" in layout_str
    assert "Xuất Excel (.xlsx)" in layout_str
    assert "tmpl-export-word-btn" in layout_str
    assert "Xuất Word (.docx)" in layout_str
    assert "tmpl-export-pdf-btn" in layout_str
    assert "Xuất PDF (.pdf)" in layout_str
    assert "tmpl-list-download" in layout_str


def test_build_templates_list_excel() -> None:
    from app.engine.template_export import build_templates_list_excel

    mock_items = [
        {
            "code": "DTP_HOA_DON",
            "name": "DTP Hóa đơn tác nghiệp",
            "file_pattern": "dtp_*.xlsx",
            "sheet": "Sheet1",
            "field_count": 14,
            "profiles": [{"name": "Theo số HĐ", "is_default": True}],
            "current_version": 1,
            "owner": "admin",
            "status": "ACTIVE",
            "last_run": {"id": 12, "status": "DONE", "finished_at": "18/11/2026 08:00"},
            "created_at": "2026-11-01 10:00:00",
            "updated_at": "2026-11-02 12:00:00",
        }
    ]
    excel_bytes = build_templates_list_excel(mock_items, exported_by="test_user")
    assert len(excel_bytes) > 0

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
    ws = wb.active
    assert ws is not None
    assert "DANH SÁCH TEMPLATE" in str(ws.cell(row=1, column=1).value)
    # Tìm mã template trong bảng
    found_code = False
    for r in range(4, 10):
        if ws.cell(row=r, column=2).value == "DTP_HOA_DON":
            found_code = True
            break
    assert found_code, "Mã template DTP_HOA_DON phải có trong file Excel xuất ra"


def test_build_templates_list_docx() -> None:
    import zipfile

    from app.engine.template_export import build_templates_list_docx

    mock_items = [
        {
            "code": "DTP_HOA_DON",
            "name": "DTP Hóa đơn tác nghiệp",
            "file_pattern": "dtp_*.xlsx",
            "field_count": 14,
            "profiles": [{"name": "Theo số HĐ", "is_default": True}],
            "current_version": 1,
            "owner": "admin",
            "status": "ACTIVE",
            "last_run": {"id": 12, "status": "DONE", "finished_at": "18/11/2026 08:00"},
        }
    ]
    docx_bytes = build_templates_list_docx(mock_items, exported_by="test_user")
    assert len(docx_bytes) > 0

    # Kiểm tra là file zip OpenXML hợp lệ
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as z:
        assert "word/document.xml" in z.namelist()
        doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "DTP_HOA_DON" in doc_xml
        assert "DANH SÁCH TEMPLATE ĐỐI SOÁT" in doc_xml


def test_build_templates_list_pdf() -> None:
    from app.engine.template_export import build_templates_list_pdf

    mock_items = [
        {
            "code": "DTP_HOA_DON",
            "name": "DTP Hóa đơn tác nghiệp",
            "file_pattern": "dtp_*.xlsx",
            "field_count": 14,
            "profiles": [{"name": "Theo số HĐ", "is_default": True}],
            "current_version": 1,
            "owner": "admin",
            "status": "ACTIVE",
            "last_run": {"id": 12, "status": "DONE", "finished_at": "18/11/2026 08:00"},
        }
    ]
    pdf_bytes = build_templates_list_pdf(mock_items, exported_by="test_user")
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-"), "File PDF phải bắt đầu bằng header %PDF-"


def test_templates_email_elements_in_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.ui.pages.templates.page_gate", lambda ctx, menu: None)
    page_layout = layout()
    layout_str = str(page_layout)
    assert "tmpl-export-email-btn" in layout_str
    assert "tmpl-email-modal" in layout_str
    assert "tmpl-email-formats" in layout_str
    assert "tmpl-email-recipients" in layout_str
    assert "tmpl-email-subject" in layout_str
    assert "tmpl-email-submit-btn" in layout_str


@patch("app.ui.pages.templates.get_current_ctx")
@patch("app.ui.pages.templates.send_templates_list_email")
def test_handle_email_modal_actions(
    mock_send_email: MagicMock,
    mock_ctx: MagicMock,
) -> None:
    from app.core.context import Ctx
    from app.schemas.errors import ServiceResult
    from app.ui.pages.templates import handle_email_modal_actions

    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])
    mock_ctx.return_value = admin_ctx

    # 1. Open modal
    with patch("dash.callback_context") as mock_dash_ctx:
        mock_dash_ctx.triggered = [{"prop_id": "tmpl-export-email-btn.n_clicks"}]
        opened, subject, recipients, alert, toast, progress_style, disabled = handle_email_modal_actions(
            1, None, None, False, None, None, None, None, None, None
        )
        assert opened is True
        assert "[ReconHub] Danh sách Template đối soát" in subject
        assert alert is None
        assert progress_style == {"display": "none"}
        assert disabled is False

        # 2. Cancel modal
        mock_dash_ctx.triggered = [{"prop_id": "tmpl-email-cancel-btn.n_clicks"}]
        opened_c, _, _, _, _, _, _ = handle_email_modal_actions(
            None, 1, None, True, None, None, None, None, None, None
        )
        assert opened_c is False

        # 3. Submit validation (missing recipients)
        mock_dash_ctx.triggered = [{"prop_id": "tmpl-email-submit-btn.n_clicks"}]
        opened_err, _, _, alert_err, _, progress_err, dis_err = handle_email_modal_actions(
            None, None, 1, True, "", ["XLSX"], "Subject", "", "", ""
        )
        assert opened_err is True
        assert "Vui lòng nhập ít nhất một địa chỉ email" in str(alert_err)
        assert progress_err == {"display": "none"}
        assert dis_err is False

        # 4. Submit success
        mock_send_email.return_value = ServiceResult(
            ok=True,
            data={"to_emails": ["test@company.com"], "attachments_count": 1, "subject": "Subject"},
        )
        opened_ok, _, _, alert_ok, toast_ok, progress_ok, dis_ok = handle_email_modal_actions(
            None, None, 1, True, "test@company.com", ["XLSX"], "Subject", "Note", "search", "ACTIVE"
        )
        assert opened_ok is False
        assert alert_ok is None
        assert progress_ok == {"display": "none"}
        assert dis_ok is False
        assert "Đã gửi email danh sách template thành công" in str(toast_ok)
