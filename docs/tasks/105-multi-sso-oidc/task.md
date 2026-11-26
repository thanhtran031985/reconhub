# 105-multi-sso-oidc — Hỗ trợ đăng ký nhiều SSO Provider (Google, Microsoft Entra ID, OIDC bên thứ 3)

- Ngày tạo: 2026-11-26
- Giai đoạn: GĐ3
- Phụ thuộc: 102-fastapi-sso
- Nhánh git: feat/105-multi-sso-oidc

## Mục tiêu
1. Nâng cấp cơ chế SSO của ReconHub từ 1 provider nội bộ đơn lẻ sang mô hình **Multi-Provider SSO** theo chuẩn **OpenID Connect (OIDC) / OAuth 2.0** (Authorization Code + PKCE S256 + `state` + `nonce` + JWKS verification), vẫn giữ `sso_server/` (FastAPI) làm provider `INTERNAL`.
2. Cho phép Admin đăng ký, cấu hình, bật/tắt, kiểm tra Auto-Discovery cho nhiều nhà cung cấp SSO (Google, Microsoft Entra ID, OIDC bên thứ 3, FastAPI nội bộ) ngay tại tab **Nhà cung cấp SSO** trên trang `/sso-flow`.
3. Khi người dùng đăng nhập qua SSO ngoài (OIDC), lấy `email` làm tên tài khoản (`RECON_USER.USERNAME`) và tự động liên kết với tài khoản sẵn có (qua `RECON_USER_IDENTITY` hoặc khớp `EMAIL`/`USERNAME` khi `email_verified=True`), hỗ trợ `ALLOWED_DOMAINS` và JIT Provisioning an toàn (không tự cấp `ADMIN`).
4. Hiển thị danh sách nút đăng nhập SSO động trên trang `/login` theo các provider đang hoạt động.

## Phạm vi
- Database & Migration: `app/db/metadata.py`, `migrations/versions/0017_multi_sso_oidc.py`, `app/services/schema_inspector.py`, `app/services/metadata_migration.py`, regenerate `docs/data-model/schema-manifest.json` & `schema-history.json`.
- Schemas & Config: `app/schemas/sso.py`, `app/schemas/errors.py`, `app/core/config.py`, `.env.example`.
- Services: `app/services/sso_provider.py`, `app/services/sso_client.py`.
- Routes: `app/routes/auth_routes.py`.
- UI: `app/ui/pages/sso_flow.py` (chia 2 tab: Nhà cung cấp SSO & Sơ đồ kiến trúc), `app/ui/pages/login.py`.
- Tests: `tests/unit/test_sso_schema.py`, `tests/unit/test_sso_provider_service.py`, `tests/unit/test_oidc_client.py`, `tests/unit/test_sso_routes.py`, `tests/unit/test_sso_ui.py`, `tests/e2e/test_sso_multi_e2e.py`.

## Ngoài phạm vi
- Không biến `sso_server/` thành Identity Broker (làm theo Hướng 1: ReconHub là OIDC Client trực tiếp).
- Không thay đổi cấu trúc cột `RECON_USER` (không gây rủi ro alter FK bảng lõi).
- Không cài thêm thư viện ngoài `pyproject.toml`.

## Thiết kế
- Phong cách Fluent Compact theo hệ thống hiện tại (`app/ui/pages/sso_flow.py`, `app/ui/pages/login.py`, `app/ui/pages/settings.py`).

## Spec liên quan
- `docs/tasks/102-fastapi-sso/task.md`
- `.agents/rules/security.md`

## Quyết định kiến trúc
- Ghi nhận trong `docs/tasks/105-multi-sso-oidc/decisions.md`.

