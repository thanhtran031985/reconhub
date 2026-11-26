from __future__ import annotations

import re
from typing import Any

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from app.core.config import get_settings
from app.core.session import get_current_ctx
from app.schemas.sso import SsoProviderCreateDTO, SsoProviderResponse, SsoProviderUpdateDTO
from app.services.perm import page_gate
from app.services.sso_provider import (
    SSO_PROVIDER_PRESETS,
    create_sso_provider,
    delete_sso_provider,
    fetch_oidc_discovery,
    list_sso_providers,
    update_sso_provider,
)
from app.ui.components.alert_box import alert_box
from app.ui.components.button import button_primary, button_subtle
from app.ui.components.empty_state import empty_state
from app.ui.components.modal_confirm import modal_confirm
from app.ui.components.notification import notify_error, notify_success
from app.ui.components.page_header import page_header

try:
    dash.register_page(  # type: ignore[no-untyped-call]
        f"pages.{__name__.split('.')[-1]}",
        path="/sso-flow",
        title="Quản lý & Kiến trúc SSO — ReconHub",
    )
except Exception:
    pass

MENU_CODE = "sso_flow"


def set_sso_enabled_setting(enabled: bool) -> None:
    """Cập nhật trạng thái SSO vào cấu hình runtime và lưu bền vững vào file .env."""
    settings = get_settings()
    settings.SSO_ENABLED = enabled
    env_path = settings.PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            content = env_path.read_text(encoding="utf-8")
            val_str = "true" if enabled else "false"
            if re.search(r"^SSO_ENABLED=.*$", content, flags=re.MULTILINE):
                new_content = re.sub(
                    r"^SSO_ENABLED=.*$",
                    f"SSO_ENABLED={val_str}",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                new_content = content + f"\nSSO_ENABLED={val_str}\n"
            env_path.write_text(new_content, encoding="utf-8")
        except Exception:
            pass


def _effective_base_url() -> str:
    settings = get_settings()
    base = settings.PUBLIC_BASE_URL.strip().rstrip("/")
    if base:
        return base
    return f"http://localhost:{settings.DASH_PORT}"


def _build_callback_preview(code: str | None) -> str:
    clean = (code or "<ma>").strip().lower() or "<ma>"
    return f"{_effective_base_url()}/auth/sso/{clean}/callback"


def _render_status_badge(enabled: bool) -> dmc.Badge:
    if enabled:
        return dmc.Badge("SSO Đang Bật", color="green", variant="filled", size="sm")
    return dmc.Badge("SSO Đang Tắt (Local Only)", color="gray", variant="light", size="sm")


def render_providers_table(providers: list[SsoProviderResponse]) -> Any:
    """Render bảng danh sách nhà cung cấp SSO."""
    if not providers:
        return empty_state(
            title="Chưa có nhà cung cấp SSO nào",
            description="Đăng ký Google, Microsoft Entra ID, OIDC bên thứ 3 hoặc SSO nội bộ để người dùng đăng nhập.",
            icon="lucide:shield-plus",
        )

    rows = []
    for p in providers:
        cb_url = _build_callback_preview(p.code)
        type_badge = dmc.Badge(
            "Nội bộ" if p.provider_type == "INTERNAL" else "OIDC",
            color="blue" if p.provider_type == "INTERNAL" else "violet",
            variant="light",
            size="xs",
        )
        status_badge = dmc.Badge(
            "Hoạt động" if p.is_active else "Đang tắt",
            color="green" if p.is_active else "gray",
            variant="light",
            size="xs",
        )
        mode_badges = dmc.Group(
            [
                dmc.Badge(
                    "Auto-link" if p.auto_link_email else "Không link",
                    color="teal" if p.auto_link_email else "gray",
                    variant="outline",
                    size="xs",
                ),
                dmc.Badge(
                    "JIT" if p.jit_enabled else "No-JIT",
                    color="indigo" if p.jit_enabled else "gray",
                    variant="outline",
                    size="xs",
                ),
            ],
            gap=4,
        )
        actions = dmc.Group(
            [
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:power", width=14),
                        id={"type": "sso-prov-toggle", "id": p.id},
                        color="orange" if p.is_active else "green",
                        variant="light",
                        size="sm",
                        **{"aria-label": f"Bật/tắt {p.code}"},
                    ),
                    label="Tạm tắt" if p.is_active else "Kích hoạt",
                ),
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:pencil", width=14),
                        id={"type": "sso-prov-edit", "id": p.id},
                        color="primary",
                        variant="light",
                        size="sm",
                        **{"aria-label": f"Sửa {p.code}"},
                    ),
                    label="Chỉnh sửa",
                ),
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="lucide:trash-2", width=14),
                        id={"type": "sso-prov-delete", "id": p.id},
                        color="red",
                        variant="light",
                        size="sm",
                        disabled=(p.code == "internal"),
                        **{"aria-label": f"Xóa {p.code}"},
                    ),
                    label="Không thể xóa SSO nội bộ" if p.code == "internal" else "Xóa nhà cung cấp",
                ),
            ],
            gap=4,
            wrap="nowrap",
        )

        rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(p.code, ff="monospace", size="xs", fw=600)),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                DashIconify(icon=p.icon or "lucide:shield-check", width=15),
                                dmc.Text(p.name, size="xs", fw=500),
                            ],
                            gap="xs",
                            wrap="nowrap",
                        )
                    ),
                    dmc.TableTd(type_badge),
                    dmc.TableTd(
                        dmc.Group(
                            [
                                dmc.Text(cb_url, ff="monospace", size="xs", c="dimmed"),
                                dcc.Clipboard(content=cb_url, title="Sao chép Callback URL"),
                            ],
                            gap=4,
                            wrap="nowrap",
                        )
                    ),
                    dmc.TableTd(
                        dmc.Text(p.allowed_domains, size="xs", ff="monospace")
                        if p.allowed_domains
                        else dmc.Text("Mọi domain", size="xs", c="dimmed")
                    ),
                    dmc.TableTd(mode_badges),
                    dmc.TableTd(status_badge),
                    dmc.TableTd(actions),
                ]
            )
        )

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
        withColumnBorders=False,
        verticalSpacing="xs",
        horizontalSpacing="xs",
        children=[
            dmc.TableThead(
                dmc.TableTr(
                    [
                        dmc.TableTh("Mã", w=110),
                        dmc.TableTh("Tên hiển thị"),
                        dmc.TableTh("Loại", w=90),
                        dmc.TableTh("Callback URL"),
                        dmc.TableTh("Domain cho phép"),
                        dmc.TableTh("Đồng bộ user", w=140),
                        dmc.TableTh("Trạng thái", w=110),
                        dmc.TableTh("Thao tác", w=110),
                    ]
                )
            ),
            dmc.TableTbody(rows),
        ],
    )


