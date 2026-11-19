from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.context import Ctx, Role
from app.db.metadata import metadata, recon_user
from app.engine.mail_token_inspector import (
    get_available_pages,
    get_flat_tokens_for_page,
    get_mock_payload_for_page,
    introspect_tokens_for_page,
)
from app.engine.user_export import (
    build_users_list_docx,
    build_users_list_excel,
    build_users_list_pdf,
)
from app.schemas.user import UserCreateDTO
from app.services.user import create_user
from app.services.user_export import (
    export_users_list_docx,
    export_users_list_excel,
    export_users_list_pdf,
    send_users_list_email,
)


def test_mail_token_inspector_pages():
    pages = get_available_pages()
    page_vals = [p["value"] for p in pages]
    assert "user" in page_vals
    assert "template" in page_vals
    assert "batch_run" in page_vals
    assert "common" in page_vals


def test_mail_token_inspector_user_tokens():
    tokens = introspect_tokens_for_page("user")
    table_fields = tokens["table_fields"]
    system_fields = tokens["system_fields"]

    table_keys = {t["key"] for t in table_fields}
    assert "user.username" in table_keys
    assert "user.full_name" in table_keys
    assert "user.email" in table_keys
    assert "user.roles" in table_keys
    assert "user.temp_password" in table_keys

    # Kiểm tra cột nhạy cảm bị loại trừ
    assert "user.password_hash" not in table_keys
    assert "user.session_version" not in table_keys
    assert "user.failed_count" not in table_keys

    sys_keys = {s["key"] for s in system_fields}
    assert "actor.name" in sys_keys
    assert "links.login" in sys_keys
    assert "created_at" in sys_keys

    flat = get_flat_tokens_for_page("user")
    assert len(flat) == len(table_fields) + len(system_fields)


def test_mail_token_inspector_mock_payload():
    mock = get_mock_payload_for_page("user", "success")
    assert mock["user.username"] == "nguyenvana"
    assert mock["username"] == "nguyenvana"
    assert mock["user.full_name"] == "Nguyễn Văn A"
    assert mock["actor.name"] == "Quản trị viên"
    assert mock["links.login"].endswith("/login")
    assert mock["links.login"].startswith("http")


def test_user_export_excel():
    items = [
        {
            "username": "user1",
            "full_name": "Người dùng Một",
            "email": "user1@example.com",
            "roles": ["OPERATOR"],
            "is_active": "Y",
            "last_login_at": datetime.now(),
            "created_at": datetime.now(),
        }
    ]
    excel_bytes = build_users_list_excel(items, exported_by="tester", filters_info="Vai trò: OPERATOR")
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 1000
    # Header PK Zip format của .xlsx
    assert excel_bytes.startswith(b"PK")


def test_user_export_docx():
    items = [
        {
            "username": "user2",
            "full_name": "Người dùng Hai",
            "email": "user2@example.com",
            "roles": ["VIEWER"],
            "is_active": "Y",
            "last_login_at": None,
            "created_at": datetime.now(),
        }
    ]
    docx_bytes = build_users_list_docx(items, exported_by="tester")
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 500

    # Phải là file zip hợp lệ chứa word/document.xml
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as z:
        files = z.namelist()
        assert "word/document.xml" in files
        doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "DANH SÁCH TÀI KHOẢN NGƯỜI DÙNG" in doc_xml
        assert "user2" in doc_xml


def test_user_export_pdf():
    items = [
        {
            "username": "user3",
            "full_name": "Người dùng Ba",
            "email": "user3@example.com",
            "roles": ["ADMIN"],
            "is_active": "Y",
            "created_at": datetime.now(),
        }
    ]
    pdf_bytes = build_users_list_pdf(items, exported_by="tester")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0


@pytest.fixture
def mock_app_db(monkeypatch, tmp_path):
    db_file = tmp_path / "app_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res = conn.execute(
            recon_user.insert().values(
                USERNAME="superadmin",
                FULL_NAME="Super Admin",
                PASSWORD_HASH=hash_password("adminpw123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="system",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        admin_id = res.inserted_primary_key[0]

    from tests.conftest import seed_perm_basics

    seed_perm_basics(engine, {int(admin_id): ["ADMIN"]})
    admin_ctx = Ctx(user_id=admin_id, username="superadmin", full_name="Super Admin", roles=[Role.ADMIN])
    return engine, admin_ctx


def test_user_export_services(mock_app_db):
    engine, admin_ctx = mock_app_db
    res_excel = export_users_list_excel(admin_ctx)
    assert res_excel.ok
    assert res_excel.data["filename"].endswith(".xlsx")
    assert len(res_excel.data["content"]) > 0

    res_docx = export_users_list_docx(admin_ctx)
    assert res_docx.ok
    assert res_docx.data["filename"].endswith(".docx")
    assert len(res_docx.data["content"]) > 0

    res_pdf = export_users_list_pdf(admin_ctx)
    assert res_pdf.ok
    assert res_pdf.data["filename"].endswith(".pdf")
    assert len(res_pdf.data["content"]) > 0


def test_send_users_list_email(mock_app_db):
    engine, admin_ctx = mock_app_db
    with patch("app.services.user_export.get_smtp_config_internal") as mock_smtp, \
         patch("app.services.user_export.send_smtp_email") as mock_send:
        mock_smtp.return_value = {
            "host": "smtp.test.com",
            "port": 587,
            "security": "STARTTLS",
            "username": "user",
            "password": "pw",
            "from_email": "alert@reconhub.vn",
        }
        mock_send.return_value = {"ok": True, "message": "Thành công"}

        res = send_users_list_email(
            admin_ctx,
            to_emails=["manager@example.com"],
            format_types=["XLSX", "DOCX"],
            custom_subject="Test Export Users",
            notes="Please review",
        )
        assert res.ok
        assert res.data["success"] is True
        assert res.data["attachments_count"] == 2
        assert mock_send.called
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to_addrs"] == ["manager@example.com"]
        assert call_kwargs["subject"] == "Test Export Users"
        assert len(call_kwargs["attachments"]) == 2


def test_auto_send_welcome_email_on_create_user(mock_app_db):
    engine, admin_ctx = mock_app_db
    with patch("app.services.smtp_settings.get_smtp_config_internal") as mock_smtp, \
         patch("app.engine.mailer.send_smtp_email") as mock_send:
        mock_smtp.return_value = {
            "host": "smtp.gmail.com",
            "port": 587,
            "security": "STARTTLS",
            "username": "admin@reconhub.vn",
            "password": "secret",
            "from_email": "admin@reconhub.vn",
        }
        mock_send.return_value = {"ok": True, "message": "Email sent"}

        dto = UserCreateDTO(
            username="newemployee",
            full_name="Nhân viên mới",
            email="newemp@reconhub.vn",
            password="TemporaryPassword123",
            roles=["OPERATOR"],
            must_change_pw=True,
        )
        res = create_user(admin_ctx, dto, async_email=True)
        assert res.ok
        assert res.data.username == "newemployee"

        from app.services.user import _last_welcome_email_thread
        if _last_welcome_email_thread:
            _last_welcome_email_thread.join(timeout=3.0)

        # Kiểm tra đã gọi gửi mail tự động trong luồng nền
        assert mock_send.called
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["to_addrs"] == ["newemp@reconhub.vn"]
        assert "newemployee" in call_kwargs["body_html"]
        assert "Nhân viên mới" in call_kwargs["body_html"]
