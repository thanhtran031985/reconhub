from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Cấu hình ứng dụng ReconHub đọc từ biến môi trường hoặc .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["dev", "test", "uat", "prod"] = "dev"

    # Database RECON_APP
    RECON_DB_URL: str = "sqlite:///data/recon_app.db"

    # Bí mật
    RECON_SECRET_KEY: str = "change_me"
    FLASK_SECRET_KEY: str = "change_me"

    # Đăng nhập & phiên
    SESSION_HOURS: int = 8
    LOGIN_MAX_FAILS: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    # Thư mục lưu trữ
    RECON_STORAGE_DIR: str = "./storage"
    BACKUP_DIR: str = "./backup"

    # Ngưỡng cảnh báo dữ liệu tạm
    TEMP_WARN_GB: int = 5
    TEMP_WARN_DAYS: int = 30
    RESULT_RETENTION_DAYS: int = 0

    # Dash & Worker
    DASH_PORT: int = 8050
    DASH_DEBUG: bool = True
    WORKER_POLL_SECONDS: int = 2
    WORKER_STUCK_MINUTES: int = 15
    RUN_MAX_ROWS: int = 1000000
    RUN_DB_CALL_TIMEOUT_SECONDS: int = 600

    # Oracle test (VPN)
    ORACLE_TEST_DSN: str = ""
    ORACLE_TEST_SRC_USER: str = ""
    ORACLE_TEST_SRC_PASSWORD: str = ""
    ORACLE_TEST_SRC_SCHEMA: str = ""
    ORACLE_TEST_APP_USER: str = ""
    ORACLE_TEST_APP_PASSWORD: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def PROJECT_ROOT(self) -> Path:
        return PROJECT_ROOT

    @property
    def storage_dir(self) -> Path:
        p = Path(self.RECON_STORAGE_DIR)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    @property
    def backup_dir(self) -> Path:
        p = Path(self.BACKUP_DIR)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    def get_sqlite_path(self) -> Path | None:
        prefix = "sqlite:///"
        if not self.RECON_DB_URL.startswith(prefix):
            return None
        rel_or_abs = self.RECON_DB_URL[len(prefix):]
        p = Path(rel_or_abs)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    @property
    def effective_db_url(self) -> str:
        """Trả về URL kết nối DB với đường dẫn SQLite đã chuẩn hóa tuyệt đối."""
        sqlite_path = self.get_sqlite_path()
        if sqlite_path is not None:
            # Dùng dạng chuẩn sqlite:////path hoặc sqlite:///path
            return f"sqlite:///{sqlite_path.as_posix()}"
        return self.RECON_DB_URL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton trả về cấu hình ứng dụng."""
    return Settings()