def _render_provider_modal() -> dmc.Modal:
    return dmc.Modal(
        id="sso-provider-modal",
        title=dmc.Text("Đăng ký nhà cung cấp SSO", id="sso-provider-modal-title", fw=700, size="md"),
        opened=False,
        size="lg",
        radius="md",
        children=dmc.Stack(
            [
                html.Div(id="sso-form-alert-container"),
                dmc.Grid(
                    [
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-code",
                                label="Mã định danh (Code)",
                                placeholder="vd: google, microsoft, keycloak",
                                withAsterisk=True,
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=4,
                        ),
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-name",
                                label="Tên nút hiển thị trên Login",
                                placeholder="vd: Đăng nhập với Google",
                                withAsterisk=True,
                                size="xs",
                            ),
                            span=5,
                        ),
                        dmc.GridCol(
                            dmc.Select(
                                id="sso-form-type",
                                label="Loại giao thức",
                                data=[
                                    {"value": "OIDC", "label": "OIDC / OAuth 2.0"},
                                    {"value": "INTERNAL", "label": "FastAPI SSO Nội bộ"},
                                ],
                                value="OIDC",
                                allowDeselect=False,
                                size="xs",
                            ),
                            span=3,
                        ),
                    ],
                    gutter="xs",
                ),
                dmc.Paper(
                    dmc.Group(
                        [
                            dmc.Text("Redirect / Callback URL:", size="xs", fw=600),
                            dmc.Text(
                                _build_callback_preview("google"),
                                id="sso-form-callback-preview",
                                ff="monospace",
                                size="xs",
                                c="primary",
                            ),
                            dcc.Clipboard(
                                id="sso-form-callback-clipboard",
                                content=_build_callback_preview("google"),
                                title="Sao chép Callback URL",
                            ),
                        ],
                        gap="xs",
                        wrap="wrap",
                    ),
                    withBorder=True,
                    p="xs",
                    radius="sm",
                    bg="var(--surface-2)",
                ),
                dmc.Group(
                    [
                        dmc.TextInput(
                            id="sso-form-discovery-url",
                            label="OIDC Discovery URL (.well-known/openid-configuration)",
                            placeholder="https://accounts.google.com/.well-known/openid-configuration",
                            size="xs",
                            style={"flex": 1},
                            styles={"input": {"fontFamily": "monospace"}},
                        ),
                        button_subtle(
                            "Tải Discovery",
                            id="sso-fetch-discovery-btn",
                            icon="lucide:download",
                            color="primary",
                            size="xs",
                            mt="lg",
                        ),
                    ],
                    align="flex-end",
                    gap="xs",
                ),
                dmc.Grid(
                    [
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-client-id",
                                label="Client ID",
                                placeholder="Client ID từ Google / Microsoft / IdP",
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=6,
                        ),
                        dmc.GridCol(
                            dmc.PasswordInput(
                                id="sso-form-client-secret",
                                label="Client Secret",
                                placeholder="Nhập secret (để trống nếu giữ nguyên khi sửa)",
                                size="xs",
                            ),
                            span=6,
                        ),
                    ],
                    gutter="xs",
                ),
                dmc.Grid(
                    [
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-auth-url",
                                label="Authorization Endpoint URL",
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=6,
                        ),
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-token-url",
                                label="Token Endpoint URL",
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=6,
                        ),
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-jwks-uri",
                                label="JWKS URI",
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=6,
                        ),
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-userinfo-url",
                                label="UserInfo Endpoint URL (tùy chọn)",
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=6,
                        ),
                    ],
                    gutter="xs",
                ),
                dmc.Grid(
                    [
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-issuer",
                                label="Issuer",
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=6,
                        ),
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-scopes",
                                label="Scopes",
                                value="openid profile email",
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=6,
                        ),
                    ],
                    gutter="xs",
                ),
                dmc.Grid(
                    [
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-allowed-domains",
                                label="Domain email cho phép (phân cách dấu phẩy)",
                                placeholder="vd: company.com, partner.vn (để trống = mọi domain)",
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=6,
                        ),
                        dmc.GridCol(
                            dmc.TextInput(
                                id="sso-form-icon",
                                label="Icon (Lucide)",
                                value="lucide:globe",
                                size="xs",
                                styles={"input": {"fontFamily": "monospace"}},
                            ),
                            span=3,
                        ),
                        dmc.GridCol(
                            dmc.NumberInput(
                                id="sso-form-sort-order",
                                label="Thứ tự",
                                value=10,
                                min=0,
                                max=9999,
                                size="xs",
                            ),
                            span=3,
                        ),
                    ],
                    gutter="xs",
                ),
                dmc.Group(
                    [
                        dmc.Switch(id="sso-form-active", label="Kích hoạt", checked=True, size="xs"),
                        dmc.Switch(
                            id="sso-form-autolink",
                            label="Tự động liên kết email sẵn có",
                            checked=True,
                            size="xs",
                        ),
                        dmc.Switch(
                            id="sso-form-jit",
                            label="Tự động tạo tài khoản (lấy email làm username)",
                            checked=True,
                            size="xs",
                        ),
                    ],
                    gap="md",
                    wrap="wrap",
                ),
                dmc.Group(
                    [
                        button_subtle("Hủy", id="sso-form-cancel-btn", size="xs"),
                        button_primary("Lưu cấu hình", id="sso-form-save-btn", icon="lucide:save", size="xs"),
                    ],
                    justify="flex-end",
                    gap="xs",
                    mt="xs",
                ),
            ],
            gap="xs",
        ),
    )


