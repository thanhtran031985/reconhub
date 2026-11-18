from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.context import Ctx, Role
from app.schemas.errors import ServiceResult
from app.ui.pages.settings import (
    handle_settings_save,
    handle_settings_smtp_test,
    layout,
)


@patch("app.ui.pages.settings.page_gate", return_value=None)
@patch("app.ui.pages.settings.get_current_ctx")
def test_settings_layout_renders(mock_ctx: MagicMock, mock_gate: MagicMock) -> None:
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", role=Role.ADMIN)
    mock_ctx.return_value = admin_ctx
    page_layout = layout()
    assert page_layout is not None
    layout_str = str(page_layout)
    assert "settings-smtp-host" in layout_str
    assert "settings-smtp-port" in layout_str
    assert "settings-smtp-security" in layout_str
    assert "settings-smtp-test-btn" in layout_str


@patch("app.ui.pages.settings.get_current_ctx")
@patch("app.ui.pages.settings.set_export_retention")
@patch("app.ui.pages.settings.set_export_concurrency")
@patch("app.ui.pages.settings.set_report_timeouts")
@patch("app.ui.pages.settings.set_telegram_settings")
@patch("app.ui.pages.settings.set_smtp_settings")
def test_handle_settings_save(
    mock_set_smtp: MagicMock,
    mock_set_tg: MagicMock,
    mock_set_timeouts: MagicMock,
    mock_set_concurrency: MagicMock,
    mock_set_retention: MagicMock,
    mock_ctx: MagicMock,
) -> None:
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", role=Role.ADMIN)
    mock_ctx.return_value = admin_ctx
    mock_set_retention.return_value = ServiceResult(ok=True, data={"mode": "manual", "days": 30})
    mock_set_concurrency.return_value = ServiceResult(ok=True, data={"max_concurrent": 10})
    mock_set_timeouts.return_value = ServiceResult(ok=True, data={"count_timeout_sec": 300, "data_timeout_sec": 300})
    mock_set_tg.return_value = ServiceResult(ok=True, data={"configured": False})
    mock_set_smtp.return_value = ServiceResult(ok=True, data={"configured": True})

    res = handle_settings_save(
        n_clicks=1,
        mode="manual",
        days=30,
        max_concurrent=10,
        count_timeout=300,
        data_timeout=300,
        telegram_token=None,
        telegram_username=None,
        smtp_host="smtp.company.com",
        smtp_port=587,
        smtp_security="STARTTLS",
        smtp_username="user@company.com",
        smtp_password="password123",
        smtp_from_email="noreply@company.com",
        smtp_from_name="ReconHub",
    )

    assert res is not None
    assert mock_set_smtp.called
    mock_set_smtp.assert_called_once_with(
        ctx=admin_ctx,
        host="smtp.company.com",
        port=587,
        security="STARTTLS",
        username="user@company.com",
        password="password123",
        from_email="noreply@company.com",
        from_name="ReconHub",
    )


@patch("app.ui.pages.settings.get_current_ctx")
@patch("app.ui.pages.settings.test_smtp_connection")
def test_handle_settings_smtp_test(
    mock_test_smtp: MagicMock,
    mock_ctx: MagicMock,
) -> None:
    admin_ctx = Ctx(user_id=1, username="admin", full_name="Admin", role=Role.ADMIN)
    mock_ctx.return_value = admin_ctx

    # Empty email
    err = handle_settings_smtp_test(1, "")
    assert "Vui lòng nhập địa chỉ email" in str(err)

    # Success
    mock_test_smtp.return_value = ServiceResult(ok=True, message="Đã gửi email thử nghiệm thành công.")
    res = handle_settings_smtp_test(1, "test@company.com")
    assert "Đã gửi email thử nghiệm thành công" in str(res)
    mock_test_smtp.assert_called_once_with(admin_ctx, "test@company.com")
