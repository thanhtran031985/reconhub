"""Server Layout Cache cho các page Dash thuần khung / Skeleton-first (task 104 bước 2)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from weakref import WeakKeyDictionary

from sqlalchemy import Engine

from app.services.perm import get_perm_revision, register_cache_clear_hook

_LAYOUT_CACHE: WeakKeyDictionary[Engine, dict[tuple[Any, ...], tuple[float, Any]]] = WeakKeyDictionary()
_LAYOUT_TTL_S = 30.0


def clear_layout_cache() -> None:
    """Xóa toàn bộ Server Layout Cache."""
    _LAYOUT_CACHE.clear()


register_cache_clear_hook(clear_layout_cache)


def cached_layout(
    engine: Engine,
    key: tuple[Any, ...],
    builder: Callable[[], Any],
    ttl_s: float = _LAYOUT_TTL_S,
) -> Any:
    """Trả về cây component layout đã cache theo (engine, PERM_REVISION, key)."""
    rev = get_perm_revision(engine)
    cache_key = (rev, *key)
    now = time.monotonic()

    by_key = _LAYOUT_CACHE.get(engine)
    if by_key is not None:
        entry = by_key.get(cache_key)
        if entry is not None and (now - entry[0]) < ttl_s:
            return entry[1]

    built = builder()
    if by_key is None:
        by_key = {}
        _LAYOUT_CACHE[engine] = by_key
    by_key[cache_key] = (now, built)
    return built