def _render_architecture_info_cards(settings: Any) -> dmc.Stack:
    """Hiển thị thông số cấu hình nhanh và các thẻ diễn giải luồng SSO."""
    return dmc.Stack(
        [
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p="sm",
                children=dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.ThemeIcon(
                                    DashIconify(icon="lucide:sliders-horizontal", width=14),
                                    size="sm",
                                    radius="sm",
                                    color="primary",
                                    variant="light",
                                ),
                                dmc.Text("Thông số & Thử nghiệm nhanh", size="xs", fw=700),
                            ],
                            gap="xs",
                        ),
                        dmc.Group(
                            [
                                dmc.Badge(
                                    f"Server: {settings.SSO_SERVER_URL}",
                                    variant="outline",
                                    color="gray",
                                    size="xs",
                                    style={"textTransform": "none"},
                                ),
                                dmc.Badge(
                                    "Callback: /auth/sso/<mã>/callback",
                                    variant="outline",
                                    color="gray",
                                    size="xs",
                                    style={"textTransform": "none"},
                                ),
                                dmc.Badge(
                                    "TTL: 60s",
                                    variant="outline",
                                    color="gray",
                                    size="xs",
                                    style={"textTransform": "none"},
                                ),
                            ],
                            gap=6,
                            wrap="wrap",
                        ),
                        dmc.Group(
                            [
                                html.A(
                                    dmc.Button(
                                        "Thử nghiệm Đăng nhập SSO",
                                        leftSection=DashIconify(icon="lucide:log-in", width=14),
                                        color="primary",
                                        variant="light",
                                        size="xs",
                                    ),
                                    href="/auth/sso/login",
                                    target="_blank",
                                    style={"textDecoration": "none"},
                                ),
                                html.A(
                                    dmc.Button(
                                        "Mở sơ đồ đầy đủ",
                                        leftSection=DashIconify(icon="lucide:maximize-2", width=14),
                                        color="gray",
                                        variant="subtle",
                                        size="xs",
                                    ),
                                    href="/assets/sso_flow_archify.html",
                                    target="_blank",
                                    style={"textDecoration": "none"},
                                ),
                            ],
                            gap="xs",
                            wrap="wrap",
                        ),
                    ],
                    gap="xs",
                ),
            ),
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p="sm",
                children=dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.ThemeIcon(
                                    DashIconify(icon="lucide:key-round", width=14),
                                    size="sm",
                                    radius="sm",
                                    color="cyan",
                                    variant="light",
                                ),
                                dmc.Text("Single Sign-On Thực thụ", size="xs", fw=700),
                            ],
                            gap="xs",
                        ),
                        dmc.List(
                            size="xs",
                            spacing=4,
                            children=[
                                dmc.ListItem("Đăng nhập một lần tại SSO nội bộ (:9000) hoặc Google / Microsoft / OIDC"),
                                dmc.ListItem("Trình duyệt lưu cookie phiên SSO (JWT 8 giờ, HttpOnly)"),
                                dmc.ListItem("Tự động nhận diện phiên hợp lệ khi chuyển ứng dụng"),
                            ],
                        ),
                    ],
                    gap="xs",
                ),
            ),
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p="sm",
                children=dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.ThemeIcon(
                                    DashIconify(icon="lucide:shield-check", width=14),
                                    size="sm",
                                    radius="sm",
                                    color="teal",
                                    variant="light",
                                ),
                                dmc.Text("Bảo mật Back-channel & PKCE", size="xs", fw=700),
                            ],
                            gap="xs",
                        ),
                        dmc.List(
                            size="xs",
                            spacing=4,
                            children=[
                                dmc.ListItem("Nội bộ: code 1 lần (60s) xác minh qua POST /api/verify-code"),
                                dmc.ListItem("OIDC: Authorization Code + PKCE (S256), state, nonce & JWKS"),
                                dmc.ListItem("Client Secret mã hóa Fernet, không lộ qua trình duyệt"),
                            ],
                        ),
                    ],
                    gap="xs",
                ),
            ),
            dmc.Paper(
                withBorder=True,
                radius="sm",
                p="sm",
                children=dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.ThemeIcon(
                                    DashIconify(icon="lucide:users", width=14),
                                    size="sm",
                                    radius="sm",
                                    color="red",
                                    variant="light",
                                ),
                                dmc.Text("Dual-Mode, Email Auto-Link & JIT", size="xs", fw=700),
                            ],
                            gap="xs",
                        ),
                        dmc.List(
                            size="xs",
                            spacing=4,
                            children=[
                                dmc.ListItem("SSO OIDC lấy email làm tài khoản (RECON_USER.USERNAME)"),
                                dmc.ListItem("Tự động liên kết RECON_USER_IDENTITY nếu trùng email sẵn có"),
                                dmc.ListItem("Giữ form mật khẩu cục bộ cho Admin khẩn cấp khi bảo trì"),
                            ],
                        ),
                    ],
                    gap="xs",
                ),
            ),
        ],
        gap="xs",
    )


