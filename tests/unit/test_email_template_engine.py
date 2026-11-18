"""Unit tests for email template engine (token parser, renderer, built-in defaults)."""

from app.engine.email_template import (
    SUPPORTED_EMAIL_FUNCTIONS,
    get_builtin_default_template,
    get_email_function_meta,
    render_email_body,
    render_email_subject,
)


def test_render_email_subject_simple():
    pattern = "ReconHub - Danh sách cấu hình template [{{items_count}} template]"
    context = {"items_count": 15}
    subject = render_email_subject(pattern, context)
    assert subject == "ReconHub - Danh sách cấu hình template [15 template]"


def test_render_email_subject_with_spacing_and_multiple_tokens():
    pattern = "[{{env}}] Xuất template bởi {{ user_name }} lúc {{created_at}}"
    context = {
        "env": "PROD",
        "user_name": "nguyenvana",
        "created_at": "18/11/2026 10:00",
    }
    subject = render_email_subject(pattern, context)
    assert subject == "[PROD] Xuất template bởi nguyenvana lúc 18/11/2026 10:00"


def test_render_email_subject_missing_token_retains_placeholder():
    pattern = "Thông báo: {{title}} - {{missing_token}}"
    context = {"title": "Báo cáo"}
    subject = render_email_subject(pattern, context)
    assert subject == "Thông báo: Báo cáo - {{missing_token}}"


def test_render_email_body_html_tokens():
    html = """
    <div>
        <p>Kính gửi anh/chị,</p>
        <p>Hệ thống gửi danh sách gồm {{items_count}} mẫu đối soát được xuất bởi <b>{{user_name}}</b> vào lúc {{created_at}}.</p>
        <div>{{notes}}</div>
    </div>
    """
    context = {
        "items_count": 5,
        "user_name": "admin",
        "created_at": "18/11/2026 10:30",
        "notes": "<p>Ghi chú quan trọng</p>",
    }
    rendered = render_email_body(html, context)
    assert "5 mẫu đối soát" in rendered
    assert "<b>admin</b>" in rendered
    assert "18/11/2026 10:30" in rendered
    assert "<p>Ghi chú quan trọng</p>" in rendered


def test_render_email_body_files_list_as_list():
    html = "<p>Tập tin đính kèm:</p>{{files_list}}"
    context = {
        "files_list": ["templates_export.xlsx", "templates_export.docx", "templates_export.pdf"]
    }
    rendered = render_email_body(html, context)
    assert "<ul" in rendered
    assert "</ul>" in rendered
    assert "<li>templates_export.xlsx</li>" in rendered
    assert "<li>templates_export.docx</li>" in rendered
    assert "<li>templates_export.pdf</li>" in rendered


def test_render_email_body_files_list_empty():
    html = "<p>Tập tin:</p>{{files_list}}"
    context = {"files_list": []}
    rendered = render_email_body(html, context)
    assert "<em>Không có tệp đính kèm</em>" in rendered


def test_get_builtin_default_template_general_export():
    tmpl = get_builtin_default_template("GENERAL_EXPORT")
    assert tmpl["function_code"] == "GENERAL_EXPORT"
    assert "ReconHub" in tmpl["subject_pattern"]
    assert "{{module_name}}" in tmpl["subject_pattern"]
    assert "{{items_count}}" in tmpl["subject_pattern"]
    assert "body_html" in tmpl
    assert "{{user_name}}" in tmpl["body_html"]
    assert "{{files_list}}" in tmpl["body_html"]
    assert len(tmpl["available_tokens"]) >= 5


def test_get_builtin_default_template_template_list_export():
    tmpl = get_builtin_default_template("TEMPLATE_LIST_EXPORT")
    assert tmpl["function_code"] == "TEMPLATE_LIST_EXPORT"
    assert "ReconHub" in tmpl["subject_pattern"]
    assert "{{items_count}}" in tmpl["subject_pattern"]
    assert "body_html" in tmpl
    assert "{{user_name}}" in tmpl["body_html"]
    assert "{{files_list}}" in tmpl["body_html"]
    assert len(tmpl["available_tokens"]) >= 4
    # Kiểm tra mock context hoạt động tốt để render preview
    rendered_subject = render_email_subject(tmpl["subject_pattern"], tmpl["mock_context"])
    rendered_body = render_email_body(tmpl["body_html"], tmpl["mock_context"])
    assert "{{" not in rendered_subject
    assert "{{" not in rendered_body


def test_get_builtin_default_template_run_result_export():
    tmpl = get_builtin_default_template("RUN_RESULT_EXPORT")
    assert tmpl["function_code"] == "RUN_RESULT_EXPORT"
    assert "mock_context" in tmpl
    assert len(tmpl["available_tokens"]) >= 4


def test_get_builtin_default_template_unknown_fallback():
    tmpl = get_builtin_default_template("UNKNOWN_FUNCTION_XYZ")
    assert tmpl["function_code"] == "UNKNOWN_FUNCTION_XYZ"
    assert tmpl["name"]
    assert tmpl["subject_pattern"]
    assert tmpl["body_html"]


def test_list_supported_email_functions():
    assert len(SUPPORTED_EMAIL_FUNCTIONS) >= 3
    codes = [f["code"] for f in SUPPORTED_EMAIL_FUNCTIONS]
    assert "TEMPLATE_LIST_EXPORT" in codes
    assert "RUN_RESULT_EXPORT" in codes
    assert "REPORT_EXPORT" in codes

    meta = get_email_function_meta("TEMPLATE_LIST_EXPORT")
    assert meta is not None
    assert meta["label"] == "Xuất danh sách Template"
