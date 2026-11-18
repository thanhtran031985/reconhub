from __future__ import annotations

import smtplib
import socket
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any


@dataclass
class AttachmentSpec:
    filename: str
    content: bytes
    mimetype: str = "application/octet-stream"


def build_email_message(
    from_addr: str,
    to_addrs: list[str],
    subject: str,
    body_html: str,
    body_text: str | None = None,
    attachments: list[AttachmentSpec] | None = None,
) -> EmailMessage:
    """Tạo EmailMessage MIME multipart UTF-8 chuẩn kèm HTML và file đính kèm."""
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject

    # Plain text fallback
    fallback_text = (
        body_text if body_text is not None else body_html.replace("<br>", "\n").replace("<p>", "").replace("</p>", "\n")
    )
    msg.set_content(fallback_text)
    msg.add_alternative(body_html, subtype="html")

    if attachments:
        for att in attachments:
            mimetype = att.mimetype or "application/octet-stream"
            if "/" in mimetype:
                maintype, subtype = mimetype.split("/", 1)
            else:
                maintype, subtype = "application", "octet-stream"

            msg.add_attachment(
                att.content,
                maintype=maintype,
                subtype=subtype,
                filename=att.filename,
            )

    return msg


def send_smtp_email(
    host: str,
    port: int,
    security: str = "STARTTLS",  # "STARTTLS" | "SSL" | "NONE"
    username: str = "",
    password: str = "",
    from_addr: str = "",
    to_addrs: list[str] | None = None,
    subject: str = "",
    body_html: str = "",
    body_text: str | None = None,
    attachments: list[AttachmentSpec] | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    """Kết nối máy chủ SMTP và gửi email. Trả về dict {ok: bool, message: str}."""
    recipients = to_addrs or []
    if not host:
        return {"ok": False, "message": "Chưa cấu hình máy chủ SMTP (Host trống)."}
    if not recipients:
        return {"ok": False, "message": "Danh sách người nhận (To) trống."}

    sender = from_addr or username or "no-reply@reconhub.local"
    sec = (security or "STARTTLS").strip().upper()

    try:
        msg = build_email_message(
            from_addr=sender,
            to_addrs=recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachments=attachments,
        )

        server: smtplib.SMTP | smtplib.SMTP_SSL
        if sec == "SSL" or port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
            if sec == "STARTTLS":
                server.starttls()

        if username and password:
            server.login(username, password)

        server.send_message(msg)
        server.quit()
        return {"ok": True, "message": f"Đã gửi email thành công tới {len(recipients)} người nhận."}

    except smtplib.SMTPAuthenticationError as exc:
        return {"ok": False, "message": f"Lỗi xác thực tài khoản SMTP: {exc}"}
    except (smtplib.SMTPConnectError, socket.timeout) as exc:
        return {"ok": False, "message": f"Không thể kết nối máy chủ SMTP ({host}:{port}): {exc}"}
    except smtplib.SMTPException as exc:
        return {"ok": False, "message": f"Lỗi giao thức SMTP: {exc}"}
    except Exception as exc:
        return {"ok": False, "message": f"Lỗi gửi email: {exc}"}