## Các bước
### Bước 1 — Schema DB & Migration (`RECON_SSO_PROVIDER`, `RECON_USER_IDENTITY`)
- Làm: Thêm 2 bảng vào `app/db/metadata.py`, tạo `migrations/versions/0017_multi_sso_oidc.py`, cập nhật `app/services/schema_inspector.py` và `app/services/metadata_migration.py`.
- Test viết trước: `tests/unit/test_sso_schema.py`.
- Kiểm tra: `uv run pytest tests/unit/test_sso_schema.py tests/unit/test_schema_inspector.py tests/unit/test_schema_drift.py -v`, `uv run poe schema-introspect`.

### Bước 2 — Service quản lý SSO Provider & Auto-Discovery
- Làm: Tạo `app/schemas/sso.py`, bổ sung `ErrorCode` vào `app/schemas/errors.py`, tạo `app/services/sso_provider.py` (CRUD, mã hóa Fernet secret, audit log, preset Google/MS/OIDC/Internal, Auto-Discovery).
- Test viết trước: `tests/unit/test_sso_provider_service.py`.
- Kiểm tra: `uv run pytest tests/unit/test_sso_provider_service.py -v`.

### Bước 3 — OIDC Client Engine (PKCE, Token Exchange, JWKS Verify) & Identity Sync
- Làm: Cập nhật `app/core/config.py`, `.env.example`, nâng cấp `app/services/sso_client.py` (OIDC authorize URL + PKCE, token exchange, JWKS RS256/ES256 verify bằng `pyjwt` + `cryptography`, kiểm tra `ALLOWED_DOMAINS`, lấy email làm username và tự động liên kết `RECON_USER_IDENTITY`).
- Test viết trước: `tests/unit/test_oidc_client.py`.
- Kiểm tra: `uv run pytest tests/unit/test_oidc_client.py tests/unit/test_sso_client.py -v`.

### Bước 4 — Dynamic Flask Routes (`/auth/sso/<provider_code>/...`)
- Làm: Nâng cấp `app/routes/auth_routes.py` hỗ trợ `/auth/sso/<provider_code>/login` và `/auth/sso/<provider_code>/callback` (giữ alias `/auth/sso/login` & `/auth/sso/callback`).
- Test viết trước: mở rộng `tests/unit/test_sso_routes.py`.
- Kiểm tra: `uv run pytest tests/unit/test_sso_routes.py -v`.

### Bước 5 — Giao diện `/sso-flow` (2 tab) & Trang `/login` đa nhà cung cấp
- Làm: Cập nhật `app/ui/pages/sso_flow.py` thành 2 tab (*Nhà cung cấp SSO* & *Kiến trúc & Luồng SSO*), hỗ trợ thêm/sửa/bật/tắt/xóa/tải Discovery/copy Redirect URI; cập nhật `app/ui/pages/login.py` render danh sách nút SSO động.
- Test viết trước: `tests/unit/test_sso_ui.py`, mở rộng `tests/unit/test_sso_flow_page.py`.
- Kiểm tra: `uv run pytest tests/unit/test_sso_ui.py tests/unit/test_sso_flow_page.py -v`.

### Bước 6 — Kiểm thử tổng, Data Model Explorer, Security Check & E2E
- Làm: Kiểm tra UI thực tế với Playwright, chạy `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run poe schema-introspect --check`, `uv run poe test-engine`, `uv run poe e2e`.
- Kiểm tra: Toàn bộ các lệnh trên xanh 100%.

## Chấp nhận khi
- [x] `uv run poe typecheck`, `uv run poe lint`, `uv run poe security-check`, `uv run poe test-engine` xanh
- [x] `uv run poe e2e` xanh

### Data Model Impact
- [x] Migration cập nhật (`0017_multi_sso_oidc`).
- [x] DB model cập nhật (`RECON_SSO_PROVIDER`, `RECON_USER_IDENTITY`).
- [x] `uv run poe schema-introspect` đã chạy.
- [x] `docs/data-model/schema-manifest.json` đã regenerate.
- [x] `docs/data-model/schema-history.json` đã cập nhật.
- [x] Schema drift = 0 hoặc đã ghi rõ lý do.
- [x] Page `/data-model` hiển thị thay đổi.
- [x] Regression tests pass.
