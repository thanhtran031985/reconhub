from __future__ import annotations

from unittest.mock import patch

from app.schemas.errors import ErrorCode, ServiceResult
from app.ui.pages.reset_password import handle_reset_submit, layout


def test_reset_password_layout_missing_token():
    comp = layout(token=None)
    assert comp is not None
    comp_str = str(comp)
    assert "Liên kết đặt lại mật khẩu không hợp lệ" in comp_str


def test_reset_password_layout_invalid_token():
    with patch(
        "app.ui.pages.reset_password.validate_reset_token",
        return_value=ServiceResult.fail(ErrorCode.VALIDATION_ERROR, "Liên kết đã hết hạn"),
    ):
        comp = layout(token="some_invalid_token")
        assert comp is not None
        assert "Liên kết đã hết hạn" in str(comp)


def test_reset_password_layout_valid_token():
    with patch(
        "app.ui.pages.reset_password.validate_reset_token",
        return_value=ServiceResult.success({"username": "user1", "full_name": "User One"}),
    ):
        comp = layout(token="valid_token_abc")
        assert comp is not None
        comp_str = str(comp)
        assert "reset-pw-new" in comp_str
        assert "reset-pw-confirm" in comp_str
        assert "reset-submit-btn" in comp_str


def test_handle_reset_submit_mismatch():
    alert, loc = handle_reset_submit(1, "pass123456", "pass khác", "token_123")
    assert "không khớp" in str(alert)
    assert loc is None


def test_handle_reset_submit_short():
    alert, loc = handle_reset_submit(1, "123", "123", "token_123")
    assert "tối thiểu 6 ký tự" in str(alert)
    assert loc is None


def test_handle_reset_submit_success():
    with patch(
        "app.ui.pages.reset_password.perform_password_reset",
        return_value=ServiceResult.success({"username": "user1"}),
    ) as mock_reset:
        alert, loc = handle_reset_submit(1, "ValidPass2026!", "ValidPass2026!", "token_123")
        assert mock_reset.called
        assert loc == "/login?msg=reset_success"
