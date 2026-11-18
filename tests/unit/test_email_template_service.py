"""Unit tests for email template service."""

import pytest
from sqlalchemy import create_engine

from app.core.context import Ctx
from app.db.metadata import metadata
from app.schemas.errors import ErrorCode
from app.services.email_template import (
    get_email_template_for_function,
    list_supported_functions,
    reset_email_template_to_default,
    save_email_template,
)
from tests.conftest import seed_perm_basics


@pytest.fixture(autouse=True)
def isolated_tmpl_db(tmp_path, monkeypatch):
    """Cách ly database cho bài test Email Template để không ghi đè dữ liệu thật trong data/recon_app.db."""
    db_file = tmp_path / "email_tmpl_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url)
    metadata.create_all(engine)
    seed_perm_basics(engine)
    monkeypatch.setattr("app.services.email_template.get_recon_engine", lambda: engine)
    yield engine


@pytest.fixture
def admin_ctx() -> Ctx:
    return Ctx(user_id=1, username="admin_user", full_name="Admin User", roles=["ADMIN"])


@pytest.fixture
def operator_ctx() -> Ctx:
    return Ctx(user_id=2, username="operator_user", full_name="Operator User", roles=["OPERATOR"])


def test_list_supported_functions(admin_ctx):
    res = list_supported_functions(admin_ctx)
    assert res.ok
    assert len(res.data) >= 3
    codes = [f["code"] for f in res.data]
    assert "TEMPLATE_LIST_EXPORT" in codes


def test_get_email_template_for_function_fallback(admin_ctx):
    # Function chưa lưu trong DB (hoặc chạy test mới) -> fallback built-in
    res = get_email_template_for_function(admin_ctx, "REPORT_EXPORT")
    assert res.ok
    tmpl = res.data
    assert tmpl["function_code"] == "REPORT_EXPORT"
    assert "ReconHub" in tmpl["subject_pattern"]
    assert "body_html" in tmpl
    assert len(tmpl["available_tokens"]) > 0


def test_save_email_template_requires_admin(operator_ctx):
    res = save_email_template(
        operator_ctx,
        {
            "function_code": "TEMPLATE_LIST_EXPORT",
            "subject_pattern": "Custom Subject",
            "body_html": "<p>Custom Body</p>",
        },
    )
    assert not res.ok
    assert res.code == ErrorCode.FORBIDDEN


def test_save_email_template_and_retrieve(admin_ctx):
    custom_subject = "Tiêu đề tùy biến [{{items_count}} template]"
    custom_body = "<div>Nội dung tùy biến bởi {{user_name}}</div>"

    save_res = save_email_template(
        admin_ctx,
        {
            "function_code": "TEMPLATE_LIST_EXPORT",
            "name": "Mẫu xuất danh sách tùy biến",
            "subject_pattern": custom_subject,
            "body_html": custom_body,
        },
    )
    assert save_res.ok
    assert save_res.data["subject_pattern"] == custom_subject

    # Đọc lại
    get_res = get_email_template_for_function(admin_ctx, "TEMPLATE_LIST_EXPORT")
    assert get_res.ok
    assert get_res.data["subject_pattern"] == custom_subject
    assert get_res.data["body_html"] == custom_body


def test_reset_email_template_to_default(admin_ctx):
    # Lưu custom trước
    save_email_template(
        admin_ctx,
        {
            "function_code": "TEMPLATE_LIST_EXPORT",
            "subject_pattern": "Temp Subject",
            "body_html": "<p>Temp Body</p>",
        },
    )

    # Reset về mặc định
    reset_res = reset_email_template_to_default(admin_ctx, "TEMPLATE_LIST_EXPORT")
    assert reset_res.ok

    # Đọc lại -> phải là subject mặc định
    get_res = get_email_template_for_function(admin_ctx, "TEMPLATE_LIST_EXPORT")
    assert get_res.ok
    assert "ReconHub - Danh sách cấu hình template" in get_res.data["subject_pattern"]
