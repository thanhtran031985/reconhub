from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine

from app.core.context import Ctx
from app.db.metadata import metadata
from app.schemas.errors import ErrorCode
from app.services.smtp_settings import (
    get_smtp_config_internal,
    get_smtp_settings,
    set_smtp_settings,
)
from app.services.smtp_settings import (
    test_smtp_connection as exec_test_smtp_connection,
)
from tests.conftest import seed_perm_basics


@pytest.fixture(autouse=True)
def isolated_smtp_db(tmp_path, monkeypatch):
    """Cách ly database cho bài test SMTP để không ghi đè dữ liệu thật trong data/recon_app.db."""
    db_file = tmp_path / "smtp_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    engine = create_engine(db_url)
    metadata.create_all(engine)
    seed_perm_basics(engine, assignments={1: ["ADMIN"], 2: ["VIEWER"]})
    monkeypatch.setattr("app.services.smtp_settings.get_recon_engine", lambda: engine)
    monkeypatch.setattr("app.services.perm.get_recon_engine", lambda: engine)
    yield engine


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin", full_name="Admin", roles=["ADMIN"])


@pytest.fixture
def viewer_ctx() -> Ctx:
    return Ctx(user_id=2, username="viewer", full_name="Viewer", roles=["VIEWER"])


def test_get_smtp_settings_requires_admin(viewer_ctx: Ctx) -> None:
    res = get_smtp_settings(viewer_ctx)
    assert not res.ok
    assert res.code == ErrorCode.FORBIDDEN


def test_set_and_get_smtp_settings(admin_ctx: Ctx) -> None:
    save_res = set_smtp_settings(
        ctx=admin_ctx,
        host="smtp.company.com",
        port=587,
        security="STARTTLS",
        username="smtp_user",
        password="MySecretPassword123",
        from_email="reconhub@company.com",
        from_name="ReconHub Alert",
    )
    assert save_res.ok

    get_res = get_smtp_settings(admin_ctx)
    assert get_res.ok
    data = get_res.data
    assert data["host"] == "smtp.company.com"
    assert data["port"] == 587
    assert data["security"] == "STARTTLS"
    assert data["username"] == "smtp_user"
    assert data["from_email"] == "reconhub@company.com"
    assert data["from_name"] == "ReconHub Alert"
    assert data["has_password"] is True
    # Mật khẩu không bao giờ lộ ra ngoài API / UI
    assert "password" not in data

    # Kiểm tra hàm nội bộ giải mã đúng mật khẩu
    internal_cfg = get_smtp_config_internal()
    assert internal_cfg["host"] == "smtp.company.com"
    assert internal_cfg["password"] == "MySecretPassword123"


def test_test_smtp_connection_calls_mailer(admin_ctx: Ctx) -> None:
    set_smtp_settings(
        ctx=admin_ctx,
        host="smtp.company.com",
        port=587,
        security="STARTTLS",
        username="smtp_user",
        password="MySecretPassword123",
        from_email="reconhub@company.com",
        from_name="ReconHub Alert",
    )
    with patch("app.services.smtp_settings.send_smtp_email") as mock_send:
        mock_send.return_value = {"ok": True, "message": "Gửi thành công"}

        res = exec_test_smtp_connection(admin_ctx, to_email="recipient@test.com")
        assert res.ok
        assert res.data["sent"] is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["to_addrs"] == ["recipient@test.com"]
        assert "ReconHub" in call_kwargs["subject"]
