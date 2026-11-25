from __future__ import annotations

from unittest.mock import patch

import dash

from app.schemas.errors import ServiceResult
from app.ui.pages.forgot_password import handle_forgot_password, layout


def test_forgot_password_layout():
    comp = layout()
    assert comp is not None
    comp_str = str(comp)
    assert "forgot-username-input" in comp_str
    assert "forgot-email-input" in comp_str
    assert "forgot-progress-wrap" in comp_str
    assert "forgot-submit-btn" in comp_str


def test_handle_forgot_password_empty():
    alert, u_val, e_val = handle_forgot_password(1, "active_user", "   ")
    assert alert is not None
    assert "đầy đủ" in str(alert)
    assert u_val is dash.no_update
    assert e_val is dash.no_update

    alert2, u_val2, e_val2 = handle_forgot_password(1, "  ", "user@company.local")
    assert alert2 is not None
    assert "đầy đủ" in str(alert2)
    assert u_val2 is dash.no_update
    assert e_val2 is dash.no_update


def test_handle_forgot_password_success():
    with patch(
        "app.ui.pages.forgot_password.request_password_reset",
        return_value=ServiceResult.success({"sent": True, "message": "Email đã được gửi nếu thông tin đúng"}),
    ) as mock_req:
        alert, u_val, e_val = handle_forgot_password(1, "active_user", "user@company.local")
        assert mock_req.called
        assert mock_req.call_args.kwargs["username"] == "active_user"
        assert mock_req.call_args.kwargs["email"] == "user@company.local"
        assert alert is not None
        assert "Email đã được gửi" in str(alert)
        assert u_val == ""
        assert e_val == ""
