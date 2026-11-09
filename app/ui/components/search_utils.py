"""Tiện ích tìm kiếm không dấu dùng chung cho page Mô hình dữ liệu.

Theo mẫu ``app/ui/layout/shell.py`` (``_strip_accents``): NFKD, bỏ combining,
Đ/đ -> d, lower. Tách riêng để page không phải import từ shell (tránh kéo
layout) và để test thuần không cần browser.
"""

from __future__ import annotations

import unicodedata


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt + chữ thường để so khớp có dấu/không dấu đều ra."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("Đ", "D").replace("đ", "d").lower()


def matches_query(text: str | None, query: str) -> bool:
    """Chuỗi con sau khi chuẩn hoá; query rỗng thì khớp mọi thứ."""
    q = strip_accents((query or "").strip())
    if not q:
        return True
    return q in strip_accents(text or "")
