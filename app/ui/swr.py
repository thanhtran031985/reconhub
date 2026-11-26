"""Tiện ích Client-side Stale-While-Revalidate (SWR) dùng chung cho các màn danh sách."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_fingerprint(payload: Any) -> str:
    """Sinh mã vân tay SHA-256 ổn định từ cấu trúc dữ liệu danh sách."""
    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]


def should_skip_swr_update(
    cached_data: Any,
    user_id: int | None,
    new_fingerprint: str,
) -> bool:
    """Trả True nếu dữ liệu trong sessionStorage khớp user và vân tay hiện tại."""
    if user_id is None or not new_fingerprint:
        return False
    if not isinstance(cached_data, dict):
        return False
    if cached_data.get("error"):
        return False
    if cached_data.get("user_id") != user_id:
        return False
    return cached_data.get("fingerprint") == new_fingerprint


def is_stale_user_store(store_data: Any, user_id: int | None) -> bool:
    """Trả True khi dữ liệu lưu trên sessionStorage thuộc người dùng khác."""
    if user_id is None or not isinstance(store_data, dict):
        return False
    cached_uid = store_data.get("user_id")
    return cached_uid is not None and cached_uid != user_id
