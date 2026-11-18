from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.context import Ctx
from app.schemas.errors import ErrorCode
from app.services.template_export_import import send_templates_list_email


@pytest.fixture
def user_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin System", roles=["ADMIN"])


@patch("app.services.template_export_import.get_smtp_config_internal")
def test_send_templates_list_email_missing_to_emails(
    mock_get_smtp: MagicMock,
    user_ctx: Ctx,
) -> None:
    res = send_templates_list_email(
        ctx=user_ctx,
        to_emails=[],
        format_types=["XLSX"],
    )
    assert not res.ok
    assert res.code == ErrorCode.VALIDATION_ERROR
    assert "Danh sách người nhận không được để trống" in (res.message or "")


@patch("app.services.template_export_import.get_smtp_config_internal")
def test_send_templates_list_email_missing_format_types(
    mock_get_smtp: MagicMock,
    user_ctx: Ctx,
) -> None:
    res = send_templates_list_email(
        ctx=user_ctx,
        to_emails=["test@example.com"],
        format_types=[],
    )
    assert not res.ok
    assert res.code == ErrorCode.VALIDATION_ERROR
    assert "chọn ít nhất một định dạng" in (res.message or "")


@patch("app.services.template_export_import.get_smtp_config_internal")
def test_send_templates_list_email_unconfigured_smtp(
    mock_get_smtp: MagicMock,
    user_ctx: Ctx,
) -> None:
    mock_get_smtp.return_value = {"host": ""}
    res = send_templates_list_email(
        ctx=user_ctx,
        to_emails=["test@example.com"],
        format_types=["XLSX"],
    )
    assert not res.ok
    assert res.code == ErrorCode.VALIDATION_ERROR
    assert "chưa được cấu hình máy chủ SMTP" in (res.message or "")


@patch("app.services.template_export_import.get_recon_engine")
@patch("app.services.template_export_import.write_audit_log")
@patch("app.services.template_export_import.send_smtp_email")
@patch("app.services.template_export_import.build_templates_list_pdf")
@patch("app.services.template_export_import.build_templates_list_docx")
@patch("app.services.template_export_import.build_templates_list_excel")
@patch("app.services.template_export_import._get_filtered_templates")
@patch("app.services.template_export_import.get_smtp_config_internal")
def test_send_templates_list_email_success(
    mock_get_smtp: MagicMock,
    mock_get_templates: MagicMock,
    mock_build_excel: MagicMock,
    mock_build_docx: MagicMock,
    mock_build_pdf: MagicMock,
    mock_send_smtp: MagicMock,
    mock_audit: MagicMock,
    mock_engine: MagicMock,
    user_ctx: Ctx,
) -> None:
    mock_get_smtp.return_value = {
        "host": "smtp.company.com",
        "port": 587,
        "security": "STARTTLS",
        "username": "mailer@company.com",
        "password": "secret_password",
        "from_email": "reconhub@company.com",
        "from_name": "ReconHub System",
    }
    mock_get_templates.return_value = ([{"template_id": "T1", "name": "Template 1"}], "Bộ lọc: Đang dùng")
    mock_build_excel.return_value = b"excel_bytes"
    mock_build_docx.return_value = b"docx_bytes"
    mock_build_pdf.return_value = b"pdf_bytes"

    res = send_templates_list_email(
        ctx=user_ctx,
        to_emails=["recipient1@example.com", "recipient2@example.com"],
        format_types=["XLSX", "DOCX", "PDF"],
        search_term="test",
        status_filter="ACTIVE",
        custom_subject="Custom Subject",
        notes="Please check attached files.",
    )

    assert res.ok
    assert res.data is not None
    assert res.data["attachments_count"] == 3
    assert res.data["subject"] == "Custom Subject"
    assert len(res.data["to_emails"]) == 2

    # Check send_smtp_email was called with correct attachments
    mock_send_smtp.assert_called_once()
    kwargs = mock_send_smtp.call_args.kwargs
    assert kwargs["host"] == "smtp.company.com"
    assert kwargs["port"] == 587
    assert kwargs["security"] == "STARTTLS"
    assert kwargs["username"] == "mailer@company.com"
    assert kwargs["password"] == "secret_password"
    assert "reconhub@company.com" in kwargs["from_addr"]
    assert kwargs["to_addrs"] == ["recipient1@example.com", "recipient2@example.com"]
    assert kwargs["subject"] == "Custom Subject"
    assert len(kwargs["attachments"]) == 3

    # Check audit log
    mock_audit.assert_called_once()
    audit_kwargs = mock_audit.call_args.kwargs
    assert audit_kwargs["action"] == "SEND_TEMPLATE_EMAIL"
    assert audit_kwargs["entity"] == "TEMPLATE_LIST"
