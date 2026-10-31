# 01-auth-users — Người dùng trên RECON_APP, đăng nhập, phân quyền 4 vai trò

- Ngày tạo: 2026-10-31
- Giai đoạn: GĐ0
- Phụ thuộc: 00
- Nhánh git: feat/01-auth-users

## Mục tiêu
Người dùng đăng nhập bằng username/mật khẩu lưu trong RECON_APP; mọi page và service biết người dùng và vai trò; Admin quản lý người dùng qua service; có lệnh tạo Admin đầu tiên.

## Phạm vi
- app/core/auth.py: argon2id (hash, verify, needs_rehash); login (khóa sau LOGIN_MAX_FAILS, LOCKED_UNTIL, RECON_LOGIN_LOG, thông báo chung); phiên Flask (user_id, session_version, hết hạn SESSION_HOURS); kiểm SESSION_VERSION mỗi request (cache 60s)
- Flask before_request: chưa đăng nhập → /login (trừ /login, /health, /assets, tài nguyên Dash cần cho trang login); kiểm Origin cho /_dash-update-component; MUST_CHANGE_PW → /login?step=change
- `Ctx` (user_id, username, full_name, roles) + `require_role(ctx, *roles)`
- ServiceResult + app/schemas/errors.py; decorator `@service` chuyển exception thành INTERNAL_ERROR có request_id
- services/user.py theo spec 05 (list, create, update, set_active, reset_password, unlock, login_log, change_password); LAST_ADMIN; mật khẩu chỉ cần không rỗng
- Audit helper `audit.write(conn, …)` cùng transaction; audit người dùng ghi PASSWORD_HASH '***'
- app/cli.py: create-admin (từ chối nếu đã có Admin trừ --force), reset-password; seed 4 user mẫu (chỉ dev/test)
- Page /login (đăng nhập + bước đổi mật khẩu bắt buộc), /account (đổi mật khẩu), /forbidden; menu người dùng (Tài khoản, Đăng xuất) ở khung tối thiểu

## Ngoài phạm vi
- Màn Người dùng đầy đủ (task 08)
- SSO/Entra ID

## Thiết kế
- designs/components/Screen10-Login
- designs/components/AppShell (menu người dùng)

## Spec liên quan
- docs/specs/06_security_ops.md mục 1, 5
- docs/specs/05_services_pages.md mục 1–3
- docs/specs/02 mục 1

## Quyết định kiến trúc
- Người dùng trong RECON_APP, không SSO (ADR-010)
- Mật khẩu tự do, không rỗng

## Các bước
### Bước 1 — ServiceResult và mã lỗi
- Làm: errors.py, @service
- Test viết trước: ValidationError → VALIDATION_ERROR tiếng Việt kèm path; lỗi bất ngờ → INTERNAL_ERROR không lộ stack
- Kiểm tra: `uv run poe test`

### Bước 2 — Băm mật khẩu + login + khóa
- Làm: auth.py, RECON_LOGIN_LOG
- Test viết trước: sai 5 lần → ACCOUNT_LOCKED 15 phút; hết hạn khóa đăng nhập lại được; user không tồn tại và sai mật khẩu cùng thông báo; INACTIVE; rehash
- Kiểm tra: `uv run poe test`

### Bước 3 — Phiên + before_request
- Làm: Flask session, SESSION_VERSION, chặn route
- Test viết trước: Flask test client: chưa đăng nhập → /login; đổi mật khẩu → phiên cũ bị đăng xuất; MUST_CHANGE_PW chặn page; Origin lạ → 403
- Kiểm tra: `uv run poe test`

### Bước 4 — Service user + LAST_ADMIN + audit
- Làm: user.py, audit
- Test viết trước: tạo/sửa/khóa/đặt lại mật khẩu; USERNAME_EXISTS; PASSWORD_EMPTY; LAST_ADMIN; audit không chứa hash; quyền từng role
- Kiểm tra: `uv run poe test`

### Bước 5 — CLI + seed
- Làm: create-admin, reset-password, seed
- Test viết trước: test CLI bằng input giả
- Kiểm tra: `uv run python -m app.cli create-admin`; `uv run poe db-seed` 2 lần không trùng

### Bước 6 — UI login, đổi mật khẩu, tài khoản
- Làm: Pages theo Screen10
- Test viết trước: e2e: đăng nhập đúng/sai, khóa, đổi mật khẩu lần đầu, đăng xuất
- Kiểm tra: `uv run poe e2e`

## Chấp nhận khi
- [ ] Đăng nhập, khóa tạm, đổi mật khẩu, đăng xuất hoạt động
- [ ] Viewer gọi service Admin nhận FORBIDDEN
- [ ] Không có mật khẩu rõ trong DB, log, audit
- [ ] `uv run poe typecheck`, `uv run poe lint`, `uv run poe test` xanh

## Câu hỏi mở
- —
