from __future__ import annotations

import sqlite3
from typing import Any

from sqlalchemy import Engine, create_engine, event

from app.core.config import get_settings


def _set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
    """Thiết lập PRAGMA cho kết nối SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def get_sqlite_engine(db_url: str) -> Engine:
    """Tạo SQLAlchemy engine cho SQLite với cấu hình PRAGMA tối ưu."""
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


def get_oracle_engine(db_url: str) -> Engine:
    """Tạo SQLAlchemy engine cho Oracle sử dụng python-oracledb ở chế độ Thin."""
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def get_db_engine(db_url: str | None = None) -> Engine:
    """Trả về SQLAlchemy engine phù hợp với chuỗi kết nối (mặc định từ settings)."""
    if db_url is None:
        settings = get_settings()
        db_url = settings.effective_db_url

    if db_url.startswith("sqlite"):
        return get_sqlite_engine(db_url)
    elif "oracle" in db_url:
        return get_oracle_engine(db_url)
    else:
        return create_engine(db_url, pool_pre_ping=True)
