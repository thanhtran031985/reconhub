"""Task 18 bước 2: công thức kỳ (spec 10 mục 4.4, mục 13)."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import ParamSpec
from app.services.batch_formula import (
    compute_file_set_hash,
    parse_period,
    resolve,
    resolve_params,
)


def _params() -> list[ParamSpec]:
    return [
        ParamSpec(name="p_ky", type="text", source="user", default=None, label="Kỳ", required=True),
        ParamSpec(name="p_so", type="number", source="user", default="0", label="Số", required=False),
        ParamSpec(name="p_ngay", type="date", source="user", default=None, label="Ngày", required=False),
        ParamSpec(name="p_gio", type="datetime", source="user", default=None, label="Giờ", required=False),
    ]


class TestParsePeriod:
    def test_october_2026(self):
        start, end = parse_period("2026-10")
        assert start == datetime(2026, 10, 1, 0, 0, 0)
        assert end == datetime(2026, 10, 31, 23, 59, 59)

    def test_february_leap_year(self):
        _start, end = parse_period("2024-02")
        assert end == datetime(2024, 2, 29, 23, 59, 59)

    def test_february_non_leap(self):
        _start, end = parse_period("2023-02")
        assert end == datetime(2023, 2, 28, 23, 59, 59)

    def test_invalid_period(self):
        for bad in ("2026-13", "2026-1", "202610", "2026/10", "", "abcd-ef"):
            with pytest.raises(ServiceError) as exc:
                parse_period(bad)
            assert exc.value.code == ErrorCode.BATCH_FORMULA_INVALID


class TestResolve:
    def test_ky_tu_den(self):
        assert resolve("{ky.tu}", "2026-10") == datetime(2026, 10, 1, 0, 0, 0)
        assert resolve("{ky.den}", "2026-10") == datetime(2026, 10, 31, 23, 59, 59)

    def test_offset_days(self):
        assert resolve("{ky.tu+1d}", "2026-10") == datetime(2026, 10, 2, 0, 0, 0)
        assert resolve("{ky.tu-1d}", "2026-10") == datetime(2026, 9, 30, 0, 0, 0)
        assert resolve("{ky.den+1d}", "2026-10") == datetime(2026, 11, 1, 23, 59, 59)
        assert resolve("{ky.den-31d}", "2026-10") == datetime(2026, 9, 30, 23, 59, 59)
        assert resolve("{ky.tu+0d}", "2026-10") == datetime(2026, 10, 1, 0, 0, 0)

    def test_offset_across_year(self):
        assert resolve("{ky.tu-1d}", "2026-01") == datetime(2025, 12, 31, 0, 0, 0)
        assert resolve("{ky.den+1d}", "2025-12") == datetime(2026, 1, 1, 23, 59, 59)

    def test_thang_nam(self):
        assert resolve("{ky.thang}", "2026-10") == "202610"
        assert resolve("{ky.nam}", "2026-10") == "2026"

    def test_embedded_in_text(self):
        assert resolve("BC_{ky.thang}", "2026-10") == "BC_202610"
        assert resolve("KY{ky.nam}X", "2026-10") == "KY2026X"

    def test_plain_text_unchanged(self):
        assert resolve("abc", "2026-10") == "abc"
        assert resolve("", "2026-10") == ""

    def test_invalid_expressions(self):
        for bad in (
            "{ky}",
            "{foo}",
            "{ky.tu+32d}",
            "{ky.tu-32d}",
            "{ky.tu+1x}",
            "{ky.tu +1d}",
            "{ky.tu+1D}",
            "{ky.tu+}",
            "{ky.thang+1d}",
        ):
            with pytest.raises(ServiceError) as exc:
                resolve(bad, "2026-10")
            assert exc.value.code == ErrorCode.BATCH_FORMULA_INVALID

    def test_no_eval(self):
        # Biểu thức lạ không được thực thi mã — chỉ báo lỗi.
        with pytest.raises(ServiceError):
            resolve("{__import__('os').system('id')}", "2026-10")


class TestResolveParams:
    def test_priority_run_over_def_over_default(self):
        out = resolve_params(
            _params(),
            def_override={"p_ky": "202609", "p_so": "5"},
            run_override={"p_so": "7"},
            period="2026-10",
        )
        assert out["p_ky"] == "202609"
        assert out["p_so"] == 7

    def test_formula_in_override(self):
        out = resolve_params(_params(), def_override={"p_ky": "{ky.thang}"}, run_override={}, period="2026-10")
        assert out["p_ky"] == "202610"

    def test_defaults_p_from_p_to(self):
        out = resolve_params(_params(), def_override={"p_ky": "202610"}, run_override={}, period="2026-10")
        assert out["p_from"] == datetime(2026, 10, 1, 0, 0, 0)
        assert out["p_to"] == datetime(2026, 10, 31, 23, 59, 59)

    def test_p_from_p_to_override_with_formula(self):
        out = resolve_params(
            _params(),
            def_override={"p_ky": "202610"},
            run_override={"p_from": "{ky.tu-1d}", "p_to": "{ky.den}"},
            period="2026-10",
        )
        assert out["p_from"] == datetime(2026, 9, 30, 0, 0, 0)
        assert out["p_to"] == datetime(2026, 10, 31, 23, 59, 59)

    def test_unknown_param(self):
        with pytest.raises(ServiceError) as exc:
            resolve_params(_params(), def_override={"p_la": "x"}, run_override={}, period="2026-10")
        assert exc.value.code == ErrorCode.BATCH_PARAM_UNKNOWN

    def test_required_missing(self):
        with pytest.raises(ServiceError) as exc:
            resolve_params(_params(), def_override={}, run_override={}, period="2026-10")
        assert exc.value.code == ErrorCode.BATCH_PARAM_REQUIRED

    def test_type_errors(self):
        with pytest.raises(ServiceError) as exc:
            resolve_params(
                _params(), def_override={"p_ky": "202610", "p_so": "khong-phai-so"},
                run_override={}, period="2026-10",
            )
        assert exc.value.code == ErrorCode.BATCH_PARAM_TYPE
        with pytest.raises(ServiceError) as exc:
            resolve_params(
                _params(), def_override={"p_ky": "202610", "p_ngay": "32/13/2026"},
                run_override={}, period="2026-10",
            )
        assert exc.value.code == ErrorCode.BATCH_PARAM_TYPE

    def test_coercion(self):
        out = resolve_params(
            _params(),
            def_override={"p_ky": "202610", "p_so": "12.5", "p_ngay": "2026-10-05", "p_gio": "2026-10-05 08:30:00"},
            run_override={},
            period="2026-10",
        )
        assert out["p_so"] == pytest.approx(12.5)
        assert out["p_ngay"] == datetime(2026, 10, 5).date()
        assert out["p_gio"] == datetime(2026, 10, 5, 8, 30, 0)

    def test_p_from_after_p_to(self):
        with pytest.raises(ServiceError) as exc:
            resolve_params(
                _params(),
                def_override={"p_ky": "202610"},
                run_override={"p_from": "2026-10-31 00:00:00", "p_to": "2026-10-01 00:00:00"},
                period="2026-10",
            )
        assert exc.value.code == ErrorCode.INVALID_RANGE


class TestComputeFileSetHash:
    def test_single_file_matches_backfill_formula(self):
        import hashlib

        assert compute_file_set_hash(["a" * 64], "Sheet1", 2, 1) == hashlib.sha256(("a" * 64).encode()).hexdigest()

    def test_order_independent_and_context_sensitive(self):
        h1 = compute_file_set_hash(["b" * 64, "a" * 64], "Sheet1", 2, 1)
        h2 = compute_file_set_hash(["a" * 64, "b" * 64], "Sheet1", 2, 1)
        assert h1 == h2
        assert compute_file_set_hash(["a" * 64, "b" * 64], "Sheet2", 2, 1) != h1
        assert compute_file_set_hash(["a" * 64, "b" * 64], "Sheet1", 3, 1) != h1
