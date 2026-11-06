"""Ghép file theo mẫu tên (task 18, spec 10 mục 4.3).

Chuẩn hóa tên file: chỉ lấy tên file (bỏ đường dẫn trong zip), bỏ đuôi,
bỏ dấu tiếng Việt, chữ HOA, chỉ giữ A–Z, 0–9 và `*` (để mẫu glob dùng
được). Mẫu glob đơn giản: `*` khớp mọi chuỗi; nhiều mẫu cách nhau `|`.
"""

from __future__ import annotations

import fnmatch
import re
import unicodedata
from typing import Any

_KEEP_RE = re.compile(r"[^A-Z0-9*]")


def normalize_name(name: str) -> str:
    """Chuẩn hóa tên file/mẫu theo spec 10 mục 4.3."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    decomposed = unicodedata.normalize("NFKD", stem)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_only = ascii_only.replace("Đ", "D").replace("đ", "d")
    return _KEEP_RE.sub("", ascii_only.upper())


def match(file_name: str, items: list[dict[str, Any]]) -> list[int]:
    """Trả về id các mục mà tên file khớp mẫu (0 = không khớp,
    1 = ghép tự động, >1 = mơ hồ). Mỗi mục: {"item_id", "pattern"}."""
    name = normalize_name(file_name)
    matched: list[int] = []
    for item in items:
        patterns = str(item.get("pattern") or "").split("|")
        for raw in patterns:
            pattern = normalize_name(raw.strip())
            if not pattern:
                continue
            if fnmatch.fnmatchcase(name, pattern):
                matched.append(int(item["item_id"]))
                break
    return matched
