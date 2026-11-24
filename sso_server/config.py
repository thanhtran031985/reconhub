from __future__ import annotations

import os

SSO_HOST: str = os.getenv("SSO_HOST", "0.0.0.0")
SSO_PORT: int = int(os.getenv("SSO_PORT", "9000"))
SSO_JWT_SECRET: str = os.getenv("SSO_JWT_SECRET", "reconhub_sso_internal_jwt_secret_key_32chars_minimum!")
SSO_CLIENT_SECRET: str = os.getenv("SSO_CLIENT_SECRET", "internal_sso_secret")
SSO_COOKIE_NAME: str = "company_sso_session"
SSO_CODE_TTL_SECONDS: int = 60
SSO_SESSION_HOURS: int = 8

# Whitelist các host được phép redirect để phòng chống lỗ hổng Open Redirect
ALLOWED_REDIRECT_HOSTS: list[str] = [
    "localhost:8050",
    "127.0.0.1:8050",
    "localhost:9000",
    "127.0.0.1:9000",
    "reconhub.company.local",
]
