from pathlib import Path
import pytest


def test_config_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Clear any environment variables that might interfere
    for key in [
        "APP_ENV",
        "RECON_DB_URL",
        "RECON_SECRET_KEY",
        "FLASK_SECRET_KEY",
        "RECON_STORAGE_DIR",
        "BACKUP_DIR",
        "DASH_PORT",
        "WORKER_POLL_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)

    from app.core.config import Settings, get_settings

    settings = Settings(_env_file=None)
    assert settings.APP_ENV in ("dev", "test", "uat", "prod")
    assert isinstance(settings.PROJECT_ROOT, Path)
    assert settings.PROJECT_ROOT.exists()

    # Check relative paths resolved to absolute paths on Windows
    assert isinstance(settings.storage_dir, Path)
    assert settings.storage_dir.is_absolute()
    assert isinstance(settings.backup_dir, Path)
    assert settings.backup_dir.is_absolute()

    # Check sqlite path resolution
    db_file = settings.get_sqlite_path()
    assert db_file is not None
    assert isinstance(db_file, Path)
    assert db_file.is_absolute()
    assert db_file.name == "recon_app.db"


def test_config_from_env_example() -> None:
    from app.core.config import Settings, get_settings

    root = Path(__file__).resolve().parent.parent
    env_example = root / ".env.example"
    assert env_example.exists(), ".env.example phải tồn tại"

    settings = Settings(_env_file=env_example)
    assert settings.DASH_PORT == 8050
    assert settings.LOGIN_MAX_FAILS == 5
    assert settings.RUN_MAX_ROWS == 1000000
    assert settings.RUN_DB_CALL_TIMEOUT_SECONDS == 600
    assert settings.TEMP_WARN_GB == 5

