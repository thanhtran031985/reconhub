from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import get_settings


def setup_logging() -> None:
    """Khởi tạo cấu hình structlog ghi ra console và file logs/app.log."""
    settings = get_settings()
    log_dir = settings.PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=False if sys.platform == "win32" else True),
        ],
    )

    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO if not settings.DASH_DEBUG else logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_logger(name: str | None = None) -> Any:
    """Lấy structlog logger theo tên."""
    return structlog.get_logger(name)
