from __future__ import annotations

from logging.config import fileConfig
import sqlite3
from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.config import get_settings
from app.db.metadata import metadata
from app.db.engine import _set_sqlite_pragmas

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def get_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        url = get_settings().effective_db_url
    if url.startswith("sqlite:///"):
        from pathlib import Path
        p = Path(url[len("sqlite:///"):])
        p.parent.mkdir(parents=True, exist_ok=True)
    return url


def run_migrations_offline() -> None:
    """Chạy migration ở chế độ offline."""
    url = get_url()
    is_sqlite = url.startswith("sqlite")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Chạy migration ở chế độ online."""
    url = get_url()
    is_sqlite = url.startswith("sqlite")

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if is_sqlite:
            # Bật auto_vacuum trước khi tạo bảng nếu là SQLite mới
            raw_conn = connection.connection
            if isinstance(raw_conn, sqlite3.Connection):
                cursor = raw_conn.cursor()
                cursor.execute("PRAGMA auto_vacuum = INCREMENTAL")
                cursor.close()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
