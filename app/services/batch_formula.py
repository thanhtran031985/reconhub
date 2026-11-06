"""Công thức kỳ cho bộ đối soát (task 18, spec 10 mục 4.4).

Parser là regex cố định, không `eval`: chỉ chấp nhận `{ky.tu}`,
`{ky.den}`, `{ky.tu±Nd}`, `{ky.den±Nd}` (N ≤ 31), `{ky.thang}`,
`{ky.nam}`. Ngoài cú pháp trên → BATCH_FORMULA_INVALID.
"""

from __future__ import annotations

import calendar
import hashlib
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.errors import ErrorCode, ServiceError
from app.schemas.template_config import ParamSpec

_PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_FORMULA_RE = re.compile(r"\{(ky\.(?:tu|den)(?:[+-]\d{1,2}d)?|ky\.thang|ky\.nam)\}")
_WHOLE_DT_RE = re.compile(r"^\{ky\.(tu|den)([+-]\d{1,2}d)?\}$")
_DT_OFFSET_RE = re.compile(r"^ky\.(tu|den)([+-]\d{1,2}d)?$")

_DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")
_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


def _invalid(message: str) -> ServiceError:
    return ServiceError(ErrorCode.BATCH_FORMULA_INVALID, message)


def parse_period(period: str) -> tuple[datetime, datetime]:
    """Kỳ YYYY-MM → (ngày 1 00:00:00, ngày cuối 23:59:59)."""
    m = _PERIOD_RE.match(period or "")
    if not m:
        raise _invalid(f"Kỳ không hợp lệ: {period!r}. Kỳ phải dạng YYYY-MM.")
    year, month = int(m.group(1)), int(m.group(2))
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, 1, 0, 0, 0), datetime(year, month, last_day, 23, 59, 59)


def _resolve_token(token: str, period: str) -> str | datetime:
    """Giá trị của một công thức (phần trong dấu {})."""
    if token in ("ky.thang", "ky.nam"):
        year, month = period.split("-")
        return f"{year}{month}" if token == "ky.thang" else year
    m = _DT_OFFSET_RE.match(token)
    if not m:
        raise _invalid(f"Biểu thức không hợp lệ: {{{token}}}.")
    start, end = parse_period(period)
    base = start if m.group(1) == "tu" else end
    offset = m.group(2)
    if offset:
        days = int(offset[:-1])
        if abs(days) > 31:
            raise _invalid(f"Biểu thức không hợp lệ: {{{token}}}. Độ lệch tối đa 31 ngày.")
        return base + timedelta(days=days)
    return base


def _format_value(value: str | datetime) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def resolve(expr: str, period: str) -> str | datetime:
    """Tính một biểu thức: công thức kỳ hoặc chuỗi chứa công thức.

    Toàn bộ biểu thức là một công thức datetime → trả datetime; còn lại
    trả chuỗi sau khi thay công thức. Không có công thức → giữ nguyên.
    """
    if not isinstance(expr, str):
        return expr
    if _WHOLE_DT_RE.match(expr):
        return _resolve_token(expr[1:-1], period)
    result = expr
    for match in _FORMULA_RE.finditer(expr):
        result = result.replace(match.group(0), _format_value(_resolve_token(match.group(1), period)))
    if "{" in result or "}" in result:
        raise _invalid(f"Biểu thức không hợp lệ: {expr!r}.")
    return result


def _coerce_datetime(raw: Any, name: str) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, date):
        return datetime(raw.year, raw.month, raw.day, 0, 0, 0)
    if isinstance(raw, str):
        for fmt in _DT_FORMATS:
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
    raise ServiceError(ErrorCode.BATCH_PARAM_TYPE, f"Tham số {name}: giá trị {raw!r} không phải ngày giờ hợp lệ.")


def _coerce_date(raw: Any, name: str) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue
    raise ServiceError(ErrorCode.BATCH_PARAM_TYPE, f"Tham số {name}: giá trị {raw!r} không phải ngày hợp lệ.")


