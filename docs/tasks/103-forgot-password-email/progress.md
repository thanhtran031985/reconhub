# Tiến độ — 103-forgot-password-email

Trạng thái: ✅

| Bước | Nội dung | Trạng thái | Ngày | Commit |
|---|---|---|---|---|
| 1 | Schema & Database Migration (`RECON_PASSWORD_RESET_TOKEN`) | ✅ | 2026-11-24 | pending |
| 2 | Service Quên & Đặt lại mật khẩu (Backend Logic) | ✅ | 2026-11-24 | pending |
| 3 | Giao diện Yêu cầu đặt lại mật khẩu (`/forgot-password`) | ✅ | 2026-11-24 | pending |
| 4 | Giao diện Đặt lại mật khẩu (`/reset-password`) & Hoàn tất | ✅ | 2026-11-24 | pending |
| 5 | E2E Testing, Data Model Validation & Hoàn tất | ✅ | 2026-11-25 | pending |

## Nhật ký
- **2026-11-24**: Hoàn thiện Bước 1–4 (`RECON_PASSWORD_RESET_TOKEN`, migration `0016_password_reset_token`, service `password_reset.py`, trang `/forgot-password`, `/reset-password` và liên kết tại `/login`).
- **2026-11-25**:
  - Whitelist `/forgot-password` và `/reset-password` trong `auth_and_security_guard` (`app/ui/app.py`) và ẩn AppShell (sidebar menu/header) trên 2 route này trong `app/ui/layout/shell.py`.
  - Bổ sung chặn đặt lại mật khẩu cho tài khoản SSO (`!sso_managed_...`), xóa cache phiên tức thời (`invalidate_user_session_cache`), cập nhật `PW_CHANGED_AT`, escape HTML email, truyền `ip`/`base_url` thực tế và chuẩn hóa token giao diện.
  - Xếp `RECON_PASSWORD_RESET_TOKEN` vào phân hệ `core` trong `schema_inspector.py`, regenerate manifest (50 bảng) và cập nhật test Data Model Explorer.
  - Đã kiểm tra `uv run poe lint`, `uv run poe typecheck`, `uv run poe security-check`, `uv run poe schema-introspect --check`, `uv run poe e2e` (38/38 passed), unit/integration liên quan (116/116 + 19/19 passed).