def layout() -> Any:
    ctx = get_current_ctx()
    gate = page_gate(ctx, MENU_CODE)
    if gate:
        return html.Div(
            [
                dcc.Location(id="sso-forbidden-redirect", href=gate),
                alert_box("Bạn không có quyền truy cập cấu hình SSO.", tone="crit"),
            ]
        )

    settings = get_settings()
    status_badge = _render_status_badge(settings.SSO_ENABLED)

    # Nạp danh sách provider ban đầu ngay khi render để tránh trống trước callback
    initial_table: Any
    try:
        res = list_sso_providers(ctx) if ctx else None
        if res and res.ok and res.data is not None:
            initial_table = render_providers_table(res.data)
        else:
            initial_table = alert_box(
                "Không thể tải danh sách nhà cung cấp SSO",
                res.message if res else "Chưa xác thực",
                tone="crit",
            )
    except Exception as exc:
        initial_table = alert_box("Lỗi tải nhà cung cấp SSO", str(exc), tone="crit")

    return dmc.Container(
        fluid=True,
        px="md",
        py="xs",
        children=[
            html.Div(id="sso-toast-container"),
            dcc.Store(id="sso-editing-id-store", data=None),
            dcc.Store(id="sso-deleting-id-store", data=None),
            dcc.Store(id="sso-refresh-trigger", data=0),
            page_header(
                title="Quản lý & Kiến trúc SSO",
                actions=[
                    dmc.Group(
                        [
                            dmc.Badge(
                                f"Phiên: {settings.SESSION_HOURS}h",
                                variant="outline",
                                color="gray",
                                size="sm",
                                style={"textTransform": "none"},
                            ),
                            html.Div(id="sso-status-badge-container", children=status_badge),
                            dmc.Switch(
                                id="sso-toggle-switch",
                                checked=settings.SSO_ENABLED,
                                label="Bật SSO",
                                size="sm",
                                color="primary",
                            ),
                            html.A(
                                dmc.Badge(
                                    "Mở sơ đồ toàn màn hình",
                                    leftSection=DashIconify(icon="lucide:maximize-2", width=12),
                                    color="gray",
                                    variant="light",
                                    size="sm",
                                    style={"cursor": "pointer", "textTransform": "none"},
                                ),
                                href="/assets/sso_flow_archify.html",
                                target="_blank",
                                style={"textDecoration": "none", "display": "inline-flex", "alignItems": "center"},
                            ),
                        ],
                        gap="xs",
                        align="center",
                    ),
                ],
            ),
            dmc.Tabs(
                id="sso-page-tabs",
                value="providers",
                keepMounted=False,
                mt="xs",
                children=[
                    dmc.TabsList(
                        [
                            dmc.TabsTab(
                                "Nhà cung cấp SSO",
                                value="providers",
                                leftSection=DashIconify(icon="lucide:key-round", width=14),
                            ),
                            dmc.TabsTab(
                                "Kiến trúc & Luồng SSO",
                                value="architecture",
                                leftSection=DashIconify(icon="lucide:workflow", width=14),
                            ),
                        ]
                    ),
                    dmc.TabsPanel(
                        value="providers",
                        pt="xs",
                        children=dmc.Stack(
                            [
                                dmc.Paper(
                                    withBorder=True,
                                    p="xs",
                                    radius="sm",
                                    children=dmc.Group(
                                        [
                                            dmc.Stack(
                                                [
                                                    dmc.Text(
                                                        "Đăng ký thêm Google, Microsoft Entra ID hoặc bên thứ 3 chuẩn OpenID Connect (OIDC).",
                                                        size="xs",
                                                        fw=600,
                                                    ),
                                                    dmc.Text(
                                                        "Khi người dùng đăng nhập SSO ngoài, hệ thống lấy email làm tài khoản và tự động liên kết với user sẵn có nếu trùng email.",
                                                        size="xs",
                                                        c="dimmed",
                                                    ),
                                                ],
                                                gap=2,
                                            ),
                                            dmc.Group(
                                                [
                                                    button_subtle(
                                                        "Preset Google",
                                                        id={"type": "sso-preset-btn", "preset": "google"},
                                                        icon="lucide:globe",
                                                        color="primary",
                                                        size="xs",
                                                    ),
                                                    button_subtle(
                                                        "Preset Microsoft",
                                                        id={"type": "sso-preset-btn", "preset": "microsoft"},
                                                        icon="lucide:building-2",
                                                        color="primary",
                                                        size="xs",
                                                    ),
                                                    button_subtle(
                                                        "Preset OIDC khác",
                                                        id={"type": "sso-preset-btn", "preset": "oidc"},
                                                        icon="lucide:key-round",
                                                        color="primary",
                                                        size="xs",
                                                    ),
                                                    button_primary(
                                                        "Thêm SSO mới",
                                                        id="sso-add-btn",
                                                        icon="lucide:plus",
                                                        size="xs",
                                                    ),
                                                ],
                                                gap="xs",
                                                wrap="wrap",
                                            ),
                                        ],
                                        justify="space-between",
                                        align="center",
                                        wrap="wrap",
                                        gap="sm",
                                    ),
                                ),
                                dmc.Paper(
                                    withBorder=True,
                                    radius="sm",
                                    p="xs",
                                    children=html.Div(id="sso-providers-table-container", children=initial_table),
                                ),
                            ],
                            gap="sm",
                        ),
                    ),
                    dmc.TabsPanel(
                        value="architecture",
                        pt="xs",
                        children=dmc.Grid(
                            gutter="sm",
                            align="stretch",
                            children=[
                                dmc.GridCol(
                                    span={"base": 12, "lg": 8},
                                    children=dmc.Paper(
                                        withBorder=True,
                                        radius="sm",
                                        p="xs",
                                        h="100%",
                                        style={"backgroundColor": "var(--surface)", "overflow": "hidden"},
                                        children=dmc.Stack(
                                            [
                                                dmc.Group(
                                                    [
                                                        dmc.Text(
                                                            "Sơ đồ tương tác Luồng xác thực SSO",
                                                            size="xs",
                                                            fw=700,
                                                        ),
                                                        html.A(
                                                            dmc.Badge(
                                                                "Mở chế độ Route / Lens / Export",
                                                                leftSection=DashIconify(
                                                                    icon="lucide:external-link", width=11
                                                                ),
                                                                color="primary",
                                                                variant="light",
                                                                size="xs",
                                                                style={"cursor": "pointer", "textTransform": "none"},
                                                            ),
                                                            href="/assets/sso_flow_archify.html",
                                                            target="_blank",
                                                            style={"textDecoration": "none"},
                                                        ),
                                                    ],
                                                    justify="space-between",
                                                    align="center",
                                                ),
                                                html.Iframe(
                                                    src="/assets/sso_flow_archify.html?embed=1",
                                                    id="sso-archify-frame",
                                                    style={
                                                        "width": "100%",
                                                        "aspectRatio": "1100 / 470",
                                                        "minHeight": "280px",
                                                        "border": "none",
                                                        "display": "block",
                                                        "backgroundColor": "transparent",
                                                    },
                                                ),
                                                dmc.Divider(
                                                    label="Luồng OIDC ngoài (Google / Microsoft / Bên thứ 3)",
                                                    labelPosition="left",
                                                    my=2,
                                                ),
                                                dmc.SimpleGrid(
                                                    cols={"base": 1, "sm": 2, "xl": 4},
                                                    spacing="xs",
                                                    children=[
                                                        dmc.Paper(
                                                            withBorder=True,
                                                            p="xs",
                                                            radius="sm",
                                                            bg="var(--surface-2)",
                                                            children=dmc.Stack(
                                                                [
                                                                    dmc.Badge(
                                                                        "1. Khởi tạo PKCE",
                                                                        color="blue",
                                                                        variant="light",
                                                                        size="xs",
                                                                    ),
                                                                    dmc.Text(
                                                                        "/auth/sso/<mã>/login sinh state, nonce, PKCE S256 rồi chuyển hướng tới IdP.",
                                                                        size="xs",
                                                                        c="dimmed",
                                                                    ),
                                                                ],
                                                                gap=4,
                                                            ),
                                                        ),
                                                        dmc.Paper(
                                                            withBorder=True,
                                                            p="xs",
                                                            radius="sm",
                                                            bg="var(--surface-2)",
                                                            children=dmc.Stack(
                                                                [
                                                                    dmc.Badge(
                                                                        "2. IdP xác thực",
                                                                        color="violet",
                                                                        variant="light",
                                                                        size="xs",
                                                                    ),
                                                                    dmc.Text(
                                                                        "Người dùng đăng nhập Google / Microsoft / IdP và trả code + state về callback.",
                                                                        size="xs",
                                                                        c="dimmed",
                                                                    ),
                                                                ],
                                                                gap=4,
                                                            ),
                                                        ),
                                                        dmc.Paper(
                                                            withBorder=True,
                                                            p="xs",
                                                            radius="sm",
                                                            bg="var(--surface-2)",
                                                            children=dmc.Stack(
                                                                [
                                                                    dmc.Badge(
                                                                        "3. Verify JWKS",
                                                                        color="teal",
                                                                        variant="light",
                                                                        size="xs",
                                                                    ),
                                                                    dmc.Text(
                                                                        "Server đổi token qua back-channel, kiểm tra chữ ký id_token, nonce & domain.",
                                                                        size="xs",
                                                                        c="dimmed",
                                                                    ),
                                                                ],
                                                                gap=4,
                                                            ),
                                                        ),
                                                        dmc.Paper(
                                                            withBorder=True,
                                                            p="xs",
                                                            radius="sm",
                                                            bg="var(--surface-2)",
                                                            children=dmc.Stack(
                                                                [
                                                                    dmc.Badge(
                                                                        "4. Auto-Link Email",
                                                                        color="green",
                                                                        variant="light",
                                                                        size="xs",
                                                                    ),
                                                                    dmc.Text(
                                                                        "Lấy email làm username, tự liên kết RECON_USER_IDENTITY & cấp phiên Flask.",
                                                                        size="xs",
                                                                        c="dimmed",
                                                                    ),
                                                                ],
                                                                gap=4,
                                                            ),
                                                        ),
                                                    ],
                                                ),
                                            ],
                                            gap="xs",
                                        ),
                                    ),
                                ),
                                dmc.GridCol(
                                    span={"base": 12, "lg": 4},
                                    children=_render_architecture_info_cards(settings),
                                ),
                            ],
                        ),
                    ),
                ],
            ),
            _render_provider_modal(),
            modal_confirm(
                id="sso-delete-confirm-modal",
                title="Xác nhận xóa nhà cung cấp SSO",
                description="Thao tác này sẽ xóa cấu hình nhà cung cấp SSO khỏi danh sách đăng nhập. Các tài khoản đã đồng bộ trước đó vẫn được giữ nguyên.",
                confirm_label="Xóa nhà cung cấp",
                danger=True,
            ),
        ],
    )


