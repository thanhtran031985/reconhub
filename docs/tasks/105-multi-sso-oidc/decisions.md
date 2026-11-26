# Quyết định kỹ thuật — 105-multi-sso-oidc

## Quyết định 1: Kiến trúc Multi-Provider trực tiếp ở ReconHub (Hướng 1)
- **Ngày**: 2026-11-26
- **Quyết định**: ReconHub đóng vai trò OIDC Client trực tiếp cho Google, Microsoft Entra ID và các bên thứ 3 chuẩn OpenID Connect; vẫn giữ `sso_server/` (FastAPI) làm một provider loại `INTERNAL`.
- **Lý do**: Giảm thành phần vận hành (không biến `sso_server/` thành Identity Broker có DB riêng), Admin đăng ký và bật/tắt provider trực tiếp trong ReconHub.

## Quyết định 2: Giao diện quản lý đặt ngay trên `/sso-flow` dạng 2 tab
- **Ngày**: 2026-11-26
- **Quyết định**: Trang `/sso-flow` giữ `MENU_CODE = "sso_flow"` và chia thành 2 tab: Tab 1 *Nhà cung cấp SSO* (CRUD provider, preset Google/Microsoft/OIDC/Internal, tải Auto-Discovery, copy Redirect URI) và Tab 2 *Kiến trúc & Luồng SSO* (sơ đồ Archify hiện tại).

## Quyết định 3: Dùng email làm tài khoản người dùng (`USERNAME`) và tự động liên kết
- **Ngày**: 2026-11-26
- **Quyết định**:
  - Với provider OIDC ngoài (Google, Microsoft, OIDC bên thứ 3), lấy `email` (chuẩn hóa lowercase) làm `RECON_USER.USERNAME` và `RECON_USER.EMAIL`.
  - Tự động liên kết: ưu tiên tìm theo `(PROVIDER_CODE, SUBJECT)` trong `RECON_USER_IDENTITY`; nếu chưa có và `email_verified=True` (hoặc provider nội bộ tin cậy), tự động khớp `RECON_USER` có `EMAIL == email` hoặc `USERNAME == email` rồi tạo bản ghi liên kết trong `RECON_USER_IDENTITY`.
  - Giữ nguyên độ dài cột `RECON_USER.USERNAME` (`String(60)`) để không đụng DDL bảng gốc có nhiều khóa ngoại; nếu email hiếm gặp dài >60 ký tự sẽ rút gọn an toàn kèm hậu tố hash ngắn cho `USERNAME` trong khi vẫn lưu email đầy đủ ở `RECON_USER.EMAIL` (`String(200)`) và `RECON_USER_IDENTITY.EMAIL_AT_PROVIDER` (`String(200)`).
  - Với provider `INTERNAL` (`sso_server/`) khi truyền `username` nội bộ (không phải OIDC) vẫn giữ tương thích ngược cho `test_sso_client.py`.

## Quyết định 4: Dùng `pyjwt` + `cryptography` + `urllib.request` có sẵn
- **Ngày**: 2026-11-26
- **Quyết định**: Không cài thêm package ngoài `pyproject.toml`. Sử dụng `pyjwt` + `cryptography` để verify chữ ký `id_token` qua JWKS và `urllib.request` để gọi Discovery / Token / JWKS / UserInfo.
