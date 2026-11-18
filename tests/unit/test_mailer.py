from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.engine.mailer import AttachmentSpec, build_email_message, send_smtp_email


def test_build_email_message_structure() -> None:
    attachments = [
        AttachmentSpec(
            filename="test.xlsx",
            content=b"dummy excel bytes",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        AttachmentSpec(
            filename="test.pdf",
            content=b"%PDF-dummy",
            mimetype="application/pdf",
        ),
    ]

    msg = build_email_message(
        from_addr="ReconHub <noreply@reconhub.local>",
        to_addrs=["user1@company.com", "user2@company.com"],
        subject="[ReconHub] Danh sách đối soát",
        body_html="<h1>Báo cáo</h1><p>Nội dung thử nghiệm</p>",
        body_text="Báo cáo: Nội dung thử nghiệm",
        attachments=attachments,
    )

    assert msg["From"] == "ReconHub <noreply@reconhub.local>"
    assert msg["To"] == "user1@company.com, user2@company.com"
    assert msg["Subject"] == "[ReconHub] Danh sách đối soát"

    # Kiểm tra có 2 đính kèm
    part_filenames = [p.get_filename() for p in msg.iter_attachments()]
    assert "test.xlsx" in part_filenames
    assert "test.pdf" in part_filenames


def test_send_smtp_email_starttls_success() -> None:
    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_instance) as mock_smtp_cls:
        res = send_smtp_email(
            host="smtp.example.com",
            port=587,
            security="STARTTLS",
            username="admin@example.com",
            password="secret_password",
            from_addr="noreply@example.com",
            to_addrs=["target@example.com"],
            subject="Test subject",
            body_html="<p>Test</p>",
            attachments=[],
        )

        assert res["ok"] is True
        mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=10)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("admin@example.com", "secret_password")
        mock_smtp_instance.send_message.assert_called_once()
        mock_smtp_instance.quit.assert_called_once()


def test_send_smtp_email_ssl_success() -> None:
    mock_ssl_instance = MagicMock()
    with patch("smtplib.SMTP_SSL", return_value=mock_ssl_instance) as mock_ssl_cls:
        res = send_smtp_email(
            host="smtp.example.com",
            port=465,
            security="SSL",
            username="admin@example.com",
            password="secret_password",
            from_addr="noreply@example.com",
            to_addrs=["target@example.com"],
            subject="Test SSL",
            body_html="<p>Test SSL</p>",
            attachments=[],
        )

        assert res["ok"] is True
        mock_ssl_cls.assert_called_once_with("smtp.example.com", 465, timeout=10)
        mock_ssl_instance.login.assert_called_once_with("admin@example.com", "secret_password")
        mock_ssl_instance.send_message.assert_called_once()
        mock_ssl_instance.quit.assert_called_once()


def test_send_smtp_email_auth_failure() -> None:
    import smtplib

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        res = send_smtp_email(
            host="smtp.example.com",
            port=587,
            security="STARTTLS",
            username="wrong_user",
            password="wrong_password",
            from_addr="noreply@example.com",
            to_addrs=["target@example.com"],
            subject="Test Fail",
            body_html="<p>Test Fail</p>",
        )

        assert res["ok"] is False
        assert "xác thực" in res["message"].lower() or "authentication" in res["message"].lower()