@callback(
    Output("sso-status-badge-container", "children"),
    Output("sso-toast-container", "children", allow_duplicate=True),
    Input("sso-toggle-switch", "checked"),
    prevent_initial_call=True,
)
def handle_toggle_sso(is_checked: bool) -> tuple[Any, Any]:
    """Xử lý bật/tắt SSO trực tiếp trên giao diện."""
    set_sso_enabled_setting(is_checked)
    badge = _render_status_badge(is_checked)
    msg = (
        "Đã kích hoạt chế độ đăng nhập SSO."
        if is_checked
        else "Đã tắt chế độ đăng nhập SSO (chỉ dùng tài khoản cục bộ)."
    )
    notif = notify_success(msg, title="Cập nhật cấu hình")
    return badge, notif


@callback(
    Output("sso-providers-table-container", "children"),
    Input("sso-refresh-trigger", "data"),
    prevent_initial_call=True,
)
def refresh_providers_table(_trigger: int) -> Any:
    ctx = get_current_ctx()
    if not ctx:
        raise PreventUpdate
    res = list_sso_providers(ctx)
    if not res.ok or res.data is None:
        return alert_box("Lỗi tải nhà cung cấp SSO", res.message or "Không thể tải dữ liệu", tone="crit")
    return render_providers_table(res.data)


