from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx, Role
from app.core.session import invalidate_user_session_cache
from app.db.metadata import metadata, recon_user, recon_user_role
from app.services.file_service import upload_file
from app.ui.app import create_app


@pytest.fixture
def test_setup(tmp_path, monkeypatch):
    invalidate_user_session_cache()
    db_file = tmp_path / "test_file_routes.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-key-1234567890")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="operator_user",
                FULL_NAME="Operator User",
                PASSWORD_HASH=hash_password("pw123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        user_id = res.inserted_primary_key[0]
        conn.execute(
            recon_user_role.insert().values(
                USER_ID=user_id,
                ROLE="OPERATOR",
                CREATED_AT=now,
            )
        )

    app = create_app()
    app.server.config["TESTING"] = True
    with app.server.test_client() as c:
        yield c, user_id


def test_download_file_unauthenticated(test_setup) -> None:
    client, _ = test_setup
    res = client.get("/download/file/999")
    # Chưa đăng nhập bị redirect về /login (302)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_download_file_authenticated(test_setup) -> None:
    client, user_id = test_setup
    op_ctx = Ctx(
        user_id=user_id,
        username="operator_user",
        full_name="Operator User",
        roles=[Role.OPERATOR],
    )
    sample_path = Path("samples/dtp_sample_200.xlsx")
    up_res = upload_file(op_ctx, filename="dtp_sample_200.xlsx", content=sample_path.read_bytes())
    assert up_res.ok is True
    file_id = up_res.data["id"]

    # Đăng nhập vào session
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = "operator_user"
        sess["roles"] = ["OPERATOR"]
        sess["session_version"] = 1
        sess["must_change_pw"] = "N"

    res = client.get(f"/download/file/{file_id}")
    assert res.status_code == 200
    assert len(res.data) == len(sample_path.read_bytes())
    assert "dtp_sample_200.xlsx" in res.headers["Content-Disposition"]



def test_download_export_unauthenticated(test_setup) -> None:
    client, _ = test_setup
    res = client.get("/download/export/999")
    # Chưa đăng nhập bị redirect về /login (302)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