def _coerce_number(raw: Any, name: str) -> int | float:
    if isinstance(raw, bool):
        raise ServiceError(ErrorCode.BATCH_PARAM_TYPE, f"Tham số {name}: giá trị {raw!r} không phải số.")
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ServiceError(ErrorCode.BATCH_PARAM_TYPE, f"Tham số {name}: giá trị {raw!r} không phải số.") from None
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _coerce_text(raw: Any) -> str:
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(raw, date):
        return raw.isoformat()
    return str(raw)


def _coerce(raw: Any, spec: ParamSpec) -> Any:
    """Ép giá trị đã tính công thức theo kiểu tham số của template."""
    if spec.type == "text":
        return _coerce_text(raw)
    if spec.type == "number":
        if isinstance(raw, (datetime, date)):
            raise ServiceError(
                ErrorCode.BATCH_PARAM_TYPE, f"Tham số {spec.name}: công thức ngày giờ không dùng cho tham số số."
            )
        return _coerce_number(raw, spec.name)
    if spec.type == "date":
        return _coerce_date(raw, spec.name)
    return _coerce_datetime(raw, spec.name)


def resolve_params(
    template_params: list[ParamSpec],
    def_override: dict[str, Any] | None,
    run_override: dict[str, Any] | None,
    period: str,
) -> dict[str, Any]:
    """Tính giá trị cuối cùng của mọi tham số cho một lần chạy bộ.

    Thứ tự ưu tiên: ghi đè khi chạy > ghi đè trong bộ > mặc định template.
    Riêng p_from/p_to mặc định {ky.tu}/{ky.den}. Kiểm như run đơn lẻ:
    chỉ chặn p_from > p_to (không chặn max_range_days nữa).
    """
    parse_period(period)
    def_override = def_override or {}
    run_override = run_override or {}
    known = {p.name for p in template_params} | {"p_from", "p_to"}
    for source in (def_override, run_override):
        for key in source:
            if key not in known:
                raise ServiceError(ErrorCode.BATCH_PARAM_UNKNOWN, f"Tham số {key} không có trong template.")

    resolved: dict[str, Any] = {}
    for key, default_expr in (("p_from", "{ky.tu}"), ("p_to", "{ky.den}")):
        raw = run_override.get(key, def_override.get(key, default_expr))
        resolved[key] = _coerce_datetime(resolve(raw, period) if isinstance(raw, str) else raw, key)
    if resolved["p_from"] > resolved["p_to"]:
        raise ServiceError(
            ErrorCode.INVALID_RANGE,
            "Khoảng thời gian không hợp lệ: 'Từ ngày' phải trước hoặc bằng 'Đến ngày'.",
        )

    for spec in template_params:
        if spec.name in run_override:
            raw = run_override[spec.name]
        elif spec.name in def_override:
            raw = def_override[spec.name]
        else:
            raw = spec.default
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            if spec.required:
                raise ServiceError(ErrorCode.BATCH_PARAM_REQUIRED, f"Tham số {spec.name} ({spec.label}) là bắt buộc.")
            continue
        value = resolve(raw, period) if isinstance(raw, str) else raw
        resolved[spec.name] = _coerce(value, spec)
    return resolved


def compute_file_set_hash(file_sha256_list: list[str], sheet_name: str, template_id: int, template_version: int) -> str:
    """FILE_SET_HASH (spec 10a §6): 1 file = sha256(SHA256 của file);
    nhiều file = sha256(danh sách SHA-256 đã sắp xếp + sheet + template
    + version). Dùng cho UQ và dedup của RECON_EXCEL_LOAD."""
    if not file_sha256_list:
        raise ValueError("compute_file_set_hash cần ít nhất 1 file.")
    ordered = sorted(file_sha256_list)
    if len(ordered) == 1:
        return hashlib.sha256(ordered[0].encode()).hexdigest()
    payload = "\n".join(ordered) + "|" + sheet_name + "|" + str(template_id) + "|" + str(template_version)
    return hashlib.sha256(payload.encode()).hexdigest()