@callback(
    Output("sso-form-callback-preview", "children"),
    Output("sso-form-callback-clipboard", "content"),
    Input("sso-form-code", "value"),
)
def update_callback_preview(code: str | None) -> tuple[str, str]:
    preview = _build_callback_preview(code)
    return preview, preview


@callback(
    Output("sso-provider-modal", "opened"),
    Output("sso-provider-modal-title", "children"),
    Output("sso-editing-id-store", "data"),
    Output("sso-form-code", "value"),
    Output("sso-form-code", "disabled"),
    Output("sso-form-name", "value"),
    Output("sso-form-type", "value"),
    Output("sso-form-icon", "value"),
    Output("sso-form-discovery-url", "value"),
    Output("sso-form-issuer", "value"),
    Output("sso-form-auth-url", "value"),
    Output("sso-form-token-url", "value"),
    Output("sso-form-userinfo-url", "value"),
    Output("sso-form-jwks-uri", "value"),
    Output("sso-form-client-id", "value"),
    Output("sso-form-client-secret", "value"),
    Output("sso-form-scopes", "value"),
    Output("sso-form-allowed-domains", "value"),
    Output("sso-form-sort-order", "value"),
    Output("sso-form-active", "checked"),
    Output("sso-form-autolink", "checked"),
    Output("sso-form-jit", "checked"),
    Output("sso-form-alert-container", "children", allow_duplicate=True),
    Input("sso-add-btn", "n_clicks"),
    Input({"type": "sso-preset-btn", "preset": ALL}, "n_clicks"),
    Input({"type": "sso-prov-edit", "id": ALL}, "n_clicks"),
    Input("sso-form-cancel-btn", "n_clicks"),
    prevent_initial_call=True,
)
def open_or_close_provider_modal(
    _add_clicks: int | None,
    _preset_clicks: list[int | None],
    _edit_clicks: list[int | None],
    _cancel_clicks: int | None,
) -> tuple[Any, ...]:
    if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
        raise PreventUpdate

    trig_id = dash.ctx.triggered_id
    if trig_id == "sso-form-cancel-btn":
        return (False,) + (dash.no_update,) * 22

    if trig_id == "sso-add-btn":
        return (
            True,
            "Đăng ký nhà cung cấp SSO mới",
            None,
            "",
            False,
            "",
            "OIDC",
            "lucide:globe",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "openid profile email",
            "",
            10,
            True,
            True,
            True,
            None,
        )

    if isinstance(trig_id, dict) and trig_id.get("type") == "sso-preset-btn":
        preset_key = str(trig_id.get("preset", "oidc"))
        preset = SSO_PROVIDER_PRESETS.get(preset_key, SSO_PROVIDER_PRESETS["oidc"])
        return (
            True,
            f"Đăng ký nhanh: {preset['name']}",
            None,
            preset["code"],
            False,
            preset["name"],
            preset["provider_type"],
            preset.get("icon", "lucide:globe"),
            preset.get("discovery_url", ""),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            preset.get("scopes", "openid profile email"),
            "",
            10,
            True,
            True,
            True,
            None,
        )

    if isinstance(trig_id, dict) and trig_id.get("type") == "sso-prov-edit":
        ctx = get_current_ctx()
        if not ctx:
            raise PreventUpdate
        pid = int(trig_id["id"])
        res = list_sso_providers(ctx)
        if not res.ok or not res.data:
            raise PreventUpdate
        target = next((p for p in res.data if p.id == pid), None)
        if target is None:
            raise PreventUpdate
        return (
            True,
            f"Chỉnh sửa SSO: {target.code}",
            target.id,
            target.code,
            True,
            target.name,
            target.provider_type,
            target.icon or "lucide:shield-check",
            target.discovery_url or "",
            target.issuer or "",
            target.auth_url or "",
            target.token_url or "",
            target.userinfo_url or "",
            target.jwks_uri or "",
            target.client_id or "",
            "",  # Không bao giờ đổ secret ra form
            target.scopes,
            target.allowed_domains or "",
            target.sort_order,
            target.is_active,
            target.auto_link_email,
            target.jit_enabled,
            None,
        )

    raise PreventUpdate


