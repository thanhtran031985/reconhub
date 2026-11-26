from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.context import Ctx
from app.db.metadata import metadata, recon_sso_provider, recon_user
from tests.conftest import seed_perm_basics


def _walk_components(node: Any):
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for ch in children:
            yield from _walk_components(ch)
    elif children is not None:
        yield from _walk_components(children)


@pytest.fixture
def ui_env(tmp_path, monkeypatch):
    db_file = tmp_path / "sso_ui_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("RECON_DB_URL", db_url)
    monkeypatch.setenv("RECON_SECRET_KEY", "test_secret_key_for_ui_12345678")
    get_settings.cache_clear()

    engine = create_engine(db_url)
    metadata.create_all(engine)
    seed_perm_basics(engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        res_adm = conn.execute(
            recon_user.insert().values(
                USERNAME="admin_ui",
                FULL_NAME="Admin UI",
                PASSWORD_HASH=hash_password("admin123"),
                IS_ACTIVE="Y",
                MUST_CHANGE_PW="N",
                SESSION_VERSION=1,
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_AT=now,
            )
        )
        adm_id = int(res_adm.inserted_primary_key[0])  # type: ignore[index]
        seed_perm_basics(engine, {adm_id: ["ADMIN"]}, conn=conn)

        conn.execute(
            recon_sso_provider.insert().values(
                CODE="internal",
                NAME="SSO Doanh nghiệp (Nội bộ)",
                PROVIDER_TYPE="INTERNAL",
                ICON="lucide:shield-check",
                SCOPES="openid profile email",
                JIT_ENABLED="Y",
                AUTO_LINK_EMAIL="Y",
                IS_ACTIVE="Y",
                SORT_ORDER=1,
                CREATED_BY="SYSTEM",
                CREATED_AT=now,
                UPDATED_BY="SYSTEM",
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        conn.execute(
            recon_sso_provider.insert().values(
                CODE="google",
                NAME="Đăng nhập với Google",
                PROVIDER_TYPE="OIDC",
                ICON="lucide:globe",
                AUTH_URL="https://accounts.google.com/o/oauth2/v2/auth",
                TOKEN_URL="https://oauth2.googleapis.com/token",
                CLIENT_ID="g-client-123",
                CLIENT_SECRET_ENC="enc-secret-value",
                SCOPES="openid email profile",
                ALLOWED_DOMAINS="company.com",
                JIT_ENABLED="Y",
                AUTO_LINK_EMAIL="Y",
                IS_ACTIVE="Y",
                SORT_ORDER=2,
                CREATED_BY="admin_ui",
                CREATED_AT=now,
                UPDATED_BY="admin_ui",
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )
        conn.execute(
            recon_sso_provider.insert().values(
                CODE="microsoft",
                NAME="Đăng nhập với Microsoft",
                PROVIDER_TYPE="OIDC",
                ICON="lucide:building-2",
                AUTH_URL="https://login.microsoftonline.com/t1/oauth2/v2.0/authorize",
                TOKEN_URL="https://login.microsoftonline.com/t1/oauth2/v2.0/token",
                CLIENT_ID="ms-client-456",
                SCOPES="openid profile email",
                JIT_ENABLED="Y",
                AUTO_LINK_EMAIL="Y",
                IS_ACTIVE="N",
                SORT_ORDER=3,
                CREATED_BY="admin_ui",
                CREATED_AT=now,
                UPDATED_BY="admin_ui",
                UPDATED_AT=now,
                ROW_VERSION=1,
            )
        )

    from app.services.perm import clear_perm_cache

    clear_perm_cache()
    return {
        "engine": engine,
        "admin": Ctx(user_id=adm_id, username="admin_ui", full_name="Admin UI", roles=["ADMIN"]),
    }


def test_login_page_renders_only_active_sso_buttons(ui_env, monkeypatch) -> None:
    from app.ui.pages.login import layout as login_layout

    settings = get_settings()
    monkeypatch.setattr(settings, "SSO_ENABLED", True)
    monkeypatch.setattr("app.ui.pages.login.get_current_ctx", lambda: None)
    monkeypatch.setattr("app.ui.pages.login.get_recon_engine", lambda: ui_env["engine"])

    tree = login_layout()
    hrefs = [getattr(c, "href", None) for c in _walk_components(tree) if getattr(c, "href", None)]
    assert "/auth/sso/internal/login" in hrefs
    assert "/auth/sso/google/login" in hrefs
    assert "/auth/sso/microsoft/login" not in hrefs  # đang tắt IS_ACTIVE='N'


def test_sso_flow_page_has_two_tabs_and_providers_table(ui_env, monkeypatch) -> None:
    from app.ui.pages.sso_flow import layout as sso_layout

    monkeypatch.setattr("app.ui.pages.sso_flow.get_current_ctx", lambda: ui_env["admin"])

    tree = sso_layout()
    tab_values = [
        getattr(c, "value", None)
        for c in _walk_components(tree)
        if type(c).__name__ == "TabsTab"
    ]
    assert "providers" in tab_values
    assert "architecture" in tab_values

    # Không rò rỉ encrypted secret ra DOM
    assert "enc-secret-value" not in str(tree)

    # Đảm bảo không truyền c=None hoặc ff=None (gây lỗi Mantine parse color) khi có allowed_domains
    texts = [c for c in _walk_components(tree) if type(c).__name__ == "Text"]
    for t in texts:
        props = t.to_plotly_json().get("props", {})
        if "c" in props:
            assert isinstance(props["c"], str)
        if "ff" in props:
            assert isinstance(props["ff"], str)


def test_sso_flow_save_provider_and_callback_preview(ui_env, monkeypatch) -> None:
    from app.ui.pages.sso_flow import handle_save_provider, update_callback_preview

    monkeypatch.setattr("app.ui.pages.sso_flow.get_current_ctx", lambda: ui_env["admin"])

    preview_txt, clip_txt = update_callback_preview("okta")
    assert preview_txt.endswith("/auth/sso/okta/callback")
    assert clip_txt == preview_txt

    opened, next_refresh, toast, err_alert = handle_save_provider(
        n_clicks=1,
        editing_id=None,
        code="okta",
        name="Okta Corp",
        provider_type="OIDC",
        icon="lucide:key-round",
        discovery_url="",
        issuer="https://corp.okta.com",
        auth_url="https://corp.okta.com/oauth2/v1/authorize",
        token_url="https://corp.okta.com/oauth2/v1/token",
        userinfo_url="",
        jwks_uri="https://corp.okta.com/oauth2/v1/keys",
        client_id="okta-client-1",
        client_secret="okta-secret-1",
        scopes="openid profile email",
        allowed_domains="company.com",
        sort_order=5,
        is_active=True,
        auto_link_email=True,
        jit_enabled=True,
        refresh_count=0,
    )
    assert opened is False
    assert next_refresh == 1
    assert toast is not None
    assert err_alert is None

