from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def format_currency(val: Any) -> str:
    """Định dạng tiền tệ theo chuẩn Việt Nam (phân cách hàng ngàn bằng chấm, thập phân bằng phẩy).

    VD: Decimal('24114547250') -> '24.114.547.250'
    None -> '—'
    """
    if val is None or val == "":
        return "—"
    try:
        dec = Decimal(str(val))
        # Nếu là số nguyên hoặc phần thập phân bằng 0
        if dec == dec.to_integral():
            int_val = int(dec)
            return f"{int_val:,}".replace(",", ".")
        else:
            # Làm tròn 2 hoặc 4 chữ số thập phân
            parts = f"{dec:.2f}".split(".")
            int_part = f"{int(parts[0]):,}".replace(",", ".")
            return f"{int_part},{parts[1]}"
    except Exception:
        return str(val)


def format_number(val: Any) -> str:
    """Định dạng số nguyên / số lượng có phân cách hàng ngàn."""
    if val is None or val == "":
        return "—"
    try:
        dec = Decimal(str(val))
        if dec == dec.to_integral():
            return f"{int(dec):,}".replace(",", ".")
        return str(val).replace(".", ",")
    except Exception:
        return str(val)


def format_datetime(val: Any) -> str:
    """Định dạng ngày giờ Việt Nam dd/MM/yyyy HH:mm:ss."""
    if val is None or val == "":
        return "—"
    if isinstance(val, str):
        # Hỗ trợ ISO string hoặc đã có định dạng
        try:
            val = datetime.fromisoformat(val)
        except Exception:
            return str(val)
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y %H:%M:%S")
    if isinstance(val, date):
        return val.strftime("%d/%m/%Y")
    return str(val)


def format_bytes(bytes_cnt: Any) -> str:
    """Định dạng dung lượng byte ra B, KB, MB, GB với dấu phẩy thập phân kiểu Việt Nam.

    VD: 3355443 -> '3,2 MB'
    """
    if bytes_cnt is None or bytes_cnt == "":
        return "—"
    try:
        b = float(bytes_cnt)
        if b < 1024:
            return f"{int(b)} B"
        elif b < 1024 * 1024:
            val_kb = b / 1024
            return f"{val_kb:.1f}".replace(".", ",") + " KB"
        elif b < 1024 * 1024 * 1024:
            val_mb = b / (1024 * 1024)
            return f"{val_mb:.1f}".replace(".", ",") + " MB"
        else:
            val_gb = b / (1024 * 1024 * 1024)
            return f"{val_gb:.1f}".replace(".", ",") + " GB"
    except Exception:
        return str(bytes_cnt)
