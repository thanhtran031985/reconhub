# Implementation Plan — 105-multi-sso-oidc

## 1. Phạm vi & Kiến trúc tổng thể
- Giữ nguyên `sso_server/` (FastAPI) làm một provider loại `INTERNAL` để tương thích ngược.
- Bổ sung hệ thống đăng ký nhiều SSO Provider (`Google`, `Microsoft Entra ID`, `OIDC bên thứ 3`, `INTERNAL`) lưu trong `RECON_APP`, hỗ trợ Auto-Discovery (`.well-known/openid-configuration`), PKCE (`S256`), `state`, `nonce`, xác thực chữ ký `id_token` qua JWKS, và bảng ánh xạ danh tính `RECON_USER_IDENTITY` (`provider_code + subject -> user_id`).
- Bảo mật: `CLIENT_SECRET` mã hóa bằng `encrypt_secret()` (`app/core/crypto.py`), không trả secret ra UI/`dcc.Store`, kiểm soát quyền `ADMIN` + ghi `RECON_AUDIT_LOG`, hỗ trợ `ALLOWED_DOMAINS` chặn email cá nhân khi bật Google/MS.
- Quyết định đã chốt của người dùng:
  1. Tạo task mới `105-multi-sso-oidc`.
  2. Giao diện đăng ký SSO đặt ngay trên trang `/sso-flow`, chia 2 tab (*Nhà cung cấp SSO* và *Kiến trúc & Luồng SSO*).
  3. Khi người dùng đăng nhập SSO ngoài, lấy `email` làm tài khoản (`RECON_USER.USERNAME`) và tự động liên kết với tài khoản sẵn có.

## 2. Các bước thực hiện
- **Bước 1 — Schema DB & Migration (`RECON_SSO_PROVIDER`, `RECON_USER_IDENTITY`)**
  - Sửa: `app/db/metadata.py`, `app/services/schema_inspector.py`, `app/services/metadata_migration.py`.
  - Tạo: `migrations/versions/0017_multi_sso_oidc.py` (tương thích SQLite batch mode và Oracle).
  - Test viết trước: `tests/unit/test_sso_schema.py`.
  - Kiểm tra: `uv run pytest tests/unit/test_sso_schema.py tests/unit/test_schema_inspector.py tests/unit/test_schema_drift.py -v`, `uv run poe schema-introspect`.

- **Bước 2 — Service quản lý SSO Provider & Auto-Discovery**
  - Sửa: `app/schemas/errors.py`, tạo `app/schemas/sso.py`.
  - Tạo: `app/services/sso_provider.py` (CRUD provider chỉ `ADMIN`, preset `google` / `microsoft` / `oidc` / `internal`, fetch OIDC Discovery JSON, mã hóa/giải mã secret, ghi `RECON_AUDIT_LOG`, `list_active_login_providers()` không chứa secret).
  - Test viết trước: `tests/unit/test_sso_provider_service.py`.
  - Kiểm tra: `uv run pytest tests/unit/test_sso_provider_service.py -v`.

- **Bước 3 — OIDC Client Engine (PKCE, Token Exchange, JWKS Verify) & Identity Sync**
  - Sửa: `app/services/sso_client.py`, `app/core/config.py`, `.env.example` (thêm `PUBLIC_BASE_URL`).
  - Test viết trước: `tests/unit/test_oidc_client.py`.
  - Kiểm tra: `uv run pytest tests/unit/test_oidc_client.py tests/unit/test_sso_client.py -v`.

- **Bước 4 — Dynamic Flask Routes (`/auth/sso/<provider_code>/...`)**
  - Sửa: `app/routes/auth_routes.py`.
  - Test viết trước: mở rộng `tests/unit/test_sso_routes.py`.
  - Kiểm tra: `uv run pytest tests/unit/test_sso_routes.py -v`.

- **Bước 5 — Giao diện `/sso-flow` (2 tab) & Trang `/login` đa nhà cung cấp**
  - Sửa: `app/ui/pages/login.py`, `app/ui/pages/sso_flow.py`.
  - Test viết trước: `tests/unit/test_sso_ui.py`, mở rộng `tests/unit/test_sso_flow_page.py`.
  - Kiểm tra: `uv run pytest tests/unit/test_sso_ui.py tests/unit/test_sso_flow_page.py -v`.

- **Bước 6 — Hoàn thiện, Kiểm thử tổng, Data Model Explorer & E2E**
  - Chạy toàn bộ: `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run poe schema-introspect --check`, `uv run poe test-engine`, `uv run poe e2e`.
