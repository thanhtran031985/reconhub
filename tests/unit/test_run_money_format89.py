"""Task 89: fmt_num dung dau ',' hang nghin, '.' so le (vd 1910000 -> 1,910,000)."""

from __future__ import annotations

import pytest

from app.ui.pages.run_result import fmt_num


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1910000, "1,910,000"),
        (624500000, "624,500,000"),
        (1000, "1,000"),
        (1000.0, "1,000"),
        (1234567.89, "1,234,567.89"),
        (1234.5, "1,234.5"),
        (0, "0"),
        (0.0, "0"),
        (-1910000, "-1,910,000"),
        (None, "—"),
        ("", "—"),
        ("abc", "abc"),
        ("1910000", "1,910,000"),
    ],
)
def test_fmt_num_comma_thousands_dot_decimal(value, expected):
    assert fmt_num(value) == expected
