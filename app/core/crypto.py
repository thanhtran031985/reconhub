from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _get_fernet_key() -> bytes:
    """Tạo khóa 32-byte url-safe base64 từ RECON_SECRET_KEY."""
    settings = get_settings()
    raw_key = settings.RECON_SECRET_KEY.encode("utf-8")
    digest = hashlib.sha256(raw_key).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plain: str) -> str:
    """Mã hóa chuỗi bí mật (như mật khẩu Data Source) bằng Fernet."""
    if not plain:
        return ""
    f = Fernet(_get_fernet_key())
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(enc: str) -> str:
    """Giải mã chuỗi bí mật đã được mã hóa bằng Fernet."""
    if not enc:
        return ""
    f = Fernet(_get_fernet_key())
    return f.decrypt(enc.encode("utf-8")).decode("utf-8")