@callback(
    Output("sso-form-issuer", "value", allow_duplicate=True),
    Output("sso-form-auth-url", "value", allow_duplicate=True),
    Output("sso-form-token-url", "value", allow_duplicate=True),
    Output("sso-form-userinfo-url", "value", allow_duplicate=True),
    Output("sso-form-jwks-uri", "value", allow_duplicate=True),
    Output("sso-form-alert-container", "children", allow_duplicate=True),
    Input("sso-fetch-discovery-btn", "n_clicks"),
    State("sso-form-discovery-url", "value"),
    prevent_initial_call=True,
)
def handle_fetch_discovery(n_clicks: int | None, discovery_url: str | None) -> tuple[Any, ...]:
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if not ctx:
        raise PreventUpdate
    if not discovery_url or not discovery_url.strip():
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            alert_box("Thiếu Discovery URL", "Vui lòng nhập đường dẫn .well-known/openid-configuration", tone="warn"),
        )
    res = fetch_oidc_discovery(ctx, discovery_url)
    if not res.ok or not res.data:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            alert_box("Không tải được Discovery", res.message or "Lỗi kết nối", tone="crit"),
        )
    doc = res.data
    return (
        doc.get("issuer") or "",
        doc.get("auth_url") or "",
        doc.get("token_url") or "",
        doc.get("userinfo_url") or "",
        doc.get("jwks_uri") or "",
        alert_box("Đã tải cấu hình OIDC", "Các endpoint đã được điền tự động từ Discovery URL.", tone="ok"),
    )


