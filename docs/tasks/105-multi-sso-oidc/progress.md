# Tiến độ — 105-multi-sso-oidc

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Schema DB & Migration (`RECON_SSO_PROVIDER`, `RECON_USER_IDENTITY`) | ✅ | 2026-11-26 | |
| 2 | Service quản lý SSO Provider & Auto-Discovery | ✅ | 2026-11-26 | |
| 3 | OIDC Client Engine (PKCE, JWKS) & Identity Sync (email + auto-link) | ✅ | 2026-11-26 | |
| 4 | Dynamic Flask Routes (`/auth/sso/<provider_code>/...`) | ✅ | 2026-11-26 | |
| 5 | Giao diện `/sso-flow` (2 tab) & `/login` đa nhà cung cấp | ✅ | 2026-11-26 | |
| 6 | Kiểm thử tổng, Data Model Explorer, Security Check & E2E | ✅ | 2026-11-26 | |

## Nhật ký
- 2026-11-26:
  - Tạo task `105-multi-sso-oidc` và nhánh `feat/105-multi-sso-oidc`.
  - Bước 1: Thêm bảng `RECON_SSO_PROVIDER`, `RECON_USER_IDENTITY` vào `app/db/metadata.py`, tạo migration `migrations/versions/0017_multi_sso_oidc.py` (kèm seed provider `internal`), cập nhật `schema_inspector.py` & `metadata_migration.py`, chạy `uv run poe db-migrate` và `uv run poe schema-introspect` (52 bảng, 0 drift).
  - Bước 2: Tạo `app/schemas/sso.py`, `app/services/sso_provider.py` (CRUD `ADMIN`, Fernet secret encryption, `RECON_AUDIT_LOG`, preset Google/Microsoft/OIDC/Internal, Auto-Discovery `.well-known/openid-configuration`).
  - Bước 3: Nâng cấp `app/services/sso_client.py` hỗ trợ OIDC Authorization Code + PKCE S256 + verify `id_token` JWKS (RS256/ES256) + `nonce` + `ALLOWED_DOMAINS`, lấy email làm `RECON_USER.USERNAME` và tự động liên kết `RECON_USER_IDENTITY`. Thêm `PUBLIC_BASE_URL` vào `app/core/config.py` và `.env.example`.
  - Bước 4: Nâng cấp `app/routes/auth_routes.py` hỗ trợ `/auth/sso/<provider_code>/login` và `/callback` (giữ alias `/auth/sso/login` & `/auth/sso/callback`).
  - Bước 5: Cập nhật `app/ui/pages/sso_flow.py` thành 2 tab (*Nhà cung cấp SSO* & *Kiến trúc & Luồng SSO*) với đầy đủ CRUD/Preset/Discovery/Copy Callback URL; cập nhật `app/ui/pages/login.py` render động các nút SSO đang bật.
  - Bước 6: Cập nhật test Data Model Explorer (`test_schema_inspector.py`, `test_page_data_model.py`); chạy `typecheck`, `lint`, `security-check` (6/6), `schema-introspect --check`, `e2e` (39/39) và toàn bộ test SSO + Data Model.
  - Lưu ý việc làm tay (nếu dùng Oracle): chạy `uv run poe test-oracle` qua VPN khi kiểm thử tích hợp Oracle và chạy `uv run poe db-migrate` trên môi trường đích.
