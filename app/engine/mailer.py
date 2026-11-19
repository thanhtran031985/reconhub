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
            server.ehlo()
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
            server.ehlo()
            if sec == "STARTTLS":
                server.starttls()
                server.ehlo()

        if username and password:
            try:
                server.login(username, password)
            except smtplib.SMTPServerDisconnected as exc:
                if "gmail" in host.lower():
                    return {
                        "ok": False,
                        "message": (
                            "Máy chủ Gmail từ chối xác thực (535 Bad Credentials). "
                            "Tài khoản hoặc Mật khẩu Gmail không đúng. "
                            "Lưu ý: Gmail không cho phép dùng mật khẩu tài khoản thông thường. "
                            "Bạn cần vào myaccount.google.com > Bảo mật > Mật khẩu ứng dụng (App Passwords) để tạo mã 16 ký tự, "
                            "dán vào ô Mật khẩu và bấm nút 'Lưu cài đặt' ở góc trên bên phải."
                        ),
                    }
                return {
                    "ok": False,
                    "message": f"Máy chủ đóng kết nối đột ngột khi xác thực tài khoản (kiểm tra lại username/mật khẩu): {exc}",
                }
            except smtplib.SMTPAuthenticationError as exc:
                msg_str = str(exc)
                if "535" in msg_str and "gmail" in host.lower():
                    return {
                        "ok": False,
                        "message": (
                            "Lỗi xác thực Gmail (535 Bad Credentials): Mật khẩu không đúng hoặc chưa dùng Mật khẩu ứng dụng (App Password). "
                            "Với Gmail, cần bật 'Xác minh 2 bước' trong tài khoản Google và tạo 'Mật khẩu ứng dụng' 16 ký tự để điền vào ô Mật khẩu SMTP."
                        ),
                    }
                return {"ok": False, "message": f"Lỗi xác thực tài khoản SMTP: {exc}"}

        server.send_message(msg)
        try:
            server.quit()
        except Exception:
            pass
        return {"ok": True, "message": f"Đã gửi email thành công tới {len(recipients)} người nhận."}

    except smtplib.SMTPAuthenticationError as exc:
        msg_str = str(exc)
        if "535" in msg_str and "gmail" in host.lower():
            return {
                "ok": False,
                "message": (
                    "Lỗi xác thực Gmail: Mật khẩu không đúng hoặc chưa dùng Mật khẩu ứng dụng (App Password). "
                    "Với Gmail, cần bật 'Xác minh 2 bước' trong tài khoản Google và tạo 'Mật khẩu ứng dụng' 16 ký tự để điền vào ô Mật khẩu SMTP."
                ),
            }
        return {"ok": False, "message": f"Lỗi xác thực tài khoản SMTP: {exc}"}
    except smtplib.SMTPServerDisconnected as exc:
        return {
            "ok": False,
            "message": (
                f"Máy chủ đóng kết nối đột ngột (Connection unexpectedly closed): {exc}. "
                "Vui lòng kiểm tra lại Cổng (Port 587 cho STARTTLS hoặc 465 cho SSL) và kết nối mạng."
            ),
        }
    except (smtplib.SMTPConnectError, socket.timeout, ConnectionRefusedError, OSError) as exc:
        return {"ok": False, "message": f"Không thể kết nối máy chủ SMTP ({host}:{port}): {exc}"}
    except smtplib.SMTPException as exc:
        return {"ok": False, "message": f"Lỗi giao thức SMTP: {exc}"}
    except Exception as exc:
        return {"ok": False, "message": f"Lỗi gửi email: {exc}"}