@callback(
    Output("sso-provider-modal", "opened", allow_duplicate=True),
    Output("sso-refresh-trigger", "data", allow_duplicate=True),
    Output("sso-toast-container", "children", allow_duplicate=True),
    Output("sso-form-alert-container", "children", allow_duplicate=True),
    Input("sso-form-save-btn", "n_clicks"),
    State("sso-editing-id-store", "data"),
    State("sso-form-code", "value"),
    State("sso-form-name", "value"),
    State("sso-form-type", "value"),
    State("sso-form-icon", "value"),
    State("sso-form-discovery-url", "value"),
    State("sso-form-issuer", "value"),
    State("sso-form-auth-url", "value"),
    State("sso-form-token-url", "value"),
    State("sso-form-userinfo-url", "value"),
    State("sso-form-jwks-uri", "value"),
    State("sso-form-client-id", "value"),
    State("sso-form-client-secret", "value"),
    State("sso-form-scopes", "value"),
    State("sso-form-allowed-domains", "value"),
    State("sso-form-sort-order", "value"),
    State("sso-form-active", "checked"),
    State("sso-form-autolink", "checked"),
    State("sso-form-jit", "checked"),
    State("sso-refresh-trigger", "data"),
    prevent_initial_call=True,
)
def handle_save_provider(
    n_clicks: int | None,
    editing_id: int | None,
    code: str | None,
    name: str | None,
    provider_type: str | None,
    icon: str | None,
    discovery_url: str | None,
    issuer: str | None,
    auth_url: str | None,
    token_url: str | None,
    userinfo_url: str | None,
    jwks_uri: str | None,
    client_id: str | None,
    client_secret: str | None,
    scopes: str | None,
    allowed_domains: str | None,
    sort_order: int | float | None,
    is_active: bool,
    auto_link_email: bool,
    jit_enabled: bool,
    refresh_count: int | None,
) -> tuple[Any, Any, Any, Any]:
    if not n_clicks:
        raise PreventUpdate
    ctx = get_current_ctx()
    if not ctx:
        raise PreventUpdate

    p_type = "INTERNAL" if str(provider_type).upper() == "INTERNAL" else "OIDC"
    order_int = int(sort_order) if sort_order is not None else 10

    try:
        if editing_id is None:
            dto = SsoProviderCreateDTO(
                code=code or "",
                name=name or "",
                provider_type=p_type,  # type: ignore[arg-type]
                icon=icon,
                discovery_url=discovery_url,
                issuer=issuer,
                auth_url=auth_url,
                token_url=token_url,
                userinfo_url=userinfo_url,
                jwks_uri=jwks_uri,
                client_id=client_id,
                client_secret=client_secret,
                scopes=scopes or "openid profile email",
                allowed_domains=allowed_domains,
                jit_enabled=bool(jit_enabled),
                auto_link_email=bool(auto_link_email),
                is_active=bool(is_active),
                sort_order=order_int,
            )
            res = create_sso_provider(ctx, dto)
            success_msg = f"Đã đăng ký nhà cung cấp SSO '{dto.code}'."
        else:
            upd_dto = SsoProviderUpdateDTO(
                name=name,
                provider_type=p_type,  # type: ignore[arg-type]
                icon=icon,
                discovery_url=discovery_url or "",
                issuer=issuer or "",
                auth_url=auth_url or "",
                token_url=token_url or "",
                userinfo_url=userinfo_url or "",
                jwks_uri=jwks_uri or "",
                client_id=client_id or "",
                client_secret=client_secret,
                scopes=scopes or "openid profile email",
                allowed_domains=allowed_domains or "",
                jit_enabled=bool(jit_enabled),
                auto_link_email=bool(auto_link_email),
                is_active=bool(is_active),
                sort_order=order_int,
            )
            res = update_sso_provider(ctx, int(editing_id), upd_dto)
            success_msg = "Đã cập nhật cấu hình nhà cung cấp SSO."
    except Exception as exc:
        return (
            True,
            dash.no_update,
            dash.no_update,
            alert_box("Dữ liệu chưa hợp lệ", str(exc), tone="crit"),
        )

    if not res.ok:
        return (
            True,
            dash.no_update,
            dash.no_update,
            alert_box("Không thể lưu cấu hình", res.message or "Lỗi hệ thống", tone="crit"),
        )

    return (
        False,
        (refresh_count or 0) + 1,
        notify_success(success_msg, title="SSO Provider"),
        None,
    )


@callback(
    Output("sso-refresh-trigger", "data", allow_duplicate=True),
    Output("sso-toast-container", "children", allow_duplicate=True),
    Input({"type": "sso-prov-toggle", "id": ALL}, "n_clicks"),
    State("sso-refresh-trigger", "data"),
    prevent_initial_call=True,
)
def handle_toggle_provider(_clicks: list[int | None], refresh_count: int | None) -> tuple[Any, Any]:
    if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
        raise PreventUpdate
    trig_id = dash.ctx.triggered_id
    if not isinstance(trig_id, dict):
        raise PreventUpdate
    ctx = get_current_ctx()
    if not ctx:
        raise PreventUpdate
    pid = int(trig_id["id"])
    res_list = list_sso_providers(ctx)
    if not res_list.ok or not res_list.data:
        raise PreventUpdate
    target = next((p for p in res_list.data if p.id == pid), None)
    if target is None:
        raise PreventUpdate

    upd = update_sso_provider(ctx, pid, SsoProviderUpdateDTO(is_active=not target.is_active))
    if not upd.ok:
        return dash.no_update, notify_error(upd.message or "Không thể cập nhật trạng thái")
    state_txt = "kích hoạt" if not target.is_active else "tạm tắt"
    return (refresh_count or 0) + 1, notify_success(f"Đã {state_txt} nhà cung cấp '{target.code}'.")


@callback(
    Output("sso-delete-confirm-modal", "opened"),
    Output("sso-deleting-id-store", "data"),
    Input({"type": "sso-prov-delete", "id": ALL}, "n_clicks"),
    Input("sso-delete-confirm-modal-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def open_delete_modal(_del_clicks: list[int | None], _cancel_clicks: int | None) -> tuple[bool, Any]:
    if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
        raise PreventUpdate
    trig_id = dash.ctx.triggered_id
    if trig_id == "sso-delete-confirm-modal-cancel":
        return False, None
    if isinstance(trig_id, dict) and trig_id.get("type") == "sso-prov-delete":
        return True, int(trig_id["id"])
    raise PreventUpdate


@callback(
    Output("sso-delete-confirm-modal", "opened", allow_duplicate=True),
    Output("sso-refresh-trigger", "data", allow_duplicate=True),
    Output("sso-toast-container", "children", allow_duplicate=True),
    Input("sso-delete-confirm-modal-confirm", "n_clicks"),
    State("sso-deleting-id-store", "data"),
    State("sso-refresh-trigger", "data"),
    prevent_initial_call=True,
)
def confirm_delete_provider(
    n_clicks: int | None,
    deleting_id: int | None,
    refresh_count: int | None,
) -> tuple[bool, Any, Any]:
    if not n_clicks or deleting_id is None:
        raise PreventUpdate
    ctx = get_current_ctx()
    if not ctx:
        raise PreventUpdate
    res = delete_sso_provider(ctx, int(deleting_id))
    if not res.ok:
        return False, dash.no_update, notify_error(res.message or "Không thể xóa nhà cung cấp")
    return False, (refresh_count or 0) + 1, notify_success("Đã xóa nhà cung cấp SSO.")
