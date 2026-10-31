from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import dash_mantine_components as dmc
from dash_iconify import DashIconify

from app.ui.components.field import form_field
from app.ui.components.status_chip import status_chip
from app.ui.formatters import format_bytes, format_currency, format_datetime, format_number


def test_status_chip_has_icon_and_label() -> None:
    # 1. 7 trạng thái kết quả
    for status in [
        "MATCHED",
        "MISMATCH",
        "MISSING_IN_DB",
        "MISSING_IN_EXCEL",
        "INCONSISTENT",
        "DUPLICATE",
        "INVALID",
    ]:
        chip = status_chip(status)
        assert isinstance(chip, dmc.Badge)
        assert chip.leftSection is not None
        assert isinstance(chip.leftSection, DashIconify)
        assert len(chip.children) > 0

    # 2. Trạng thái người dùng
    for user_st in ["ACTIVE", "LOCKED", "DISABLED", "MUST_CHANGE_PW"]:
        chip = status_chip(user_st)
        assert chip.leftSection is not None
        assert isinstance(chip.leftSection, DashIconify)
        assert len(chip.children) > 0

    # 3. Trạng thái template
    for tmpl_st in ["ACTIVE", "DRAFT", "ARCHIVED"]:
        chip = status_chip(tmpl_st)
        assert chip.leftSection is not None
        assert len(chip.children) > 0

    # 4. Nhãn môi trường
    for env in ["DEV", "UAT", "PROD"]:
        chip = status_chip(env)
        assert chip.leftSection is not None
        assert len(chip.children) > 0


def test_form_field_error_has_aria_describedby() -> None:
    # Trường không có lỗi
    input_elem = dmc.TextInput(id="test-username")
    field = form_field(input_elem, label="Tên đăng nhập", field_id="test-username")
    assert field is not None

    # Trường có lỗi: phải gán aria-describedby cho input và render thông báo lỗi có id tương ứng
    input_elem_err = dmc.TextInput(id="test-email")
    field_err = form_field(
        input_elem_err,
        label="Email",
        field_id="test-email",
        error="Email không đúng định dạng",
    )
    assert field_err is not None
    # Input element phải nhận aria-describedby trỏ tới test-email-error
    assert input_elem_err.aria_describedby == "test-email-error" or getattr(input_elem_err, "aria-describedby", None) == "test-email-error"


def test_formatters() -> None:
    # Currency
    assert format_currency(Decimal("24114547250")) == "24.114.547.250"
    assert format_currency(1234567) == "1.234.567"
    assert format_currency(None) == "—"

    # Number
    assert format_number(1234567) == "1.234.567"
    assert format_number(0) == "0"
    assert format_number(None) == "—"

    # Datetime
    dt = datetime(2026, 2, 5, 14, 30, 45)
    assert format_datetime(dt) == "05/02/2026 14:30:45"
    assert format_datetime("2026-02-05T14:30:45") == "05/02/2026 14:30:45"
    assert format_datetime(None) == "—"

    # Bytes
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1,0 KB"
    assert format_bytes(3355443) == "3,2 MB"
    assert format_bytes(1073741824) == "1,0 GB"
    assert format_bytes(None) == "—"

